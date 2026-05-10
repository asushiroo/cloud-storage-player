import { buildAssetUrl } from "../api/client";

interface CoverCardProps {
  coverPath: string | null;
  title: string;
  versionToken?: string | number;
}

export function CoverCard({ coverPath, title, versionToken }: CoverCardProps) {
  const url = buildAssetUrl(coverPath, versionToken);
  return (
    <div className="cover-card">
      {url ? <img alt={title} className="cover-image" src={url} /> : <div className="cover-placeholder">No Cover</div>}
    </div>
  );
}
