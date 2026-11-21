@echo off
echo ========================================================
echo Trusting YouTube Downloader Certificate (bombdevgif)
echo ========================================================
certutil -addstore -user "TrustedPublisher" "%~dp0bombdevgif.cer"
echo.
echo Certificate installed into Trusted Publishers!

if exist "%~dp0YouTubeMP3Downloader.exe" (
    powershell -NoProfile -Command "Unblock-File -Path '%~dp0YouTubeMP3Downloader.exe' -ErrorAction SilentlyContinue"
    echo Unblocked YouTubeMP3Downloader.exe from SmartScreen Mark-of-the-Web.
)

echo Windows will now recognize the publisher as trusted.
echo ========================================================
pause
