import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { createInterface } from "node:readline";

const [projectArg, outputArg] = process.argv.slice(2);
if (!projectArg || !outputArg) {
  throw new Error("usage: node e2e/kicad-mcp-smoke.mjs <project-dir> <output.json>");
}

const projectPath = resolve(projectArg);
const outputPath = resolve(outputArg);
const command = (program, args = []) => execFileSync(program, args, { encoding: "utf8" }).trim();
const ngspiceVersion = command("ngspice", ["-v"]).split("\n").find(line => line.includes("ngspice-"))?.trim();
const freeroutingStore = command("realpath", [process.env.FREEROUTING]).split("/")[3]?.replace(/^[^-]+-/, "");
const mcpVenv = resolve(".pcb-cache/kicad-mcp-py314");
const child = spawn("npx", [
  "-y", "kicad-mcp@0.1.6", "--stdio", "--python", "python3", "--venv", mcpVenv,
], {
  env: { ...process.env, KICAD_SEARCH_PATHS: resolve("hardware") },
  stdio: ["pipe", "pipe", "inherit"],
});
const lines = createInterface({ input: child.stdout });
const pending = new Map();
let nextId = 1;

lines.on("line", line => {
  let message;
  try { message = JSON.parse(line); } catch { return; }
  if (message.id !== undefined && pending.has(message.id)) {
    const { resolve: accept, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else accept(message.result);
  }
});

function send(method, params = {}) {
  const id = nextId++;
  child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
  return new Promise((accept, reject) => pending.set(id, { resolve: accept, reject }));
}

function notify(method, params = {}) {
  child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method, params })}\n`);
}

const timeout = setTimeout(() => {
  child.kill("SIGTERM");
  throw new Error("KiCad MCP smoke timed out");
}, 120_000);

try {
  const initialized = await send("initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "outfitter-playground", version: "0.1.0" },
  });
  notify("notifications/initialized");
  const tools = await send("tools/list");
  const names = tools.tools.map(tool => tool.name);
  for (const required of ["kicad_tool_inventory", "kicad_project_summary", "kicad_validate_board"]) {
    if (!names.includes(required)) throw new Error(`KiCad MCP is missing ${required}`);
  }
  const inventory = await send("tools/call", {
    name: "kicad_tool_inventory",
    arguments: { include_tools: true },
  });
  const summary = await send("tools/call", {
    name: "kicad_project_summary",
    arguments: { project_path: projectPath },
  });
  const validation = await send("tools/call", {
    name: "kicad_validate_board",
    arguments: {
      board_path: `${projectPath}/pnb-1.kicad_pcb`,
      run_drc_check: true,
      output_path: `${projectPath}/review/mcp-drc.json`,
    },
  });
  const inventoryData = JSON.parse(inventory.content[0].text);
  const summaryData = JSON.parse(summary.content[0].text);
  const validationData = JSON.parse(validation.content[0].text);
  const report = {
    package: "kicad-mcp@0.1.6",
    protocolVersion: initialized.protocolVersion,
    toolCount: names.length,
    requiredTools: ["kicad_tool_inventory", "kicad_project_summary", "kicad_validate_board"],
    toolVersions: {
      kicad: command("kicad-cli", ["version"]),
      pythonStack: JSON.parse(command("hardware/.venv/bin/python", ["-c", [
        "import importlib.metadata as m, json, pcbnew",
        "print(json.dumps({'pcbnew': pcbnew.Version(), **{p: m.version(p) for p in ['skidl','kibot','kinet2pcb','lxml']}}))",
      ].join("; ")])),
      kicadMcp: "0.1.6",
      freerouting: freeroutingStore,
      ngspice: ngspiceVersion,
    },
    inventory: {
      total: inventoryData.total,
      categories: inventoryData.categories,
      safetyCounts: inventoryData.safety_counts,
      requiresCounts: inventoryData.requires_counts,
    },
    projectSummary: {
      projectDir: "hardware/pnb-1",
      projectFiles: summaryData.project_files,
      schematics: summaryData.schematics,
      boards: summaryData.boards,
      outputs: summaryData.outputs,
      files: summaryData.files.map(file => file.slice(projectPath.length + 1)),
    },
    boardValidation: {
      ok: validationData.ok,
      parseOk: validationData.parse_ok,
      fileSizeBytes: validationData.file_size_bytes,
      drc: {
        ok: validationData.drc?.ok,
        returncode: validationData.drc?.returncode,
        violations: validationData.drc?.violations,
        unconnected: validationData.drc?.unconnected,
      },
    },
  };
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);
  console.log(`KiCad MCP: ${names.length} tools; inventory, project summary, and board validation passed`);
} finally {
  clearTimeout(timeout);
  child.stdin.end();
  child.kill("SIGTERM");
}
