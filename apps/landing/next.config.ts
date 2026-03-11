import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // GitHub Pages 项目页部署在 username.github.io/repo-name
  basePath: process.env.NODE_ENV === "production" ? "/wukong" : "",
  assetPrefix: process.env.NODE_ENV === "production" ? "/wukong/" : "",
};

export default nextConfig;
