import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function run(command, args, cwd = root) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: "inherit",
    shell: true,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

console.log("Installing root tooling...");
run("npm", ["install"]);

console.log("\nSetting up backend...");
run(process.execPath, ["scripts/setup-backend.mjs"]);

console.log("\nInstalling frontend dependencies...");
run("npm", ["install"], path.join(root, "frontend"));

console.log("\nSetup complete. Start the app with: npm start");
