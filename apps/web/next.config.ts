import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Transpile the workspace packages so their TS sources are compiled by Next.
  transpilePackages: ["@omniboost/contracts", "@omniboost/design-tokens"],
};

export default nextConfig;
