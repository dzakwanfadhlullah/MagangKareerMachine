import "server-only";

import { spawn, type ChildProcessWithoutNullStreams } from "child_process";
import { existsSync } from "fs";
import { promises as fs } from "fs";
import path from "path";

export type EngineCommand = "crawl-sources" | "research" | "export-dashboard";

export type EngineRunRequest = {
  command?: EngineCommand;
  query?: string;
  location?: string;
  targetCategory?: string;
  profile?: string;
  minScore?: number;
};

export type EngineRunStatus = {
  running: boolean;
  phase: "idle" | "engine" | "export" | "success" | "failed";
  command: EngineCommand | null;
  args: string[];
  startedAt: string | null;
  finishedAt: string | null;
  exitCode: number | null;
  message: string;
  stdoutTail: string[];
  stderrTail: string[];
};

const STATUS_PATH = path.join(process.cwd(), "exports", "dashboard", "engine-status.json");
const DEFAULT_STATUS: EngineRunStatus = {
  running: false,
  phase: "idle",
  command: null,
  args: [],
  startedAt: null,
  finishedAt: null,
  exitCode: null,
  message: "Engine belum dijalankan dari dashboard.",
  stdoutTail: [],
  stderrTail: [],
};

let currentProcess: ChildProcessWithoutNullStreams | null = null;
let currentStatus: EngineRunStatus | null = null;

function pythonExecutable() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const venvPython = path.join(process.cwd(), ".venv", "Scripts", "python.exe");
  if (existsSync(venvPython)) return venvPython;
  return "python";
}

function clampTail(lines: string[]) {
  return lines.slice(-80);
}

function appendOutput(lines: string[], chunk: Buffer) {
  const text = chunk.toString("utf8").replace(/\r/g, "");
  return clampTail([...lines, ...text.split("\n").filter(Boolean)]);
}

async function writeStatus(status: EngineRunStatus) {
  currentStatus = status;
  await fs.mkdir(path.dirname(STATUS_PATH), { recursive: true });
  await fs.writeFile(STATUS_PATH, JSON.stringify(status, null, 2), "utf-8");
}

function buildArgs(request: EngineRunRequest) {
  const command = request.command ?? "crawl-sources";
  const profile = request.profile ?? "quick";
  const minScore = Number.isFinite(request.minScore) ? String(request.minScore) : "40";

  if (command === "export-dashboard") {
    return { command, args: ["main.py", "export-dashboard", "--output-dir", "exports/dashboard"] };
  }

  if (command === "research") {
    const args = [
      "main.py",
      "research",
      "--location",
      request.location?.trim() || "Indonesia",
      "--profile",
      profile,
      "--min-score",
      minScore,
    ];
    if (request.query?.trim()) args.push("--query", request.query.trim());
    if (request.targetCategory?.trim()) args.push("--target-category", request.targetCategory.trim());
    if (!request.query?.trim() && !request.targetCategory?.trim()) {
      args.push("--target-category", "tech");
    }
    return { command, args };
  }

  const args = ["main.py", "crawl-sources", "--profile", profile, "--min-score", minScore];
  if (request.targetCategory?.trim()) args.push("--target-category", request.targetCategory.trim());
  return { command, args };
}

function spawnPython(args: string[], status: EngineRunStatus, phase: EngineRunStatus["phase"]) {
  const child = spawn(pythonExecutable(), args, {
    cwd: process.cwd(),
    env: {
      ...process.env,
      PYTHONIOENCODING: "utf-8",
    },
    shell: false,
  });

  currentProcess = child;
  child.stdout.on("data", (chunk) => {
    const latest = currentStatus ?? status;
    void writeStatus({ ...latest, phase, stdoutTail: appendOutput(latest.stdoutTail, chunk) });
  });
  child.stderr.on("data", (chunk) => {
    const latest = currentStatus ?? status;
    void writeStatus({ ...latest, phase, stderrTail: appendOutput(latest.stderrTail, chunk) });
  });
  child.on("error", (error) => {
    currentProcess = null;
    void writeStatus({
      ...(currentStatus ?? status),
      running: false,
      phase: "failed",
      finishedAt: new Date().toISOString(),
      exitCode: null,
      message: `Gagal menjalankan Python: ${error.message}`,
    });
  });
  return child;
}

async function runExportAfterEngine(status: EngineRunStatus) {
  const exportStatus = {
    ...status,
    phase: "export" as const,
    message: "Engine selesai. Menulis export dashboard...",
  };
  await writeStatus(exportStatus);

  const child = spawnPython(["main.py", "export-dashboard", "--output-dir", "exports/dashboard"], exportStatus, "export");
  child.on("close", async (code) => {
    currentProcess = null;
    await writeStatus({
      ...(currentStatus ?? exportStatus),
      running: false,
      phase: code === 0 ? "success" : "failed",
      finishedAt: new Date().toISOString(),
      exitCode: code,
      message: code === 0 ? "Data dashboard sudah diperbarui." : "Engine selesai, tapi export dashboard gagal.",
    });
  });
}

export async function readEngineStatus(): Promise<EngineRunStatus> {
  if (currentStatus) return currentStatus;
  try {
    return JSON.parse(await fs.readFile(STATUS_PATH, "utf-8")) as EngineRunStatus;
  } catch {
    return DEFAULT_STATUS;
  }
}

export async function startEngineRun(request: EngineRunRequest): Promise<EngineRunStatus> {
  if (currentProcess) {
    return {
      ...(currentStatus ?? DEFAULT_STATUS),
      message: "Engine masih berjalan. Tunggu run sekarang selesai dulu.",
    };
  }

  const { command, args } = buildArgs(request);
  const status: EngineRunStatus = {
    running: true,
    phase: "engine",
    command,
    args,
    startedAt: new Date().toISOString(),
    finishedAt: null,
    exitCode: null,
    message: "Engine sedang berjalan...",
    stdoutTail: [],
    stderrTail: [],
  };
  await writeStatus(status);

  const child = spawnPython(args, status, "engine");
  child.on("close", async (code) => {
    if (code === 0 && command !== "export-dashboard") {
      await runExportAfterEngine(currentStatus ?? status);
      return;
    }
    currentProcess = null;
    await writeStatus({
      ...(currentStatus ?? status),
      running: false,
      phase: code === 0 ? "success" : "failed",
      finishedAt: new Date().toISOString(),
      exitCode: code,
      message: code === 0 ? "Data dashboard sudah diperbarui." : "Engine gagal. Cek log terakhir di status.",
    });
  });

  return status;
}
