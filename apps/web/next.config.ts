import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      (process.env.VERCEL_ENV ? "https://fit-check-b2-api.vercel.app" : "http://localhost:8000");
    return [
      {
        source: "/v1/:path*",
        destination: `${apiBase}/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${apiBase}/health`,
      },
      {
        source: "/docs",
        destination: `${apiBase}/docs`,
      },
      {
        source: "/openapi.json",
        destination: `${apiBase}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
