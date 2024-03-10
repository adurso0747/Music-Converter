import subprocess
import os
from tkinter import messagebox
import shutil
import threading


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
            self.progress_step += self.iter_step
            self.progress.set(self.progress_step)


def start_conversion_process(self, output_path):
    self.progress.set(0)  # Reset progress bar to 0
    # Calculate total number of files to process
    total_files = sum(len(files) for folder_path in self.selected_folders for _, _, files in os.walk(folder_path))
    self.iter_step = 1 / total_files
    self.progress_step = 0

    # Lock for thread-safe updates to the processed_files and progress bar
    lock = threading.Lock()

    # Function to process each file and copy artwork within a folder
    def process_folder(folder_path):
        target_format = "mp3"
        bitrate_mode = self.bitrate_mode.get()
        bitrate_value = self.constant_bitrate_var.get() if bitrate_mode == "constant" else self.variable_bitrate_var.get() if bitrate_mode == "variable" else self.custom_bitrate_entry.get()

        # Correctly forming the final output path for each folder
        new_folder_name = os.path.basename(folder_path)
        final_output_path = os.path.join(output_path, new_folder_name)
        os.makedirs(final_output_path, exist_ok=True)  # Ensures directory exists

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith((".wav", ".flac")):
                    convert_file(self, os.path.join(root, file), target_format, bitrate_mode, bitrate_value,
                                      final_output_path)
                    with lock:
                        self.progress_step += self.iter_step
                        self.master.after(0, lambda: self.progress.set(self.progress_step))

        # Copy album artwork after processing all files in the folder
        copy_image_files(self, folder_path, final_output_path)

    # Create and start a thread for each folder
    threads = [threading.Thread(target=process_folder, args=(folder_path,)) for folder_path in
               self.selected_folders]
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # After all threads complete, show a completion message
    self.master.after(0, lambda: messagebox.showinfo("Conversion Complete!",
                                                     "All processing has completed successfully."))


def convert(self):
    if hasattr(self, 'selected_folders'):  # Check if multiple folders have been selected
        output_path = self.output_label.cget("text")
        if output_path == "No output location selected":
            messagebox.showerror("Error", "Please select an output location.")
            return

        # Start the conversion process in a new thread to keep UI responsive
        threading.Thread(target=start_conversion_process, args=(self, output_path,), daemon=True).start()
    else:
        messagebox.showerror("Error", "Please select one or more folders.")