import type {
  ApiError,
  AuthSession,
  CatalogSyncResult,
  Folder,
  ImportJob,
  PublicSettings,
  Video,
} from "../types/api";

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

export const buildAssetUrl = (path: string | null): string | null => (path ? buildUrl(path) : null);
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

export const fetchVideo = (videoId: number): Promise<Video> => request(`/api/videos/${videoId}`);

export const updateVideoTags = (videoId: number, tags: string[]): Promise<Video> =>
  request(`/api/videos/${videoId}/tags`, {
    method: "PATCH",
    headers: jsonHeaders,
    body: JSON.stringify({ tags }),
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

export const syncRemoteCatalog = (): Promise<CatalogSyncResult> =>
  request("/api/videos/sync", {
    method: "POST",
  });

export const fetchSettings = (): Promise<PublicSettings> => request("/api/settings");

export const updateSettings = (payload: Partial<PublicSettings>): Promise<PublicSettings> =>
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
