import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev-mode access from the WSL NAT IP (Windows browser cannot use
  // localhost:3000 while winnat reserves that port — see CLAUDE.md).
  // Update the IP if `wsl hostname -I` changes after a WSL restart.
  allowedDevOrigins: ["172.17.71.187"],
};

export default nextConfig;
