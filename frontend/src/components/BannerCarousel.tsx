import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { buildAssetUrl } from "../api/client";
import type { Video } from "../types/api";

const DRAG_TRIGGER_PX = 32;

interface BannerCarouselProps {
  videos: Video[];
  versionToken?: number;
}

function getWrappedIndex(index: number, length: number): number {
  return ((index % length) + length) % length;
}

export function BannerCarousel({ videos, versionToken }: BannerCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [transitionDirection, setTransitionDirection] = useState<1 | -1 | 0>(0);
  const dragRef = useRef<{ pointerId: number | null; startX: number }>({
    pointerId: null,
    startX: 0,
  });

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

  const rotate = (direction: 1 | -1) => {
    if (videos.length <= 1 || transitionDirection !== 0) {
      return;
    }
    setTransitionDirection(direction);
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (transitionDirection !== 0) {
      return;
    }
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.pointerId !== event.pointerId || transitionDirection !== 0) {
      return;
    }
    const deltaX = event.clientX - dragRef.current.startX;
    if (Math.abs(deltaX) < DRAG_TRIGGER_PX) {
      return;
    }
    dragRef.current.pointerId = null;
    rotate(deltaX < 0 ? 1 : -1);
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.pointerId !== event.pointerId) {
      return;
    }
    dragRef.current.pointerId = null;
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
      <div
        className={`banner-carousel-shell ${transitionDirection !== 0 ? "banner-carousel-shell-animating" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
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
          {visibleVideos.map(({ slot, video, renderKey }) => (
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
              <span className="banner-carousel-title">{video.title}</span>
            </Link>
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
