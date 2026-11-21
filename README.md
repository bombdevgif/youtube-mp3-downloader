# YouTube MP3 Downloader

A clean, modern Windows desktop application built with Python and CustomTkinter for downloading YouTube videos and playlists directly into high-fidelity MP3 audio files.

## Features

- **Modern GUI**: Built with `customtkinter` featuring dark mode styling.
- **URL Handling**: Easy input with one-click **Paste** (from clipboard) and **Clear** buttons.
- **Playlist & Single Video Support**:
  - Auto-detection of playlist URLs.
  - Playlist behavior selector: **Auto Detect**, **Entire Playlist**, or **Single Video Only** (useful if a video URL contains a `&list=` parameter).
  - Dedicated subfolder named after the playlist title when downloading playlists.
  - Automatically prefixes tracks with two-digit indices (e.g. `01 - Song Title.mp3`).
- **Bitrate Selector**: Choose between `128 kbps`, `192 kbps` (default), or `320 kbps` passed directly to `yt-dlp`'s `FFmpegExtractAudio`.
- **Metadata & Cover Embedding**: Automatically embeds ID3 tags (artist, title, album) and thumbnail cover into the MP3 file.
- **Directory Picker**: Browse and choose any folder to save your audio files (defaults to your Windows Downloads folder). Includes an **Open Folder** button.
- **Multi-threaded & Responsive**: Downloads run in background worker threads so the interface never freezes, accompanied by a real-time progress bar and track progress indicators.
- **Resilient Error Handling**: Tolerates private/deleted videos in playlists by skipping them without interrupting the batch, with popups and status notifications.
- **Automatic FFmpeg Detection**: Automatically discovers `ffmpeg` in standard PATH as well as local WinGet packages.

## Quick Start

### Launch with Batch File
Simply double-click:
```bat
run.bat
```

### Launch via Terminal
```powershell
python main.py
```
*(Or specify Python path if not registered in system PATH: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe main.py`)*

## Requirements
Listed in [requirements.txt](file:///e:/code/youtube%20mp3/requirements.txt):
- `customtkinter`
- `yt-dlp`
- `Pillow`
- `mutagen`
- `ffmpeg` (installed via WinGet / system PATH)
