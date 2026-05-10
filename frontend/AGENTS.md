# Frontend Architecture

## Summary

This directory is the primary tracked web frontend for Cloud Storage Player.

- Use `React` + `TypeScript` + `Vite`.
- Treat the backend as a JSON API server.
- `third/` is reference-only; copy/adapt what is needed here.
- Keep frontend concerns in the frontend; do not duplicate backend import, storage, crypto, or stream logic in the browser.

## Core Rules

- Prefer small focused components over large mixed files.
- Keep API access in `src/api/`.
- Keep route-level screens in `src/pages/`.
- Keep browser-only presentational state out of backend models.
- Do not implement browser-side decryption.
- Use backend session cookies with `credentials: include`.

## Layout

- `frontend/src/main.tsx`
  App bootstrap.
- `frontend/src/App.tsx`
  Router definition.
- `frontend/src/api/`
  Fetch wrappers for backend APIs.
- `frontend/src/pages/`
  Route-level pages.
- `frontend/src/components/`
  Reusable presentational components.
- `frontend/src/hooks/`
  Shared auth/session hooks.
- `frontend/src/types/`
  Shared TypeScript API types.
- `frontend/src/utils/`
  Pure helpers.

## API Usage

- Auth calls use `/api/auth/*`.
- Library data uses `/api/folders`, `/api/videos`, `/api/videos/{id}`.
- Import jobs use `/api/imports`.
- Settings use `/api/settings`.
- Playback uses backend stream URLs directly.

## Non-Goals

- No browser-side upload of huge files from remote devices in the first version.
- No browser-side media decryption.
- No frontend-owned business rules for cloud sync or encryption.
