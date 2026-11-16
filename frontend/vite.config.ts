import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// The dev server passes /api/* on to the FastAPI backend, so the browser sees one site
// (localhost:5173): the login cookie (SameSite=Strict, path /api/v1/auth) just works and
// no CORS is involved. API_TARGET in frontend/.env changes where the backend is.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxy = {
    "/api": { target: env.API_TARGET || "http://127.0.0.1:8000", changeOrigin: true },
  };
  return {
    plugins: [react(), tailwindcss()],
    server: { host: "localhost", port: 5173, strictPort: true, proxy },
    preview: { host: "localhost", port: 4173, strictPort: true, proxy },
  };
});
