"use client";

import dynamic from "next/dynamic";

import { RankingsShell } from "./rankings-content";

const RankingsHomeContent = dynamic(() => import("./rankings-content"), {
  ssr: false,
  loading: () => <RankingsShell message="Loading rankings browser..." />,
});

export default function RankingsClientPage() {
  return <RankingsHomeContent />;
}
