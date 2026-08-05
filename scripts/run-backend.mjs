import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backend = path.join(root, "backend");
const venvPython = path.join(
  backend,
  ".venv",
  process.platform === "win32" ? "Scripts\\python.exe" : "bin/python",
);

if (!fs.existsSync(venvPython)) {
  console.error("Backend venv missing. Run: npm run setup");
  process.exit(1);
}

const child = spawn(
  venvPython,
  [
    "-m",
    "uvicorn",
    "app.main:app",
    "--reload",
    "--reload-dir",
    path.join(backend, "app"),
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
  ],
  {
    cwd: backend,
    stdio: "inherit",
    env: process.env,
  },
);

child.on("exit", (code) => process.exit(code ?? 0));
