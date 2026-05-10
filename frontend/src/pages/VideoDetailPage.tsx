import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteVideo, fetchVideo, updateVideoTags } from "../api/client";
import { CoverCard } from "../components/CoverCard";
import { EditableTagList } from "../components/EditableTagList";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
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
      setFeedback("标签已自动保存。新的 manifest 会在下次 sync 时同步。");
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

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在加载视频详情...</p>;
  }

  if (!Number.isFinite(videoId)) {
    return <p className="state-text">无效的视频 ID。</p>;
  }

  const video = videoQuery.data;
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
            <div className="detail-cover">
              <CoverCard artworkPath={video.poster_path ?? video.cover_path} title={video.title} versionToken={videoQuery.dataUpdatedAt} />
            </div>
            <div className="detail-main">
              <p className="eyebrow">Video #{video.id}</p>
              <h1>{video.title}</h1>
              <p className="muted">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.mime_type}</p>
              <div className="chip-row compact">
                {video.tags.length > 0 ? video.tags.map((tag) => <TagChip key={tag} label={tag} small />) : <span className="muted small-text">暂无标签</span>}
              </div>
              <div className="detail-info">
                <p>源文件：{video.source_path ?? "未保留"}</p>
                <p>Manifest：{video.manifest_path ?? "未生成"}</p>
                <p>创建时间：{formatDateTime(video.created_at)}</p>
                <p>分片数量：{video.segment_count}</p>
                <p>Poster：{video.poster_path ?? video.cover_path ?? "未设置"}</p>
              </div>
              <div className="action-row">
                <Link className="primary-button link-button" to={`/videos/${video.id}/play`}>
                  播放
                </Link>
                <Link className="secondary-button link-button" to="/">
                  返回媒体库
                </Link>
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
                  {deleteVideoMutation.isPending ? "创建中..." : "加入删除任务"}
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
            disabled={updateTagsMutation.isPending}
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
