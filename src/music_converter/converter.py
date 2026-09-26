"""Run a plan's jobs on a thread pool, one ffmpeg process per track."""

from __future__ import annotations

import base64
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .formats import OutputFormat
from .planner import IMAGE_EXTENSIONS, Job, JobKind

# Keep ffmpeg from flashing a console window for every track on Windows.
_CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Checked in order when a track has no embedded cover of its own.
COVER_NAMES = ("cover", "folder", "front", "albumart", "album")


class Status(Enum):
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Result:
    job: Job
    status: Status
    message: str = ""


@dataclass(frozen=True)
class Settings:
    fmt: OutputFormat
    mode_key: str
    quality: str
    threads: int = os.cpu_count() or 1
    skip_existing: bool = True
    embed_cover: bool = True


def find_ffmpeg() -> str | None:
    """Locate ffmpeg: $MUSIC_CONVERTER_FFMPEG, then next to the app, then PATH."""
    override = os.environ.get("MUSIC_CONVERTER_FFMPEG")
    if override and Path(override).is_file():
        return override
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    if getattr(sys, "frozen", False):
        # Packaged app: an ffmpeg folder shipped next to MusicConverter.exe.
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[2]  # project root
    for candidate in (base / exe, base / "ffmpeg" / exe, base / "ffmpeg" / "bin" / exe):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ffmpeg")


class Converter:
    def __init__(
        self, ffmpeg: str, settings: Settings, on_result: Callable[[Result], None] | None = None
    ):
        self.ffmpeg = ffmpeg
        self.settings = settings
        # Validate up front so a bad bitrate fails once, not once per track.
        self.quality_args = settings.fmt.mode(settings.mode_key).args(settings.quality)
        self.on_result = on_result or (lambda result: None)
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen] = set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        """Stop queued jobs and kill any running ffmpeg processes."""
        self._cancel.set()
        with self._lock:
            for process in self._processes:
                process.kill()

    def run(self, jobs: list[Job]) -> list[Result]:
        """Blocking; call from a background thread when driving a GUI."""
        # Artwork copies are quick, do them first so folders look right early on.
        ordered = sorted(jobs, key=lambda job: job.kind is not JobKind.COPY_IMAGE)
        with ThreadPoolExecutor(max_workers=max(1, self.settings.threads)) as pool:
            futures = [pool.submit(self._run_one, job) for job in ordered]
            try:
                # Wait in short slices so Ctrl+C is noticed promptly (on Windows a
                # plain blocking wait can't be interrupted).
                while wait(futures, timeout=0.25).not_done:
                    pass
            except BaseException:
                self.cancel()
                raise
            return [future.result() for future in futures]

    def _run_one(self, job: Job) -> Result:
        if self.cancelled:
            result = Result(job, Status.CANCELLED)
        elif self.settings.skip_existing and job.destination.exists():
            result = Result(job, Status.SKIPPED, "already exists")
        else:
            try:
                job.destination.parent.mkdir(parents=True, exist_ok=True)
                if job.kind is JobKind.CONVERT:
                    self._convert(job)
                else:
                    shutil.copy2(job.source, job.destination)
                result = Result(job, Status.DONE)
            except _Cancelled:
                result = Result(job, Status.CANCELLED)
            except Exception as exc:
                result = Result(job, Status.FAILED, str(exc).strip() or type(exc).__name__)
        if result.status is not Status.CANCELLED:
            self.on_result(result)
        return result

    def _convert(self, job: Job) -> None:
        fmt = self.settings.fmt
        # Write to a temporary name so a cancelled or failed run never leaves a
        # truncated file that "skip existing" would later mistake for a finished one.
        partial = job.destination.with_name(job.destination.name + ".part")
        with tempfile.TemporaryDirectory(prefix="music-converter-") as tmp:
            cmd = [
                self.ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(job.source),
            ]
            maps = ["-map", "0:a:0", "-map_metadata", "0"]

            cover = self._find_cover(job.source) if self.settings.embed_cover else None
            if cover and fmt.cover_method == "stream":
                image = Path(tmp) / f"cover{cover.extension}"
                image.write_bytes(cover.data)
                cmd += ["-i", str(image)]
                maps += [
                    "-map",
                    "1:v:0",
                    "-c:v",
                    "copy",
                    "-disposition:v:0",
                    "attached_pic",
                    "-metadata:s:v:0",
                    "comment=Cover (front)",
                ]
            elif cover and fmt.cover_method == "metadata_block":
                # Ogg has no attached-picture streams; players read a base64 FLAC
                # picture block from the METADATA_BLOCK_PICTURE comment instead.
                # It is passed via a metadata file because it is far too long for a
                # command line.
                meta = Path(tmp) / "cover.ffmeta"
                meta.write_text(
                    ";FFMETADATA1\nMETADATA_BLOCK_PICTURE="
                    + cover.picture_block_b64().replace("=", "\\=")
                    + "\n",
                    encoding="utf-8",
                )
                cmd += ["-f", "ffmetadata", "-i", str(meta)]
                maps += ["-map_metadata", "1"]

            cmd += maps
            cmd += [
                "-c:a",
                fmt.codec,
                *self.quality_args,
                *fmt.extra_args,
                "-f",
                fmt.muxer,
                str(partial),
            ]
            try:
                self._run_ffmpeg(cmd)
                os.replace(partial, job.destination)
            finally:
                partial.unlink(missing_ok=True)

    def _run_ffmpeg(self, cmd: list[str], capture_stdout: bool = False) -> bytes:
        if self.cancelled:
            raise _Cancelled
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=_CREATE_FLAGS,
        )
        with self._lock:
            self._processes.add(process)
        try:
            stdout, stderr = process.communicate()
        finally:
            with self._lock:
                self._processes.discard(process)
        if self.cancelled:
            raise _Cancelled
        if process.returncode != 0:
            lines = stderr.decode("utf-8", "replace").strip().splitlines()
            raise RuntimeError(lines[-1] if lines else f"ffmpeg exited with {process.returncode}")
        return stdout or b""

    def _find_cover(self, source: Path) -> _Cover | None:
        """The track's embedded picture, else a cover image from its folder."""
        try:
            data = self._run_ffmpeg(
                [
                    self.ffmpeg,
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-c",
                    "copy",
                    "-frames:v",
                    "1",
                    "-f",
                    "image2pipe",
                    "-",
                ],
                capture_stdout=True,
            )
            cover = _Cover.from_bytes(data)
            if cover:
                return cover
        except RuntimeError:
            pass  # No embedded picture.
        image = find_folder_cover(source.parent)
        return _Cover.from_bytes(image.read_bytes()) if image else None


def find_folder_cover(folder: Path) -> Path | None:
    try:
        images = sorted(
            p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()
        )
    except OSError:
        return None
    by_stem = {p.stem.lower(): p for p in images}
    for name in COVER_NAMES:
        if name in by_stem:
            return by_stem[name]
    for image in images:
        if any(name in image.stem.lower() for name in COVER_NAMES):
            return image
    return images[0] if len(images) == 1 else None


@dataclass(frozen=True)
class _Cover:
    data: bytes
    mime: str
    extension: str

    @classmethod
    def from_bytes(cls, data: bytes) -> _Cover | None:
        # Only JPEG and PNG are embeddable in every target container.
        if data.startswith(b"\xff\xd8"):
            return cls(data, "image/jpeg", ".jpg")
        if data.startswith(b"\x89PNG"):
            return cls(data, "image/png", ".png")
        return None

    def picture_block_b64(self) -> str:
        mime = self.mime.encode("ascii")
        block = (
            struct.pack(">II", 3, len(mime))
            + mime  # picture type 3 = front cover
            + struct.pack(">I", 0)  # empty description
            + struct.pack(">IIIII", 0, 0, 0, 0, len(self.data))  # size/depth unknown
            + self.data
        )
        return base64.b64encode(block).decode("ascii")


class _Cancelled(Exception):
    pass
