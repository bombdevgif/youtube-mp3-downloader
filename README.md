# 🎵 YouTube to MP3 Downloader

A clean, modern Windows desktop application for downloading YouTube videos and playlists directly into high-fidelity MP3 audio files.

![Application Icon](app_icon.png)

## 🚀 Completely Standalone (Zero Dependencies Needed)

**No Python, FFmpeg, or extra tools required!** Everything is bundled directly into the executable:
- Full Python runtime
- Modern Dark UI (`CustomTkinter`)
- Extraction engine (`yt-dlp`)
- Audio conversion & metadata tools (`FFmpeg`, `ffprobe`, `mutagen`, `Pillow`)
- **Seamless In-App Auto-Updater**: Detects new releases on GitHub and downloads/updates directly inside the app!

---

## 📥 Download & Run

1. Go to the [**Releases**](https://github.com/bombdevgif/youtube-mp3-downloader/releases) page.
2. Download `YouTubeMP3Downloader.exe`.
3. Double-click to run! (No installation required).

---

## ✨ Features

- **Automatic In-App Updates**:
  - Whenever the application launches, it automatically checks the GitHub repository for newer releases.
  - If a newer version exists, a dialog appears showing release notes.
  - Clicking **Update Now** downloads the new executable directly inside the app and restarts into the new version seamlessly without manual browser visits or folder extractions.
- **Auto-Versioning & Automated GitHub Releases**:
  - Every push to GitHub triggers a GitHub Action workflow that automatically increments the patch version (e.g., `1.0.1` -> `1.0.2`), builds the single-file binary with bundled FFmpeg, and publishes a new GitHub Release.
- **Adaptive Responsive UI**:
  - Automatically adjusts to any window dimensions (maximized, resized, or compact) with a scrollable container so the **Start Download** button and controls are always reachable.
- **Remembers Selected Folder**:
  - Automatically saves and reloads your previously chosen destination folder between sessions.
- **Highest Bitrate by Default**:
  - Defaults to **320 kbps (Best)** audio quality.
- **Single Videos & Full Playlists**:
  - Automatically detects playlists.
  - Option to download either the entire playlist or just a single video (even if the link contains `&list=`).
  - Playlist tracks are organized into dedicated subfolders named after the playlist title, prefixed with track numbers (`01 - Track Title.mp3`).
- **Automatic ID3 Tagging & Artwork**: Embeds artist, title, album tags, and thumbnail cover art directly into the MP3.
- **Asynchronous & Non-Blocking**: Runs downloads in background threads with live progress bars, speed, ETA, and percentage counters.
- **Resilient**: Skips deleted or private videos in playlists without halting the download batch.
