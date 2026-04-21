import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_DIR = path.resolve(PLUGIN_DIR, "../..");
const SCRIPT_PATH = path.join(REPO_DIR, "scripts", "transcribe-url.py");
const DEFAULT_EMAIL = "igor.arsenin@gmail.com";
const COMMAND_TIMEOUT_MS = 15 * 60 * 1000;
const PYTHON_IMPORT_CHECK = "import requests, bs4; print('ok')";

const OPENCLAW_CLI_CANDIDATES = [
    "/opt/homebrew/bin/openclaw",
    "/usr/local/bin/openclaw",
];

function resolveOpenclawCli() {
    for (const candidate of OPENCLAW_CLI_CANDIDATES) {
        if (fs.existsSync(candidate)) {
            return candidate;
        }
    }
    return "openclaw";
}

// Quick URL classification — do we expect a pre-made transcript (fast path,
// usually seconds) or do we have to download audio and send it to a model
// (slow path, several minutes)?
function estimateTranscribeSpeed(url) {
    const lc = url.toLowerCase();
    if (/(?:^|\/\/)(?:www\.)?(?:youtube\.com|youtu\.be|m\.youtube\.com)\b/u.test(lc)) {
        return { fast: true };
    }
    return {
        fast: false,
        ackText:
            "Got it — transcribing now. This source has no pre-made captions, so I'll "
            + "download the audio and run it through Gemini. Expect ~3–10 min depending "
            + "on episode length. You'll get the email + a summary here when it's done.",
    };
}

// WhatsApp senderId is a JID (`19179752041@s.whatsapp.net` or
// `19179752041@c.us`). `openclaw message send --target` expects E.164
// (`+19179752041`). Normalize so the ack actually lands.
function normalizeWhatsappTarget(raw) {
    const value = typeof raw === "string" ? raw.trim() : "";
    if (!value) {
        return null;
    }
    if (value.startsWith("+") && /^\+\d{6,15}$/u.test(value)) {
        return value;
    }
    const atIdx = value.indexOf("@");
    const localPart = atIdx === -1 ? value : value.slice(0, atIdx);
    const digits = localPart.replace(/[^\d]/gu, "");
    if (!digits || digits.length < 6 || digits.length > 15) {
        return null;
    }
    return `+${digits}`;
}

function sendInterimAck(text, rawTarget, logger) {
    if (!text) {
        return { ok: false, reason: "no-text" };
    }
    const target = normalizeWhatsappTarget(rawTarget);
    if (!target) {
        return { ok: false, reason: `unparseable-target:${rawTarget ?? "<none>"}` };
    }
    try {
        const child = spawn(
            resolveOpenclawCli(),
            [
                "message", "send",
                "--channel", "whatsapp",
                "--target", target,
                "--message", text,
            ],
            {
                cwd: REPO_DIR,
                stdio: ["ignore", "pipe", "pipe"],
            },
        );
        let stderr = "";
        child.stderr?.on("data", (chunk) => { stderr += String(chunk); });
        child.on("error", (err) => {
            logger?.warn?.(`transcribe-command ack spawn error: ${err.message}`);
        });
        child.on("close", (code) => {
            if (code !== 0) {
                logger?.warn?.(`transcribe-command ack exited code=${code} target=${target} stderr=${stderr.trim().slice(0, 300)}`);
            } else {
                logger?.info?.(`transcribe-command ack delivered to ${target}`);
            }
        });
        return { ok: true, target };
    } catch (error) {
        return { ok: false, reason: error instanceof Error ? error.message : String(error) };
    }
}

function parseDotEnv(dotenvPath) {
    const env = {};
    if (!fs.existsSync(dotenvPath)) {
        return env;
    }
    for (const line of fs.readFileSync(dotenvPath, "utf8").split(/\r?\n/u)) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) {
            continue;
        }
        const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/u);
        if (!match) {
            continue;
        }
        let value = match[2] ?? "";
        if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
            value = value.slice(1, -1);
        }
        env[match[1]] = value.replace(/\\n/g, "\n");
    }
    return env;
}

function sanitizeText(value) {
    return typeof value === "string" ? value.trim() : "";
}

function extractTranscribeUrl(body) {
    const trimmed = sanitizeText(body);
    if (!trimmed) {
        return null;
    }
    const match = trimmed.match(/(?:^|\s)\/transcribe(?:\s+(\S+))?(?:\s|$)/isu);
    if (!match) {
        return null;
    }
    const rawArg = sanitizeText(match[1] ?? "");
    return rawArg || "";
}

function buildReply(result) {
    const summary = sanitizeText(result.whatsapp_summary) || sanitizeText(result.title) || "Transcript request finished.";
    if (result.transcript_available) {
        if (result.email_sent) {
            return `${summary}\n\nFull transcript emailed to Igor.`;
        }
        return `${summary}\n\nI got the transcript, but the email send failed.`;
    }
    return `${summary}\n\nI couldn't get a full transcript, so I didn't send an email.`;
}

function resolvePythonCommand(env) {
    const candidates = [
        env.PYTHON3_PATH,
        env.PYTHON_PATH,
        "python3",
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
    ].filter(Boolean);

    for (const candidate of candidates) {
        const probe = spawnSync(candidate, ["-c", PYTHON_IMPORT_CHECK], {
            cwd: REPO_DIR,
            env,
            encoding: "utf8",
        });
        if (probe.status === 0 && String(probe.stdout || "").trim() === "ok") {
            return candidate;
        }
    }
    return null;
}

function runHelper(url) {
    return new Promise((resolve, reject) => {
        const env = {
            ...parseDotEnv(path.join(REPO_DIR, ".env")),
            ...process.env,
        };
        env.HOME ||= os.homedir();
        const pythonCommand = resolvePythonCommand(env);
        if (!pythonCommand) {
            reject(new Error("Python runtime for /transcribe is missing requests/beautifulsoup4. Run scripts/setup.sh again or install them for the gateway Python."));
            return;
        }
        const child = spawn(
            pythonCommand,
            [SCRIPT_PATH, "run", url, "--email-to", DEFAULT_EMAIL, "--json"],
            {
                cwd: REPO_DIR,
                env,
                stdio: ["ignore", "pipe", "pipe"],
            },
        );

        let stdout = "";
        let stderr = "";
        let timedOut = false;
        const timer = setTimeout(() => {
            timedOut = true;
            child.kill("SIGTERM");
        }, COMMAND_TIMEOUT_MS);

        child.stdout.on("data", (chunk) => {
            stdout += String(chunk);
        });
        child.stderr.on("data", (chunk) => {
            stderr += String(chunk);
        });
        child.on("error", (error) => {
            clearTimeout(timer);
            reject(error);
        });
        child.on("close", (code) => {
            clearTimeout(timer);
            if (timedOut) {
                reject(new Error("Transcription timed out before the helper finished."));
                return;
            }
            if (code !== 0) {
                reject(new Error(sanitizeText(stderr) || `Helper exited with code ${code}.`));
                return;
            }
            try {
                resolve(JSON.parse(stdout));
            } catch (error) {
                reject(new Error(`Could not parse helper JSON output: ${error instanceof Error ? error.message : String(error)}`));
            }
        });
    });
}

export default {
    id: "transcribe-command",
    name: "Transcribe Command",
    description: "Deterministic /transcribe command that runs the repo transcript helper directly.",
    register(api) {
        api.on("before_dispatch", async (event) => {
            const url = extractTranscribeUrl(event.body);
            if (url === null) {
                return;
            }
            api.logger.info?.(`transcribe-command intercepting before_dispatch for ${url || "<missing-url>"}`);
            if (event.isGroup) {
                return {
                    handled: true,
                    text: "Use /transcribe in a direct chat with me so I can send the summary and transcript package safely."
                };
            }
            if (!url) {
                return {
                    handled: true,
                    text: "Usage: /transcribe <URL>"
                };
            }
            if (!/^https?:\/\//iu.test(url)) {
                return {
                    handled: true,
                    text: "Usage: /transcribe <URL> (the argument must be a full http/https URL)"
                };
            }
            if (!fs.existsSync(SCRIPT_PATH)) {
                return {
                    handled: true,
                    text: "The transcription helper is missing from the repo checkout on this machine."
                };
            }
            const speed = estimateTranscribeSpeed(url);
            if (!speed.fast) {
                const rawTarget = sanitizeText(event.senderId) || sanitizeText(event.from);
                const ack = sendInterimAck(speed.ackText, rawTarget, api.logger);
                if (ack.ok) {
                    api.logger.info?.(`transcribe-command queued slow-path ETA ack for ${url} → ${ack.target}`);
                } else {
                    api.logger.warn?.(`transcribe-command could not queue ETA ack for ${url}: ${ack.reason}`);
                }
            }
            try {
                const result = await runHelper(url);
                return {
                    handled: true,
                    text: buildReply(result)
                };
            } catch (error) {
                const message = error instanceof Error ? error.message : String(error);
                api.logger.error?.(`transcribe-command before_dispatch failed for ${url}: ${message}`);
                return {
                    handled: true,
                    text: `I couldn't finish the transcript run.\n\n${message}`
                };
            }
        });

        api.registerCommand({
            name: "transcribe",
            description: "Fetch or generate a full transcript for a media URL, then email it when available.",
            acceptsArgs: true,
            handler: async (ctx) => {
                const url = sanitizeText(ctx.args);
                if (!url) {
                    return { text: "Usage: /transcribe <URL>" };
                }
                if (!/^https?:\/\//iu.test(url)) {
                    return { text: "Usage: /transcribe <URL> (the argument must be a full http/https URL)" };
                }
                if (!fs.existsSync(SCRIPT_PATH)) {
                    return { text: "The transcription helper is missing from the repo checkout on this machine." };
                }
                try {
                    const result = await runHelper(url);
                    return { text: buildReply(result) };
                } catch (error) {
                    const message = error instanceof Error ? error.message : String(error);
                    api.logger.error?.(`transcribe-command failed for ${url}: ${message}`);
                    return { text: `I couldn't finish the transcript run.\n\n${message}` };
                }
            },
        });
    },
};
