import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { buildAssetUrl, fetchVideos } from "../api/client";
import { CoverCard } from "../components/CoverCard";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { Video } from "../types/api";
import { formatBytes, formatDuration } from "../utils/format";

const BANNER_SELECTION_SIZE = 5;
const BANNER_ROTATE_MS = 8_000;
const BANNER_REFRESH_MS = 10 * 60 * 1_000;

function pickBannerVideos(videoIdsSeed: number, videos: Video[]) {
  const withCover = videos.filter((video) => video.poster_path || video.cover_path);
  const source = withCover.length >= BANNER_SELECTION_SIZE ? withCover : videos;
  if (source.length <= BANNER_SELECTION_SIZE) {
    return source;
  }

  const decorated = source.map((video, index) => ({
    video,
    weight: Math.abs(Math.sin(videoIdsSeed * 997 + video.id * 131 + index * 17)),
  }));
  decorated.sort((left, right) => left.weight - right.weight);
  return decorated.slice(0, BANNER_SELECTION_SIZE).map((item) => item.video);
}

export function LibraryPage() {
  const session = useRequireSession();
  const [bannerSeed, setBannerSeed] = useState(() => Math.floor(Date.now() / BANNER_REFRESH_MS));
  const [bannerIndex, setBannerIndex] = useState(0);
  const videosQuery = useQuery({
    queryKey: ["videos", "library-home"],
    queryFn: () => fetchVideos(),
    enabled: session.data?.authenticated === true,
  });

  useEffect(() => {
    const refreshTimer = window.setInterval(() => {
      setBannerSeed(Math.floor(Date.now() / BANNER_REFRESH_MS));
    }, 30_000);
    return () => window.clearInterval(refreshTimer);
  }, []);

  const videos = videosQuery.data ?? [];
  const bannerVideos = useMemo(() => pickBannerVideos(bannerSeed, videos), [bannerSeed, videos]);
  const activeBannerVideo = bannerVideos[bannerIndex % Math.max(bannerVideos.length, 1)] ?? null;

  useEffect(() => {
    setBannerIndex(0);
  }, [bannerSeed, bannerVideos.length]);

  useEffect(() => {
    if (bannerVideos.length <= 1) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setBannerIndex((current) => (current + 1) % bannerVideos.length);
    }, BANNER_ROTATE_MS);
    return () => window.clearInterval(timer);
  }, [bannerVideos]);

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  return (
    <div className="page-stack">
      {activeBannerVideo ? (
        <Link className="banner-link" to={`/videos/${activeBannerVideo.id}`}>
          <section
            className="banner-surface"
            style={{ backgroundImage: `linear-gradient(120deg, rgba(12,16,32,0.92), rgba(12,16,32,0.35)), url(${buildAssetUrl(activeBannerVideo.poster_path ?? activeBannerVideo.cover_path) ?? ""})` }}
          >
            <div className="banner-content">
              <p className="eyebrow">每 10 分钟随机推荐 5 部</p>
              <h1>{activeBannerVideo.title}</h1>
              <p className="muted banner-copy">
                {formatDuration(activeBannerVideo.duration_seconds)} · {formatBytes(activeBannerVideo.size)} · {activeBannerVideo.segment_count} segments
              </p>
              <div className="chip-row compact">
                {activeBannerVideo.tags.slice(0, 4).map((tag) => (
                  <span className="mini-tag" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
              <span className="primary-button banner-button">进入视频页</span>
            </div>
            <div className="banner-dots">
              {bannerVideos.map((video, index) => (
                <button
                  aria-label={`切换到 ${video.title}`}
                  className={`banner-dot ${index === bannerIndex ? "banner-dot-active" : ""}`}
                  key={video.id}
                  onClick={(event) => {
                    event.preventDefault();
                    setBannerIndex(index);
                  }}
                  type="button"
                />
              ))}
            </div>
          </section>
        </Link>
      ) : (
        <Surface>
          <p className="eyebrow">Cloud Storage Player</p>
          <h1>局域网加密影库</h1>
          <p className="muted">当前还没有可用于推荐的视频封面，先去管理页导入视频吧。</p>
        </Surface>
      )}

      <Surface>
        <div className="section-head">
          <div>
            <p className="eyebrow">媒体库</p>
            <h2>全部视频</h2>
          </div>
          <Link className="secondary-button link-button" to="/manage">
            搜索 / 导入 / 任务管理
          </Link>
        </div>
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
          <p className="muted">当前媒体库为空。</p>
        </Surface>
      ) : null}
    </div>
  );
}
