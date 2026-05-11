import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createVideoCacheJob, deleteVideo, fetchVideo, updateVideoMetadata, updateVideoTags } from "../api/client";
import { CoverCard } from "../components/CoverCard";
import { EditableTagList } from "../components/EditableTagList";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError } from "../types/api";
import { formatBytes, formatDateTime, formatDuration } from "../utils/format";

export function VideoDetailPage() {
  const { videoId: rawVideoId } = useParams();
  const videoId = Number(rawVideoId);
  const session = useRequireSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editingTitle, setEditingTitle] = useState("");

  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  const deleteVideoMutation = useMutation({
    mutationFn: () => deleteVideo(videoId),
    onSuccess: async (job) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["imports"] }),
        queryClient.invalidateQueries({ queryKey: ["video", videoId] }),
        queryClient.invalidateQueries({ queryKey: ["videos"] }),
      ]);
      navigate("/manage", {
        replace: true,
        state: { feedback: `已创建任务：${job.task_name}` },
      });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const updateTagsMutation = useMutation({
    mutationFn: (tags: string[]) => updateVideoTags(videoId, tags),
    onSuccess: async () => {
      setFeedback("标签已保存到本地，远端 manifest 会在空闲约 10 分钟后自动同步。");
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["video", videoId] }),
        queryClient.invalidateQueries({ queryKey: ["videos"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const updateMetadataMutation = useMutation({
    mutationFn: (payload: { title: string; tags: string[] }) =>
      updateVideoMetadata({
        videoId,
        title: payload.title,
        tags: payload.tags,
      }),
    onSuccess: async () => {
      setFeedback("视频信息已保存到本地，远端 manifest 会在空闲约 10 分钟后自动同步。");
      setError(null);
      setIsEditingTitle(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["video", videoId] }),
        queryClient.invalidateQueries({ queryKey: ["videos"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const cacheVideoMutation = useMutation({
    mutationFn: () => createVideoCacheJob(videoId),
    onSuccess: async (job) => {
      setFeedback(`已创建任务：${job.task_name}`);
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["imports"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在加载视频详情...</p>;
  }

  if (!Number.isFinite(videoId)) {
    return <p className="state-text">无效的视频 ID。</p>;
  }

  const video = videoQuery.data;
  const isFullyCached = video ? video.segment_count > 0 && video.cached_segment_count >= video.segment_count : false;
  const submitTitle = async () => {
    if (!video) {
      return;
    }
    const normalizedTitle = editingTitle.trim();
    if (!normalizedTitle) {
      setError("视频名称不能为空。");
      setFeedback(null);
      return;
    }
    if (normalizedTitle === video.title) {
      setIsEditingTitle(false);
      return;
    }
    await updateMetadataMutation.mutateAsync({
      title: normalizedTitle,
      tags: video.tags,
    });
  };

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

      {video ? (
        <Surface>
          <div className="detail-layout">
            <Link className="detail-cover detail-cover-link" to={`/videos/${video.id}/play`}>
              <CoverCard artworkPath={video.poster_path ?? video.cover_path} title={video.title} versionToken={videoQuery.dataUpdatedAt} />
            </Link>
            <div className="detail-main">
              {isEditingTitle ? (
                <input
                  autoFocus
                  className="detail-title-input"
                  disabled={updateMetadataMutation.isPending}
                  onBlur={() => {
                    void submitTitle();
                  }}
                  onChange={(event) => setEditingTitle(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void submitTitle();
                    }
                    if (event.key === "Escape") {
                      setIsEditingTitle(false);
                      setEditingTitle(video.title);
                    }
                  }}
                  value={editingTitle}
                />
              ) : (
                <h1
                  className="detail-title"
                  onDoubleClick={() => {
                    setIsEditingTitle(true);
                    setEditingTitle(video.title);
                  }}
                  title="双击修改视频名称"
                >
                  {video.title}
                </h1>
              )}
              <p className="muted">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.mime_type}</p>
              <div className="detail-info">
                <p>Manifest：{video.manifest_path ?? "未生成"}</p>
                <p>创建时间：{formatDateTime(video.created_at)}</p>
                <p>分片数量：{video.segment_count}</p>
                <p>本地缓存：{video.cached_segment_count}/{video.segment_count} 分片 · {formatBytes(video.cached_size_bytes)}</p>
                <p>Poster：{video.poster_path ?? video.cover_path ?? "未设置"}</p>
              </div>
              <div className="action-row">
                <Link className="primary-button link-button" to={`/videos/${video.id}/play`}>
                  播放
                </Link>
                {!isFullyCached ? (
                  <button
                    aria-label="缓存"
                    className="secondary-button icon-button"
                    disabled={cacheVideoMutation.isPending}
                    onClick={() => cacheVideoMutation.mutate()}
                    type="button"
                  >
                    {cacheVideoMutation.isPending ? "缓存中..." : "缓存"}
                  </button>
                ) : null}
                <button
                  className="secondary-button danger-button"
                  disabled={deleteVideoMutation.isPending}
                  onClick={() => {
                    if (!window.confirm(`确认把《${video.title}》加入删除任务队列吗？`)) {
                      return;
                    }
                    deleteVideoMutation.mutate();
                  }}
                  type="button"
                >
                  {deleteVideoMutation.isPending ? "删除中..." : "删除"}
                </button>
              </div>
            </div>
          </div>
        </Surface>
      ) : (
        <Surface>
          <p className="muted">{videoQuery.isLoading ? "正在加载..." : "没有找到这个视频。"}</p>
        </Surface>
      )}

      {video ? (
        <Surface>
          <h2>标签编辑</h2>
          <EditableTagList
            disabled={updateTagsMutation.isPending || updateMetadataMutation.isPending}
            onSave={async (tags) => {
              await updateTagsMutation.mutateAsync(tags);
            }}
            tags={video.tags}
          />
        </Surface>
      ) : null}
    </div>
  );
}
