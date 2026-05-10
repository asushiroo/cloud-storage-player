import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  cancelAllImportJobs,
  cancelImportJob,
  clearFinishedImportJobs,
  createFolderImport,
  createImport,
  fetchFolders,
  fetchImportJobs,
  syncRemoteCatalog,
} from "../api/client";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
import { useRequireSession } from "../hooks/session";
import type { ApiError, ImportJob } from "../types/api";
import { parseTagInput } from "../utils/format";

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
  const importJobs = importsQuery.data ?? [];

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
      setFeedback(`已清理 ${result.deleted_job_count} 条失败 / 已取消任务。`);
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
        <h1>导入与任务管理</h1>
        <p className="muted">搜索媒体库已经移动到首页，这里专注导入、同步和任务控制。</p>
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
        <h2>导入目录</h2>
        <p className="muted">新导入的视频会写入当前选中的目录；不选则为未分类。</p>
        <div className="chip-row top-gap">
          <TagChip active={selectedFolderId === undefined} label="未分类" onClick={() => setSelectedFolderId(undefined)} />
          {folders.map((folder) => (
            <TagChip key={folder.id} active={selectedFolderId === folder.id} label={folder.name} onClick={() => setSelectedFolderId(folder.id)} />
          ))}
        </div>
      </Surface>

      <div className="management-grid">
        <Surface>
          <h2>导入单个视频</h2>
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
