**Stream Monitor v1.1**
A lightweight, multi-threaded monitoring tool designed for real-time analysis of HLS, SRT, and UDP streams. 
It helps QA engineers detect broadcast issues (black screens, freezes, or signal corruption) before viewers do.

**Quick Setup**
FFmpeg (Mandatory): > IMPORTANT: You must manually place ffmpeg.exe in the script's folder. This file is too large for Git/repositories and is not included. Ensure you are using version 6.0 or higher.

Channel List:
Create a channels.txt file in the same directory. Add your streams in the following format:
"Channel Name,Stream URL"

**Features & Diagnostics**
Multi-threading: Monitor dozens of streams simultaneously with minimal CPU/RAM usage.

Smart Detection: * [CONTENT ERROR]: Black screen detection (10s threshold).

[CRITICAL ERROR]: Static "Video Unavailable" screen detection (Freeze + Black filter).

[STREAM DEGRADATION]: Identifies packet loss and codec corruption.

[NETWORK ERROR]: Instant alert if the server/VPN is down.

Evidence Capture: Automatically saves a .jpg screenshot whenever an error is detected.
