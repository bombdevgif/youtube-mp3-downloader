# 🎵 YouTube to MP3 Downloader

A clean, modern Windows desktop application for downloading YouTube videos and playlists directly into high-fidelity MP3 audio files.

![Application Icon](app_icon.png)

## 🚀 Completely Standalone (Zero Dependencies Needed)

**No Python, FFmpeg, or extra tools required!** Everything is bundled directly into the executable:
- Full Python runtime
- Modern Dark UI (`CustomTkinter`)
- Extraction engine (`yt-dlp`)
- Audio conversion & metadata tools (`FFmpeg`, `ffprobe`, `mutagen`, `Pillow`)

---

## 📥 Download & Run

1. Go to the [**Releases**](https://github.com/bombdevgif/youtube-mp3-downloader/releases) page.
2. Download `YouTubeMP3Downloader.exe`.
3. Double-click to run! (No installation required).

---

## ✨ Features

- **Modern Dark UI**: Clean, responsive interface built with CustomTkinter.
- **Single Videos & Full Playlists**:
  - Automatically detects playlists.
  - Option to download either the entire playlist or just a single video (even if the link contains `&list=`).
  - Playlist tracks are neatly organized into a dedicated subfolder named after the playlist title, prefixed with track numbers (`01 - Track Title.mp3`).
- **Bitrate Selector**: Choose between `128 kbps`, `192 kbps` (default), or `320 kbps`.
- **Automatic ID3 Tagging & Artwork**: Embeds artist, title, album tags, and thumbnail cover art directly into the MP3.
- **Save Location Picker**: Choose where files are saved (defaults to Windows `Downloads`). Includes a quick "Open Folder" button.
- **Asynchronous & Non-Blocking**: Runs downloads in background threads with live progress bars, speed, ETA, and percentage counters.
- **Resilient**: Skips deleted or private videos in playlists without halting the download batch.

---

## 🛠️ For Developers / Building from Source

If you prefer to run or build from source code:

### Requirements
- Python 3.10+
- FFmpeg (accessible in PATH or installed via `winget install Gyan.FFmpeg`)

### Setup & Run
```powershell
pip install -r requirements.txt
python main.py
```
Or run `run.bat`.

### Build Standalone Executable
```powershell
pyinstaller --noconfirm --onefile --windowed `
  --name "YouTubeMP3Downloader" `
  --icon "app_icon.ico" `
  --add-data "<PATH_TO_CUSTOMTKINTER>;customtkinter" `
  --add-data "app_icon.ico;." `
  --add-binary "<PATH_TO_FFMPEG>\ffmpeg.exe;." `
  --add-binary "<PATH_TO_FFMPEG>\ffprobe.exe;." `
  --copy-metadata yt-dlp "main.py"
```
