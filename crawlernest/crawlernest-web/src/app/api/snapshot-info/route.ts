import { NextResponse } from "next/server";
import { existsSync, readFileSync } from "fs";
import path from "path";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  // Resolve path relative to the Next.js project root (crawlernest/crawlernest-web)
  // process.cwd() = crawlernest/crawlernest-web when running npm run dev / start
  const snapshotPath = path.resolve(process.cwd(), "../../snapshots/latest_status.json");

  if (!existsSync(snapshotPath)) {
    return NextResponse.json(
      {
        success: true,
        data: {
          has_snapshot: false,
          snapshot_timestamp: null,
          snapshot_file: null,
          aggregated_count: null,
          unresolved_total: null,
          unresolved_last_7d: null,
          unresolved_trend_pct: null,
          drift_warning_count: null,
          last_aggregation_run_id: null,
          last_aggregation_at: null,
          last_aggregation_status: null,
          last_ingestion: null,
          overall_stale: null,
        },
      },
      {
        headers: { "Cache-Control": "no-store" },
      }
    );
  }

  try {
    const raw = readFileSync(snapshotPath, "utf-8");
    const data = JSON.parse(raw) as Record<string, unknown>;
    return NextResponse.json(
      { success: true, data: { has_snapshot: true, ...data } },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch {
    return NextResponse.json(
      { success: false, error: "Failed to parse snapshot file" },
      { status: 500, headers: { "Cache-Control": "no-store" } }
    );
  }
}
