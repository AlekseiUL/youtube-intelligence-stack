#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from common import (
    ensure_project_dirs,
    TRANSCRIPTS_DIR,
    chunk_text,
    clean_text,
    now_iso,
    resolve_video_inputs,
    run_command,
    sleep_ms,
    write_json,
    write_text,
)


YT_DLP = shutil.which("yt-dlp") or "yt-dlp"
DEFAULT_LANGS = ["en", "en-US", "en-GB", "ru", "ru-RU"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch YouTube transcripts via yt-dlp subtitles.")
    parser.add_argument("--video-id", action="append", default=[])
    parser.add_argument("--video-url", action="append", default=[])
    parser.add_argument("--from-search", help="Search bundle json path, defaults to latest search bundle")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--lang", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--retry-count", type=int, default=2)
    parser.add_argument("--retry-backoff-ms", type=int, default=2500)
    parser.add_argument("--command-timeout-sec", type=float, default=20.0)
    return parser.parse_args()


def fetch_metadata(url: str, timeout_sec: float | None = None) -> dict[str, Any]:
    result = run_command([YT_DLP, "--dump-single-json", "--skip-download", url], timeout_sec=timeout_sec)
    return json.loads(result.stdout)


def classify_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "429" in text or "too many requests" in text:
        return "rate_limited"
    if "403" in text or "forbidden" in text:
        return "forbidden"
    if "404" in text or "not found" in text:
        return "not_found"
    return "error"


def choose_language(meta: dict[str, Any], preferred: list[str]) -> tuple[str | None, bool]:
    subtitles = meta.get("subtitles") or {}
    automatic = meta.get("automatic_captions") or {}
    for lang in preferred:
        if lang in subtitles:
            return lang, False
    for lang in preferred:
        if lang in automatic:
            return lang, True
    if subtitles:
        return sorted(subtitles.keys())[0], False
    if automatic:
        return sorted(automatic.keys())[0], True
    return None, False


def download_subtitle(url: str, video_id: str, lang: str, is_generated: bool, timeout_sec: float | None = None) -> Path | None:
    with tempfile.TemporaryDirectory(prefix="yt-transcripts-") as tmpdir:
        output_template = str(Path(tmpdir) / "%(id)s.%(ext)s")
        args = [YT_DLP, "--skip-download", "--sub-langs", lang, "--sub-format", "vtt", "-o", output_template]
        args.append("--write-auto-subs" if is_generated else "--write-subs")
        args.append(url)
        run_command(args, timeout_sec=timeout_sec)
        temp_path = Path(tmpdir)
        candidates = sorted(temp_path.glob(f"{video_id}*.vtt"))
        if not candidates:
            return None
        target_dir = TRANSCRIPTS_DIR / video_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / candidates[0].name
        target.write_text(candidates[0].read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        return target


def parse_vtt(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\s*\n", text)
    cues: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0] == "WEBVTT":
            continue
        if any("-->" in line for line in lines):
            payload: list[str] = []
            for line in lines:
                if "-->" in line:
                    continue
                if re.fullmatch(r"\d+", line):
                    continue
                payload.append(line)
            cue = clean_text(" ".join(payload))
            if cue and (not cues or cues[-1] != cue):
                cues.append(cue)
    return cues


def main() -> None:
    ensure_project_dirs()
    args = parse_args()
    preferred = args.lang or DEFAULT_LANGS
    inputs = resolve_video_inputs(
        video_ids=args.video_id,
        video_urls=args.video_url,
        from_search=args.from_search,
        limit=args.limit,
    )

    results: list[dict[str, Any]] = []
    for item in inputs:
        url = item.get("video_url")
        if not url:
            continue

        meta: dict[str, Any] = {}
        metadata_error = None
        try:
            meta = fetch_metadata(url, timeout_sec=args.command_timeout_sec)
        except Exception as exc:
            metadata_error = str(exc)

        video_id = (meta.get("id") if meta else None) or item.get("video_id")
        if not video_id:
            continue

        target_json = TRANSCRIPTS_DIR / video_id / "latest.json"
        if target_json.exists() and not args.overwrite:
            results.append(json.loads(target_json.read_text(encoding="utf-8")))
            continue

        transcript_text = ""
        transcript_chunks: list[str] = []
        status = "missing"
        raw_path = None
        error = metadata_error
        language = None
        is_generated = False

        if meta:
            language, is_generated = choose_language(meta, preferred)
            if language:
                for attempt_no in range(1, args.retry_count + 2):
                    try:
                        raw_path = download_subtitle(url, video_id, language, is_generated, timeout_sec=args.command_timeout_sec)
                        error = None
                        break
                    except Exception as exc:
                        error = str(exc)
                        status = classify_error(exc)
                        if attempt_no <= args.retry_count:
                            sleep_ms(args.retry_backoff_ms * attempt_no)
                if raw_path:
                    cues = parse_vtt(raw_path)
                    transcript_text = clean_text(" ".join(cues))
                    transcript_chunks = chunk_text(transcript_text)
                    status = "ok" if transcript_text else "empty"
                elif status == "missing":
                    status = "download_failed"
            else:
                status = "no_subtitles"
        else:
            status = classify_error(Exception(metadata_error)) if metadata_error else "metadata_failed"

        collected_at = now_iso()
        record = {
            "fetched_at": collected_at,
            "collected_at": collected_at,
            "video_id": video_id,
            "video_url": url,
            "title": meta.get("title") if meta else item.get("title"),
            "language": language,
            "is_generated": is_generated,
            "transcript_text": transcript_text,
            "transcript_chunks": transcript_chunks,
            "transcript_available": bool(transcript_text),
            "status": status,
            "error": error,
            "raw_subtitle_path": str(raw_path) if raw_path else None,
            "available_manual_languages": sorted((meta.get("subtitles") or {}).keys()) if meta else [],
            "available_auto_languages": sorted((meta.get("automatic_captions") or {}).keys()) if meta else [],
            "source": "yt_dlp_subtitles",
        }
        out_dir = TRANSCRIPTS_DIR / video_id
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / "latest.json", record)
        if transcript_text:
            write_text(out_dir / "latest.txt", transcript_text + "\n")
        results.append(record)

    print(json.dumps({
        "processed": len(results),
        "available": sum(1 for item in results if item.get("transcript_available")),
        "missing": sum(1 for item in results if not item.get("transcript_available")),
        "videos": [
            {
                "video_id": item.get("video_id"),
                "language": item.get("language"),
                "is_generated": item.get("is_generated"),
                "status": item.get("status"),
            }
            for item in results
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
