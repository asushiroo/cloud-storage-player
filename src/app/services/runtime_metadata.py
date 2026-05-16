from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.services.runtime_paths import runtime_metadata_path, runtime_run_dir


@dataclass(slots=True)
class RuntimeMetadata:
    pid: int
    port: int
    control_token: str


def write_runtime_metadata(settings: Settings, metadata: RuntimeMetadata) -> Path:
    path = runtime_metadata_path(settings)
    runtime_run_dir(settings).mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "pid": metadata.pid,
                "port": metadata.port,
                "control_token": metadata.control_token,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def read_runtime_metadata(settings: Settings) -> RuntimeMetadata | None:
    path = runtime_metadata_path(settings)
    if not path.exists() or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RuntimeMetadata(
        pid=int(payload["pid"]),
        port=int(payload["port"]),
        control_token=str(payload["control_token"]),
    )


def delete_runtime_metadata(settings: Settings) -> None:
    runtime_metadata_path(settings).unlink(missing_ok=True)
