import test from "node:test";
import assert from "node:assert/strict";
import plugin, { parseShrink, whatsappTarget, handle, queue } from "./index.js";

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
    });
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
    }), /Check its Python and Gemini configuration/);
});
