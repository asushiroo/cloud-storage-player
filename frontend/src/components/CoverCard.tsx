import { buildAssetUrl } from "../api/client";

interface CoverCardProps {
  coverPath: string | null;
  title: string;
}

export function CoverCard({ coverPath, title }: CoverCardProps) {
  const url = buildAssetUrl(coverPath);
  return (
    <div className="cover-card">
      {url ? <img alt={title} className="cover-image" src={url} /> : <div className="cover-placeholder">No Cover</div>}
      <div className="cover-title">{title}</div>
    </div>
  );
}
