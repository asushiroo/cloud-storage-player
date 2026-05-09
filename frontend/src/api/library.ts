import { http } from "./http";
import type { Folder, Video } from "../types/api";

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
