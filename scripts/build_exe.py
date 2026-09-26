"""Build a standalone Windows app with PyInstaller.

    python scripts/build_exe.py                     # bundle the ffmpeg found on PATH
    python scripts/build_exe.py --ffmpeg C:/ffmpeg/bin/ffmpeg.exe
    python scripts/build_exe.py --no-ffmpeg         # users must install ffmpeg themselves

Produces dist/MusicConverter/ (run MusicConverter.exe) and a zip of it for sharing.
Requires the build extra: pip install -e .[build]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ASSETS = SRC / "music_converter" / "assets"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
APP_NAME = "MusicConverter"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ffmpeg", type=Path, help="ffmpeg executable to bundle")
    group.add_argument("--no-ffmpeg", action="store_true", help="don't bundle ffmpeg")
    args = parser.parse_args()

    ffmpeg = None
    if not args.no_ffmpeg:
        ffmpeg = resolve_ffmpeg(args.ffmpeg)
        if ffmpeg is None:
            parser.error("ffmpeg not found; pass --ffmpeg PATH or --no-ffmpeg")

    sys.path.insert(0, str(SRC))
    import PyInstaller.__main__

    from music_converter import __version__

    BUILD.mkdir(exist_ok=True)
    entry = BUILD / "entry.py"
    entry.write_text("from music_converter.gui import main\n\nmain()\n", encoding="utf-8")

    PyInstaller.__main__.run(
        [
            str(entry),
            "--name", APP_NAME,
            "--windowed",
            "--onedir",
            "--noconfirm",
            "--clean",
            "--icon", str(ASSETS / "icon.ico"),
            "--paths", str(SRC),
            "--add-data", f"{ASSETS}{os.pathsep}music_converter/assets",
            "--collect-data", "customtkinter",
            "--distpath", str(DIST),
            "--workpath", str(BUILD / "pyinstaller"),
            "--specpath", str(BUILD),
        ]
    )  # fmt: skip

    app_dir = DIST / APP_NAME
    shutil.copy2(ROOT / "LICENSE", app_dir / "LICENSE.txt")
    if ffmpeg is not None:
        bundle_ffmpeg(ffmpeg, app_dir / "ffmpeg")

    platform = "windows" if sys.platform == "win32" else sys.platform
    archive = shutil.make_archive(
        str(DIST / f"{APP_NAME}-{__version__}-{platform}"), "zip", DIST, APP_NAME
    )
    print(f"\nBuilt {app_dir / (APP_NAME + '.exe')}\nArchive: {archive}")
    return 0


def resolve_ffmpeg(explicit: Path | None) -> Path | None:
    path = explicit or (Path(found) if (found := shutil.which("ffmpeg")) else None)
    if path is None or not path.is_file():
        return None
    # Scoop installs a small "shim" exe on PATH; the real binary is named in a .shim file.
    shim = path.with_suffix(".shim")
    if shim.is_file():
        for line in shim.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "path":
                return Path(value.strip().strip('"'))
    return path.resolve()


def bundle_ffmpeg(ffmpeg: Path, target: Path) -> None:
    """Copy ffmpeg and, for "shared" builds, the DLLs it loads from its own folder."""
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ffmpeg, target / ffmpeg.name)
    for dll in ffmpeg.parent.glob("*.dll"):
        shutil.copy2(dll, target / dll.name)
    license_file = next(
        (p for p in (ffmpeg.parent / "LICENSE", ffmpeg.parent.parent / "LICENSE") if p.is_file()),
        None,
    )
    if license_file:
        shutil.copy2(license_file, target / "LICENSE.txt")
    (target / "README.txt").write_text(
        "This folder contains FFmpeg (https://ffmpeg.org), which Music Converter uses to\n"
        "encode audio. FFmpeg is licensed separately from Music Converter; see LICENSE.txt\n"
        "here and https://ffmpeg.org/legal.html. Its source code is available from\n"
        "https://ffmpeg.org/download.html.\n",
        encoding="utf-8",
    )
    print(f"Bundled ffmpeg from {ffmpeg.parent}")


if __name__ == "__main__":
    sys.exit(main())
