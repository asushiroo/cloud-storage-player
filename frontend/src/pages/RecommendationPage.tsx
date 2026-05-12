import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchVideoRecommendations } from "../api/client";
import { BannerCarousel } from "../components/BannerCarousel";
import { Surface } from "../components/Surface";
import { VideoGridCard } from "../components/VideoGridCard";
import { useRequireSession } from "../hooks/session";
import type { Video, VideoRecommendationShelf } from "../types/api";

const HERO_BANNER_LIMIT = 5;
const SECONDARY_RECOMMENDATION_LIMIT = 12;
const RECENT_WATCH_LIMIT = 10;

function mergeUniqueVideos(...groups: Video[][]): Video[] {
  const merged: Video[] = [];
  const seenIds = new Set<number>();
  for (const group of groups) {
    for (const video of group) {
      if (seenIds.has(video.id)) {
        continue;
      }
      seenIds.add(video.id);
      merged.push(video);
    }
  }
  return merged;
}

function pickHeroVideos(shelf?: VideoRecommendationShelf): Video[] {
  if (!shelf) {
    return [];
  }
  return mergeUniqueVideos(shelf.recommended, shelf.popular)
    .filter((video) => video.poster_path || video.cover_path)
    .slice(0, HERO_BANNER_LIMIT);
}

function pickSecondaryVideos(shelf?: VideoRecommendationShelf, heroVideos: Video[] = []): Video[] {
  if (!shelf) {
    return [];
  }
  const excludedIds = new Set(heroVideos.map((video) => video.id));
  return mergeUniqueVideos(shelf.recommended, shelf.popular, shelf.continue_watching)
    .filter((video) => !excludedIds.has(video.id))
    .slice(0, SECONDARY_RECOMMENDATION_LIMIT);
}

export function RecommendationPage() {
  const session = useRequireSession();
  const recommendationsQuery = useQuery({
    queryKey: ["videos", "recommendations"],
    queryFn: fetchVideoRecommendations,
    enabled: session.data?.authenticated === true,
  });

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  const shelf = recommendationsQuery.data;
  const bannerVideos = pickHeroVideos(shelf);
  const secondaryVideos = pickSecondaryVideos(shelf, bannerVideos);
  const recentVideos = shelf?.continue_watching.slice(0, RECENT_WATCH_LIMIT) ?? [];
  const artworkVersionToken = recommendationsQuery.dataUpdatedAt;

  return (
    <div className="library-page recommendation-page">
      <div className="library-banner-shell">
        {bannerVideos.length > 0 ? (
          <BannerCarousel versionToken={artworkVersionToken} videos={bannerVideos} />
        ) : (
          <Surface>
            <h1>推荐页</h1>
            <p className="muted">当前还没有可推荐的视频，先去管理页导入内容。</p>
          </Surface>
        )}
      </div>

      <div className="library-content-shell page-stack">
        <Surface>
          <div className="section-head">
            <div>
              <h2>最近观看</h2>
              <p className="muted">这里只保留一行标题，方便快速回到上次停下的位置。</p>
            </div>
          </div>
          {recentVideos.length > 0 ? (
            <div className="recent-watch-row top-gap">
              {recentVideos.map((video) => (
                <Link className="recent-watch-link" key={`recent-${video.id}`} title={video.title} to={`/videos/${video.id}/play`}>
                  {video.title}
                </Link>
              ))}
            </div>
          ) : (
            <p className="muted top-gap">还没有最近观看记录。</p>
          )}
        </Surface>

        <Surface>
          <div className="section-head">
            <div>
              <h2>次推荐位</h2>
              <p className="muted">优先展示推荐候选，数量限制为 4 行 3 列的首屏节奏。</p>
            </div>
            <Link className="secondary-button link-button" to="/library">
              打开媒体库
            </Link>
          </div>
        </Surface>

        {secondaryVideos.length > 0 ? (
          <div className="video-grid">
            {secondaryVideos.map((video) => (
              <VideoGridCard key={`secondary-${video.id}`} versionToken={artworkVersionToken} video={video} />
            ))}
          </div>
        ) : (
          <Surface>
            <p className="muted">推荐位还没有足够的数据，先去媒体库播放几部视频。</p>
          </Surface>
        )}
      </div>
    </div>
  );
}
