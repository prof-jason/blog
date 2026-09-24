import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// Production is a static export served by FastAPI (same origin as /api).
// In dev, `next dev` proxies /api to the FastAPI server instead.
const nextConfig: NextConfig = isDev
  ? {
      async rewrites() {
        return [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }];
      },
    }
  : { output: "export" };

export default nextConfig;
