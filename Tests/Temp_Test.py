from Util import configure_dpi
from tkinter import filedialog
import tkinter as tk
import os


def openfile() -> str:
    return filedialog.askopenfilename(filetypes=[("All Files", "*.*"), ("Plain Text Files", "*.txt"),
                                                 ("Portable Network Graphics", "*.png"),
                                                 ("Bitmap Image File", "*.bmp"),
                                                 ("Portable Document Format", "*.pdf"),
                                                 ("Structured Query Language File", "*.sql"),
                                                 ("Hyper-Text Markup Language", "*.html"),
                                                 ("Cascading Style-Sheet", "*.css"),
                                                 ("Javascript Files", "*.js"), ("Windows PE Executable", "*.exe"),
                                                 ("MS-DOS Executable", "*.com"), ("Screensaver Program", "*.scr"),
                                                 ("Microsoft Installer Database", "*.msi"), ("Batch script", "*.bat"),
                                                 ("Dynamic linked library", "*.dll"), ("Icon File", "*.ico"),
                                                 ("Python Script", "*.py"), ("Python Script (no console)", "*.pyw"),
                                                 ("CPython Cache File", "*.pyc"), ("ZIP Archive", "*.zip"),
                                                 ("7-Zip Archive File", "*.7z")],
                                      initialdir=os.path.join(os.path.expanduser("~"), "Documents"),
                                      parent=root,
                                      title="Open")


def set_entry_path() -> None:
    text_var.set("\"{}\"".format(openfile()))


configure_dpi()
root = tk.Tk()
root.title("File-dialog Test")
root.geometry("350x350")
root.minsize(350, 350)
text_var = tk.StringVar(root)
row1 = tk.Frame(root, borderwidth=10)
tk.Label(row1, text="Filename: ").pack(side="left")
tk.Entry(row1, textvariable=text_var).pack(side="left")
tk.Button(row1, text="Browse...", command=set_entry_path).pack(side="left")
row1.pack()
root.mainloop()
