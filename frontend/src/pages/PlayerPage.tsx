import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchVideo, getStreamUrl, updateVideoArtwork } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError, Video } from "../types/api";
import { formatBytes, formatDuration } from "../utils/format";

const POSTER_TARGET = { width: 1280, height: 720 };
const DEFAULT_CROP = { zoom: 1, offsetX: 0, offsetY: 0 };
const OVERLAY_HIDE_DELAY_MS = 500;

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

export function PlayerPage() {
  const { videoId: rawVideoId } = useParams();
  const videoId = Number(rawVideoId);
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const overlayHideTimerRef = useRef<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [showOverlay, setShowOverlay] = useState(false);
  const [capturedDataUrl, setCapturedDataUrl] = useState<string | null>(null);
  const [posterPreviewDataUrl, setPosterPreviewDataUrl] = useState<string | null>(null);
  const [posterCrop, setPosterCrop] = useState<CropConfig>(DEFAULT_CROP);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  useEffect(() => {
    return () => {
      if (overlayHideTimerRef.current !== null) {
        window.clearTimeout(overlayHideTimerRef.current);
      }
    };
  }, []);

  const refreshVideoCaches = (updatedVideo: Video) => {
    queryClient.setQueryData(["video", videoId], updatedVideo);
    queryClient.setQueriesData({ queryKey: ["videos"] }, (current: Video[] | undefined) => {
      if (!Array.isArray(current)) {
        return current;
      }
      return current.map((item) => (item.id === updatedVideo.id ? { ...item, ...updatedVideo } : item));
    });
  };

  const armOverlayHideTimer = () => {
    if (overlayHideTimerRef.current !== null) {
      window.clearTimeout(overlayHideTimerRef.current);
    }
    overlayHideTimerRef.current = window.setTimeout(() => {
      setShowOverlay(false);
      overlayHideTimerRef.current = null;
    }, OVERLAY_HIDE_DELAY_MS);
  };

  const revealOverlay = () => {
    setShowOverlay(true);
    armOverlayHideTimer();
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
      setFeedback("Poster 已更新。媒体库和首页推荐位都会直接使用这张横版图。");
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

  const seekBy = (seconds: number) => {
    const element = videoRef.current;
    if (!element || !Number.isFinite(element.duration)) {
      return;
    }
    revealOverlay();
    const nextTime = Math.min(Math.max(element.currentTime + seconds, 0), element.duration);
    element.currentTime = nextTime;
  };

  const togglePlayback = () => {
    const element = videoRef.current;
    if (!element) {
      return;
    }
    revealOverlay();
    if (element.paused) {
      void element.play();
      return;
    }
    element.pause();
  };

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
      <div
        className="player-surface"
        onClick={(event) => {
          if (event.target instanceof HTMLButtonElement) {
            return;
          }
          revealOverlay();
        }}
      >
        <video
          autoPlay
          className="player-video"
          controls
          onEnded={() => {
            setIsPlaying(false);
          }}
          onLoadedMetadata={() => {
            setIsPlaying(!(videoRef.current?.paused ?? true));
          }}
          onPause={() => {
            setIsPlaying(false);
          }}
          onPlay={() => {
            setIsPlaying(true);
          }}
          ref={videoRef}
          src={getStreamUrl(videoId)}
        />
        <div className={`player-overlay ${showOverlay ? "player-overlay-visible" : "player-overlay-hidden"}`}>
          <button
            aria-label="后退 10 秒"
            className="player-overlay-zone player-overlay-zone-left"
            onClick={() => seekBy(-10)}
            type="button"
          >
            <span className="player-overlay-icon-shell">
              <span className="material-symbols-rounded player-overlay-icon">replay_10</span>
            </span>
          </button>
          <button
            aria-label={isPlaying ? "暂停播放" : "开始播放"}
            className="player-overlay-zone player-overlay-zone-center"
            onClick={togglePlayback}
            type="button"
          >
            <span className="player-overlay-icon-shell player-overlay-icon-shell-center">
              <span className="material-symbols-rounded player-overlay-icon">{isPlaying ? "pause" : "play_arrow"}</span>
            </span>
          </button>
          <button
            aria-label="快进 10 秒"
            className="player-overlay-zone player-overlay-zone-right"
            onClick={() => seekBy(10)}
            type="button"
          >
            <span className="player-overlay-icon-shell">
              <span className="material-symbols-rounded player-overlay-icon">forward_10</span>
            </span>
          </button>
        </div>
      </div>
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
              <div className="artwork-controls-shell">
                <CropControls crop={posterCrop} onChange={setPosterCrop} title="调整横版 poster" />
              </div>
            </div>
            <div className="action-row">
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
