# AGENTS.md

This repository hosts a Windows-first internal video server that stores encrypted video segments in Baidu Netdisk and streams them back to browsers inside a LAN.

## Project Constraints

- Keep coupling low. Prefer separate modules over large mixed files.
- Use Python with UV-managed project metadata and environment setup.
- Use a separated frontend/backend architecture.
- Do not re-encode or compress video/audio payloads during import or playback.
- Use only Baidu Netdisk official open platform APIs for cloud storage access.
- Treat the Windows host as the trusted machine. Other devices access only the web UI and playback stream.
- Preserve existing code style and make surgical changes only.

## Product Shape

- The app starts on a Windows machine as a command-line web service.
- The service listens on a LAN-accessible port.
- Users authenticate with a single password.
- The backend exposes JSON APIs for a separate frontend.
- The frontend shows folders, video covers, names, import status, settings, and a playback page.
- Playback must support seek, speed, volume, play, and pause through browser-native video support.

## Implementation Defaults

- Python version target: `3.12` unless a later README changes that requirement.
- Backend frameworks: `FastAPI`, `SQLite`, and focused service/repository modules.
- Frontend frameworks: `Vue 3`, `TypeScript`, `Vite`, `Pinia`, and `Vue Router`.
- Import source: Windows host local file paths entered from the admin UI.
- Media metadata and cover extraction may use external `ffmpeg` and `ffprobe`.
- Segment encryption uses `AES-256-GCM`.
- Stream decryption happens on the server, not in the browser.
- Cached encrypted segments use an LRU size cap.

## Source Layout

Detailed backend architecture and module-level expectations live in [src/AGENTS.md](/root/cloud-storage-player/src/AGENTS.md).
Detailed frontend architecture lives in [frontend/AGENTS.md](/root/cloud-storage-player/frontend/AGENTS.md).

## Frontend/Backend Separation Rules

- New UI feature work goes into `frontend/`, not backend templates.
- Backend route handlers should return JSON APIs for the Vue frontend.
- Session auth remains backend-owned; frontend consumes it through `/api/auth/*`.
- Do not move encryption, cloud sync, or decryption logic into the frontend.
- Backend may temporarily keep simple server-rendered pages for smoke tests or fallback debugging, but they are not the main product direction.

## Baidu Cloud Disk API KEY

百度网盘的appkey，secretkey，signkey都在环境变量中
BAIDU_APP_KEY
BAIDU_SECRET_KEY
BAIDU_SIGN_KEY

## 技术要求

在生成代码的同时要同步在docs中更新技术文档, 技术文档使用中文
由于该项目会有视频解码编码的操作，python的速度绝对是不够的，必要时使用rust异步操作提高速度
需要极限也可以使用cpp
在完成一个阶段是就用git进行commit，分阶段push代码
