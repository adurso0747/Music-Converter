from ui_components import setup_file_selection, setup_output_selection, setup_thread_selection, setup_bitrate_options, setup_bitrate_mode_selection
import tkinter as tk
import customtkinter as ctk
from conversion_utils import convert


class MusicConverterApp:
    def __init__(self, master):
        self.master = master
        self.main_frame = ctk.CTkFrame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.bitrate_mode = tk.StringVar(value="constant")

        self.convert_btn = ctk.CTkButton(master, text="Convert", command=lambda: convert(self))
        self.convert_btn.pack(pady=20)
        self.progress = ctk.CTkProgressBar(master, orientation="horizontal", width=300, mode="determinate")
        self.progress.pack(pady=20)
        self.progress.set(0)

        self.progress_step = 1
        self.iter_step = 1

        self.setup_ui_components()

    def setup_ui_components(self):
        self.master.title("Music Converter")
        self.master.geometry('600x500')
        self.master.minsize(600, 500)
        setup_file_selection(self)
        setup_output_selection(self)
        setup_thread_selection(self)
        setup_bitrate_options(self)
        setup_bitrate_mode_selection(self)
