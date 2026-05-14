import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchVideo, getStreamUrl, reportVideoWatchHeartbeat, updateVideoArtwork } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError, Video, VideoRecommendationShelf } from "../types/api";
import { formatBytes, formatDuration } from "../utils/format";

const POSTER_TARGET = { width: 1280, height: 720 };
const DEFAULT_CROP = { zoom: 1, offsetX: 0, offsetY: 0 };
const WATCH_HEARTBEAT_MS = 10_000;

type CropConfig = typeof DEFAULT_CROP;

function loadImage(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("无法加载截图预览。"));
    image.src = source;
  });
}

async function buildArtworkDataUrl(
  sourceDataUrl: string,
  target: { width: number; height: number },
  crop: CropConfig,
): Promise<string> {
  const image = await loadImage(sourceDataUrl);
  const sourceWidth = image.naturalWidth;
  const sourceHeight = image.naturalHeight;
  const targetRatio = target.width / target.height;
  const sourceRatio = sourceWidth / sourceHeight;

  let baseCropWidth = sourceWidth;
  let baseCropHeight = sourceHeight;
  if (sourceRatio > targetRatio) {
    baseCropWidth = sourceHeight * targetRatio;
  } else {
    baseCropHeight = sourceWidth / targetRatio;
  }

  const cropWidth = baseCropWidth / crop.zoom;
  const cropHeight = baseCropHeight / crop.zoom;
  const maxOffsetX = Math.max((sourceWidth - cropWidth) / 2, 0);
  const maxOffsetY = Math.max((sourceHeight - cropHeight) / 2, 0);
  const centerX = sourceWidth / 2 + crop.offsetX * maxOffsetX;
  const centerY = sourceHeight / 2 + crop.offsetY * maxOffsetY;
  const cropX = Math.min(Math.max(centerX - cropWidth / 2, 0), sourceWidth - cropWidth);
  const cropY = Math.min(Math.max(centerY - cropHeight / 2, 0), sourceHeight - cropHeight);

  const canvas = document.createElement("canvas");
  canvas.width = target.width;
  canvas.height = target.height;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("浏览器当前无法生成预览帧。");
  }
  context.drawImage(image, cropX, cropY, cropWidth, cropHeight, 0, 0, target.width, target.height);
  return canvas.toDataURL("image/jpeg", 0.92);
}

function CropControls({
  title,
  crop,
  onChange,
}: {
  title: string;
  crop: CropConfig;
  onChange: (next: CropConfig) => void;
}) {
  return (
    <div className="crop-controls-card">
      <p className="small-text muted">{title}</p>
      <label className="crop-control-item">
        <span>缩放</span>
        <input
          max="3"
          min="1"
          onChange={(event) => onChange({ ...crop, zoom: Number(event.target.value) })}
          step="0.05"
          type="range"
          value={crop.zoom}
        />
      </label>
      <label className="crop-control-item">
        <span>水平位置</span>
        <input
          max="1"
          min="-1"
          onChange={(event) => onChange({ ...crop, offsetX: Number(event.target.value) })}
          step="0.01"
          type="range"
          value={crop.offsetX}
        />
      </label>
      <label className="crop-control-item">
        <span>垂直位置</span>
        <input
          max="1"
          min="-1"
          onChange={(event) => onChange({ ...crop, offsetY: Number(event.target.value) })}
          step="0.01"
          type="range"
          value={crop.offsetY}
        />
      </label>
    </div>
  );
}

function buildCacheOverlayRanges(video: Video): Array<{ startPercent: number; widthPercent: number }> {
  if (video.size <= 0 || video.cached_byte_ranges.length === 0) {
    return [];
  }
  return video.cached_byte_ranges
    .map((range) => {
      const clampedStart = Math.max(0, Math.min(range.start, video.size));
      const clampedEnd = Math.max(clampedStart, Math.min(range.end, video.size));
      const length = clampedEnd - clampedStart;
      if (length <= 0) {
        return null;
      }
      return {
        startPercent: (clampedStart / video.size) * 100,
        widthPercent: (length / video.size) * 100,
      };
    })
    .filter((value): value is { startPercent: number; widthPercent: number } => value !== null);
}

export function PlayerPage() {
  const { videoId: rawVideoId } = useParams();
  const videoId = Number(rawVideoId);
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const lastHeartbeatAtRef = useRef<number | null>(null);
  const lastPlaybackPositionRef = useRef(0);
  const [capturedDataUrl, setCapturedDataUrl] = useState<string | null>(null);
  const [posterPreviewDataUrl, setPosterPreviewDataUrl] = useState<string | null>(null);
  const [posterCrop, setPosterCrop] = useState<CropConfig>(DEFAULT_CROP);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watchSessionToken, setWatchSessionToken] = useState<string | null>(null);

  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  const refreshVideoCaches = (updatedVideo: Video) => {
    queryClient.setQueryData(["video", videoId], updatedVideo);
    queryClient.setQueriesData({ queryKey: ["videos"] }, (current: unknown) => {
      if (!Array.isArray(current)) {
        if (!current || typeof current !== "object" || !("pages" in current) || !Array.isArray(current.pages)) {
          return current;
        }
        return {
          ...current,
          pages: current.pages.map((page) => {
            if (!page || typeof page !== "object" || !("items" in page) || !Array.isArray(page.items)) {
              return page;
            }
            return {
              ...page,
              items: page.items.map((item: Video) => (item.id === updatedVideo.id ? { ...item, ...updatedVideo } : item)),
            };
          }),
        };
      }
      return current.map((item) => (item.id === updatedVideo.id ? { ...item, ...updatedVideo } : item));
    });
    queryClient.setQueryData(["videos", "recommendations"], (current: VideoRecommendationShelf | undefined) => {
      if (!current) {
        return current;
      }
      const patch = (items: Video[]) => items.map((item) => (item.id === updatedVideo.id ? { ...item, ...updatedVideo } : item));
      return {
        recommended: patch(current.recommended),
        continue_watching: patch(current.continue_watching),
        popular: patch(current.popular),
      };
    });
  };

  useEffect(() => {
    if (!capturedDataUrl) {
      setPosterPreviewDataUrl(null);
      return;
    }
    let active = true;
    buildArtworkDataUrl(capturedDataUrl, POSTER_TARGET, posterCrop)
      .then((poster) => {
        if (!active) {
          return;
        }
        setPosterPreviewDataUrl(poster);
      })
      .catch((exc: Error) => {
        if (!active) {
          return;
        }
        setError(exc.message);
      });
    return () => {
      active = false;
    };
  }, [capturedDataUrl, posterCrop]);

  const artworkMutation = useMutation({
    mutationFn: () =>
      updateVideoArtwork({
        videoId,
        posterDataUrl: posterPreviewDataUrl ?? undefined,
      }),
    onSuccess: async (updatedVideo) => {
      refreshVideoCaches(updatedVideo);
      setCapturedDataUrl(null);
      setFeedback("Poster 已更新。媒体库和推荐位会直接使用这张横版图。");
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["video", videoId] }),
        queryClient.invalidateQueries({ queryKey: ["videos"] }),
        queryClient.invalidateQueries({ queryKey: ["videos", "recommendations"] }),
      ]);
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const watchMutation = useMutation({
    mutationFn: (payload: { positionSeconds: number; watchedSecondsDelta: number; completed?: boolean }) =>
      reportVideoWatchHeartbeat({
        videoId,
        sessionToken: watchSessionToken,
        positionSeconds: payload.positionSeconds,
        watchedSecondsDelta: payload.watchedSecondsDelta,
        completed: payload.completed,
      }),
    onSuccess: (result) => {
      setWatchSessionToken(result.session_token);
      refreshVideoCaches(result.video);
    },
  });

  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement || !Number.isFinite(videoId)) {
      return;
    }

    const sendHeartbeat = (completed: boolean) => {
      const now = Date.now();
      const previousAt = lastHeartbeatAtRef.current;
      const previousPosition = lastPlaybackPositionRef.current;
      const currentPosition = Math.max(videoElement.currentTime || 0, 0);
      lastPlaybackPositionRef.current = currentPosition;
      lastHeartbeatAtRef.current = now;
      if (previousAt === null) {
        return;
      }
      const elapsedSeconds = Math.max((now - previousAt) / 1000, 0);
      const progressedSeconds = Math.max(currentPosition - previousPosition, 0);
      const watchedSecondsDelta = Math.min(elapsedSeconds, progressedSeconds > 0 ? progressedSeconds : elapsedSeconds);
      if (watchedSecondsDelta <= 0 && !completed) {
        return;
      }
      watchMutation.mutate({
        positionSeconds: currentPosition,
        watchedSecondsDelta,
        completed,
      });
    };

    const handlePlay = () => {
      lastHeartbeatAtRef.current = Date.now();
      lastPlaybackPositionRef.current = Math.max(videoElement.currentTime || 0, 0);
    };
    const handlePause = () => sendHeartbeat(false);
    const handleSeeked = () => {
      lastPlaybackPositionRef.current = Math.max(videoElement.currentTime || 0, 0);
      lastHeartbeatAtRef.current = Date.now();
    };
    const handleEnded = () => sendHeartbeat(true);
    const heartbeatTimer = window.setInterval(() => {
      if (!videoElement.paused && !videoElement.ended) {
        sendHeartbeat(false);
      }
    }, WATCH_HEARTBEAT_MS);

    videoElement.addEventListener("play", handlePlay);
    videoElement.addEventListener("pause", handlePause);
    videoElement.addEventListener("seeked", handleSeeked);
    videoElement.addEventListener("ended", handleEnded);

    return () => {
      window.clearInterval(heartbeatTimer);
      videoElement.removeEventListener("play", handlePlay);
      videoElement.removeEventListener("pause", handlePause);
      videoElement.removeEventListener("seeked", handleSeeked);
      videoElement.removeEventListener("ended", handleEnded);
    };
  }, [videoId, watchMutation.mutate]);

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在准备播放...</p>;
  }

  if (!Number.isFinite(videoId)) {
    return <p className="state-text">无效的视频 ID。</p>;
  }

  const video = videoQuery.data;
  const cachedRanges = video ? buildCacheOverlayRanges(video) : [];

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
    setPosterCrop(DEFAULT_CROP);
    setCapturedDataUrl(canvas.toDataURL("image/jpeg", 0.92));
    setFeedback("已捕获当前帧。现在只需要调整一个横版 poster。");
    setError(null);
  };

  const jumpToHighlight = () => {
    const element = videoRef.current;
    if (!element || !video || video.highlight_start_seconds === null) {
      return;
    }
    element.currentTime = video.highlight_start_seconds;
    void element.play().catch(() => undefined);
    setFeedback(`已跳转到高光片段 ${formatDuration(video.highlight_start_seconds)}。`);
    setError(null);
  };

  return (
    <div className="page-stack">
      <Surface>
        <h1>{video?.title ?? `Video #${videoId}`}</h1>
        {video ? (
          <p className="muted">
            {formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.mime_type}
          </p>
        ) : null}
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
        <video
          autoPlay
          className="player-video"
          controls
          crossOrigin="use-credentials"
          preload="metadata"
          ref={videoRef}
          src={getStreamUrl(videoId)}
        />
        {cachedRanges.length > 0 ? (
          <div className="cache-range-overlay" aria-hidden="true">
            {cachedRanges.map((range, index) => (
              <span
                className="cache-range-overlay-segment"
                key={`cache-range-${index}`}
                style={{ left: `${range.startPercent}%`, width: `${range.widthPercent}%` }}
              />
            ))}
          </div>
        ) : null}
      </div>

      {video && video.highlight_start_seconds !== null && video.highlight_end_seconds !== null ? (
        <Surface>
          <div className="section-head">
            <div>
              <h2>高光片段</h2>
              <p className="muted">
                {formatDuration(video.highlight_start_seconds)} - {formatDuration(video.highlight_end_seconds)}
              </p>
            </div>
            <button className="primary-button" onClick={jumpToHighlight} type="button">
              跳到高潮
            </button>
          </div>
        </Surface>
      ) : null}

      <Surface>
        <div className="section-head">
          <div>
            <h2>帧捕获</h2>
            <p className="muted">捕获后会生成固定 16:9 的横版 poster，用于首页推荐位和媒体库缩略图。</p>
          </div>
          <button className="primary-button" onClick={captureCurrentFrame} type="button">
            捕获当前帧
          </button>
        </div>
        {capturedDataUrl && posterPreviewDataUrl ? (
          <div className="artwork-editor">
            <div className="artwork-editor-split">
              <div className="artwork-preview-card artwork-preview-card-compact">
                <p className="small-text muted">Poster 预览（固定横版）</p>
                <img alt="Poster preview" className="artwork-preview-image artwork-preview-poster" src={posterPreviewDataUrl} />
              </div>
              <div className="artwork-controls-shell artwork-controls-shell-stacked">
                <CropControls crop={posterCrop} onChange={setPosterCrop} title="调整横版 poster" />
                <div className="artwork-action-stack">
                  <button className="primary-button" disabled={artworkMutation.isPending} onClick={() => artworkMutation.mutate()} type="button">
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
            </div>
          </div>
        ) : null}
      </Surface>

      <div className="action-row">
        <Link className="secondary-button link-button" to={`/videos/${videoId}`}>
          返回详情
        </Link>
        <Link className="secondary-button link-button" to="/library">
          返回媒体库
        </Link>
      </div>
    </div>
  );
}
