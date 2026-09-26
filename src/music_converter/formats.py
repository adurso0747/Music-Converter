"""Output formats and the ffmpeg encoder arguments for each quality setting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityMode:
    """One way of expressing quality for a format (e.g. CBR bitrate or VBR preset)."""

    key: str
    label: str
    choices: tuple[str, ...]
    default: str
    # Build encoder args from a choice (or a user-typed value when custom_range is set).
    build_args: Callable[[str], list[str]]
    # When set, the user may type any integer bitrate (kbps) within this range.
    custom_range: tuple[int, int] | None = None
    hint: str = ""

    def validate(self, value: str) -> str:
        """Return the normalised value or raise ValueError with a readable message."""
        value = value.strip()
        if value in self.choices:
            return value
        if self.custom_range is not None:
            low, high = self.custom_range
            number = value.lower().removesuffix("k").removesuffix("kbps").strip()
            if number.isdigit() and low <= int(number) <= high:
                return number
            raise ValueError(f"{self.label}: enter a bitrate between {low} and {high} kbps.")
        raise ValueError(f"{self.label}: choose one of {', '.join(self.choices)}.")

    def args(self, value: str) -> list[str]:
        return self.build_args(self.validate(value))


@dataclass(frozen=True)
class OutputFormat:
    key: str
    label: str
    extension: str
    muxer: str
    codec: str
    modes: tuple[QualityMode, ...]
    # "stream": cover is an attached-picture video stream (MP3, MP4).
    # "metadata_block": cover is a base64 METADATA_BLOCK_PICTURE comment (Ogg).
    cover_method: str
    extra_args: tuple[str, ...] = ()

    def mode(self, key: str) -> QualityMode:
        for mode in self.modes:
            if mode.key == key:
                return mode
        return self.modes[0]


def _bitrate(value: str) -> list[str]:
    return ["-b:a", f"{value.split()[0]}k"]


def _vbr_quality(value: str) -> list[str]:
    # "V2 (~190 kbps)" -> "2", "q6 (~192 kbps)" -> "6"
    return ["-q:a", value.split()[0].lstrip("Vq")]


MP3 = OutputFormat(
    key="mp3",
    label="MP3",
    extension=".mp3",
    muxer="mp3",
    codec="libmp3lame",
    modes=(
        QualityMode(
            key="vbr",
            label="VBR",
            choices=(
                "V0 (~245 kbps)",
                "V1 (~225 kbps)",
                "V2 (~190 kbps)",
                "V3 (~175 kbps)",
                "V4 (~165 kbps)",
                "V5 (~130 kbps)",
            ),
            default="V0 (~245 kbps)",
            build_args=_vbr_quality,
            hint="V0 is the best quality, higher numbers make smaller files",
        ),
        QualityMode(
            key="cbr",
            label="CBR",
            choices=("128", "160", "192", "224", "256", "320"),
            default="320",
            build_args=_bitrate,
            custom_range=(32, 320),
        ),
    ),
    cover_method="stream",
    # ID3v2.3 is the most widely supported tag version on phones and in Windows.
    extra_args=("-id3v2_version", "3"),
)

OPUS = OutputFormat(
    key="opus",
    label="Opus",
    extension=".opus",
    muxer="ogg",
    codec="libopus",
    modes=(
        QualityMode(
            key="vbr",
            label="VBR",
            choices=("64", "96", "128", "160", "192", "256"),
            default="128",
            build_args=lambda v: [*_bitrate(v), "-vbr", "on"],
            custom_range=(6, 510),
        ),
        QualityMode(
            key="cbr",
            label="CBR",
            choices=("64", "96", "128", "160", "192", "256"),
            default="128",
            build_args=lambda v: [*_bitrate(v), "-vbr", "off"],
            custom_range=(6, 510),
        ),
    ),
    cover_method="metadata_block",
)

AAC = OutputFormat(
    key="aac",
    label="AAC (M4A)",
    extension=".m4a",
    muxer="ipod",
    codec="aac",
    modes=(
        QualityMode(
            key="cbr",
            label="CBR",
            choices=("128", "160", "192", "256", "320"),
            default="256",
            build_args=_bitrate,
            custom_range=(32, 512),
        ),
    ),
    cover_method="stream",
    extra_args=("-movflags", "+faststart"),
)

VORBIS = OutputFormat(
    key="vorbis",
    label="Ogg Vorbis",
    extension=".ogg",
    muxer="ogg",
    codec="libvorbis",
    modes=(
        QualityMode(
            key="vbr",
            label="VBR",
            choices=(
                "q3 (~112 kbps)",
                "q4 (~128 kbps)",
                "q5 (~160 kbps)",
                "q6 (~192 kbps)",
                "q7 (~224 kbps)",
                "q8 (~256 kbps)",
                "q9 (~320 kbps)",
                "q10 (~500 kbps)",
            ),
            default="q6 (~192 kbps)",
            build_args=_vbr_quality,
            hint="higher q = better quality, larger files",
        ),
    ),
    cover_method="metadata_block",
)

FORMATS: dict[str, OutputFormat] = {f.key: f for f in (MP3, OPUS, AAC, VORBIS)}


def get_format(key: str) -> OutputFormat:
    try:
        return FORMATS[key.lower()]
    except KeyError:
        raise ValueError(f"Unknown format '{key}'. Choose from: {', '.join(FORMATS)}") from None
