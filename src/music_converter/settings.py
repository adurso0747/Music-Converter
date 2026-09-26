"""Remember the user's choices between runs."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class UserSettings:
    output_dir: str = ""
    format_key: str = "mp3"
    mode_key: str = ""
    quality: str = ""
    threads: int = os.cpu_count() or 1
    copy_artwork: bool = True
    embed_cover: bool = True
    skip_existing: bool = True
    copy_lossy: bool = False
    last_browse_dir: str = ""


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "MusicConverter" / "settings.json"


def load() -> UserSettings:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UserSettings()
    known = {f.name: f.type for f in fields(UserSettings)}
    defaults = UserSettings()
    values = {}
    for key, value in data.items():
        # Ignore unknown or wrongly typed entries rather than failing to start.
        if key in known and isinstance(value, type(getattr(defaults, key))):
            values[key] = value
    return UserSettings(**values)


def save(settings: UserSettings) -> None:
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    except OSError:
        pass  # Not being able to remember settings should never break a conversion.
