# Backend Source Architecture

## Summary

Build a Python FastAPI backend that runs on a Windows host, exposes LAN JSON APIs for a separate Vue frontend, imports local videos from host paths, splits them into fixed-size byte segments, encrypts each segment, uploads segments and manifests through a storage backend, and later streams the original video bytes back to browsers through HTTP Range responses.

The current default storage backend is a local `mock` implementation for offline development and tests. The long-term production target remains Baidu Netdisk.

## Core Rules

- Do not transcode video or audio.
- Do not add speculative abstractions.
- Keep business logic out of route handlers.
- Use SQLite as the local source of truth.
- Keep encryption keys on the Windows host only.
- Prefer explicit state transitions for imports.
- Prefer services depending on `storage/base.py`, not on a concrete backend.
- Keep backend/frontend contracts explicit and stable.

## Package Layout

- `src/app/main.py`
  Backend entrypoint, FastAPI app creation, startup hooks, middleware, CORS, and router registration.
- `src/app/core/`
  Settings, path management, session auth, password hashing, and shared security helpers.
- `src/app/db/`
  Engine/session setup, schema models, and migration bootstrap.
- `src/app/models/`
  Domain models for folders, videos, segments, imports, and settings.
- `src/app/repositories/`
  Thin database access helpers. No cloud or media logic here.
- `src/app/storage/`
  Storage backend contract, mock implementation, backend factory, and future Baidu integration.
- `src/app/media/`
  Probe, cover extraction, chunk mapping, encryption, and stream range helpers.
- `src/app/services/`
  Import workflow, playback workflow, manifest helpers, and settings management.
- `src/app/api/`
  Auth, library, import, settings, and stream JSON endpoints.
- `src/app/web/`
  Transitional server-rendered pages only for smoke tests or temporary fallback use. Do not add new product UI here.
- `tests/`
  Unit and integration coverage for chunking, crypto, auth, import, storage, and streaming.

## Frontend Boundary

- The main UI lives in `/frontend`, not in `src/app/web`.
- Backend should expose API-ready response models for the Vue app.
- Backend may keep simple cookie-session auth and return JSON auth endpoints under `/api/auth/*`.
- Browser-facing playback still uses backend stream URLs; no browser-side decryption.

## Responsibilities

### Config and Security

- `core/config.py` reads environment variables and resolves project-relative paths.
- `core/security.py` manages password hashing and cookie sessions.
- `core/keys.py` manages the local content key file.
- Backend CORS settings must allow the separated Vue frontend origins while keeping credentialed session support.
- Secrets needed for Baidu access are stored locally, never in manifests.

### Storage

- `storage/base.py` defines the cloud/object storage contract used by services.
- `storage/mock.py` maps remote object paths into a local directory for tests and offline development.
- `storage/factory.py` selects the configured backend.
- `storage/baidu.py` remains a placeholder until the real API integration is implemented.

### Media Processing

- `media/probe.py` shells out to `ffprobe` for duration and stream metadata.
- `media/covers.py` shells out to `ffmpeg` to generate a static cover image when available.
- `media/chunker.py` maps original byte ranges to fixed-size encrypted segments.
- `media/crypto.py` handles per-segment AES-256-GCM encrypt/decrypt helpers.
- `media/range_map.py` converts HTTP Range requests into one or more segment reads.

### Services

- `ImportService`
  Validates a host file path, probes metadata, builds segments, encrypts each segment, writes local staging files, writes manifest metadata, uploads artifacts through the configured storage backend, and persists task state.
- `StreamService`
  Resolves browser Range requests, prefers local encrypted staging files, falls back to remote objects through the storage backend when needed, decrypts only what is needed, and emits the exact original bytes requested.
- `SettingsService`
  Reads and updates public runtime settings such as Baidu root path and cache limit.

## Data Model

Keep the schema explicit and small.

- `folders`
  Display categories shown in the UI.
- `videos`
  One row per imported video, including folder assignment, title, cover path, mime type, size, duration, remote manifest path, and source path.
- `video_segments`
  One row per encrypted segment with index, original offset, original length, ciphertext size, checksum, remote path, nonce/tag metadata, and local staging path.
- `import_jobs`
  Tracks queued, running, failed, and completed imports.
- `settings`
  Stores local configuration such as Baidu root path and cache limit.

## Remote Layout

Store each video under its own logical directory.

- `/CloudStoragePlayer/videos/{video_id}/manifest.json`
- `/CloudStoragePlayer/videos/{video_id}/segments/{index}.cspseg`

In the current `mock` backend these remote paths are mapped into a local directory tree.

The manifest must include:

- Video title and source file metadata.
- Segment size and segment count.
- Original size and mime type.
- Per-segment original offset, original length, checksum, and remote path.
- Encryption algorithm version and creation time.

The manifest must not include:

- Plaintext encryption keys.
- Session credentials.
- Login password material.

## HTTP Surface

- `GET /api/auth/session`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/folders`
- `GET /api/videos`
- `GET /api/videos/{video_id}`
- `GET /api/videos/{video_id}/stream`
- `POST /api/imports`
- `GET /api/imports`
- `GET /api/imports/{job_id}`
- `GET /api/settings`
- `POST /api/settings`

Transitional server-rendered routes like `/login` or `/` may remain temporarily, but they are not the primary product contract.

## Playback Model

- Browsers receive a normal video URL backed by `GET /api/videos/{video_id}/stream`.
- The stream endpoint must support `Accept-Ranges` and `206 Partial Content`.
- The service must return original file bytes so the browser can seek without custom client-side decryption logic.
- Current resolution order is:
  1. local encrypted staging files
  2. remote objects from the configured storage backend
  3. source file fallback
- Keep decrypted data in memory or short-lived buffers only.

## Testing Requirements

- Unit-test segment slicing and range-to-segment mapping.
- Unit-test AES-GCM round trips and checksum stability.
- Unit-test auth guards and session handling.
- Integration-test import workflow against the mock storage backend.
- Integration-test playback range requests against locally staged encrypted segments.
- Integration-test playback fallback against mock remote objects after local staging removal.

## Non-Goals For Current Phase

- Multi-user access control.
- Browser-side upload of large video files from remote devices.
- Browser-side decryption.
- Re-encoding, HLS generation, or adaptive bitrate streaming.
- Full Windows service packaging.
- Final Baidu production integration.
