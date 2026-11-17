import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_sum_fallback import helper, provider, response, gpt


FINAL = {"email_subject": "A qualified claim", "whatsapp_summary": "- Not all failures are inevitable.",
         "detailed_summary": "- Not all failures are inevitable.\n- Only some cases may qualify.",
         "who": "Unknown", "transcript_possible": True}
CHUNK = {"chunk_summary": "- Not all failures are inevitable.", "who": "Unknown",
         "important_topics": ["Qualifications", 'The "sim-to-real" gap']}
BAD = '{"chunk_summary": "The "sim-to-real" gap", "who":"Unknown", "important_topics":["AI"]}'
LONG = ("Not all failures are inevitable. " + "one " * 10000 + "\n\n"
        + "Only some cases may qualify. " + "two " * 10000)


def gemini(text, reason="STOP", **extra):
    return response({"candidates": [{"finishReason": reason, "content": {"parts": [{"text": text}]}, **extra}],
                     "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7}})


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = mock.patch.dict(helper.os.environ, {
            "OPENAI_API_KEY": "private-test-key", "GOOGLE_API_KEY": "private-google-key",
            "SUM_PROVIDER_EVIDENCE_DIR": str(self.root / "evidence")}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def summarize(self, text="Not all failures are inevitable."):
        return helper.summarize_text_for_email(transcript_text=text, source_text="", metadata={}, api_key="private-google-key")

    def test_primary_structured_summary_schema_and_plain_text_calls_are_separate(self):
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", side_effect=[
                gemini(json.dumps(FINAL)), gemini("verbatim words")]) as post:
            self.assertEqual(self.summarize(), FINAL)
            self.assertEqual(helper.gemini_generate([{"text": "speaker text"}], api_key="private-google-key"), "verbatim words")
        config = post.call_args_list[0].kwargs["json"]["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["responseJsonSchema"], helper.SUMMARY_SCHEMA)
        self.assertNotIn("responseMimeType", post.call_args_list[1].kwargs["json"]["generationConfig"])

    def test_bad_first_long_chunk_switches_once_for_all_remaining_requests(self):
        with provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post", side_effect=[
                gemini(BAD), response(gpt(json.dumps(CHUNK))), response(gpt(json.dumps(CHUNK))),
                response(gpt(json.dumps(FINAL)))]) as post:
            self.assertEqual(self.summarize(LONG), FINAL)
            self.assertEqual(run.switch_reason, "Gemini invalid summary format")
            self.assertTrue(run.google_stopped)
            self.assertEqual(len(list(run.directory.glob("*.json"))), 4)
            self.assertEqual(json.loads((run.directory / "0001.json").read_text())["raw"]["candidates"][0]["content"]["parts"][0]["text"], BAD)
        self.assertEqual(post.call_count, 4)
        calls = post.call_args_list
        self.assertTrue(all("api.openai.com" in c.args[0] for c in calls[1:]))
        self.assertIn("Not all failures", calls[1].kwargs["json"]["input"])
        self.assertIn("Only some cases", calls[2].kwargs["json"]["input"])
        self.assertNotIn(BAD, calls[1].kwargs["json"]["input"])
        self.assertNotIn("Response to repair", calls[1].kwargs["json"]["input"])
        fmt = calls[1].kwargs["json"]["text"]["format"]
        self.assertTrue(fmt["strict"])
        self.assertEqual(fmt["schema"], helper.CHUNK_SUMMARY_SCHEMA)
        self.assertEqual(calls[-1].kwargs["json"]["text"]["format"]["schema"], helper.SUMMARY_SCHEMA)

    def test_bad_later_chunk_keeps_first_valid_chunk_and_switches(self):
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", side_effect=[
                gemini(json.dumps(CHUNK)), gemini(BAD), response(gpt(json.dumps(CHUNK))), response(gpt(json.dumps(FINAL)))]) as post:
            self.assertEqual(self.summarize(LONG), FINAL)
        self.assertEqual(post.call_count, 4)
        self.assertIn("Only some cases", post.call_args_list[2].kwargs["json"]["input"])
        self.assertEqual(post.call_args_list[-1].kwargs["json"]["input"].count("Not all failures are inevitable."), 2)

    def test_final_synthesis_has_same_bounded_fallback_as_chunks(self):
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", side_effect=[
                gemini(json.dumps(CHUNK)), gemini(json.dumps(CHUNK)), gemini('{"email_subject":"bad "quote""}'),
                response(gpt(json.dumps(FINAL)))]) as post:
            self.assertEqual(self.summarize(LONG), FINAL)
        self.assertEqual(post.call_count, 4)
        self.assertIn("Chunk summaries:", post.call_args.kwargs["json"]["input"])
        self.assertNotIn('bad "quote"', post.call_args.kwargs["json"]["input"])

    def test_short_final_summary_uses_original_source_for_fallback(self):
        with provider.scope(self.root / "job"), mock.patch.object(provider.requests, "post", side_effect=[
                gemini("not JSON"), response(gpt(json.dumps(FINAL)))]) as post:
            self.assertEqual(self.summarize(), FINAL)
        self.assertEqual(post.call_count, 2)
        self.assertIn("Not all failures", post.call_args.kwargs["json"]["input"])
        self.assertNotIn("not JSON", post.call_args.kwargs["json"]["input"])

    def test_empty_completed_summary_switches_but_plain_text_empty_stays_held(self):
        for text in ("", "  "):
            with self.subTest(text=text), provider.scope(self.root / "summary"), \
                    mock.patch.object(provider.requests, "post", side_effect=[gemini(text), response(gpt(json.dumps(FINAL)))]) as post:
                self.assertEqual(self.summarize(), FINAL)
                self.assertEqual(post.call_count, 2)
        with provider.scope(self.root / "plain"), mock.patch.object(provider.requests, "post", return_value=gemini("")) as post:
            with self.assertRaises(provider.ProviderError): helper.gemini_generate([{"text": "plain"}], api_key="key")
            post.assert_called_once()

    def test_schema_errors_all_trigger_only_one_primary_switch(self):
        cases = [{}, [], {**FINAL, "who": ""}, {**FINAL, "transcript_possible": "true"},
                 {**FINAL, "whatsapp_summary": ["a bullet"]}, {**FINAL, "extra": "no"},
                 {k: v for k, v in FINAL.items() if k != "detailed_summary"}]
        for i, bad in enumerate(cases):
            with self.subTest(case=i), provider.scope(self.root / str(i)) as run, \
                    mock.patch.object(provider.requests, "post", side_effect=[gemini(json.dumps(bad)), response(gpt(json.dumps(FINAL)))]) as post:
                self.assertEqual(self.summarize(), FINAL)
                self.assertFalse(run.failed)
                self.assertTrue(run.google_stopped)
                self.assertEqual(post.call_count, 2)

    def test_bad_fallback_json_http_refusal_incomplete_and_envelopes_latch(self):
        bads = [response(gpt("bad JSON")), response(gpt(json.dumps({**FINAL, "who": 0}))),
                response(gpt(status="incomplete")), response({"error": {"code": "rate_limit_exceeded"}}, 429),
                response({"status": "completed", "output": [{"type": "message", "status": "completed",
                    "content": [{"type": "refusal", "refusal": "no"}]}]}),
                response({"status": "completed", "output": [None]}),
                response({"status": "completed", "output": [{"type": "message", "status": "completed", "content": [None]}]})]
        for i, bad in enumerate(bads):
            with self.subTest(case=i), provider.scope(self.root / str(i)) as run, \
                    mock.patch.object(provider.requests, "post", side_effect=[gemini(BAD), bad]) as post:
                for _ in range(2):
                    with self.assertRaises(provider.ProviderError): self.summarize()
                self.assertTrue(run.failed or run.openai_stopped)
                self.assertEqual(post.call_count, 2)

    def test_primary_safety_and_unknown_envelopes_never_switch(self):
        for reason in ("SAFETY", "RECITATION", "OTHER"):
            with self.subTest(reason=reason), provider.scope(self.root / reason), \
                    mock.patch.object(provider.requests, "post", return_value=gemini(BAD, reason)) as post:
                with self.assertRaises(provider.ProviderError): self.summarize()
                post.assert_called_once()
        with provider.scope(self.root / "blocked"), mock.patch.object(provider.requests, "post",
                return_value=gemini(BAD, safetyRatings=[{"blocked": True}])) as post:
            with self.assertRaises(provider.ProviderError): self.summarize()
            post.assert_called_once()

    def test_structured_summaries_do_not_switch_for_malformed_or_thought_only_envelopes(self):
        for parts in ([], [{}], [{"text": 42}], [{"functionCall": {"name": "unexpected"}}],
                      [{"thought": True, "text": "internal"}], [{"text": "valid"}, {}]):
            with self.subTest(parts=parts), provider.scope(self.root / "bad") as run, \
                    mock.patch.object(provider.requests, "post", return_value=response({
                        "candidates": [{"finishReason": "STOP", "content": {"parts": parts}}]})) as post:
                for _ in range(2):
                    with self.assertRaises(provider.ProviderError): self.summarize()
                post.assert_called_once()
                self.assertTrue(run.failed)
                self.assertIsNone(run.switch_reason)

    def test_structured_summary_never_consumes_audio_file_reference(self):
        with provider.scope(self.root / "job") as run, mock.patch.object(provider.requests, "post") as post:
            with self.assertRaises(provider.ProviderError):
                run.summary([{"file_data": {"file_uri": "uri"}}], "key", "model", 0.1, helper.SUMMARY_SCHEMA)
            post.assert_not_called()

    def test_opt_out_and_missing_openai_key_do_not_make_fallback_calls(self):
        for env in ({"SUM_OPENAI_FALLBACK": "0"}, {"OPENAI_API_KEY": ""}):
            with self.subTest(env=env), mock.patch.dict(helper.os.environ, env), provider.scope(self.root / "job"), \
                    mock.patch.object(provider.requests, "post", return_value=gemini(BAD)) as post:
                for _ in range(2):
                    with self.assertRaises(provider.ProviderError): self.summarize()
                post.assert_called_once()

    def test_explicit_openai_and_new_run_reset(self):
        with mock.patch.dict(helper.os.environ, {"SUM_PROVIDER": "openai", "SUM_OPENAI_FALLBACK": "0"}), \
                provider.scope(self.root / "one"), mock.patch.object(provider.requests, "post", return_value=response(gpt(json.dumps(FINAL)))) as post:
            self.assertEqual(self.summarize(), FINAL)
            self.assertIn("api.openai.com", post.call_args.args[0])
        with provider.scope(self.root / "two") as run, mock.patch.object(provider.requests, "post", return_value=gemini(json.dumps(FINAL))) as post:
            self.assertFalse(run.google_stopped)
            self.assertEqual(self.summarize(), FINAL)
            post.assert_called_once()

    def test_transcript_availability_is_known_state_not_model_guess(self):
        for transcript, claimed, expected in (("Complete actual transcript.", False, True),
                                               (None, True, False), ("  ", True, False)):
            with self.subTest(transcript=transcript), provider.scope(self.root / "state"), \
                    mock.patch.object(provider.requests, "post", return_value=gemini(json.dumps({**FINAL, "transcript_possible": claimed}))) as post:
                result = helper.summarize_text_for_email(transcript_text=transcript, source_text="Metadata only.", metadata={}, api_key="private-google-key")
                self.assertIs(result['transcript_possible'], expected)
                self.assertEqual(result['detailed_summary'], FINAL['detailed_summary'])
                post.assert_called_once()

    def test_strict_parser_rejects_duplicates_prose_nonfinite_and_bad_field_types(self):
        bads = [BAD, json.dumps(FINAL) + " extra", "prefix " + json.dumps(FINAL),
                json.dumps(FINAL)[:-1] + ',"who":"duplicate"}',
                json.dumps(FINAL).replace('"transcript_possible": true', '"transcript_possible": NaN'),
                "x" * 200001]
        for text in bads:
            with self.subTest(text=text[:50]), self.assertRaises(ValueError): provider.parse_summary(text, helper.SUMMARY_SCHEMA)
        for bad in ({**CHUNK, "important_topics": []}, {**CHUNK, "important_topics": [None]}, {**CHUNK, "chunk_summary": " "}):
            with self.assertRaises(ValueError): provider.parse_summary(json.dumps(bad), helper.CHUNK_SUMMARY_SCHEMA)

    def test_escaped_quotes_and_russian_text_preserved_without_repair(self):
        value = {**FINAL, "email_subject": 'Что значит "sim-to-real"?', "detailed_summary": '- Не все случаи — провал.\n- Возможно, только 3 из 10.'}
        for text in (json.dumps(value, ensure_ascii=False), "```json\n" + json.dumps(value) + "\n```"):
            self.assertEqual(provider.parse_summary(text, helper.SUMMARY_SCHEMA), value)

    def test_full_long_pipeline_no_repeat_download_asr_and_email_package(self):
        work = self.root / "scratch"; work.mkdir()
        def existing(state):
            state.transcript_text = LONG
            state.transcript_source = "cached-full-transcript"
            return True
        with mock.patch.object(helper, "ensure_runtime_dirs", return_value=work), mock.patch.object(helper, "resolve_url"), \
                mock.patch.object(helper, "try_existing_transcript", side_effect=existing), \
                mock.patch.object(helper, "obtain_audio", side_effect=AssertionError("No repeat download")), \
                mock.patch.object(helper, "transcribe_audio", side_effect=AssertionError("No repeat ASR")), \
                mock.patch.object(helper, "diarize_transcript_with_gemini"), mock.patch.object(helper, "send_email") as email, \
                mock.patch.object(provider.requests, "post", side_effect=[gemini(BAD), response(gpt(json.dumps(CHUNK))),
                    response(gpt(json.dumps(CHUNK))), response(gpt(json.dumps(FINAL)))]) as post:
            result = helper.run_pipeline("https://example.com/episode", email_to="test@example.com", skip_email=False)
        self.assertTrue(result["transcript_available"] and result["email_sent"])
        self.assertEqual(result["status"], "ok")
        email.assert_called_once()
        self.assertEqual(email.call_args.kwargs["transcript_text"], LONG)
        self.assertEqual(email.call_args.kwargs["summary"]["detailed_summary"], FINAL["detailed_summary"])
        self.assertEqual(post.call_count, 4)
        self.assertEqual(len(list(Path(result["provider_evidence"]).glob("*.json"))), 4)
        self.assertFalse(work.exists())

    def test_terminal_failure_keeps_complete_transcript_and_never_emails_prefix(self):
        work = self.root / "scratch"; work.mkdir()
        def existing(state):
            state.transcript_text = LONG; state.transcript_source = "cached-full-transcript"; return True
        with mock.patch.object(helper, "ensure_runtime_dirs", return_value=work), mock.patch.object(helper, "resolve_url"), \
                mock.patch.object(helper, "try_existing_transcript", side_effect=existing), \
                mock.patch.object(helper, "diarize_transcript_with_gemini"), mock.patch.object(helper, "send_email") as email, \
                mock.patch.object(provider.requests, "post", side_effect=[gemini(BAD), response(gpt("bad fallback"))]) as post:
            with self.assertRaises(provider.ProviderError):
                helper.run_pipeline("https://example.com/episode", email_to="test@example.com", skip_email=False)
        email.assert_not_called()
        self.assertEqual(post.call_count, 2)
        self.assertTrue(work.exists())
        self.assertEqual(next(work.glob('*.transcript.txt')).read_text(), LONG.strip() + "\n")


if __name__ == "__main__": unittest.main()
