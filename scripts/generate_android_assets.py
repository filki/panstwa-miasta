#!/usr/bin/env python3
"""Generate Android icon & splash assets from static/icons/icon.svg."""

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG_ICON = ROOT / "static" / "icons" / "icon.svg"
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"

# --- Adaptive icon foreground (transparent "PM" on gradient mask) ---
# ImageMagick magick command
MAGICK = "magick"

DENSITIES = {
    "mdpi": 1.0,
    "hdpi": 1.5,
    "xhdpi": 2.0,
    "xxhdpi": 3.0,
    "xxxhdpi": 4.0,
}

# Legacy icon sizes (dp → px at given density)
LEGACY_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}

# Adaptive icon foreground: safe zone 66dp diameter (inner 72dp canvas for padding)
ADAPTIVE_BASE = 432  # 108dp * 4 (xxxhdpi)
ADAPTIVE_CANVAS = 432
ADAPTIVE_SAFE_RADIUS = 66  # dp

# Splash screen: 1280×720 landscape, 720×1280 portrait
SPLASH_SIZES = {
    "land-hdpi": (800, 480),
    "land-mdpi": (480, 320),
    "land-xhdpi": (1280, 720),
    "land-xxhdpi": (1920, 1080),
    "land-xxxhdpi": (2560, 1440),
    "port-hdpi": (480, 800),
    "port-mdpi": (320, 480),
    "port-xhdpi": (720, 1280),
    "port-xxhdpi": (1080, 1920),
    "port-xxxhdpi": (1440, 2560),
}


def run(cmd):
    print(f"  {' '.join(cmd)}")
    subprocess.run(cmd, check=True, capture_output=True)


def generate_icons():
    print("=== Generating adaptive icon foregrounds ===")
    for density, scale in DENSITIES.items():
        size = int(ADAPTIVE_CANVAS * scale)
        out = ANDROID_RES / f"mipmap-{density}" / "ic_launcher_foreground.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        # Render icon centered in adaptive canvas
        run(
            [
                MAGICK,
                "-background",
                "none",
                "-density",
                "300",
                str(SVG_ICON),
                "-resize",
                f"{int(size * 0.66)}x{int(size * 0.66)}",
                "-gravity",
                "center",
                "-extent",
                f"{size}x{size}",
                str(out),
            ]
        )

    print("=== Generating legacy icons ===")
    for density, size in LEGACY_SIZES.items():
        out = ANDROID_RES / f"mipmap-{density}" / "ic_launcher.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        run(
            [
                MAGICK,
                "-background",
                "none",
                "-density",
                "300",
                str(SVG_ICON),
                "-resize",
                f"{size}x{size}",
                str(out),
            ]
        )
        # round version = same as regular for now
        round_out = ANDROID_RES / f"mipmap-{density}" / "ic_launcher_round.png"
        run(["cp", str(out), str(round_out)])


def generate_splash():
    print("=== Generating splash screens ===")
    splash_dir = ROOT / "android" / "app" / "src" / "main" / "res"
    for key, (w, h) in SPLASH_SIZES.items():
        out = splash_dir / f"drawable-{key}" / "splash.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        # Solid #f2f6ff background with centered icon
        icon_size = min(w, h) // 3
        run(
            [
                MAGICK,
                "-size",
                f"{w}x{h}",
                f"xc:#f2f6ff",
                "-gravity",
                "center",
                str(SVG_ICON),
                "-density",
                "300",
                "-resize",
                f"{icon_size}x{icon_size}",
                "-composite",
                str(out),
            ]
        )
    # Also a default splash for drawable/
    default_out = splash_dir / "drawable" / "splash.png"
    default_out.parent.mkdir(parents=True, exist_ok=True)
    default_w, default_h = 480, 800
    default_icon = min(default_w, default_h) // 3
    run(
        [
            MAGICK,
            "-size",
            f"{default_w}x{default_h}",
            "xc:#f2f6ff",
            "-gravity",
            "center",
            str(SVG_ICON),
            "-density",
            "300",
            "-resize",
            f"{default_icon}x{default_icon}",
            "-composite",
            str(default_out),
        ]
    )


if __name__ == "__main__":
    generate_icons()
    generate_splash()
    print("=== Done ===")
