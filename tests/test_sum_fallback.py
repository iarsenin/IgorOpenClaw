import importlib.util
import json
import hashlib
from pathlib import Path
import sys
import shutil
import subprocess
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
        self.duration = mock.patch.object(helper, "audio_duration", return_value=1)
        self.duration.start()

    def tearDown(self):
        self.duration.stop(); self.env.stop(); self.temp.cleanup()

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

    def test_primary_output_limit_discards_partial_and_latches_openai(self):
        payload = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial"}]}}]}
        with provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post", side_effect=[
                response(payload), response(gpt()), response(gpt("next"))]) as post:
            self.assertEqual(helper.gemini_generate([{"text": "input"}], api_key="private-google-key"), "complete text")
            self.assertEqual(helper.gemini_generate([{"text": "next input"}], api_key="private-google-key"), "next")
            self.assertTrue(run.google_stopped)
            self.assertFalse(run.failed)
            self.assertEqual(run.switch_reason, "Gemini output limit (MAX_TOKENS)")
            self.assertEqual(post.call_count, 3)
            self.assertEqual(post.call_args_list[0].kwargs["json"]["generationConfig"]["maxOutputTokens"], 16384)
            self.assertNotIn("partial", json.dumps(post.call_args_list[1].kwargs["json"]))
            self.assertEqual(json.loads((run.directory / "0001.json").read_text())["raw"], payload)

    def test_audio_output_limit_uses_actual_audio_then_openai_summary(self):
        audio = self.root / "input.wav"; audio.write_bytes(b"actual audio")
        state = helper.RunState("https://example.com/a.wav", self.root, audio_path=audio)
        start = response({}); start.headers = {"X-Goog-Upload-URL": "https://upload.example"}
        payload = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "BAD partial"}]}}]}
        summary = {"email_subject": "Test", "detailed_summary": "- Actual point.", "whatsapp_summary": "- Actual point.", "who": "Unknown", "transcript_possible": True}
        with provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post", side_effect=[
                start, response({"file": {"uri": "private-gemini-file"}}), response(payload),
                response({"text": "Complete actual transcript."}), response(gpt(json.dumps(summary)))]) as post:
            self.assertTrue(helper.transcribe_audio(state))
            self.assertEqual(state.transcript_text, "Complete actual transcript.")
            self.assertEqual(state.transcript_source, "openai-audio")
            self.assertEqual(helper.summarize(state)["detailed_summary"], "- Actual point.")
            self.assertEqual(post.call_count, 5)
            self.assertTrue(run.google_stopped)
            self.assertIn("/audio/transcriptions", post.call_args_list[3].args[0])
            self.assertEqual(post.call_args_list[3].kwargs["files"]["file"][0], "input.wav")
            self.assertNotIn("BAD partial", post.call_args_list[4].kwargs["json"]["input"])
            self.assertNotIn("private-gemini-file", post.call_args_list[4].kwargs["json"]["input"])

    def test_only_output_limit_not_safety_unknown_or_malformed_can_switch(self):
        payloads = [
            {"candidates": [{"finishReason": reason}]} for reason in
            ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "OTHER", None)
        ] + [{"candidates": []}, {"candidates": "bad"},
             {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
             {"candidates": [{"finishReason": "STOP", "content": {"parts": [None]}}]},
             {"promptFeedback": {"blockReason": "SAFETY"}, "candidates": [{"finishReason": "MAX_TOKENS"}]},
             {"candidates": [{"finishReason": "MAX_TOKENS", "safetyRatings": [{"blocked": True}]}]}]
        for i, payload in enumerate(payloads):
            with self.subTest(payload=payload), provider.scope(self.root / str(i)) as run, \
                    mock.patch.object(provider.requests, "post", return_value=response(payload)) as post:
                for _ in range(2):
                    with self.assertRaises(provider.ProviderError):
                        helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
                post.assert_called_once()
                self.assertTrue(run.failed)
                self.assertIsNone(run.switch_reason)

    def test_output_limit_respects_fallback_opt_out_and_missing_key(self):
        payload = {"candidates": [{"finishReason": "MAX_TOKENS"}]}
        for env in ({"SUM_OPENAI_FALLBACK": "0"}, {"OPENAI_API_KEY": ""}):
            with self.subTest(env=env), mock.patch.dict(helper.os.environ, env), provider.scope(self.root / "job"), \
                    mock.patch.object(provider.requests, "post", return_value=response(payload)) as post:
                for _ in range(2):
                    with self.assertRaises(provider.ProviderError):
                        helper.gemini_generate([{"text": "input"}], api_key="private-google-key")
                post.assert_called_once()

    def test_openai_chunk_failure_never_returns_prefix_or_continues_peers(self):
        audio = self.root / "input.wav"; audio.write_bytes(b"wav")
        for bad in ({"text": "   "}, {"text": 42}, {"text": "partial", "usage": {"output_tokens": 2048}}):
            with self.subTest(bad=bad), provider.scope(self.root / "job") as run, \
                    mock.patch.object(helper, "openai_transcription_inputs", return_value=[audio, audio, audio]), \
                    mock.patch.object(provider.requests, "post", side_effect=[response({"text": "prefix"}), response(bad)]) as post:
                with self.assertRaises(provider.ProviderError):
                    helper.transcribe_with_openai(audio, "private-test-key")
                self.assertTrue(run.failed)
                with self.assertRaises(provider.ProviderError):
                    helper.gemini_generate([{"text": "must not summarize prefix"}], api_key="private-google-key")
                self.assertEqual(post.call_count, 2)

    def test_duration_not_just_file_size_splits_compressed_audio(self):
        audio = self.root / "small-but-long.mp3"; audio.write_bytes(b"mp3")
        chunks = [self.root / f"chunk-{i}.mp3" for i in range(4)]
        for chunk in chunks: chunk.write_bytes(b"part")
        with mock.patch.object(helper, "audio_duration", side_effect=[601, 180, 180, 180, 61]), \
                mock.patch.object(helper, "command_exists", return_value=True), \
                mock.patch.object(helper, "ffmpeg_segment_audio", return_value=chunks) as segment, \
                provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", side_effect=[
                    response({"text": f"part {i}"}) for i in range(4)]) as post:
            self.assertEqual(helper.transcribe_with_openai(audio, "private-test-key"), "part 0\n\npart 1\n\npart 2\n\npart 3")
            self.assertEqual(segment.call_args.kwargs["segment_seconds"], 180)
            self.assertEqual(post.call_count, 4)

    def test_missing_chunk_tail_stops_before_any_provider_request(self):
        audio = self.root / "input.wav"; audio.write_bytes(b"wav")
        chunk = self.root / "chunk.mp3"; chunk.write_bytes(b"part")
        with mock.patch.object(helper, "audio_duration", side_effect=[360, 180]), \
                mock.patch.object(helper, "command_exists", return_value=True), \
                mock.patch.object(helper, "ffmpeg_segment_audio", return_value=[chunk]), \
                provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post") as post:
            with self.assertRaises(provider.ProviderError):
                helper.transcribe_with_openai(audio, "private-test-key")
            self.assertTrue(run.failed)
            post.assert_not_called()

    def test_full_pipeline_output_limit_still_packages_transcript_summary_and_email(self):
        work = self.root / "scratch"; work.mkdir()
        audio = work / "input.wav"; audio.write_bytes(b"audio")
        transcript = "Not all problems are solved. A plan still matters."
        start = response({}); start.headers = {"X-Goog-Upload-URL": "https://upload.example"}
        summary = {"email_subject": "Test", "detailed_summary": "- A plan still matters.",
                   "whatsapp_summary": "- A plan still matters.", "who": "Unknown", "transcript_possible": True}
        with mock.patch.object(helper, "ensure_runtime_dirs", return_value=work), \
                mock.patch.object(helper, "resolve_url"), mock.patch.object(helper, "try_existing_transcript", return_value=False), \
                mock.patch.object(helper, "obtain_audio", return_value=audio), mock.patch.object(helper, "send_email") as email, \
                mock.patch.object(provider.requests, "post", side_effect=[start,
                    response({"file": {"uri": "private-uri"}}),
                    response({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "bad partial"}]}}]}),
                    response({"text": transcript}), response(gpt("Speaker A: " + transcript)),
                    response(gpt(json.dumps(summary)))]) as post:
            result = helper.run_pipeline("https://example.com/a.wav", email_to="test@example.com", skip_email=False)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["transcript_available"])
        self.assertTrue(result["email_sent"])
        self.assertIn("A plan still matters.", result["whatsapp_summary"])
        self.assertEqual(result["provider_fallback"], "Gemini output limit (MAX_TOKENS)")
        self.assertEqual(post.call_count, 6)
        email.assert_called_once()
        self.assertIn("Not all problems", email.call_args.kwargs["transcript_text"])
        self.assertNotIn("bad partial", email.call_args.kwargs["transcript_text"])
        self.assertFalse(work.exists())
        self.assertEqual(len(list(Path(result["provider_evidence"]).glob("*.json"))), 6)

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


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RealSumAudioChunkTests(unittest.TestCase):
    def test_real_compressed_audio_is_split_with_complete_final_tail(self):
        with tempfile.TemporaryDirectory() as temp:
            audio = Path(temp) / "input.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                            "-t", "361.25", "-b:a", "32k", str(audio)], check=True, capture_output=True)
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            chunks = helper.openai_transcription_inputs(audio)
            self.assertEqual(len(chunks), 3)
            durations = [helper.audio_duration(p) for p in chunks]
            self.assertLess(abs(sum(durations) - helper.audio_duration(audio)), 0.5)
            self.assertGreater(durations[-1], 1)
            self.assertTrue(all(d <= 180.5 for d in durations))
            self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
