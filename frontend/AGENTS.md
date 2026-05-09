# Frontend Architecture

## Summary

This directory contains the separated web frontend for Cloud Storage Player.

- Use `Vue 3` + `TypeScript` + `Vite`.
- Treat the backend as a JSON API server.
- Do not add server-rendered feature work here.
- Keep frontend concerns in the frontend; do not duplicate backend import, storage, crypto, or stream logic in the browser.

## Core Rules

- Prefer small focused components over large mixed views.
- Keep API access in `src/api/`.
- Keep route-level screens in `src/views/`.
- Keep shared state in `src/stores/`.
- Keep browser-only presentational state out of backend models.
- Do not implement browser-side decryption.
- Use backend session cookies with `withCredentials`.

## Layout

- `frontend/src/main.ts`
  Vue app bootstrap.
- `frontend/src/router/`
  Vue Router setup and route guards.
- `frontend/src/stores/`
  Pinia stores such as auth/session state.
- `frontend/src/api/`
  Axios client and API wrappers.
- `frontend/src/views/`
  Route-level pages.
- `frontend/src/components/`
  Reusable presentational components.
- `frontend/src/types/`
  Shared TypeScript API types.

## API Usage

- Auth calls use `/api/auth/*`.
- Library data uses `/api/folders`, `/api/videos`, `/api/videos/{id}`.
- Import jobs use `/api/imports`.
- Settings use `/api/settings`.
- Future playback should use backend stream URLs directly.

## Non-Goals

- No browser-side upload of huge files from remote devices in the first version.
- No browser-side media decryption.
- No frontend-owned business rules for cloud sync or encryption.
