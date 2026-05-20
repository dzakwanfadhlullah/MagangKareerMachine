import { NextResponse } from "next/server";
import { readDashboardSnapshot } from "@/lib/dashboard/server-data";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const snapshot = await readDashboardSnapshot();
  return NextResponse.json(snapshot, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
