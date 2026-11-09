"""把识别到的二维码放大显示在屏幕上，方便手机微信「扫一扫」。"""
import tkinter as tk

import cv2
from PIL import Image, ImageTk


def show(image, text, size=520, seconds=0, screen_y=60):
    """置顶显示一张二维码图；seconds=0 表示一直显示到手动关闭。"""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    picture = Image.fromarray(rgb).resize((size, size), Image.NEAREST)
    root = tk.Tk()
    root.title('微信扫一扫')
    root.attributes('-topmost', True)
    root.configure(bg='#111111')
    root.resizable(False, False)

    photo = ImageTk.PhotoImage(picture)
    label = tk.Label(root, image=photo, bg='white', bd=0)
    label.pack(padx=18, pady=(18, 8))

    tk.Label(root, text='手机微信「扫一扫」这个二维码', fg='white', bg='#111111',
             font=('Microsoft YaHei', 15, 'bold')).pack(pady=(4, 2))
    tk.Label(root, text=text if len(text) <= 70 else text[:67] + '...',
             fg='#66d9a8', bg='#111111', font=('Consolas', 10),
             wraplength=size + 20, justify='center').pack(padx=10, pady=(0, 14))

    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    root.geometry(f'+{x}+{screen_y}')

    if seconds:
        root.after(int(seconds * 1000), root.destroy)
    root.mainloop()
