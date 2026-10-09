import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";

import plugin, { extractSumUrl, parseHelperJsonOutput, runHelper, shouldRetryHelper } from "./index.js";

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
        text: "Use /sum <URL> for a transcript and summary, or /shrink <URL> for a shorter audio edition.",
    });
    assert.equal(await hook({ body: "/shrink https://example.com", isGroup: false }), undefined);
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
