from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.services.data_archive import load_local_data_archive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore local Cloud Storage Player data from a zip archive.")
    parser.add_argument("archive_path", help="Source zip path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = load_local_data_archive(get_settings(), archive_path=Path(args.archive_path))
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Loaded local data archive: {result.output_path}")
    for entry in result.included_entries:
        print(f"- {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
