"""The desktop GUI."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import settings as user_settings
from ..converter import Converter, Result, Settings, Status, find_ffmpeg
from ..formats import FORMATS, OutputFormat
from ..planner import LOSSLESS_EXTENSIONS, LOSSY_EXTENSIONS, Plan, build_plan
from .widgets import IntSpinbox, SourceList

POLL_MS = 100
ICON = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"


class MusicConverterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Music Converter")
        self.geometry("760x780")
        self.minsize(660, 700)
        if sys.platform == "win32" and ICON.is_file():
            self.iconbitmap(str(ICON))

        self.prefs = user_settings.load()
        self.ffmpeg = find_ffmpeg()
        self.events: queue.Queue = queue.Queue()
        self.converter: Converter | None = None
        self.worker: threading.Thread | None = None
        self.total_jobs = 0
        self.finished_jobs = 0
        self.counts = {Status.DONE: 0, Status.SKIPPED: 0, Status.FAILED: 0}
        self._format_by_label = {fmt.label: fmt for fmt in FORMATS.values()}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self._build_sources(row=0)
        self._build_output(row=1)
        self._build_options(row=2)
        self._build_progress(row=3)
        self._build_log(row=4)
        self._build_actions(row=5)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll_events)
        if not self.ffmpeg:
            self._log(
                "ffmpeg was not found. Install it (e.g. `winget install ffmpeg`) and make "
                "sure it is on your PATH, then restart the app."
            )
            self.convert_button.configure(state="disabled")

    # ----------------------------------------------------------------- layout

    def _section(self, row: int, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self)
        frame.grid(row=row, column=0, sticky="nsew", padx=12, pady=(10 if row == 0 else 0, 8))
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(6, 0)
        )
        return frame

    def _build_sources(self, row: int) -> None:
        frame = self._section(row, "Files and folders to convert")
        frame.grid_columnconfigure(0, weight=1)
        self.source_list = SourceList(
            frame, height=90, placeholder="Add files or folders to convert."
        )
        self.source_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=1, column=1, sticky="n", padx=(0, 10), pady=6)
        self.add_files_button = ctk.CTkButton(
            buttons, text="Add Files…", width=110, command=self._add_files
        )
        self.add_folder_button = ctk.CTkButton(
            buttons, text="Add Folder…", width=110, command=self._add_folder
        )
        self.clear_button = ctk.CTkButton(
            buttons,
            text="Clear",
            width=110,
            fg_color="gray40",
            hover_color="gray30",
            command=self.source_list.clear,
        )
        for i, button in enumerate(
            (self.add_files_button, self.add_folder_button, self.clear_button)
        ):
            button.grid(row=i, column=0, pady=(0, 6))

    def _build_output(self, row: int) -> None:
        frame = self._section(row, "Output folder")
        frame.grid_columnconfigure(0, weight=1)
        self.output_var = ctk.StringVar(value=self.prefs.output_dir)
        self.output_entry = ctk.CTkEntry(
            frame, textvariable=self.output_var, placeholder_text="Where converted music is written"
        )
        self.output_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 10))
        self.browse_button = ctk.CTkButton(
            frame, text="Browse…", width=90, command=self._browse_output
        )
        self.browse_button.grid(row=1, column=1, padx=(0, 6), pady=(6, 10))
        self.open_button = ctk.CTkButton(
            frame,
            text="Open",
            width=70,
            fg_color="gray40",
            hover_color="gray30",
            command=self._open_output,
        )
        self.open_button.grid(row=1, column=2, padx=(0, 10), pady=(6, 10))

    def _build_options(self, row: int) -> None:
        frame = self._section(row, "Options")
        frame.grid_columnconfigure((1, 3), weight=1)
        pad = {"padx": 10, "pady": 4}

        ctk.CTkLabel(frame, text="Format").grid(row=1, column=0, sticky="w", **pad)
        fmt = FORMATS.get(self.prefs.format_key, next(iter(FORMATS.values())))
        self.format_menu = ctk.CTkOptionMenu(
            frame,
            values=list(self._format_by_label),
            command=lambda _label: self._on_format_changed(),
        )
        self.format_menu.set(fmt.label)
        self.format_menu.grid(row=1, column=1, sticky="w", **pad)

        ctk.CTkLabel(frame, text="Threads").grid(row=1, column=2, sticky="w", **pad)
        cpu_count = os.cpu_count() or 1
        self.threads = IntSpinbox(
            frame, minimum=1, maximum=cpu_count, value=min(self.prefs.threads, cpu_count)
        )
        self.threads.grid(row=1, column=3, sticky="w", **pad)

        ctk.CTkLabel(frame, text="Mode").grid(row=2, column=0, sticky="w", **pad)
        self.mode_button = ctk.CTkSegmentedButton(
            frame, values=["VBR"], command=lambda _label: self._on_mode_changed()
        )
        self.mode_button.grid(row=2, column=1, sticky="w", **pad)

        ctk.CTkLabel(frame, text="Quality").grid(row=2, column=2, sticky="w", **pad)
        self.quality_box = ctk.CTkComboBox(frame, values=[""], width=170)
        self.quality_box.grid(row=2, column=3, sticky="w", **pad)
        self.quality_hint = ctk.CTkLabel(frame, text="", text_color="gray55")
        self.quality_hint.grid(row=3, column=2, columnspan=2, sticky="w", padx=10)

        self.copy_artwork_var = ctk.BooleanVar(value=self.prefs.copy_artwork)
        self.embed_cover_var = ctk.BooleanVar(value=self.prefs.embed_cover)
        self.skip_existing_var = ctk.BooleanVar(value=self.prefs.skip_existing)
        self.copy_lossy_var = ctk.BooleanVar(value=self.prefs.copy_lossy)
        self.checkboxes = [
            ctk.CTkCheckBox(
                frame, text="Copy album artwork images", variable=self.copy_artwork_var
            ),
            ctk.CTkCheckBox(frame, text="Embed cover art in files", variable=self.embed_cover_var),
            ctk.CTkCheckBox(
                frame, text="Skip files already converted", variable=self.skip_existing_var
            ),
            ctk.CTkCheckBox(
                frame, text="Copy MP3/AAC/Ogg files as-is", variable=self.copy_lossy_var
            ),
        ]
        for i, box in enumerate(self.checkboxes):
            box.grid(
                row=4 + i // 2,
                column=(i % 2) * 2,
                columnspan=2,
                sticky="w",
                padx=10,
                pady=(4, 10) if i >= 2 else 4,
            )

        self._on_format_changed(initial=True)

    def _build_progress(self, row: int) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 4))
        frame.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(frame, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(frame, text="Ready", anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew")

    def _build_log(self, row: int) -> None:
        self.log_box = ctk.CTkTextbox(self, height=120, wrap="word")
        self.log_box.grid(row=row, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.log_box.configure(state="disabled")

    def _build_actions(self, row: int) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="e", padx=12, pady=(0, 12))
        self.cancel_button = ctk.CTkButton(
            frame,
            text="Cancel",
            width=110,
            state="disabled",
            fg_color="#b33a3a",
            hover_color="#8f2e2e",
            command=self._cancel,
        )
        self.cancel_button.grid(row=0, column=0, padx=(0, 8))
        self.convert_button = ctk.CTkButton(frame, text="Convert", width=140, command=self._start)
        self.convert_button.grid(row=0, column=1)

    # ---------------------------------------------------------------- sources

    def _add_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(LOSSLESS_EXTENSIONS | LOSSY_EXTENSIONS))
        lossless = " ".join(f"*{ext}" for ext in sorted(LOSSLESS_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Choose audio files",
            initialdir=self._browse_dir(),
            filetypes=[("Lossless audio", lossless), ("All audio", patterns), ("All files", "*")],
        )
        self._add_sources(Path(p) for p in paths)

    def _add_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self,
            title="Choose a music folder",
            initialdir=self._browse_dir(),
            mustexist=True,
        )
        if path:
            self._add_sources([Path(path)])

    def _add_sources(self, paths) -> None:
        paths = list(paths)
        if self.source_list.add(paths):
            self.prefs.last_browse_dir = str(paths[-1].parent)

    def _browse_dir(self) -> str:
        return (
            self.prefs.last_browse_dir if Path(self.prefs.last_browse_dir or ".").is_dir() else ""
        )

    # ----------------------------------------------------------------- output

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(
            parent=self,
            title="Choose the output folder",
            initialdir=self.output_var.get() or self._browse_dir(),
        )
        if path:
            self.output_var.set(str(Path(path)))

    def _open_output(self) -> None:
        path = self.output_var.get().strip()
        if not path or not Path(path).is_dir():
            messagebox.showinfo(
                "Output folder", "The output folder doesn't exist yet.", parent=self
            )
            return
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])

    # ---------------------------------------------------------------- quality

    def _current_format(self) -> OutputFormat:
        return self._format_by_label[self.format_menu.get()]

    def _current_mode(self):
        fmt = self._current_format()
        label = self.mode_button.get()
        return next((m for m in fmt.modes if m.label == label), fmt.modes[0])

    def _on_format_changed(self, initial: bool = False) -> None:
        fmt = self._current_format()
        self.mode_button.configure(values=[m.label for m in fmt.modes])
        mode = fmt.mode(self.prefs.mode_key) if initial else fmt.modes[0]
        self.mode_button.set(mode.label)
        self._on_mode_changed(initial=initial)

    def _on_mode_changed(self, initial: bool = False) -> None:
        mode = self._current_mode()
        self.quality_box.configure(
            values=list(mode.choices), state="normal" if mode.custom_range else "readonly"
        )
        value = self.prefs.quality if initial and self.prefs.quality else mode.default
        try:
            value = mode.validate(value)
        except ValueError:
            value = mode.default
        self.quality_box.set(value)
        if mode.custom_range:
            low, high = mode.custom_range
            self.quality_hint.configure(text=f"kbps — pick one or type {low}–{high}")
        else:
            self.quality_hint.configure(text=mode.hint)

    # ------------------------------------------------------------- conversion

    def _collect_settings(self) -> tuple[Settings, Path] | None:
        if not self.source_list.paths:
            messagebox.showerror(
                "Nothing to convert", "Add some files or folders first.", parent=self
            )
            return None
        output = self.output_var.get().strip()
        if not output:
            messagebox.showerror(
                "No output folder", "Choose where to save the converted music.", parent=self
            )
            return None
        fmt = self._current_format()
        mode = self._current_mode()
        try:
            quality = mode.validate(self.quality_box.get())
        except ValueError as exc:
            messagebox.showerror("Invalid quality", str(exc), parent=self)
            return None
        settings = Settings(
            fmt=fmt,
            mode_key=mode.key,
            quality=quality,
            threads=self.threads.get(),
            skip_existing=self.skip_existing_var.get(),
            embed_cover=self.embed_cover_var.get(),
        )
        self._save_prefs(settings, output)
        return settings, Path(output)

    def _save_prefs(self, settings: Settings, output: str) -> None:
        self.prefs.output_dir = output
        self.prefs.format_key = settings.fmt.key
        self.prefs.mode_key = settings.mode_key
        self.prefs.quality = settings.quality
        self.prefs.threads = settings.threads
        self.prefs.copy_artwork = self.copy_artwork_var.get()
        self.prefs.embed_cover = self.embed_cover_var.get()
        self.prefs.skip_existing = self.skip_existing_var.get()
        self.prefs.copy_lossy = self.copy_lossy_var.get()
        user_settings.save(self.prefs)

    def _start(self) -> None:
        collected = self._collect_settings()
        if collected is None:
            return
        settings, output = collected
        self.converter = Converter(self.ffmpeg, settings, on_result=self.events.put)
        self.total_jobs = self.finished_jobs = 0
        self.counts = dict.fromkeys(self.counts, 0)
        self.progress.set(0)
        self._clear_log()
        self.status_label.configure(text="Scanning folders…")

        sources = self.source_list.paths
        copy_artwork = self.copy_artwork_var.get()
        copy_lossy = self.copy_lossy_var.get()
        converter = self.converter

        def work():
            try:
                plan = build_plan(
                    sources, output, settings.fmt, copy_artwork=copy_artwork, copy_lossy=copy_lossy
                )
                self.events.put(plan)
                if plan.jobs and not converter.cancelled:
                    converter.run(plan.jobs)
            except Exception as exc:
                self.events.put(exc)
            finally:
                self.events.put(None)  # "finished" marker

        self.worker = threading.Thread(target=work, daemon=True)
        self._set_running(True)
        self.worker.start()

    def _cancel(self) -> None:
        if self.converter:
            self.converter.cancel()
            self.cancel_button.configure(state="disabled")
            self.status_label.configure(text="Cancelling…")

    def _poll_events(self) -> None:
        # Worker threads never touch widgets; everything is applied here on the UI thread.
        try:
            while True:
                event = self.events.get_nowait()
                if isinstance(event, Result):
                    self._on_result(event)
                elif isinstance(event, Plan):
                    self._on_plan(event)
                elif isinstance(event, Exception):
                    self._log(f"Error: {event}")
                elif event is None:
                    self._on_finished()
        except queue.Empty:
            pass
        self.after(POLL_MS, self._poll_events)

    def _on_plan(self, plan: Plan) -> None:
        self.total_jobs = len(plan.jobs)
        for path in plan.ignored:
            self._log(f"Ignored {path} (missing or not a supported audio file)")
        if not plan.jobs:
            self._log("No FLAC/WAV files were found in the selected items.")
        else:
            self._log(
                f"Found {plan.convert_count} track(s) to convert, "
                f"{self.total_jobs - plan.convert_count} file(s) to copy."
            )
        self._update_status()

    def _on_result(self, result: Result) -> None:
        self.finished_jobs += 1
        self.counts[result.status] += 1
        output = Path(self.output_var.get())
        try:
            name = result.job.destination.relative_to(output)
        except ValueError:
            name = result.job.destination
        if result.status is Status.FAILED:
            self._log(f"FAILED  {name}\n        {result.job.source}\n        {result.message}")
        elif result.status is Status.DONE:
            self._log(f"✓  {name}")
        self.progress.set(self.finished_jobs / self.total_jobs if self.total_jobs else 0)
        self._update_status()

    def _update_status(self) -> None:
        parts = [f"{self.finished_jobs} / {self.total_jobs}"]
        if self.counts[Status.SKIPPED]:
            parts.append(f"{self.counts[Status.SKIPPED]} skipped")
        if self.counts[Status.FAILED]:
            parts.append(f"{self.counts[Status.FAILED]} failed")
        self.status_label.configure(text=" · ".join(parts))

    def _on_finished(self) -> None:
        cancelled = self.converter is not None and self.converter.cancelled
        self.worker = None
        self.converter = None
        self._set_running(False)
        done, skipped, failed = (
            self.counts[s] for s in (Status.DONE, Status.SKIPPED, Status.FAILED)
        )
        summary = f"{done} done, {skipped} skipped, {failed} failed"
        if cancelled:
            self.status_label.configure(text=f"Cancelled — {summary}")
            self._log(f"Cancelled. {summary}.")
            return
        if self.total_jobs:
            self.progress.set(1)
        self.status_label.configure(text=f"Finished — {summary}")
        self._log(f"Finished. {summary}.")
        if failed:
            messagebox.showwarning(
                "Conversion finished", f"{summary}.\n\nSee the log for details.", parent=self
            )
        elif self.total_jobs:
            messagebox.showinfo("Conversion finished", f"{summary}.", parent=self)

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for widget in (
            self.add_files_button,
            self.add_folder_button,
            self.clear_button,
            self.browse_button,
            self.output_entry,
            self.format_menu,
            self.mode_button,
            *self.checkboxes,
        ):
            widget.configure(state=state)
        mode = self._current_mode()
        self.quality_box.configure(
            state="disabled" if running else ("normal" if mode.custom_range else "readonly")
        )
        self.threads.configure_state(state)
        self.convert_button.configure(state=state if self.ffmpeg else "disabled")
        self.cancel_button.configure(state="normal" if running else "disabled")
        self.source_list.set_enabled(not running)

    # -------------------------------------------------------------------- log

    def _log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _on_close(self) -> None:
        if self.worker is not None:
            if not messagebox.askyesno(
                "Conversion running",
                "A conversion is still running. Cancel it and quit?",
                parent=self,
            ):
                return
            if self.converter:
                self.converter.cancel()
            self.worker.join(timeout=5)
        self.destroy()


def main() -> None:
    ctk.set_appearance_mode("system")
    app = MusicConverterApp()
    app.mainloop()
