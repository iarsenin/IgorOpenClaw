import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import sum, { runHelper } from "../openclaw-plugins/sum-command/index.js";

function register(plugin) {
    const hooks = new Map(), commands = new Map();
    plugin.register({ on: (n, f) => hooks.set(n, f), registerCommand: c => commands.set(c.name, c),
        logger: { info() {}, warn() {}, error() {} } });
    return { hooks, commands };
}

test("only /sum is registered, with group and missing-URL checks intact", async () => {
        assert.deepEqual([...register(sum).commands.keys()], ["sum"]);
        const sumHook = register(sum).hooks.get("before_dispatch");
        assert.deepEqual(await sumHook({ body: "/sum", isGroup: false }), { handled: true, text: "Usage: /sum <URL>" });
        assert.match((await sumHook({ body: "/sum https://example.com", isGroup: true })).text, /direct chat/);
        assert.match((await register(sum).commands.get("sum").handler({ args: "" })).text, /Usage: \/sum/);
});

test("/sum still invokes transcript+email helper, never original-audio worker", async () => {
    let captured;
    const result = await runHelper("https://example.com/episode", {
        pythonCommand: "python3", env: { SUM_EMAIL_TO: "test@example.com" }, setTimeoutImpl: () => 0, clearTimeoutImpl() {},
        spawnImpl: (binary, args, options) => {
            captured = { binary, args, options };
            const child = new EventEmitter(); child.stdout = new EventEmitter(); child.stderr = new EventEmitter(); child.kill = () => {};
            queueMicrotask(() => {
                child.stdout.emit("data", JSON.stringify({ transcript_available: true, email_sent: true, whatsapp_summary: "Full existing summary" }));
                child.emit("close", 0);
            });
            return child;
        },
    });
    assert.match(captured.args[0], /scripts\/transcribe-url\.py$/);
    assert.equal(captured.args[1], "run");
    assert.deepEqual(captured.args.slice(-3), ["--email-to", "test@example.com", "--json"]);
    assert.equal(result.email_sent, true);
    assert.equal(result.whatsapp_summary, "Full existing summary");
    assert.doesNotMatch(captured.args.join(" "), /shrink_original/);
});

test("retired /shrink and unknown commands are handled by /sum usage, never fall through", async () => {
    const hook = register(sum).hooks.get("before_dispatch");
    for (const body of ["/shrink https://example.com", "/shrink status", "/other", "hello"]) {
        assert.deepEqual(await hook({ body, isGroup: false }), {
            handled: true, text: "Use /sum <URL> for a transcript and summary.",
        });
    }
});
