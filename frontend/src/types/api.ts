export interface AuthSession {
  authenticated: boolean;
}

export interface Folder {
  id: number;
  name: string;
  cover_path: string | null;
  created_at: string;
}

export interface Video {
  id: number;
  folder_id: number | null;
  title: string;
  cover_path: string | null;
  mime_type: string;
  size: number;
  duration_seconds: number | null;
  manifest_path: string | null;
  source_path: string | null;
  created_at: string;
  segment_count: number;
}

export interface ImportJob {
  id: number;
  source_path: string;
  folder_id: number | null;
  requested_title: string | null;
  status: string;
  progress_percent: number;
  error_message: string | null;
  video_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface PublicSettings {
  baidu_root_path: string;
  cache_limit_bytes: number;
}
