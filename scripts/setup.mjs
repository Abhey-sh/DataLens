import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function run(command, args, cwd = root, shell = false) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: "inherit",
    shell,
  });
  if (result.error) {
    console.error(`Failed to run ${command}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

console.log("Installing root tooling...");
run("npm", ["install"], root, process.platform === "win32");

console.log("\nSetting up backend...");
run(process.execPath, ["scripts/setup-backend.mjs"]);

console.log("\nInstalling frontend dependencies...");
run(
  "npm",
  ["install"],
  path.join(root, "frontend"),
  process.platform === "win32",
);

console.log("\nSetup complete. Start the app with: npm start");
