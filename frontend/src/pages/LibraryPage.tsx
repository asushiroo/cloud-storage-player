import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchVideos } from "../api/client";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
import { VideoGridCard } from "../components/VideoGridCard";
import { useRequireSession } from "../hooks/session";
import { expandTagValue } from "../utils/tagHierarchy";

const LIBRARY_PAGE_SIZE = 12;

export function LibraryPage() {
  const session = useRequireSession();
  const [searchParams] = useSearchParams();
  const [activePrimaryTag, setActivePrimaryTag] = useState<string | undefined>();
  const [activeSecondaryTag, setActiveSecondaryTag] = useState<string | undefined>();
  const [visibleCount, setVisibleCount] = useState(LIBRARY_PAGE_SIZE);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const appliedSearch = searchParams.get("q")?.trim() ?? "";

  const videosQuery = useQuery({
    queryKey: ["videos", "library", appliedSearch],
    queryFn: () =>
      fetchVideos({
        q: appliedSearch,
      }),
    enabled: session.data?.authenticated === true,
    refetchOnMount: "always",
  });

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
  const visibleVideos = filteredVideos.slice(0, visibleCount);
  const hasMoreVisibleVideos = visibleVideos.length < filteredVideos.length;

  useEffect(() => {
    setVisibleCount(LIBRARY_PAGE_SIZE);
  }, [activePrimaryTag, activeSecondaryTag, appliedSearch]);

  useEffect(() => {
    if (!activePrimaryTag) {
      return;
    }
    if (!primaryTagGroups.some((primary) => primary.label === activePrimaryTag)) {
      setActivePrimaryTag(undefined);
      setActiveSecondaryTag(undefined);
    }
  }, [activePrimaryTag, primaryTagGroups]);

  useEffect(() => {
    if (!activeSecondaryTag) {
      return;
    }
    if (!secondaryTagGroups.some((secondary) => secondary.label === activeSecondaryTag)) {
      setActiveSecondaryTag(undefined);
    }
  }, [activeSecondaryTag, secondaryTagGroups]);

  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (!sentinel || !hasMoreVisibleVideos) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisibleCount((current) => Math.min(current + LIBRARY_PAGE_SIZE, filteredVideos.length));
        }
      },
      { rootMargin: "240px 0px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [filteredVideos.length, hasMoreVisibleVideos]);

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  return (
    <div className="library-page">
      <div className="library-content-shell page-stack">
        <Surface>
          <div className="top-gap">
            <p className="muted small-text">一级标签</p>
            <div className="chip-row top-gap">
              <TagChip
                active={activePrimaryTag === undefined}
                label={`全部视频 (${videos.length})`}
                onClick={() => {
                  setActivePrimaryTag(undefined);
                  setActiveSecondaryTag(undefined);
                }}
              />
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
          </div>

          {activePrimaryTag && secondaryTagGroups.length > 0 ? (
            <div className="top-gap">
              <p className="muted small-text">二级标签</p>
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
            </div>
          ) : null}
        </Surface>

        <div className="section-divider" />

        {videosQuery.isLoading ? (
          <Surface>
            <p className="muted">正在加载视频ლ(´ڡ`ლ)...</p>
          </Surface>
        ) : null}

        {visibleVideos.length > 0 ? (
          <div className="video-grid">
            {visibleVideos.map((video) => (
              <VideoGridCard key={video.id} versionToken={artworkVersionToken} video={video} />
            ))}
          </div>
        ) : null}

        {filteredVideos.length === 0 && !videosQuery.isLoading ? (
          <Surface>
            <p className="muted">没找到呀(｡•́‿•̀｡)</p>
          </Surface>
        ) : null}

        {hasMoreVisibleVideos ? (
          <div className="video-grid-footer">
            <div className="load-more-sentinel" ref={loadMoreRef} />
            <p className="muted small-text">摩多摩多(✪ω✪)</p>
          </div>
        ) : filteredVideos.length > 0 && !videosQuery.isLoading ? (
          <div className="video-grid-footer">
            <p className="muted small-text">已经到底了!!!∑(ﾟДﾟノ)ノ</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
