import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  cancelAllImportJobs,
  cancelImportJob,
  clearAllCachedVideos,
  clearCachedVideo,
  clearFinishedImportJobs,
  createFolderImport,
  createImport,
  fetchCacheSummary,
  fetchCachedVideos,
  fetchImportJobs,
  syncRemoteCatalog,
} from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError, CachedVideo, ImportJob } from "../types/api";
import { buildAssetUrl } from "../api/client";
import { formatBytes, parseTagInput } from "../utils/format";

const ACTIVE_JOB_STATUSES = new Set(["queued", "running", "cancelling"]);
const ERROR_MESSAGE_PREVIEW_MAX_LENGTH = 240;
const IMPORT_MODE_OPTIONS = [
  { value: "file", label: "导入视频" },
  { value: "folder", label: "导入文件夹" },
] as const;

type ImportMode = (typeof IMPORT_MODE_OPTIONS)[number]["value"];

function canCancelJob(job: ImportJob) {
  return job.job_kind !== "delete" && ACTIVE_JOB_STATUSES.has(job.status);
}

function describeJob(job: ImportJob) {
  if (job.job_kind === "delete") {
    return `删除任务 · ${job.status} · ${job.progress_percent}%`;
  }
  if (job.job_kind === "cache") {
    return `缓存任务 · ${job.status} · ${job.progress_percent}%`;
  }
  return `导入任务 · ${job.status} · ${job.progress_percent}%`;
}

function shouldCollapseErrorMessage(message: string) {
  return message.length > ERROR_MESSAGE_PREVIEW_MAX_LENGTH || message.includes("\n");
}

export function ManagementPage() {
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const location = useLocation();
  const [importMode, setImportMode] = useState<ImportMode>("file");
  const [sourcePath, setSourcePath] = useState("");
  const [sourceDir, setSourceDir] = useState("");
  const [title, setTitle] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [showCachePanel, setShowCachePanel] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const message = (location.state as { feedback?: string } | null)?.feedback;
    if (!message) {
      return;
    }
    setFeedback(message);
  }, [location.state]);

  const importsQuery = useQuery({
    queryKey: ["imports"],
    queryFn: fetchImportJobs,
    enabled: session.data?.authenticated === true,
    refetchInterval: (query) => {
      const jobs = query.state.data as ImportJob[] | undefined;
      return jobs?.some((job) => ACTIVE_JOB_STATUSES.has(job.status)) ? 2000 : false;
    },
  });

  const importJobs = importsQuery.data ?? [];
  const cacheSummaryQuery = useQuery({
    queryKey: ["cache-summary"],
    queryFn: fetchCacheSummary,
    enabled: session.data?.authenticated === true,
  });
  const cachedVideosQuery = useQuery({
    queryKey: ["cached-videos"],
    queryFn: fetchCachedVideos,
    enabled: session.data?.authenticated === true && showCachePanel,
  });

  const importMutation = useMutation({
    mutationFn: createImport,
    onSuccess: async (job) => {
      setFeedback(`已创建任务：${job.task_name}`);
      setError(null);
      setSourcePath("");
      setTitle("");
      setTagInput("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["imports"] }),
        queryClient.invalidateQueries({ queryKey: ["videos"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const folderImportMutation = useMutation({
    mutationFn: createFolderImport,
    onSuccess: async (result) => {
      setFeedback(`已从文件夹发现 ${result.discovered_file_count} 个视频并创建导入任务。`);
      setError(null);
      setSourceDir("");
      setTagInput("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["imports"] }),
        queryClient.invalidateQueries({ queryKey: ["videos"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const cancelJobMutation = useMutation({
    mutationFn: cancelImportJob,
    onSuccess: async (job) => {
      setFeedback(`已请求取消：${job.task_name}`);
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const cancelAllMutation = useMutation({
    mutationFn: cancelAllImportJobs,
    onSuccess: async (result) => {
      setFeedback(`已请求取消 ${result.updated_job_count} 条活动任务。`);
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const clearCompletedJobsMutation = useMutation({
    mutationFn: () => clearFinishedImportJobs("completed"),
    onSuccess: async (result) => {
      setFeedback(`已清理 ${result.deleted_job_count} 条已完成任务。`);
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const clearFailedJobsMutation = useMutation({
    mutationFn: () => clearFinishedImportJobs("failed"),
    onSuccess: async (result) => {
      setFeedback(`已清理 ${result.deleted_job_count} 条失败/取消任务。`);
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const syncMutation = useMutation({
    mutationFn: syncRemoteCatalog,
    onSuccess: async (result) => {
      setFeedback(`发现 ${result.discovered_manifest_count} 个 manifest，新增 ${result.created_video_count} 个视频，更新 ${result.updated_video_count} 个视频。`);
      setError(result.errors.length > 0 ? result.errors.join("；") : null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["imports"] }),
        queryClient.invalidateQueries({ queryKey: ["videos"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const clearAllCacheMutation = useMutation({
    mutationFn: clearAllCachedVideos,
    onSuccess: async (result) => {
      setFeedback(`已清理 ${result.cleared_video_count} 个视频的本地缓存。`);
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["cache-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["cached-videos"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const clearSingleCacheMutation = useMutation({
    mutationFn: (videoId: number) => clearCachedVideo(videoId),
    onSuccess: async () => {
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["cache-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["cached-videos"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  return (
    <div className="page-stack">
      {error ? (
        <Surface>
          <p className="error-text">{error}</p>
        </Surface>
      ) : null}
      {feedback ? (
        <Surface>
          <p>{feedback}</p>
        </Surface>
      ) : null}

      <Surface>
        <div className="section-head">
          <div>
            <h2>本地缓存</h2>
            <p className="muted">
              当前缓存：{formatBytes(cacheSummaryQuery.data?.total_size_bytes ?? 0)} · {cacheSummaryQuery.data?.video_count ?? 0} 个视频
            </p>
          </div>
          <div className="action-row">
            <button
              className="secondary-button"
              onClick={() => setShowCachePanel((value) => !value)}
              type="button"
            >
              {showCachePanel ? "收起缓存列表" : "查看缓存"}
            </button>
          </div>
        </div>
        {showCachePanel ? (
          <div className="cache-panel top-gap">
            <div className="section-head">
              <p className="muted">仅展示当前后端本地仍保留分片缓存的视频。</p>
              <button
                className="secondary-button danger-button"
                disabled={clearAllCacheMutation.isPending || (cachedVideosQuery.data?.length ?? 0) === 0}
                onClick={() => {
                  if (!window.confirm("确认清理全部本地缓存吗？")) {
                    return;
                  }
                  clearAllCacheMutation.mutate();
                }}
                type="button"
              >
                {clearAllCacheMutation.isPending ? "清理中..." : "清理全部缓存"}
              </button>
            </div>
            {cachedVideosQuery.data && cachedVideosQuery.data.length > 0 ? (
              <div className="cache-grid">
                {cachedVideosQuery.data.map((video) => (
                  <CachedVideoCard
                    disabled={clearSingleCacheMutation.isPending}
                    key={video.id}
                    onClear={() => {
                      if (!window.confirm(`确认清理《${video.title}》的本地缓存吗？`)) {
                        return;
                      }
                      clearSingleCacheMutation.mutate(video.id);
                    }}
                    video={video}
                  />
                ))}
              </div>
            ) : (
              <p className="muted">{cachedVideosQuery.isLoading ? "正在加载缓存列表..." : "当前没有本地缓存。"}</p>
            )}
          </div>
        ) : null}
      </Surface>

      <div className="section-divider" />

      <Surface>
        <div className="action-row">
          <button
            className="primary-button"
            style={{ width: "100%" }}
            disabled={syncMutation.isPending}
            onClick={() => syncMutation.mutate()}
            type="button"
          >
            {syncMutation.isPending ? "同步中..." : "同步远端目录"}
          </button>
        </div>
      </Surface>

      <div className="section-divider" />

      <div className="management-grid management-grid-single">
        <Surface>
          <h2>导入</h2>
          <div className="form-stack top-gap">
            <div className="chip-row compact">
              {IMPORT_MODE_OPTIONS.map((option) => (
                <button
                  className={`chip ${importMode === option.value ? "chip-active" : "chip-outline"}`}
                  key={option.value}
                  onClick={() => setImportMode(option.value)}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>
            {importMode === "file" ? (
              <>
                <input
                  className="text-input"
                  onChange={(event) => setSourcePath(event.target.value)}
                  placeholder="例如：D:\\Videos\\movie.mp4"
                  value={sourcePath}
                />
                <input
                  className="text-input"
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="可选：显示标题"
                  value={title}
                />
              </>
            ) : (
              <input
                className="text-input"
                onChange={(event) => setSourceDir(event.target.value)}
                placeholder="例如：D:\\Videos\\Anime"
                value={sourceDir}
              />
            )}
            <input
              className="text-input"
              onChange={(event) => setTagInput(event.target.value)}
              placeholder="可选：标签，逗号分隔"
              value={tagInput}
            />
            <button
              className="primary-button"
              disabled={
                importMutation.isPending ||
                folderImportMutation.isPending ||
                (importMode === "file" ? sourcePath.trim().length === 0 : sourceDir.trim().length === 0)
              }
              onClick={() => {
                const tags = parseTagInput(tagInput);
                if (importMode === "file") {
                  importMutation.mutate({
                    source_path: sourcePath,
                    title: title || null,
                    tags,
                  });
                  return;
                }
                folderImportMutation.mutate({
                  source_dir: sourceDir,
                  tags,
                });
              }}
              type="button"
            >
              {importMutation.isPending || folderImportMutation.isPending
                ? "创建中..."
                : importMode === "file"
                  ? "创建导入任务"
                  : "创建批量导入任务"}
            </button>
          </div>
        </Surface>
      </div>

      <div className="section-divider" />

      <Surface>
        <div className="section-head">
          <div>
            <h2>任务栏</h2>
          </div>
          <div className="action-row">
            <button className="secondary-button danger-button" disabled={cancelAllMutation.isPending} onClick={() => cancelAllMutation.mutate()} type="button">
              {cancelAllMutation.isPending ? "请求中..." : "取消全部导入/缓存任务"}
            </button>
            <button
              className="secondary-button"
              disabled={clearCompletedJobsMutation.isPending}
              onClick={() => clearCompletedJobsMutation.mutate()}
              type="button"
            >
              {clearCompletedJobsMutation.isPending ? "清理中..." : "清理已完成任务"}
            </button>
            <button
              className="secondary-button"
              disabled={clearFailedJobsMutation.isPending}
              onClick={() => clearFailedJobsMutation.mutate()}
              type="button"
            >
              {clearFailedJobsMutation.isPending ? "清理中..." : "清理失败/取消任务"}
            </button>
          </div>
        </div>
        {importJobs.length === 0 ? (
          <p className="muted">当前没有任务。</p>
        ) : (
          <div className="job-list">
            {importJobs.map((job) => (
              <JobCard
                cancelJobMutation={cancelJobMutation}
                job={job}
                key={job.id}
              />
            ))}
          </div>
        )}
      </Surface>
    </div>
  );
}

interface JobCardProps {
  job: ImportJob;
  cancelJobMutation: ReturnType<typeof useMutation<ImportJob, ApiError, number>>;
}

function JobCard({ job, cancelJobMutation }: JobCardProps) {
  const [showFullError, setShowFullError] = useState(false);
  const canCollapseError = job.error_message ? shouldCollapseErrorMessage(job.error_message) : false;

  return (
    <article className="job-card">
      <div className="job-head">
        <div className="job-head-main">
          <strong>#{job.id} · {job.task_name}</strong>
          <span className="muted small-text">{describeJob(job)}</span>
        </div>
        <div className="job-head-actions">
          {job.video_id ? (
            <Link className="secondary-button link-button" to={`/videos/${job.video_id}`}>
              查看视频
            </Link>
          ) : null}
          {canCancelJob(job) ? (
            <button
              className="secondary-button danger-button"
              disabled={cancelJobMutation.isPending}
              onClick={() => cancelJobMutation.mutate(job.id)}
              type="button"
            >
              {job.status === "cancelling" ? "取消中..." : "取消"}
            </button>
          ) : null}
        </div>
      </div>
      {job.transfer_speed_bytes_per_second ? (
        <p className="muted small-text top-gap">
          网速：{formatBytes(job.transfer_speed_bytes_per_second)}/s · 已传输 {formatBytes(job.remote_bytes_transferred)}
        </p>
      ) : null}
      {job.requested_tags.length > 0 ? (
        <div className="chip-row compact top-gap">
          {job.requested_tags.map((tag) => (
            <span className="mini-tag" key={`${job.id}-${tag}`}>
              {tag}
            </span>
          ))}
        </div>
      ) : null}
      {job.error_message ? (
        <div className="job-error-block top-gap">
          <p className={`error-text job-error-message${showFullError ? " is-expanded" : ""}`}>
            {job.error_message}
          </p>
          {canCollapseError ? (
            <button
              className="job-error-toggle"
              onClick={() => setShowFullError((value) => !value)}
              type="button"
            >
              {showFullError ? "收起详情" : "展开详情"}
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

interface CachedVideoCardProps {
  video: CachedVideo;
  disabled: boolean;
  onClear: () => void;
}

function CachedVideoCard({ video, disabled, onClear }: CachedVideoCardProps) {
  const artworkUrl = buildAssetUrl(video.poster_path ?? video.cover_path);

  return (
    <article className="cache-card">
      <div className="cache-card-cover">
        {artworkUrl ? <img alt={video.title} className="cover-image" src={artworkUrl} /> : <div className="cover-placeholder">No Cover</div>}
        <button
          aria-label={`清理 ${video.title} 缓存`}
          className="cache-card-delete"
          disabled={disabled}
          onClick={onClear}
          type="button"
        >
          ×
        </button>
      </div>
      <div className="cache-card-meta">
        <strong>{video.title}</strong>
        <span className="muted small-text">
          {formatBytes(video.cached_size_bytes)} · {video.cached_segment_count}/{video.total_segment_count} 分片
        </span>
      </div>
    </article>
  );
}
