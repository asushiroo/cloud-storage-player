import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchVideo, getStreamUrl } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import { formatBytes, formatDuration } from "../utils/format";

export function PlayerPage() {
  const { videoId: rawVideoId } = useParams();
  const videoId = Number(rawVideoId);
  const session = useRequireSession();
  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在准备播放...</p>;
  }

  if (!Number.isFinite(videoId)) {
    return <p className="state-text">无效的视频 ID。</p>;
  }

  const video = videoQuery.data;
  return (
    <div className="page-stack">
      <Surface>
        <h1>{video?.title ?? `Video #${videoId}`}</h1>
        {video ? <p className="muted">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.mime_type}</p> : null}
      </Surface>
      <div className="player-surface">
        <video autoPlay className="player-video" controls src={getStreamUrl(videoId)} />
      </div>
      <div className="action-row">
        <Link className="secondary-button link-button" to={`/videos/${videoId}`}>
          返回详情
        </Link>
        <Link className="secondary-button link-button" to="/">
          返回媒体库
        </Link>
      </div>
    </div>
  );
}
