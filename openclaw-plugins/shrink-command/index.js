import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import { createHash, randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseDotEnv, resolvePythonCommand } from "../sum-command/index.js";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const HELPER = path.join(REPO, "scripts/shrink_original.py");
const USAGE = "/shrink <podcast-or-audio-URL>";

function parseShrink(body) {
    if (typeof body !== "string") return null;
    const match = body.trim().match(/^\/shrink(?:\s+(.*))?$/isu);
    if (!match) return null;
    const argument = (match[1] ?? "").trim();
    if (!argument || /\s/u.test(argument)) return { error: `Usage: ${USAGE}` };
    try {
        const url = new URL(argument);
        if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error();
        return { url: url.href };
    } catch {
        return { error: `Usage: ${USAGE} (use one complete http/https URL)` };
    }
}

function whatsappTarget(event) {
    const channel = event.channelId || event.channel;
    if (event.isGroup || event.isSelf || channel && channel !== "whatsapp") return null;
    // Native command contexts do not always include isGroup. A group
    // conversation must not fall through to its participant's private phone.
    if (/@g\.us$/u.test(String(event.from || "")) || /^whatsapp:group:/u.test(String(event.from || ""))) return null;
    for (const candidate of [event.from, event.senderId]) {
        const raw = String(candidate || "").trim().replace(/^whatsapp:/u, "");
        // A WhatsApp LID is not a phone number. Never manufacture an E.164
        // destination from one; use the resolved caller phone if provided.
        if (raw.includes("@") && !/@(?:s\.whatsapp\.net|c\.us)$/u.test(raw)) continue;
        const local = raw.split("@")[0].split(":")[0];
        const digits = local.replace(/^\+/u, "");
        if (/^\d{6,15}$/u.test(digits)) return `+${digits}`;
    }
    return null;
}

function redactDiagnostic(value, env) {
    let text = String(value ?? "");
    for (const [key, secret] of Object.entries(env)) {
        if (/(?:KEY|TOKEN|PASSWORD|SECRET)/iu.test(key) && typeof secret === "string" && secret.length >= 4) {
            text = text.split(secret).join("<redacted>");
        }
    }
    return text.replace(/([?&](?:key|token|access_token|api_key)=)[^\s&"']+/giu, "$1<redacted>")
        .replace(/Bearer\s+[^\s"']+/giu, "Bearer <redacted>")
        .replace(/\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}/gu, "<redacted>");
}

function writeLaunchDiagnostic(id, phase, record, env) {
    const root = path.resolve(env.SHRINK_LAUNCH_LOG_DIR || path.join(os.homedir(), ".openclaw/state/shrink-launch-evidence"));
    fs.mkdirSync(root, { recursive: true, mode: 0o700 });
    const filename = path.join(root, `${id}-${phase}.json`);
    const scrub = (value) => typeof value === "string" ? redactDiagnostic(value, env)
        : Array.isArray(value) ? value.map(scrub)
            : value && typeof value === "object" ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, scrub(item)])) : value;
    const data = scrub(record);
    fs.writeFileSync(filename, JSON.stringify(data, null, 2), { flag: "wx", mode: 0o600 });
    return filename;
}

function queue(url, target, execImpl = execFile, options = {}) {
    return new Promise((resolve, reject) => {
        const id = randomUUID();
        let env = { ...process.env, ...(options.env ?? {}) };
        const record = { id, at: new Date().toISOString(), helper: HELPER, cwd: REPO,
            url_sha256: createHash("sha256").update(url).digest("hex"),
            target_sha256: createHash("sha256").update(target).digest("hex") };
        const persist = (phase, extra) => {
            try { return (options.logImpl ?? writeLaunchDiagnostic)(id, phase, { ...record, ...extra }, env); }
            catch (error) { options.logger?.error?.(`shrink launch ${id}: private logging failed (${error.code || error.name}).`); return null; }
        };
        const fail = (error, stdout, stderr) => {
            persist("failed", { status: "failed", python: record.python, error: {
                code: error.code, signal: error.signal, killed: error.killed, message: error.message }, stdout, stderr });
            options.logger?.error?.(`shrink launch ${id} failed (code=${error.code ?? "unknown"}, signal=${error.signal ?? "none"}); see private launch evidence.`);
            reject(new Error(`The /shrink launcher failed. Private diagnostic: ${id}. No audio job was confirmed; it will not retry automatically.`));
        };
        try {
            env = { ...parseDotEnv(path.join(REPO, ".env")), ...env };
            record.python = (options.resolvePythonImpl ?? resolvePythonCommand)(env);
            if (!record.python) throw new Error("No Python interpreter with requests and beautifulsoup4 is available.");
            persist("started", { status: "started", python: record.python });
            execImpl(record.python, [HELPER, "enqueue", url, "--target", target],
            { cwd: REPO, env, timeout: 20000, maxBuffer: 64 * 1024 },
            (error, stdout, stderr) => {
                if (error) return fail(error, stdout, stderr);
                try {
                    const result = JSON.parse(stdout);
                    if (typeof result.id !== "string" || !result.id || result.status !== "queued") throw new Error("The worker did not return a complete queued receipt.");
                    persist("queued", { status: "queued", job_id: result.id, python: record.python, stdout, stderr });
                    resolve(result);
                } catch (error) { fail(error, stdout, stderr); }
            });
        } catch (error) { fail(error, "", ""); }
    });
}

async function handle(event, queueImpl = queue) {
    const parsed = parseShrink(event.body);
    if (parsed === null) return undefined;
    const target = whatsappTarget(event);
    if (!target) return { handled: true, text: `Use ${USAGE} in a direct WhatsApp chat.` };
    if (parsed.error) return { handled: true, text: parsed.error };
    try {
        const job = await queueImpl(parsed.url, target);
        return { handled: true, text: `I'll make a chronological edit of the original recording, keeping its voices, useful stories and humor, and send the finished audio here if the listening checks pass. No synthetic speech. Long episodes take time; you can leave the chat.\nJob: ${job.id}` };
    } catch (error) {
        return { handled: true, text: `Could not start /shrink: ${error.message}` };
    }
}

export default {
    id: "shrink-command",
    name: "Shrink Command",
    description: "Chronological original-voice podcast editing with playable chat audio; no synthetic speech.",
    configSchema: { type: "object", additionalProperties: false, properties: {} },
    register(api) {
        const launch = (url, target) => queue(url, target, execFile, { logger: api.logger });
        api.on("before_dispatch", (event) => handle(event, launch));
        api.registerCommand({
            name: "shrink", description: "Edit a podcast and return a shorter audio edition in this chat.", acceptsArgs: true,
            channels: ["whatsapp"], requireAuth: true,
            handler: async (ctx) => {
                const result = await handle({ ...ctx, body: `/shrink ${ctx.args ?? ""}` }, launch);
                return { text: result.text };
            },
        });
    },
};

export { parseShrink, whatsappTarget, queue, handle, redactDiagnostic, writeLaunchDiagnostic };
