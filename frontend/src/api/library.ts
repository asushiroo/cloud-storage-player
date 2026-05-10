import { http } from "./http";
import type { CatalogSyncResult, Folder, Video } from "../types/api";

export interface FetchVideosParams {
  folderId?: number;
  q?: string;
  tag?: string;
}

export async function fetchFolders(): Promise<Folder[]> {
  const response = await http.get<Folder[]>("/api/folders");
  return response.data;
}

export async function fetchVideos(params?: FetchVideosParams): Promise<Video[]> {
  const response = await http.get<Video[]>("/api/videos", {
    params: {
      folder_id: params?.folderId,
      q: params?.q?.trim() || undefined,
      tag: params?.tag?.trim() || undefined,
    },
  });
  return response.data;
}

export async function fetchVideo(videoId: number): Promise<Video> {
  const response = await http.get<Video>(`/api/videos/${videoId}`);
  return response.data;
}

export async function updateVideoTags(videoId: number, tags: string[]): Promise<Video> {
  const response = await http.patch<Video>(`/api/videos/${videoId}/tags`, { tags });
  return response.data;
}

export async function syncRemoteCatalog(): Promise<CatalogSyncResult> {
  const response = await http.post<CatalogSyncResult>("/api/videos/sync");
  return response.data;
}
