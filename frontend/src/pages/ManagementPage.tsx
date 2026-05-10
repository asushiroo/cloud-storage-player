import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  cancelAllImportJobs,
  cancelImportJob,
  clearFinishedImportJobs,
  createFolderImport,
  createImport,
  fetchFolders,
  fetchImportJobs,
  fetchVideos,
  syncRemoteCatalog,
} from "../api/client";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
import { useRequireSession } from "../hooks/session";
import type { ApiError, ImportJob } from "../types/api";
import { formatBytes, formatDuration, parseTagInput } from "../utils/format";

const ACTIVE_JOB_STATUSES = new Set(["queued", "running", "cancelling"]);

function describeJob(job: ImportJob) {
  if (job.job_kind === "delete") {
    return `删除任务 · ${job.status} · ${job.progress_percent}%`;
  }
  return `导入任务 · ${job.status} · ${job.progress_percent}%`;
}

export function ManagementPage() {
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const location = useLocation();
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [activeTag, setActiveTag] = useState<string | undefined>();
  const [selectedFolderId, setSelectedFolderId] = useState<number | undefined>();
  const [sourcePath, setSourcePath] = useState("");
  const [title, setTitle] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [folderSourcePath, setFolderSourcePath] = useState("");
  const [folderTagInput, setFolderTagInput] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const message = (location.state as { feedback?: string } | null)?.feedback;
    if (!message) {
      return;
    }
    setFeedback(message);
  }, [location.state]);

  const foldersQuery = useQuery({
    queryKey: ["folders"],
    queryFn: fetchFolders,
    enabled: session.data?.authenticated === true,
  });
  const videosQuery = useQuery({
    queryKey: ["videos", "manage-search", selectedFolderId ?? "all", appliedSearch, activeTag ?? ""],
    queryFn: () => fetchVideos({ folderId: selectedFolderId, q: appliedSearch, tag: activeTag }),
    enabled: session.data?.authenticated === true,
  });
  const importsQuery = useQuery({
    queryKey: ["imports"],
    queryFn: fetchImportJobs,
    enabled: session.data?.authenticated === true,
    refetchInterval: (query) => {
      const jobs = query.state.data as ImportJob[] | undefined;
      return jobs?.some((job) => ACTIVE_JOB_STATUSES.has(job.status)) ? 2000 : false;
    },
  });

  const folders = foldersQuery.data ?? [];
  const videos = videosQuery.data ?? [];
  const importJobs = importsQuery.data ?? [];
  const tagCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const video of videos) {
      for (const tag of video.tags) {
        counts.set(tag, (counts.get(tag) ?? 0) + 1);
      }
    }
    return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
  }, [videos]);

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
      setFeedback(`文件夹导入已入队，共创建 ${result.created_job_count} 个任务。`);
      setError(null);
      setFolderSourcePath("");
      setFolderTagInput("");
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

  const clearJobsMutation = useMutation({
    mutationFn: clearFinishedImportJobs,
    onSuccess: async (result) => {
      setFeedback(`已清理 ${result.deleted_job_count} 条已完成/失败/已取消任务。`);
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

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  return (
    <div className="page-stack">
      <Surface>
        <p className="eyebrow">管理页</p>
        <h1>搜索、导入与任务管理</h1>
        <p className="muted">首页现在只保留推荐 Banner 和媒体库，这里承载搜索、单文件导入、文件夹批量导入、同步与任务清理。</p>
        <div className="action-row">
          <button className="primary-button" disabled={syncMutation.isPending} onClick={() => syncMutation.mutate()} type="button">
            {syncMutation.isPending ? "同步中..." : "同步远端目录"}
          </button>
          <Link className="secondary-button link-button" to="/">
            返回首页媒体库
          </Link>
        </div>
      </Surface>

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
        <h2>搜索媒体库</h2>
        <div className="toolbar-row">
          <input
            className="text-input grow"
            onChange={(event) => setSearchInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                setAppliedSearch(searchInput.trim());
              }
            }}
            placeholder="按标题、源路径、标签搜索"
            value={searchInput}
          />
          <button className="secondary-button" onClick={() => setAppliedSearch(searchInput.trim())} type="button">
            应用搜索
          </button>
          <button
            className="secondary-button"
            onClick={() => {
              setSearchInput("");
              setAppliedSearch("");
              setActiveTag(undefined);
              setSelectedFolderId(undefined);
            }}
            type="button"
          >
            清空
          </button>
        </div>
        <div className="chip-row">
          <TagChip active={selectedFolderId === undefined} label="全部目录" onClick={() => setSelectedFolderId(undefined)} />
          {folders.map((folder) => (
            <TagChip key={folder.id} active={selectedFolderId === folder.id} label={folder.name} onClick={() => setSelectedFolderId(folder.id)} />
          ))}
        </div>
        {tagCounts.length > 0 ? (
          <div className="chip-row">
            {tagCounts.map(([tag, count]) => (
              <TagChip key={tag} active={activeTag === tag} label={`${tag} (${count})`} onClick={() => setActiveTag(activeTag === tag ? undefined : tag)} />
            ))}
          </div>
        ) : null}
        <div className="manage-result-list">
          {videos.map((video) => (
            <Link className="manage-result-card" key={video.id} to={`/videos/${video.id}`}>
              <strong>{video.title}</strong>
              <span className="muted small-text">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)}</span>
            </Link>
          ))}
          {videos.length === 0 ? <p className="muted">当前搜索条件下没有视频。</p> : null}
        </div>
      </Surface>

      <div className="management-grid">
        <Surface>
          <h2>导入单个视频</h2>
          <p className="muted">单文件导入可自定义标题；后台仍按单任务执行。</p>
          <div className="form-stack">
            <input className="text-input" onChange={(event) => setSourcePath(event.target.value)} placeholder="例如：D:\\Videos\\movie.mp4" value={sourcePath} />
            <input className="text-input" onChange={(event) => setTitle(event.target.value)} placeholder="可选：显示标题" value={title} />
            <input className="text-input" onChange={(event) => setTagInput(event.target.value)} placeholder="可选：标签，逗号分隔" value={tagInput} />
            <button
              className="primary-button"
              disabled={importMutation.isPending || sourcePath.trim().length === 0}
              onClick={() =>
                importMutation.mutate({
                  source_path: sourcePath,
                  title: title || null,
                  folder_id: selectedFolderId ?? null,
                  tags: parseTagInput(tagInput),
                })
              }
              type="button"
            >
              {importMutation.isPending ? "创建中..." : "创建单文件导入任务"}
            </button>
          </div>
        </Surface>

        <Surface>
          <h2>导入整个文件夹</h2>
          <p className="muted">按递归方式扫描常见视频格式；每个视频文件会创建一个独立导入任务。</p>
          <div className="form-stack">
            <input className="text-input" onChange={(event) => setFolderSourcePath(event.target.value)} placeholder="例如：D:\\Anime\\Season1" value={folderSourcePath} />
            <input className="text-input" onChange={(event) => setFolderTagInput(event.target.value)} placeholder="可选：给整个文件夹导入统一打标签" value={folderTagInput} />
            <button
              className="primary-button"
              disabled={folderImportMutation.isPending || folderSourcePath.trim().length === 0}
              onClick={() =>
                folderImportMutation.mutate({
                  source_path: folderSourcePath,
                  folder_id: selectedFolderId ?? null,
                  tags: parseTagInput(folderTagInput),
                })
              }
              type="button"
            >
              {folderImportMutation.isPending ? "批量入队中..." : "导入整个文件夹"}
            </button>
          </div>
        </Surface>
      </div>

      <Surface>
        <div className="section-head">
          <div>
            <h2>任务栏</h2>
            <p className="muted">导入和删除都会显示在这里；运行中的任务支持单条取消，也支持一键全部取消。</p>
          </div>
          <div className="action-row">
            <button className="secondary-button danger-button" disabled={cancelAllMutation.isPending} onClick={() => cancelAllMutation.mutate()} type="button">
              {cancelAllMutation.isPending ? "请求中..." : "取消全部活动任务"}
            </button>
            <button className="secondary-button" disabled={clearJobsMutation.isPending} onClick={() => clearJobsMutation.mutate()} type="button">
              {clearJobsMutation.isPending ? "清理中..." : "清理已完成任务"}
            </button>
          </div>
        </div>
        {importJobs.length === 0 ? (
          <p className="muted">当前没有任务。</p>
        ) : (
          <div className="job-list">
            {importJobs.map((job) => (
              <article className="job-card" key={job.id}>
                <div className="job-head">
                  <div className="job-head-main">
                    <strong>#{job.id} · {job.task_name}</strong>
                    <span className="muted small-text">{describeJob(job)}</span>
                  </div>
                  {ACTIVE_JOB_STATUSES.has(job.status) ? (
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
                <p className="muted small-text">{job.source_path || "无源路径"}</p>
                {job.requested_tags.length > 0 ? (
                  <div className="chip-row compact top-gap">
                    {job.requested_tags.map((tag) => (
                      <span className="mini-tag" key={`${job.id}-${tag}`}>
                        {tag}
                      </span>
                    ))}
                  </div>
                ) : null}
                {job.video_id ? (
                  <div className="top-gap">
                    <Link className="secondary-button link-button" to={`/videos/${job.video_id}`}>
                      查看视频
                    </Link>
                  </div>
                ) : null}
                {job.error_message ? <p className="error-text top-gap">{job.error_message}</p> : null}
              </article>
            ))}
          </div>
        )}
      </Surface>
    </div>
  );
}
