import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { createImport, fetchFolders, fetchImportJobs, fetchVideos, syncRemoteCatalog } from "../api/client";
import { CoverCard } from "../components/CoverCard";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
import { useRequireSession } from "../hooks/session";
import type { ApiError, ImportJob } from "../types/api";
import { formatBytes, formatDuration, parseTagInput } from "../utils/format";

export function LibraryPage() {
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedFolderId, setSelectedFolderId] = useState<number | undefined>();
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [activeTag, setActiveTag] = useState<string | undefined>();
  const [sourcePath, setSourcePath] = useState("");
  const [title, setTitle] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = searchParams.get("q") ?? "";
    setSearchInput(q);
    setAppliedSearch(q.trim());
  }, [searchParams]);

  const foldersQuery = useQuery({
    queryKey: ["folders"],
    queryFn: fetchFolders,
    enabled: session.data?.authenticated === true,
  });

  const videosQuery = useQuery({
    queryKey: ["videos", selectedFolderId ?? "all", appliedSearch, activeTag ?? ""],
    queryFn: () => fetchVideos({ folderId: selectedFolderId, q: appliedSearch, tag: activeTag }),
    enabled: session.data?.authenticated === true,
  });

  const importsQuery = useQuery({
    queryKey: ["imports"],
    queryFn: fetchImportJobs,
    enabled: session.data?.authenticated === true,
    refetchInterval: (query) => {
      const jobs = query.state.data as ImportJob[] | undefined;
      return jobs?.some((job) => job.status === "queued" || job.status === "running") ? 2000 : false;
    },
  });

  const importMutation = useMutation({
    mutationFn: createImport,
    onSuccess: async () => {
      setFeedback("导入任务已创建，后台会继续执行并自动轮询状态。");
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

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  return (
    <div className="page-stack">
      <Surface>
        <p className="eyebrow">Cloud Storage Player</p>
        <h1>{videos[0]?.title ?? "局域网加密影库"}</h1>
        <p className="muted">third 现在只做参考。当前 frontend/ 已直接接管媒体库、导入、设置、播放页面。</p>
        <div className="pill-row">
          <span className="pill">{videos.length} 个视频</span>
          <span className="pill">{importJobs.length} 个任务</span>
          <span className="pill">{tagCounts.length} 个标签</span>
        </div>
        <div className="action-row">
          <button className="primary-button" disabled={syncMutation.isPending} onClick={() => syncMutation.mutate()} type="button">
            {syncMutation.isPending ? "同步中..." : "同步远端目录"}
          </button>
          <button className="secondary-button" onClick={() => void queryClient.invalidateQueries()} type="button">
            刷新媒体库
          </button>
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
        <h2>筛选与搜索</h2>
        <div className="toolbar-row">
          <input
            className="text-input grow"
            onChange={(event) => setSearchInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                const next = searchInput.trim();
                setAppliedSearch(next);
                setSearchParams(next ? { q: next } : {});
              }
            }}
            placeholder="按标题、源路径、标签搜索"
            value={searchInput}
          />
          <button
            className="secondary-button"
            onClick={() => {
              const next = searchInput.trim();
              setAppliedSearch(next);
              setSearchParams(next ? { q: next } : {});
            }}
            type="button"
          >
            应用搜索
          </button>
          <button
            className="secondary-button"
            onClick={() => {
              setSearchInput("");
              setAppliedSearch("");
              setActiveTag(undefined);
              setSelectedFolderId(undefined);
              setSearchParams({});
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
      </Surface>

      <Surface>
        <h2>导入视频</h2>
        <p className="muted">路径输入仍然面向 Windows 主机本地文件。</p>
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
            {importMutation.isPending ? "创建中..." : "创建导入任务"}
          </button>
        </div>
      </Surface>

      <Surface>
        <h2>导入任务</h2>
        {importJobs.length === 0 ? (
          <p className="muted">当前没有导入任务。</p>
        ) : (
          <div className="job-list">
            {importJobs.slice(0, 6).map((job) => (
              <article className="job-card" key={job.id}>
                <div className="job-head">
                  <strong>#{job.id} · {job.requested_title ?? job.source_path}</strong>
                  <span>{job.status} · {job.progress_percent}%</span>
                </div>
                <p className="muted small-text">{job.source_path}</p>
                {job.error_message ? <p className="error-text">{job.error_message}</p> : null}
              </article>
            ))}
          </div>
        )}
      </Surface>

      <div className="video-grid">
        {videos.map((video) => (
          <Link className="video-card" key={video.id} to={`/videos/${video.id}`}>
            <CoverCard coverPath={video.cover_path} title={video.title} />
            <div className="video-meta">
              <h2>{video.title}</h2>
              <p className="muted">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.segment_count} segments</p>
              <p className="small-text">{video.source_path ?? "未保留源路径"}</p>
              <div className="chip-row compact">
                {video.tags.length > 0 ? (
                  video.tags.map((tag) => (
                    <span className="mini-tag" key={tag}>
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="muted small-text">暂无标签</span>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>

      {videos.length === 0 && !videosQuery.isLoading ? (
        <Surface>
          <p className="muted">当前筛选条件下没有视频。</p>
        </Surface>
      ) : null}
    </div>
  );
}
