# AGENTS.md

This repository hosts a Windows-first internal video server that stores encrypted video segments in Baidu Netdisk and streams them back to browsers inside a LAN.

## Project Constraints

- Keep coupling low. Prefer separate modules over large mixed files.
- Use Python with UV-managed project metadata and environment setup.
- Do not re-encode or compress video/audio payloads during import or playback.
- Use only Baidu Netdisk official open platform APIs for cloud storage access.
- Treat the Windows host as the trusted machine. Other devices access only the web UI and playback stream.
- Preserve existing code style and make surgical changes only.

## Product Shape

- The app starts on a Windows machine as a command-line web service.
- The service listens on a LAN-accessible port.
- Users authenticate with a single password.
- The web UI shows folders, video covers, names, import status, and a playback page.
- Playback must support seek, speed, volume, play, and pause through browser-native video support.

## Implementation Defaults

- Python version target: `3.12` unless a later README changes that requirement.
- Frameworks: `FastAPI`, `Jinja2` templates, `SQLite`, and standard browser JavaScript.
- Import source: Windows host local file paths entered from the admin UI.
- Media metadata and cover extraction may use external `ffmpeg` and `ffprobe`.
- Segment encryption uses `AES-256-GCM`.
- Stream decryption happens on the server, not in the browser.
- Cached encrypted segments use an LRU size cap.

## Source Layout

Detailed architecture and module-level expectations live in [src/AGENTS.md](/root/cloud-storage-player/src/AGENTS.md).
