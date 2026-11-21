"""
YouTube MP3 Downloader - Desktop GUI Application
Modern CustomTkinter desktop interface for downloading YouTube videos and playlists as MP3.
"""

import os
import sys
import re
import shutil
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    import tkinter as ctk

import yt_dlp

# Set appearance and theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def find_ffmpeg_location():
    """Detect ffmpeg binary location on system or winget packages."""
    # 1. Standard PATH check
    path_ffmpeg = shutil.which("ffmpeg")
    if path_ffmpeg:
        return os.path.dirname(os.path.abspath(path_ffmpeg))

    # 2. Check WinGet package directories
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

    # Search in WinGet directory dynamically if not found yet
    winget_packages = os.path.join(user_profile, "AppData", "Local", "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_packages):
        for root, _, files in os.walk(winget_packages):
            if "ffmpeg.exe" in files:
                return root

    return None


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class YouTubeMP3Downloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube to MP3 Downloader")
        self.geometry("740x650")
        self.minsize(680, 580)

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

        # Default download path (Windows Downloads)
        default_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(default_folder):
            default_folder = os.getcwd()
        self.download_path_var = tk.StringVar(value=default_folder)

        # URL variable
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)

        # Options
        self.bitrate_var = tk.StringVar(value="192 kbps")
        self.playlist_mode_var = tk.StringVar(value="auto")  # "auto", "playlist", "single"
        self.embed_metadata_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._check_queue()
        self._check_initial_ffmpeg()

    def _build_ui(self):
        # Configure layout grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main Scrollable / Container Frame
        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray92", "#1e1e24"))
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header Title & Subtitle
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        title_label = ctk.CTkLabel(
            header_frame,
            text="🎵 YouTube to MP3 Downloader",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Download single videos or full playlists in high-fidelity MP3 with metadata",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray70"),
        )
        subtitle_label.pack(anchor="w", pady=(2, 0))

        # ---------------- Section 1: URL Input ----------------
        url_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        url_frame.pack(fill="x", padx=20, pady=10)
        url_frame.grid_columnconfigure(0, weight=1)

        url_label = ctk.CTkLabel(
            url_frame,
            text="YouTube Video or Playlist URL:",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        url_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(12, 5))

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
            width=85,
            height=38,
            command=self.paste_url,
            font=ctk.CTkFont(size=12),
        )
        self.paste_btn.grid(row=1, column=1, padx=4, pady=(0, 12))

        self.clear_btn = ctk.CTkButton(
            url_frame,
            text="✕ Clear",
            width=75,
            height=38,
            fg_color=("gray60", "gray35"),
            hover_color=("gray50", "gray45"),
            command=self.clear_url,
            font=ctk.CTkFont(size=12),
        )
        self.clear_btn.grid(row=1, column=2, padx=(4, 15), pady=(0, 12))

        # ---------------- Section 2: Download Options ----------------
        options_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        options_frame.pack(fill="x", padx=20, pady=10)
        options_frame.grid_columnconfigure(1, weight=1)

        # Quality selector
        bitrate_label = ctk.CTkLabel(
            options_frame,
            text="Audio Bitrate:",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        bitrate_label.grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))

        self.bitrate_menu = ctk.CTkOptionMenu(
            options_frame,
            values=["128 kbps", "192 kbps", "320 kbps"],
            variable=self.bitrate_var,
            width=140,
        )
        self.bitrate_menu.grid(row=0, column=1, sticky="w", padx=10, pady=(12, 8))

        # Playlist mode selector
        playlist_label = ctk.CTkLabel(
            options_frame,
            text="Playlist Behavior:",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        playlist_label.grid(row=1, column=0, sticky="w", padx=15, pady=8)

        playlist_options_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        playlist_options_frame.grid(row=1, column=1, sticky="w", padx=10, pady=8)

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
        self.metadata_chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(8, 12))

        # ---------------- Section 3: Save Location ----------------
        save_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        save_frame.pack(fill="x", padx=20, pady=10)
        save_frame.grid_columnconfigure(0, weight=1)

        save_label = ctk.CTkLabel(
            save_frame,
            text="Save Location:",
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
            width=100,
            height=36,
            command=self.browse_directory,
            font=ctk.CTkFont(size=12),
        )
        self.browse_btn.grid(row=1, column=1, padx=(0, 15), pady=(0, 12))

        # ---------------- Section 4: Progress & Status ----------------
        progress_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray85", "#282830"), corner_radius=10)
        progress_frame.pack(fill="x", padx=20, pady=10)

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready. Paste a YouTube link and click Download.",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray85"),
            wraplength=640,
            justify="left",
        )
        self.status_label.pack(anchor="w", padx=15, pady=(12, 6))

        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=12)
        self.progress_bar.pack(fill="x", padx=15, pady=(4, 8))
        self.progress_bar.set(0)

        self.detail_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray65"),
        )
        self.detail_label.pack(anchor="w", padx=15, pady=(0, 12))

        # ---------------- Action Buttons ----------------
        action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        action_frame.pack(fill="x", padx=20, pady=(10, 20))

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
            width=130,
            font=ctk.CTkFont(size=13),
            command=self.open_target_folder,
            fg_color=("gray60", "gray35"),
            hover_color=("gray50", "gray45"),
        )
        self.open_folder_btn.pack(side="right")

    def _check_initial_ffmpeg(self):
        """Notify user if ffmpeg was not detected."""
        if not self.ffmpeg_location:
            self.status_label.configure(
                text="⚠️ Warning: FFmpeg not detected. MP3 conversion requires FFmpeg installed.",
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
        """Open directory picker dialog."""
        selected = filedialog.askdirectory(
            initialdir=self.download_path_var.get(),
            title="Select Destination Folder",
        )
        if selected:
            self.download_path_var.set(os.path.normpath(selected))

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

        # Parse selected bitrate (e.g. '192 kbps' -> '192')
        bitrate_str = self.bitrate_var.get().split()[0]

        self._set_ui_state(True)
        self.progress_bar.set(0)
        self.status_label.configure(text="Fetching video/playlist metadata...", text_color=("gray30", "gray85"))
        self.detail_label.configure(text="Connecting to YouTube...")

        worker = threading.Thread(
            target=self._download_worker,
            args=(
                url,
                save_dir,
                bitrate_str,
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
                    # Overall progress calculation if playlist
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
                # Don't spam warnings, but log if track is unavailable
                if "unavailable" in msg.lower() or "private" in msg.lower():
                    self.q.put(("warning", msg[:100]))

            def error(self, msg):
                # We handle errors via exception or list
                pass

        # Configure yt-dlp parameters
        is_playlist = False
        if playlist_mode == "playlist":
            noplaylist = False
        elif playlist_mode == "single":
            noplaylist = True
        else:  # "auto"
            # If list is in url, inspect it
            noplaylist = "list=" not in url

        # Output template logic
        # For playlist: Save in dedicated folder <save_dir>/<playlist_title>/<track_number> - <title>.mp3
        # For single: <save_dir>/<title>.mp3
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
            "ignoreerrors": True,  # Continues playlist even if individual tracks are private/deleted
            "quiet": True,
            "no_warnings": False,
            "writethumbnail": embed_metadata,
        }

        if ffmpeg_loc:
            ydl_opts["ffmpeg_location"] = ffmpeg_loc

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Pre-fetch info to get track count
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
                    # Filter None entries (unavailable videos)
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

                # Define a hook or counter to increment current_item_index
                def each_entry_hook(d):
                    if d.get("status") == "downloading" and d.get("filename"):
                        # If playlist index is present
                        p_idx = d.get("info_dict", {}).get("playlist_index")
                        if p_idx:
                            current_item_index[0] = p_idx
                        else:
                            current_item_index[0] = 1

                ydl_opts["progress_hooks"].append(each_entry_hook)

                # Execute actual download
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
