#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, rmSync } from "node:fs";
import path from "node:path";

const projectRoot = process.cwd();

const run = (command, args) => {
  const result = spawnSync(command, args, {
    cwd: projectRoot,
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
};

const pyinstallerAddData = (source, target) =>
  process.platform === "win32" ? `${source};${target}` : `${source}:${target}`;

run("npm", ["run", "build"]);

const distDir = path.join(projectRoot, "dist");
const buildDir = path.join(projectRoot, "build");
rmSync(distDir, { recursive: true, force: true });
rmSync(buildDir, { recursive: true, force: true });

const sharedArgs = [
  "--noconfirm",
  "--clean",
  "--onefile",
  "--paths",
  "src",
  "--add-data",
  pyinstallerAddData("src/app/web/templates", "src/app/web/templates"),
  "--add-data",
  pyinstallerAddData("frontend/dist", "frontend/dist"),
];

const pyinstallerExecutable =
  process.platform === "win32"
    ? path.join(projectRoot, ".venv", "Scripts", "pyinstaller.exe")
    : path.join(projectRoot, ".venv", "bin", "pyinstaller");

if (!existsSync(pyinstallerExecutable)) {
  console.error("[build:csp] PyInstaller is not installed in .venv. Run `uv sync --dev` first.");
  process.exit(1);
}

run(pyinstallerExecutable, [...sharedArgs, "--name", "start", "src/app/cli/runtime_start.py"]);
run(pyinstallerExecutable, [...sharedArgs, "--name", "stop", "src/app/cli/runtime_stop.py"]);

const startExe = path.join(distDir, "start.exe");
const stopExe = path.join(distDir, "stop.exe");
if (existsSync(startExe)) {
  copyFileSync(startExe, path.join(projectRoot, "start.exe"));
}
if (existsSync(stopExe)) {
  copyFileSync(stopExe, path.join(projectRoot, "stop.exe"));
}
