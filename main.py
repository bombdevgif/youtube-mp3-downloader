"""
YouTube MP3 Downloader - Desktop GUI Application
macOS / Apple Human Interface Guidelines aesthetic design.
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

# Apple HIG Hex Color Palette
APPLE_BG = ("#F5F5F7", "#1C1C1E")               # Base system background
APPLE_CARD = ("#FFFFFF", "#2C2C2E")             # Inset grouped card surface
APPLE_CARD_HOVER = ("#F0F0F2", "#363638")       # Subtle card hover
APPLE_BORDER = ("#E5E5EA", "#38383A")           # Hairline low-contrast border
APPLE_BORDER_FOCUS = ("#007AFF", "#0A84FF")     # System Blue focus
APPLE_BLUE = ("#007AFF", "#0A84FF")             # Apple System Blue
APPLE_BLUE_HOVER = ("#0062CC", "#0071E3")       # System Blue hover / pressed
APPLE_TEXT = ("#1D1D1F", "#F5F5F7")             # Primary Label
APPLE_SECONDARY = ("#86868B", "#98989D")        # Secondary Label
APPLE_GREEN = ("#34C759", "#30D158")            # System Green
APPLE_ORANGE = ("#FF9500", "#FF9F0A")           # System Orange
APPLE_RED = ("#FF3B30", "#FF453A")              # System Red
APPLE_ENTRY_BG = ("#F9F9FB", "#242426")         # Inset entry field
APPLE_PILL_BLUE_BG = ("#EBF5FF", "#142845")     # Light blue badge tint
APPLE_PILL_GREEN_BG = ("#E8F8EE", "#163422")    # Light green badge tint
APPLE_BAR_BG = ("#E5E5EA", "#3A3A3C")           # Track bar bg

# Apple typography preference
FONT_FAMILY = "Segoe UI Variable Text"
FONT_DISPLAY = "Segoe UI Variable Display"

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
        "bitrate": "320 kbps (Best)",
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
                    if saved_bitrate:
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
    """Apple HIG Sheet / Modal for App Updates."""
    def __init__(self, parent, latest_tag, release_notes, download_url):
        super().__init__(parent)
        self.title("Software Update")
        self.geometry("500x350")
        self.minsize(440, 310)
        self.parent = parent
        self.download_url = download_url
        self.latest_tag = latest_tag
        self.configure(fg_color=APPLE_BG)

        self.transient(parent)
        self.grab_set()

        card = ctk.CTkFrame(
            self,
            fg_color=APPLE_CARD,
            border_color=APPLE_BORDER,
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="both", expand=True, padx=20, pady=20)

        # Header with icon
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(fill="x", padx=20, pady=(20, 8))

        icon_lbl = ctk.CTkLabel(
            header_row,
            text="✨",
            font=ctk.CTkFont(size=24),
        )
        icon_lbl.pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        lbl_title = ctk.CTkLabel(
            title_box,
            text=f"Update Available: {latest_tag}",
            font=ctk.CTkFont(family=FONT_DISPLAY, size=17, weight="bold"),
            text_color=APPLE_TEXT,
            anchor="w",
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_box,
            text="A new version of YouTube MP3 Downloader is ready to install.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=APPLE_SECONDARY,
            anchor="w",
        )
        lbl_sub.pack(anchor="w")

        # Release notes text
        notes_box = ctk.CTkTextbox(
            card,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=APPLE_ENTRY_BG,
            border_color=APPLE_BORDER,
            border_width=1,
            corner_radius=8,
            wrap="word",
        )
        notes_box.pack(fill="both", expand=True, padx=20, pady=10)
        notes_box.insert("1.0", release_notes or "Stability and performance improvements.")
        notes_box.configure(state="disabled")

        # Actions
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 18))

        btn_update = ctk.CTkButton(
            btn_frame,
            text="Update Now",
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            corner_radius=7,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            command=self._on_update,
        )
        btn_update.pack(side="right", padx=(10, 0))

        btn_later = ctk.CTkButton(
            btn_frame,
            text="Later",
            fg_color="transparent",
            text_color=APPLE_SECONDARY,
            hover_color=APPLE_BORDER,
            border_color=APPLE_BORDER,
            border_width=1,
            corner_radius=7,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
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
        self.title("YouTube to MP3")
        self.geometry("740x670")
        self.minsize(580, 500)
        self.configure(fg_color=APPLE_BG)

        # Set window icon
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Download & Worker state
        self.is_downloading = False
        self.download_queue = queue.Queue()
        self.ffmpeg_location = find_ffmpeg_location()

        # User persistent settings
        self.user_cfg = load_user_config()
        self.download_path_var = tk.StringVar(value=self.user_cfg["save_dir"])
        self.bitrate_var = tk.StringVar(value=self.user_cfg.get("bitrate", "320 kbps (Best)"))

        # URL variable
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)

        # Playlist Options
        self.playlist_mode_var = tk.StringVar(value="auto")  # "auto", "playlist", "single"
        self.embed_metadata_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._check_queue()
        self._check_initial_ffmpeg()

        # Automatic background check for new releases
        self.after(1200, self.check_for_updates_background)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Scrollable container styled like macOS System Settings
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=0,
            fg_color=APPLE_BG,
        )
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # ---------------- Toolbar / Top Header ----------------
        top_bar = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=24, pady=(20, 12))

        header_title = ctk.CTkLabel(
            top_bar,
            text="YouTube to MP3",
            font=ctk.CTkFont(family=FONT_DISPLAY, size=24, weight="bold"),
            text_color=APPLE_TEXT,
        )
        header_title.pack(side="left")

        # Pill badge for version
        self.version_pill = ctk.CTkLabel(
            top_bar,
            text=f"v{self.current_version}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=APPLE_BLUE,
            fg_color=APPLE_PILL_BLUE_BG,
            corner_radius=12,
            padx=9,
            pady=3,
        )
        self.version_pill.pack(side="left", padx=(10, 0))

        # Update Status Badge / Notification Pill in header
        self.update_status_pill = ctk.CTkLabel(
            top_bar,
            text="Checking for updates...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=APPLE_SECONDARY,
            fg_color="transparent",
            corner_radius=10,
            padx=8,
            pady=2,
        )
        self.update_status_pill.pack(side="right")

        # ---------------- Card 1: URL Input ----------------
        card_url = self._create_card()

        lbl_url = ctk.CTkLabel(
            card_url,
            text="Link",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=APPLE_TEXT,
        )
        lbl_url.pack(anchor="w", padx=16, pady=(14, 6))

        input_row = ctk.CTkFrame(card_url, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(0, 14))
        input_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            input_row,
            textvariable=self.url_var,
            placeholder_text="Paste video or playlist link...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            height=34,
            corner_radius=8,
            border_width=1,
            border_color=APPLE_BORDER,
            fg_color=APPLE_ENTRY_BG,
            text_color=APPLE_TEXT,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.paste_btn = ctk.CTkButton(
            input_row,
            text="Paste",
            width=70,
            height=34,
            corner_radius=7,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            command=self.paste_url,
        )
        self.paste_btn.grid(row=0, column=1, padx=(0, 6))

        self.clear_btn = ctk.CTkButton(
            input_row,
            text="Clear",
            width=65,
            height=34,
            corner_radius=7,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent",
            text_color=APPLE_SECONDARY,
            hover_color=APPLE_BORDER,
            border_width=1,
            border_color=APPLE_BORDER,
            command=self.clear_url,
        )
        self.clear_btn.grid(row=0, column=2)

        # ---------------- Card 2: Options (Bitrate & Playlist) ----------------
        card_opts = self._create_card()

        # Row 1: Bitrate Selector
        row_bitrate = ctk.CTkFrame(card_opts, fg_color="transparent")
        row_bitrate.pack(fill="x", padx=16, pady=(14, 10))

        lbl_bitrate = ctk.CTkLabel(
            row_bitrate,
            text="Audio Quality",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=APPLE_TEXT,
        )
        lbl_bitrate.pack(side="left")

        self.bitrate_menu = ctk.CTkOptionMenu(
            row_bitrate,
            values=["320 kbps (Best)", "192 kbps (Standard)", "128 kbps (Compact)"],
            variable=self.bitrate_var,
            width=170,
            height=28,
            corner_radius=7,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            dropdown_font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=APPLE_ENTRY_BG,
            button_color=APPLE_BORDER,
            button_hover_color=APPLE_BLUE,
            text_color=APPLE_TEXT,
            command=self._on_bitrate_changed,
        )
        self.bitrate_menu.pack(side="right")

        # Hairline separator
        self._add_hairline(card_opts)

        # Row 2: Playlist Segmented Mode
        row_playlist = ctk.CTkFrame(card_opts, fg_color="transparent")
        row_playlist.pack(fill="x", padx=16, pady=10)

        lbl_playlist = ctk.CTkLabel(
            row_playlist,
            text="Playlist Behavior",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=APPLE_TEXT,
        )
        lbl_playlist.pack(side="left")

        self.segmented_playlist = ctk.CTkSegmentedButton(
            row_playlist,
            values=["Auto Detect", "Entire Playlist", "Single Video"],
            height=28,
            corner_radius=7,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            selected_color=APPLE_BLUE,
            selected_hover_color=APPLE_BLUE_HOVER,
            command=self._on_segment_changed,
        )
        self.segmented_playlist.set("Auto Detect")
        self.segmented_playlist.pack(side="right")

        # Hairline separator
        self._add_hairline(card_opts)

        # Row 3: Metadata Switch (Apple Style)
        row_meta = ctk.CTkFrame(card_opts, fg_color="transparent")
        row_meta.pack(fill="x", padx=16, pady=(10, 14))

        meta_info = ctk.CTkFrame(row_meta, fg_color="transparent")
        meta_info.pack(side="left")

        lbl_meta = ctk.CTkLabel(
            meta_info,
            text="Embed ID3 Tags & Album Artwork",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=APPLE_TEXT,
            anchor="w",
        )
        lbl_meta.pack(anchor="w")

        lbl_meta_sub = ctk.CTkLabel(
            meta_info,
            text="Adds title, artist, album metadata, and cover art to the file",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=APPLE_SECONDARY,
            anchor="w",
        )
        lbl_meta_sub.pack(anchor="w")

        self.metadata_switch = ctk.CTkSwitch(
            row_meta,
            text="",
            variable=self.embed_metadata_var,
            progress_color=APPLE_BLUE,
            width=46,
            height=24,
            corner_radius=12,
        )
        self.metadata_switch.pack(side="right")

        # ---------------- Card 3: Destination Folder ----------------
        card_dir = self._create_card()

        row_dir_title = ctk.CTkFrame(card_dir, fg_color="transparent")
        row_dir_title.pack(fill="x", padx=16, pady=(14, 6))

        lbl_dir = ctk.CTkLabel(
            row_dir_title,
            text="Save Location",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=APPLE_TEXT,
        )
        lbl_dir.pack(side="left")

        row_dir = ctk.CTkFrame(card_dir, fg_color="transparent")
        row_dir.pack(fill="x", padx=16, pady=(0, 14))
        row_dir.grid_columnconfigure(0, weight=1)

        self.path_entry = ctk.CTkEntry(
            row_dir,
            textvariable=self.download_path_var,
            state="readonly",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=34,
            corner_radius=8,
            border_width=1,
            border_color=APPLE_BORDER,
            fg_color=APPLE_ENTRY_BG,
            text_color=APPLE_TEXT,
        )
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.browse_btn = ctk.CTkButton(
            row_dir,
            text="Choose...",
            width=80,
            height=34,
            corner_radius=7,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color="transparent",
            text_color=APPLE_TEXT,
            border_width=1,
            border_color=APPLE_BORDER,
            hover_color=APPLE_BORDER,
            command=self.browse_directory,
        )
        self.browse_btn.grid(row=0, column=1)

        # ---------------- Card 4: Progress & Status ----------------
        card_progress = self._create_card()

        status_box = ctk.CTkFrame(card_progress, fg_color="transparent")
        status_box.pack(fill="x", padx=16, pady=(14, 6))

        self.status_label = ctk.CTkLabel(
            status_box,
            text="Ready to download",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=APPLE_TEXT,
            anchor="w",
        )
        self.status_label.pack(side="left")

        self.metric_label = ctk.CTkLabel(
            status_box,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=APPLE_SECONDARY,
            anchor="e",
        )
        self.metric_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            card_progress,
            height=6,
            corner_radius=3,
            progress_color=APPLE_BLUE,
            fg_color=APPLE_BAR_BG,
        )
        self.progress_bar.pack(fill="x", padx=16, pady=(4, 6))
        self.progress_bar.set(0)

        self.detail_label = ctk.CTkLabel(
            card_progress,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=APPLE_SECONDARY,
            anchor="w",
        )
        self.detail_label.pack(fill="x", padx=16, pady=(0, 12))

        # ---------------- Actions: Primary Start & Open Folder ----------------
        action_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        action_frame.pack(fill="x", padx=24, pady=(12, 28))

        self.download_btn = ctk.CTkButton(
            action_frame,
            text="Download MP3",
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=APPLE_BLUE,
            hover_color=APPLE_BLUE_HOVER,
            command=self.start_download_thread,
        )
        self.download_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.open_folder_btn = ctk.CTkButton(
            action_frame,
            text="Open Folder",
            height=40,
            width=120,
            corner_radius=8,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color="transparent",
            text_color=APPLE_TEXT,
            border_width=1,
            border_color=APPLE_BORDER,
            hover_color=APPLE_BORDER,
            command=self.open_target_folder,
        )
        self.open_folder_btn.pack(side="right")

    def _create_card(self):
        """Helper to create an Apple HIG inset card container."""
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=APPLE_CARD,
            border_color=APPLE_BORDER,
            border_width=1,
            corner_radius=12,
        )
        card.pack(fill="x", padx=24, pady=6)
        return card

    def _add_hairline(self, parent):
        """Helper to add 1px subtle divider inside grouped card."""
        divider = ctk.CTkFrame(
            parent,
            height=1,
            fg_color=APPLE_BORDER,
        )
        divider.pack(fill="x", padx=16)

    def _on_segment_changed(self, value):
        if value == "Auto Detect":
            self.playlist_mode_var.set("auto")
        elif value == "Entire Playlist":
            self.playlist_mode_var.set("playlist")
        else:
            self.playlist_mode_var.set("single")

    def check_for_updates_background(self):
        """Worker thread to query GitHub API for releases and notify user."""
        def _check():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "YouTubeMP3Downloader-App"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        tag = data.get("tag_name", "")
                        body = data.get("body", "")
                        assets = data.get("assets", [])

                        current_v = parse_version_tuple(self.current_version)
                        latest_v = parse_version_tuple(tag)

                        if latest_v > current_v:
                            exe_url = None
                            for a in assets:
                                if a.get("name", "").endswith(".exe"):
                                    exe_url = a.get("browser_download_url")
                                    break
                            if exe_url:
                                self.download_queue.put(("prompt_update", (tag, body, exe_url)))
                        else:
                            # Notify that app is on latest version
                            self.download_queue.put(("update_checked", "Up to date"))
            except Exception:
                self.download_queue.put(("update_checked", ""))

        threading.Thread(target=_check, daemon=True).start()

    def start_in_app_update(self, download_url, latest_tag):
        """Download update in-app and restart smoothly."""
        self._set_ui_state(True)
        self.download_btn.configure(text="Updating App...", state="disabled")
        self.status_label.configure(text=f"Downloading {latest_tag}...", text_color=APPLE_BLUE)
        self.progress_bar.set(0)

        def _update_worker():
            try:
                app_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
                temp_update_exe = os.path.join(os.environ.get("TEMP", os.getcwd()), f"Update_{latest_tag}.exe")

                req = urllib.request.Request(download_url, headers={"User-Agent": "YouTubeMP3Downloader-App"})
                with urllib.request.urlopen(req, timeout=30) as response, open(temp_update_exe, "wb") as out_file:
                    total_length = response.getheader("content-length")
                    total_length = int(total_length) if total_length else None
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
                                ("status_metric", (f"Downloading {latest_tag}", f"{mb_down:.1f} / {mb_tot:.1f} MB ({progress*100:.0f}%)"))
                            )

                self.download_queue.put(("status", "Update ready! Restarting into new version..."))
                self.download_queue.put(("progress", 1.0))

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
                self.download_queue.put(("error", f"Update failed: {str(e)}"))
                self._set_ui_state(False)

        threading.Thread(target=_update_worker, daemon=True).start()

    def _check_initial_ffmpeg(self):
        """Notify user if ffmpeg was not detected."""
        if not self.ffmpeg_location:
            self.status_label.configure(
                text="FFmpeg not detected",
                text_color=APPLE_ORANGE,
            )
            self.detail_label.configure(text="MP3 conversion requires FFmpeg installed or bundled.")
        else:
            self.detail_label.configure(
                text=f"Engine ready • FFmpeg active"
            )

    def _on_url_change(self, *args):
        """Update playlist mode hint automatically when URL is pasted."""
        url = self.url_var.get().strip()
        if "list=" in url and self.playlist_mode_var.get() == "auto":
            self.detail_label.configure(text="Detected playlist in link")

    def _on_bitrate_changed(self, choice):
        save_user_config(self.download_path_var.get(), choice)

    def paste_url(self):
        try:
            clipboard = self.clipboard_get().strip()
            if clipboard:
                self.url_var.set(clipboard)
        except Exception:
            pass

    def clear_url(self):
        self.url_var.set("")
        if not self.is_downloading:
            self.progress_bar.set(0)
            self.status_label.configure(
                text="Ready to download",
                text_color=APPLE_TEXT,
            )
            self.metric_label.configure(text="")
            self.detail_label.configure(text="Engine ready • FFmpeg active")

    def browse_directory(self):
        selected = filedialog.askdirectory(
            initialdir=self.download_path_var.get(),
            title="Select Destination Folder",
        )
        if selected:
            norm = os.path.normpath(selected)
            self.download_path_var.set(norm)
            save_user_config(norm, self.bitrate_var.get())

    def open_target_folder(self):
        target_path = self.download_path_var.get()
        if os.path.exists(target_path):
            os.startfile(target_path)
        else:
            messagebox.showwarning("Folder Not Found", f"The directory does not exist:\n{target_path}")

    def _set_ui_state(self, downloading: bool):
        self.is_downloading = downloading
        state = "disabled" if downloading else "normal"
        self.download_btn.configure(
            text="Downloading..." if downloading else "Download MP3",
            state=state,
        )
        self.paste_btn.configure(state=state)
        self.clear_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        self.bitrate_menu.configure(state=state)
        self.metadata_switch.configure(state=state)
        self.segmented_playlist.configure(state=state)

    def _check_queue(self):
        """Process GUI updates dispatched from worker thread."""
        try:
            while True:
                msg_type, data = self.download_queue.get_nowait()
                if msg_type == "status":
                    self.status_label.configure(text=data, text_color=APPLE_TEXT)
                elif msg_type == "status_metric":
                    title, metric = data
                    self.status_label.configure(text=title, text_color=APPLE_TEXT)
                    self.metric_label.configure(text=metric)
                elif msg_type == "detail":
                    self.detail_label.configure(text=data)
                elif msg_type == "progress":
                    self.progress_bar.set(data)
                elif msg_type == "warning":
                    self.status_label.configure(text=f"{data}", text_color=APPLE_ORANGE)
                elif msg_type == "error":
                    self.status_label.configure(text=f"Error: {data}", text_color=APPLE_RED)
                    messagebox.showerror("Error", data)
                elif msg_type == "finish":
                    self._set_ui_state(False)
                    self.progress_bar.set(1.0)
                    self.status_label.configure(text="Download complete", text_color=APPLE_GREEN)
                    self.metric_label.configure(text="")
                    messagebox.showinfo("Done", "All tracks downloaded successfully!")
                elif msg_type == "finish_with_errors":
                    self._set_ui_state(False)
                    self.progress_bar.set(1.0)
                    self.status_label.configure(
                        text=f"Finished with skipped tracks",
                        text_color=APPLE_ORANGE,
                    )
                    messagebox.showwarning("Notice", f"Some tracks could not be downloaded:\n{data}")
                elif msg_type == "prompt_update":
                    tag, body, exe_url = data
                    self.update_status_pill.configure(
                        text=f"Update {tag} available",
                        text_color=APPLE_BLUE,
                        fg_color=APPLE_PILL_BLUE_BG,
                    )
                    UpdateDialog(self, tag, body, exe_url)
                elif msg_type == "update_checked":
                    if data:
                        self.update_status_pill.configure(
                            text="✓ Up to date",
                            text_color=APPLE_GREEN,
                            fg_color=APPLE_PILL_GREEN_BG,
                        )
                    else:
                        self.update_status_pill.configure(text="", fg_color="transparent")
                self.download_queue.task_done()
        except queue.Empty:
            pass

        self.after(100, self._check_queue)

    def start_download_thread(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing Link", "Please enter or paste a YouTube link.")
            return

        if not (url.startswith("http://") or url.startswith("https://")):
            messagebox.showwarning("Invalid Link", "Please enter a valid URL starting with http:// or https://")
            return

        if not self.ffmpeg_location:
            self.ffmpeg_location = find_ffmpeg_location()

        save_dir = self.download_path_var.get().strip()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create folder:\n{e}")
                return

        save_user_config(save_dir, self.bitrate_var.get())

        bitrate_str = re.findall(r"\d+", self.bitrate_var.get())
        bitrate_val = bitrate_str[0] if bitrate_str else "320"

        self._set_ui_state(True)
        self.progress_bar.set(0)
        self.status_label.configure(text="Fetching metadata...", text_color=APPLE_TEXT)
        self.metric_label.configure(text="")
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
                    percent_str = f"{fraction * 100:.0f}%"

                speed = d.get("speed")
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else ""
                eta = d.get("eta")
                eta_str = f"ETA {eta}s" if eta else ""

                if total_items[0] > 1:
                    status_text = f"Track {current_item_index[0]} of {total_items[0]}"
                else:
                    filename = os.path.basename(d.get("filename", "audio stream"))
                    clean_name = re.sub(r"\.[^.]+$", "", filename)
                    status_text = f"{clean_name[:42]}"

                metric_text = " • ".join(filter(None, [percent_str, speed_str, eta_str]))
                self.download_queue.put(("status_metric", (status_text, metric_text)))

            elif status == "finished":
                self.download_queue.put(("status", "Converting audio..."))
                self.metric_label.configure(text="")
                self.download_queue.put(("detail", "Extracting MP3 stream with FFmpeg..."))

        class MyCustomLogger:
            def __init__(self, q):
                self.q = q

            def debug(self, msg): pass
            def info(self, msg): pass
            def warning(self, msg):
                if "unavailable" in msg.lower() or "private" in msg.lower():
                    self.q.put(("warning", msg[:80]))
            def error(self, msg): pass

        if playlist_mode == "playlist":
            noplaylist = False
        elif playlist_mode == "single":
            noplaylist = True
        else:
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
                self.download_queue.put(("detail", "Connecting to YouTube..."))
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as ex:
                    self.download_queue.put(("error", f"Could not load link:\n{str(ex)}"))
                    return

                if not info:
                    self.download_queue.put(("error", "No video or playlist found at this link."))
                    return

                if "entries" in info:
                    entries = list(info["entries"])
                    valid_entries = [e for e in entries if e is not None]
                    total_items[0] = max(1, len(valid_entries))
                    p_title = info.get("title", "Playlist")
                    self.download_queue.put(
                        ("status", f"Playlist: {p_title} ({total_items[0]} items)")
                    )
                else:
                    total_items[0] = 1
                    v_title = info.get("title", "Video")
                    self.download_queue.put(("status", f"{v_title}"))

                def each_entry_hook(d):
                    if d.get("status") == "downloading" and d.get("filename"):
                        p_idx = d.get("info_dict", {}).get("playlist_index")
                        current_item_index[0] = p_idx if p_idx else 1

                ydl_opts["progress_hooks"].append(each_entry_hook)
                download_result = ydl.download([url])

                if download_result != 0 and len(skipped_items) > 0:
                    self.download_queue.put(("finish_with_errors", f"{len(skipped_items)} tracks skipped."))
                else:
                    self.download_queue.put(("finish", ""))

        except yt_dlp.utils.DownloadError as de:
            self.download_queue.put(("error", f"Download failed:\n{str(de)}"))
        except Exception as e:
            self.download_queue.put(("error", f"Unexpected error:\n{str(e)}"))


def main():
    app = YouTubeMP3Downloader()
    app.mainloop()


if __name__ == "__main__":
    main()
