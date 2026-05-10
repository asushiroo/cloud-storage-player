import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchVideo, getStreamUrl, updateVideoArtwork } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError } from "../types/api";
import { formatBytes, formatDuration } from "../utils/format";

const COVER_TARGET = { width: 540, height: 810 };
const POSTER_TARGET = { width: 1280, height: 720 };
const DEFAULT_CROP = { zoom: 1, offsetX: 0, offsetY: 0 };

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
  const [capturedDataUrl, setCapturedDataUrl] = useState<string | null>(null);
  const [coverPreviewDataUrl, setCoverPreviewDataUrl] = useState<string | null>(null);
  const [posterPreviewDataUrl, setPosterPreviewDataUrl] = useState<string | null>(null);
  const [coverCrop, setCoverCrop] = useState<CropConfig>(DEFAULT_CROP);
  const [posterCrop, setPosterCrop] = useState<CropConfig>(DEFAULT_CROP);
  const [replaceCover, setReplaceCover] = useState(true);
  const [replacePoster, setReplacePoster] = useState(true);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  useEffect(() => {
    if (!capturedDataUrl) {
      setCoverPreviewDataUrl(null);
      setPosterPreviewDataUrl(null);
      return;
    }
    let active = true;
    Promise.all([
      buildArtworkDataUrl(capturedDataUrl, COVER_TARGET, coverCrop),
      buildArtworkDataUrl(capturedDataUrl, POSTER_TARGET, posterCrop),
    ])
      .then(([cover, poster]) => {
        if (!active) {
          return;
        }
        setCoverPreviewDataUrl(cover);
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
  }, [capturedDataUrl, coverCrop, posterCrop]);

  const artworkMutation = useMutation({
    mutationFn: () =>
      updateVideoArtwork({
        videoId,
        coverDataUrl: replaceCover ? coverPreviewDataUrl ?? undefined : undefined,
        posterDataUrl: replacePoster ? posterPreviewDataUrl ?? undefined : undefined,
      }),
    onSuccess: async () => {
      setCapturedDataUrl(null);
      setFeedback("封面 / Poster 已更新。现在 cover 会固定输出竖版比例，poster 固定输出横版比例。");
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
    setCoverCrop(DEFAULT_CROP);
    setPosterCrop(DEFAULT_CROP);
    setCapturedDataUrl(canvas.toDataURL("image/jpeg", 0.92));
    setFeedback("已捕获当前帧。你现在可以分别调整竖版 cover 与横版 poster 的缩放和截取位置。");
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
            <p className="muted">捕获后会分别生成固定比例的竖版 cover 与横版 poster，你可以独立调整缩放和截取位置。</p>
          </div>
          <button className="primary-button" onClick={captureCurrentFrame} type="button">
            捕获当前帧
          </button>
        </div>
        {capturedDataUrl && coverPreviewDataUrl && posterPreviewDataUrl ? (
          <div className="artwork-editor">
            <div className="artwork-preview-grid">
              <div className="artwork-preview-card">
                <p className="small-text muted">Cover 预览（固定竖版）</p>
                <img alt="Cover preview" className="artwork-preview-image artwork-preview-cover" src={coverPreviewDataUrl} />
                <CropControls crop={coverCrop} onChange={setCoverCrop} title="调整竖版 cover" />
              </div>
              <div className="artwork-preview-card">
                <p className="small-text muted">Poster 预览（固定横版）</p>
                <img alt="Poster preview" className="artwork-preview-image artwork-preview-poster" src={posterPreviewDataUrl} />
                <CropControls crop={posterCrop} onChange={setPosterCrop} title="调整横版 poster" />
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
                onClick={() => artworkMutation.mutate()}
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
