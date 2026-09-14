import ast
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser

from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

IGNORED_DIRS = {'.git', 'venv', '.venv', 'env', '.env', 'build', 'dist',
                '__pycache__', 'site-packages', '.idea', '.vscode'}

APP_NAME = "Smart-Pyinstaller"
APP_VERSION = "V1.0"
APP_AUTHOR = "KiziName"
APP_GITHUB = "https://github.com/KIziName/Smart-PyInstaller"

WINDOW_TITLE = APP_NAME
WINDOW_GEOMETRY = "900x800"
WINDOW_MIN_WIDTH = 820
WINDOW_MIN_HEIGHT = 700

POLL_INTERVAL_MS = 90
PROGRESS_INTERVAL_MS = 25
PROGRESS_LENGTH = 220

LOG_FONT = ("Consolas", 9)
LOG_HEIGHT = 16
BOLD_FONT = ("", 9, "bold")

TAG_INFO = "info"
TAG_OK = "ok"
TAG_WARN = "warn"
TAG_ERROR = "error"
TAG_MUTED = "muted"

COLOR_INFO = "#1565c0"
COLOR_OK = "#2e7d32"
COLOR_WARN = "#ef6c00"
COLOR_ERROR = "#c62828"
COLOR_MUTED = "#616161"
COLOR_HINT = "#666"
COLOR_LABEL = "#555"
COLOR_LINK = "#1565c0"

PREFIX_INFO = "[i]"
PREFIX_OK = "[✓]"
PREFIX_WARN = "[!]"
PREFIX_ERROR = "[✗]"

TAG_COLORS = {
    TAG_INFO: COLOR_INFO,
    TAG_OK: COLOR_OK,
    TAG_WARN: COLOR_WARN,
    TAG_ERROR: COLOR_ERROR,
    TAG_MUTED: COLOR_MUTED,
}

TAG_PREFIX = {
    TAG_INFO: PREFIX_INFO,
    TAG_OK: PREFIX_OK,
    TAG_WARN: PREFIX_WARN,
    TAG_ERROR: PREFIX_ERROR,
}

MODULES = (
    ('numpy', 'Bundle NumPy'),
    ('customtkinter', 'Bundle customtkinter'),
    ('scipy', 'Bundle SciPy'),
    ('wx', 'Bundle wxPython'),
    ('kivy', 'Bundle Kivy'),
    ('matplotlib', 'Bundle matplotlib'),
    ('cv2', 'Bundle OpenCV'),
    ('sklearn', 'Bundle scikit-learn'),
    ('PIL', 'Bundle Pillow (PIL)'),
    ('reportlab', 'Bundle ReportLab'),
)

MODULES_TO_DETECT = frozenset(name for name, _ in MODULES)

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'

ICON_SUPPORTED = IS_WINDOWS
ICON_FILETYPES = [("Icon files", "*.ico"), ("All files", "*.*")] if ICON_SUPPORTED else []
ACCEPTED_ICON_SUFFIXES = {'.ico'} if ICON_SUPPORTED else set()
ICON_HINT = ".ico (Windows only)"


def _resolve_self_name() -> str:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).name
    return Path(__file__).name


SELF_NAME = _resolve_self_name()


@dataclass
class BuildOptions:
    console: bool = False
    admin: bool = False
    keep_spec: bool = False
    keep_build: bool = False
    clean_build: bool = False
    modules: dict = field(default_factory=dict)


def find_used_modules(base_dir: Path, names: frozenset) -> set:
    found: set = set()

    for py_file in base_dir.rglob("*.py"):
        rel_parts = py_file.relative_to(base_dir).parts
        if any(part in IGNORED_DIRS for part in rel_parts[:-1]):
            continue
        if py_file.name == SELF_NAME:
            continue

        try:
            source = py_file.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, ValueError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = (alias.name.split('.', 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    continue
                roots = (node.module.split('.', 1)[0],)
            else:
                continue
            found.update(root for root in roots if root in names)

    return found


def cleanup(base_dir: Path, exe_name: str, keep_spec: bool, keep_build: bool):
    if not keep_build:
        shutil.rmtree(base_dir / "build", ignore_errors=True)
    if not keep_spec:
        (base_dir / f"{exe_name}.spec").unlink(missing_ok=True)


class SmartPyInstallerGUI:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self.base_dir = Path.cwd().resolve()
        self.build_in_progress = False
        self._proc: Optional[subprocess.Popen] = None
        self._proc_lock = threading.Lock()
        self._closing = False
        self.pyinstaller_available = False

        self.log_queue: queue.Queue = queue.Queue()

        self.folder_var = tk.StringVar(value=str(self.base_dir))
        self.script_var = tk.StringVar()
        self.exe_name_var = tk.StringVar()
        self.icon_var = tk.StringVar()
        self.module_vars = {name: tk.BooleanVar(value=False) for name, _ in MODULES}
        self.console_var = tk.BooleanVar(value=False)
        self.admin_var = tk.BooleanVar(value=False)
        self.clean_build_var = tk.BooleanVar(value=False)
        self.keep_spec_var = tk.BooleanVar(value=False)
        self.keep_build_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._scan_project()

        self.root.after(POLL_INTERVAL_MS, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        folder_frame = ttk.LabelFrame(main, text="Project folder", padding=8)
        folder_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Entry(folder_frame, textvariable=self.folder_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        self.browse_btn = ttk.Button(
            folder_frame, text="Browse…", command=self._choose_folder)
        self.browse_btn.pack(side=tk.LEFT, padx=(6, 0))
        self.rescan_btn = ttk.Button(
            folder_frame, text="Rescan", command=self._scan_project)
        self.rescan_btn.pack(side=tk.LEFT, padx=(6, 0))

        script_frame = ttk.LabelFrame(
            main, text="Entry script & EXE/ELF name", padding=8)
        script_frame.pack(fill=tk.X, pady=(0, 8))
        self.script_combo = ttk.Combobox(
            script_frame, textvariable=self.script_var, state="readonly")
        self.script_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(script_frame, text="EXE/ELF name:").pack(
            side=tk.LEFT, padx=(10, 4))
        ttk.Entry(script_frame, textvariable=self.exe_name_var,
                  width=22).pack(side=tk.LEFT)

        icon_frame = ttk.LabelFrame(main, padding=8)
        icon_frame.pack(fill=tk.X, pady=(0, 8))
        head = tk.Frame(icon_frame)
        head.pack(anchor=tk.W, padx=2, pady=(0, 6))
        tk.Label(head, text="App icon").pack(side=tk.LEFT)
        tk.Label(head, text=f"  [{ICON_HINT}]",
                 foreground=COLOR_HINT).pack(side=tk.LEFT)
        row = tk.Frame(icon_frame)
        row.pack(fill=tk.X)
        icon_entry = ttk.Entry(row, textvariable=self.icon_var)
        icon_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        icon_browse = ttk.Button(
            row, text="Browse…", command=self._choose_icon)
        icon_browse.pack(side=tk.LEFT, padx=(6, 0))
        icon_clear = ttk.Button(
            row, text="Clear", command=lambda: self.icon_var.set(""))
        icon_clear.pack(side=tk.LEFT, padx=(6, 0))
        if not ICON_SUPPORTED:
            for widget in (icon_entry, icon_browse, icon_clear):
                widget.configure(state=tk.DISABLED)

        opts = ttk.LabelFrame(main, text="Build options", padding=8)
        opts.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(opts, text="Libraries", font=BOLD_FONT).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(0, 4))
        ttk.Label(opts, text="Output files", font=BOLD_FONT).grid(
            row=0, column=2, sticky=tk.W, padx=6, pady=(0, 4))
        ttk.Label(opts, text="Application", font=BOLD_FONT).grid(
            row=0, column=3, sticky=tk.W, padx=6, pady=(0, 4))

        half = (len(MODULES) + 1) // 2
        for i, (name, label) in enumerate(MODULES):
            ttk.Checkbutton(opts, text=label,
                            variable=self.module_vars[name]).grid(
                row=i % half + 1, column=i // half,
                sticky=tk.W, padx=(6, 24), pady=2)

        for text, var, r, c in (
            ("Keep .spec file", self.keep_spec_var, 1, 2),
            ("Keep build/ folder", self.keep_build_var, 2, 2),
            ("Show console window  (--noconsole: not for Linux)",
             self.console_var, 1, 3),
            ("Request admin privileges", self.admin_var, 2, 3),
            ("Clean before build (--clean)", self.clean_build_var, 3, 3),
        ):
            ttk.Checkbutton(opts, text=text, variable=var).grid(
                row=r, column=c, sticky=tk.W, padx=6, pady=2)

        self.detected_label = ttk.Label(
            opts, text="Detected modules: —", foreground=COLOR_LABEL)
        self.detected_label.grid(row=half + 1, column=0, columnspan=4,
                                 sticky=tk.W, padx=6, pady=(8, 0))

        bar = ttk.Frame(main)
        bar.pack(fill=tk.X, pady=(0, 8))
        self.build_btn = ttk.Button(
            bar, text="▶  Build", command=self._start_build)
        self.build_btn.pack(side=tk.LEFT)
        ttk.Button(bar, text="📂  Open dist/",
                   command=self._open_dist).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bar, text="Clear log",
                   command=self._clear_log).pack(side=tk.LEFT, padx=6)
        ttk.Button(bar, text="About",
                   command=self._show_about).pack(side=tk.LEFT, padx=(0, 6))
        self.progress = ttk.Progressbar(
            bar, mode="indeterminate", length=PROGRESS_LENGTH)
        self.progress.pack(side=tk.RIGHT, padx=4)

        log_frame = ttk.LabelFrame(main, text="Log", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log = scrolledtext.ScrolledText(
            log_frame, height=LOG_HEIGHT, wrap=tk.WORD,
            state=tk.DISABLED, font=LOG_FONT)
        self.log.pack(fill=tk.BOTH, expand=True)
        for tag, color in TAG_COLORS.items():
            self.log.tag_config(tag, foreground=color)

    def _show_about(self):
        win = tk.Toplevel(self.root)
        win.title("About")
        win.transient(self.root)
        win.resizable(False, False)

        body = ttk.Frame(win, padding=16)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text=APP_NAME, font=("", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(body, text=f"Version {APP_VERSION}").pack(
            anchor=tk.W, pady=(2, 10))
        ttk.Label(body, text=f"Author: {APP_AUTHOR}").pack(anchor=tk.W)
        ttk.Label(body, text="License: MIT").pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(body, text="GitHub:").pack(anchor=tk.W)
        link = ttk.Label(body, text=APP_GITHUB,
                         foreground=COLOR_LINK, cursor="hand2")
        link.pack(anchor=tk.W, pady=(0, 12))
        link.bind("<Button-1>", lambda _e: webbrowser.open(APP_GITHUB))
        ttk.Button(body, text="Close", command=win.destroy).pack(anchor=tk.E)

        win.update_idletasks()
        px = self.root.winfo_rootx() + (
            self.root.winfo_width() - win.winfo_width()) // 2
        py = self.root.winfo_rooty() + (
            self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(px, 0)}+{max(py, 0)}")
        win.grab_set()
        win.focus_set()

    def _log(self, msg: str, tag: str = TAG_MUTED):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n", tag)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _q_tagged(self, msg: str, tag: str):
        self.log_queue.put((f"{TAG_PREFIX[tag]} {msg}", tag))

    def q_info(self, msg):  self._q_tagged(msg, TAG_INFO)
    def q_ok(self, msg):    self._q_tagged(msg, TAG_OK)
    def q_warn(self, msg):  self._q_tagged(msg, TAG_WARN)
    def q_error(self, msg): self._q_tagged(msg, TAG_ERROR)

    def _poll_queue(self):
        if self._closing:
            return
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item is None:
                    self._set_busy(False)
                else:
                    self._log(*item)
        except queue.Empty:
            pass
        if not self._closing:
            try:
                self.root.after(POLL_INTERVAL_MS, self._poll_queue)
            except tk.TclError:
                pass

    def _drain_queue(self):
        try:
            while True:
                self.log_queue.get_nowait()
        except queue.Empty:
            pass

    def _clear_log(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _choose_folder(self):
        if self.build_in_progress:
            return
        folder = filedialog.askdirectory(
            initialdir=str(self.base_dir), title="Choose project folder")
        if folder:
            self.folder_var.set(folder)
            self._scan_project()

    def _choose_icon(self):
        if not ICON_SUPPORTED:
            return
        path = filedialog.askopenfilename(
            initialdir=str(self.base_dir),
            title="Choose icon file",
            filetypes=ICON_FILETYPES,
        )
        if not path:
            return
        if Path(path).suffix.lower() not in ACCEPTED_ICON_SUFFIXES:
            messagebox.showwarning(
                "Unsupported icon format",
                "Supported on this platform: "
                + ", ".join(sorted(ACCEPTED_ICON_SUFFIXES)),
            )
            return
        self.icon_var.set(path)

    def _open_dist(self):
        dist_dir = self.base_dir / "dist"
        if not dist_dir.exists():
            messagebox.showinfo(
                "dist/ not found",
                f"Folder does not exist yet:\n{dist_dir}",
            )
            return
        try:
            if IS_WINDOWS:
                os.startfile(str(dist_dir))
            elif IS_MACOS:
                subprocess.Popen(["open", str(dist_dir)])
            else:
                subprocess.Popen(["xdg-open", str(dist_dir)])
        except Exception as e:
            messagebox.showerror("Cannot open folder", str(e))

    def _on_close(self):
        if self.build_in_progress:
            if not messagebox.askyesno(
                "Build in progress",
                "A build is currently running.\nStop PyInstaller and quit?",
            ):
                return
            self._closing = True
            self._terminate_proc()
        else:
            self._closing = True
        self.root.destroy()

    def _terminate_proc(self):
        with self._proc_lock:
            proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=5,
                )
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

    def _scan_project(self):
        if self.build_in_progress:
            return

        self.base_dir = Path(self.folder_var.get()).resolve()
        self.icon_var.set("")

        try:
            import PyInstaller  
            self.pyinstaller_available = True
        except ImportError:
            self.pyinstaller_available = False

        if not self.pyinstaller_available:
            self.script_combo["values"] = []
            self.script_var.set("")
            self.exe_name_var.set("")
            for var in self.module_vars.values():
                var.set(False)
            self.build_btn.configure(state=tk.DISABLED)
            self.detected_label.configure(
                text="⚠ PyInstaller is not installed — run: pip install pyinstaller",
                foreground=COLOR_ERROR,
            )
            self._log(f"{PREFIX_ERROR} PyInstaller is not installed — "
                      "run: pip install pyinstaller", TAG_ERROR)
            self._log("Build button disabled.", TAG_MUTED)
            return

        self.detected_label.configure(foreground=COLOR_LABEL)
        self.build_btn.configure(state=tk.NORMAL)

        scripts = [f for f in self.base_dir.glob("*.py") if f.name != SELF_NAME]
        if not scripts:
            self.script_combo["values"] = []
            self.script_var.set("")
            self.exe_name_var.set("")
            self.detected_label.configure(
                text="Detected modules: —", foreground=COLOR_LABEL)
            for var in self.module_vars.values():
                var.set(False)
            return

        mains = [f for f in scripts if f.stem.lower() == "main"]
        ordered = mains + [f for f in scripts if f not in mains]
        names = [f.name for f in ordered]

        self.script_combo["values"] = names
        self.script_var.set(names[0])
        self.exe_name_var.set(Path(names[0]).stem)

        used = find_used_modules(self.base_dir, MODULES_TO_DETECT)
        self.detected_label.configure(
            text=f"Detected modules: {', '.join(sorted(used)) if used else '—'}",
            foreground=COLOR_LABEL,
        )
        for name, var in self.module_vars.items():
            var.set(name in used)

        self._log(f"Project: {self.base_dir}", TAG_MUTED)
        self._log(f"Scripts found: {len(names)}", TAG_MUTED)

    def _set_busy(self, busy: bool):
        self.build_in_progress = busy

        state = tk.DISABLED if busy else tk.NORMAL
        self.browse_btn.configure(state=state)
        self.rescan_btn.configure(state=state)

        if busy:
            self.build_btn.configure(state=tk.DISABLED)
            self.progress.start(PROGRESS_INTERVAL_MS)
        else:
            self.progress.stop()
            self.build_btn.configure(
                state=tk.NORMAL if self.pyinstaller_available else tk.DISABLED)

    def _start_build(self):
        if self.build_in_progress:
            return

        if not self.pyinstaller_available:
            self._log(f"{PREFIX_ERROR} PyInstaller is not installed — "
                      "cannot start build.", TAG_ERROR)
            return

        script_name = self.script_var.get()
        if not script_name:
            messagebox.showwarning("No script",
                                   "Please choose an entry script.")
            return

        script = self.base_dir / script_name
        if not script.exists():
            messagebox.showerror("Missing script",
                                 f"{script} does not exist.")
            return

        exe_name = self.exe_name_var.get().strip(' .')
        if exe_name.lower().endswith('.exe'):
            exe_name = exe_name[:-4]
        for ch in r'\/:*?"<>|':
            exe_name = exe_name.replace(ch, '_')
        exe_name = exe_name.strip(' ._') or script.stem

        icon_path: Optional[Path] = None
        if ICON_SUPPORTED:
            icon_str = self.icon_var.get().strip()
            if icon_str:
                icon_path = Path(icon_str)
                if not icon_path.exists():
                    messagebox.showerror(
                        "Icon missing",
                        f"Icon file not found:\n{icon_path}",
                    )
                    return
                if icon_path.suffix.lower() not in ACCEPTED_ICON_SUFFIXES:
                    messagebox.showerror(
                        "Unsupported icon format",
                        "Supported on this platform: "
                        + ", ".join(sorted(ACCEPTED_ICON_SUFFIXES)),
                    )
                    return

        options = BuildOptions(
            console=self.console_var.get(),
            admin=self.admin_var.get(),
            keep_spec=self.keep_spec_var.get(),
            keep_build=self.keep_build_var.get(),
            clean_build=self.clean_build_var.get(),
            modules={name: var.get()
                     for name, var in self.module_vars.items()},
        )

        self._drain_queue()
        self._set_busy(True)
        self._clear_log()
        self._log(f"{PREFIX_INFO} Starting build…", TAG_INFO)

        if options.clean_build and options.keep_build:
            self._log(f"{PREFIX_INFO} --clean wipes PyInstaller cache; "
                      "keep_build keeps local build/ folder.", TAG_INFO)

        threading.Thread(
            target=self._run_build,
            args=(self.base_dir, script, exe_name, options, icon_path),
            daemon=True,
        ).start()

    def _run_build(self, base_dir: Path, script: Path, exe_name: str,
                   options: BuildOptions, icon_path: Optional[Path]):
        start_time = time.time()

        if IS_WINDOWS and icon_path:
            self.q_info(f"Using icon: {icon_path.name}")
        elif IS_WINDOWS:
            self.q_info("No icon will be applied")

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile", f"--name={exe_name}", "--noconfirm",
        ]
        if options.clean_build:
            cmd.append("--clean")
            self.q_info("--clean enabled (wipe cache before build)")

        if not options.console:
            cmd.append("--noconsole")
            if not IS_WINDOWS:
                self.q_warn("--noconsole is ignored on Linux "
                            "(no-op, flag has no effect)")
        if icon_path and IS_WINDOWS:
            cmd.extend(["--icon", str(icon_path)])
        if options.admin:
            if IS_WINDOWS:
                cmd.append("--uac-admin")
            else:
                self.q_warn("--uac-admin skipped (Windows only)")

        bundled = [name for name, flag in options.modules.items() if flag]
        for name in bundled:
            cmd.append(f"--collect-all={name}")

        if bundled:
            self.q_info(f"Bundled: {', '.join(bundled)}")
        else:
            self.q_info("No optional modules bundled")

        cmd.append(str(script))
        self.log_queue.put(("Command:\n  " + " ".join(cmd), TAG_MUTED))

        success = False
        try:
            dist_dir = base_dir / "dist"
            dist_dir.mkdir(exist_ok=True)

            if IS_WINDOWS:
                popen_kwargs: dict = {
                    'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
            else:
                popen_kwargs = {'start_new_session': True}

            proc = subprocess.Popen(
                cmd,
                cwd=str(base_dir),
                stdout=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                **popen_kwargs,
            )

            with self._proc_lock:
                self._proc = proc
                closing = self._closing

            if closing:
                self._terminate_proc()
            else:
                if proc.stdout is None:
                    raise RuntimeError("PyInstaller subprocess has no stdout")

                for line in proc.stdout:
                    self.log_queue.put((line.rstrip(), TAG_MUTED))
                proc.wait()

                if not self._closing:
                    success = proc.returncode == 0
                    if not success:
                        self.q_error(
                            f"PyInstaller exited with code {proc.returncode}")
        except Exception as e:
            self.q_error(f"Build error: {e}")
        finally:
            with self._proc_lock:
                self._proc = None

            if not self._closing:
                cleanup(
                    base_dir, exe_name,
                    keep_spec=options.keep_spec,
                    keep_build=options.keep_build,
                )

                if not success and not options.keep_spec:
                    self.q_info("Tip: enable 'Keep .spec file' to inspect "
                                "the generated .spec for debugging.")
                if not success and not options.keep_build:
                    self.q_info("Tip: enable 'Keep build/ folder' to "
                                "inspect PyInstaller's intermediate "
                                "artifacts.")

                elapsed = time.time() - start_time
                self.q_info(f"Build time: {elapsed:.1f}s")

                if success:
                    suffix = ".exe" if IS_WINDOWS else ""
                    exe_path = base_dir / "dist" / f"{exe_name}{suffix}"
                    if exe_path.exists():
                        size_mb = exe_path.stat().st_size / (1024 * 1024)
                        self.q_ok(f"Build successful: {exe_path}")
                        self.q_info(f"Size: {size_mb:.2f} MB")
                    else:
                        self.q_warn(
                            f"Build reported success, but "
                            f"{exe_path} not found.")
                else:
                    self.q_error("Build failed. Check log above.")

            self.log_queue.put(None)


def main():
    root = tk.Tk()
    style = ttk.Style()
    for theme in ('vista', 'clam'):
        if theme in style.theme_names():
            style.theme_use(theme)
            break
    SmartPyInstallerGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
