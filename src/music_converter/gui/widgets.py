from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import customtkinter as ctk


class IntSpinbox(ctk.CTkFrame):
    """An integer entry with -/+ buttons, clamped to [minimum, maximum]."""

    def __init__(
        self,
        master,
        *,
        minimum: int,
        maximum: int,
        value: int,
        width: int = 120,
        height: int = 28,
        **kwargs,
    ):
        super().__init__(master, width=width, height=height, **kwargs)
        self.minimum = minimum
        self.maximum = maximum

        self.grid_columnconfigure(1, weight=1)
        button_size = height - 6
        self.subtract_button = ctk.CTkButton(
            self, text="−", width=button_size, height=button_size, command=lambda: self._step(-1)
        )
        self.subtract_button.grid(row=0, column=0, padx=(3, 0), pady=3)
        self.entry = ctk.CTkEntry(
            self, width=width - 2 * height, height=button_size, border_width=0, justify="center"
        )
        self.entry.grid(row=0, column=1, padx=3, pady=3, sticky="ew")
        self.add_button = ctk.CTkButton(
            self, text="+", width=button_size, height=button_size, command=lambda: self._step(1)
        )
        self.add_button.grid(row=0, column=2, padx=(0, 3), pady=3)

        self.entry.bind("<FocusOut>", lambda _event: self.set(self.get()))
        self.set(value)

    def _step(self, delta: int) -> None:
        self.set(self.get() + delta)

    def get(self) -> int:
        try:
            value = int(self.entry.get().strip())
        except ValueError:
            value = self.minimum
        return max(self.minimum, min(self.maximum, value))

    def set(self, value: int) -> None:
        value = max(self.minimum, min(self.maximum, int(value)))
        self.entry.delete(0, "end")
        self.entry.insert(0, str(value))

    def configure_state(self, state: str) -> None:
        for widget in (self.subtract_button, self.entry, self.add_button):
            widget.configure(state=state)


class SourceList(ctk.CTkScrollableFrame):
    """The list of files and folders to convert, each with a remove button."""

    def __init__(self, master, *, placeholder: str, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.placeholder = placeholder
        self._paths: list[Path] = []
        self._enabled = True
        self._render()

    @property
    def paths(self) -> list[Path]:
        return list(self._paths)

    def add(self, paths: Iterable[Path]) -> bool:
        """Add paths not already listed; returns True if anything was added."""
        new = [p for p in dict.fromkeys(paths) if p not in self._paths]
        self._paths.extend(new)
        if new:
            self._render()
        return bool(new)

    def remove(self, path: Path) -> None:
        self._paths.remove(path)
        self._render()

    def clear(self) -> None:
        self._paths.clear()
        self._render()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._render()

    def _render(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        if not self._paths:
            ctk.CTkLabel(self, text=self.placeholder, text_color="gray55").grid(
                row=0, column=0, sticky="w", padx=4
            )
            return
        for row, path in enumerate(self._paths):
            icon = "📁" if path.is_dir() else "🎵"
            ctk.CTkLabel(self, text=f"{icon}  {path}", anchor="w").grid(
                row=row, column=0, sticky="ew", padx=4
            )
            ctk.CTkButton(
                self,
                text="✕",
                width=28,
                height=24,
                fg_color="transparent",
                hover_color=("gray75", "gray30"),
                text_color=("gray20", "gray80"),
                state="normal" if self._enabled else "disabled",
                command=lambda p=path: self.remove(p),
            ).grid(row=row, column=1, padx=(4, 0), pady=1)
