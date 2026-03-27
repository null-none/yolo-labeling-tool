"""
setup.py — build executable installers using PyInstaller.

Usage:
  python setup.py build          — builds a single executable into dist/
  python setup.py build --debug  — same, but keeps the console window open

Requirements:
  pip install pyinstaller

Output:
  dist/yolo-labeling-tool        (macOS)
  dist/yolo-labeling-tool.exe    (Windows)

Note: to create a full installer (.dmg / .msi) after building, see README.md.
"""

import sys
import subprocess
import argparse

APP_NAME = "yolo-labeling-tool"
ENTRY_POINT = "main.py"

# Extra data files copied into the bundle alongside the executable.
# Format: ("source", "destination_folder")  — "." means root of the bundle.
INCLUDE_FILES = [
    ("config.json", "."),
    ("start.png", "."),
    ("end.png", "."),
    ("create_file_list.py", "."),
]

def build(debug=False):
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                        # bundle everything into a single file
        f"--name={APP_NAME}",
    ]

    # Hide the console window on Windows for GUI apps
    if sys.platform == "win32" and not debug:
        cmd.append("--noconsole")

    # Add data files
    sep = ";" if sys.platform == "win32" else ":"
    for src, dst in INCLUDE_FILES:
        cmd += ["--add-data", f"{src}{sep}{dst}"]

    cmd.append(ENTRY_POINT)

    print(f"Running: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)
    print(f"\nBuild complete. Executable is in the dist/ directory.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build yolo-labeling-tool executable")
    parser.add_argument("command", choices=["build"], help="build the executable")
    parser.add_argument("--debug", action="store_true",
                        help="keep console window open (Windows only)")
    args = parser.parse_args()

    if args.command == "build":
        build(debug=args.debug)
