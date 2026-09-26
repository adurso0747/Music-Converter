from pathlib import Path

from music_converter.formats import MP3, OPUS
from music_converter.planner import JobKind, build_plan


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def destinations(plan, kind=None):
    return sorted(str(j.destination) for j in plan.jobs if kind is None or j.kind is kind)


def test_folder_structure_is_recreated(tmp_path):
    library = tmp_path / "Music"
    touch(library / "Artist" / "Album" / "01 Song.flac")
    touch(library / "Artist" / "Album" / "02 Song.wav")
    touch(library / "Artist" / "Album" / "cover.jpg")
    touch(library / "Artist" / "Album" / "notes.txt")
    touch(library / "Artist" / "Album" / "Scans" / "booklet.jpg")
    out = tmp_path / "out"

    plan = build_plan([library], out, OPUS)

    album = out / "Music" / "Artist" / "Album"
    assert destinations(plan, JobKind.CONVERT) == sorted(
        [str(album / "01 Song.opus"), str(album / "02 Song.opus")]
    )
    # Artwork next to the music is copied; image-only folders are not recreated.
    assert destinations(plan, JobKind.COPY_IMAGE) == [str(album / "cover.jpg")]


def test_single_files_go_to_output_root(tmp_path):
    song = touch(tmp_path / "a" / "Song.flac")
    out = tmp_path / "out"
    plan = build_plan([song], out, MP3)
    assert destinations(plan) == [str(out / "Song.mp3")]


def test_name_collisions_get_suffix(tmp_path):
    a = touch(tmp_path / "a" / "Song.flac")
    b = touch(tmp_path / "b" / "Song.wav")
    plan = build_plan([a, b], tmp_path / "out", MP3)
    assert [j.destination.name for j in plan.jobs] == ["Song.mp3", "Song (2).mp3"]


def test_overlapping_inputs_are_converted_once(tmp_path):
    library = tmp_path / "Music"
    song = touch(library / "Album" / "Song.flac")
    plan = build_plan([library, library / "Album", song], tmp_path / "out", MP3)
    assert len(plan.jobs) == 1


def test_output_inside_input_is_not_scanned(tmp_path):
    library = tmp_path / "Music"
    touch(library / "Song.flac")
    out = library / "converted"
    touch(out / "Old.flac")
    plan = build_plan([library], out, MP3)
    assert [j.source.name for j in plan.jobs] == ["Song.flac"]


def test_lossy_files_and_options(tmp_path):
    library = tmp_path / "Music"
    touch(library / "Song.flac")
    touch(library / "Other.mp3")
    touch(library / "cover.png")
    out = tmp_path / "out"

    default = build_plan([library], out, MP3)
    assert {j.kind for j in default.jobs} == {JobKind.CONVERT, JobKind.COPY_IMAGE}

    plan = build_plan([library], out, MP3, copy_artwork=False, copy_lossy=True)
    assert {j.kind for j in plan.jobs} == {JobKind.CONVERT, JobKind.COPY_AUDIO}


def test_unsupported_and_missing_inputs_are_reported(tmp_path):
    text = touch(tmp_path / "notes.txt")
    missing = tmp_path / "nope.flac"
    plan = build_plan([text, missing], tmp_path / "out", MP3)
    assert plan.jobs == []
    assert plan.ignored == [text, missing]
