import type { NextConfig } from "next";

const staticExport = process.env.CF_PAGES === "1" || process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  output: staticExport ? "export" : "standalone",
  webpack: (config) => {
    config.cache = false;
    return config;
  },
  experimental: {
    reactCompiler: false
  }
};

export default nextConfig;
