from __future__ import annotations

import os
import secrets
import subprocess
import sys

from app.core.config import get_settings
from app.services.runtime_metadata import RuntimeMetadata, write_runtime_metadata
from app.services.runtime_paths import runtime_logs_dir, runtime_run_dir


def main() -> int:
    settings = get_settings()
    if "--serve" in sys.argv or os.environ.get("CSP_RUNTIME_SERVE") == "1":
        from app.main import run_server

        run_server(settings)
        return 0

    existing_metadata = None
    try:
        from app.services.runtime_control_client import fetch_shutdown_state
        from app.services.runtime_metadata import read_runtime_metadata, delete_runtime_metadata

        existing_metadata = read_runtime_metadata(settings)
        if existing_metadata is not None:
            try:
                fetch_shutdown_state(
                    port=existing_metadata.port,
                    control_token=existing_metadata.control_token,
                )
            except Exception:
                delete_runtime_metadata(settings)
            else:
                print(f"Cloud Storage Player is already running. pid={existing_metadata.pid} port={existing_metadata.port}")
                return 1
    except Exception:
        existing_metadata = None

    runtime_run_dir(settings).mkdir(parents=True, exist_ok=True)
    runtime_logs_dir(settings).mkdir(parents=True, exist_ok=True)

    control_token = secrets.token_urlsafe(24)
    env = os.environ.copy()
    env["CSP_USE_FRONTEND_DIST"] = "1"
    env["CSP_CONTROL_TOKEN"] = control_token
    env["CSP_RUNTIME_ROOT"] = str(settings.runtime_root)
    env["CSP_RUNTIME_SERVE"] = "1"
    src_path = str((settings.runtime_root / "src").resolve())
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"

    stdout_path = runtime_logs_dir(settings) / "start.out.log"
    stderr_path = runtime_logs_dir(settings) / "start.err.log"
    if getattr(sys, "frozen", False):
        python_executable = sys.executable
        entrypoint = [python_executable]
    else:
        python_executable = sys.executable
        entrypoint = [python_executable, "-m", "app.main"]

    with stdout_path.open("ab") as stdout_file, stderr_path.open("ab") as stderr_file:
        process = subprocess.Popen(
            entrypoint,
            cwd=str(settings.runtime_root),
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            ),
        )

    write_runtime_metadata(
        settings,
        RuntimeMetadata(
            pid=process.pid,
            port=settings.port,
            control_token=control_token,
        ),
    )
    print(f"Started Cloud Storage Player backend. pid={process.pid} port={settings.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
