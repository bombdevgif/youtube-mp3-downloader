fn main() {
    if std::env::var_os("CARGO_CFG_WINDOWS").is_some() {
        let mut res = winres::WindowsResource::new();
        res.set_icon("app_icon.ico");
        res.set("ProductName", "YouTube Downloader");
        res.set("FileDescription", "YouTube to MP3 & MP4 Downloader");
        res.set("LegalCopyright", "Copyright (C) 2026 bombdevgif. All rights reserved.");
        res.set("CompanyName", "bombdevgif");
        res.set("ProductVersion", "2.0.0.0");
        res.set("FileVersion", "2.0.0.0");
        let _ = res.compile();
    }
}
