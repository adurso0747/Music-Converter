import pytest

from music_converter.formats import AAC, MP3, OPUS, VORBIS, get_format


def test_mp3_vbr_preset():
    assert MP3.mode("vbr").args("V2 (~190 kbps)") == ["-q:a", "2"]


def test_mp3_custom_cbr_bitrate():
    assert MP3.mode("cbr").args("200") == ["-b:a", "200k"]
    assert MP3.mode("cbr").args("200k") == ["-b:a", "200k"]
    with pytest.raises(ValueError):
        MP3.mode("cbr").args("500")
    with pytest.raises(ValueError):
        MP3.mode("cbr").args("abc")


def test_opus_modes():
    assert OPUS.mode("vbr").args("128") == ["-b:a", "128k", "-vbr", "on"]
    assert OPUS.mode("cbr").args("96") == ["-b:a", "96k", "-vbr", "off"]


def test_fixed_choice_modes_reject_other_values():
    assert VORBIS.mode("vbr").args("q6 (~192 kbps)") == ["-q:a", "6"]
    with pytest.raises(ValueError):
        VORBIS.mode("vbr").args("192")


def test_defaults_are_valid():
    for fmt in (MP3, OPUS, AAC, VORBIS):
        for mode in fmt.modes:
            mode.args(mode.default)


def test_get_format():
    assert get_format("OPUS") is OPUS
    with pytest.raises(ValueError):
        get_format("wma")
