import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";

import plugin, { buildErrorReply, buildReply, extractSumUrl, parseHelperJsonOutput, runHelper, shouldRetryHelper } from "./index.js";

test("/sum failures use a short error status, never helper traceback or secrets", () => {
    const reply = buildErrorReply(new Error("Traceback /Users/private/server.py secret-key"));
    assert.equal(reply, "I couldn't finish the transcript. The error has been logged.");
    assert.doesNotMatch(reply, /Traceback|\/Users|secret-key/);
});

function makeChild({ stdout = "", stderr = "", code = 0 }) {
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.kill = () => {};

    queueMicrotask(() => {
        if (stdout) {
            child.stdout.emit("data", stdout);
        }
        if (stderr) {
            child.stderr.emit("data", stderr);
        }
        child.emit("close", code);
    });

    return child;
}

test("parseHelperJsonOutput extracts JSON when stdout has extra noise", () => {
    const parsed = parseHelperJsonOutput("warning: slow path\n{\n  \"status\": \"ok\"\n}\n");
    assert.deepEqual(parsed, { status: "ok" });
});

test("extractSumUrl accepts /sum and rejects the old /transcribe command", () => {
    assert.equal(extractSumUrl("/sum https://example.com/video"), "https://example.com/video");
    assert.equal(extractSumUrl("/sum"), "");
    assert.equal(extractSumUrl("/transcribe https://example.com/video"), null);
});

test("plugin registers /sum command and before_dispatch gate", async () => {
    const hooks = new Map();
    const commands = [];
    plugin.register({
        on(name, handler) {
            hooks.set(name, handler);
        },
        registerCommand(command) {
            commands.push(command);
        },
        logger: {
            info() {},
            warn() {},
            error() {},
        },
    });

    assert.equal(commands.length, 1);
    assert.equal(commands[0].name, "sum");
    assert.equal(hooks.has("before_dispatch"), true);

    const hook = hooks.get("before_dispatch");
    assert.deepEqual(await hook({ body: "/sum", isGroup: false }), {
        handled: true,
        text: "Usage: /sum <URL>",
    });
    assert.deepEqual(await hook({ body: "/transcribe https://example.com", isGroup: false }), {
        handled: true,
        text: "Use /sum <URL> for a transcript and summary.",
    });
    assert.deepEqual(await hook({ body: "/shrink https://example.com", isGroup: false }), {
        handled: true, text: "Use /sum <URL> for a transcript and summary.",
    });
});

test("shouldRetryHelper returns true for empty stdout parse failures", () => {
    let error = null;
    try {
        parseHelperJsonOutput("", "");
    } catch (caught) {
        error = caught;
    }
    assert.ok(error);
    assert.equal(shouldRetryHelper(error), true);
});

test("runHelper retries once after an empty-stdout helper close", async () => {
    let calls = 0;
    const spawnImpl = () => {
        calls += 1;
        if (calls === 1) {
            return makeChild({ stdout: "", stderr: "", code: 0 });
        }
        return makeChild({ stdout: "{\"status\":\"ok\"}", stderr: "", code: 0 });
    };

    const result = await runHelper("https://example.com", {
        env: {},
        pythonCommand: "python3",
        spawnImpl,
        setTimeoutImpl: () => 0,
        clearTimeoutImpl: () => {},
    });

    assert.equal(calls, 2);
    assert.deepEqual(result, { status: "ok" });
});

test("runHelper passes SUM_EMAIL_TO to the Python helper", async () => {
    let helperArgs = null;
    const spawnImpl = (_command, args) => {
        helperArgs = args;
        return makeChild({ stdout: "{\"status\":\"ok\"}", stderr: "", code: 0 });
    };

    const result = await runHelper("https://example.com", {
        env: { SUM_EMAIL_TO: "summaries@example.com" },
        pythonCommand: "python3",
        spawnImpl,
        setTimeoutImpl: () => 0,
        clearTimeoutImpl: () => {},
    });

    assert.deepEqual(result, { status: "ok" });
    assert.ok(helperArgs);
    assert.equal(helperArgs[helperArgs.indexOf("--email-to") + 1], "summaries@example.com");
});

test("summary and email statuses stay distinct and never invent an email success", () => {
    assert.match(buildReply({ whatsapp_summary: "Real summary", transcript_available: true, email_sent: true }), /Real summary\n\nFull transcript emailed/);
    assert.match(buildReply({ whatsapp_summary: "Real summary", transcript_available: true, email_sent: false }), /Real summary\n\nI got the transcript, but the email send failed/);
    assert.match(buildReply({ whatsapp_summary: "No transcript", transcript_available: false, email_sent: false }), /didn't send an email/);
});

test("provider/helper failures never retry the pipeline", async () => {
    let calls = 0;
    await assert.rejects(runHelper("https://example.com", {
        pythonCommand: "python3", env: {}, setTimeoutImpl: () => 0, clearTimeoutImpl() {},
        spawnImpl: () => { calls++; return makeChild({ stderr: "Private provider failure", code: 1 }); },
    }), /Private provider failure/);
    assert.equal(calls, 1);
});

test("timeout stops the helper and does not restart or claim success", async () => {
    let calls = 0, killed = false;
    await assert.rejects(runHelper("https://example.com", {
        pythonCommand: "python3", env: {}, clearTimeoutImpl() {},
        setTimeoutImpl: callback => { queueMicrotask(callback); return 0; },
        spawnImpl: () => {
            calls++;
            const child = new EventEmitter(); child.stdout = new EventEmitter(); child.stderr = new EventEmitter();
            child.kill = signal => { assert.equal(signal, "SIGTERM"); killed = true; child.emit("close", 1); };
            return child;
        },
    }), /timed out/);
    assert.equal(calls, 1);
    assert.equal(killed, true);
});
