🎬 StreamDrop — YouTube Video & Playlist Downloader
> A free, open-source YouTube downloader built with \*\*Python (Flask) + yt-dlp + FFmpeg\*\*
> Created by \*\*Mr. M. Hammad\*\* — \[YouTube Channel: Mr.Tech\_Hammad](https://youtube.com/@Mr.Tech\_Hammad)
---
✨ Features
⬇️ Download YouTube videos at fixed 720p MP4
🎵 Extract audio as MP3 (320kbps)
📋 Download full playlists automatically
📊 Live progress bar with speed and ETA
🎨 Clean dark UI with smooth animations
🔍 Auto-fetches video/playlist info before download
---
🖥️ Requirements
Make sure these are installed on your system:
Tool	Purpose	Download
Python 3.10+	Backend language	python.org
FFmpeg	Merge video + audio	gyan.dev/ffmpeg
yt-dlp	YouTube download engine	Installed via pip
Flask	Web server	Installed via pip
---
⚙️ Installation & Setup
Step 1 — Clone the Repository
```bash
git clone https://github.com/MrTech-Hammad/YT-Video-Downloader.git
cd YT-Video-Downloader
```
Step 2 — Install Python Dependencies
```bash
pip install flask yt-dlp
```
Step 3 — Install FFmpeg
Windows: Download from gyan.dev, extract to `C:\\ffmpeg`, add `C:\\ffmpeg\\bin` to PATH
macOS: `brew install ffmpeg`
Linux: `sudo apt install ffmpeg`
Step 4 — Run the Server
Windows (PowerShell):
```powershell
\& "path\\to\\python.exe" app.py
```
macOS / Linux:
```bash
python app.py
```
Step 5 — Open in Browser
```
http://localhost:5000
```
---
📁 Project Structure
```
StreamDrop/
├── app.py          ← Python Flask backend
├── index.html      ← Frontend UI
├── requirements.txt← Python dependencies
├── downloads/      ← Temporary download folder (auto-created)
└── cookies.txt     ← Optional: for age-restricted videos
```
---
🔌 API Endpoints
Method	Endpoint	Description
GET	`/`	Serves the frontend
POST	`/api/download`	Starts a download job
GET	`/api/status/<job\_id>`	Get live download progress
GET	`/api/file/<job\_id>/<filename>`	Download the finished file
POST	`/api/playlist-info`	Fetch video/playlist metadata
---
🛠️ Want to Contribute?
This project is 100% open source and made for learners!
You can improve it by:
🎨 Adding new UI themes or fonts
📱 Making it mobile responsive
🔊 Adding more quality options (1080p, 480p, 128kbps)
🌐 Adding support for other platforms
🔐 Adding user authentication
📦 Adding ZIP download for playlists
🌍 Adding multi-language support
How to Contribute:
Fork this repository
Create a new branch: `git checkout -b my-feature`
Make your changes
Commit: `git commit -m "Added new feature"`
Push: `git push origin my-feature`
Open a Pull Request
---
⚠️ Keep yt-dlp Updated
YouTube changes its download cipher regularly. If downloads stop working, run:
```bash
pip install -U yt-dlp
```
---
📜 License
This project is licensed under the MIT License — see LICENSE file.
You are free to use, modify, and share this project.
---
🙏 Credits
Built with:
yt-dlp
Flask
FFmpeg
---
> ⭐ If this project helped you, please give it a \*\*star\*\* on GitHub!
> Subscribe to \[Mr.Tech\_Hammad](https://youtube.com/@Mr.Tech\_Hammad) for more projects!
