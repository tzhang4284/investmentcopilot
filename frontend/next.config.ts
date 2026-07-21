import type { NextConfig } from "next";

// All /api/* traffic goes through the authenticated proxy route handler at
// src/app/api/[...path]/route.ts (BACKEND_URL env var), not a rewrite, so the
// backend token never reaches the browser.
const nextConfig: NextConfig = {};

export default nextConfig;
