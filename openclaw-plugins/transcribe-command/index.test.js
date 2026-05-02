import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";

import { parseHelperJsonOutput, runHelper, shouldRetryHelper } from "./index.js";

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
