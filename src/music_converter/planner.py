"""Turn the user's selected files and folders into a list of conversion/copy jobs.

Folder inputs keep their structure: selecting ``D:/Music/Artist`` with output
``E:/Phone`` produces ``E:/Phone/Artist/<Album>/<Track>.mp3``. Single-file inputs
are written directly into the output folder.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .formats import OutputFormat

LOSSLESS_EXTENSIONS = frozenset({".flac", ".wav", ".aiff", ".aif", ".wv", ".ape"})
LOSSY_EXTENSIONS = frozenset({".mp3", ".m4a", ".aac", ".ogg", ".opus"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"})


class JobKind(Enum):
    CONVERT = "convert"
    COPY_AUDIO = "copy audio"
    COPY_IMAGE = "copy image"


@dataclass(frozen=True)
class Job:
    kind: JobKind
    source: Path
    destination: Path


@dataclass
class Plan:
    jobs: list[Job] = field(default_factory=list)
    # Inputs that could not be used (missing, or a file with an unsupported extension).
    ignored: list[Path] = field(default_factory=list)

    @property
    def convert_count(self) -> int:
        return sum(1 for job in self.jobs if job.kind is JobKind.CONVERT)


def is_convertible(path: Path) -> bool:
    return path.suffix.lower() in LOSSLESS_EXTENSIONS


def build_plan(
    inputs: list[Path],
    output_dir: Path,
    fmt: OutputFormat,
    *,
    copy_artwork: bool = True,
    copy_lossy: bool = False,
) -> Plan:
    plan = Plan()
    planner = _Planner(plan, output_dir, fmt, copy_artwork, copy_lossy)
    for source in inputs:
        source = Path(source)
        if source.is_dir():
            planner.add_folder(source)
        elif source.is_file() and planner.audio_kind(source) is not None:
            planner.add_audio(source, output_dir)
        else:
            plan.ignored.append(source)
    return plan


class _Planner:
    def __init__(
        self, plan: Plan, output_dir: Path, fmt: OutputFormat, copy_artwork: bool, copy_lossy: bool
    ):
        self.plan = plan
        self.output_dir = output_dir
        self.fmt = fmt
        self.copy_artwork = copy_artwork
        self.copy_lossy = copy_lossy
        self._output_resolved = _resolve(output_dir)
        self._claimed: set[str] = set()
        self._queued_sources: set[str] = set()

    def audio_kind(self, path: Path) -> JobKind | None:
        suffix = path.suffix.lower()
        if suffix in LOSSLESS_EXTENSIONS:
            return JobKind.CONVERT
        if self.copy_lossy and suffix in LOSSY_EXTENSIONS:
            return JobKind.COPY_AUDIO
        return None

    def add_folder(self, folder: Path) -> None:
        # A drive root such as "D:\" has no name; fall back to something readable.
        root_name = folder.name or _drive_label(folder)
        dest_root = self.output_dir / root_name

        for dirpath, dirnames, filenames in os.walk(folder):
            current = Path(dirpath)
            # Never descend into the output folder if it lives inside an input folder.
            dirnames[:] = sorted(
                d for d in dirnames if _resolve(current / d) != self._output_resolved
            )
            filenames.sort(key=str.lower)
            dest_dir = dest_root / current.relative_to(folder)

            added = [
                self.add_audio(current / f, dest_dir)
                for f in filenames
                if self.audio_kind(Path(f)) is not None
            ]
            if not any(added):
                # Folders without (new) music, e.g. "Scans", are not recreated.
                continue
            if self.copy_artwork:
                for name in filenames:
                    if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
                        self._add_image(current / name, dest_dir / name)

    def add_audio(self, source: Path, dest_dir: Path) -> bool:
        """Queue one audio file; returns False if it was already queued by another input."""
        source_key = _key(_resolve(source))
        if source_key in self._queued_sources:
            return False
        self._queued_sources.add(source_key)
        kind = self.audio_kind(source)
        if kind is JobKind.CONVERT:
            destination = dest_dir / (source.stem + self.fmt.extension)
        else:
            destination = dest_dir / source.name
        destination = self._claim_unique(destination)
        self.plan.jobs.append(Job(kind, source, destination))
        return True

    def _add_image(self, source: Path, destination: Path) -> None:
        # The same artwork file name twice in one folder can only happen with
        # overlapping inputs; one copy is enough.
        key = _key(destination)
        if key in self._claimed:
            return
        self._claimed.add(key)
        self.plan.jobs.append(Job(JobKind.COPY_IMAGE, source, destination))

    def _claim_unique(self, destination: Path) -> Path:
        """Avoid two jobs writing the same file (e.g. "track.flac" and "track.wav")."""
        candidate = destination
        counter = 2
        while _key(candidate) in self._claimed:
            candidate = destination.with_name(f"{destination.stem} ({counter}){destination.suffix}")
            counter += 1
        self._claimed.add(_key(candidate))
        return candidate


def _key(path: Path) -> str:
    # Windows, macOS and most phone file systems are case-insensitive.
    return os.path.normcase(os.path.normpath(str(path))).lower()


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _drive_label(folder: Path) -> str:
    drive = folder.drive.rstrip(":\\/") or "root"
    return f"Drive {drive}"
