# 🎵 YouTube Downloader (v1.2.0)

A clean, modern Windows desktop application for downloading YouTube videos and playlists as **MP3 audio** or **MP4 video** files, styled with Apple's Human Interface Guidelines.

![Application Icon](app_icon.png)

## 🚀 Completely Standalone (Zero Dependencies Needed)

**No Python, FFmpeg, or extra tools required!** Everything is bundled directly into the executable:
- Full Python runtime
- Modern Apple HIG UI (`CustomTkinter`)
- Extraction engine (`yt-dlp`)
- Audio & Video conversion tools (`FFmpeg`, `ffprobe`, `mutagen`, `Pillow`)
- **Seamless In-App Auto-Updater**: Detects new releases on GitHub and downloads/updates directly inside the app!

---

## 📥 Download & Run

1. Go to the [**Releases**](https://github.com/bombdevgif/youtube-mp3-downloader/releases) page.
2. Download `YouTubeMP3Downloader.exe`.
3. Double-click to run! (No installation required).

---

## ✨ Features in v1.2.0

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
  - Playlist tracks are organized into dedicated subfolders named after the playlist title, prefixed with track numbers (`01 - Track Title.mp4` / `.mp3`).
- **Automatic ID3 & Video Metadata Tagging**: Embeds title, artist/creator tags, and thumbnail cover art.
- **Remembers Your Preferences**:
  - Automatically remembers your selected output folder, preferred format, bitrate, and resolution between launches.
- **Automatic In-App Updates**:
  - Directly updates to new releases without browser downloads or manual extraction.
