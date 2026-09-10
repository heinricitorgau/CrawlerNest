import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lets a Windows browser load dev pages from the WSL NAT IP. Without it,
  // Next serves the chunks but never hydrates a non-localhost origin.
  //
  // This is not a general workaround for winnat reserving localhost:3000,
  // and it does not rescue /agent: that page calls crypto.randomUUID(), which
  // browsers only expose in a secure context, and a bare-IP http:// origin is
  // not one. Over the WSL IP it dies in the error boundary on first render.
  // localhost is a secure context at any port, so the workaround that covers
  // every page is a port outside winnat's excluded ranges (2901-3000,
  // 3001-3500), browsed via localhost:
  //
  //   WEB_PORT=4000 ./scripts/start_localhost.sh   ->  http://localhost:4000
  //
  // Update the IP if `wsl hostname -I` changes after a WSL restart.
  allowedDevOrigins: ["172.17.71.187"],
};

export default nextConfig;
