#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use eframe::egui::{self, Color32, Margin, RichText, Rounding, Stroke, Vec2};
use serde::{Deserialize, Serialize};
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::Arc;
use std::thread;

pub const APP_VERSION: &str = "2.0.0";
const GITHUB_REPO: &str = "bombdevgif/youtube-mp3-downloader";

// Bundled binaries
const YTDLP_BYTES: &[u8] = include_bytes!("D:\\Tools\\yt-dlp.exe");
const FFMPEG_BYTES: &[u8] = include_bytes!("D:\\Tools\\FFmpeg\\ffmpeg-9.1-full_build\\bin\\ffmpeg.exe");
const FFPROBE_BYTES: &[u8] = include_bytes!("D:\\Tools\\FFmpeg\\ffmpeg-9.1-full_build\\bin\\ffprobe.exe");

// Apple HIG Palette
const APPLE_BLUE: Color32 = Color32::from_rgb(0, 122, 255);
const APPLE_GREEN: Color32 = Color32::from_rgb(52, 199, 89);

#[derive(Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub save_dir: String,
    pub format_mode: String,
    pub bitrate: String,
    pub resolution: String,
    pub appearance_mode: String,
}

impl Default for AppConfig {
    fn default() -> Self {
        let dl = dirs::download_dir().unwrap_or_else(|| PathBuf::from("."));
        Self {
            save_dir: dl.to_string_lossy().to_string(),
            format_mode: "MP3 Audio".to_string(),
            bitrate: "320 kbps (Best)".to_string(),
            resolution: "1080p (FHD)".to_string(),
            appearance_mode: "Dark".to_string(),
        }
    }
}

fn config_path() -> PathBuf {
    let mut p = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
    p.push("YouTubeMP3Downloader");
    let _ = fs::create_dir_all(&p);
    p.push("config.json");
    p
}

fn load_config() -> AppConfig {
    let cp = config_path();
    if let Ok(data) = fs::read_to_string(&cp) {
        if let Ok(cfg) = serde_json::from_str::<AppConfig>(&data) {
            return cfg;
        }
    }
    AppConfig::default()
}

fn save_config(cfg: &AppConfig) {
    let cp = config_path();
    if let Ok(data) = serde_json::to_string_pretty(cfg) {
        let _ = fs::write(cp, data);
    }
}

fn ensure_tools_extracted() -> Result<PathBuf, String> {
    let base = dirs::cache_dir().unwrap_or_else(std::env::temp_dir);
    let bin_dir = base.join("YouTubeDownloader_Bin");
    fs::create_dir_all(&bin_dir).map_err(|e| e.to_string())?;

    let ytdlp_path = bin_dir.join("yt-dlp.exe");
    if !ytdlp_path.exists() || fs::metadata(&ytdlp_path).map(|m| m.len()).unwrap_or(0) != YTDLP_BYTES.len() as u64 {
        let _ = fs::write(&ytdlp_path, YTDLP_BYTES);
    }

    let ffmpeg_path = bin_dir.join("ffmpeg.exe");
    if !ffmpeg_path.exists() || fs::metadata(&ffmpeg_path).map(|m| m.len()).unwrap_or(0) != FFMPEG_BYTES.len() as u64 {
        let _ = fs::write(&ffmpeg_path, FFMPEG_BYTES);
    }

    let ffprobe_path = bin_dir.join("ffprobe.exe");
    if !ffprobe_path.exists() || fs::metadata(&ffprobe_path).map(|m| m.len()).unwrap_or(0) != FFPROBE_BYTES.len() as u64 {
        let _ = fs::write(&ffprobe_path, FFPROBE_BYTES);
    }

    Ok(bin_dir)
}

#[derive(Clone, Debug)]
pub enum UiMessage {
    Status(String),
    StatusMetric(String, String),
    Detail(String),
    Progress(f32),
    Error(String),
    Finished(bool),
    UpdateAvailable { tag: String, body: String, url: String },
    UpdateChecked(String),
}

pub struct YouTubeDownloaderApp {
    config: AppConfig,
    url_input: String,
    playlist_mode: String,
    embed_metadata: bool,
    is_downloading: bool,
    status_text: String,
    metric_text: String,
    detail_text: String,
    progress_val: f32,
    update_pill: String,
    update_pill_color: Color32,
    show_update_modal: bool,
    update_tag: String,
    update_notes: String,
    update_url: String,
    rx: Receiver<UiMessage>,
    tx: Sender<UiMessage>,
    cancel_flag: Arc<AtomicBool>,
    active_child: Arc<std::sync::Mutex<Option<u32>>>,
}

impl YouTubeDownloaderApp {
    pub fn new(cc: &eframe::CreationContext<'_>) -> Self {
        let (tx, rx) = channel();
        let config = load_config();

        // Configure visuals for Apple Dark/Light aesthetics
        let is_dark = config.appearance_mode == "Dark";
        let visuals = if is_dark {
            let mut v = egui::Visuals::dark();
            v.panel_fill = Color32::from_rgb(28, 28, 30);
            v.window_fill = Color32::from_rgb(44, 44, 46);
            v.widgets.noninteractive.bg_fill = Color32::from_rgb(44, 44, 46);
            v.widgets.noninteractive.bg_stroke = Stroke::new(1.0_f32, Color32::from_rgb(56, 56, 58));
            v.widgets.inactive.bg_fill = Color32::from_rgb(36, 36, 38);
            v.widgets.inactive.bg_stroke = Stroke::new(1.0_f32, Color32::from_rgb(56, 56, 58));
            v.widgets.hovered.bg_fill = Color32::from_rgb(54, 54, 56);
            v.widgets.active.bg_fill = Color32::from_rgb(60, 60, 64);
            v
        } else {
            let mut v = egui::Visuals::light();
            v.panel_fill = Color32::from_rgb(245, 245, 247);
            v.window_fill = Color32::from_rgb(255, 255, 255);
            v.widgets.noninteractive.bg_fill = Color32::from_rgb(255, 255, 255);
            v.widgets.noninteractive.bg_stroke = Stroke::new(1.0_f32, Color32::from_rgb(229, 229, 234));
            v.widgets.inactive.bg_fill = Color32::from_rgb(249, 249, 251);
            v.widgets.inactive.bg_stroke = Stroke::new(1.0_f32, Color32::from_rgb(229, 229, 234));
            v.widgets.hovered.bg_fill = Color32::from_rgb(240, 240, 242);
            v.widgets.active.bg_fill = Color32::from_rgb(230, 230, 235);
            v
        };
        cc.egui_ctx.set_visuals(visuals);

        let app = Self {
            config,
            url_input: String::new(),
            playlist_mode: "auto".to_string(),
            embed_metadata: true,
            is_downloading: false,
            status_text: "Ready to download".to_string(),
            metric_text: String::new(),
            detail_text: "Engine ready • Standalone Rust 2.0 active".to_string(),
            progress_val: 0.0,
            update_pill: "Checking for updates...".to_string(),
            update_pill_color: Color32::from_rgb(134, 134, 139),
            show_update_modal: false,
            update_tag: String::new(),
            update_notes: String::new(),
            update_url: String::new(),
            rx,
            tx: tx.clone(),
            cancel_flag: Arc::new(AtomicBool::new(false)),
            active_child: Arc::new(std::sync::Mutex::new(None)),
        };

        // Background update check
        let tx_up = tx.clone();
        thread::spawn(move || {
            thread::sleep(std::time::Duration::from_millis(1000));
            let url = format!("https://api.github.com/repos/{}/releases/latest", GITHUB_REPO);
            if let Ok(resp) = ureq::get(&url)
                .header("User-Agent", "YouTubeDownloader-Rust")
                .call()
            {
                if let Ok(body) = resp.into_body().read_to_string() {
                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(&body) {
                        let tag = json.get("tag_name").and_then(|t| t.as_str()).unwrap_or("");
                        let notes = json.get("body").and_then(|b| b.as_str()).unwrap_or("");
                        let mut exe_url = String::new();
                        if let Some(assets) = json.get("assets").and_then(|a| a.as_array()) {
                            for a in assets {
                                if let Some(n) = a.get("name").and_then(|name| name.as_str()) {
                                    if n.ends_with(".exe") {
                                        if let Some(dl) = a.get("browser_download_url").and_then(|u| u.as_str()) {
                                            exe_url = dl.to_string();
                                            break;
                                        }
                                    }
                                }
                            }
                        }

                        let cur_clean = APP_VERSION.trim_start_matches('v');
                        let tag_clean = tag.trim_start_matches('v');
                        if is_newer_version(tag_clean, cur_clean) && !exe_url.is_empty() {
                            let _ = tx_up.send(UiMessage::UpdateAvailable {
                                tag: tag.to_string(),
                                body: notes.to_string(),
                                url: exe_url,
                            });
                            return;
                        } else {
                            let _ = tx_up.send(UiMessage::UpdateChecked("✓ Up to date".to_string()));
                            return;
                        }
                    }
                }
            }
            let _ = tx_up.send(UiMessage::UpdateChecked("".to_string()));
        });

        app
    }

    fn start_download(&mut self) {
        let url = self.url_input.trim().to_string();
        if url.is_empty() || (!url.starts_with("http://") && !url.starts_with("https://")) {
            self.status_text = "Please enter a valid YouTube URL".to_string();
            return;
        }

        self.is_downloading = true;
        self.progress_val = 0.0;
        self.status_text = "Preparing download engine...".to_string();
        self.metric_text = String::new();
        self.detail_text = "Extracting bundled tools...".to_string();
        self.cancel_flag.store(false, Ordering::SeqCst);

        let bin_dir = match ensure_tools_extracted() {
            Ok(d) => d,
            Err(e) => {
                self.is_downloading = false;
                self.status_text = format!("Initialization error: {}", e);
                return;
            }
        };

        let tx = self.tx.clone();
        let cancel = self.cancel_flag.clone();
        let child_store = self.active_child.clone();
        let save_dir = self.config.save_dir.clone();
        let format_mode = self.config.format_mode.clone();
        let bitrate_str = self.config.bitrate.clone();
        let resolution_str = self.config.resolution.clone();
        let playlist_mode = self.playlist_mode.clone();
        let embed_meta = self.embed_metadata;

        thread::spawn(move || {
            let ytdlp_bin = bin_dir.join("yt-dlp.exe");
            let ffmpeg_bin = bin_dir.join("ffmpeg.exe");

            let mut args: Vec<String> = Vec::new();
            args.push("--ffmpeg-location".to_string());
            args.push(ffmpeg_bin.to_string_lossy().to_string());
            args.push("--newline".to_string());
            args.push("--ignore-errors".to_string());

            let is_playlist_mode = match playlist_mode.as_str() {
                "playlist" => true,
                "single" => false,
                _ => url.contains("list="),
            };

            if is_playlist_mode {
                args.push("--yes-playlist".to_string());
                let template = format!("{}/%(playlist,playlist_title)s/%(playlist_index)02d - %(title)s.%(ext)s", save_dir);
                args.push("-o".to_string());
                args.push(template);
            } else {
                args.push("--no-playlist".to_string());
                let template = format!("{}/%(title)s.%(ext)s", save_dir);
                args.push("-o".to_string());
                args.push(template);
            }

            if format_mode == "MP3 Audio" {
                args.push("-x".to_string());
                args.push("--audio-format".to_string());
                args.push("mp3".to_string());
                let br_clean: String = bitrate_str.chars().filter(|c| c.is_ascii_digit()).collect();
                let br = if br_clean.is_empty() { "320" } else { &br_clean };
                args.push("--audio-quality".to_string());
                args.push(format!("{}K", br));
            } else {
                let res_clean: String = resolution_str.chars().filter(|c| c.is_ascii_digit()).collect();
                if let Ok(height) = res_clean.parse::<u32>() {
                    let fmt = format!("bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best", h = height);
                    args.push("-f".to_string());
                    args.push(fmt);
                } else {
                    args.push("-f".to_string());
                    args.push("bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best".to_string());
                }
                args.push("--merge-output-format".to_string());
                args.push("mp4".to_string());
            }

            if embed_meta {
                args.push("--add-metadata".to_string());
                args.push("--embed-thumbnail".to_string());
            }

            args.push(url);

            let mut cmd = Command::new(&ytdlp_bin);
            cmd.args(&args)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped());

            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
            }

            let mut child = match cmd.spawn() {
                Ok(c) => c,
                Err(e) => {
                    let _ = tx.send(UiMessage::Error(format!("Failed to start downloader: {}", e)));
                    let _ = tx.send(UiMessage::Finished(false));
                    return;
                }
            };

            if let Ok(mut g) = child_store.lock() {
                *g = Some(child.id());
            }

            if let Some(stdout) = child.stdout.take() {
                let reader = BufReader::new(stdout);
                for line in reader.lines().flatten() {
                    if cancel.load(Ordering::SeqCst) {
                        let _ = child.kill();
                        let _ = tx.send(UiMessage::Status("Download cancelled".to_string()));
                        let _ = tx.send(UiMessage::Finished(false));
                        return;
                    }

                    parse_ytdlp_line(&line, &tx);
                }
            }

            let status = child.wait();
            if let Ok(mut g) = child_store.lock() {
                *g = None;
            }

            match status {
                Ok(s) if s.success() => {
                    let _ = tx.send(UiMessage::Progress(1.0));
                    let _ = tx.send(UiMessage::Status("Download complete".to_string()));
                    let _ = tx.send(UiMessage::Detail("Finished processing media file(s)".to_string()));
                    let _ = tx.send(UiMessage::Finished(true));
                }
                _ => {
                    let _ = tx.send(UiMessage::Finished(false));
                }
            }
        });
    }

    fn start_in_app_update(&mut self, url: String, tag: String) {
        self.is_downloading = true;
        self.status_text = format!("Downloading update {}...", tag);
        self.progress_val = 0.0;
        let tx = self.tx.clone();

        thread::spawn(move || {
            let temp_dir = std::env::temp_dir();
            let update_exe = temp_dir.join(format!("Update_{}.exe", tag));
            let cur_exe = match std::env::current_exe() {
                Ok(p) => p,
                Err(e) => {
                    let _ = tx.send(UiMessage::Error(format!("Could not locate current app: {}", e)));
                    let _ = tx.send(UiMessage::Finished(false));
                    return;
                }
            };

            if let Ok(resp) = ureq::get(&url).header("User-Agent", "YouTubeDownloader-Rust").call() {
                let len = resp.headers()
                    .get("content-length")
                    .and_then(|v| v.to_str().ok())
                    .and_then(|v| v.parse::<usize>().ok())
                    .unwrap_or(0);

                let mut reader = resp.into_body().into_reader();
                if let Ok(mut file) = File::create(&update_exe) {
                    let mut buffer = [0u8; 1024 * 256];
                    let mut downloaded = 0usize;
                    let mut last_progress = std::time::Instant::now();

                    loop {
                        match std::io::Read::read(&mut reader, &mut buffer) {
                            Ok(0) => break,
                            Ok(n) => {
                                if file.write_all(&buffer[..n]).is_err() {
                                    break;
                                }
                                downloaded += n;
                                if len > 0 && (last_progress.elapsed().as_millis() > 100 || downloaded >= len) {
                                    last_progress = std::time::Instant::now();
                                    let frac = downloaded as f32 / len as f32;
                                    let _ = tx.send(UiMessage::Progress(frac));
                                    let mb_cur = downloaded as f32 / 1048576.0;
                                    let mb_tot = len as f32 / 1048576.0;
                                    let _ = tx.send(UiMessage::StatusMetric(
                                        format!("Downloading {}", tag),
                                        format!("{:.1} / {:.1} MB ({:.0}%)", mb_cur, mb_tot, frac * 100.0),
                                    ));
                                }
                            }
                            Err(_) => break,
                        }
                    }

                    let bat_script = format!(
                        "@echo off\r\ntimeout /t 2 /nobreak >nul\r\nmove /y \"{}\" \"{}\"\r\nstart \"\" \"{}\"\r\ndel \"%~f0\"\r\n",
                        update_exe.to_string_lossy(),
                        cur_exe.to_string_lossy(),
                        cur_exe.to_string_lossy()
                    );
                    let bat_path = temp_dir.join("apply_update.bat");
                    let _ = fs::write(&bat_path, bat_script);

                    let mut cmd = Command::new("cmd.exe");
                    cmd.args(["/c", &bat_path.to_string_lossy()]);
                    #[cfg(target_os = "windows")]
                    {
                        use std::os::windows::process::CommandExt;
                        cmd.creation_flags(0x08000000);
                    }
                    let _ = cmd.spawn();
                    std::process::exit(0);
                }
            }
            let _ = tx.send(UiMessage::Error("Update download failed".to_string()));
            let _ = tx.send(UiMessage::Finished(false));
        });
    }
}

fn parse_ytdlp_line(line: &str, tx: &Sender<UiMessage>) {
    let trimmed = line.trim();
    if trimmed.starts_with("[download]") {
        if trimmed.contains('%') {
            let parts: Vec<&str> = trimmed.split_whitespace().collect();
            let mut pct = None;
            let mut speed = None;
            let mut eta = None;

            for (i, p) in parts.iter().enumerate() {
                if p.ends_with('%') {
                    if let Ok(v) = p.trim_end_matches('%').parse::<f32>() {
                        pct = Some(v / 100.0);
                    }
                }
                if p.ends_with("/s") {
                    speed = Some(*p);
                }
                if *p == "ETA" && i + 1 < parts.len() {
                    eta = Some(parts[i + 1]);
                }
            }

            if let Some(p) = pct {
                let _ = tx.send(UiMessage::Progress(p));
                let metric = format!(
                    "{:.0}% • {} • ETA {}",
                    p * 100.0,
                    speed.unwrap_or(""),
                    eta.unwrap_or("")
                );
                let _ = tx.send(UiMessage::StatusMetric("Downloading stream...".to_string(), metric));
            }
        } else if trimmed.contains("Destination:") {
            if let Some(dest) = trimmed.split("Destination:").nth(1) {
                let fname = Path::new(dest.trim()).file_name().and_then(|f| f.to_str()).unwrap_or("");
                let _ = tx.send(UiMessage::Detail(format!("Writing: {}", fname)));
            }
        }
    } else if trimmed.starts_with("[ExtractAudio]") {
        let _ = tx.send(UiMessage::Status("Converting audio...".to_string()));
        let _ = tx.send(UiMessage::Detail("Extracting high quality MP3 audio stream...".to_string()));
    } else if trimmed.starts_with("[Merger]") {
        let _ = tx.send(UiMessage::Status("Multiplexing video...".to_string()));
        let _ = tx.send(UiMessage::Detail("Merging MP4 video and audio streams...".to_string()));
    }
}

fn is_newer_version(remote: &str, local: &str) -> bool {
    let r_parts: Vec<u32> = remote.split('.').filter_map(|s| s.parse().ok()).collect();
    let l_parts: Vec<u32> = local.split('.').filter_map(|s| s.parse().ok()).collect();
    for i in 0..std::cmp::max(r_parts.len(), l_parts.len()) {
        let r = r_parts.get(i).copied().unwrap_or(0);
        let l = l_parts.get(i).copied().unwrap_or(0);
        if r > l {
            return true;
        } else if r < l {
            return false;
        }
    }
    false
}

impl eframe::App for YouTubeDownloaderApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Drain message queue
        while let Ok(msg) = self.rx.try_recv() {
            match msg {
                UiMessage::Status(s) => self.status_text = s,
                UiMessage::StatusMetric(s, m) => {
                    self.status_text = s;
                    self.metric_text = m;
                }
                UiMessage::Detail(d) => self.detail_text = d,
                UiMessage::Progress(p) => self.progress_val = p,
                UiMessage::Error(e) => {
                    self.status_text = format!("Error: {}", e);
                    self.is_downloading = false;
                }
                UiMessage::Finished(success) => {
                    self.is_downloading = false;
                    if success {
                        self.progress_val = 1.0;
                    }
                }
                UiMessage::UpdateAvailable { tag, body, url } => {
                    self.update_pill = format!("Update {} available", tag);
                    self.update_pill_color = APPLE_BLUE;
                    self.update_tag = tag;
                    self.update_notes = body;
                    self.update_url = url;
                    self.show_update_modal = true;
                }
                UiMessage::UpdateChecked(p) => {
                    self.update_pill = p;
                    self.update_pill_color = APPLE_GREEN;
                }
            }
        }

        // Render Update Modal Sheet if open
        if self.show_update_modal {
            egui::Window::new(format!("Software Update: {}", self.update_tag))
                .collapsible(false)
                .resizable(false)
                .anchor(egui::Align2::CENTER_CENTER, Vec2::ZERO)
                .fixed_size(Vec2::new(480.0, 320.0))
                .show(ctx, |ui| {
                    ui.add_space(8.0);
                    ui.heading("A new version of YouTube Downloader is ready to install.");
                    ui.add_space(6.0);
                    ui.label(RichText::new("Release Notes:").strong());

                    egui::ScrollArea::vertical().max_height(160.0).show(ui, |ui| {
                        ui.label(&self.update_notes);
                    });

                    ui.add_space(14.0);
                    ui.horizontal(|ui| {
                        if ui.button(RichText::new("Install Update & Restart").strong().color(Color32::WHITE))
                            .clicked()
                        {
                            self.show_update_modal = false;
                            self.start_in_app_update(self.update_url.clone(), self.update_tag.clone());
                        }
                        if ui.button("Later").clicked() {
                            self.show_update_modal = false;
                        }
                    });
                });
        }

        egui::CentralPanel::default().show(ctx, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| {
                ui.add_space(12.0);

                // Top Toolbar
                ui.horizontal(|ui| {
                    ui.heading(RichText::new("YouTube Downloader").size(22.0).strong());

                    ui.add_space(6.0);
                    let pill = RichText::new(format!("v{}", APP_VERSION))
                        .size(11.0)
                        .strong()
                        .color(APPLE_BLUE);
                    ui.label(pill);

                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        // Light / Dark Switch
                        let is_dark = self.config.appearance_mode == "Dark";
                        let mode_text = if is_dark { "🌙 Dark Mode" } else { "☀️ Light Mode" };
                        if ui.button(RichText::new(mode_text).strong().size(12.0)).clicked() {
                            let new_mode = if is_dark { "Light" } else { "Dark" };
                            self.config.appearance_mode = new_mode.to_string();
                            save_config(&self.config);

                            let v = if new_mode == "Dark" {
                                let mut d = egui::Visuals::dark();
                                d.panel_fill = Color32::from_rgb(28, 28, 30);
                                d.window_fill = Color32::from_rgb(44, 44, 46);
                                d.widgets.noninteractive.bg_fill = Color32::from_rgb(44, 44, 46);
                                d.widgets.noninteractive.bg_stroke = Stroke::new(1.0_f32, Color32::from_rgb(56, 56, 58));
                                d
                            } else {
                                let mut l = egui::Visuals::light();
                                l.panel_fill = Color32::from_rgb(245, 245, 247);
                                l.window_fill = Color32::from_rgb(255, 255, 255);
                                l.widgets.noninteractive.bg_fill = Color32::from_rgb(255, 255, 255);
                                l.widgets.noninteractive.bg_stroke = Stroke::new(1.0_f32, Color32::from_rgb(229, 229, 234));
                                l
                            };
                            ctx.set_visuals(v);
                        }

                        if !self.update_pill.is_empty() {
                            ui.label(RichText::new(&self.update_pill).color(self.update_pill_color).size(12.0));
                        }
                    });
                });

                ui.add_space(10.0);

                // Card 1: Link Input
                render_card(ui, "Link", |ui| {
                    ui.horizontal(|ui| {
                        let text_box = egui::TextEdit::singleline(&mut self.url_input)
                            .hint_text("Paste video or playlist link...")
                            .desired_width(ui.available_width() - 150.0);
                        ui.add(text_box);

                        if ui.button(RichText::new("Paste").strong()).clicked() {
                            if let Ok(mut cb) = arboard::Clipboard::new() {
                                if let Ok(text) = cb.get_text() {
                                    self.url_input = text.trim().to_string();
                                }
                            }
                        }

                        if ui.button("Clear").clicked() {
                            self.url_input.clear();
                            self.progress_val = 0.0;
                            self.status_text = "Ready to download".to_string();
                            self.metric_text.clear();
                            self.detail_text = "Engine ready • Standalone Rust 2.0 active".to_string();
                        }
                    });
                });

                ui.add_space(10.0);

                // Card 2: Options
                render_card(ui, "Download Settings", |ui| {
                    // Format selection
                    ui.horizontal(|ui| {
                        ui.label(RichText::new("Output Format:").strong());
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            let mut fmt = self.config.format_mode.clone();
                            if ui.selectable_value(&mut fmt, "MP4 Video".to_string(), "MP4 Video").changed()
                                || ui.selectable_value(&mut fmt, "MP3 Audio".to_string(), "MP3 Audio").changed()
                            {
                                self.config.format_mode = fmt;
                                save_config(&self.config);
                            }
                        });
                    });

                    ui.separator();

                    // Quality Selection
                    ui.horizontal(|ui| {
                        if self.config.format_mode == "MP3 Audio" {
                            ui.label(RichText::new("Audio Bitrate:").strong());
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                egui::ComboBox::from_id_salt("bitrate_select")
                                    .selected_text(&self.config.bitrate)
                                    .show_ui(ui, |ui| {
                                        for opt in ["320 kbps (Best)", "192 kbps (Standard)", "128 kbps (Compact)"] {
                                            if ui.selectable_value(&mut self.config.bitrate, opt.to_string(), opt).changed() {
                                                save_config(&self.config);
                                            }
                                        }
                                    });
                            });
                        } else {
                            ui.label(RichText::new("Video Resolution:").strong());
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                egui::ComboBox::from_id_salt("resolution_select")
                                    .selected_text(&self.config.resolution)
                                    .show_ui(ui, |ui| {
                                        for opt in ["Best Available", "2160p (4K)", "1440p (2K)", "1080p (FHD)", "720p (HD)", "480p (SD)"] {
                                            if ui.selectable_value(&mut self.config.resolution, opt.to_string(), opt).changed() {
                                                save_config(&self.config);
                                            }
                                        }
                                    });
                            });
                        }
                    });

                    ui.separator();

                    // Playlist Behavior
                    ui.horizontal(|ui| {
                        ui.label(RichText::new("Playlist Behavior:").strong());
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            ui.selectable_value(&mut self.playlist_mode, "single".to_string(), "Single Video");
                            ui.selectable_value(&mut self.playlist_mode, "playlist".to_string(), "Entire Playlist");
                            ui.selectable_value(&mut self.playlist_mode, "auto".to_string(), "Auto Detect");
                        });
                    });

                    ui.separator();

                    // Embed Metadata
                    ui.horizontal(|ui| {
                        ui.label(RichText::new("Embed ID3 & Cover Thumbnail:").strong());
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            ui.checkbox(&mut self.embed_metadata, "");
                        });
                    });
                });

                ui.add_space(10.0);

                // Card 3: Destination Folder
                render_card(ui, "Save Location", |ui| {
                    ui.horizontal(|ui| {
                        ui.label(&self.config.save_dir);
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            if ui.button("Choose...").clicked() {
                                if let Some(path) = rfd::FileDialog::new().pick_folder() {
                                    self.config.save_dir = path.to_string_lossy().to_string();
                                    save_config(&self.config);
                                }
                            }
                        });
                    });
                });

                ui.add_space(10.0);

                // Card 4: Progress & Status
                render_card(ui, "Status", |ui| {
                    ui.horizontal(|ui| {
                        ui.label(RichText::new(&self.status_text).strong().size(13.0));
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            ui.label(RichText::new(&self.metric_text).color(Color32::from_rgb(134, 134, 139)).size(12.0));
                        });
                    });

                    ui.add_space(6.0);
                    let bar = egui::ProgressBar::new(self.progress_val)
                        .show_percentage()
                        .animate(self.is_downloading);
                    ui.add(bar);

                    if !self.detail_text.is_empty() {
                        ui.add_space(4.0);
                        ui.label(RichText::new(&self.detail_text).size(11.0).color(Color32::from_rgb(134, 134, 139)));
                    }
                });

                ui.add_space(14.0);

                // Primary Action Button & Open Folder
                ui.horizontal(|ui| {
                    let btn_label = if self.is_downloading {
                        "Downloading...".to_string()
                    } else if self.config.format_mode == "MP3 Audio" {
                        "Download MP3".to_string()
                    } else {
                        "Download MP4".to_string()
                    };

                    let dl_btn = egui::Button::new(RichText::new(btn_label).strong().size(14.0).color(Color32::WHITE))
                        .fill(if self.is_downloading { Color32::from_rgb(100, 100, 105) } else { APPLE_BLUE })
                        .min_size(Vec2::new(ui.available_width() - 140.0, 42.0));

                    if ui.add_enabled(!self.is_downloading, dl_btn).clicked() {
                        self.start_download();
                    }

                    if ui.add_sized(Vec2::new(130.0, 42.0), egui::Button::new("Open Folder")).clicked() {
                        let path = &self.config.save_dir;
                        #[cfg(target_os = "windows")]
                        {
                            let _ = Command::new("explorer").arg(path).spawn();
                        }
                    }
                });

                ui.add_space(20.0);
            });
        });

        // Request frame redraw while active
        if self.is_downloading {
            ctx.request_repaint_after(std::time::Duration::from_millis(50));
        }
    }
}

fn render_card<R>(ui: &mut egui::Ui, title: &str, add_contents: impl FnOnce(&mut egui::Ui) -> R) -> R {
    let frame = egui::Frame::group(ui.style())
        .rounding(Rounding::same(10.0))
        .inner_margin(Margin::same(14.0));

    frame.show(ui, |ui| {
        ui.label(RichText::new(title).strong().size(13.0));
        ui.add_space(6.0);
        add_contents(ui)
    }).inner
}

fn main() -> eframe::Result<()> {
    let mut native_options = eframe::NativeOptions::default();
    native_options.viewport = egui::ViewportBuilder::default()
        .with_inner_size([720.0, 680.0])
        .with_min_inner_size([580.0, 520.0])
        .with_title("YouTube Downloader v2.0.0");

    if let Ok(icon_data) = image::open("app_icon.png") {
        let rgba = icon_data.to_rgba8();
        let (width, height) = rgba.dimensions();
        native_options.viewport = native_options.viewport.with_icon(egui::IconData {
            rgba: rgba.into_raw(),
            width,
            height,
        });
    }

    eframe::run_native(
        "YouTube Downloader",
        native_options,
        Box::new(|cc| Ok(Box::new(YouTubeDownloaderApp::new(cc)))),
    )
}
