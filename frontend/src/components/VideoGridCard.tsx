import { Link } from "react-router-dom";
import type { Video } from "../types/api";
import { formatBytes, formatDuration } from "../utils/format";
import { expandTagValue } from "../utils/tagHierarchy";
import { CoverCard } from "./CoverCard";

interface VideoGridCardProps {
  video: Video;
  versionToken?: string | number;
}

export function VideoGridCard({ video, versionToken }: VideoGridCardProps) {
  const parsedTags = video.tags.flatMap(expandTagValue);
  const primaryTags = parsedTags.filter((tag) => tag.level === "primary" && tag.label).map((tag) => tag.label);
  const secondaryTags = parsedTags.filter((tag) => tag.level === "secondary" && tag.label).map((tag) => tag.label);
  const hasTags = primaryTags.length > 0 || secondaryTags.length > 0;

  return (
    <Link className="video-card" to={`/videos/${video.id}`}>
      <CoverCard artworkPath={video.poster_path ?? video.cover_path} title={video.title} versionToken={versionToken} />
      <div className="video-meta">
        <h2>{video.title}</h2>
        <p className="muted">
          {formatDuration(video.duration_seconds)} · {formatBytes(video.size)} · {video.segment_count} segments
        </p>
        {hasTags ? (
          <div className="video-tag-lines">
            <div className="video-tag-line">
              {primaryTags.map((tag, index) => (
                <span className="mini-tag" key={`${video.id}-primary-${tag}-${index}`}>
                  {tag}
                </span>
              ))}
            </div>
            <div className="video-tag-line">
              {secondaryTags.map((tag, index) => (
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
  );
}
