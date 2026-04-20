import { cpSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const nextRoot = path.join(projectRoot, ".next");
const standaloneRoot = path.join(nextRoot, "standalone");
const standaloneNextRoot = path.join(standaloneRoot, ".next");
const standaloneServer = path.join(standaloneRoot, "server.js");
const staticSource = path.join(nextRoot, "static");
const staticTarget = path.join(standaloneNextRoot, "static");
const publicSource = path.join(projectRoot, "public");
const publicTarget = path.join(standaloneRoot, "public");

function syncDirectory(source, target) {
  if (!existsSync(source)) {
    return;
  }

  mkdirSync(path.dirname(target), { recursive: true });
  cpSync(source, target, {
    recursive: true,
    force: true,
  });
}

function prepareStandalone() {
  if (!existsSync(standaloneServer)) {
    throw new Error(
      "Missing .next/standalone/server.js. Run `npm run build` before starting standalone."
    );
  }

  syncDirectory(staticSource, staticTarget);
  syncDirectory(publicSource, publicTarget);
}

async function main() {
  prepareStandalone();

  if (process.argv.includes("--prepare-only")) {
    console.log("Standalone assets prepared.");
    return;
  }

  const child = spawn(process.execPath, [standaloneServer], {
    cwd: projectRoot,
    stdio: "inherit",
    env: process.env,
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }

    process.exit(code ?? 0);
  });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
