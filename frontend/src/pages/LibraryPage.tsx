import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchFolders, fetchVideoPage } from "../api/client";
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
  const [selectedFolderId, setSelectedFolderId] = useState<number | undefined>();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const appliedSearch = searchParams.get("q")?.trim() ?? "";

  const foldersQuery = useQuery({
    queryKey: ["folders"],
    queryFn: fetchFolders,
    enabled: session.data?.authenticated === true,
  });
  const videosQuery = useInfiniteQuery({
    queryKey: ["videos", "library-page", selectedFolderId ?? "all", appliedSearch],
    queryFn: ({ pageParam }) =>
      fetchVideoPage({
        folderId: selectedFolderId,
        q: appliedSearch,
        offset: Number(pageParam),
        limit: LIBRARY_PAGE_SIZE,
      }),
    enabled: session.data?.authenticated === true,
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.offset + lastPage.items.length : undefined),
  });

  const folders = foldersQuery.data ?? [];
  const videos = videosQuery.data?.pages.flatMap((page) => page.items) ?? [];
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
  const { fetchNextPage, hasNextPage, isFetchingNextPage } = videosQuery;

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
    if (!sentinel || !hasNextPage || isFetchingNextPage) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          void fetchNextPage();
        }
      },
      { rootMargin: "240px 0px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  return (
    <div className="library-page">
      <div className="library-content-shell page-stack">
        <Surface>
          <div className="section-head">
            <div>
              <h1>媒体库</h1>
              <p className="muted">移除推荐 Banner 后，这里只保留筛选、搜索和分批滚动加载的库视图。</p>
            </div>
          </div>
          {folders.length > 0 ? (
            <div className="chip-row top-gap">
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

        {filteredVideos.length > 0 ? (
          <div className="video-grid">
            {filteredVideos.map((video) => (
              <VideoGridCard key={video.id} versionToken={artworkVersionToken} video={video} />
            ))}
          </div>
        ) : null}

        {filteredVideos.length === 0 && !videosQuery.isLoading ? (
          <Surface>
            <p className="muted">当前筛选条件下没有视频。</p>
          </Surface>
        ) : null}

        {hasNextPage ? (
          <div className="video-grid-footer">
            <div className="load-more-sentinel" ref={loadMoreRef} />
            <p className="muted small-text">{isFetchingNextPage ? "正在加载下一页..." : "继续向下滚动以加载更多 poster。"}</p>
          </div>
        ) : filteredVideos.length > 0 ? (
          <div className="video-grid-footer">
            <p className="muted small-text">媒体库已经全部加载完毕。</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
