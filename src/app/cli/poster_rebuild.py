from __future__ import annotations

from app.core.config import get_settings
from app.services.poster_rebuild import rebuild_all_video_posters


def main() -> None:
    settings = get_settings()
    result = rebuild_all_video_posters(settings)
    print(
        "Poster rebuild finished: "
        f"rebuilt={result.rebuilt_count}, "
        f"skipped={result.skipped_count}, "
        f"failed={result.failed_count}"
    )
    if result.failed_video_ids:
        print(f"Failed video ids: {', '.join(str(video_id) for video_id in result.failed_video_ids)}")
