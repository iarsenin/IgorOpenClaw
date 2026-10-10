"""Provider fallback isolation: no paid calls, no quality-gate relaxation."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("openai_shrink_tests", Path(__file__).resolve().parents[1] / "scripts/shrink_original.py")
original = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(original)
PASS = {"pass": True, "issues": [], "uncertainties": [], "checked_ids": [], "protected_ids": []}


def response(payload, status=200):
    value = mock.Mock(status_code=status, ok=status < 400, headers={})
    value.json.return_value = payload
    return value


def report(value=PASS, finish="tool_calls", **message):
    return {"choices": [{"finish_reason": finish, "message": {
        "tool_calls": [{"type": "function", "function": {"name": "return_report", "arguments": json.dumps(value)}}], **message}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10}}


class OpenAITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = mock.patch.dict(original.os.environ, {"GOOGLE_API_KEY": "test-google", "OPENAI_API_KEY": "test-openai",
            "SHRINK_PROVIDER": "gemini", "SHRINK_OPENAI_FALLBACK": "1"}, clear=True)
        self.env.start()
        self.loader = mock.patch.object(original, "load_env")
        self.loader.start()

    def tearDown(self):
        self.loader.stop(); self.env.stop(); self.temp.cleanup()

    def test_429_switches_once_retains_error_and_latches_google_off(self):
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", side_effect=[response({"error": {"details": []}}, 429), response(report()), response(report())]) as call:
            self.assertEqual(client.generate(self.root / "one", "review", original.REVIEW_SCHEMA, client.critic), PASS)
            self.assertEqual(client.generate(self.root / "two", "review", original.REVIEW_SCHEMA, client.critic), PASS)
            self.assertEqual(call.call_count, 3)
            self.assertIn("googleapis.com", call.call_args_list[0].args[1])
            self.assertTrue(all("api.openai.com" in c.args[1] for c in call.call_args_list[1:]))
        self.assertTrue(client.gemini_quota_stop)
        self.assertFalse(client.quota_stop)
        self.assertEqual(original.read(self.root / "one/gemini/raw.json")["error"]["details"], [])
        self.assertEqual(len((self.root / "usage.jsonl").read_text().splitlines()), 3)
        self.assertEqual(original.Client(self.root).provider, "openai")

    def test_primary_400_is_not_availability_fallback(self):
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", return_value=response({"error": {}}, 400)) as call:
            with self.assertRaises(original.ShrinkError):
                client.generate(self.root / "one", "review", original.REVIEW_SCHEMA, client.critic)
            call.assert_called_once()
        self.assertFalse((self.root / "provider-route.json").exists())

    def test_malformed_primary_success_never_falls_back(self):
        client = original.Client(self.root)
        payload = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not-json"}]}}]}
        with mock.patch.object(original.requests, "request", return_value=response(payload)) as call:
            with self.assertRaises(original.ShrinkError):
                client.generate(self.root / "one", "review", original.REVIEW_SCHEMA, client.critic)
            call.assert_called_once()
        self.assertEqual(client.provider, "gemini")

    def test_semantic_failure_stays_failure_no_other_provider(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        client = original.Client(self.root)
        failed = {**PASS, "issues": ["Negative omitted"], "pass": False}
        with mock.patch.object(original.requests, "request", return_value=response(report(failed))) as call:
            value = client.generate(self.root / "one", "review", original.REVIEW_SCHEMA, client.critic)
            with self.assertRaises(original.ShrinkError):
                original.require_pass(value, [])
            call.assert_called_once()

    def test_openai_429_stops_every_peer_and_never_retries(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", return_value=response({"error": {"code": "insufficient_quota"}}, 429)) as call:
            for stage in ("one", "two"):
                with self.assertRaises(original.ShrinkError):
                    client.generate(self.root / stage, "review", original.REVIEW_SCHEMA, client.critic)
            call.assert_called_once()
        self.assertTrue(client.quota_stop)
        self.assertIsNone(original.read(self.root / "openai-quota-stop.json")["retry_after"])

    def test_transport_failure_no_switch_or_retry(self):
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", side_effect=original.requests.Timeout) as call:
            with self.assertRaises(original.ShrinkError):
                client.generate(self.root / "one", "review", original.REVIEW_SCHEMA, client.critic)
            call.assert_called_once()
        self.assertEqual(client.provider, "gemini")

    def test_incomplete_refusal_extra_tools_and_audio_output_held_raw_preserved(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        for i, payload in enumerate([report(finish="length"), report(refusal="refused"), report(audio={"id": "unexpected"}),
                                     report(value={**PASS, "extra": True}), {"choices": []}, []]):
            client = original.Client(self.root)
            with mock.patch.object(original.requests, "request", return_value=response(payload)) as call:
                with self.assertRaises(original.ShrinkError):
                    client.generate(self.root / str(i), "review", original.REVIEW_SCHEMA, client.critic)
                call.assert_called_once()
            self.assertEqual(original.read(self.root / str(i) / "openai/raw.json"), payload)

    def test_audio_is_exact_input_text_only_and_not_sent_to_text_model(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        audio = self.root / "actual.wav"; audio.write_bytes(b"actual-exact-wav-bytes")
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", return_value=response(report())) as call:
            client.generate(self.root / "audio", "listen", original.REVIEW_SCHEMA, client.listen, audio)
            body = call.call_args.kwargs["json"]
            self.assertEqual(body["model"], client.openai_audio)
            self.assertEqual(body["modalities"], ["text"])
            self.assertFalse(body["store"])
            self.assertNotIn("audio", body)
            self.assertNotIn("reasoning_effort", body)
            data = body["messages"][1]["content"][1]["input_audio"]["data"]
            self.assertEqual(base64.b64decode(data), audio.read_bytes())

    def test_text_model_does_not_receive_audio_only_modalities(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", return_value=response(report())) as call:
            client.generate(self.root / "text", "review", original.REVIEW_SCHEMA, client.edit)
        body = call.call_args.kwargs["json"]
        self.assertEqual(body["reasoning_effort"], "none")
        self.assertNotIn("modalities", body)

    def test_audio_natural_stop_requires_exact_valid_tool_call(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        audio = self.root / "actual.wav"; audio.write_bytes(b"wav")
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", return_value=response(report(finish="stop"))):
            self.assertEqual(client.generate(self.root / "one", "listen", original.REVIEW_SCHEMA, client.listen, audio), PASS)
        for i, payload in enumerate([report(finish="length"), report(finish="stop", tool_calls=[]),
                                     report(finish="stop", audio={"id": "speech-not-allowed"}),
                                     report(value={**PASS, "protected_ids": [1]}, finish="stop")]):
            with mock.patch.object(original.requests, "request", return_value=response(payload)), self.assertRaises(original.ShrinkError):
                client.generate(self.root / str(i), "listen", original.REVIEW_SCHEMA, client.listen, audio)

    def test_whisper_exact_words_timestamp_navigation_unknown_speakers(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        audio = self.root / "actual.wav"; audio.write_bytes(b"wav")
        payload = {"text": "No, not 3.7.", "words": [{"word": "No,", "start": .1, "end": .3},
            {"word": "not", "start": .4, "end": .6}, {"word": "3.7.", "start": .7, "end": 1.2}]}
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", return_value=response(payload)) as call:
            value = client.transcribe(self.root / "asr", audio)
            self.assertIn(("timestamp_granularities[]", "word"), call.call_args.kwargs["data"])
            self.assertIn(("language", "en"), call.call_args.kwargs["data"])
        rows = original.flatten(value, 0, 2)
        self.assertEqual([w["text"] for w in rows], ["No,", "not", "3.7."])
        self.assertTrue(all(w["speaker_local"] is None for w in rows))

    def test_whisper_missing_word_or_normalized_alternative_held(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        audio = self.root / "actual.wav"; audio.write_bytes(b"wav")
        for i, payload in enumerate([{"text": "not three", "words": [{"word": "three", "start": 0, "end": 1}]},
                                     {"text": "three", "words": [{"word": "3", "start": 0, "end": 1}]},
                                     {"text": "not three", "words": [{"word": "not", "start": 0, "end": 1}]}]):
            with mock.patch.object(original.requests, "request", return_value=response(payload)), self.assertRaises(original.ShrinkError):
                original.Client(self.root).transcribe(self.root / str(i), audio)

    def test_language_mismatch_is_not_translated_or_normalized(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        audio = self.root / "actual.wav"; audio.write_bytes(b"wav")
        payload = {"language": "welsh", "text": "Dwi", "words": [{"word": "Dwi", "start": 0, "end": 1}]}
        with mock.patch.object(original.requests, "request", return_value=response(payload)), self.assertRaises(original.ShrinkError):
            original.Client(self.root).transcribe(self.root / "asr", audio)

    def test_auto_language_omits_language_hint(self):
        original.os.environ.update(SHRINK_PROVIDER="openai", SHRINK_OPENAI_LANGUAGE="auto")
        audio = self.root / "actual.wav"; audio.write_bytes(b"wav")
        payload = {"text": "Hello", "words": [{"word": "Hello", "start": 0, "end": 1}]}
        with mock.patch.object(original.requests, "request", return_value=response(payload)) as call:
            original.Client(self.root).transcribe(self.root / "asr", audio)
        self.assertNotIn("language", [k for k, v in call.call_args.kwargs["data"]])

    def test_explicit_openai_queue_does_not_require_fallback_toggle_or_google(self):
        original.os.environ.update(SHRINK_PROVIDER="openai", SHRINK_OPENAI_FALLBACK="0", GOOGLE_API_KEY="",
            SHRINK_ORIGINAL_STATE_DIR=str(self.root), SHRINK_WORKER_MODE="launchd")
        with mock.patch.object(original.subprocess, "Popen") as spawn:
            result = original.enqueue("https://example.com/audio", "+15551234567")
        self.assertEqual(result["status"], "queued")
        spawn.assert_not_called()

    def test_primary_critic_is_explicit_gemini_3_6_not_redirected_3_5(self):
        self.assertEqual(original.Client(self.root).critic, "gemini-3.6-flash")

    def test_started_openai_request_is_not_replayed(self):
        original.os.environ["SHRINK_PROVIDER"] = "openai"
        client = original.Client(self.root)
        original.save(self.root / "one/openai/request-attempt.json", {"status": "started"})
        with mock.patch.object(original.requests, "request") as call, self.assertRaises(original.ShrinkError):
            client.generate(self.root / "one", "review", original.REVIEW_SCHEMA, client.critic)
        call.assert_not_called()

    def test_fallback_disabled_and_changed_model_route_refused(self):
        original.os.environ["SHRINK_OPENAI_FALLBACK"] = "0"
        client = original.Client(self.root)
        with mock.patch.object(original.requests, "request", return_value=response({"error": {}}, 404)) as call, self.assertRaises(original.ShrinkError):
            client.generate(self.root / "one", "review", original.REVIEW_SCHEMA, client.critic)
        call.assert_called_once()
        original.os.environ["SHRINK_OPENAI_FALLBACK"] = "1"
        client = original.Client(self.root)
        original.save(self.root / "provider-route.json", {"binding": client.route_binding, "provider": "openai"})
        original.os.environ["SHRINK_OPENAI_TEXT_MODEL"] = "another-model"
        with self.assertRaises(original.ShrinkError):
            original.Client(self.root)


if __name__ == "__main__":
    unittest.main()
