import { execFile } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

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

function queue(url, target, execImpl = execFile) {
    return new Promise((resolve, reject) => {
        execImpl(process.env.PYTHON3_PATH || "python3", [HELPER, "enqueue", url, "--target", target],
            { cwd: REPO, env: process.env, timeout: 20000, maxBuffer: 64 * 1024 },
            (error, stdout, stderr) => {
                if (error) {
                    // The helper emits deliberately sanitized, actionable errors.
                    const detail = stderr?.trim();
                    reject(new Error(detail && !detail.includes("\n") && detail.length < 400
                        ? detail : "Could not start the worker. Check its Python and Gemini configuration."));
                    return;
                }
                try {
                    const result = JSON.parse(stdout);
                    if (!result.id || result.status !== "queued") throw new Error();
                    resolve(result);
                } catch {
                    reject(new Error("The /shrink worker did not confirm the queued request."));
                }
            });
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
        api.on("before_dispatch", (event) => handle(event));
        api.registerCommand({
            name: "shrink", description: "Edit a podcast and return a shorter audio edition in this chat.", acceptsArgs: true,
            channels: ["whatsapp"], requireAuth: true,
            handler: async (ctx) => {
                const result = await handle({ ...ctx, body: `/shrink ${ctx.args ?? ""}` });
                return { text: result.text };
            },
        });
    },
};

export { parseShrink, whatsappTarget, queue, handle };
