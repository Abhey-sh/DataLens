import { spawnSync } from "node:child_process";
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

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: backend,
    stdio: "inherit",
    ...options,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function resolvePython() {
  const candidates =
    process.platform === "win32"
      ? [
          ["py", ["-3"]],
          ["python", []],
        ]
      : [
          ["python3", []],
          ["python", []],
        ];

  for (const [command, baseArgs] of candidates) {
    const check = spawnSync(command, [...baseArgs, "--version"], {
      encoding: "utf8",
      shell: false,
    });
    if (check.status === 0) {
      return [command, baseArgs];
    }
  }
  console.error("Python 3 is required. Install Python and retry.");
  process.exit(1);
}

if (!fs.existsSync(venvPython)) {
  console.log("Creating backend virtual environment...");
  const [command, baseArgs] = resolvePython();
  run(command, [...baseArgs, "-m", "venv", ".venv"]);
}

console.log("Installing backend dependencies...");
run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);
run(venvPython, ["-m", "pip", "install", "-r", "requirements.txt"]);
console.log("Backend setup complete.");
