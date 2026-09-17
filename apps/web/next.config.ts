import type { NextConfig } from "next";

/** API traffic is proxied at runtime via app/api/[...path]/route.ts (uses API_PROXY_URL). */
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
