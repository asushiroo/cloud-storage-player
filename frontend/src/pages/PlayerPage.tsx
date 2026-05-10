import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchVideo, getStreamUrl, updateVideoArtwork } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError } from "../types/api";
import { formatBytes, formatDuration } from "../utils/format";

export function PlayerPage() {
  const { videoId: rawVideoId } = useParams();
  const videoId = Number(rawVideoId);
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [capturedDataUrl, setCapturedDataUrl] = useState<string | null>(null);
  const [replaceCover, setReplaceCover] = useState(true);
  const [replacePoster, setReplacePoster] = useState(true);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  const artworkMutation = useMutation({
    mutationFn: (dataUrl: string) =>
      updateVideoArtwork({
        videoId,
        coverDataUrl: replaceCover ? dataUrl : undefined,
        posterDataUrl: replacePoster ? dataUrl : undefined,
      }),
    onSuccess: async () => {
      setFeedback("封面 / Poster 已更新。首页轮播会优先使用 poster，视频卡片继续使用 cover。");
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
    return <p className="state-text">正在准备播放...</p>;
  }

  if (!Number.isFinite(videoId)) {
    return <p className="state-text">无效的视频 ID。</p>;
  }

  const video = videoQuery.data;

  const captureCurrentFrame = () => {
    const element = videoRef.current;
    if (!element || element.readyState < 2 || element.videoWidth <= 0 || element.videoHeight <= 0) {
      setError("当前帧还不可用，请等待视频加载后再捕获。");
      setFeedback(null);
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = element.videoWidth;
    canvas.height = element.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      setError("浏览器当前无法生成预览帧。");
      setFeedback(null);
      return;
    }
    context.drawImage(element, 0, 0, canvas.width, canvas.height);
    setCapturedDataUrl(canvas.toDataURL("image/jpeg", 0.92));
    setFeedback("已捕获当前帧，请预览后选择替换 cover / poster。");
    setError(null);
  };

  return (
    <div className="page-stack">
      <Surface>
        <h1>{video?.title ?? `Video #${videoId}`}</h1>
        {video ? <p className="muted">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.mime_type}</p> : null}
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
      <div className="player-surface">
        <video autoPlay className="player-video" controls ref={videoRef} src={getStreamUrl(videoId)} />
      </div>
      <Surface>
        <div className="section-head">
          <div>
            <h2>帧捕获</h2>
            <p className="muted">在播放界面直接截取当前帧，预览后选择是否替换数据库中的 cover 与首页轮播 poster。</p>
          </div>
          <button className="primary-button" onClick={captureCurrentFrame} type="button">
            捕获当前帧
          </button>
        </div>
        {capturedDataUrl ? (
          <div className="artwork-editor">
            <div className="artwork-preview-grid">
              <div className="artwork-preview-card">
                <p className="small-text muted">Cover 预览</p>
                <img alt="Cover preview" className="artwork-preview-image artwork-preview-cover" src={capturedDataUrl} />
              </div>
              <div className="artwork-preview-card">
                <p className="small-text muted">Poster 预览</p>
                <img alt="Poster preview" className="artwork-preview-image artwork-preview-poster" src={capturedDataUrl} />
              </div>
            </div>
            <div className="checkbox-row">
              <label className="checkbox-item">
                <input checked={replaceCover} onChange={(event) => setReplaceCover(event.target.checked)} type="checkbox" />
                替换 cover
              </label>
              <label className="checkbox-item">
                <input checked={replacePoster} onChange={(event) => setReplacePoster(event.target.checked)} type="checkbox" />
                替换 poster
              </label>
            </div>
            <div className="action-row">
              <button
                className="primary-button"
                disabled={artworkMutation.isPending || (!replaceCover && !replacePoster)}
                onClick={() => artworkMutation.mutate(capturedDataUrl)}
                type="button"
              >
                {artworkMutation.isPending ? "保存中..." : "应用到数据库"}
              </button>
              <button
                className="secondary-button"
                onClick={() => {
                  setCapturedDataUrl(null);
                  setFeedback(null);
                  setError(null);
                }}
                type="button"
              >
                丢弃预览
              </button>
            </div>
          </div>
        ) : null}
      </Surface>
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
