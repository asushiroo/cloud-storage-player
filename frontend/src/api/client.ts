import type {
  ApiError,
  AuthSession,
  CancelAllImportJobsResult,
  CacheSummary,
  CatalogSyncResult,
  CachedVideo,
  ClearedCacheResult,
  ClearedImportJobsResult,
  Folder,
  ImportFolderResult,
  ImportJob,
  PublicSettings,
  VideoPage,
  Video,
  VideoRecommendationShelf,
  VideoWatchHeartbeatResult,
} from "../types/api";

export interface SettingsUpdatePayload {
  baidu_root_path?: string;
  cache_limit_bytes?: number;
  storage_backend?: string;
  upload_transfer_concurrency?: number;
  download_transfer_concurrency?: number;
  remote_transfer_concurrency?: number;
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const jsonHeaders = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

const buildUrl = (path: string): string => {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
};

async function toApiError(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}.`;
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string") {
      message = payload.detail;
    }
  } catch {
    const text = await response.text();
    if (text) {
      message = text;
    }
  }
  return { status: response.status, message };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export const buildAssetUrl = (path: string | null, versionToken?: string | number): string | null => {
  if (!path) {
    return null;
  }
  const url = buildUrl(path);
  if (versionToken === undefined || versionToken === null || versionToken === "") {
    return url;
  }
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}v=${encodeURIComponent(String(versionToken))}`;
};
export const getStreamUrl = (videoId: number): string => buildUrl(`/api/videos/${videoId}/stream`);

export const fetchSession = (): Promise<AuthSession> => request("/api/auth/session");

export const login = (password: string): Promise<AuthSession> =>
  request("/api/auth/login", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ password }),
  });

export const logout = (): Promise<AuthSession> =>
  request("/api/auth/logout", {
    method: "POST",
  });

export const fetchFolders = (): Promise<Folder[]> => request("/api/folders");

export const fetchVideos = (params?: { folderId?: number; q?: string; tag?: string }): Promise<Video[]> => {
  const search = new URLSearchParams();
  if (params?.folderId !== undefined) {
    search.set("folder_id", String(params.folderId));
  }
  if (params?.q?.trim()) {
    search.set("q", params.q.trim());
  }
  if (params?.tag?.trim()) {
    search.set("tag", params.tag.trim());
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  return request(`/api/videos${suffix}`);
};

export const fetchVideoPage = (params?: {
  folderId?: number;
  q?: string;
  tag?: string;
  offset?: number;
  limit?: number;
}): Promise<VideoPage> => {
  const search = new URLSearchParams();
  if (params?.folderId !== undefined) {
    search.set("folder_id", String(params.folderId));
  }
  if (params?.q?.trim()) {
    search.set("q", params.q.trim());
  }
  if (params?.tag?.trim()) {
    search.set("tag", params.tag.trim());
  }
  if (params?.offset !== undefined) {
    search.set("offset", String(params.offset));
  }
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  return request(`/api/videos/page${suffix}`);
};

export const fetchVideo = (videoId: number): Promise<Video> => request(`/api/videos/${videoId}`);

export const fetchVideoRecommendations = (): Promise<VideoRecommendationShelf> =>
  request("/api/videos/recommendations");

export const reportVideoWatchHeartbeat = (payload: {
  videoId: number;
  sessionToken?: string | null;
  positionSeconds: number;
  watchedSecondsDelta: number;
  completed?: boolean;
}): Promise<VideoWatchHeartbeatResult> =>
  request(`/api/videos/${payload.videoId}/watch`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      session_token: payload.sessionToken ?? null,
      position_seconds: payload.positionSeconds,
      watched_seconds_delta: payload.watchedSecondsDelta,
      completed: payload.completed ?? false,
    }),
  });

export const deleteVideo = (videoId: number): Promise<ImportJob> =>
  request(`/api/videos/${videoId}`, {
    method: "DELETE",
  });

export const updateVideoTags = (videoId: number, tags: string[]): Promise<Video> =>
  request(`/api/videos/${videoId}/tags`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ tags }),
  });

export const updateVideoMetadata = (payload: {
  videoId: number;
  title: string;
  tags: string[];
}): Promise<Video> =>
  request(`/api/videos/${payload.videoId}`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({
      title: payload.title,
      tags: payload.tags,
    }),
  });

export const updateVideoArtwork = (payload: {
  videoId: number;
  coverDataUrl?: string;
  posterDataUrl?: string;
}): Promise<Video> =>
  request(`/api/videos/${payload.videoId}/artwork`, {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({
      cover_data_url: payload.coverDataUrl ?? null,
      poster_data_url: payload.posterDataUrl ?? null,
    }),
  });

export const fetchImportJobs = (): Promise<ImportJob[]> => request("/api/imports");

export const createImport = (payload: {
  source_path: string;
  folder_id?: number | null;
  title?: string | null;
  tags?: string[];
}): Promise<ImportJob> =>
  request("/api/imports", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });

export const createFolderImport = (payload: {
  source_path: string;
  folder_id?: number | null;
  tags?: string[];
}): Promise<ImportFolderResult> =>
  request("/api/imports/folder", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });

export const cancelImportJob = (jobId: number): Promise<ImportJob> =>
  request(`/api/imports/${jobId}/cancel`, {
    method: "POST",
  });

export const cancelAllImportJobs = (): Promise<CancelAllImportJobsResult> =>
  request("/api/imports/cancel-all", {
    method: "POST",
  });

export const clearFinishedImportJobs = (statusGroup: "completed" | "failed"): Promise<ClearedImportJobsResult> =>
  request(`/api/imports?status_group=${statusGroup}`, {
    method: "DELETE",
  });

export const syncRemoteCatalog = (): Promise<CatalogSyncResult> =>
  request("/api/videos/sync", {
    method: "POST",
  });

export const fetchSettings = (): Promise<PublicSettings> => request("/api/settings");

export const fetchCacheSummary = (): Promise<CacheSummary> => request("/api/cache");

export const fetchCachedVideos = (): Promise<CachedVideo[]> => request("/api/cache/videos");

export const clearAllCachedVideos = (): Promise<ClearedCacheResult> =>
  request("/api/cache", {
    method: "DELETE",
  });

export const clearCachedVideo = (videoId: number): Promise<ClearedCacheResult> =>
  request(`/api/cache/videos/${videoId}`, {
    method: "DELETE",
  });

export const createVideoCacheJob = (videoId: number): Promise<ImportJob> =>
  request(`/api/videos/${videoId}/cache`, {
    method: "POST",
  });

export const updateSettings = (payload: SettingsUpdatePayload): Promise<PublicSettings> =>
  request("/api/settings", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });

export const authorizeBaidu = (code: string): Promise<PublicSettings> =>
  request("/api/settings/baidu/oauth", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify({ code }),
  });
