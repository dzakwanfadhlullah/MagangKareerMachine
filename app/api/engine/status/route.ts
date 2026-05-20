import { NextResponse } from "next/server";
import { readEngineStatus } from "@/lib/dashboard/engine-runner";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(await readEngineStatus(), {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
