from tkinter import filedialog
from tkfilebrowser import askopendirnames


def select_folder(self):
    folder_paths = askopendirnames()
    if folder_paths:
        folder_paths_str = "\n".join(folder_paths)
        self.folder_label.configure(text=folder_paths_str)
        self.selected_folders = folder_paths


def select_file(self):
    file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav *.flac")])
    if file_path:
        self.file_label.configure(text=file_path)


def select_output(self):
    output_path = filedialog.askdirectory()
    if output_path:
        self.output_label.configure(text=output_path)
