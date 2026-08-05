import { spawn, spawnSync } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function canConnect(port, host) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host });
    socket.setTimeout(500);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => resolve(false));
  });
}

const unavailablePorts = [];
for (const port of [8000, 5173]) {
  const inUse =
    (await canConnect(port, "127.0.0.1")) ||
    (await canConnect(port, "::1"));
  if (inUse) unavailablePorts.push(port);
}

if (unavailablePorts.length) {
  console.error(
    `Cannot start DataLens: port${unavailablePorts.length > 1 ? "s" : ""} ${unavailablePorts.join(", ")} already in use.`,
  );
  console.error("Stop the previous DataLens process, then run npm run dev:full again.");
  process.exit(1);
}

const vite = path.join(
  root,
  "frontend",
  "node_modules",
  "vite",
  "bin",
  "vite.js",
);
const children = [
  spawn(process.execPath, ["scripts/run-backend.mjs"], {
    cwd: root,
    stdio: "inherit",
    env: process.env,
  }),
  spawn(process.execPath, [vite, "--strictPort"], {
    cwd: path.join(root, "frontend"),
    stdio: "inherit",
    env: process.env,
  }),
];

let shuttingDown = false;

function stopProcessTree(child) {
  if (!child.pid || child.exitCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
    });
  } else {
    child.kill("SIGTERM");
  }
}

function shutdown(exitCode = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  children.forEach(stopProcessTree);
  process.exit(exitCode);
}

for (const child of children) {
  child.once("error", (error) => {
    console.error(`Failed to start DataLens service: ${error.message}`);
    shutdown(1);
  });
  child.once("exit", (code) => {
    if (!shuttingDown) shutdown(code ?? 1);
  });
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
