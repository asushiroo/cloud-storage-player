#!/usr/bin/env node

import { accessSync, constants } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";

const projectRoot = process.cwd();
const pythonExecutable =
  process.platform === "win32"
    ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
    : path.join(projectRoot, ".venv", "bin", "python");

try {
  accessSync(pythonExecutable, constants.X_OK);
} catch {
  console.error("[backend] Virtual environment Python was not found. Run `uv sync --dev` first.");
  process.exit(1);
}

const child = spawn(pythonExecutable, ["-m", "app.main"], {
  cwd: projectRoot,
  stdio: "inherit",
  shell: false,
  env: process.env,
});

child.on("error", (error) => {
  console.error(`[backend] Failed to start backend: ${error.message}`);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
