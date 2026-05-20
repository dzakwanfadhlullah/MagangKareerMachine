import { NextResponse } from "next/server";
import { startEngineRun, type EngineRunRequest } from "@/lib/dashboard/engine-runner";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as EngineRunRequest;
  const status = await startEngineRun(body);
  return NextResponse.json(status, {
    status: status.running ? 202 : 409,
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
