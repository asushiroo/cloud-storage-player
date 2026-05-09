import axios from "axios";

const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

export const http = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
});

export function buildAssetUrl(path: string | null): string | null {
  if (!path) {
    return null;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${apiBaseUrl}${path}`;
}
