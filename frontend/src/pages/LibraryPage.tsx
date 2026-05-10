import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { buildAssetUrl, fetchFolders, fetchVideos } from "../api/client";
import { CoverCard } from "../components/CoverCard";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
import { useRequireSession } from "../hooks/session";
import type { Video } from "../types/api";
import { expandTagValue } from "../utils/tagHierarchy";
import { formatBytes, formatDuration } from "../utils/format";

const BANNER_SELECTION_SIZE = 5;
const BANNER_ROTATE_MS = 8_000;
const BANNER_REFRESH_MS = 10 * 60 * 1_000;
const BANNER_VISIBLE_SLOTS = ["left", "center", "right"] as const;

type BannerSlot = (typeof BANNER_VISIBLE_SLOTS)[number];

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
    const groups = new Map<string, number>();
    for (const video of videos) {
      for (const tag of video.tags) {
        for (const parsed of expandTagValue(tag)) {
          if (parsed.level !== "primary" || !parsed.label) {
            continue;
          }
          groups.set(parsed.label, (groups.get(parsed.label) ?? 0) + 1);
        }
      }
    }
    return [...groups.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
  }, [videos]);
  const secondaryTagGroups = useMemo(() => {
    if (!activePrimaryTag) {
      return [];
    }
    const groups = new Map<string, number>();
    for (const video of videos) {
      const parsedTags = video.tags.flatMap(expandTagValue);
      if (!parsedTags.some((tag) => tag.level === "primary" && tag.label === activePrimaryTag)) {
        continue;
      }
      for (const tag of parsedTags) {
        if (tag.level !== "secondary" || !tag.label) {
          continue;
        }
        groups.set(tag.label, (groups.get(tag.label) ?? 0) + 1);
      }
    }
    return [...groups.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
  }, [activePrimaryTag, videos]);
  const filteredVideos = useMemo(
    () =>
      videos.filter((video) => {
        if (!activePrimaryTag) {
          return true;
        }
        const parsedTags = video.tags.flatMap(expandTagValue);
        const matchesPrimary = parsedTags.some((tag) => tag.level === "primary" && tag.label === activePrimaryTag);
        if (!matchesPrimary) {
          return false;
        }
        if (!activeSecondaryTag) {
          return true;
        }
        return parsedTags.some((tag) => tag.level === "secondary" && tag.label === activeSecondaryTag);
      }),
    [activePrimaryTag, activeSecondaryTag, videos],
  );
  const groupedVideoTags = useMemo(
    () =>
      new Map(
        filteredVideos.map((video) => {
          const primaryTags = video.tags
            .flatMap(expandTagValue)
            .filter((tag) => tag.level === "primary" && tag.label)
            .map((tag) => tag.label);
          const secondaryTags = video.tags
            .flatMap(expandTagValue)
            .filter((tag) => tag.level === "secondary" && tag.label)
            .map((tag) => tag.label);
          return [video.id, { primaryTags, secondaryTags }] as const;
        }),
      ),
    [filteredVideos],
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
    if (!activeSecondaryTag) {
      return;
    }
    if (!secondaryTagGroups.some((secondary) => secondary.label === activeSecondaryTag)) {
      setActiveSecondaryTag(undefined);
    }
  }, [activeSecondaryTag, secondaryTagGroups]);

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

      <div className="section-divider" />

      <Surface>
        {folders.length > 0 ? (
          <div className="chip-row">
            {folders.map((folder) => (
              <TagChip
                key={folder.id}
                active={selectedFolderId === folder.id}
                label={folder.name}
                onClick={() => setSelectedFolderId(selectedFolderId === folder.id ? undefined : folder.id)}
              />
            ))}
          </div>
        ) : null}
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
        {activePrimaryTag && secondaryTagGroups.length > 0 ? (
          <div className="chip-row top-gap">
            <TagChip active={activeSecondaryTag === undefined} label="全部子分类" onClick={() => setActiveSecondaryTag(undefined)} />
            {secondaryTagGroups.map((secondary) => (
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

      <div className="section-divider" />

      <div className="video-grid">
        {filteredVideos.map((video) => (
          <Link className="video-card" key={video.id} to={`/videos/${video.id}`}>
            <CoverCard artworkPath={video.poster_path ?? video.cover_path} title={video.title} versionToken={artworkVersionToken} />
            <div className="video-meta">
              <h2>{video.title}</h2>
              <p className="muted">{formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.segment_count} segments</p>
              {groupedVideoTags.get(video.id)?.primaryTags.length || groupedVideoTags.get(video.id)?.secondaryTags.length ? (
                <div className="video-tag-lines">
                  <div className="video-tag-line">
                    {(groupedVideoTags.get(video.id)?.primaryTags ?? []).map((tag, index) => (
                      <span className="mini-tag" key={`${video.id}-primary-${tag}-${index}`}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className="video-tag-line">
                    {(groupedVideoTags.get(video.id)?.secondaryTags ?? []).map((tag, index) => (
                      <span className="mini-tag" key={`${video.id}-secondary-${tag}-${index}`}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="chip-row compact">
                  <span className="muted small-text">暂无标签</span>
                </div>
              )}
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
