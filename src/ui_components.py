import customtkinter as ctk
from customTkinterWidgets import FloatSpinbox
import tkinter as tk
import os
from file_utils import select_folder, select_file, select_output


def setup_file_selection(self):
    self.folder_frame = ctk.CTkFrame(self.main_frame)
    self.folder_frame.pack(pady=10, fill=tk.X)
    self.folder_label = ctk.CTkLabel(self.folder_frame, text="No folder selected", wraplength=400)
    self.folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    self.select_folder_btn = ctk.CTkButton(self.folder_frame, text="Select Folder", command=lambda: select_folder(self))
    self.select_folder_btn.pack(side=tk.RIGHT, padx=5)

    self.file_frame = ctk.CTkFrame(self.main_frame)
    self.file_frame.pack(pady=10, fill=tk.X)
    self.file_label = ctk.CTkLabel(self.file_frame, text="No file selected", wraplength=400)
    self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    self.select_file_btn = ctk.CTkButton(self.file_frame, text="Select File", command=lambda: select_file(self))
    self.select_file_btn.pack(side=tk.RIGHT, padx=5)


def setup_output_selection(self):
    self.output_frame = ctk.CTkFrame(self.main_frame)
    self.output_frame.pack(pady=10, fill=tk.X)
    self.output_label = ctk.CTkLabel(self.output_frame, text="No output location selected")
    self.output_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    self.select_output_btn = ctk.CTkButton(self.output_frame, text="Select Output", command=lambda: select_output(self))
    self.select_output_btn.pack(side=tk.RIGHT, padx=5)


def setup_bitrate_mode_selection(self):
    self.bitrate_mode_label = ctk.CTkLabel(self.main_frame, text="Bitrate Mode", width=10, height=10)
    self.bitrate_mode_label.pack(anchor="w")
    self.bitrate_mode_frame = ctk.CTkFrame(self.main_frame)
    self.bitrate_mode_frame.pack(fill=tk.X, pady=10)
    modes = [("Constant Bitrate", "constant"), ("Variable Bitrate", "variable"), ("Custom", "custom")]
    for mode, value in modes:
        ctk.CTkRadioButton(self.bitrate_mode_frame, text=mode, value=value, variable=self.bitrate_mode,
                           command=update_bitrate_options_visibility(self)).pack(side=tk.TOP, anchor="w")


def setup_bitrate_options(self):
    self.options_frame = ctk.CTkFrame(self.main_frame)
    self.options_frame.pack(pady=10, fill=tk.X)
    self.options_label = ctk.CTkLabel(self.options_frame, text="Options:")
    self.options_label.pack(side=tk.LEFT, padx=5)
    self.constant_bitrate_var = tk.StringVar(value="320")
    self.constant_bitrate_options = ctk.CTkComboBox(self.options_frame, variable=self.constant_bitrate_var,
                                                    values=["128", "192", "256", "320"], state="readonly")
    self.variable_bitrate_var = tk.StringVar(value="V0")
    self.variable_bitrate_options = ctk.CTkComboBox(self.options_frame, variable=self.variable_bitrate_var,
                                                    values=["V0", "V2"], state="readonly")
    self.custom_bitrate_entry = ctk.CTkEntry(self.options_frame)
    self.custom_bitrate_entry.insert(0, "192")  # Default value
    update_bitrate_options_visibility(self)


def setup_thread_selection(self):
    self.thread_frame = ctk.CTkFrame(self.main_frame)
    self.thread_frame.pack(pady=10, fill=tk.X)
    default_threads = os.cpu_count() or 1  # Default to CPU count or 1 if unavailable
    self.thread_label = ctk.CTkLabel(self.thread_frame, text="Number of Threads:")
    self.thread_label.pack(side=tk.LEFT, padx=5)

    self.thread_spinbox = FloatSpinbox(self.thread_frame, width=150, step_size=1, from_num=1, to_num=default_threads)
    self.thread_spinbox.set(default_threads)  # Set the default value
    self.thread_spinbox.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=5)


def update_bitrate_options_visibility(self):
    if self.bitrate_mode.get() == "constant":
        self.constant_bitrate_options.pack(pady=5)
        self.variable_bitrate_options.pack_forget()
        self.custom_bitrate_entry.pack_forget()
    elif self.bitrate_mode.get() == "variable":
        self.constant_bitrate_options.pack_forget()
        self.variable_bitrate_options.pack(pady=5)
        self.custom_bitrate_entry.pack_forget()
    else:  # Custom
        self.constant_bitrate_options.pack_forget()
        self.variable_bitrate_options.pack_forget()
        self.custom_bitrate_entry.pack(pady=5)
