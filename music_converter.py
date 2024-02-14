import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
from tkfilebrowser import askopendirnames
import shutil
import threading

class MusicConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Music Converter")
        master.geometry('400x400')  # Adjusted size for additional controls

        # Initialize ttk style
        style = ttk.Style()
        style.theme_use('clam')

        # Bitrate Mode Selection
        self.bitrate_mode = tk.StringVar(value="constant")

        # Main frame
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Setup UI Components
        self.setup_file_selection()
        self.setup_output_selection()
        self.setup_bitrate_mode_selection()
        self.setup_bitrate_options()

        # Convert Button
        self.convert_btn = ttk.Button(master, text="Convert", command=self.convert)
        self.convert_btn.pack(pady=20)
        # Progress Bar
        self.progress = ttk.Progressbar(master, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(pady=20)

        # Thread Frame for Number of Threads Selection
        self.thread_frame = ttk.Frame(self.main_frame)  # Ensure this line is before its use
        self.thread_frame.pack(pady=10, fill=tk.X)
        self.setup_thread_selection()

    def setup_file_selection(self):
        # Folder Selection
        self.folder_frame = ttk.Frame(self.main_frame)
        self.folder_frame.pack(pady=10, fill=tk.X)
        self.folder_label = ttk.Label(self.folder_frame, text="No folder selected")
        self.folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.select_folder_btn = ttk.Button(self.folder_frame, text="Select Folder", command=self.select_folder)
        self.select_folder_btn.pack(side=tk.RIGHT, padx=5)

        # File Selection
        self.file_frame = ttk.Frame(self.main_frame)
        self.file_frame.pack(pady=10, fill=tk.X)
        self.file_label = ttk.Label(self.file_frame, text="No file selected")
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.select_file_btn = ttk.Button(self.file_frame, text="Select File", command=self.select_file)
        self.select_file_btn.pack(side=tk.RIGHT, padx=5)

    def setup_output_selection(self):
        # Output Directory Selection
        self.output_frame = ttk.Frame(self.main_frame)
        self.output_frame.pack(pady=10, fill=tk.X)
        self.output_label = ttk.Label(self.output_frame, text="No output location selected")
        self.output_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.select_output_btn = ttk.Button(self.output_frame, text="Select Output", command=self.select_output)
        self.select_output_btn.pack(side=tk.RIGHT, padx=5)

    def setup_bitrate_mode_selection(self):
        self.bitrate_mode_frame = ttk.LabelFrame(self.main_frame, text="Bitrate Mode")
        self.bitrate_mode_frame.pack(pady=10, fill=tk.X)
        modes = [("Constant Bitrate", "constant"), ("Variable Bitrate", "variable"), ("Custom", "custom")]
        for mode, value in modes:
            ttk.Radiobutton(self.bitrate_mode_frame, text=mode, value=value, variable=self.bitrate_mode, command=self.update_bitrate_options_visibility).pack(side=tk.LEFT, expand=True)

    def setup_bitrate_options(self):
        self.constant_bitrate_var = tk.StringVar(value="320")
        self.constant_bitrate_options = ttk.Combobox(self.main_frame, textvariable=self.constant_bitrate_var, values=["128", "192", "256", "320"], state="readonly")
        self.variable_bitrate_var = tk.StringVar(value="V0")
        self.variable_bitrate_options = ttk.Combobox(self.main_frame, textvariable=self.variable_bitrate_var, values=["V0", "V2"], state="readonly")
        self.custom_bitrate_entry = ttk.Entry(self.main_frame)
        self.custom_bitrate_entry.insert(0, "192")  # Default value
        self.update_bitrate_options_visibility()

    def setup_thread_selection(self):
        default_threads = os.cpu_count() or 1  # Default to CPU count or 1 if unavailable
        self.thread_label = ttk.Label(self.thread_frame, text="Number of Threads:")
        self.thread_label.pack(side=tk.LEFT, padx=5)

        self.thread_spinbox = ttk.Spinbox(self.thread_frame, from_=1, to=2 * default_threads, wrap=True)
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

    def select_folder(self):
        folder_paths = askopendirnames()  # Use tkfilebrowser to select multiple folders
        if folder_paths:
            folder_paths_str = "; ".join(folder_paths)  # Join selected folder paths into a single string
            self.folder_label.config(text=folder_paths_str)
            self.selected_folders = folder_paths  # Store the list of selected folders for later processing

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav *.flac")])
        if file_path:
            self.file_label.config(text=file_path)

    def select_output(self):
        output_path = filedialog.askdirectory()
        if output_path:
            self.output_label.config(text=output_path)

    def convert_file(self, file_path, target_format, bitrate_mode, bitrate_value, output_path):
        base, ext = os.path.splitext(os.path.basename(file_path))
        output_file = os.path.join(output_path, f"{base}.{target_format}")
        cmd = ['ffmpeg', '-y', '-i', file_path]

        if bitrate_mode == "constant":
            cmd += ['-b:a', bitrate_value + 'k', '-acodec', 'libmp3lame']
        elif bitrate_mode == "variable":
            if bitrate_value == "V0":
                cmd += ['-q:a', '0', '-acodec', 'libmp3lame']
            elif bitrate_value == "V2":
                cmd += ['-q:a', '2', '-acodec', 'libmp3lame']
        else:  # custom
            cmd += ['-b:a', bitrate_value + 'k', '-acodec', 'libmp3lame']
        cmd.append(output_file)

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Conversion Failed", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def copy_image_files(self, source_folder, destination_folder):
        """
        Copy image files from the source folder to the destination folder.
        """
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
        for item in os.listdir(source_folder):
            if any(item.lower().endswith(ext) for ext in image_extensions):
                source_path = os.path.join(source_folder, item)
                destination_path = os.path.join(destination_folder, item)
                shutil.copy(source_path, destination_path)
                self.progress["value"] += 1

    def start_conversion_process(self, output_path):
        total_files = sum(len(files) for folder_path in self.selected_folders for _, _, files in os.walk(folder_path))
        self.progress["maximum"] = total_files
        self.progress["value"] = 0

        for folder_path in self.selected_folders:
            target_format = "mp3"
            bitrate_mode = self.bitrate_mode.get()
            bitrate_value = self.constant_bitrate_var.get() if bitrate_mode == "constant" else self.variable_bitrate_var.get() if bitrate_mode == "variable" else self.custom_bitrate_entry.get()

            new_folder_name = os.path.basename(folder_path)
            final_output_path = os.path.join(output_path, new_folder_name)
            if not os.path.exists(final_output_path):
                os.makedirs(final_output_path)

            for file in os.listdir(folder_path):
                if file.endswith(".wav") or file.endswith(".flac"):
                    self.convert_file(os.path.join(folder_path, file), target_format, bitrate_mode, bitrate_value,
                                      final_output_path)
                    self.progress["value"] += 1
                    self.master.update_idletasks()  # Ensure UI updates are processed

            # Copy album artwork
            self.copy_image_files(folder_path, final_output_path)

        # After all processing is complete show a completion message
        def on_completion():
            messagebox.showinfo("Conversion Complete!", "All processing has completed successfully.")
        self.master.after(0, on_completion)

    def convert(self):
        if hasattr(self, 'selected_folders'):  # Check if multiple folders have been selected
            output_path = self.output_label.cget("text")
            if output_path == "No output location selected":
                messagebox.showerror("Error", "Please select an output location.")
                return

            # Start the conversion process in a new thread to keep UI responsive
            threading.Thread(target=self.start_conversion_process, args=(output_path,), daemon=True).start()
        else:
            messagebox.showerror("Error", "Please select one or more folders.")

if __name__ == "__main__":
    root = tk.Tk()
    app = MusicConverterApp(root)
    root.mainloop()
