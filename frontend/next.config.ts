import type { NextConfig } from "next";
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  turbopack: { root: process.cwd() },
  experimental: {
    cpus: 1,
    optimizePackageImports: ["radix-ui", "lucide-react", "recharts"],
    webpackMemoryOptimizations: true,
  },
};
export default config;
