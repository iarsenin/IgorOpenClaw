import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import plugin, { parseShrink, whatsappTarget, handle, queue, writeLaunchDiagnostic } from "./index.js";

const launcherTestOptions = { logImpl: () => {}, resolvePythonImpl: () => "/test/python3" };

test("parses one URL and refuses shell-like arguments or other commands", () => {
    assert.equal(parseShrink("/sum https://example.com"), null);
    assert.deepEqual(parseShrink("/shrink https://example.com/audio.mp3"), { url: "https://example.com/audio.mp3" });
    for (const body of ["/shrink", "/shrink file:///etc/passwd", "/shrink https://example.com ; rm x", "/shrink https://user:pass@example.com"]) {
        assert.ok(parseShrink(body).error);
    }
});

test("routes only to the requesting WhatsApp direct chat", () => {
    assert.equal(whatsappTarget({ senderId: "15551234567@s.whatsapp.net" }), "+15551234567");
    assert.equal(whatsappTarget({ senderId: "15551234567:5@s.whatsapp.net" }), "+15551234567");
    assert.equal(whatsappTarget({ senderId: "15551234567@g.us" }), null);
    assert.equal(whatsappTarget({ from: "whatsapp:120363000000000@g.us", senderId: "15551234567@s.whatsapp.net", channelId: "whatsapp" }), null);
    assert.equal(whatsappTarget({ senderId: "15551234567", isGroup: true }), null);
    assert.equal(whatsappTarget({ senderId: "15551234567", channel: "telegram" }), null);
    assert.equal(whatsappTarget({ senderId: "15551234567", channel: "chat", channelId: "whatsapp" }), "+15551234567");
    assert.equal(whatsappTarget({ senderId: "157565321269383@lid" }), null);
    assert.equal(whatsappTarget({ senderId: "157565321269383@lid", from: "whatsapp:+15551234567" }), "+15551234567");
});

test("acknowledges a queued job and preserves the caller's destination", async () => {
    let captured;
    const result = await handle({ body: "/shrink https://example.com/audio", from: "+15551234567" }, async (...args) => {
        captured = args; return { id: "job-1", status: "queued" };
    });
    assert.deepEqual(captured, ["https://example.com/audio", "+15551234567"]);
    assert.equal(result.handled, true);
    assert.match(result.text, /send the finished audio here/);
    assert.equal(await handle({ body: "hello" }), undefined);
});

test("does not claim a job exists after enqueue failure", async () => {
    const result = await handle({ body: "/shrink https://example.com", from: "+15551234567" }, async () => { throw new Error("Gemini quota exceeded"); });
    assert.match(result.text, /Could not start.*quota/);
    assert.doesNotMatch(result.text, /Job:/);
});

test("executes Python without a shell and validates the acknowledgment", async () => {
    let captured;
    const result = await queue("https://example.com/audio?a=$()", "+15551234567", (binary, args, options, callback) => {
        captured = { binary, args, options }; callback(null, '{"id":"a","status":"queued"}', "");
    }, launcherTestOptions);
    assert.equal(result.id, "a");
    assert.equal(captured.options.shell, undefined);
    assert.match(captured.args[0], /scripts\/shrink_original\.py$/);
    assert.doesNotMatch(captured.args[0], /shrink_audio\.py$/);
    assert.ok(captured.args.includes("https://example.com/audio?a=$()"));
});

test("acknowledgment explicitly preserves original voices and avoids synthetic promises", async () => {
    const result = await handle({ body: "/shrink https://example.com/audio", from: "+15551234567" }, async () => ({ id: "test", status: "queued" }));
    assert.match(result.text, /original recording/);
    assert.match(result.text, /No synthetic speech/);
    assert.match(result.text, /if the listening checks pass/);
});

test("registers the deterministic hook and native command", () => {
    const hooks = [], commands = [];
    plugin.register({ on: (name) => hooks.push(name), registerCommand: (c) => commands.push(c.name) });
    assert.deepEqual(hooks, ["before_dispatch"]);
    assert.deepEqual(commands, ["shrink"]);
});

test("does not expose worker tracebacks in a chat error", async () => {
    await assert.rejects(queue("https://example.com", "+15551234567", (binary, args, options, callback) => {
        callback(new Error("exit"), "", "Traceback (most recent call last):\nprivate diagnostic data");
    }, launcherTestOptions), /Private diagnostic/);
});

test("private launcher record keeps full error and stdout without exposing them in chat", async () => {
    const records = [];
    const error = Object.assign(new Error("process failed"), { code: 1, signal: "SIGTERM", killed: true });
    await assert.rejects(queue("https://example.com", "+15551234567", (binary, args, options, callback) => {
        callback(error, "partial receipt", "Traceback\nPermissionError: queue path");
    }, { ...launcherTestOptions, logImpl: (id, phase, record) => records.push({ id, phase, record }) }), (error) => {
        assert.match(error.message, /Private diagnostic/);
        assert.doesNotMatch(error.message, /PermissionError|Traceback|partial receipt/);
        return true;
    });
    assert.deepEqual(records.map(r => r.phase), ["started", "failed"]);
    assert.equal(records[1].record.stderr, "Traceback\nPermissionError: queue path");
    assert.equal(records[1].record.error.code, 1);
    assert.equal(records[1].record.error.signal, "SIGTERM");
});

test("missing dependency-aware interpreter holds without spawning a helper", async () => {
    let spawned = false;
    const records = [];
    await assert.rejects(queue("https://example.com", "+15551234567", () => { spawned = true; }, {
        logImpl: (id, phase, record) => records.push(record), resolvePythonImpl: () => null,
    }), /Private diagnostic/);
    assert.equal(spawned, false);
    assert.match(records[0].error.message, /No Python interpreter/);
});

test("malformed enqueue acknowledgment is held and preserved without retry", async () => {
    let calls = 0;
    const records = [];
    await assert.rejects(queue("https://example.com", "+15551234567", (binary, args, options, callback) => {
        calls++; callback(null, "not a complete receipt", "private warning");
    }, { ...launcherTestOptions, logImpl: (id, phase, record) => records.push(record) }), /Private diagnostic/);
    assert.equal(calls, 1);
    assert.equal(records[1].stdout, "not a complete receipt");
});

test("private receipts redact configured credentials, bearer tokens and URL keys", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "shrink-launch-log-test-"));
    try {
        const env = { SHRINK_LAUNCH_LOG_DIR: root, OPENAI_API_KEY: 'secret-key-quote"back\\slash' };
        const filename = writeLaunchDiagnostic("test", "failed", {
            stderr: 'Traceback secret-key-quote"back\\slash https://provider.test/?key=do-not-log Bearer another-private-token',
        }, env);
        const data = fs.readFileSync(filename, "utf8");
        assert.doesNotMatch(data, /secret-key|do-not-log|another-private-token/);
        assert.match(JSON.parse(data).stderr, /Traceback/);
        assert.equal(fs.statSync(filename).mode & 0o777, 0o600);
    } finally { fs.rmSync(root, { recursive: true }); }
});
