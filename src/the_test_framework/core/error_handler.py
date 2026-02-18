import tkinter as tk
import traceback
from tkinter import messagebox
from logging import getLogger


def error_handler(exc: BaseException):
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    getLogger(__name__).exception("error handler handles", exc_info=exc)
    root = tk.Tk()
    root.withdraw()
    root.lift()
    root.attributes("-topmost", True)
    root.update_idletasks()
    message = f"Aborting due to an unexpected error:\n\n{tb_str}"
    messagebox.showerror("shit hit the fan!", message, parent=root)
    root.destroy()
