import { execFileSync } from "node:child_process";
export default function teardown() {
  execFileSync(process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python", ["../scripts/browser_api.py", "--cleanup"], { stdio: "inherit", timeout: 30000 });
}
