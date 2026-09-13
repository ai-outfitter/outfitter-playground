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
read("skills", "pcb-quote", "SKILL.md");

if (!agent.includes("pcb-tools-setup")) {
  throw new Error("hardware-engineer does not select pcb-tools-setup");
}
if (!agent.includes("pcb-quote") || !agent.includes("browser-mcp")) {
  throw new Error("hardware-engineer does not select pcb-quote and browser-mcp");
}

const kicadArgs = mcp.mcpServers?.kicad?.args;
if (!Array.isArray(kicadArgs) || !kicadArgs.includes("kicad-mcp@0.1.6")) {
  throw new Error("hardware-engineer does not pin kicad-mcp@0.1.6");
}
const playwrightArgs = mcp.mcpServers?.playwright?.args;
if (!Array.isArray(playwrightArgs) || !playwrightArgs.includes("@playwright/mcp@0.0.55")) {
  throw new Error("hardware-engineer does not pin the Playwright MCP integration");
}

const evidence = workflow.outputs?.["toolchain-evidence"];
if (evidence?.from !== "setup" || evidence?.type !== "toolchain-evidence") {
  throw new Error("pcb-design does not expose typed toolchain-evidence from setup");
}

const nodes = new Map(workflow.nodes?.map(node => [node.id, node]));
const setup = nodes.get("setup");
const schematic = nodes.get("schematic");
const quote = nodes.get("quote");
const draft = nodes.get("draft");
if (setup?.action !== "establish-and-prove-pcb-toolchain" || setup?.skill !== "pcb-tools-setup") {
  throw new Error("pcb-design setup node does not run pcb-tools-setup");
}
if (!setup.uses?.includes("kicad")) {
  throw new Error("pcb-design setup node does not use the KiCad MCP integration");
}
if (!schematic?.needs?.includes("setup")) {
  throw new Error("pcb-design schematic node does not depend on setup");
}

const supplierQuote = workflow.outputs?.["supplier-quote"];
if (supplierQuote?.from !== "quote" || supplierQuote?.type !== "supplier-quote") {
  throw new Error("pcb-design does not expose typed supplier-quote evidence");
}
if (quote?.action !== "reconcile-supplier-landed-cost" || quote?.skill !== "pcb-quote") {
  throw new Error("pcb-design quote node does not run pcb-quote");
}
if (!quote.needs?.includes("release") || !quote.uses?.includes("browser")) {
  throw new Error("pcb-design quote node does not gate the release through browser evidence");
}
if (!draft?.needs?.includes("quote")) {
  throw new Error("pcb-design draft PR does not depend on the complete supplier quote");
}
