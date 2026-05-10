import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { buildAssetUrl, fetchFolders, fetchVideos } from "../api/client";
import { CoverCard } from "../components/CoverCard";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
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
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [activeTag, setActiveTag] = useState<string | undefined>();
  const [selectedFolderId, setSelectedFolderId] = useState<number | undefined>();

  const foldersQuery = useQuery({
    queryKey: ["folders"],
    queryFn: fetchFolders,
    enabled: session.data?.authenticated === true,
  });
  const videosQuery = useQuery({
    queryKey: ["videos", "library-wall", selectedFolderId ?? "all", appliedSearch, activeTag ?? ""],
    queryFn: () => fetchVideos({ folderId: selectedFolderId, q: appliedSearch, tag: activeTag }),
    enabled: session.data?.authenticated === true,
  });

  useEffect(() => {
    const refreshTimer = window.setInterval(() => {
      setBannerSeed(Math.floor(Date.now() / BANNER_REFRESH_MS));
    }, 30_000);
    return () => window.clearInterval(refreshTimer);
  }, []);

  const folders = foldersQuery.data ?? [];
  const videos = videosQuery.data ?? [];
  const artworkVersionToken = videosQuery.dataUpdatedAt;
  const tagCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const video of videos) {
      for (const tag of video.tags) {
        counts.set(tag, (counts.get(tag) ?? 0) + 1);
      }
    }
    return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
  }, [videos]);
  const bannerVideos = useMemo(() => pickBannerVideos(bannerSeed, videos), [bannerSeed, videos]);
  const activeBannerVideo = bannerVideos[bannerIndex % Math.max(bannerVideos.length, 1)] ?? null;

  useEffect(() => {
    setBannerIndex(0);
  }, [bannerSeed, bannerVideos.length, appliedSearch, activeTag, selectedFolderId]);

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
            style={{
              backgroundImage: `linear-gradient(120deg, rgba(12,16,32,0.45), rgba(12,16,32,0.05)), url(${buildAssetUrl(
                activeBannerVideo.poster_path ?? activeBannerVideo.cover_path,
                artworkVersionToken,
              ) ?? ""})`,
            }}
          >
            <div className="banner-title-corner">
              <h1 className="banner-title-simple">{activeBannerVideo.title}</h1>
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
          <h1>局域网加密影库</h1>
          <p className="muted">当前还没有可展示的视频，先去管理页导入吧。</p>
        </Surface>
      )}

      <Surface>
        <div className="section-head">
          <div>
            <h2>媒体库</h2>
            <p className="muted">搜索结果会直接显示在下面的海报墙里。</p>
          </div>
          <Link className="secondary-button link-button" to="/manage">
            导入 / 任务管理
          </Link>
        </div>
        <div className="toolbar-row top-gap">
          <input
            className="text-input grow"
            onChange={(event) => setSearchInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                setAppliedSearch(searchInput.trim());
              }
            }}
            placeholder="按标题、源路径、标签搜索"
            value={searchInput}
          />
          <button className="secondary-button" onClick={() => setAppliedSearch(searchInput.trim())} type="button">
            搜索
          </button>
          <button
            className="secondary-button"
            onClick={() => {
              setSearchInput("");
              setAppliedSearch("");
              setActiveTag(undefined);
              setSelectedFolderId(undefined);
            }}
            type="button"
          >
            清空
          </button>
        </div>
        <div className="chip-row top-gap">
          <TagChip active={selectedFolderId === undefined} label="全部目录" onClick={() => setSelectedFolderId(undefined)} />
          {folders.map((folder) => (
            <TagChip key={folder.id} active={selectedFolderId === folder.id} label={folder.name} onClick={() => setSelectedFolderId(folder.id)} />
          ))}
        </div>
        {tagCounts.length > 0 ? (
          <div className="chip-row top-gap">
            {tagCounts.map(([tag, count]) => (
              <TagChip key={tag} active={activeTag === tag} label={`${tag} (${count})`} onClick={() => setActiveTag(activeTag === tag ? undefined : tag)} />
            ))}
          </div>
        ) : null}
      </Surface>

      <div className="video-grid">
        {videos.map((video) => (
          <Link className="video-card" key={video.id} to={`/videos/${video.id}`}>
            <CoverCard coverPath={video.cover_path} title={video.title} versionToken={artworkVersionToken} />
            <div className="video-meta">
              <h2>{video.title}</h2>
              <p className="muted">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.segment_count} segments</p>
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
          <p className="muted">当前筛选条件下没有视频。</p>
        </Surface>
      ) : null}
    </div>
  );
}
