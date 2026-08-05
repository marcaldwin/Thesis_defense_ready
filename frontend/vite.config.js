import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontendDir = fileURLToPath(new URL(".", import.meta.url));
const projectDir = path.resolve(frontendDir, "..");
const backendPort = Number(process.env.SAGE_BACKEND_PORT || 8001);
const defaultPython = process.platform === "win32"
  ? path.resolve(projectDir, "..", ".venv", "Scripts", "python.exe")
  : path.resolve(projectDir, "..", ".venv", "bin", "python");

function startSageBackend() {
  return {
    name: "start-sage-backend",
    configureServer(server) {
      const python = process.env.SAGE_PYTHON || defaultPython;
      const backendProcess = spawn(
        python,
        [
          "-m",
          "uvicorn",
          "backend.main:app",
          "--host",
          "127.0.0.1",
          "--port",
          String(backendPort),
          "--reload",
          "--reload-dir",
          path.resolve(projectDir, "backend")
        ],
        {
          cwd: projectDir,
          env: { ...process.env, PYTHONUNBUFFERED: "1" },
          stdio: "inherit",
          windowsHide: true
        }
      );

      backendProcess.on("error", (error) => {
        console.error(`[SAGE backend] Could not start: ${error.message}`);
      });

      const stopBackend = () => {
        if (!backendProcess.killed) backendProcess.kill();
      };
      server.httpServer?.once("close", stopBackend);
      process.once("exit", stopBackend);
    }
  };
}

export default defineConfig({
  plugins: [react(), startSageBackend()],
  server: {
    port: 5174,
    strictPort: true,
    host: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, "")
      }
    }
  }
});
