import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  webpack: (config) => {
    config.cache = false;
    return config;
  },
  experimental: {
    reactCompiler: false
  }
};

export default nextConfig;
