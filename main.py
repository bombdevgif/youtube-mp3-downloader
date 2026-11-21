"""
YouTube MP3 Downloader - Desktop GUI Application
Modern CustomTkinter desktop interface for downloading YouTube videos and playlists as MP3.
"""

import os
import sys
import re
import json
import shutil
import threading
import queue
import urllib.request
import urllib.error
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    import tkinter as ctk

import yt_dlp

APP_VERSION = "1.0.1"
GITHUB_REPO = "bombdevgif/youtube-mp3-downloader"

# Set appearance and theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_current_version():
    """Read version from version.json if available, else fallback to constant."""
    v_file = resource_path("version.json")
    if os.path.isfile(v_file):
        try:
            with open(v_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version", APP_VERSION)
        except Exception:
            pass
    return APP_VERSION


def parse_version_tuple(v_str):
    """Parse version string like 'v1.0.3' or '1.0.3' into tuple (1, 0, 3)."""
    clean = v_str.lstrip("v").strip()
    parts = clean.split(".")
    res = []
    for p in parts:
        nums = re.findall(r"\d+", p)
        res.append(int(nums[0]) if nums else 0)
    while len(res) < 3:
        res.append(0)
    return tuple(res)


def get_config_path():
    """Returns path to user settings JSON file in AppData."""
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    config_dir = os.path.join(appdata, "YouTubeMP3Downloader")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")


def load_user_config():
    """Load persistent settings like last save folder."""
    cfg_file = get_config_path()
    default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(default_dir):
        default_dir = os.getcwd()

    defaults = {
        "save_dir": default_dir,
        "bitrate": "320 kbps",
    }
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    saved_dir = data.get("save_dir")
                    if saved_dir and os.path.isdir(saved_dir):
                        defaults["save_dir"] = os.path.normpath(saved_dir)
                    saved_bitrate = data.get("bitrate")
                    if saved_bitrate in ["128 kbps", "192 kbps", "320 kbps"]:
                        defaults["bitrate"] = saved_bitrate
        except Exception:
            pass
    return defaults


def save_user_config(save_dir, bitrate=None):
    """Save persistent settings."""
    try:
        cfg_file = get_config_path()
        data = {"save_dir": save_dir}
        if bitrate:
            data["bitrate"] = bitrate
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def find_ffmpeg_location():
    """Detect ffmpeg binary location (bundled inside app, local folder, PATH, or WinGet)."""
    bundled_ffmpeg = resource_path("ffmpeg.exe")
    if os.path.isfile(bundled_ffmpeg):
        return os.path.dirname(os.path.abspath(bundled_ffmpeg))

    app_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(os.path.join(app_dir, "ffmpeg.exe")):
        return app_dir

    path_ffmpeg = shutil.which("ffmpeg")
    if path_ffmpeg:
        return os.path.dirname(os.path.abspath(path_ffmpeg))

    user_profile = os.environ.get("USERPROFILE", "")
    candidates = [
        os.path.join(user_profile, "AppData", "Local", "Microsoft", "WinGet", "Links"),
        os.path.join(
            user_profile,
            "AppData",
            "Local",
            "Microsoft",
            "WinGet",
            "Packages",
            "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
            "ffmpeg-9.1-full_build",
            "bin",
        ),
        "C:\\ffmpeg\\bin",
        "C:\\Program Files\\ffmpeg\\bin",
    ]
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "ffmpeg.exe")):
            return candidate

    winget_packages = os.path.join(user_profile, "AppData", "Local", "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_packages):
        for root, _, files in os.walk(winget_packages):
            if "ffmpeg.exe" in files:
                return root

    return None


class UpdateDialog(ctk.CTkToplevel):
    """Modern popup asking user if they want to download the new update."""
    def __init__(self, parent, latest_tag, release_notes, download_url):
        super().__init__(parent)
        self.title("New Update Available")
        self.geometry("520x360")
        self.minsize(450, 300)
        self.parent = parent
        self.download_url = download_url
        self.latest_tag = latest_tag

        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        lbl_title = ctk.CTkLabel(
            self,
            text=f"🚀 Update Available: {latest_tag}",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        lbl_title.pack(anchor="w", padx=20, pady=(20, 5))

        lbl_desc = ctk.CTkLabel(
            self,
            text=f"A newer version of YouTube MP3 Downloader is available on GitHub.\nWould you like to download and install it now inside the app?",
            justify="left",
            font=ctk.CTkFont(size=12),
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(0, 10))

        # Release Notes Preview
        notes_box = ctk.CTkTextbox(self, height=130, font=ctk.CTkFont(size=11))
        notes_box.pack(fill="both", expand=True, padx=20, pady=5)
        notes_box.insert("1.0", release_notes or "Bug fixes and improvements.")
        notes_box.configure(state="disabled")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 20))

        btn_update = ctk.CTkButton(
            btn_frame,
            text="⬇ Update Now (In-App)",
            fg_color="#2a9d8f",
            hover_color="#21867a",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_update,
        )
        btn_update.pack(side="right", padx=(10, 0))

        btn_later = ctk.CTkButton(
            btn_frame,
            text="Later",
            fg_color=("gray60", "gray35"),
            hover_color=("gray50", "gray45"),
            command=self.destroy,
        )
        btn_later.pack(side="right")

    def _on_update(self):
        self.destroy()
        self.parent.start_in_app_update(self.download_url, self.latest_tag)


class YouTubeMP3Downloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.current_version = get_current_version()
        self.title(f"YouTube to MP3 Downloader (v{self.current_version})")
        self.geometry("740x660")
        self.minsize(580, 480)

        # Set window icon
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Download state
        self.is_downloading = False
        self.cancel_requested = False
        self.download_queue = queue.Queue()
        self.ffmpeg_location = find_ffmpeg_location()

        # Load saved user settings (Remember last folder & default to highest bitrate 320 kbps)
        self.user_cfg = load_user_config()
        self.download_path_var = tk.StringVar(value=self.user_cfg["save_dir"])
        self.bitrate_var = tk.StringVar(value=self.user_cfg.get("bitrate", "320 kbps"))

        # URL variable
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)

        # Playlist Options
        self.playlist_mode_var = tk.StringVar(value="auto")  # "auto", "playlist", "single"
        self.embed_metadata_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._check_queue()
        self._check_initial_ffmpeg()

        # Trigger automatic background check for new releases
        self.after(1500, self.check_for_updates_background)

    def _build_ui(self):
        # Configure layout grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main Scrollable Frame - ensures all controls adapt gracefully to any window size
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=15,
            fg_color=("gray92", "#1e1e24"),
        )
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Header Title & Subtitle
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(15, 8))

        top_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        top_row.pack(fill="x")

        title_label = ctk.CTkLabel(
            top_row,
            text="🎵 YouTube to MP3 Downloader",
            font=ctk.CTkFont(size=23, weight="bold"),
        )
        title_label.pack(side="left")

        self.ver_label = ctk.CTkLabel(
            top_row,
            text=f"v{self.current_version}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#2a9d8f",
        )
        self.ver_label.pack(side="left", padx=10)

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Download single videos or full playlists in high-fidelity MP3 with metadata",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70"),
        )
        subtitle_label.pack(anchor="w", pady=(2, 0))

        # ---------------- Section 1: URL Input ----------------
        url_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        url_frame.pack(fill="x", padx=10, pady=8)
        url_frame.grid_columnconfigure(0, weight=1)

        url_label = ctk.CTkLabel(
            url_frame,
            text="YouTube Video or Playlist URL:",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        url_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))

        self.url_entry = ctk.CTkEntry(
            url_frame,
            textvariable=self.url_var,
            placeholder_text="https://www.youtube.com/watch?v=... or https://www.youtube.com/playlist?list=...",
            height=38,
            font=ctk.CTkFont(size=12),
        )
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=(15, 8), pady=(0, 12))

        self.paste_btn = ctk.CTkButton(
            url_frame,
            text="📋 Paste",
            width=80,
            height=38,
            command=self.paste_url,
            font=ctk.CTkFont(size=12),
        )
        self.paste_btn.grid(row=1, column=1, padx=4, pady=(0, 12))

        self.clear_btn = ctk.CTkButton(
            url_frame,
            text="✕ Clear",
            width=70,
            height=38,
            fg_color=("gray60", "gray35"),
            hover_color=("gray50", "gray45"),
            command=self.clear_url,
            font=ctk.CTkFont(size=12),
        )
        self.clear_btn.grid(row=1, column=2, padx=(4, 15), pady=(0, 12))

        # ---------------- Section 2: Download Options ----------------
        options_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        options_frame.pack(fill="x", padx=10, pady=8)
        options_frame.grid_columnconfigure(1, weight=1)

        # Quality selector (Defaulted to 320 kbps - Highest Available)
        bitrate_label = ctk.CTkLabel(
            options_frame,
            text="Audio Bitrate:",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        bitrate_label.grid(row=0, column=0, sticky="w", padx=15, pady=(12, 6))

        self.bitrate_menu = ctk.CTkOptionMenu(
            options_frame,
            values=["320 kbps (Best)", "192 kbps (Standard)", "128 kbps (Compact)"],
            variable=self.bitrate_var,
            width=180,
            command=self._on_bitrate_changed,
        )
        cur_b = self.bitrate_var.get()
        if "320" in cur_b:
            self.bitrate_var.set("320 kbps (Best)")
        elif "192" in cur_b:
            self.bitrate_var.set("192 kbps (Standard)")
        elif "128" in cur_b:
            self.bitrate_var.set("128 kbps (Compact)")
        else:
            self.bitrate_var.set("320 kbps (Best)")

        self.bitrate_menu.grid(row=0, column=1, sticky="w", padx=10, pady=(12, 6))

        # Playlist mode selector
        playlist_label = ctk.CTkLabel(
            options_frame,
            text="Playlist Behavior:",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        playlist_label.grid(row=1, column=0, sticky="w", padx=15, pady=6)

        playlist_options_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        playlist_options_frame.grid(row=1, column=1, sticky="w", padx=10, pady=6)

        self.rb_auto = ctk.CTkRadioButton(
            playlist_options_frame,
            text="Auto Detect",
            variable=self.playlist_mode_var,
            value="auto",
        )
        self.rb_auto.pack(side="left", padx=(0, 10))

        self.rb_playlist = ctk.CTkRadioButton(
            playlist_options_frame,
            text="Entire Playlist",
            variable=self.playlist_mode_var,
            value="playlist",
        )
        self.rb_playlist.pack(side="left", padx=10)

        self.rb_single = ctk.CTkRadioButton(
            playlist_options_frame,
            text="Single Video Only",
            variable=self.playlist_mode_var,
            value="single",
        )
        self.rb_single.pack(side="left", padx=10)

        # Metadata toggle
        self.metadata_chk = ctk.CTkCheckBox(
            options_frame,
            text="Embed ID3 tags (Title, Artist, Album) & Thumbnail Cover",
            variable=self.embed_metadata_var,
        )
        self.metadata_chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(6, 12))

        # ---------------- Section 3: Save Location ----------------
        save_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        save_frame.pack(fill="x", padx=10, pady=8)
        save_frame.grid_columnconfigure(0, weight=1)

        save_label = ctk.CTkLabel(
            save_frame,
            text="Save Location (Remembers your chosen folder):",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        save_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 4))

        self.path_entry = ctk.CTkEntry(
            save_frame,
            textvariable=self.download_path_var,
            state="readonly",
            height=36,
            font=ctk.CTkFont(size=11),
        )
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(15, 8), pady=(0, 12))

        self.browse_btn = ctk.CTkButton(
            save_frame,
            text="📁 Browse...",
            width=95,
            height=36,
            command=self.browse_directory,
            font=ctk.CTkFont(size=12),
        )
        self.browse_btn.grid(row=1, column=1, padx=(0, 15), pady=(0, 12))

        # ---------------- Section 4: Progress & Status ----------------
        progress_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        progress_frame.pack(fill="x", padx=10, pady=8)

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready. Paste a YouTube link and click Download.",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray85"),
            wraplength=640,
            justify="left",
        )
        self.status_label.pack(anchor="w", padx=15, pady=(10, 5))

        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=12)
        self.progress_bar.pack(fill="x", padx=15, pady=(4, 6))
        self.progress_bar.set(0)

        self.detail_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray65"),
        )
        self.detail_label.pack(anchor="w", padx=15, pady=(0, 10))

        # ---------------- Action Buttons ----------------
        action_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        action_frame.pack(fill="x", padx=10, pady=(10, 25))

        self.download_btn = ctk.CTkButton(
            action_frame,
            text="⬇ Start Download",
            height=46,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_download_thread,
            fg_color="#1f6aa5",
            hover_color="#144870",
        )
        self.download_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.open_folder_btn = ctk.CTkButton(
            action_frame,
            text="📂 Open Folder",
            height=46,
            width=125,
            font=ctk.CTkFont(size=13),
            command=self.open_target_folder,
            fg_color=("gray60", "gray35"),
            hover_color=("gray50", "gray45"),
        )
        self.open_folder_btn.pack(side="right")

    # ---------------- Automatic Update Logic ----------------
    def check_for_updates_background(self):
        """Worker thread to query GitHub API for releases."""
        def _check():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "YouTubeMP3Downloader-App"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        tag = data.get("tag_name", "")
                        body = data.get("body", "")
                        assets = data.get("assets", [])

                        current_v = parse_version_tuple(self.current_version)
                        latest_v = parse_version_tuple(tag)

                        if latest_v > current_v:
                            # Look for .exe asset
                            exe_url = None
                            for a in assets:
                                if a.get("name", "").endswith(".exe"):
                                    exe_url = a.get("browser_download_url")
                                    break
                            if exe_url:
                                self.download_queue.put(("prompt_update", (tag, body, exe_url)))
            except Exception:
                # Silently skip if user is offline or rate limited
                pass

        threading.Thread(target=_check, daemon=True).start()

    def start_in_app_update(self, download_url, latest_tag):
        """Download update in-app and restart seamlessly."""
        self._set_ui_state(True)
        self.download_btn.configure(text="⬇ Updating App...", state="disabled")
        self.status_label.configure(text=f"Downloading update {latest_tag} in-app...", text_color="#2a9d8f")
        self.progress_bar.set(0)

        def _update_worker():
            try:
                app_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
                temp_update_exe = os.path.join(os.environ.get("TEMP", os.getcwd()), f"Update_{latest_tag}.exe")

                req = urllib.request.Request(download_url, headers={"User-Agent": "YouTubeMP3Downloader-App"})
                with urllib.request.urlopen(req, timeout=30) as response, open(temp_update_exe, "wb") as out_file:
                    total_length = response.getheader("content-length")
                    if total_length:
                        total_length = int(total_length)
                    downloaded = 0
                    chunk_size = 1024 * 64

                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        out_file.write(chunk)
                        if total_length:
                            progress = downloaded / total_length
                            self.download_queue.put(("progress", progress))
                            mb_down = downloaded / (1024 * 1024)
                            mb_tot = total_length / (1024 * 1024)
                            self.download_queue.put(
                                ("status", f"Downloading update {latest_tag}: {mb_down:.1f} MB / {mb_tot:.1f} MB ({progress*100:.0f}%)")
                            )

                self.download_queue.put(("status", "Update downloaded! Applying update and restarting..."))
                self.download_queue.put(("progress", 1.0))

                # Launch updater script to replace current running executable and restart it
                if getattr(sys, "frozen", False):
                    bat_content = f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{temp_update_exe}" "{app_exe}"
start "" "{app_exe}"
del "%~f0"
"""
                    bat_path = os.path.join(os.environ.get("TEMP", os.getcwd()), "apply_update.bat")
                    with open(bat_path, "w", encoding="utf-8") as f:
                        f.write(bat_content)

                    subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    self.after(500, self.destroy)
                else:
                    self.download_queue.put(("finish", ""))
                    messagebox.showinfo("Update Downloaded", f"Update downloaded to:\n{temp_update_exe}")

            except Exception as e:
                self.download_queue.put(("error", f"Update download failed:\n{str(e)}"))
                self._set_ui_state(False)

        threading.Thread(target=_update_worker, daemon=True).start()

    def _check_initial_ffmpeg(self):
        """Notify user if ffmpeg was not detected."""
        if not self.ffmpeg_location:
            self.status_label.configure(
                text="⚠️ Warning: FFmpeg not detected. MP3 conversion requires FFmpeg.",
                text_color="#e07a5f",
            )
        else:
            self.detail_label.configure(
                text=f"FFmpeg ready ({self.ffmpeg_location})"
            )

    def _on_url_change(self, *args):
        """Update playlist mode hint automatically when URL is pasted."""
        url = self.url_var.get().strip()
        if "list=" in url and self.playlist_mode_var.get() == "auto":
            self.detail_label.configure(text="ℹ️ Detected playlist link in URL.")

    def _on_bitrate_changed(self, choice):
        """Save selected bitrate."""
        save_user_config(self.download_path_var.get(), choice)

    def paste_url(self):
        """Read clipboard and paste into URL entry."""
        try:
            clipboard = self.clipboard_get().strip()
            if clipboard:
                self.url_var.set(clipboard)
        except Exception:
            pass

    def clear_url(self):
        """Clear URL entry and status."""
        self.url_var.set("")
        if not self.is_downloading:
            self.progress_bar.set(0)
            self.status_label.configure(
                text="Ready. Paste a YouTube link and click Download.",
                text_color=("gray30", "gray85"),
            )
            self.detail_label.configure(text="")

    def browse_directory(self):
        """Open directory picker dialog and save user preference."""
        selected = filedialog.askdirectory(
            initialdir=self.download_path_var.get(),
            title="Select Destination Folder",
        )
        if selected:
            norm = os.path.normpath(selected)
            self.download_path_var.set(norm)
            save_user_config(norm, self.bitrate_var.get())

    def open_target_folder(self):
        """Open destination folder in Windows File Explorer."""
        target_path = self.download_path_var.get()
        if os.path.exists(target_path):
            os.startfile(target_path)
        else:
            messagebox.showwarning("Folder Not Found", f"The directory does not exist:\n{target_path}")

    def _set_ui_state(self, downloading: bool):
        """Enable/disable controls during active downloads."""
        self.is_downloading = downloading
        state = "disabled" if downloading else "normal"
        self.download_btn.configure(
            text="⏳ Downloading..." if downloading else "⬇ Start Download",
            state=state,
        )
        self.paste_btn.configure(state=state)
        self.clear_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        self.bitrate_menu.configure(state=state)
        self.metadata_chk.configure(state=state)
        self.rb_auto.configure(state=state)
        self.rb_playlist.configure(state=state)
        self.rb_single.configure(state=state)

    def _check_queue(self):
        """Process GUI updates dispatched from worker thread."""
        try:
            while True:
                msg_type, data = self.download_queue.get_nowait()
                if msg_type == "status":
                    self.status_label.configure(text=data, text_color=("gray30", "gray85"))
                elif msg_type == "detail":
                    self.detail_label.configure(text=data)
                elif msg_type == "progress":
                    self.progress_bar.set(data)
                elif msg_type == "warning":
                    self.status_label.configure(text=f"⚠️ {data}", text_color="#e07a5f")
                elif msg_type == "error":
                    self.status_label.configure(text=f"❌ {data}", text_color="#e76f51")
                    messagebox.showerror("Download Error", data)
                elif msg_type == "finish":
                    self._set_ui_state(False)
                    self.progress_bar.set(1.0)
                    self.status_label.configure(text="✅ All downloads completed successfully!", text_color="#2a9d8f")
                    messagebox.showinfo("Done", "Download complete!")
                elif msg_type == "finish_with_errors":
                    self._set_ui_state(False)
                    self.progress_bar.set(1.0)
                    self.status_label.configure(
                        text=f"⚠️ Completed with skipped/failed tracks: {data}",
                        text_color="#e07a5f",
                    )
                    messagebox.showwarning("Download Finished with Warnings", f"Some tracks could not be downloaded:\n{data}")
                elif msg_type == "prompt_update":
                    tag, body, exe_url = data
                    UpdateDialog(self, tag, body, exe_url)
                self.download_queue.task_done()
        except queue.Empty:
            pass

        self.after(100, self._check_queue)

    def start_download_thread(self):
        """Validate input and trigger background worker thread."""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter or paste a YouTube URL.")
            return

        # Basic URL format check
        if not (url.startswith("http://") or url.startswith("https://")):
            messagebox.showwarning("Invalid URL", "Please enter a valid URL starting with http:// or https://")
            return

        # Refresh ffmpeg location if needed
        if not self.ffmpeg_location:
            self.ffmpeg_location = find_ffmpeg_location()

        save_dir = self.download_path_var.get().strip()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create destination directory:\n{e}")
                return

        # Ensure user config remembers directory
        save_user_config(save_dir, self.bitrate_var.get())

        # Parse selected bitrate (e.g. '320 kbps (Best)' -> '320')
        bitrate_str = re.findall(r"\d+", self.bitrate_var.get())
        bitrate_val = bitrate_str[0] if bitrate_str else "320"

        self._set_ui_state(True)
        self.progress_bar.set(0)
        self.status_label.configure(text="Fetching video/playlist metadata...", text_color=("gray30", "gray85"))
        self.detail_label.configure(text="Connecting to YouTube...")

        worker = threading.Thread(
            target=self._download_worker,
            args=(
                url,
                save_dir,
                bitrate_val,
                self.playlist_mode_var.get(),
                self.embed_metadata_var.get(),
                self.ffmpeg_location,
            ),
            daemon=True,
        )
        worker.start()

    def _download_worker(self, url, save_dir, bitrate, playlist_mode, embed_metadata, ffmpeg_loc):
        """Worker thread executing yt-dlp download & conversion."""
        skipped_items = []
        current_item_index = [0]
        total_items = [1]

        def ytdl_hook(d):
            status = d.get("status")
            if status == "downloading":
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                percent_str = ""
                if total_bytes > 0:
                    fraction = min(1.0, max(0.0, downloaded / total_bytes))
                    if total_items[0] > 1:
                        track_slice = 1.0 / total_items[0]
                        overall = (current_item_index[0] - 1) * track_slice + fraction * track_slice
                        self.download_queue.put(("progress", min(0.99, overall)))
                    else:
                        self.download_queue.put(("progress", min(0.95, fraction)))
                    percent_str = f" {fraction * 100:.1f}%"

                speed = d.get("speed")
                speed_str = f" @ {speed / 1024 / 1024:.2f} MB/s" if speed else ""
                eta = d.get("eta")
                eta_str = f" (ETA: {eta}s)" if eta else ""

                if total_items[0] > 1:
                    status_text = f"Downloading track {current_item_index[0]} of {total_items[0]}...{percent_str}"
                else:
                    filename = os.path.basename(d.get("filename", "audio stream"))
                    clean_name = re.sub(r"\.[^.]+$", "", filename)
                    status_text = f"Downloading: {clean_name[:40]}...{percent_str}"

                self.download_queue.put(("status", status_text))
                self.download_queue.put(("detail", f"Speed: {speed_str.strip() or 'N/A'}{eta_str}"))

            elif status == "finished":
                self.download_queue.put(("status", "Converting to MP3 at selected bitrate..."))
                self.download_queue.put(("detail", "Running FFmpeg audio extraction..."))

        class MyCustomLogger:
            def __init__(self, q):
                self.q = q

            def debug(self, msg):
                pass

            def info(self, msg):
                pass

            def warning(self, msg):
                if "unavailable" in msg.lower() or "private" in msg.lower():
                    self.q.put(("warning", msg[:100]))

            def error(self, msg):
                pass

        # Configure yt-dlp parameters
        if playlist_mode == "playlist":
            noplaylist = False
        elif playlist_mode == "single":
            noplaylist = True
        else:  # "auto"
            noplaylist = "list=" not in url

        outtmpl = os.path.join(save_dir, "%(title)s.%(ext)s")
        if not noplaylist:
            outtmpl = os.path.join(
                save_dir,
                "%(playlist,playlist_title)s",
                "%(playlist_index)02d - %(title)s.%(ext)s",
            )

        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }
        ]

        if embed_metadata:
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
            postprocessors.append(
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": False,
                }
            )

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": postprocessors,
            "progress_hooks": [ytdl_hook],
            "logger": MyCustomLogger(self.download_queue),
            "noplaylist": noplaylist,
            "ignoreerrors": True,
            "quiet": True,
            "no_warnings": False,
            "writethumbnail": embed_metadata,
        }

        if ffmpeg_loc:
            ydl_opts["ffmpeg_location"] = ffmpeg_loc

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.download_queue.put(("detail", "Extracting playlist/video information..."))
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as ex:
                    self.download_queue.put(("error", f"Could not fetch information for URL:\n{str(ex)}"))
                    self.download_queue.put(("detail", ""))
                    return

                if not info:
                    self.download_queue.put(("error", "No video or playlist found at this URL."))
                    self.download_queue.put(("detail", ""))
                    return

                if "entries" in info:
                    entries = list(info["entries"])
                    valid_entries = [e for e in entries if e is not None]
                    total_items[0] = max(1, len(valid_entries))
                    playlist_title = info.get("title", "YouTube Playlist")
                    self.download_queue.put(
                        ("status", f"Found playlist: '{playlist_title}' ({total_items[0]} tracks)")
                    )
                else:
                    total_items[0] = 1
                    video_title = info.get("title", "Video")
                    self.download_queue.put(("status", f"Found track: '{video_title}'"))

                def each_entry_hook(d):
                    if d.get("status") == "downloading" and d.get("filename"):
                        p_idx = d.get("info_dict", {}).get("playlist_index")
                        if p_idx:
                            current_item_index[0] = p_idx
                        else:
                            current_item_index[0] = 1

                ydl_opts["progress_hooks"].append(each_entry_hook)

                download_result = ydl.download([url])

                if download_result != 0 and len(skipped_items) > 0:
                    self.download_queue.put(("finish_with_errors", f"{len(skipped_items)} tracks skipped."))
                else:
                    self.download_queue.put(("finish", ""))

        except yt_dlp.utils.DownloadError as de:
            self.download_queue.put(("error", f"Download failed:\n{str(de)}"))
        except Exception as e:
            self.download_queue.put(("error", f"An unexpected error occurred:\n{str(e)}"))


def main():
    app = YouTubeMP3Downloader()
    app.mainloop()


if __name__ == "__main__":
    main()
