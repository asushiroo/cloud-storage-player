# Source Architecture

## Summary

Build a Python FastAPI service that runs on a Windows host, exposes a LAN web UI, imports local videos from host paths, splits them into fixed-size byte segments, encrypts each segment, uploads segments to Baidu Netdisk, and later streams the original video bytes back to browsers through HTTP Range responses.

## Core Rules

- Do not transcode video or audio.
- Do not add speculative abstractions.
- Keep business logic out of route handlers.
- Use SQLite as the local source of truth.
- Store encrypted segments and manifests in Baidu Netdisk.
- Keep encryption keys on the Windows host only.
- Prefer resumable tasks and explicit state transitions for imports.

## Package Layout

- `src/app/main.py`
  Application entrypoint, FastAPI app creation, startup hooks, and router/template registration.
- `src/app/core/`
  Settings, path management, session auth, password hashing, and shared security helpers.
- `src/app/db/`
  Engine/session setup, schema models, and migration bootstrap.
- `src/app/models/`
  Domain models for folders, videos, segments, imports, settings, and cache records.
- `src/app/repositories/`
  Thin database access helpers. No cloud or media logic here.
- `src/app/storage/`
  Baidu Netdisk client abstraction and implementations.
- `src/app/media/`
  Probe, cover extraction, chunk mapping, encryption, and stream range helpers.
- `src/app/services/`
  Import workflow, playback workflow, sync workflow, cache cleanup, and settings management.
- `src/app/api/`
  Auth, library, import, settings, sync, and stream endpoints.
- `src/app/web/`
  Jinja templates and static assets for login, library, folder, player, and admin pages.
- `tests/`
  Unit and integration coverage for chunking, crypto, auth, and streaming.

## Responsibilities

### Config and Security

- `core/config.py` reads environment variables and persisted settings.
- `core/security.py` manages password hashing, cookie sessions, and local key wrapping helpers.
- Secrets needed for Baidu access are stored locally, never in Baidu manifests.

### Storage

- `storage/base.py` defines the cloud storage contract used by services.
- `storage/baidu.py` implements OAuth refresh, directory creation, multipart upload, listing, and download.
- Add a local mock storage backend for tests and offline development.

### Media Processing

- `media/probe.py` shells out to `ffprobe` for duration and stream metadata.
- `media/covers.py` shells out to `ffmpeg` to generate a static cover image when available.
- `media/chunker.py` maps original byte ranges to fixed-size encrypted segments.
- `media/crypto.py` handles per-segment AES-256-GCM encrypt/decrypt helpers.
- `media/range_map.py` converts HTTP Range requests into one or more segment reads.

### Services

- `ImportService`
  Validates a host file path, probes metadata, builds segments, encrypts each segment, uploads it, writes manifest metadata, and persists task state for resume.
- `StreamService`
  Resolves browser Range requests, fetches encrypted segments from cache or Baidu, decrypts only what is needed, and emits the exact original bytes requested.
- `SyncService`
  Scans the configured Baidu root for manifests and imports missing catalog entries into SQLite.
- `CacheService`
  Tracks local encrypted segment cache entries and evicts least-recently-used files once the configured size cap is exceeded.

## Data Model

Keep the schema explicit and small.

- `folders`
  Display categories shown in the UI.
- `videos`
  One row per imported video, including folder assignment, title, cover path, mime type, size, duration, and cloud manifest path.
- `video_segments`
  One row per encrypted segment with index, original offset, original length, ciphertext size, checksum, cloud path, nonce, and tag or combined AEAD metadata.
- `import_jobs`
  Tracks queued, running, failed, and completed imports with resumable progress.
- `settings`
  Stores local configuration such as Baidu app identifiers, refresh token, root path, and cache limit.
- `cache_entries`
  Tracks local encrypted segment cache files, size, and last-access time.

## Remote Layout

Store each video under its own directory in Baidu Netdisk.

- `/CloudStoragePlayer/videos/{video_id}/manifest.json`
- `/CloudStoragePlayer/videos/{video_id}/segments/{index}.cspseg`
- `/CloudStoragePlayer/covers/{video_id}.jpg`

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

- `GET /login`
  Login page.
- `POST /auth/login`
  Password authentication, sets secure session cookie.
- `POST /auth/logout`
  Clears the session.
- `GET /`
  Library homepage with folders.
- `GET /folders/{folder_id}`
  Video grid for a folder.
- `GET /videos/{video_id}`
  Player page.
- `GET /api/folders`
  JSON folder list.
- `GET /api/videos`
  JSON video list, optionally filtered by folder.
- `GET /api/videos/{video_id}`
  JSON video details.
- `GET /api/videos/{video_id}/stream`
  Range-capable original byte stream for HTML5 video playback.
- `POST /api/imports`
  Create import job from a Windows host file path.
- `GET /api/imports`
  Import job list.
- `GET /api/imports/{job_id}`
  Import job status and progress.
- `POST /api/sync/baidu`
  Scan manifests from Baidu and sync local catalog.
- `GET /api/settings`
  Read non-secret settings needed by the admin page.
- `POST /api/settings`
  Update local settings.
- `POST /api/settings/baidu/oauth`
  Exchange authorization code and save refresh token.

## Playback Model

- Browsers receive a normal video URL backed by `GET /api/videos/{video_id}/stream`.
- The stream endpoint must support `Accept-Ranges` and `206 Partial Content`.
- The service must return original file bytes so the browser can seek without custom client-side decryption logic.
- Keep decrypted data in memory or short-lived temp buffers only. Do not maintain a long-lived plaintext cache unless a future requirement explicitly asks for it.

## Testing Requirements

- Unit-test segment slicing and range-to-segment mapping.
- Unit-test AES-GCM round trips and checksum stability.
- Unit-test auth guards and session handling.
- Integration-test import workflow against a mock storage backend.
- Integration-test playback range requests against stored encrypted segments.

## Non-Goals For First Version

- Multi-user access control.
- Browser-side upload of large video files from remote devices.
- Browser-side decryption.
- Re-encoding, HLS generation, or adaptive bitrate streaming.
- Full Windows service packaging.
