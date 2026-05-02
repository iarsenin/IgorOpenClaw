import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "transcribe-url.py"


def load_module():
    spec = importlib.util.spec_from_file_location("transcribe_url", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, *, url: str, content_type: str):
        self.url = url
        self.headers = {"Content-Type": content_type}
        self.closed = False

    def raise_for_status(self):
        return None

    @property
    def text(self):
        raise AssertionError("resolve_url should not read the body for direct media responses")

    def close(self):
        self.closed = True


class TranscribeUrlTests(unittest.TestCase):
    def test_email_summary_prompt_demands_dense_non_teaser_bullets(self):
        module = load_module()
        captured = {}

        def fake_gemini_generate(contents, **kwargs):
            captured["prompt"] = contents[0]["text"]
            return """{
              "email_subject": "AI compute bottlenecks",
              "whatsapp_summary": "AI compute bottlenecks\\n- Scaling is constrained by power, memory, and fabs.",
              "detailed_summary": "- Main takeaway: AI compute is bottlenecked by physical infrastructure, not just GPU demand.",
              "who": "Unknown",
              "transcript_possible": true
            }"""

        with mock.patch.object(module, "gemini_generate", side_effect=fake_gemini_generate):
            result = module.summarize_text_for_email(
                transcript_text="Example transcript text.",
                source_text="",
                metadata={"title": "AI compute bottlenecks"},
                api_key="test-key",
            )

        self.assertEqual(result["email_subject"], "AI compute bottlenecks")
        prompt = captured["prompt"]
        self.assertIn("Bullets should let Igor skip the transcript", prompt)
        self.assertIn("Do not write teaser bullets", prompt)
        self.assertIn("Bad:", prompt)
        self.assertIn("Good:", prompt)
        self.assertIn("First bullet should state the main takeaway immediately", prompt)
        self.assertIn("whatsapp_summary should match detailed_summary", prompt)

    def test_rewrite_whatsapp_summary_falls_back_without_gemini_key(self):
        module = load_module()

        with mock.patch.object(module, "format_whatsapp_summary", return_value="LOCAL SUMMARY"), \
             mock.patch.object(module, "gemini_generate", side_effect=AssertionError("gemini should not be called")):
            result = module.rewrite_whatsapp_summary(
                title="Episode title",
                who="Host Name",
                detailed_summary="- Point one\n- Point two",
                fallback_summary="Fallback summary",
                metadata={},
                api_key="",
            )

        self.assertEqual(result, "LOCAL SUMMARY")

    def test_whatsapp_rewrite_prompt_demands_short_takeaway_bullets(self):
        module = load_module()
        captured = {}

        def fake_gemini_generate(contents, **kwargs):
            captured["prompt"] = contents[0]["text"]
            return "Episode title\n- Main takeaway.\n- Why it matters."

        with mock.patch.object(module, "gemini_generate", side_effect=fake_gemini_generate):
            result = module.rewrite_whatsapp_summary(
                title="Episode title",
                who="Host Name",
                detailed_summary="- Main takeaway: scaling is infrastructure-limited.\n- Why it matters: compute access may decide winners.",
                fallback_summary="Fallback summary",
                metadata={},
                api_key="test-key",
            )

        self.assertEqual(result, "Episode title\n- Main takeaway.\n- Why it matters.")
        prompt = captured["prompt"]
        self.assertIn("Then write 2 to 4 bullet points", prompt)
        self.assertIn("Each bullet should deliver the takeaway, implication, or recommendation directly", prompt)
        self.assertIn("Do not tease or say that the item discusses/explores/covers a topic", prompt)
        self.assertIn("Bad:", prompt)
        self.assertIn("Good:", prompt)

    def test_format_whatsapp_summary_prioritizes_takeaway_before_who(self):
        module = load_module()

        result = module.format_whatsapp_summary(
            title="Episode title",
            who="Host Name",
            detailed_summary=(
                "- Main takeaway: AI scaling is constrained by fabs and power.\n"
                "- Why it matters: capacity access may decide who wins.\n"
                "- Evidence: hyperscalers are reserving infrastructure years ahead."
            ),
            fallback_summary="Fallback summary",
        )

        lines = result.splitlines()
        self.assertEqual(lines[0], "Episode title")
        self.assertTrue(lines[1].startswith("- Main takeaway:"))
        self.assertNotIn("- Who: Host Name", lines[1])

    def test_build_html_email_body_normalizes_list_summary_items(self):
        module = load_module()

        body = module.build_html_email_body(
            summary={
                "who": "Unknown",
                "detailed_summary": [
                    "Main takeaway: AI is missing a richer learning objective.",
                    "Why it matters: current models optimize much narrower targets than brains do.",
                ],
            },
            metadata={"title": "Brain learning", "resolved_url": "https://example.com"},
            transcript_text="Transcript text.",
            transcript_source=None,
        )

        self.assertIn("<li>Main takeaway: AI is missing a richer learning objective.</li>", body)
        self.assertIn("<li>Why it matters: current models optimize much narrower targets than brains do.</li>", body)
        self.assertNotIn("['", body)
        self.assertNotIn("']", body)

    def test_summarize_normalizes_list_fields_from_model_response(self):
        module = load_module()
        state = module.RunState(original_url="https://example.com", workdir=Path("/tmp"))
        state.metadata = {"title": "Brain learning"}
        state.source_text = "Source text"
        state.transcript_text = "Transcript text"

        with mock.patch.object(module, "read_env_key", return_value="test-key"), \
             mock.patch.object(
                 module,
                 "summarize_text_for_email",
                 return_value={
                     "email_subject": "Brain learning",
                     "whatsapp_summary": ["Main takeaway: brains learn with richer objectives."],
                     "detailed_summary": [
                         "Main takeaway: AI is missing a richer learning objective.",
                         "Why it matters: current models optimize much narrower targets than brains do.",
                     ],
                     "who": "Unknown",
                     "transcript_possible": True,
                 },
             ):
            summary = module.summarize(state)

        self.assertEqual(
            summary["detailed_summary"],
            "- Main takeaway: AI is missing a richer learning objective.\n"
            "- Why it matters: current models optimize much narrower targets than brains do.",
        )
        self.assertEqual(summary["whatsapp_summary"], summary["detailed_summary"])

    def test_summarize_prefers_full_detailed_summary_for_whatsapp(self):
        module = load_module()
        state = module.RunState(original_url="https://example.com", workdir=Path("/tmp"))
        state.metadata = {"title": "Brain learning"}
        state.source_text = "Source text"
        state.transcript_text = "Transcript text"

        with mock.patch.object(module, "read_env_key", return_value="test-key"), \
             mock.patch.object(
                 module,
                 "summarize_text_for_email",
                 return_value={
                     "email_subject": "Brain learning",
                     "whatsapp_summary": "Short teaser",
                     "detailed_summary": [
                         "Main takeaway: brains use richer objectives than current AI.",
                         "Why it matters: scaling alone may not produce brain-like generalization.",
                     ],
                     "who": "Unknown",
                     "transcript_possible": True,
                 },
             ):
            summary = module.summarize(state)

        self.assertEqual(
            summary["whatsapp_summary"],
            "- Main takeaway: brains use richer objectives than current AI.\n"
            "- Why it matters: scaling alone may not produce brain-like generalization.",
        )

    def test_run_pipeline_does_not_rewrite_or_shorten_whatsapp_summary(self):
        module = load_module()
        workdir = Path("/tmp/transcribe-run-pipeline-test")
        state = module.RunState(original_url="https://example.com", workdir=workdir)
        state.metadata = {"title": "Brain learning", "resolved_url": "https://example.com"}
        state.transcript_text = "Transcript text"
        state.transcript_path = workdir / "transcript.txt"
        state.transcript_path.parent.mkdir(parents=True, exist_ok=True)
        state.transcript_path.write_text("Transcript text", encoding="utf-8")

        full_summary = (
            "- Main takeaway: brains use richer objectives than current AI.\n"
            "- Why it matters: scaling alone may not produce brain-like generalization.\n"
            "- Evidence: the discussion contrasts omnidirectional prediction with next-token prediction."
        )

        with mock.patch.object(module, "ensure_runtime_dirs", return_value=workdir), \
             mock.patch.object(module, "resolve_url", side_effect=lambda s: None), \
             mock.patch.object(module, "try_existing_transcript", return_value=True), \
             mock.patch.object(module, "write_transcript", side_effect=lambda s: None), \
             mock.patch.object(module, "summarize", return_value={
                 "email_subject": "Brain learning",
                 "whatsapp_summary": "Short teaser",
                 "detailed_summary": full_summary,
                 "who": "Unknown",
             }), \
             mock.patch.object(module, "rewrite_whatsapp_summary", side_effect=AssertionError("should not rewrite")), \
             mock.patch.object(module, "send_email", side_effect=AssertionError("should not email")):
            result = module.run_pipeline("https://example.com", email_to=None, skip_email=True)

        self.assertEqual(result["whatsapp_summary"], full_summary)

    def test_hydrate_metadata_uses_og_title_without_html_title(self):
        module = load_module()
        state = module.RunState(original_url="https://example.com/post", workdir=Path("/tmp"))

        metadata = module.hydrate_metadata_from_html(
            "https://example.com/post",
            """
            <html>
              <head>
                <meta property="og:title" content="Open Graph Title">
                <meta property="og:description" content="Description from og">
              </head>
              <body><p>Hello</p></body>
            </html>
            """,
            state,
        )

        self.assertEqual(metadata["title"], "Open Graph Title")
        self.assertEqual(metadata["description"], "Description from og")

    def test_resolve_url_short_circuits_direct_media_fetches(self):
        module = load_module()
        state = module.RunState(original_url="https://cdn.example.com/audio.mp3", workdir=Path("/tmp"))
        response = FakeResponse(url="https://cdn.example.com/audio.mp3", content_type="audio/mpeg")

        with mock.patch.object(module, "yt_dlp_probe", return_value=None), \
             mock.patch.object(module, "fetch", return_value=response), \
             mock.patch.object(module, "hydrate_metadata_from_html", side_effect=AssertionError("html hydration should be skipped")), \
             mock.patch.object(module, "enrich_from_rss_feeds", return_value=None):
            module.resolve_url(state)

        self.assertTrue(state.accessible)
        self.assertEqual(state.access_method, "http")
        self.assertEqual(state.metadata["resolved_url"], "https://cdn.example.com/audio.mp3")
        self.assertEqual(state.metadata["platform"], "cdn.example.com")
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
