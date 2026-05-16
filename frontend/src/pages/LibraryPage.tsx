import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchVideos } from "../api/client";
import { Surface } from "../components/Surface";
import { TagChip } from "../components/TagChip";
import { VideoGridCard } from "../components/VideoGridCard";
import { useRequireSession } from "../hooks/session";
import { loadLibraryPageMemory, saveLibraryPageMemory } from "../utils/libraryMemory";
import { expandTagValue } from "../utils/tagHierarchy";

const LIBRARY_PAGE_SIZE = 6;

export function LibraryPage() {
  const session = useRequireSession();
  const [searchParams] = useSearchParams();
  const appliedSearch = searchParams.get("q")?.trim() ?? "";

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  return <LibraryPageContent appliedSearch={appliedSearch} key={appliedSearch} />;
}

interface LibraryPageContentProps {
  appliedSearch: string;
}

function LibraryPageContent({ appliedSearch }: LibraryPageContentProps) {
  const initialMemoryRef = useRef(loadLibraryPageMemory(appliedSearch));
  const lastKnownScrollYRef = useRef(initialMemoryRef.current?.scrollY ?? 0);
  const [activePrimaryTag, setActivePrimaryTag] = useState<string | undefined>(() => initialMemoryRef.current?.activePrimaryTag);
  const [activeSecondaryTag, setActiveSecondaryTag] = useState<string | undefined>(() => initialMemoryRef.current?.activeSecondaryTag);
  const [visibleCount, setVisibleCount] = useState(() =>
    Math.max(initialMemoryRef.current?.visibleCount ?? LIBRARY_PAGE_SIZE, LIBRARY_PAGE_SIZE),
  );
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const pendingScrollRestoreRef = useRef(initialMemoryRef.current);
  const restoreFrameRef = useRef<number | null>(null);
  const restoreAttemptsRef = useRef(0);
  const lastFilterKeyRef = useRef<string | null>(null);

  const videosQuery = useQuery({
    queryKey: ["videos", "library", appliedSearch],
    queryFn: () =>
      fetchVideos({
        q: appliedSearch,
      }),
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

  const saveMemorySnapshot = useCallback((captureCurrentScroll = true) => {
    if (captureCurrentScroll) {
      lastKnownScrollYRef.current = window.scrollY;
    }
    saveLibraryPageMemory({
      search: appliedSearch,
      activePrimaryTag,
      activeSecondaryTag,
      visibleCount,
      scrollY: lastKnownScrollYRef.current,
    });
  }, [activePrimaryTag, activeSecondaryTag, appliedSearch, visibleCount]);

  useEffect(() => {
    const memory = pendingScrollRestoreRef.current;
    if (!memory || videosQuery.isLoading) {
      return;
    }

    const restoreScroll = () => {
      const maxScrollY = Math.max(document.documentElement.scrollHeight - window.innerHeight, 0);
      const targetScrollY = Math.min(memory.scrollY, maxScrollY);
      const needsMoreHeight = maxScrollY < memory.scrollY;
      if (needsMoreHeight && visibleCount < filteredVideos.length) {
        if (visibleCount < filteredVideos.length) {
          setVisibleCount((current) => Math.min(current + LIBRARY_PAGE_SIZE, filteredVideos.length));
        }
        restoreFrameRef.current = window.requestAnimationFrame(restoreScroll);
        return;
      }
      window.scrollTo({ top: targetScrollY, behavior: "auto" });
      if (needsMoreHeight && restoreAttemptsRef.current < 24) {
        restoreAttemptsRef.current += 1;
        restoreFrameRef.current = window.requestAnimationFrame(restoreScroll);
        return;
      }
      pendingScrollRestoreRef.current = null;
      restoreAttemptsRef.current = 0;
      restoreFrameRef.current = null;
    };

    restoreAttemptsRef.current = 0;
    restoreFrameRef.current = window.requestAnimationFrame(restoreScroll);
    return () => {
      if (restoreFrameRef.current !== null) {
        window.cancelAnimationFrame(restoreFrameRef.current);
        restoreFrameRef.current = null;
      }
      restoreAttemptsRef.current = 0;
    };
  }, [filteredVideos.length, visibleCount, visibleVideos.length, videosQuery.isLoading]);

  useEffect(() => {
    const filterKey = JSON.stringify([activePrimaryTag ?? null, activeSecondaryTag ?? null]);
    if (lastFilterKeyRef.current === null) {
      lastFilterKeyRef.current = filterKey;
      return;
    }
    if (lastFilterKeyRef.current === filterKey) {
      return;
    }
    lastFilterKeyRef.current = filterKey;
    if (pendingScrollRestoreRef.current) {
      return;
    }
    setVisibleCount(LIBRARY_PAGE_SIZE);
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [activePrimaryTag, activeSecondaryTag]);

  useEffect(() => {
    if (pendingScrollRestoreRef.current) {
      return;
    }
    saveMemorySnapshot(true);
  }, [activePrimaryTag, activeSecondaryTag, appliedSearch, saveMemorySnapshot, visibleCount]);

  useEffect(() => {
    const handlePageHide = () => {
      saveMemorySnapshot(true);
    };
    const handleBeforeUnload = () => {
      saveMemorySnapshot(true);
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        saveMemorySnapshot(true);
      }
    };
    const trackScroll = () => {
      lastKnownScrollYRef.current = window.scrollY;
    };

    trackScroll();
    window.addEventListener("scroll", trackScroll, { passive: true });
    window.addEventListener("pagehide", handlePageHide);
    window.addEventListener("beforeunload", handleBeforeUnload);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (restoreFrameRef.current !== null) {
        window.cancelAnimationFrame(restoreFrameRef.current);
      }
      saveMemorySnapshot(false);
      window.removeEventListener("scroll", trackScroll);
      window.removeEventListener("pagehide", handlePageHide);
      window.removeEventListener("beforeunload", handleBeforeUnload);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [saveMemorySnapshot]);

  useEffect(() => {
    if (videosQuery.isLoading) {
      return;
    }
    if (!activePrimaryTag) {
      return;
    }
    if (!primaryTagGroups.some((primary) => primary.label === activePrimaryTag)) {
      setActivePrimaryTag(undefined);
      setActiveSecondaryTag(undefined);
    }
  }, [activePrimaryTag, primaryTagGroups, videosQuery.isLoading]);

  useEffect(() => {
    if (videosQuery.isLoading) {
      return;
    }
    if (!activeSecondaryTag) {
      return;
    }
    if (!secondaryTagGroups.some((secondary) => secondary.label === activeSecondaryTag)) {
      setActiveSecondaryTag(undefined);
    }
  }, [activeSecondaryTag, secondaryTagGroups, videosQuery.isLoading]);

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
              <VideoGridCard key={video.id} onNavigate={saveMemorySnapshot} versionToken={artworkVersionToken} video={video} />
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
