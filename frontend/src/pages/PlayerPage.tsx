import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchSimilarVideos, fetchVideo, flushVideoCache, flushVideoWatch, getStreamUrl, likeVideo, updateVideoArtwork } from "../api/client";
import { Surface } from "../components/Surface";
import { VideoGridCard } from "../components/VideoGridCard";
import { useRequireSession } from "../hooks/session";
import type { ApiError, SimilarVideosResult, Video, VideoRecommendationShelf } from "../types/api";
import { formatBytes, formatDuration } from "../utils/format";

const POSTER_TARGET = { width: 1280, height: 720 };
const DEFAULT_CROP = { zoom: 1, offsetX: 0, offsetY: 0 };

type CropConfig = typeof DEFAULT_CROP;
type LikeOverlay = { id: number; delta: 1 | -1 };
type PendingWatchState = {
  watchedSecondsDelta: number;
  positionSeconds: number;
  completed: boolean;
};

function ThumbUpIcon() {
  return (
    <svg aria-hidden="true" className="player-action-icon" viewBox="0 0 24 24">
      <path
        d="M9 10V21H5C3.9 21 3 20.1 3 19V12C3 10.9 3.9 10 5 10H9ZM11 10L14.4 3.2C14.7 2.5 15.5 2.1 16.2 2.4C16.9 2.7 17.3 3.5 17 4.2L15.2 10H19C20.1 10 21 10.9 21 12C21 12.2 21 12.4 20.9 12.6L18.3 19.6C18 20.4 17.2 21 16.3 21H11V10Z"
        fill="currentColor"
      />
    </svg>
  );
}

function ThumbDownIcon() {
  return (
    <svg aria-hidden="true" className="player-action-icon" viewBox="0 0 24 24">
      <path
        d="M15 14V3H19C20.1 3 21 3.9 21 5V12C21 13.1 20.1 14 19 14H15ZM13 14L9.6 20.8C9.3 21.5 8.5 21.9 7.8 21.6C7.1 21.3 6.7 20.5 7 19.8L8.8 14H5C3.9 14 3 13.1 3 12C3 11.8 3 11.6 3.1 11.4L5.7 4.4C6 3.6 6.8 3 7.7 3H13V14Z"
        fill="currentColor"
      />
    </svg>
  );
}

function FlameIcon() {
  return (
    <svg aria-hidden="true" className="player-action-icon" viewBox="0 0 24 24">
      <path
        d="M13.5 2C14.2 5.1 17.8 6.3 17.8 10.4C17.8 14.1 15.2 17 12 17C8.8 17 6.2 14.4 6.2 11.2C6.2 8.3 7.7 6.3 10.2 4.2C10.7 6.1 11.7 7 13 7.7C13.4 6.2 13.8 4.3 13.5 2ZM12 18.5C16 18.5 19.2 15.2 19.2 11.2C19.2 7.1 16.5 4.7 14.9 3.4L14.4 3L14 3.5C14 3.3 13.9 3.2 13.9 3L13.7 1.5L12.6 2.6C11.7 3.5 10.8 4.4 9.8 5.3C7.1 7.9 4.8 10.1 4.8 13.2C4.8 16.2 7.4 18.5 12 18.5Z"
        fill="currentColor"
      />
    </svg>
  );
}

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

function mergeCachedVideoState(previous: Video | undefined, next: Video): Video {
  if (!previous) {
    return next;
  }

  return {
    ...next,
    cached_size_bytes: next.cached_size_bytes > 0 ? next.cached_size_bytes : previous.cached_size_bytes,
    cached_segment_count: next.cached_segment_count > 0 ? next.cached_segment_count : previous.cached_segment_count,
    cached_byte_ranges: next.cached_byte_ranges.length > 0 ? next.cached_byte_ranges : previous.cached_byte_ranges,
  };
}

export function PlayerPage() {
  const { videoId: rawVideoId } = useParams();
  const videoId = Number(rawVideoId);
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const lastObservedAtRef = useRef<number | null>(null);
  const lastObservedPositionRef = useRef(0);
  const flushStartedRef = useRef(false);
  const pendingWatchRef = useRef<PendingWatchState>({
    watchedSecondsDelta: 0,
    positionSeconds: 0,
    completed: false,
  });
  const pendingCachedSegmentIndexesRef = useRef<Set<number>>(new Set());
  const [capturedDataUrl, setCapturedDataUrl] = useState<string | null>(null);
  const [posterPreviewDataUrl, setPosterPreviewDataUrl] = useState<string | null>(null);
  const [posterCrop, setPosterCrop] = useState<CropConfig>(DEFAULT_CROP);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watchSessionToken, setWatchSessionToken] = useState<string | null>(null);
  const [likeOverlays, setLikeOverlays] = useState<LikeOverlay[]>([]);

  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => fetchVideo(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });
  const similarVideosQuery = useQuery({
    queryKey: ["video", videoId, "similar"],
    queryFn: () => fetchSimilarVideos(videoId),
    enabled: session.data?.authenticated === true && Number.isFinite(videoId),
  });

  const refreshVideoCaches = (updatedVideo: Video) => {
    const previousVideo = queryClient.getQueryData<Video>(["video", videoId]);
    const mergedVideo = mergeCachedVideoState(previousVideo, updatedVideo);
    queryClient.setQueryData(["video", videoId], mergedVideo);
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
              items: page.items.map((item: Video) => (item.id === mergedVideo.id ? { ...item, ...mergedVideo } : item)),
            };
          }),
        };
      }
      return current.map((item) => (item.id === mergedVideo.id ? { ...item, ...mergedVideo } : item));
    });
    queryClient.setQueryData(["videos", "recommendations"], (current: VideoRecommendationShelf | undefined) => {
      if (!current) {
        return current;
      }
      const patch = (items: Video[]) => items.map((item) => (item.id === mergedVideo.id ? { ...item, ...mergedVideo } : item));
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

  const likeMutation = useMutation({
    mutationFn: ({ delta }: { delta: 1 | -1 }) => likeVideo(videoId, delta),
    onSuccess: async (updatedVideo, variables) => {
      refreshVideoCaches(updatedVideo);
      setLikeOverlays((current) => [...current, { id: Date.now() + current.length, delta: variables.delta }]);
      setFeedback(null);
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

  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement || !Number.isFinite(videoId)) {
      return;
    }

    const collectPlayback = (completed: boolean) => {
      const now = Date.now();
      const previousAt = lastObservedAtRef.current;
      const previousPosition = lastObservedPositionRef.current;
      const currentPosition = Math.max(videoElement.currentTime || 0, 0);
      lastObservedPositionRef.current = currentPosition;
      lastObservedAtRef.current = now;
      if (previousAt === null) {
        return;
      }
      const elapsedSeconds = Math.max((now - previousAt) / 1000, 0);
      const progressedSeconds = Math.max(currentPosition - previousPosition, 0);
      const watchedSecondsDelta = Math.min(elapsedSeconds, progressedSeconds > 0 ? progressedSeconds : elapsedSeconds);
      if (watchedSecondsDelta <= 0 && !completed) {
        return;
      }
      pendingWatchRef.current = {
        watchedSecondsDelta: pendingWatchRef.current.watchedSecondsDelta + watchedSecondsDelta,
        positionSeconds: currentPosition,
        completed: pendingWatchRef.current.completed || completed,
      };
    };

    const collectCachedSegments = () => {
      const ranges = videoRef.current?.buffered;
      const currentVideo = videoQuery.data;
      if (!ranges || !currentVideo || currentVideo.duration_seconds === null || currentVideo.duration_seconds <= 0) {
        return;
      }
      const duration = currentVideo.duration_seconds;
      for (let rangeIndex = 0; rangeIndex < ranges.length; rangeIndex += 1) {
        const startRatio = ranges.start(rangeIndex) / duration;
        const endRatio = ranges.end(rangeIndex) / duration;
        const startIndex = Math.max(Math.floor(startRatio * currentVideo.segment_count), 0);
        const endIndex = Math.min(Math.ceil(endRatio * currentVideo.segment_count), currentVideo.segment_count);
        for (let segmentIndex = startIndex; segmentIndex < endIndex; segmentIndex += 1) {
          pendingCachedSegmentIndexesRef.current.add(segmentIndex);
        }
      }
    };

    const flushPendingState = () => {
      if (flushStartedRef.current) {
        return;
      }
      flushStartedRef.current = true;
      collectPlayback(videoElement.ended);
      collectCachedSegments();
      const pendingWatch = pendingWatchRef.current;
      const cachedSegmentIndexes = [...pendingCachedSegmentIndexesRef.current].sort((left, right) => left - right);
      if (pendingWatch.watchedSecondsDelta > 0 || pendingWatch.completed) {
        void flushVideoWatch({
          videoId,
          sessionToken: watchSessionToken,
          positionSeconds: pendingWatch.positionSeconds,
          watchedSecondsDelta: pendingWatch.watchedSecondsDelta,
          completed: pendingWatch.completed,
        }).then((result) => {
          setWatchSessionToken(result.session_token);
          refreshVideoCaches(result.video);
        });
      }
      if (cachedSegmentIndexes.length > 0) {
        void flushVideoCache({ videoId, segmentIndexes: cachedSegmentIndexes }).then(async () => {
          await queryClient.invalidateQueries({ queryKey: ["video", videoId] });
          await queryClient.invalidateQueries({ queryKey: ["cache-summary"] });
          await queryClient.invalidateQueries({ queryKey: ["cached-videos"] });
        });
      }
    };

    const handlePlay = () => {
      lastObservedAtRef.current = Date.now();
      lastObservedPositionRef.current = Math.max(videoElement.currentTime || 0, 0);
    };
    const handlePause = () => {
      collectPlayback(false);
      collectCachedSegments();
    };
    const handleSeeked = () => {
      collectCachedSegments();
      lastObservedPositionRef.current = Math.max(videoElement.currentTime || 0, 0);
      lastObservedAtRef.current = Date.now();
    };
    const handleEnded = () => {
      collectPlayback(true);
      collectCachedSegments();
      flushPendingState();
    };
    const handleProgress = () => {
      collectCachedSegments();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        flushPendingState();
      }
    };

    videoElement.addEventListener("play", handlePlay);
    videoElement.addEventListener("pause", handlePause);
    videoElement.addEventListener("seeked", handleSeeked);
    videoElement.addEventListener("ended", handleEnded);
    videoElement.addEventListener("progress", handleProgress);
    window.addEventListener("pagehide", flushPendingState);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      flushPendingState();
      videoElement.removeEventListener("play", handlePlay);
      videoElement.removeEventListener("pause", handlePause);
      videoElement.removeEventListener("seeked", handleSeeked);
      videoElement.removeEventListener("ended", handleEnded);
      videoElement.removeEventListener("progress", handleProgress);
      window.removeEventListener("pagehide", flushPendingState);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [videoId, videoQuery.data, watchSessionToken, queryClient]);

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在准备播放...</p>;
  }

  if (!Number.isFinite(videoId)) {
    return <p className="state-text">无效的视频 ID。</p>;
  }

  const video = videoQuery.data;
  const similarVideos = similarVideosQuery.data?.items ?? [];
  const artworkVersionToken = Math.max(videoQuery.dataUpdatedAt, similarVideosQuery.dataUpdatedAt || 0);
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
    setFeedback(`高光 ${formatDuration(video.highlight_start_seconds)}`);
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
      </div>

      {video ? (
        <Surface>
          <div className="player-action-bar">
            <div className="player-like-stack">
              <button
                aria-label="点赞"
                className="secondary-button player-action-button"
                disabled={likeMutation.isPending || video.like_count >= 99}
                onClick={() => likeMutation.mutate({ delta: 1 })}
                type="button"
              >
                <ThumbUpIcon />
                <span>{video.like_count}</span>
              </button>
              {likeOverlays.map((overlay) => (
                <span
                  aria-hidden="true"
                  className={`player-like-float ${overlay.delta > 0 ? "is-positive" : "is-negative"}`}
                  key={overlay.id}
                  onAnimationEnd={() => {
                    setLikeOverlays((current) => current.filter((item) => item.id !== overlay.id));
                  }}
                >
                  {overlay.delta > 0 ? "+1" : "-1"}
                </span>
              ))}
            </div>
            <div className="player-action-cluster">
              <button
                aria-label="取消点赞"
                className="secondary-button player-action-button"
                disabled={likeMutation.isPending || video.like_count <= 0}
                onClick={() => likeMutation.mutate({ delta: -1 })}
                type="button"
              >
                <ThumbDownIcon />
              </button>
              {video.highlight_start_seconds !== null ? (
                <button className="primary-button player-action-button" onClick={jumpToHighlight} type="button">
                  <FlameIcon />
                  <span>{formatDuration(video.highlight_start_seconds)}</span>
                </button>
              ) : null}
            </div>
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

      {similarVideos.length > 0 ? (
        <Surface>
          <div className="section-head">
            <div>
              <h2>相似推荐</h2>
            </div>
          </div>
          <div className="player-recommendation-row top-gap">
            {similarVideos.slice(0, 4).map((item) => (
              <VideoGridCard key={`similar-${item.id}`} versionToken={artworkVersionToken} video={item} />
            ))}
          </div>
        </Surface>
      ) : null}
    </div>
  );
}
