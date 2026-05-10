import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
const BANNER_VISIBLE_SLOTS = ["left", "center", "right"] as const;

type BannerSlot = (typeof BANNER_VISIBLE_SLOTS)[number];

function splitTagLabel(tag: string) {
  const [primary, ...secondaryParts] = tag
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);
  return {
    primary: primary ?? "",
    secondary: secondaryParts.length > 0 ? secondaryParts.join("/") : null,
  };
}

function pickBannerVideos(videoIdsSeed: number, videos: Video[]) {
  const withPoster = videos.filter((video) => video.poster_path || video.cover_path);
  if (withPoster.length <= BANNER_SELECTION_SIZE) {
    return withPoster;
  }

  const decorated = withPoster.map((video, index) => ({
    video,
    weight: Math.abs(Math.sin(videoIdsSeed * 997 + video.id * 131 + index * 17)),
  }));
  decorated.sort((left, right) => left.weight - right.weight);
  return decorated.slice(0, BANNER_SELECTION_SIZE).map((item) => item.video);
}

function getBannerVideoAt(videos: Video[], index: number): Video | null {
  if (videos.length === 0) {
    return null;
  }
  return videos[((index % videos.length) + videos.length) % videos.length] ?? null;
}

export function LibraryPage() {
  const session = useRequireSession();
  const [searchParams] = useSearchParams();
  const [bannerSeed, setBannerSeed] = useState(() => Math.floor(Date.now() / BANNER_REFRESH_MS));
  const [bannerIndex, setBannerIndex] = useState(0);
  const [activePrimaryTag, setActivePrimaryTag] = useState<string | undefined>();
  const [activeSecondaryTag, setActiveSecondaryTag] = useState<string | undefined>();
  const [selectedFolderId, setSelectedFolderId] = useState<number | undefined>();
  const appliedSearch = searchParams.get("q")?.trim() ?? "";

  const foldersQuery = useQuery({
    queryKey: ["folders"],
    queryFn: fetchFolders,
    enabled: session.data?.authenticated === true,
  });
  const videosQuery = useQuery({
    queryKey: ["videos", "library-wall", selectedFolderId ?? "all", appliedSearch],
    queryFn: () => fetchVideos({ folderId: selectedFolderId, q: appliedSearch }),
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
  const primaryTagGroups = useMemo(() => {
    const groups = new Map<
      string,
      {
        count: number;
        secondaries: Map<string, number>;
      }
    >();
    for (const video of videos) {
      for (const tag of video.tags) {
        const parsed = splitTagLabel(tag);
        if (!parsed.primary) {
          continue;
        }
        const group = groups.get(parsed.primary) ?? { count: 0, secondaries: new Map<string, number>() };
        group.count += 1;
        if (parsed.secondary) {
          group.secondaries.set(parsed.secondary, (group.secondaries.get(parsed.secondary) ?? 0) + 1);
        }
        groups.set(parsed.primary, group);
      }
    }
    return [...groups.entries()]
      .map(([label, value]) => ({
        label,
        count: value.count,
        secondaries: [...value.secondaries.entries()]
          .map(([secondary, count]) => ({ label: secondary, count }))
          .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label)),
      }))
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
  }, [videos]);
  const activePrimaryGroup = primaryTagGroups.find((group) => group.label === activePrimaryTag);
  const filteredVideos = useMemo(
    () =>
      videos.filter((video) => {
        if (!activePrimaryTag) {
          return true;
        }
        const parsedTags = video.tags.map(splitTagLabel);
        const matchesPrimary = parsedTags.some((tag) => tag.primary === activePrimaryTag);
        if (!matchesPrimary) {
          return false;
        }
        if (!activeSecondaryTag) {
          return true;
        }
        return parsedTags.some((tag) => tag.primary === activePrimaryTag && tag.secondary === activeSecondaryTag);
      }),
    [activePrimaryTag, activeSecondaryTag, videos],
  );
  const bannerVideos = useMemo(() => pickBannerVideos(bannerSeed, filteredVideos), [bannerSeed, filteredVideos]);
  const activeBannerVideo = getBannerVideoAt(bannerVideos, bannerIndex);
  const bannerSlots = useMemo(
    () =>
      BANNER_VISIBLE_SLOTS.map((slot, slotIndex) => ({
        slot,
        video: getBannerVideoAt(bannerVideos, bannerIndex + slotIndex - 1),
      })).filter((entry): entry is { slot: BannerSlot; video: Video } => entry.video !== null),
    [bannerIndex, bannerVideos],
  );

  useEffect(() => {
    setBannerIndex(0);
  }, [bannerSeed, bannerVideos.length, appliedSearch, activePrimaryTag, activeSecondaryTag, selectedFolderId]);

  useEffect(() => {
    if (!activePrimaryGroup || activeSecondaryTag === undefined) {
      return;
    }
    if (!activePrimaryGroup.secondaries.some((secondary) => secondary.label === activeSecondaryTag)) {
      setActiveSecondaryTag(undefined);
    }
  }, [activePrimaryGroup, activeSecondaryTag]);

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
        <section className="banner-surface">
          <div className="banner-stage-shell">
            <div className="banner-stage">
              {bannerSlots.map(({ slot, video }) => (
                <Link
                  aria-label={`打开 ${video.title}`}
                  className={`banner-poster-card banner-poster-card-${slot}`}
                  key={`${slot}-${video.id}`}
                  to={`/videos/${video.id}`}
                >
                  <img
                    alt={video.title}
                    className="banner-poster-image"
                    src={buildAssetUrl(video.poster_path ?? video.cover_path, artworkVersionToken) ?? ""}
                  />
                  <span className="banner-poster-title">{video.title}</span>
                </Link>
              ))}
            </div>
          </div>
        </section>
      ) : (
        <Surface>
          <h1>局域网加密影库</h1>
          <p className="muted">当前还没有可展示的视频，先去管理页导入吧。</p>
        </Surface>
      )}

      <Surface>
        <div className="library-toolbar-row">
          <div className="chip-row">
            <TagChip active={selectedFolderId === undefined} label="全部目录" onClick={() => setSelectedFolderId(undefined)} />
            {folders.map((folder) => (
              <TagChip key={folder.id} active={selectedFolderId === folder.id} label={folder.name} onClick={() => setSelectedFolderId(folder.id)} />
            ))}
          </div>
          <Link className="secondary-button link-button" to="/manage">
            导入 / 任务管理
          </Link>
        </div>
        {primaryTagGroups.length > 0 ? (
          <div className="chip-row top-gap">
            {primaryTagGroups.map((group) => (
              <TagChip
                key={group.label}
                active={activePrimaryTag === group.label}
                label={`${group.label} (${group.count})`}
                onClick={() => {
                  const nextPrimary = activePrimaryTag === group.label ? undefined : group.label;
                  setActivePrimaryTag(nextPrimary);
                  setActiveSecondaryTag(undefined);
                }}
              />
            ))}
          </div>
        ) : null}
        {activePrimaryGroup && activePrimaryGroup.secondaries.length > 0 ? (
          <div className="chip-row top-gap">
            <TagChip active={activeSecondaryTag === undefined} label="全部子分类" onClick={() => setActiveSecondaryTag(undefined)} />
            {activePrimaryGroup.secondaries.map((secondary) => (
              <TagChip
                key={secondary.label}
                active={activeSecondaryTag === secondary.label}
                label={`${secondary.label} (${secondary.count})`}
                onClick={() => setActiveSecondaryTag(activeSecondaryTag === secondary.label ? undefined : secondary.label)}
              />
            ))}
          </div>
        ) : null}
      </Surface>

      <div className="video-grid">
        {filteredVideos.map((video) => (
          <Link className="video-card" key={video.id} to={`/videos/${video.id}`}>
            <CoverCard artworkPath={video.poster_path ?? video.cover_path} title={video.title} versionToken={artworkVersionToken} />
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

      {filteredVideos.length === 0 && !videosQuery.isLoading ? (
        <Surface>
          <p className="muted">当前筛选条件下没有视频。</p>
        </Surface>
      ) : null}
    </div>
  );
}
