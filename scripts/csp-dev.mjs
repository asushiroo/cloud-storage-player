#!/usr/bin/env node

import net from "node:net";
import { spawn } from "node:child_process";

const HOST = "0.0.0.0";
const DEFAULT_PORT = 8000;
const MAX_PORT_ATTEMPTS = 200;

const parsePort = (value) => {
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1 || parsed > 65535) {
    return null;
  }
  return parsed;
};

const checkPortAvailable = (port) =>
  new Promise((resolve) => {
    const server = net.createServer();

    server.once("error", (error) => {
      if (error && (error.code === "EADDRINUSE" || error.code === "EACCES")) {
        resolve(false);
        return;
      }
      resolve(false);
    });

    server.listen({ host: HOST, port, exclusive: true }, () => {
      server.close(() => resolve(true));
    });
  });

const findAvailablePort = async (preferredPort) => {
  for (let offset = 0; offset < MAX_PORT_ATTEMPTS; offset += 1) {
    const candidate = preferredPort + offset;
    if (candidate > 65535) {
      break;
    }
    // Avoid noisy bind failures from uvicorn by pre-checking the TCP port.
    if (await checkPortAvailable(candidate)) {
      return candidate;
    }
  }
  return null;
};

const basePort = parsePort(process.env.CSP_PORT) ?? DEFAULT_PORT;
const selectedPort = await findAvailablePort(basePort);

if (!selectedPort) {
  console.error(
    `[csp] No available port found in range ${basePort}-${Math.min(basePort + MAX_PORT_ATTEMPTS - 1, 65535)}.`
  );
  process.exit(1);
}

if (selectedPort !== basePort) {
  console.warn(`[csp] Port ${basePort} is busy, fallback to ${selectedPort}.`);
}

const childEnv = {
  ...process.env,
  CSP_PORT: String(selectedPort),
};

const child = spawn("npm", ["run", "csp:concurrently"], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: childEnv,
});

let shuttingDown = false;

const forwardSignal = (signal) => {
  if (!shuttingDown) {
    shuttingDown = true;
  }
  if (!child.killed) {
    child.kill(signal);
  }
};

["SIGINT", "SIGTERM", "SIGHUP"].forEach((signal) => {
  process.on(signal, () => forwardSignal(signal));
});

child.on("error", (error) => {
  console.error(`[csp] Failed to start child process: ${error.message}`);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
