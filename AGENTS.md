# AGENTS.md

This repository hosts a Windows-first internal video server that stores encrypted video segments in Baidu Netdisk and streams them back to browsers inside a LAN.

## Project Constraints

- Keep coupling low. Prefer separate modules over large mixed files.
- Use Python with UV-managed backend metadata and environment setup.
- The backend remains the source of truth for import, encryption, manifest, sync, and streaming logic.
- `third/` is reference material only. Do not make it the active product code path.
- The tracked frontend lives in `frontend/`, and frontend work should land there directly.
- Do not re-encode or compress video or audio payloads during import or playback.
- Use only Baidu Netdisk official open platform APIs for real cloud storage access.
- Allow a local mock storage backend for offline development, tests, and pre-production verification.
- Treat the Windows host as the trusted machine. Other devices access only the web UI and playback stream.
- Preserve existing code style and make surgical changes only.

## Product Shape

- The app starts on a Windows machine as a command-line web service.
- The service listens on a LAN-accessible port.
- Users authenticate with a single password.
- The backend exposes JSON APIs.
- The primary web UI lives in `frontend/`.
- The frontend shows folders, video covers, names, import status, settings, and a playback page.
- Playback must support seek, speed, volume, play, and pause through browser-native video support.

## Implementation Defaults

- Python version target: `3.12` unless a later README changes that requirement.
- Backend frameworks: `FastAPI`, `SQLite`, and focused service/repository modules.
- Primary frontend runtime: `React + TypeScript + Vite` in `frontend/`.
- `third/Kyoo` may be copied from or studied, but it is not the runtime path and should not be required for build/deploy.
- Import source: Windows host local file paths entered from the admin UI.
- Media metadata and cover extraction may use external `ffmpeg` and `ffprobe`.
- Segment encryption uses `AES-256-GCM`.
- Stream decryption happens on the server, not in the browser.
- Default pre-production storage backend is local `mock`; real cloud backend targets Baidu APIs.
- Default Baidu root path is `/apps/CloudStoragePlayer`.
- Cached encrypted segments use an LRU size cap.

## Source Layout

- `src/`
  Current FastAPI backend and all import/encryption/storage/streaming logic.
- `frontend/`
  Primary tracked frontend codebase.
- `third/`
  Reference-only upstream code snapshots and experiments. Do not depend on it at runtime.

Detailed backend architecture and module-level expectations live in [src/AGENTS.md](/root/cloud-storage-player/src/AGENTS.md).
Detailed frontend architecture lives in [frontend/AGENTS.md](/root/cloud-storage-player/frontend/AGENTS.md).

## Frontend/Backend Separation Rules

- New UI feature work should land in `frontend/`.
- Backend route handlers should return JSON APIs for the frontend shell.
- Session auth remains backend-owned; frontend consumes it through `/api/auth/*`.
- Do not move encryption, cloud sync, or decryption logic into the frontend.
- Backend may temporarily keep simple server-rendered pages for smoke tests or fallback debugging, but they are not the main product direction.

## Migration Rule

- Do not keep “Kyoo-inspired” rewrites as the primary approach.
- If code from `third/` is useful, copy/adapt the needed parts into `frontend/` and make `frontend/` self-contained.
- Do not preserve compatibility with the removed frontend if the task explicitly says not to.

## 技术要求

在生成代码的同时要同步在README.md中更新进度，docs文档只有我让更新时再更新，避免每轮都更新浪费token
在完成一个阶段时就用 git 进行 commit, commit的格式要符合工程规范，e. feat(cli): add run command;
