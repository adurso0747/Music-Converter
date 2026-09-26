"""Double-click launcher (no console window on Windows) that works without installing.

If the project's .venv exists it is used, so double-clicking works even when the
system Python doesn't have the dependencies installed.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHONW = ROOT / ".venv" / ("Scripts/pythonw.exe" if sys.platform == "win32" else "bin/python")

if VENV_PYTHONW.is_file() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    subprocess.Popen([str(VENV_PYTHONW), str(Path(__file__).resolve())], cwd=ROOT)
    sys.exit()

sys.path.insert(0, str(ROOT / "src"))

try:
    from music_converter.gui import main
except ImportError as exc:
    # pythonw has no console, so show the problem instead of failing silently.
    from tkinter import Tk, messagebox

    Tk().withdraw()
    messagebox.showerror(
        "Music Converter",
        f"Missing dependency: {exc.name}\n\nFrom the project folder, run:\n"
        "python -m venv .venv\n.venv\\Scripts\\pip install -e .",
    )
    sys.exit(1)

main()
