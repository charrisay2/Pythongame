# -*- coding: utf-8 -*-
"""
Build game Soul Survivors thành 1 file .exe duy nhất bằng PyInstaller.

Cách dùng (Windows):
    python build_exe.py

Kết quả:
    dist/SoulSurvivors.exe   (file duy nhất, chạy được trên máy không cài Python)
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "SoulSurvivors"
MAIN = os.path.join(HERE, "main.py")


def run(cmd, **kw):
    print("[>] " + " ".join(cmd))
    subprocess.check_call(cmd, cwd=HERE, **kw)


def ensure_package(import_name, pip_name=None):
    pip_name = pip_name or import_name
    try:
        __import__(import_name)
        print("[ok] %s đã có sẵn" % pip_name)
    except ImportError:
        print("[..] Chưa có %s -> đang cài..." % pip_name)
        run([sys.executable, "-m", "pip", "install", "--upgrade", pip_name])


def make_icon():
    """Tạo icon.ico từ pixel art (cần Pillow). Trả về đường dẫn hoặc None."""
    try:
        from PIL import Image
    except ImportError:
        print("[!] Không có Pillow -> bỏ qua bước tạo icon")
        return None

    art = [
        "................",
        ".....######.....",
        "...##########...",
        "..############..",
        "..############..",
        ".####kk##kk####.",
        ".####kk##kk####.",
        ".##############.",
        ".##############.",
        ".##############.",
        ".##############.",
        ".##############.",
        ".##############.",
        ".##.##.##.##.##.",
        "................",
        "................",
    ]
    colors = {"#": (246, 248, 255, 255), "k": (40, 38, 60, 255)}
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            c = colors.get(ch)
            if c:
                img.putpixel((x, y), c)

    big = img.resize((256, 256), Image.NEAREST)
    path = os.path.join(HERE, "icon.ico")
    big.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("[ok] Đã tạo %s" % path)
    return path


def main():
    if not os.path.exists(MAIN):
        print("[x] Không tìm thấy main.py cạnh file build_exe.py")
        return 1

    ensure_package("pygame")
    ensure_package("PyInstaller", "pyinstaller")

    icon = make_icon()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", HERE,
    ]
    if icon:
        cmd += ["--icon", icon]
    cmd.append(MAIN)

    print("\n=== BẮT ĐẦU BUILD (có thể mất 1-3 phút) ===")
    run(cmd)

    exe = os.path.join(HERE, "dist", APP_NAME + ".exe")
    print("\n=== XONG ===")
    if os.path.exists(exe):
        size = os.path.getsize(exe) / (1024.0 * 1024.0)
        print("File exe: %s  (%.1f MB)" % (exe, size))
        print("Copy file này sang máy khác là chạy được, không cần cài Python.")
    else:
        print("Không thấy file exe, xem log phía trên để biết lỗi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
