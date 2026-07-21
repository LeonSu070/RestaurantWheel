import type { NextConfig } from "next";

const isPagesBuild = process.env.GITHUB_PAGES === "true";

const nextConfig: NextConfig = {
  ...(isPagesBuild
    ? {
        output: "export" as const,
        basePath: "/RestaurantWheel",
        assetPrefix: "/RestaurantWheel",
        trailingSlash: true,
      }
    : {}),
};

export default nextConfig;
