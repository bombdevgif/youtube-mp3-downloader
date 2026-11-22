# 🎵 YouTube Downloader (v2.0.0)

A high-performance, modern native desktop application built in **Rust** for downloading YouTube videos and playlists as **MP3 audio** or **MP4 video** files, styled with Apple's Human Interface Guidelines.

![Application Icon](app_icon.png)

## 🚀 Completely Standalone & Rewritten in Rust (v2.0.0)

**Zero runtime overhead, instant native startup, and completely self-contained!**
- **Native Rust Engine**: Built with Rust, `egui`/`eframe`, and low-level multithreading for zero idle CPU overhead and ultra-fast, snappy responsiveness.
- **Embedded Tools**: `yt-dlp` and `FFmpeg` are embedded into the standalone binary and managed automatically. No external tools or runtimes required.
- **Apple Human Interface Guidelines Design**: Clean typography, inset grouped cards, smooth theme toggle (Dark Mode default / Light Mode), subtle borders, and Apple System Blue accents.
- **Seamless In-App Auto-Updater**: Detects new releases on GitHub and downloads/updates directly inside the app with a single click.

---

## 📥 Download & Run

1. Go to the [**Releases**](https://github.com/bombdevgif/youtube-mp3-downloader/releases) page.
2. Download `YouTubeMP3Downloader.exe`.
3. Double-click to run! (No installation required).

> **Note on Windows SmartScreen**: The executable is signed with an Authenticode certificate for `bombdevgif`. You can import `bombdevgif.cer` by running `Trust-Certificate.bat` as Administrator to mark the publisher as trusted, or click **"More info"** → **"Run anyway"**.

---

## ✨ Features in v2.0.0

- **Complete Native Rust Rewrite**:
  - Re-engineered from Python to pure Rust for maximum execution speed, low memory footprint, and zero idle CPU cycles.
- **Light & Dark Mode Switch (Dark by Default)**:
  - Apple-style native toggle switch (`🌙 Dark` / `☀️ Light`).
  - Seamlessly transforms cards, text, entries, and borders with full contrast.
- **Dual Format Support: MP3 Audio & MP4 Video**:
  - Segmented control to seamlessly switch between **MP3 Audio** and **MP4 Video**.
  - **Resolution Selector**: Choose from `Best Available`, `2160p (4K)`, `1440p (2K)`, `1080p (FHD)`, `720p (HD)`, or `480p (SD)`.
  - **Bitrate Selector**: Choose between `320 kbps (Best)`, `192 kbps (Standard)`, or `128 kbps (Compact)` when downloading MP3s.
- **Apple Human Interface Guidelines Design**:
  - Inset grouped cards, hairline borders, rich dark surfaces, and native typography.
  - Non-intrusive status pills in the toolbar (`✓ Up to date` or update notification).
- **Single Videos & Full Playlists**:
  - Automatically detects playlists.
  - Option to download either the entire playlist or just a single video (even if the link contains `&list=`).
  - Playlist tracks are organized into dedicated subfolders named after the playlist title, prefixed with track numbers.
- **Automatic ID3 & Video Metadata Tagging**: Embeds title, artist/creator tags, and thumbnail cover art.
- **Automatic In-App Updates**:
  - Pop-up modal with changelog and a direct **Install Update & Restart** button that downloads and restarts the app automatically without manual installation.
