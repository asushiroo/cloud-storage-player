from __future__ import annotations

import argparse
import sys

from app.core.config import get_settings
from app.services.baidu_oauth import BaiduOAuthConfigurationError
from app.services.baidu_smoke import BaiduSmokePrerequisiteError, run_baidu_smoke
from app.storage.baidu_api import BaiduApiError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a real Baidu Netdisk smoke test against the current Cloud Storage Player code path.",
    )
    parser.add_argument(
        "--source-path",
        default=None,
        help="Optional local video path. If omitted, a tiny sample MP4 will be generated automatically.",
    )
    parser.add_argument(
        "--oauth-code",
        default=None,
        help="Optional Baidu OAuth authorization code used to exchange and persist a refresh token before running.",
    )
    parser.add_argument(
        "--remote-root",
        default=None,
        help="Optional Baidu remote root. Must start with /apps/. Defaults to a timestamped smoke path.",
    )
    parser.add_argument(
        "--range-end",
        type=int,
        default=255,
        help="Verify remote playback bytes=0-range_end after sync. Default: 255.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()

    try:
        result = run_baidu_smoke(
            settings,
            source_path=args.source_path,
            oauth_code=args.oauth_code,
            remote_root=args.remote_root,
            range_end=args.range_end,
        )
    except (BaiduSmokePrerequisiteError, BaiduOAuthConfigurationError, BaiduApiError, RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"[baidu-smoke] FAILED: {exc}", file=sys.stderr)
        return 1

    print("[baidu-smoke] SUCCESS")
    print(f"remote_root={result.remote_root}")
    print(f"manifest_path={result.manifest_path}")
    print(f"writer_video_id={result.writer_video_id}")
    print(f"reader_video_id={result.reader_video_id}")
    print(f"segment_count={result.segment_count}")
    print(f"discovered_manifest_count={result.discovered_manifest_count}")
    print(f"created_video_count={result.created_video_count}")
    print(f"updated_video_count={result.updated_video_count}")
    print(f"verified_range=bytes=0-{result.verified_range_end}")
    print(f"workspace_dir={result.workspace_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
