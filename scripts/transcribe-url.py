#!/usr/bin/env python3
"""Resolve, transcribe, summarize, and email media URLs for Clawd.

Pipeline:
1. Resolve the URL and collect metadata.
2. Prefer an existing full transcript where available.
3. Otherwise acquire audio and transcribe it.
4. Produce a short WhatsApp summary and a richer email summary.
5. Email the summary + transcript only when a full transcript exists.

Dependencies:
- Python stdlib
- requests, beautifulsoup4 (already available in this repo environment)
- Optional but strongly recommended: yt-dlp, ffmpeg

This script intentionally prints JSON for deterministic agent consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import smtplib
import subprocess
import sys
import textwrap
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)
TIMEOUT = 25
WHATSAPP_MAX = 900
WHATSAPP_BULLET_MIN = 3
WHATSAPP_BULLET_MAX = 5
GEMINI_MODEL = "gemini-2.5-flash-lite"
SUMMARY_CHUNK_CHARS = 70000
TRANSCRIPT_INLINE_MAX = 120000
TRANSCRIBE_CHUNK_BYTES = 20 * 1024 * 1024

MEDIA_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".oga",
    ".ogg",
    ".wav",
    ".webm",
}
TRANSCRIPT_EXTENSIONS = {".json", ".srt", ".txt", ".vtt"}
GEMINI_SAFE_EXTENSIONS = {".aac", ".aiff", ".flac", ".mp3", ".ogg", ".wav"}
OPENAI_SAFE_EXTENSIONS = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".wav", ".webm"}
GENERIC_SPEAKER_RE = re.compile(r"^(Speaker \d+):\s*(.+)$")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", "-", value, flags=re.UNICODE)
    value = re.sub(r"[^\w.-]", "", value, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value)
    value = value.strip("._-")
    return value[:80] or "item"


def unique_strings(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = html.unescape(str(value or "")).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start:end + 1])


def build_fallback_summary(*, transcript_text: str | None, source_text: str, metadata: dict) -> dict:
    title = metadata.get("title") or "Untitled"
    resolved_url = metadata.get("resolved_url") or metadata.get("original_url") or ""
    speaker_names = metadata.get("speaker_names")
    if isinstance(speaker_names, list) and speaker_names:
        who = ", ".join(speaker_names)
    else:
        who = metadata.get("author") or metadata.get("feed_title") or "Unknown"

    summary_seed = ""
    if metadata.get("description"):
        summary_seed = str(metadata["description"]).strip()
    elif source_text:
        summary_seed = source_text.strip()
    elif transcript_text:
        summary_seed = transcript_text.strip()
    summary_seed = re.sub(r"\s+", " ", summary_seed)

    if transcript_text:
        status_line = "Transcript ready."
    else:
        status_line = "Transcript unavailable."

    whatsapp_summary = f"{title}\n{status_line}"
    if who != "Unknown":
        whatsapp_summary += f" Who: {who}."
    if summary_seed:
        whatsapp_summary += f" {summary_seed[: max(0, WHATSAPP_MAX - len(whatsapp_summary) - 1)].strip()}"
    whatsapp_summary = whatsapp_summary[:WHATSAPP_MAX].rstrip()

    detailed_lines = [
        f"- Title: {title}",
        f"- Source: {resolved_url}",
        f"- Who: {who}",
    ]
    if metadata.get("published_at"):
        detailed_lines.append(f"- Published: {metadata['published_at']}")
    if metadata.get("duration_seconds"):
        detailed_lines.append(f"- Duration: {int(metadata['duration_seconds'])} seconds")
    if summary_seed:
        detailed_lines.extend(["", summary_seed[:4000].strip()])

    return {
        "email_subject": f"[Transcript] {title}",
        "whatsapp_summary": whatsapp_summary,
        "detailed_summary": "\n".join(detailed_lines).strip(),
        "who": who,
        "transcript_possible": bool(transcript_text),
    }


def sh(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def command_exists(name: str) -> bool:
    return bool(sh(["/bin/zsh", "-lc", f"command -v {name}"]).stdout.strip())


def read_env_key(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


@dataclass
class RunState:
    original_url: str
    workdir: Path
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    transcript_text: str | None = None
    transcript_path: Path | None = None
    transcript_source: str | None = None
    audio_path: Path | None = None
    access_method: str | None = None
    accessible: bool = False
    email_sent: bool = False
    email_subject: str | None = None
    whatsapp_summary: str | None = None
    detailed_summary: str | None = None


def fetch(url: str, *, stream: bool = False, allow_redirects: bool = True) -> requests.Response:
    resp = SESSION.get(url, timeout=TIMEOUT, allow_redirects=allow_redirects, stream=stream)
    ctype = resp.headers.get("Content-Type", "")
    if "charset=" not in ctype.lower():
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp


def is_youtube(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def likely_direct_media(url: str, content_type: str | None) -> bool:
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in MEDIA_EXTENSIONS:
        return True
    if content_type and (content_type.startswith("audio/") or content_type.startswith("video/")):
        return True
    return False


def likely_transcript_link(url: str) -> bool:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in TRANSCRIPT_EXTENSIONS:
        return True
    lowered = url.lower()
    return any(token in lowered for token in ("transcript", "captions", "subtitle", "subtitles"))


def looks_like_rss_feed(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith((".rss", ".xml", "/feed")):
        return True
    lowered = url.lower()
    return any(token in lowered for token in ("podcast.rss", "/rss", "feed.xml"))


def transcript_blob_extension(url: str, content_type: str | None) -> str:
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in TRANSCRIPT_EXTENSIONS:
        return ext
    query = {k.lower(): [v.lower() for v in vals] for k, vals in parse_qs(urlparse(url).query).items()}
    format_hint = " ".join(query.get("format", []) + query.get("type", []))
    content_type = (content_type or "").lower()
    if "webvtt" in format_hint or "webvtt" in content_type or "vtt" in format_hint:
        return ".vtt"
    if "subrip" in format_hint or "srt" in format_hint or "subrip" in content_type:
        return ".srt"
    if "json" in format_hint or "json" in content_type:
        return ".json"
    return ".txt"


def transcript_link_rank(url: str) -> tuple[int, str]:
    lowered = url.lower()
    if "textwithtimestamps" in lowered or lowered.endswith(".txt"):
        return (0, lowered)
    if "webvtt" in lowered or lowered.endswith(".vtt"):
        return (1, lowered)
    if "subrip" in lowered or lowered.endswith(".srt"):
        return (2, lowered)
    if lowered.endswith(".json"):
        return (3, lowered)
    return (4, lowered)


def extract_urls_from_text(raw: str) -> list[str]:
    return unique_strings(re.findall(r"https?://[^\s\"'<>]+", html.unescape(raw or "")))


def parse_vtt(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        line = html.unescape(line.strip())
        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if line.startswith(("Kind:", "Language:")):
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue
        line = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
        line = re.sub(r"</?c(?:\.[^>]*)?>", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        lines.append(line)
    return "\n".join(_dedupe_adjacent(lines)).strip()


def parse_srt(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "-->" in line or line.isdigit():
            continue
        lines.append(line)
    return "\n".join(_dedupe_adjacent(lines)).strip()


def parse_transcript_blob(raw: str, ext: str) -> str:
    ext = ext.lower()
    if ext == ".vtt":
        return parse_vtt(raw)
    if ext == ".srt":
        return parse_srt(raw)
    if ext == ".txt":
        return raw.strip()
    if ext == ".json":
        data = json.loads(raw)
        lines = []
        for key in ("events", "segments", "transcript", "captions"):
            value = data.get(key) if isinstance(data, dict) else None
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("utf8")
                        if text:
                            lines.append(str(text).strip())
                if lines:
                    break
        if not lines and isinstance(data, dict):
            text = data.get("text")
            if isinstance(text, str):
                return text.strip()
        return "\n".join(_dedupe_adjacent(lines)).strip()
    return raw.strip()


def _dedupe_adjacent(lines: Iterable[str]) -> list[str]:
    out = []
    prev = None
    for line in lines:
        if line == prev:
            continue
        out.append(line)
        prev = line
    return out


def split_transcript_blocks(transcript_text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in transcript_text.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line.rstrip())
    if current:
        blocks.append(current)
    return blocks


def extract_speaker_segments(transcript_text: str) -> list[dict]:
    segments: list[dict] = []
    for block in split_transcript_blocks(transcript_text):
        timestamp = None
        label_line = block[0]
        text_lines = block[1:]
        if re.match(r"^\d{2}:\d{2}:\d{2}$", block[0]) and len(block) >= 2:
            timestamp = block[0]
            label_line = block[1]
            text_lines = block[2:]
        match = GENERIC_SPEAKER_RE.match(label_line)
        if not match:
            continue
        text = " ".join(line.strip() for line in text_lines if line.strip())
        if not text:
            text = match.group(2).strip()
        segments.append(
            {
                "timestamp": timestamp,
                "label": match.group(1),
                "lead_text": match.group(2).strip(),
                "text": text.strip(),
            }
        )
    return segments


def clean_person_name(name: str) -> str:
    name = re.sub(r"^[^A-Za-z]+|[^A-Za-z.' -]+$", "", name.strip())
    name = re.sub(r"\s+", " ", name).strip(" ,.-")
    return name


def extract_intro_name(text: str) -> str | None:
    patterns = [
        r"\b(?:i am|i'm|and i'm|this is)\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2})\b",
        r"\bmy name is\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        candidate = clean_person_name(match.group(1))
        if candidate:
            return candidate
    return None


def extract_guest_name_from_intro(text: str) -> str | None:
    patterns = [
        r"\bour guest(?: today| this week)?\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\b",
        r"\b(?:speaking with|talking with|talk with|joined by|welcome)\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\b",
        r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s+(?:is|was)\s+(?:a|an|the)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = clean_person_name(match.group(1))
        if candidate and len(candidate.split()) >= 2:
            return candidate
    return None


def infer_speaker_map_heuristic(transcript_text: str) -> dict[str, str]:
    segments = extract_speaker_segments(transcript_text)
    if not segments:
        return {}

    mapping: dict[str, str] = {}
    intro_window = segments[:18]

    for segment in intro_window:
        name = extract_intro_name(segment["text"])
        if name:
            mapping.setdefault(segment["label"], name)
        if "bloomberg audio studios" in segment["text"].lower():
            mapping.setdefault(segment["label"], "Bloomberg Announcer")

    for index, segment in enumerate(intro_window[:-1]):
        guest_name = extract_guest_name_from_intro(segment["text"])
        if not guest_name:
            continue
        for follow in intro_window[index + 1:index + 4]:
            lowered = follow["text"].lower()
            if follow["label"] in mapping:
                continue
            if "thank you for having me" in lowered or "thanks for having me" in lowered:
                mapping[follow["label"]] = guest_name
                break

    return mapping


def infer_speaker_map_with_model(transcript_text: str, metadata: dict, api_key: str, seed_map: dict[str, str]) -> dict[str, str]:
    segments = extract_speaker_segments(transcript_text)
    labels = sorted({segment["label"] for segment in segments})
    if not labels:
        return {}

    prompt = textwrap.dedent(
        f"""
        You are cleaning a diarized podcast transcript that currently uses generic labels like Speaker 1.

        Infer the most likely real speaker names for each generic label when the transcript makes them clear.
        Use exact speaker labels from this list: {", ".join(labels)}.

        Rules:
        - Return JSON only.
        - Output shape: {{"mapping": {{"Speaker 1": "Name", "Speaker 2": "Name"}}}}.
        - If a speaker is clearly the intro bumper, use "Bloomberg Announcer" or similar descriptive role.
        - If two generic labels are clearly the same person, map both to the same real name.
        - If a label cannot be inferred confidently, omit it from the mapping.
        - Do not invent people not supported by the transcript or metadata.

        Metadata:
        {json.dumps({k: metadata.get(k) for k in ['title', 'author', 'feed_title', 'description']}, ensure_ascii=False)}

        Seed mapping already inferred:
        {json.dumps(seed_map, ensure_ascii=False)}

        Transcript excerpt:
        {transcript_text[:16000]}
        """
    ).strip()
    result = gemini_generate([{"text": prompt}], api_key=api_key, temperature=0.0)
    payload = extract_json_object(result)
    mapping = payload.get("mapping")
    if not isinstance(mapping, dict):
        return {}
    clean_mapping: dict[str, str] = {}
    for label, name in mapping.items():
        label = str(label).strip()
        name = clean_person_name(str(name))
        if label in labels and name:
            clean_mapping[label] = name
    return clean_mapping


def infer_remaining_speaker_aliases(transcript_text: str, metadata: dict, api_key: str, current_map: dict[str, str]) -> dict[str, str]:
    segments = extract_speaker_segments(transcript_text)
    all_labels = sorted({segment["label"] for segment in segments})
    unresolved = [label for label in all_labels if label not in current_map]
    if not unresolved:
        return {}

    first_index: dict[str, int] = {}
    for idx, segment in enumerate(segments):
        first_index.setdefault(segment["label"], idx)
    labels_by_name: dict[str, list[str]] = {}
    for label, name in current_map.items():
        labels_by_name.setdefault(name, []).append(label)
    reference_snippets: dict[str, list[str]] = {}
    for name, candidate_labels in labels_by_name.items():
        texts = []
        for segment in segments:
            if segment["label"] in candidate_labels:
                texts.append(segment["text"])
            if len(texts) >= 5:
                break
        if texts:
            reference_snippets[name] = texts

    aliases: dict[str, str] = {}
    for label in unresolved:
        label_idx = first_index.get(label, 10**9)
        eligible_names = []
        for name, candidate_labels in labels_by_name.items():
            candidate_indices = [first_index.get(candidate, 10**9) for candidate in candidate_labels]
            if not candidate_indices:
                continue
            if min(candidate_indices) > label_idx + 2:
                continue
            if min(abs(idx - label_idx) for idx in candidate_indices) > 24:
                continue
            eligible_names.append(name)
        if not eligible_names:
            continue

        snippets = [segment["text"] for segment in segments if segment["label"] == label][:8]
        prompt = textwrap.dedent(
            f"""
            A podcast transcript diarizer split one real speaker into multiple generic labels.
            Decide whether {label} is actually one of the already named people listed below.

            Return JSON only in this shape:
            {{"mapping": {{"{label}": "Tracy Alloway"}}}}

            Rules:
            - Only use one of these existing names: {json.dumps(eligible_names, ensure_ascii=False)}
            - If still ambiguous, return {{"mapping": {{}}}}.
            - Do not invent new names.

            Metadata:
            {json.dumps({k: metadata.get(k) for k in ['title', 'author', 'feed_title', 'description']}, ensure_ascii=False)}

            Current resolved mapping:
            {json.dumps(current_map, ensure_ascii=False)}

            Reference snippets for already named speakers:
            {json.dumps({name: reference_snippets.get(name, []) for name in eligible_names}, ensure_ascii=False)}

            Snippets from {label}:
            {json.dumps(snippets, ensure_ascii=False)}
            """
        ).strip()
        result = gemini_generate([{"text": prompt}], api_key=api_key, temperature=0.0)
        payload = extract_json_object(result)
        mapping = payload.get("mapping")
        if not isinstance(mapping, dict):
            continue
        resolved = clean_person_name(str(mapping.get(label, "")))
        if resolved not in eligible_names:
            continue
        aliases[label] = resolved
    return aliases


def replace_speaker_labels(transcript_text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return transcript_text

    lines: list[str] = []
    for raw_line in transcript_text.splitlines():
        line = raw_line.rstrip("\n")
        match = GENERIC_SPEAKER_RE.match(line.strip())
        if match:
            replacement = mapping.get(match.group(1))
            if replacement:
                lines.append(f"{replacement}: {match.group(2)}")
                continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def normalize_transcript_speakers(state: RunState) -> None:
    if not state.transcript_text or "Speaker " not in state.transcript_text:
        return

    speaker_map = infer_speaker_map_heuristic(state.transcript_text)
    gemini_key = read_env_key("GOOGLE_API_KEY", "GEMINI_API_KEY")
    if gemini_key:
        try:
            modeled = infer_speaker_map_with_model(state.transcript_text, state.metadata, gemini_key, speaker_map)
            speaker_map.update(modeled)
            alias_map = infer_remaining_speaker_aliases(state.transcript_text, state.metadata, gemini_key, speaker_map)
            speaker_map.update(alias_map)
        except Exception as exc:
            state.warnings.append(f"Speaker relabeling model inference failed: {exc}")

    if not speaker_map:
        return

    updated = replace_speaker_labels(state.transcript_text, speaker_map)
    if updated.strip() == state.transcript_text.strip():
        return

    state.transcript_text = updated.strip()
    unique_names = unique_strings(speaker_map.values())
    if unique_names:
        state.metadata["speaker_names"] = unique_names
    state.notes.append(f"Relabeled transcript speakers: {', '.join(f'{k}->{v}' for k, v in sorted(speaker_map.items()))}")


def normalize_subtitle_transcript_text(transcript_text: str) -> str:
    lines = []
    for raw_line in transcript_text.splitlines():
        line = html.unescape(raw_line.strip())
        if not line:
            continue
        if line.startswith(("Kind:", "Language:")):
            continue
        line = re.sub(r"^>>\s*", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        lines.append(line)

    if not lines:
        return transcript_text

    paragraphs: list[str] = []
    current = ""
    for line in lines:
        if not current:
            current = line
            continue
        if re.match(r"^[A-Z][A-Za-z .'-]{1,40}:\s", line):
            paragraphs.append(current.strip())
            current = line
            continue
        current = f"{current} {line}".strip()
        if len(current) >= 320 or re.search(r"[.!?]['\"]?$", current):
            paragraphs.append(current.strip())
            current = ""
    if current:
        paragraphs.append(current.strip())

    cleaned = []
    prev = None
    for paragraph in paragraphs:
        if paragraph == prev:
            continue
        cleaned.append(paragraph)
        prev = paragraph
    return "\n\n".join(cleaned).strip()


def format_transcript_excerpt(transcript_text: str, max_chars: int = 5000) -> str:
    excerpt = normalize_subtitle_transcript_text(transcript_text)
    return excerpt[:max_chars].strip()


def should_inline_transcript(transcript_text: str, transcript_source: str | None) -> bool:
    line_count = len(transcript_text.splitlines())
    avg_line_len = (
        sum(len(line) for line in transcript_text.splitlines()) / max(1, line_count)
        if line_count
        else 0
    )
    if transcript_source == "youtube-subtitles":
        return False
    if len(transcript_text) > 30000:
        return False
    if line_count > 450:
        return False
    if avg_line_len < 60:
        return False
    return True


def strip_basic_markdown(text: str) -> str:
    text = BeautifulSoup(str(text or ""), "html.parser").get_text(" ", strip=True)
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("`", "")
    return text


def summary_lines(summary_text: str) -> list[str]:
    lines = []
    for raw_line in str(summary_text or "").splitlines():
        line = strip_basic_markdown(raw_line.strip())
        if not line:
            continue
        line = re.sub(r"^[-*•]\s*", "", line).strip()
        if line:
            lines.append(line)
    return lines


def sentence_lines(text: str) -> list[str]:
    collapsed = re.sub(r"\s+", " ", strip_basic_markdown(str(text or "")).strip())
    if not collapsed:
        return []
    parts = re.split(r"(?:[.!?…]+|\s[-–]\s+|\?\s*|\!\s*)", collapsed)
    out = []
    seen = set()
    for part in parts:
        cleaned = part.strip(" -•\n\t")
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def shorten_bullet(text: str, *, limit: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    truncated = cleaned[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return (truncated or cleaned[: limit - 1]).rstrip() + "…"


def should_keep_who(who: str) -> bool:
    generic = {
        "unknown",
        "bloomberg",
        "youtube",
        "spotify",
        "apple podcasts",
        "overcast",
        "npr",
    }
    normalized = who.strip().casefold()
    if not normalized or normalized in generic:
        return False
    if " podcast" in normalized or " radio" in normalized:
        return False
    return True


def format_whatsapp_summary(*, title: str, who: str, detailed_summary: str, fallback_summary: str) -> str:
    title_line = str(title or "Transcript ready").strip()
    title_plain = strip_basic_markdown(title_line).casefold()
    candidates = []
    seen = set()

    def add_candidate(text: str) -> None:
        cleaned = re.sub(r"\s+", " ", strip_basic_markdown(str(text or "")).strip())
        if not cleaned:
            return
        cleaned = re.sub(r"\bTranscript (?:ready|not available)\b.*$", "", cleaned, flags=re.IGNORECASE).strip(" -:;,.")
        if not cleaned:
            return
        normalized = cleaned.casefold()
        if normalized == title_plain:
            return
        if normalized in title_plain or title_plain in normalized and len(normalized) < len(title_plain) + 20:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        candidates.append(cleaned)

    if should_keep_who(who):
        add_candidate(f"Who: {who}")

    for line in summary_lines(detailed_summary):
        add_candidate(line)
    for line in sentence_lines(fallback_summary):
        add_candidate(line)

    bullets = []
    total_length = len(title_line)
    for candidate in candidates:
        bullet = shorten_bullet(candidate)
        projected = total_length + len("\n- ") + len(bullet)
        if bullets and projected > WHATSAPP_MAX:
            break
        if not bullets and projected > WHATSAPP_MAX and len(candidate) > 80:
            bullet = shorten_bullet(candidate, limit=max(80, WHATSAPP_MAX - len(title_line) - 10))
            projected = total_length + len("\n- ") + len(bullet)
        if projected > WHATSAPP_MAX:
            continue
        bullets.append(bullet)
        total_length = projected
        if len(bullets) >= WHATSAPP_BULLET_MAX:
            break

    if not bullets:
        fallback = shorten_bullet(fallback_summary or "Transcript ready.")
        return f"{title_line}\n- {fallback}"[:WHATSAPP_MAX].rstrip()

    if len(bullets) < WHATSAPP_BULLET_MIN:
        extra_candidates = sentence_lines(fallback_summary)
        for candidate in extra_candidates:
            bullet = shorten_bullet(candidate)
            projected = total_length + len("\n- ") + len(bullet)
            if projected > WHATSAPP_MAX:
                break
            key = bullet.casefold()
            if key in {item.casefold() for item in bullets}:
                continue
            bullets.append(bullet)
            total_length = projected
            if len(bullets) >= WHATSAPP_BULLET_MIN:
                break

    return f"{title_line}\n" + "\n".join(f"- {bullet}" for bullet in bullets[:WHATSAPP_BULLET_MAX])


def html_paragraphs(text: str) -> str:
    parts = []
    for paragraph in text.split("\n\n"):
        paragraph = strip_basic_markdown(paragraph.strip())
        if not paragraph:
            continue
        parts.append(f"<p>{html.escape(paragraph)}</p>")
    return "\n".join(parts)


SPEAKER_LABEL_RE = re.compile(r"^([A-Z][A-Za-z0-9 .'\-&]{0,40}):\s+")


def _split_long_paragraph(paragraph: str, target_chars: int = 500) -> list[str]:
    if len(paragraph) <= target_chars * 1.6:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'“‘])", paragraph)
    if len(sentences) <= 1:
        return [paragraph]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= target_chars:
            current = f"{current} {sentence}"
        else:
            chunks.append(current.strip())
            current = sentence
    if current:
        chunks.append(current.strip())
    return [c for c in chunks if c]


def paragraphize_transcript(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if "\n\n" in text:
        paragraphs = [re.sub(r"[ \t]*\n[ \t]*", " ", p).strip() for p in text.split("\n\n")]
        paragraphs = [re.sub(r"\s+", " ", p) for p in paragraphs if p]
    else:
        normalized = normalize_subtitle_transcript_text(text)
        paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [re.sub(r"\s+", " ", text).strip()]
    expanded: list[str] = []
    for paragraph in paragraphs:
        expanded.extend(_split_long_paragraph(paragraph))
    return expanded


def format_transcript_html(text: str) -> str:
    parts: list[str] = []
    for paragraph in paragraphize_transcript(text):
        match = SPEAKER_LABEL_RE.match(paragraph)
        if match:
            label = match.group(1)
            rest = paragraph[match.end():]
            parts.append(
                f"<p><strong>{html.escape(label)}:</strong> {html.escape(rest)}</p>"
            )
        else:
            parts.append(f"<p>{html.escape(paragraph)}</p>")
    return "\n".join(parts) if parts else "<p><em>Transcript is empty.</em></p>"


def build_standalone_transcript_html(*, title: str, metadata: dict, transcript_text: str) -> str:
    safe_title = html.escape(title or "Transcript")
    meta_rows = []
    source_url = metadata.get("resolved_url") or metadata.get("original_url") or ""
    if source_url:
        esc = html.escape(source_url)
        meta_rows.append(f'<p><strong>Source:</strong> <a href="{esc}">{esc}</a></p>')
    who = metadata.get("speaker_names") or metadata.get("author") or metadata.get("feed_title")
    if isinstance(who, list):
        who = ", ".join(who)
    if who:
        meta_rows.append(f"<p><strong>Who:</strong> {html.escape(str(who))}</p>")
    if metadata.get("published_at"):
        meta_rows.append(f"<p><strong>Published:</strong> {html.escape(str(metadata['published_at']))}</p>")
    if metadata.get("duration_seconds"):
        meta_rows.append(
            f"<p><strong>Duration:</strong> {int(metadata['duration_seconds'])} seconds</p>"
        )
    head = (
        "<!doctype html><html><head>"
        "<meta charset=\"utf-8\">"
        f"<title>{safe_title}</title>"
        "<style>"
        "body{font-family:Georgia,'Times New Roman',serif;max-width:740px;margin:2em auto;"
        "padding:0 1em;line-height:1.6;color:#111;font-size:17px;}"
        "h1{font-family:Arial,sans-serif;font-size:1.4em;margin:0 0 .5em;}"
        ".meta{color:#555;font-family:Arial,sans-serif;font-size:.9em;margin-bottom:1.5em;}"
        ".meta p{margin:.25em 0;}"
        "p{margin:0 0 1em;}"
        "strong{color:#000;}"
        "</style></head><body>"
    )
    body = (
        f"<h1>{safe_title}</h1>"
        f"<div class=\"meta\">{''.join(meta_rows)}</div>"
        f"{format_transcript_html(transcript_text)}"
    )
    return head + body + "</body></html>"


def build_html_email_body(
    *,
    summary: dict,
    metadata: dict,
    transcript_text: str,
    transcript_source: str | None,
) -> str:
    meta_rows = [
        ("Source", metadata.get("title") or "Untitled"),
        ("URL", metadata.get("resolved_url") or metadata.get("original_url") or ""),
        ("Platform", metadata.get("platform") or "Unknown"),
        ("Who", summary.get("who") or "Unknown"),
    ]
    if metadata.get("published_at"):
        meta_rows.append(("Published", str(metadata["published_at"])))
    if metadata.get("duration_seconds"):
        meta_rows.append(("Duration", f"{int(metadata['duration_seconds'])} seconds"))

    summary_items = "".join(
        f"<li>{html.escape(line)}</li>"
        for line in summary_lines(str(summary.get("detailed_summary") or ""))
    )
    if not summary_items:
        summary_items = f"<li>{html.escape(strip_basic_markdown(str(summary.get('detailed_summary') or 'Summary unavailable.')))}</li>"

    body_parts = [
        "<html>",
        "<body style=\"font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #111;\">",
        "<div>",
    ]
    for label, value in meta_rows:
        escaped_value = html.escape(str(value))
        if label == "URL" and value:
            body_parts.append(
                f"<p><strong>{html.escape(label)}:</strong> "
                f"<a href=\"{escaped_value}\">{escaped_value}</a></p>"
            )
        else:
            body_parts.append(f"<p><strong>{html.escape(label)}:</strong> {escaped_value}</p>")

    body_parts.extend(
        [
            "<p><strong>Summary:</strong></p>",
            f"<ul>{summary_items}</ul>",
        ]
    )

    if should_inline_transcript(transcript_text, transcript_source) and len(transcript_text) <= TRANSCRIPT_INLINE_MAX:
        body_parts.extend(
            [
                "<p><strong>Full transcript:</strong></p>",
                "<div style=\"font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.6;\">",
                format_transcript_html(transcript_text),
                "</div>",
            ]
        )
    else:
        body_parts.append(
            "<p><strong>Full transcript is attached (.html for reading, .txt for raw).</strong></p>"
        )
        if transcript_source != "youtube-subtitles":
            excerpt = format_transcript_excerpt(transcript_text, max_chars=5000)
            body_parts.extend(
                [
                    "<p><strong>Transcript excerpt:</strong></p>",
                    "<div style=\"font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.6;\">",
                    format_transcript_html(excerpt),
                    "</div>",
                ]
            )

    body_parts.extend(["</div>", "</body>", "</html>"])
    return "\n".join(body_parts)


def extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    items: list[dict] = []
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (node.string or node.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            items.extend([item for item in data if isinstance(item, dict)])
        elif isinstance(data, dict):
            if isinstance(data.get("@graph"), list):
                items.extend([item for item in data["@graph"] if isinstance(item, dict)])
            items.append(data)
    return items


def first_meta(soup: BeautifulSoup, *, prop: str | None = None, name: str | None = None) -> str | None:
    if prop:
        node = soup.find("meta", attrs={"property": prop})
        if node and node.get("content"):
            return node["content"].strip()
    if name:
        node = soup.find("meta", attrs={"name": name})
        if node and node.get("content"):
            return node["content"].strip()
    return None


def extract_page_transcript_section(soup: BeautifulSoup) -> str | None:
    container = soup.find(
        lambda tag: tag.name in {"article", "div", "section"}
        and (
            "transcript" in " ".join(tag.get("class", [])).lower()
            or "transcript" in (tag.get("id") or "").lower()
            or "transcript" in (tag.get("aria-label") or "").lower()
        )
    )
    if container:
        text = container.get_text("\n", strip=True)
        if len(text) > 1200:
            return text

    heading = soup.find(
        lambda tag: tag.name in {"h1", "h2", "h3", "h4", "strong", "summary"}
        and "transcript" in tag.get_text(" ", strip=True).lower()
    )
    if not heading:
        return None
    lines = []
    for sibling in heading.next_siblings:
        name = getattr(sibling, "name", None)
        if name in {"h1", "h2", "h3", "h4"}:
            break
        if hasattr(sibling, "get_text"):
            text = sibling.get_text("\n", strip=True)
        else:
            text = str(sibling).strip()
        if text:
            lines.append(text)
    text = "\n".join(lines).strip()
    if len(text) < 1200:
        return None
    return text


def extract_transcript_from_html_document(url: str, raw_html: str) -> str | None:
    soup = BeautifulSoup(raw_html, "html.parser")
    transcript = extract_page_transcript_section(soup)
    if transcript:
        return transcript

    path = urlparse(url).path.lower()
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if "/transcripts/" in path or " transcript" in title:
        for selector in [".storytext", "article", "main"]:
            node = soup.select_one(selector)
            if not node:
                continue
            text = node.get_text("\n", strip=True)
            if len(text) > 3000:
                return text
    return None


def download_text_transcript(url: str) -> str | None:
    try:
        resp = fetch(url)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    content_type = resp.headers.get("Content-Type", "")
    if "html" in content_type.lower() or resp.text.lstrip().startswith("<!doctype html") or "<html" in resp.text[:500].lower():
        return extract_transcript_from_html_document(resp.url, resp.text)
    ext = transcript_blob_extension(url, resp.headers.get("Content-Type"))
    try:
        return parse_transcript_blob(resp.text, ext)
    except Exception:
        return resp.text.strip()


def findtext_ns(node: ET.Element, *names: str) -> str | None:
    wanted = {name.lower() for name in names}
    for child in node.iter():
        tag = child.tag.split("}")[-1].lower()
        if tag in wanted and child.text and child.text.strip():
            return child.text.strip()
    return None


def parse_omny_org_id(feed_url: str) -> str | None:
    parsed = urlparse(feed_url)
    if "omnycontent.com" not in parsed.netloc.lower():
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 3 and parts[0] == "d" and parts[1] == "playlist":
        return parts[2]
    return None


def build_omny_transcript_links(org_id: str, clip_id: str) -> list[str]:
    base = f"https://api.omny.fm/orgs/{org_id}/clips/{clip_id}/transcript"
    return [
        f"{base}?format=TextWithTimestamps",
        f"{base}?format=WebVTT",
        f"{base}?format=SubRip",
    ]


def score_rss_item(item_title: str, item_link: str, guid: str, url_hint: str | None, title_hint: str | None) -> int:
    score = 0
    item_title_lower = item_title.lower()
    title_hint_lower = (title_hint or "").lower()
    if title_hint_lower and item_title_lower:
        if title_hint_lower == item_title_lower:
            score += 8
        elif title_hint_lower in item_title_lower or item_title_lower in title_hint_lower:
            score += 5
    if url_hint and item_link and url_hint.rstrip("/") == item_link.rstrip("/"):
        score += 10
    if url_hint and guid and guid in url_hint:
        score += 7
    return score


def parse_rss_feed(feed_url: str, url_hint: str | None, title_hint: str | None) -> dict:
    meta: dict = {"feed_url": feed_url}
    try:
        resp = fetch(feed_url)
        resp.raise_for_status()
    except requests.RequestException:
        return meta
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return meta

    channel_title = root.findtext("./channel/title")
    if channel_title:
        meta["feed_title"] = channel_title.strip()

    items = root.findall("./channel/item")
    best_item: ET.Element | None = None
    best_score = -1
    for item in items:
        item_title = (item.findtext("title") or "").strip()
        item_link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        score = score_rss_item(item_title, item_link, guid, url_hint, title_hint)
        if score > best_score:
            best_score = score
            best_item = item

    if best_item is None and items:
        best_item = items[0]

    if best_item is None:
        return meta

    item_title = (best_item.findtext("title") or "").strip()
    item_link = (best_item.findtext("link") or "").strip()
    item_guid = (best_item.findtext("guid") or "").strip()
    enclosure = best_item.find("enclosure")
    enclosure_url = enclosure.get("url").strip() if enclosure is not None and enclosure.get("url") else None
    item_xml = ET.tostring(best_item, encoding="unicode")
    transcript_links = [url for url in extract_urls_from_text(item_xml) if likely_transcript_link(url)]
    omny_org = parse_omny_org_id(feed_url)
    if omny_org and item_guid:
        transcript_links.extend(build_omny_transcript_links(omny_org, item_guid))

    meta.update(
        {
            "item_title": item_title or None,
            "canonical_url": item_link or None,
            "item_guid": item_guid or None,
            "enclosure_url": enclosure_url or None,
            "author": findtext_ns(best_item, "author", "creator"),
            "published_at": findtext_ns(best_item, "pubDate", "published", "updated"),
            "description": findtext_ns(best_item, "description", "summary", "subtitle"),
            "transcript_links": unique_strings(transcript_links),
        }
    )
    return meta


def yt_dlp_probe(url: str) -> dict | None:
    if not command_exists("yt-dlp"):
        return None
    proc = sh(["yt-dlp", "--dump-single-json", "--no-warnings", "--skip-download", url])
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def build_youtube_subtitle_langs(metadata: dict) -> str:
    language_hints: list[str] = []
    for candidate in (
        metadata.get("language"),
        metadata.get("audio_language"),
        metadata.get("original_language"),
    ):
        if not isinstance(candidate, str):
            continue
        normalized = candidate.strip().lower().replace("_", "-")
        if not normalized:
            continue
        language_hints.append(normalized)
        if "-" in normalized:
            language_hints.append(normalized.split("-", 1)[0])

    preferred: list[str] = []
    fallback_languages = language_hints or ["en"]
    for lang in fallback_languages:
        if not lang:
            continue
        for variant in (f"{lang}.*", lang):
            if variant not in preferred:
                preferred.append(variant)
    preferred.append("-live_chat")
    return ",".join(preferred)


def yt_dlp_download_subtitles(url: str, workdir: Path, metadata: dict | None = None) -> str | None:
    if not command_exists("yt-dlp"):
        return None
    prefix = workdir / "subtitles"
    metadata = metadata or {}
    proc = sh([
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-format",
        "vtt",
        "--sub-langs",
        build_youtube_subtitle_langs(metadata),
        "-o",
        str(prefix) + ".%(ext)s",
        url,
    ])
    candidates = sorted(workdir.glob("subtitles*.vtt"))
    for candidate in candidates:
        text = parse_vtt(candidate.read_text(encoding="utf-8", errors="replace"))
        if len(text) > 800:
            return text
    if proc.returncode != 0:
        return None
    return None


def yt_dlp_download_audio(url: str, workdir: Path) -> Path | None:
    if not command_exists("yt-dlp"):
        return None
    prefix = workdir / "audio"
    proc = sh([
        "yt-dlp",
        "--no-playlist",
        "-f",
        "bestaudio[ext=m4a]/bestaudio/best",
        "-o",
        str(prefix) + ".%(ext)s",
        url,
    ])
    if proc.returncode != 0:
        return None
    candidates = sorted(workdir.glob("audio.*"))
    return candidates[0] if candidates else None


def ffmpeg_transcode_to_mp3(src: Path, dst: Path) -> Path | None:
    if not command_exists("ffmpeg"):
        return None
    proc = sh([
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "64k",
        str(dst),
    ])
    if proc.returncode != 0 or not dst.exists():
        return None
    return dst


def ffmpeg_segment_audio(src: Path, out_dir: Path, segment_seconds: int = 600) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "chunk-%03d.mp3"
    proc = sh([
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "48k",
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        str(pattern),
    ])
    if proc.returncode != 0:
        return []
    return sorted(out_dir.glob("chunk-*.mp3"))


def direct_download(url: str, workdir: Path) -> Path | None:
    try:
        resp = fetch(url, stream=True)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    ext = Path(urlparse(resp.url).path).suffix.lower()
    if ext not in MEDIA_EXTENSIONS:
        ext = mimetypes.guess_extension(resp.headers.get("Content-Type", "").split(";")[0].strip()) or ".bin"
    path = workdir / f"audio{ext}"
    with path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 512):
            if chunk:
                fh.write(chunk)
    return path


def choose_mime_type(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0]
    return mime or "application/octet-stream"


def upload_file_to_gemini(path: Path, api_key: str) -> tuple[str, str]:
    mime_type = choose_mime_type(path)
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(path.stat().st_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json",
    }
    start = requests.post(
        f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}",
        headers=headers,
        json={"file": {"display_name": path.name}},
        timeout=TIMEOUT,
    )
    start.raise_for_status()
    upload_url = start.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        raise RuntimeError("Gemini upload URL missing")
    with path.open("rb") as fh:
        finish = requests.post(
            upload_url,
            headers={
                "Content-Length": str(path.stat().st_size),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            data=fh,
            timeout=120,
        )
    finish.raise_for_status()
    payload = finish.json()["file"]
    return payload["uri"], payload.get("mimeType") or mime_type


def gemini_generate(parts: list[dict], *, api_key: str, temperature: float = 0.1) -> str:
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": temperature},
    }
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}",
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    out = []
    for part in data["candidates"][0]["content"]["parts"]:
        if "text" in part:
            out.append(part["text"])
    return "\n".join(out).strip()


def transcribe_with_gemini(audio_path: Path, state: RunState, api_key: str) -> str:
    file_uri, mime_type = upload_file_to_gemini(audio_path, api_key)
    prompt = textwrap.dedent(
        f"""
        Generate the complete transcript for this media item.

        Requirements:
        - Return the FULL transcript from beginning to end.
        - Do not summarize, shorten, or replace sections with notes.
        - Preserve speaker labels when they are clear from the audio.
        - If speaker identity is unclear, still keep the spoken content.
        - Use plain text only.
        - Include occasional timestamps only if they are naturally inferable or obvious from segments.

        Title hint: {state.metadata.get('title') or 'Unknown'}
        Source URL: {state.metadata.get('resolved_url') or state.original_url}
        """
    ).strip()
    return gemini_generate(
        [{"text": prompt}, {"file_data": {"mime_type": mime_type, "file_uri": file_uri}}],
        api_key=api_key,
        temperature=0.0,
    )


def transcribe_with_openai(audio_path: Path, api_key: str) -> str:
    with audio_path.open("rb") as fh:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": "gpt-4o-mini-transcribe"},
            files={"file": (audio_path.name, fh, choose_mime_type(audio_path))},
            timeout=180,
        )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("text"):
        return data["text"].strip()
    if isinstance(data, str):
        return data.strip()
    raise RuntimeError("Unexpected OpenAI transcription response")


def transcribe_chunk(
    audio_path: Path,
    state: RunState,
    *,
    gemini_key: str | None,
    openai_key: str | None,
    prefer_openai: bool = False,
) -> str:
    ext = audio_path.suffix.lower()
    providers = ["openai", "gemini"] if prefer_openai else ["gemini", "openai"]
    for provider in providers:
        if provider == "gemini" and gemini_key and ext in GEMINI_SAFE_EXTENSIONS:
            try:
                return transcribe_with_gemini(audio_path, state, gemini_key)
            except Exception as exc:
                state.warnings.append(f"Gemini chunk transcription failed for {audio_path.name}: {exc}")
        if provider == "openai" and openai_key and ext in OPENAI_SAFE_EXTENSIONS:
            try:
                return transcribe_with_openai(audio_path, openai_key)
            except Exception as exc:
                state.warnings.append(f"OpenAI chunk transcription failed for {audio_path.name}: {exc}")
    raise RuntimeError(f"No compatible transcription provider for {audio_path.name}")


def chunk_text(text: str, chunk_chars: int = SUMMARY_CHUNK_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text.strip()]
    chunks: list[str] = []
    current = []
    size = 0
    for paragraph in paragraphs:
        if current and size + len(paragraph) + 2 > chunk_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            size = len(paragraph)
        else:
            current.append(paragraph)
            size += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def summarize_text_for_email(
    *,
    transcript_text: str | None,
    source_text: str,
    metadata: dict,
    api_key: str,
) -> dict:
    base_meta = json.dumps(
        {
            "title": metadata.get("title"),
            "resolved_url": metadata.get("resolved_url"),
            "platform": metadata.get("platform"),
            "author": metadata.get("author"),
            "published_at": metadata.get("published_at"),
            "duration_seconds": metadata.get("duration_seconds"),
        },
        ensure_ascii=False,
    )

    if transcript_text and len(transcript_text) > SUMMARY_CHUNK_CHARS:
        chunk_summaries = []
        for idx, chunk in enumerate(chunk_text(transcript_text), start=1):
            prompt = textwrap.dedent(
                f"""
                You are summarizing chunk {idx} of a long transcript.
                Metadata: {base_meta}

                Produce JSON only with keys:
                - chunk_summary
                - who
                - important_topics
                """
            ).strip()
            result = gemini_generate(
                [{"text": f"{prompt}\n\nTranscript chunk:\n{chunk}"}],
                api_key=api_key,
                temperature=0.1,
            )
            chunk_summaries.append(extract_json_object(result))
        synthesis_input = json.dumps(chunk_summaries, ensure_ascii=False)
        prompt_body = f"Chunk summaries:\n{synthesis_input}"
    else:
        prompt_body = f"Transcript or source text:\n{transcript_text or source_text}"

    prompt = textwrap.dedent(
        f"""
        Summarize this media item for Igor.

        Metadata: {base_meta}

        Return JSON only with keys:
        - email_subject
        - whatsapp_summary
        - detailed_summary
        - who
        - transcript_possible

        Rules:
        - whatsapp_summary must be under {WHATSAPP_MAX} characters.
        - whatsapp_summary should be a compact title plus 3 to 5 short bullet points.
        - detailed_summary should be plain text bullets separated by newlines.
        - who should identify the host/guest/speaker(s) if known, else "Unknown".
        - transcript_possible must be true only if there is a full transcript.
        """
    ).strip()
    result = gemini_generate([{"text": f"{prompt}\n\n{prompt_body}"}], api_key=api_key, temperature=0.1)
    try:
        return extract_json_object(result)
    except Exception:
        repair_prompt = textwrap.dedent(
            """
            Convert the following response into valid JSON only.

            Required keys:
            - email_subject
            - whatsapp_summary
            - detailed_summary
            - who
            - transcript_possible
            """
        ).strip()
        try:
            repaired = gemini_generate(
                [{"text": f"{repair_prompt}\n\nResponse to repair:\n{result}"}],
                api_key=api_key,
                temperature=0.0,
            )
            return extract_json_object(repaired)
        except Exception:
            return build_fallback_summary(
                transcript_text=transcript_text,
                source_text=source_text,
                metadata=metadata,
            )


def rewrite_whatsapp_summary(
    *,
    title: str,
    who: str,
    detailed_summary: str,
    fallback_summary: str,
    metadata: dict,
    api_key: str,
) -> str:
    prompt = textwrap.dedent(
        f"""
        Rewrite this into a WhatsApp summary for Igor.

        Return plain text only.

        Requirements:
        - First line must be the title.
        - Then write 3 to 5 bullet points.
        - Each bullet must start with "- ".
        - Keep the whole message under {WHATSAPP_MAX} characters.
        - Keep the source language unless the summary is already clearly in another language.
        - No HTML.
        - No URLs.
        - No promo boilerplate, subscription blurbs, or platform labels.
        - Make it read cleanly in WhatsApp.

        Metadata:
        {json.dumps({
            "title": title,
            "who": who,
            "platform": metadata.get("platform"),
            "author": metadata.get("author"),
        }, ensure_ascii=False)}

        Detailed summary:
        {detailed_summary}

        Existing short summary:
        {fallback_summary}
        """
    ).strip()

    result = gemini_generate([{"text": prompt}], api_key=api_key, temperature=0.1)
    text = re.sub(r"^```(?:text)?\s*|\s*```$", "", str(result or "").strip(), flags=re.DOTALL)
    text = strip_basic_markdown(text)
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]

    title_line = str(title or "Transcript ready").strip()
    bullet_lines = []
    for idx, line in enumerate(raw_lines):
        cleaned = re.sub(r"^[-*•]\s*", "", line).strip()
        if not cleaned:
            continue
        if idx == 0 and cleaned.casefold() == title_line.casefold():
            continue
        bullet_lines.append(f"- {cleaned}")
        if len(bullet_lines) >= WHATSAPP_BULLET_MAX:
            break

    if not bullet_lines:
        bullet_lines = [f"- {strip_basic_markdown(fallback_summary or detailed_summary or 'Transcript ready.').strip()}"]

    final_text = "\n".join([title_line, *bullet_lines]).strip()
    if len(final_text) > WHATSAPP_MAX:
        final_text = final_text[: WHATSAPP_MAX - 1].rstrip() + "…"
    return final_text


def send_email(
    *,
    to_addr: str,
    subject: str,
    summary: dict,
    metadata: dict,
    transcript_text: str,
    transcript_path: Path,
    transcript_source: str | None,
) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]

    body = [
        f"Source: {metadata.get('title') or 'Untitled'}",
        f"URL: {metadata.get('resolved_url') or metadata.get('original_url') or ''}",
        f"Platform: {metadata.get('platform') or 'Unknown'}",
        f"Who: {summary.get('who') or 'Unknown'}",
    ]
    if metadata.get("published_at"):
        body.append(f"Published: {metadata['published_at']}")
    if metadata.get("duration_seconds"):
        body.append(f"Duration: {int(metadata['duration_seconds'])} seconds")
    body.extend(
        [
            "",
            "Summary:",
            strip_basic_markdown(str(summary.get("detailed_summary") or "").strip()),
            "",
        ]
    )
    if should_inline_transcript(transcript_text, transcript_source) and len(transcript_text) <= TRANSCRIPT_INLINE_MAX:
        body.extend(["Full transcript:", transcript_text.strip()])
    else:
        body.extend(["Full transcript is attached as a text file."])
        if transcript_source != "youtube-subtitles":
            body.extend(
                [
                    "",
                    "Transcript excerpt:",
                    format_transcript_excerpt(transcript_text, max_chars=5000),
                ]
            )

    msg = EmailMessage()
    msg["From"] = gmail_user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content("\n".join(body))
    msg.add_alternative(
        build_html_email_body(
            summary=summary,
            metadata=metadata,
            transcript_text=transcript_text,
            transcript_source=transcript_source,
        ),
        subtype="html",
    )
    msg.add_attachment(
        transcript_text.encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename=transcript_path.name,
    )
    transcript_html = build_standalone_transcript_html(
        title=str(metadata.get("title") or "Transcript"),
        metadata=metadata,
        transcript_text=transcript_text,
    )
    msg.add_attachment(
        transcript_html.encode("utf-8"),
        maintype="text",
        subtype="html",
        filename=transcript_path.with_suffix(".html").name,
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as smtp:
        smtp.login(gmail_user, gmail_password)
        smtp.send_message(msg)


def hydrate_metadata_from_html(url: str, html: str, state: RunState) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    json_ld = extract_json_ld(soup)
    metadata = {
        "original_url": state.original_url,
        "resolved_url": url,
        "title": first_meta(soup, prop="og:title") or soup.title.get_text(strip=True) if soup.title else None,
        "description": first_meta(soup, prop="og:description") or first_meta(soup, name="description"),
        "author": first_meta(soup, name="author"),
        "platform": urlparse(url).netloc.lower(),
    }

    transcript_links = []
    media_links = []
    rss_links = []
    for link in soup.find_all(["a", "link", "source", "audio", "video"]):
        href = link.get("href") or link.get("src")
        if not href:
            continue
        absolute = urljoin(url, href)
        label = link.get_text(" ", strip=True).lower()
        href_lower = absolute.lower()
        if likely_transcript_link(absolute) or "transcript" in label:
            transcript_links.append(absolute)
        if likely_direct_media(absolute, None):
            media_links.append(absolute)
        rel = " ".join(link.get("rel", [])) if link.get("rel") else ""
        type_attr = link.get("type", "")
        if "alternate" in rel and ("rss" in type_attr or "xml" in type_attr):
            rss_links.append(absolute)

    for absolute in extract_urls_from_text(html):
        if likely_transcript_link(absolute):
            transcript_links.append(absolute)
        if likely_direct_media(absolute, None):
            media_links.append(absolute)
        if looks_like_rss_feed(absolute):
            rss_links.append(absolute)

    for candidate in (
        first_meta(soup, prop="og:audio"),
        first_meta(soup, prop="og:audio:secure_url"),
        first_meta(soup, name="twitter:player:stream"),
    ):
        if candidate:
            media_links.append(candidate)

    for item in json_ld:
        item_type = json.dumps(item, ensure_ascii=False).lower()
        if not metadata.get("title") and item.get("name"):
            metadata["title"] = item["name"]
        if not metadata.get("description") and item.get("description"):
            metadata["description"] = item["description"]
        author = item.get("author")
        if not metadata.get("author") and isinstance(author, dict):
            metadata["author"] = author.get("name")
        if not metadata.get("published_at") and item.get("datePublished"):
            metadata["published_at"] = item["datePublished"]
        content_url = item.get("contentUrl") or item.get("embedUrl") or item.get("url")
        if isinstance(content_url, str) and likely_direct_media(content_url, None):
            media_links.append(content_url)
        if "podcastepisode" in item_type or "audioobject" in item_type or "videoobject" in item_type:
            metadata["platform"] = metadata.get("platform") or item.get("@type")

    transcript_section = extract_page_transcript_section(soup)
    page_text = soup.get_text("\n", strip=True)
    metadata["transcript_links"] = unique_strings(transcript_links)
    metadata["media_links"] = unique_strings(media_links)
    metadata["rss_links"] = unique_strings(rss_links)
    metadata["page_text"] = page_text[:25000]
    if transcript_section:
        metadata["page_transcript"] = transcript_section
    return metadata


def enrich_from_rss_feeds(state: RunState) -> None:
    rss_links = state.metadata.get("rss_links", [])
    if not isinstance(rss_links, list) or not rss_links:
        return

    transcript_links = list(state.metadata.get("transcript_links", []))
    media_links = list(state.metadata.get("media_links", []))
    resolved_url = state.metadata.get("resolved_url") or state.original_url
    title_hint = state.metadata.get("title")

    for rss_link in rss_links[:5]:
        feed_meta = parse_rss_feed(rss_link, resolved_url, title_hint)
        if not feed_meta:
            continue
        if feed_meta.get("feed_title") and not state.metadata.get("feed_title"):
            state.metadata["feed_title"] = feed_meta["feed_title"]
        if feed_meta.get("item_title") and not state.metadata.get("title"):
            state.metadata["title"] = feed_meta["item_title"]
        if feed_meta.get("author") and not state.metadata.get("author"):
            state.metadata["author"] = feed_meta["author"]
        if feed_meta.get("published_at") and not state.metadata.get("published_at"):
            state.metadata["published_at"] = feed_meta["published_at"]
        if feed_meta.get("description") and not state.metadata.get("description"):
            state.metadata["description"] = feed_meta["description"]
        if feed_meta.get("canonical_url") and not state.metadata.get("canonical_url"):
            state.metadata["canonical_url"] = feed_meta["canonical_url"]
        if feed_meta.get("enclosure_url") and not state.metadata.get("enclosure_url"):
            state.metadata["enclosure_url"] = feed_meta["enclosure_url"]
        transcript_links.extend(feed_meta.get("transcript_links", []))
        if feed_meta.get("enclosure_url"):
            media_links.append(feed_meta["enclosure_url"])

    state.metadata["transcript_links"] = sorted(unique_strings(transcript_links), key=transcript_link_rank)
    state.metadata["media_links"] = unique_strings(media_links)


def resolve_url(state: RunState) -> None:
    url = state.original_url
    yt_info = yt_dlp_probe(url)
    if yt_info:
        state.metadata.update(
            {
                "title": yt_info.get("title"),
                "author": yt_info.get("uploader") or yt_info.get("channel"),
                "duration_seconds": yt_info.get("duration"),
                "description": yt_info.get("description"),
                "resolved_url": yt_info.get("webpage_url") or url,
                "platform": yt_info.get("extractor_key") or urlparse(url).netloc.lower(),
                "language": yt_info.get("language"),
            }
        )
        state.accessible = True
        state.access_method = "yt-dlp"
    try:
        resp = fetch(url)
        resp.raise_for_status()
        state.accessible = True
        state.access_method = state.access_method or "http"
        state.metadata.update(hydrate_metadata_from_html(resp.url, resp.text, state))
    except requests.RequestException as exc:
        state.warnings.append(f"Direct fetch failed: {exc}")
        if not state.accessible:
            state.metadata.setdefault("resolved_url", url)

    state.metadata.setdefault("original_url", url)
    state.metadata.setdefault("resolved_url", url)
    enrich_from_rss_feeds(state)


def try_existing_transcript(state: RunState) -> bool:
    page_transcript = state.metadata.get("page_transcript")
    if isinstance(page_transcript, str) and len(page_transcript) > 1200:
        state.transcript_text = page_transcript.strip()
        state.transcript_source = "page-transcript"
        return True

    for link in state.metadata.get("transcript_links", []):
        text = download_text_transcript(link)
        if text and len(text) > 800:
            state.transcript_text = text
            state.transcript_source = f"existing-transcript:{link}"
            return True

    if is_youtube(state.original_url):
        text = yt_dlp_download_subtitles(state.original_url, state.workdir, state.metadata)
        if text and len(text) > 800:
            state.transcript_text = text
            state.transcript_source = "youtube-subtitles"
            return True
    return False


def obtain_audio(state: RunState) -> Path | None:
    resolved_url = state.metadata.get("resolved_url") or state.original_url
    enclosure_url = state.metadata.get("enclosure_url")
    if isinstance(enclosure_url, str) and enclosure_url:
        audio = direct_download(enclosure_url, state.workdir)
        if audio:
            state.notes.append("Downloaded audio from canonical RSS enclosure")
            return audio

    if likely_direct_media(resolved_url, None):
        audio = direct_download(resolved_url, state.workdir)
        if audio:
            state.notes.append("Downloaded direct media URL")
            return audio

    for media_link in state.metadata.get("media_links", []):
        audio = direct_download(media_link, state.workdir)
        if audio:
            state.notes.append(f"Downloaded media from page: {media_link}")
            return audio

    for rss_link in state.metadata.get("rss_links", []):
        rss_meta = parse_rss_feed(rss_link, resolved_url, state.metadata.get("title"))
        enclosure_url = rss_meta.get("enclosure_url")
        if enclosure_url:
            state.metadata.update({k: v for k, v in rss_meta.items() if v and not state.metadata.get(k)})
            audio = direct_download(enclosure_url, state.workdir)
            if audio:
                state.notes.append(f"Downloaded audio from RSS enclosure: {rss_link}")
                return audio

    audio = yt_dlp_download_audio(state.original_url, state.workdir)
    if audio:
        state.notes.append("Downloaded audio with yt-dlp")
        return audio
    return None


def transcribe_audio(state: RunState) -> bool:
    if not state.audio_path:
        return False
    ext = state.audio_path.suffix.lower()
    gemini_key = read_env_key("GOOGLE_API_KEY", "GEMINI_API_KEY")
    openai_key = read_env_key("OPENAI_API_KEY")

    candidate = state.audio_path
    if ext not in GEMINI_SAFE_EXTENSIONS and command_exists("ffmpeg"):
        transcoded = ffmpeg_transcode_to_mp3(state.audio_path, state.workdir / "audio.transcode.mp3")
        if transcoded:
            candidate = transcoded
            ext = candidate.suffix.lower()
            state.notes.append("Transcoded audio to MP3 for Gemini compatibility")

    if gemini_key and ext in GEMINI_SAFE_EXTENSIONS:
        if candidate.stat().st_size > TRANSCRIBE_CHUNK_BYTES and command_exists("ffmpeg"):
            chunks = ffmpeg_segment_audio(candidate, state.workdir / "chunks")
            if chunks:
                state.notes.append(f"Split long audio into {len(chunks)} chunks for transcription")
                transcripts = []
                for chunk in chunks:
                    try:
                        transcripts.append(
                            transcribe_chunk(
                                chunk,
                                state,
                                gemini_key=gemini_key,
                                openai_key=openai_key,
                                prefer_openai=True,
                            ).strip()
                        )
                    except Exception as exc:
                        state.warnings.append(f"Chunk transcription failed for {chunk.name}: {exc}")
                        transcripts = []
                        break
                if transcripts:
                    state.transcript_text = "\n\n".join(t for t in transcripts if t)
                    state.transcript_source = "chunked-audio"
                    return True

        try:
            state.transcript_text = transcribe_with_gemini(candidate, state, gemini_key)
            state.transcript_source = "gemini-audio"
            return True
        except Exception as exc:
            state.warnings.append(f"Gemini transcription failed: {exc}")

    if openai_key and ext in OPENAI_SAFE_EXTENSIONS:
        try:
            state.transcript_text = transcribe_with_openai(candidate, openai_key)
            state.transcript_source = "openai-audio"
            return True
        except Exception as exc:
            state.warnings.append(f"OpenAI transcription failed: {exc}")

    return False


def write_transcript(state: RunState) -> None:
    if not state.transcript_text:
        return
    filename = slugify(state.metadata.get("title") or "transcript")
    path = state.workdir / f"{filename}.transcript.txt"
    path.write_text(state.transcript_text.strip() + "\n", encoding="utf-8")
    state.transcript_path = path


def summarize(state: RunState) -> dict:
    gemini_key = read_env_key("GOOGLE_API_KEY", "GEMINI_API_KEY")
    source_text = "\n\n".join(
        part for part in [
            str(state.metadata.get("title") or ""),
            str(state.metadata.get("description") or ""),
            str(state.metadata.get("page_text") or ""),
        ] if part
    )[:25000]
    if not state.transcript_text and not state.accessible and not source_text.strip():
        title = state.metadata.get("title") or state.original_url
        return {
            "email_subject": f"[Transcript unavailable] {title}",
            "whatsapp_summary": (
                f"I couldn't access that source well enough to obtain a full transcript. "
                f"I also skipped email because there is no transcript to send.\n{state.original_url}"
            ),
            "detailed_summary": "Source inaccessible or blocked; no reliable transcript or grounded summary available.",
            "who": state.metadata.get("author") or "Unknown",
            "transcript_possible": False,
        }
    if not gemini_key:
        title = state.metadata.get("title") or "Untitled"
        return {
            "email_subject": f"[Transcript] {title}",
            "whatsapp_summary": f"{title}\nTranscript {'ready' if state.transcript_text else 'not available'} for {state.metadata.get('resolved_url') or state.original_url}.",
            "detailed_summary": state.metadata.get("description") or "Summary unavailable because no Gemini API key is configured.",
            "who": state.metadata.get("author") or "Unknown",
            "transcript_possible": bool(state.transcript_text),
        }
    result = summarize_text_for_email(
        transcript_text=state.transcript_text,
        source_text=source_text,
        metadata=state.metadata,
        api_key=gemini_key,
    )
    if not result.get("email_subject"):
        result["email_subject"] = f"[Transcript] {state.metadata.get('title') or 'Untitled'}"
    if not result.get("whatsapp_summary"):
        result["whatsapp_summary"] = (
            f"{state.metadata.get('title') or 'Untitled'}\n"
            f"Transcript {'ready' if state.transcript_text else 'not available'}."
        )
    return result


def ensure_runtime_dirs(seed_url: str) -> Path:
    # Runtime scratch lives on local disk only (never on Google Drive — causes
    # EDEADLK lock errors and pointlessly syncs GB of audio to the cloud).
    state_root = Path.home() / ".openclaw" / "state" / "transcripts"
    digest = hashlib.sha1(seed_url.encode("utf-8")).hexdigest()[:10]
    title = slugify(urlparse(seed_url).netloc or "url")
    workdir = state_root / f"{now_utc()}-{title}-{digest}"
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def run_pipeline(url: str, *, email_to: str | None, skip_email: bool) -> dict:
    state = RunState(original_url=url, workdir=ensure_runtime_dirs(url))

    resolve_url(state)

    if try_existing_transcript(state):
        state.notes.append("Used an existing full transcript")
    else:
        state.audio_path = obtain_audio(state)
        if state.audio_path:
            transcribe_audio(state)

    if state.transcript_text:
        if state.transcript_source == "youtube-subtitles":
            normalized = normalize_subtitle_transcript_text(state.transcript_text)
            if normalized and normalized != state.transcript_text:
                state.transcript_text = normalized
                state.notes.append("Normalized YouTube subtitle transcript into readable paragraphs")
        normalize_transcript_speakers(state)
        write_transcript(state)

    summary = summarize(state)
    state.whatsapp_summary = str(summary.get("whatsapp_summary") or "").strip()
    state.detailed_summary = str(summary.get("detailed_summary") or "").strip()
    state.email_subject = str(summary.get("email_subject") or "").strip()

    title = str(state.metadata.get("title") or "Transcript ready")
    who = str(summary.get("who") or state.metadata.get("author") or "Unknown")
    gemini_key = read_env_key("GOOGLE_API_KEY", "GEMINI_API_KEY")
    state.whatsapp_summary = rewrite_whatsapp_summary(
        title=title,
        who=who,
        detailed_summary=state.detailed_summary,
        fallback_summary=state.whatsapp_summary,
        metadata=state.metadata,
        api_key=gemini_key,
    ).strip()

    if state.whatsapp_summary and len(state.whatsapp_summary) > WHATSAPP_MAX:
        state.whatsapp_summary = state.whatsapp_summary[: WHATSAPP_MAX - 1].rstrip() + "…"

    if state.transcript_text and state.transcript_path and email_to and not skip_email:
        try:
            send_email(
                to_addr=email_to,
                subject=state.email_subject or f"[Transcript] {state.metadata.get('title') or 'Untitled'}",
                summary=summary,
                metadata=state.metadata,
                transcript_text=state.transcript_text,
                transcript_path=state.transcript_path,
                transcript_source=state.transcript_source,
            )
            state.email_sent = True
        except Exception as exc:
            state.warnings.append(f"Email send failed: {exc}")

    # Once the transcript is in the user's inbox, the scratch workdir is dead
    # weight. Delete it so we don't accumulate gigabytes of audio. On failure
    # (no email / partial run), keep the dir — daily-restart sweeps anything
    # older than 1 day.
    workdir_removed = False
    if state.email_sent:
        try:
            shutil.rmtree(state.workdir, ignore_errors=True)
            workdir_removed = True
            state.transcript_path = None
            state.audio_path = None
        except Exception as exc:
            state.warnings.append(f"Workdir cleanup failed: {exc}")

    if not state.transcript_text and not state.whatsapp_summary:
        state.whatsapp_summary = (
            f"I couldn't obtain a full transcript for {state.metadata.get('resolved_url') or state.original_url}. "
            "I also skipped email because there is no transcript to send."
        )

    status = "ok" if state.transcript_text else "partial"
    return {
        "status": status,
        "original_url": state.original_url,
        "resolved_url": state.metadata.get("resolved_url") or state.original_url,
        "accessible": state.accessible,
        "access_method": state.access_method,
        "title": state.metadata.get("title"),
        "platform": state.metadata.get("platform"),
        "author": state.metadata.get("author"),
        "published_at": state.metadata.get("published_at"),
        "duration_seconds": state.metadata.get("duration_seconds"),
        "transcript_available": bool(state.transcript_text),
        "transcript_source": state.transcript_source,
        "transcript_path": str(state.transcript_path) if state.transcript_path else None,
        "audio_path": str(state.audio_path) if state.audio_path else None,
        "email_sent": state.email_sent,
        "email_subject": state.email_subject,
        "whatsapp_summary": state.whatsapp_summary,
        "detailed_summary": state.detailed_summary,
        "who": summary.get("who"),
        "warnings": state.warnings,
        "notes": state.notes,
        "workdir": None if workdir_removed else str(state.workdir),
        "workdir_removed": workdir_removed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe and summarize a URL for Clawd")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Resolve, transcribe, summarize, and optionally email")
    run_p.add_argument("url")
    run_p.add_argument("--email-to", help="Email recipient for transcript delivery")
    run_p.add_argument("--skip-email", action="store_true", help="Do not send email even if a transcript is available")
    run_p.add_argument("--json", action="store_true", help="Print JSON output")

    args = parser.parse_args()

    if args.command == "run":
        result = run_pipeline(args.url, email_to=args.email_to, skip_email=args.skip_email)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["whatsapp_summary"] or "")
        return 0 if result["status"] in {"ok", "partial"} else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
