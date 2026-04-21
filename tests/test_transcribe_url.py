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
