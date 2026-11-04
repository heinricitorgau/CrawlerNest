import type { Metadata } from "next";
import { absoluteUrl } from "@/lib/site";
import RankingsClientPage from "./rankings-client-page";

// "/" serves this same page, so both name "/" as canonical: one indexed copy.
const home = absoluteUrl("/");
export const metadata: Metadata = home ? { alternates: { canonical: home } } : {};

export default function Page() {
  return <RankingsClientPage />;
}
