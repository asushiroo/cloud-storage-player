import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { buildAssetUrl } from "../api/client";
import type { Video } from "../types/api";

interface BannerCarouselProps {
  videos: Video[];
  versionToken?: number;
}

const AUTO_ROTATE_INTERVAL_MS = 10_000;

function getWrappedIndex(index: number, length: number): number {
  return ((index % length) + length) % length;
}

export function BannerCarousel({ videos, versionToken }: BannerCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [transitionDirection, setTransitionDirection] = useState<1 | -1 | 0>(0);

  const visibleVideos = useMemo(() => {
    if (videos.length === 0) {
      return [];
    }
    const duplicateCounts = new Map<number, number>();
    const createEntry = (slot: "left" | "center" | "right" | "incoming-left" | "incoming-right", offset: number) => {
      const wrappedIndex = getWrappedIndex(activeIndex + offset, videos.length);
      const duplicateCount = (duplicateCounts.get(wrappedIndex) ?? 0) + 1;
      duplicateCounts.set(wrappedIndex, duplicateCount);
      return {
        slot,
        video: videos[wrappedIndex],
        renderKey: duplicateCount === 1 ? `video-${wrappedIndex}` : `video-${wrappedIndex}-dup-${duplicateCount}`,
      };
    };
    return [
      createEntry("left", -1),
      createEntry("center", 0),
      createEntry("right", 1),
      createEntry("incoming-left", -2),
      createEntry("incoming-right", 2),
    ];
  }, [activeIndex, videos]);

  const activeVideo = videos.length > 0 ? videos[getWrappedIndex(activeIndex, videos.length)] : null;

  useEffect(() => {
    if (videos.length <= 1 || transitionDirection !== 0) {
      return;
    }
    const timer = window.setTimeout(() => {
      setTransitionDirection(1);
    }, AUTO_ROTATE_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [activeIndex, transitionDirection, videos.length]);

  const rotate = (direction: 1 | -1) => {
    if (videos.length <= 1 || transitionDirection !== 0) {
      return;
    }
    setTransitionDirection(direction);
  };

  const handleAnimationEnd = (event: React.AnimationEvent<HTMLDivElement>) => {
    if (transitionDirection === 0) {
      return;
    }
    const expectedAnimation = transitionDirection === 1 ? "banner-slide-right-to-center" : "banner-slide-left-to-center";
    if (event.animationName !== expectedAnimation) {
      return;
    }
    setActiveIndex((current) => getWrappedIndex(current + transitionDirection, videos.length));
    setTransitionDirection(0);
  };

  if (videos.length === 0) {
    return null;
  }

  return (
    <section className="banner-carousel">
      <div className="banner-carousel-shell">
        <button
          aria-label="Previous banner"
          className="banner-carousel-arrow banner-carousel-arrow-left"
          disabled={transitionDirection !== 0}
          onClick={() => rotate(-1)}
          type="button"
        >
          &#10094;
        </button>
        <div
          className={`banner-carousel-stage ${
            transitionDirection === 1
              ? "banner-carousel-stage-next"
              : transitionDirection === -1
                ? "banner-carousel-stage-prev"
                : ""
          }`}
          onAnimationEnd={handleAnimationEnd}
        >
          {activeVideo ? (
            <div className="banner-carousel-title-shell" aria-hidden="true">
              <span className="banner-carousel-title">{activeVideo.title}</span>
            </div>
          ) : null}
          {visibleVideos.map(({ slot, video, renderKey }) => (
            slot === "center" ? (
              <Link
                aria-label={`Open ${video.title}`}
                className={`banner-carousel-card banner-carousel-card-${slot}`}
                key={renderKey}
                to={`/videos/${video.id}`}
              >
                <img
                  alt={video.title}
                  className="banner-carousel-image"
                  draggable={false}
                  src={buildAssetUrl(video.poster_path ?? video.cover_path, versionToken) ?? ""}
                />
              </Link>
            ) : slot === "left" || slot === "right" ? (
              <button
                aria-label={`${slot === "left" ? "Show previous banner" : "Show next banner"}: ${video.title}`}
                className={`banner-carousel-card banner-carousel-card-${slot} banner-carousel-card-button`}
                disabled={transitionDirection !== 0 || videos.length <= 1}
                key={renderKey}
                onClick={() => rotate(slot === "left" ? -1 : 1)}
                type="button"
              >
                <img
                  alt={video.title}
                  className="banner-carousel-image"
                  draggable={false}
                  src={buildAssetUrl(video.poster_path ?? video.cover_path, versionToken) ?? ""}
                />
              </button>
            ) : (
              <div
                aria-hidden="true"
                className={`banner-carousel-card banner-carousel-card-${slot}`}
                key={renderKey}
              >
                <img
                  alt=""
                  className="banner-carousel-image"
                  draggable={false}
                  src={buildAssetUrl(video.poster_path ?? video.cover_path, versionToken) ?? ""}
                />
              </div>
            )
          ))}
        </div>
        <button
          aria-label="Next banner"
          className="banner-carousel-arrow banner-carousel-arrow-right"
          disabled={transitionDirection !== 0}
          onClick={() => rotate(1)}
          type="button"
        >
          &#10095;
        </button>
      </div>
    </section>
  );
}
