"""
StreamDrop — YouTube Downloader Backend
========================================
Stack : Flask + yt-dlp + FFmpeg
Author: StreamDrop
Usage : python app.py
        Then open http://localhost:5000 in your browser
"""

import os
import re
import uuid
import shutil
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string

# yt-dlp is the core download engine
try:
    import yt_dlp
except ImportError:
    raise SystemExit("❌  yt-dlp not found. Run:  pip install yt-dlp")

# ── Configuration ────────────────────────────────────────────────────────────

BASE_DIR      = Path(__file__).parent
DOWNLOAD_DIR  = BASE_DIR / "downloads"          # All output files land here
DOWNLOAD_DIR.mkdir(exist_ok=True)

FFMPEG_PATH   = shutil.which("ffmpeg")          # Must be installed on system
COOKIE_FILE   = BASE_DIR / "cookies.txt"        # Optional: for age-restricted videos

# How long (seconds) to keep a finished file before auto-deleting it
FILE_TTL = 300   # 5 minutes

app = Flask(__name__)

# ── In-memory job store ───────────────────────────────────────────────────────
# Stores download progress per job_id so the browser can poll it

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_youtube_url(url: str) -> bool:
    """Return True if url looks like a real YouTube link."""
    pattern = (
        r"^(https?://)?"
        r"(www\.)?"
        r"(youtube\.com/(watch\?.*v=|playlist\?.*list=|shorts/)"
        r"|youtu\.be/)"
    )
    return bool(re.match(pattern, url.strip()))


def sanitize_filename(name: str) -> str:
    """Remove characters that break file paths."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()[:120]


def schedule_deletion(path: Path, delay: int = FILE_TTL):
    """Delete a file after `delay` seconds in a background thread."""
    def _delete():
        time.sleep(delay)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
    threading.Thread(target=_delete, daemon=True).start()


def build_ydl_opts(
    job_id: str,
    fmt: str,           # "video" | "audio"
    output_dir: Path,
) -> dict:
    """
    Build the yt_dlp options dictionary.

    Video → 720p MP4 (video + audio merged via FFmpeg)
    Audio → best audio source converted to 320kbps MP3 via FFmpeg
    """

    # ── Progress hook ─────────────────────────────────────────────────────────
    def progress_hook(d):
        with jobs_lock:
            job = jobs.get(job_id, {})
            if d["status"] == "downloading":
                total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                current = d.get("downloaded_bytes", 0)
                speed   = d.get("speed") or 0
                eta     = d.get("eta") or 0
                pct     = round((current / total) * 100, 1) if total else 0

                job["stage"]    = "downloading"
                job["percent"]  = pct
                job["speed"]    = f"{speed / 1024:.1f} KB/s" if speed else "—"
                job["eta"]      = f"{eta}s" if eta else "—"
                job["filename"] = d.get("filename", "")

            elif d["status"] == "finished":
                job["stage"]   = "merging" if fmt == "video" else "converting"
                job["percent"] = 95

            elif d["status"] == "error":
                job["stage"]   = "error"
                job["error"]   = str(d.get("error", "Unknown error"))

            jobs[job_id] = job

    # ── Shared base options ───────────────────────────────────────────────────
    opts = {
        "outtmpl"       : str(output_dir / "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "quiet"         : True,
        "no_warnings"   : True,
        "noplaylist"    : False,      # allow playlists; callers control this
    }

    # Attach cookies if the file exists (helps with age-restricted content)
    if COOKIE_FILE.exists():
        opts["cookiefile"] = str(COOKIE_FILE)

    # Attach FFmpeg location if found
    if FFMPEG_PATH:
        opts["ffmpeg_location"] = FFMPEG_PATH

    # ── Format-specific options ───────────────────────────────────────────────
    if fmt == "video":
        # Download best video ≤720p + best audio, merge into MP4
        opts["format"]     = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]"
        opts["merge_output_format"] = "mp4"
        opts["postprocessors"] = [
            {
                "key"            : "FFmpegVideoConvertor",
                "preferedformat" : "mp4",
            }
        ]

    elif fmt == "audio":
        # Download best audio stream, convert to MP3 @ 320 kbps
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key"            : "FFmpegExtractAudio",
                "preferredcodec" : "mp3",
                "preferredquality": "320",
            }
        ]

    return opts


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the frontend HTML page."""
    html_file = BASE_DIR / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h2>index.html not found — place it next to app.py</h2>", 404


@app.route("/api/download", methods=["POST"])
def api_download():
    """
    POST /api/download
    Body (JSON):
        url      : str   — YouTube video or playlist URL
        format   : str   — "video" | "audio"
        type     : str   — "single" | "playlist"

    Returns (JSON):
        job_id   : str   — poll /api/status/<job_id> for progress
    """
    data = request.get_json(force=True)

    url        = (data.get("url") or "").strip()
    fmt        = data.get("format", "video")        # video | audio
    dl_type    = data.get("type", "single")         # single | playlist

    # ── Validate ─────────────────────────────────────────────────────────────
    if not url:
        return jsonify({"error": "URL is required."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Only YouTube URLs are supported."}), 400

    if fmt not in ("video", "audio"):
        return jsonify({"error": "format must be 'video' or 'audio'."}), 400

    if dl_type not in ("single", "playlist"):
        return jsonify({"error": "type must be 'single' or 'playlist'."}), 400

    if dl_type == "playlist" and "list=" not in url:
        return jsonify({"error": "Playlist URL must contain 'list=' parameter."}), 400

    # ── Create job ────────────────────────────────────────────────────────────
    job_id     = str(uuid.uuid4())
    job_dir    = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    with jobs_lock:
        jobs[job_id] = {
            "stage"   : "queued",
            "percent" : 0,
            "speed"   : "—",
            "eta"     : "—",
            "format"  : fmt,
            "type"    : dl_type,
            "files"   : [],
            "error"   : None,
        }

    # ── Run download in background thread ─────────────────────────────────────
    def run_download():
        try:
            opts = build_ydl_opts(job_id, fmt, job_dir)

            # For single videos, disable playlist downloading
            if dl_type == "single":
                opts["noplaylist"] = True

            with jobs_lock:
                jobs[job_id]["stage"] = "downloading"

            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            # Collect output files
            output_files = list(job_dir.iterdir())
            with jobs_lock:
                jobs[job_id]["stage"]   = "done"
                jobs[job_id]["percent"] = 100
                jobs[job_id]["files"]   = [f.name for f in output_files]

            # Auto-delete job folder after TTL
            schedule_deletion(job_dir, FILE_TTL)

        except yt_dlp.utils.DownloadError as e:
            with jobs_lock:
                jobs[job_id]["stage"] = "error"
                jobs[job_id]["error"] = str(e)
        except Exception as e:
            with jobs_lock:
                jobs[job_id]["stage"] = "error"
                jobs[job_id]["error"] = f"Unexpected error: {e}"

    thread = threading.Thread(target=run_download, daemon=True)
    thread.start()

    return jsonify({"job_id": job_id}), 202


@app.route("/api/status/<job_id>", methods=["GET"])
def api_status(job_id: str):
    """
    GET /api/status/<job_id>
    Returns current job state so the frontend can show live progress.
    """
    with jobs_lock:
        job = jobs.get(job_id)

    if job is None:
        return jsonify({"error": "Job not found."}), 404

    return jsonify(job)


@app.route("/api/file/<job_id>/<filename>", methods=["GET"])
def api_file(job_id: str, filename: str):
    """
    GET /api/file/<job_id>/<filename>
    Streams the finished file to the browser as a download.
    """
    # Security: prevent path traversal
    safe_name = Path(filename).name
    file_path = DOWNLOAD_DIR / job_id / safe_name

    if not file_path.exists():
        return jsonify({"error": "File not found or already deleted."}), 404

    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=safe_name,
    )


@app.route("/api/playlist-info", methods=["POST"])
def api_playlist_info():
    """
    POST /api/playlist-info
    Body: { "url": "..." }
    Returns playlist title + video count (no download).
    """
    data = request.get_json(force=True)
    url  = (data.get("url") or "").strip()

    if not url or not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400

    try:
        opts = {
            "quiet"          : True,
            "no_warnings"    : True,
            "extract_flat"   : True,       # Don't download, just extract metadata
            "skip_download"  : True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            return jsonify({"error": "Could not fetch info."}), 400

        # Could be a single video or a playlist
        if info.get("_type") == "playlist":
            entries = info.get("entries") or []
            return jsonify({
                "title"      : info.get("title", "Unknown Playlist"),
                "video_count": len(entries),
                "is_playlist": True,
            })
        else:
            return jsonify({
                "title"      : info.get("title", "Unknown Video"),
                "duration"   : info.get("duration_string", "—"),
                "channel"    : info.get("uploader", "—"),
                "is_playlist": False,
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 52)
    print("  StreamDrop Backend — Running on http://localhost:5000")
    print("=" * 52)
    print(f"  Downloads folder : {DOWNLOAD_DIR}")
    print(f"  FFmpeg detected  : {'✅ Yes' if FFMPEG_PATH else '❌ No — install FFmpeg!'}")
    print(f"  Cookies file     : {'✅ Found' if COOKIE_FILE.exists() else 'Not set (optional)'}")
    print("=" * 52)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,      # Set True during development only
        threaded=True,    # Handle multiple downloads simultaneously
    )
