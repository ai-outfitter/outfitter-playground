import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parse } from "yaml";

const root = process.argv[2];
if (!root) throw new Error("usage: node e2e/assert-pcb-workflow.mjs <dump-root>");

const read = (...parts) => readFileSync(join(root, ".agents", ...parts), "utf8");
const agent = read("agents", "hardware-engineer", "agent.md");
const mcp = JSON.parse(read("agents", "hardware-engineer", "mcp.json"));
const workflow = parse(read("workflows", "pcb-design", "workflow.yaml"));
read("skills", "pcb-tools-setup", "SKILL.md");

if (!agent.includes("pcb-tools-setup")) {
  throw new Error("hardware-engineer does not select pcb-tools-setup");
}

const kicadArgs = mcp.mcpServers?.kicad?.args;
if (!Array.isArray(kicadArgs) || !kicadArgs.includes("kicad-mcp@0.1.6")) {
  throw new Error("hardware-engineer does not pin kicad-mcp@0.1.6");
}

const evidence = workflow.outputs?.["toolchain-evidence"];
if (evidence?.from !== "setup" || evidence?.type !== "toolchain-evidence") {
  throw new Error("pcb-design does not expose typed toolchain-evidence from setup");
}

const nodes = new Map(workflow.nodes?.map(node => [node.id, node]));
const setup = nodes.get("setup");
const schematic = nodes.get("schematic");
if (setup?.action !== "establish-and-prove-pcb-toolchain" || setup?.skill !== "pcb-tools-setup") {
  throw new Error("pcb-design setup node does not run pcb-tools-setup");
}
if (!setup.uses?.includes("kicad")) {
  throw new Error("pcb-design setup node does not use the KiCad MCP integration");
}
if (!schematic?.needs?.includes("setup")) {
  throw new Error("pcb-design schematic node does not depend on setup");
}
