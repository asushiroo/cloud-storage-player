import { http } from "./http";
import type { CatalogSyncResult, Folder, Video } from "../types/api";

export async function fetchFolders(): Promise<Folder[]> {
  const response = await http.get<Folder[]>("/api/folders");
  return response.data;
}

export async function fetchVideos(folderId?: number): Promise<Video[]> {
  const response = await http.get<Video[]>("/api/videos", {
    params: folderId ? { folder_id: folderId } : undefined,
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
