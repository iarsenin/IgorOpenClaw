import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("sum_fallback_tests", Path(__file__).resolve().parents[1] / "scripts/transcribe-url.py")
helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helper
SPEC.loader.exec_module(helper)
provider = helper.provider


def response(value, status=200):
    r = mock.Mock(status_code=status, ok=status < 400, headers={})
    r.json.return_value = value
    return r


def gpt(text="complete text", status="completed"):
    return {"status": status, "model": "gpt-6-luna", "output": [{"type": "message", "status": "completed",
        "content": [{"type": "output_text", "text": text}]}], "usage": {"input_tokens": 10, "output_tokens": 5}}


class SumFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = mock.patch.dict(helper.os.environ, {"OPENAI_API_KEY": "private-test-key", "GOOGLE_API_KEY": "private-google-key",
            "SUM_PROVIDER_EVIDENCE_DIR": str(self.root / "evidence")}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop(); self.temp.cleanup()

    def test_google429_latches_switch_for_every_later_text_call(self):
        with provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post", side_effect=[
                response({"error": {"message": "monthly spending cap"}}, 429), response(gpt()), response(gpt("second"))]) as post:
            self.assertEqual(helper.gemini_generate([{"text": "input"}], api_key="private-google-key"), "complete text")
            self.assertEqual(helper.gemini_generate([{"text": "another"}], api_key="private-google-key"), "second")
            self.assertEqual(post.call_count, 3)
            self.assertTrue(all("api.openai.com" in c.args[0] for c in post.call_args_list[1:]))
            self.assertEqual(run.switch_reason, "Gemini HTTP 429")
            self.assertEqual(len(list(run.directory.glob("*.json"))), 3)

    def test_upload429_transcription_then_summary_use_openai(self):
        source = self.root / "input.wav"; source.write_bytes(b"wav")
        state = helper.RunState("https://example.com/a.wav", self.root, audio_path=source)
        summary = {"email_subject": "Test", "detailed_summary": "- Actual point.", "whatsapp_summary": "- Actual point.", "who": "Unknown", "transcript_possible": True}
        with provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post", side_effect=[
                response({"error": {"message": "cap"}}, 429), response({"text": "Actual transcript."}), response(gpt(json.dumps(summary)))]) as post:
            self.assertTrue(helper.transcribe_audio(state))
            self.assertEqual(state.transcript_source, "openai-audio")
            self.assertEqual(helper.summarize(state)["detailed_summary"], "- Actual point.")
            self.assertEqual(post.call_count, 3)
            self.assertTrue(run.google_stopped)

    def test_openai_only_summary_needs_no_google_key(self):
        helper.os.environ["GOOGLE_API_KEY"] = ""
        state = helper.RunState("https://example.com", self.root, transcript_text="Complete transcript.")
        data = {"email_subject": "Test", "detailed_summary": "- Actual point.", "whatsapp_summary": "- Actual point.", "who": "Unknown", "transcript_possible": True}
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response(gpt(json.dumps(data)))) as post:
            self.assertEqual(helper.summarize(state)["detailed_summary"], "- Actual point.")
            post.assert_called_once()
            self.assertIn("api.openai.com", post.call_args.args[0])

    def test_google400_is_not_fallback_and_stops_peer_calls(self):
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response({"error": {}}, 400)) as post:
            for _ in range(2):
                with self.assertRaises(provider.ProviderError):
                    helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
            post.assert_called_once()

    def test_incomplete_primary_text_does_not_switch(self):
        payload = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial"}]}}]}
        with provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post", return_value=response(payload)) as post:
            for _ in range(2):
                with self.assertRaises(provider.ProviderError):
                    helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
            post.assert_called_once()
            self.assertIsNone(run.switch_reason)

    def test_google_file_reference_is_not_sent_to_text_model(self):
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response({"error": {}}, 429)) as post:
            with self.assertRaises(provider.PrimaryUnavailable):
                helper.gemini_generate([{"file_data": {"file_uri": "uri"}}], api_key="private-google-key")
            post.assert_called_once()

    def test_openai429_stops_both_providers_even_if_caller_catches_error(self):
        helper.os.environ["SUM_PROVIDER"] = "openai"
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response({"error": {"code": "insufficient_quota"}}, 429)) as post:
            for _ in range(2):
                with self.assertRaises(provider.ProviderError):
                    helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
            post.assert_called_once()

    def test_openai_incomplete_refusal_or_empty_results_stay_held(self):
        helper.os.environ["SUM_PROVIDER"] = "openai"
        payloads = [gpt(status="incomplete"), gpt(""), {"status": "completed", "output": []},
            {"status": "completed", "output": [{"type": "message", "status": "completed", "content": [{"type": "refusal", "refusal": "no"}]}]}]
        for i, payload in enumerate(payloads):
            with provider.scope(self.root / str(i)) as run, mock.patch.object(provider.requests, "post", return_value=response(payload)) as post:
                for _ in range(2):
                    with self.assertRaises(provider.ProviderError):
                        helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
                post.assert_called_once()
                self.assertTrue(list(run.directory.glob("*.json")))

    def test_disabled_fallback_does_not_consume_openai(self):
        helper.os.environ["SUM_OPENAI_FALLBACK"] = "0"
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response({"error": {}}, 429)) as post:
            with self.assertRaises(provider.PrimaryUnavailable):
                helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
            post.assert_called_once()

    def test_transport_error_no_retry_or_cross_provider_probe(self):
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", side_effect=provider.requests.Timeout) as post:
            for _ in range(2):
                with self.assertRaises(provider.ProviderError):
                    helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
            post.assert_called_once()

    def test_raw_is_redacted_and_retained_outside_email_scratch(self):
        helper.os.environ["SUM_PROVIDER"] = "openai"
        scratch = self.root / "scratch"; scratch.mkdir()
        payload = gpt("private-test-key should not be logged")
        with provider.scope(scratch) as run, mock.patch.object(provider.requests, "post", return_value=response(payload)):
            helper.gemini_generate([{"text": "input"}], api_key="")
            raw = next(run.directory.glob("*.json"))
            self.assertNotIn("private-test-key", raw.read_text())
            self.assertEqual(raw.stat().st_mode & 0o777, 0o600)
            self.assertFalse(raw.is_relative_to(scratch))

    def test_state_is_per_run_and_resets_after_scope(self):
        with provider.scope(self.root / "first") as first:
            first.google_stopped = True
        with provider.scope(self.root / "second") as second:
            self.assertFalse(second.google_stopped)

    def test_chunk_failure_uses_provider_module_not_loop_name(self):
        audio = self.root / "a.wav"; audio.write_bytes(b"wav")
        state = helper.RunState("https://example.com", self.root)
        with mock.patch.object(helper, "transcribe_with_gemini", side_effect=provider.PrimaryUnavailable("cap")), \
             mock.patch.object(helper, "transcribe_with_openai", return_value="complete"):
            self.assertEqual(helper.transcribe_chunk(audio, state, gemini_key="google", openai_key="openai"), "complete")

    def test_openai_instruction_does_not_treat_mentioned_name_as_identity(self):
        helper.os.environ["SUM_PROVIDER"] = "openai"
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response(gpt())) as post:
            helper.gemini_generate([{"text": "Mentioned name could be wrong."}], api_key="")
        self.assertIn("not verified speaker identity", post.call_args.kwargs["json"]["instructions"])

    def test_speaker_tagging_rejects_dropped_word_despite_long_output(self):
        state = helper.RunState("https://example.com", self.root, transcript_text="A necessary negative. Not a certainty. Only a possibility.")
        labeled = "Speaker A: A necessary negative.\nSpeaker B: A certainty.\nSpeaker A: Only a possibility."
        with mock.patch.object(helper, "gemini_generate", return_value=labeled):
            helper.diarize_transcript_with_gemini(state)
        self.assertIn("Not", state.transcript_text)
        self.assertTrue(any("changed spoken words" in w for w in state.warnings))

    def test_speaker_tagging_keeps_exact_word_sequence(self):
        state = helper.RunState("https://example.com", self.root, transcript_text="A necessary negative. Not a certainty. Only a possibility.")
        labeled = "Speaker A: A necessary negative.\nSpeaker B: Not a certainty.\nSpeaker A: Only a possibility."
        with mock.patch.object(helper, "gemini_generate", return_value=labeled):
            helper.diarize_transcript_with_gemini(state)
        self.assertEqual(state.transcript_text, labeled)

    def test_fallback_opt_out_also_disables_audio_fallback(self):
        helper.os.environ["SUM_OPENAI_FALLBACK"] = "0"
        audio = self.root / "input.wav"; audio.write_bytes(b"wav")
        state = helper.RunState("https://example.com/a.wav", self.root, audio_path=audio)
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response({"error": {}}, 429)) as post:
            self.assertFalse(helper.transcribe_audio(state))
            post.assert_called_once()

    def test_explicit_openai_mode_is_allowed_when_implicit_fallback_is_disabled(self):
        helper.os.environ.update(SUM_OPENAI_FALLBACK="0", SUM_PROVIDER="openai")
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", return_value=response(gpt())) as post:
            self.assertEqual(helper.gemini_generate([{"text": "input"}], api_key=""), "complete text")
            post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
