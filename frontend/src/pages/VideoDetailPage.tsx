import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchVideo, updateVideoTags } from "../api/client";
import { CoverCard } from "../components/CoverCard";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
import { useRequireSession } from "../hooks/session";
import type { ApiError } from "../types/api";
import { formatBytes, formatDateTime, formatDuration, parseTagInput } from "../utils/format";

export function VideoDetailPage() {
  const { videoId: rawVideoId } = useParams();
  const videoId = Number(rawVideoId);
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const [tagInput, setTagInput] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  useEffect(() => {
    if (videoQuery.data) {
      setTagInput(videoQuery.data.tags.join(", "));
    }
  }, [videoQuery.data]);

  const updateTagsMutation = useMutation({
    mutationFn: (tags: string[]) => updateVideoTags(videoId, tags),
    onSuccess: async (video) => {
      setFeedback("标签已更新。新的 manifest 会在下次 sync 时同步。");
      setError(null);
      setTagInput(video.tags.join(", "));
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
              <CoverCard coverPath={video.cover_path} title={video.title} />
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
              </div>
              <div className="action-row">
                <Link className="primary-button link-button" to={`/videos/${video.id}/play`}>
                  播放
                </Link>
                <Link className="secondary-button link-button" to="/">
                  返回媒体库
                </Link>
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
          <div className="form-stack">
            <input className="text-input" onChange={(event) => setTagInput(event.target.value)} placeholder="输入标签，逗号分隔" value={tagInput} />
            <button className="primary-button" disabled={updateTagsMutation.isPending} onClick={() => updateTagsMutation.mutate(parseTagInput(tagInput))} type="button">
              {updateTagsMutation.isPending ? "保存中..." : "保存标签"}
            </button>
          </div>
        </Surface>
      ) : null}
    </div>
  );
}
