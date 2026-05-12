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
  poster_path: string | null;
  mime_type: string;
  size: number;
  duration_seconds: number | null;
  manifest_path: string | null;
  source_path: string | null;
  created_at: string;
  segment_count: number;
  cached_size_bytes: number;
  cached_segment_count: number;
  tags: string[];
}

export interface ImportJob {
  id: number;
  source_path: string;
  folder_id: number | null;
  requested_title: string | null;
  requested_tags: string[];
  job_kind: string;
  task_name: string;
  status: string;
  progress_percent: number;
  error_message: string | null;
  video_id: number | null;
  target_video_id: number | null;
  cancel_requested: boolean;
  remote_bytes_transferred: number;
  remote_transfer_millis: number;
  transfer_speed_bytes_per_second: number | null;
  created_at: string;
  updated_at: string;
}

export interface ImportFolderResult {
  source_path: string;
  created_job_count: number;
  created_job_ids: number[];
}

export interface ClearedImportJobsResult {
  deleted_job_count: number;
  status_group: "completed" | "failed";
}

export interface CancelAllImportJobsResult {
  updated_job_count: number;
}

export interface CatalogSyncResult {
  discovered_manifest_count: number;
  created_video_count: number;
  updated_video_count: number;
  failed_manifest_count: number;
  errors: string[];
}

export interface PublicSettings {
  baidu_root_path: string;
  cache_limit_bytes: number;
  storage_backend: "mock" | "baidu" | string;
  upload_transfer_concurrency?: number;
  download_transfer_concurrency?: number;
  remote_transfer_concurrency?: number;
  baidu_authorize_url: string | null;
  baidu_has_refresh_token: boolean;
}

export interface CacheSummary {
  total_size_bytes: number;
  video_count: number;
}

export interface CachedVideo {
  id: number;
  title: string;
  poster_path: string | null;
  cover_path: string | null;
  cached_size_bytes: number;
  cached_segment_count: number;
  total_segment_count: number;
}

export interface ClearedCacheResult {
  cleared_video_count: number;
}

export interface ApiError {
  status: number;
  message: string;
}
