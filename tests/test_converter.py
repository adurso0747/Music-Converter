"""End-to-end tests that run the real ffmpeg (skipped if it isn't installed)."""

import json
import subprocess
from pathlib import Path

import pytest

from music_converter.cli import main as cli_main
from music_converter.converter import Converter, Settings, Status, find_ffmpeg
from music_converter.formats import FORMATS, MP3, OPUS
from music_converter.planner import build_plan

FFMPEG = find_ffmpeg()
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")


def ffmpeg(*args):
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def probe(path: Path) -> dict:
    ffprobe = str(Path(FFMPEG).with_name(Path(FFMPEG).name.replace("ffmpeg", "ffprobe")))
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
    ).stdout
    return json.loads(out)


def tags(info: dict) -> dict:
    merged = {k.lower(): v for k, v in info["format"].get("tags", {}).items()}
    for stream in info["streams"]:
        merged.update({k.lower(): v for k, v in stream.get("tags", {}).items()})
    return merged


@pytest.fixture
def library(tmp_path):
    album = tmp_path / "Music" / "Artist" / "Album"
    album.mkdir(parents=True)
    cover = tmp_path / "embedded.png"
    ffmpeg("-f", "lavfi", "-i", "color=red:s=32x32", "-frames:v", "1", str(cover))
    # FLAC with tags and an embedded cover.
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "sine=d=1",
        "-i",
        str(cover),
        "-map",
        "0",
        "-map",
        "1",
        "-c:v",
        "copy",
        "-disposition:v",
        "attached_pic",
        "-metadata",
        "title=Tagged",
        "-metadata",
        "artist=Someone",
        str(album / "01 Tagged.flac"),
    )
    # WAV without a cover; should pick up folder.jpg.
    ffmpeg("-f", "lavfi", "-i", "sine=d=1:sample_rate=96000", str(album / "02 Plain.wav"))
    ffmpeg("-f", "lavfi", "-i", "color=blue:s=32x32", "-frames:v", "1", str(album / "folder.jpg"))
    (album / "broken.flac").write_bytes(b"not audio")
    return tmp_path / "Music"


@pytest.mark.parametrize("fmt_key", list(FORMATS))
def test_convert_library(tmp_path, library, fmt_key):
    fmt = FORMATS[fmt_key]
    out = tmp_path / "out"
    plan = build_plan([library], out, fmt)
    settings = Settings(fmt=fmt, mode_key=fmt.modes[0].key, quality=fmt.modes[0].default, threads=4)
    results = Converter(FFMPEG, settings).run(plan.jobs)

    by_name = {r.job.source.name: r for r in results}
    assert by_name["broken.flac"].status is Status.FAILED
    assert all(r.status is Status.DONE for n, r in by_name.items() if n != "broken.flac")

    album = out / "Music" / "Artist" / "Album"
    assert (album / "folder.jpg").is_file()
    assert not list(album.glob("*.part"))
    assert not (album / f"broken{fmt.extension}").exists()

    tagged = probe(album / f"01 Tagged{fmt.extension}")
    assert tags(tagged)["title"] == "Tagged"
    assert tags(tagged)["artist"] == "Someone"
    # Every format carries a cover: embedded for the FLAC, folder.jpg for the WAV.
    for name in ("01 Tagged", "02 Plain"):
        info = probe(album / f"{name}{fmt.extension}")
        assert any(s["codec_type"] == "video" for s in info["streams"]), name
    assert probe(album / f"01 Tagged{fmt.extension}")["streams"][0]["codec_name"] in (
        "mp3",
        "opus",
        "aac",
        "vorbis",
    )


def test_skip_existing_and_no_embed(tmp_path, library):
    out = tmp_path / "out"
    plan = build_plan([library], out, OPUS, copy_artwork=False)
    settings = Settings(fmt=OPUS, mode_key="vbr", quality="96", threads=2, embed_cover=False)
    first = Converter(FFMPEG, settings).run(plan.jobs)
    second = Converter(FFMPEG, settings).run(plan.jobs)
    assert sum(r.status is Status.DONE for r in first) == 2
    assert sum(r.status is Status.SKIPPED for r in second) == 2

    info = probe(out / "Music" / "Artist" / "Album" / "01 Tagged.opus")
    assert not any(s["codec_type"] == "video" for s in info["streams"])


def test_cancel_before_start(tmp_path, library):
    plan = build_plan([library], tmp_path / "out", MP3)
    converter = Converter(FFMPEG, Settings(fmt=MP3, mode_key="cbr", quality="192"))
    converter.cancel()
    assert all(r.status is Status.CANCELLED for r in converter.run(plan.jobs))


def test_cli(tmp_path, library, capsys):
    out = tmp_path / "cli-out"
    song = library / "Artist" / "Album" / "02 Plain.wav"
    assert cli_main([str(song), "-o", str(out), "-f", "mp3", "-q", "V2"]) == 0
    assert (out / "02 Plain.mp3").is_file()
    assert "1 done" in capsys.readouterr().out
