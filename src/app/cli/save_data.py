from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.services.data_archive import save_local_data_archive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Save local Cloud Storage Player data into a zip archive.")
    parser.add_argument("output_path", help="Target zip path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = save_local_data_archive(get_settings(), output_path=Path(args.output_path))
    print(f"Saved local data archive: {result.output_path}")
    for entry in result.included_entries:
        print(f"- {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
