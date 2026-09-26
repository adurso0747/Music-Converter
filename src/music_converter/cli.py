"""Command-line interface: ``music-converter-cli INPUT... -o OUTPUT [options]``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .converter import Converter, Settings, Status, find_ffmpeg
from .formats import FORMATS, get_format
from .planner import build_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="music-converter-cli",
        description="Convert FLAC/WAV files and folders to MP3, Opus, AAC or Ogg Vorbis, "
        "keeping the folder structure and album artwork.",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="audio files and/or folders")
    parser.add_argument("-o", "--output", required=True, type=Path, help="output folder")
    parser.add_argument("-f", "--format", default="mp3", choices=list(FORMATS))
    parser.add_argument(
        "-m", "--mode", help="quality mode, e.g. vbr or cbr (default: the format's first mode)"
    )
    parser.add_argument(
        "-q", "--quality", help="bitrate in kbps, or a preset such as V0 (MP3) or q6 (Vorbis)"
    )
    parser.add_argument("-j", "--threads", type=int, default=os.cpu_count() or 1)
    parser.add_argument(
        "--overwrite", action="store_true", help="re-convert files that already exist in the output"
    )
    parser.add_argument("--no-artwork", action="store_true", help="don't copy folder images")
    parser.add_argument("--no-embed-cover", action="store_true", help="don't embed cover art")
    parser.add_argument(
        "--copy-lossy",
        action="store_true",
        help="copy MP3/AAC/Ogg/Opus files found in folders as-is",
    )
    args = parser.parse_args(argv)
    # Track names often contain characters a Windows console code page can't print.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        parser.error("ffmpeg was not found. Install it and make sure it is on your PATH.")

    fmt = get_format(args.format)
    mode = fmt.mode(args.mode) if args.mode else fmt.modes[0]
    if args.mode and mode.key != args.mode:
        parser.error(f"{fmt.label} supports modes: {', '.join(m.key for m in fmt.modes)}")
    quality = _match_choice(mode.choices, args.quality) if args.quality else mode.default

    settings = Settings(
        fmt=fmt,
        mode_key=mode.key,
        quality=quality,
        threads=args.threads,
        skip_existing=not args.overwrite,
        embed_cover=not args.no_embed_cover,
    )
    plan = build_plan(
        args.inputs, args.output, fmt, copy_artwork=not args.no_artwork, copy_lossy=args.copy_lossy
    )
    for path in plan.ignored:
        print(f"Ignoring {path} (not found or not a supported audio file)", file=sys.stderr)
    if not plan.jobs:
        print("Nothing to do.", file=sys.stderr)
        return 1

    total = len(plan.jobs)
    counter = iter(range(1, total + 1))

    def report(result):
        tag = {Status.DONE: "ok", Status.SKIPPED: "skip", Status.FAILED: "FAIL"}[result.status]
        line = f"[{next(counter)}/{total}] {tag:4} {result.job.destination}"
        if result.status is Status.FAILED:
            line += f"\n        {result.message}"
        print(line, flush=True)

    try:
        converter = Converter(ffmpeg, settings, on_result=report)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        results = converter.run(plan.jobs)
    except KeyboardInterrupt:
        converter.cancel()
        print("Cancelled.", file=sys.stderr)
        return 130

    failed = sum(1 for r in results if r.status is Status.FAILED)
    print(
        f"Finished: {sum(1 for r in results if r.status is Status.DONE)} done, "
        f"{sum(1 for r in results if r.status is Status.SKIPPED)} skipped, {failed} failed."
    )
    return 1 if failed else 0


def _match_choice(choices: tuple[str, ...], value: str) -> str:
    """Let users type "V0" for the "V0 (~245 kbps)" preset."""
    for choice in choices:
        if choice.split()[0].lower() == value.lower():
            return choice
    return value


if __name__ == "__main__":
    sys.exit(main())
