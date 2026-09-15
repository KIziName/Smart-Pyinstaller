## Smart-PyInstaller
· A simple GUI helper for building Python projects with PyInstaller.

## Features:
· Automatic discovery of .py scripts in the project folder (main.py is placed first in the list).
· AST analysis of source code and automatic detection of used libraries.
· Build into a single file (--onefile) with a configurable name.
· Apply an icon (Windows only, .ico).

## Build options:
· Show/hide the console window (--noconsole);
· Request administrator privileges (--uac-admin, Windows);
· Clean cache before build (--clean);
· Keep .spec and/or the build/ folder.
· Live log with color highlighting, progress bar, and a button to open dist/.
· Cross-platform: Windows, Linux.
· Properly terminates the PyInstaller child process when the window is closed.

## Requirements:
Python 3.8+
· `pip install pyinstaller`

## How to use:
· Specify the project folder (default — current directory). The “Rescan” button rescans the project.
· Entry script & EXE/ELF name — select the entry point and set the output file name.
· App icon — if needed, select a .ico file (available only on Windows).
· Build options — check the libraries to bundle and the build parameters.
· Click ▶ Build and watch the log.
· The finished file will appear in dist/. The 📂 Open dist/ button opens the folder.

## Notes:
· On Linux, the --noconsole flag is ignored, and --uac-admin is skipped — a corresponding warning will appear in the log.
· Icon formats other than .ico are not supported on Windows.
