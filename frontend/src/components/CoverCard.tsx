import { buildAssetUrl } from "../api/client";

interface CoverCardProps {
  artworkPath: string | null;
  title: string;
  versionToken?: string | number;
}

export function CoverCard({ artworkPath, title, versionToken }: CoverCardProps) {
  const url = buildAssetUrl(artworkPath, versionToken);
  return (
    <div className="cover-card">
      {url ? <img alt={title} className="cover-image" src={url} /> : <div className="cover-placeholder">No Cover</div>}
    </div>
  );
}
