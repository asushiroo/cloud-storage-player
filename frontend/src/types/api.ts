export interface AuthSession {
  authenticated: boolean;
}

export interface CachedByteRange {
  start: number;
  end: number;
}

export interface Video {
  id: number;
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
  valid_play_count: number;
  total_session_count: number;
  total_watch_seconds: number;
  last_watched_at: string | null;
  last_position_seconds: number;
  avg_completion_ratio: number;
  bounce_count: number;
  bounce_rate: number;
  rewatch_score: number;
  interest_score: number;
  popularity_score: number;
  resume_score: number;
  recommendation_score: number;
  cache_priority: number;
  like_count: number;
  highlight_start_seconds: number | null;
  highlight_end_seconds: number | null;
  highlight_bucket_count: number;
  highlight_heatmap: number[];
  cached_byte_ranges: CachedByteRange[];
}

export interface VideoRecommendationShelf {
  recommended: Video[];
  continue_watching: Video[];
  popular: Video[];
}

export interface VideoPage {
  items: Video[];
  offset: number;
  limit: number;
  total: number;
  has_more: boolean;
}

export interface VideoWatchHeartbeatResult {
  session_token: string;
  video: Video;
}

export interface ImportJob {
  id: number;
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

export interface FolderImportResult {
  discovered_file_count: number;
  jobs: ImportJob[];
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
  segment_cache_root_path: string;
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
