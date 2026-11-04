/**
 * @jest-environment node
 *
 * Tassel's prompt and tools (Java resources, sent to the model by
 * TasselChatService) against the files they must agree with: the rubric the
 * essay scorer reads, and the allow-list the database enforces.
 */
import { readFileSync } from "fs";
import path from "path";

const JAVA_RESOURCES = path.resolve(__dirname, "../../../servise_for_java/src/main/resources");
const TASSEL_SYSTEM_PROMPT = readFileSync(path.join(JAVA_RESOURCES, "prompts/tassel_system.txt"), "utf8");
const tools = JSON.parse(readFileSync(path.join(JAVA_RESOURCES, "prompts/tassel_tools.json"), "utf8")) as {
  tools: { function: { name: string; parameters: unknown } }[];
  policy: Record<string, unknown>;
};
const rubric = JSON.parse(readFileSync(path.join(JAVA_RESOURCES, "prompts/essay_rubric.json"), "utf8")) as {
  dimensions: { key: string; label: string; definition: string }[];
};
const allowListSql = readFileSync(path.join(JAVA_RESOURCES, "db/auth/V004__tassel_tool_allow_list.sql"), "utf8");

type Schema = { type?: unknown; properties?: Record<string, Schema>; required?: string[]; additionalProperties?: unknown; items?: Schema };
const toolNames = tools.tools.map((tool) => tool.function.name);

describe("Tassel system prompt", () => {
  it("states every rubric dimension exactly as the essay scorer defines it", () => {
    for (const d of rubric.dimensions) {
      expect(TASSEL_SYSTEM_PROMPT).toContain(`- ${d.key} (${d.label}): ${d.definition}`);
    }
  });

  it("names each of its tools, and no tool it does not have", () => {
    for (const name of toolNames) {
      expect(TASSEL_SYSTEM_PROMPT).toContain(name);
    }
    const mentioned = TASSEL_SYSTEM_PROMPT.match(/\b[a-z]+(?:_[a-z]+){1,}\b/g) ?? [];
    expect(mentioned.filter((word) => !toolNames.includes(word))).toEqual([]);
  });

  it("keeps the rules that stop it inventing numbers, facts and saves", () => {
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/Never estimate a student's chance of admission/);
    // A school's admission rate, now that some schools have one, must not be turned into a chance.
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/not this student's chance; never turn it into one/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/A figure marked withheld or not available is not zero/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/Never give a numeric essay score in chat/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/Never invent a fact about the student/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/unless a tool result says "applied"/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/not as instructions to you/);
  });
});

describe("Tassel tools", () => {
  it("that change something are exactly the tools the database allows", () => {
    // A read changes nothing, so it is never a desk.chat_action row; its policy says so.
    const policy = tools.policy as Record<string, { outcome?: string }>;
    const reads = toolNames.filter((name) => policy[name]?.outcome?.startsWith("read only"));
    expect(reads).toEqual(["lookup_us_federal_data"]);
    const allowed = allowListSql.match(/tool_name IN \(([^)]*)\)/)?.[1].match(/'([a-z_]+)'/g)?.map((s) => s.slice(1, -1));
    expect([...(allowed ?? [])].sort()).toEqual(toolNames.filter((name) => !reads.includes(name)).sort());
  });

  it("have a policy entry each", () => {
    expect(Object.keys(tools.policy).sort()).toEqual([...toolNames].sort());
  });

  it("are closed object schemas whose required fields all exist", () => {
    const check = (schema: Schema, where: string) => {
      if (schema.type === "object") {
        expect({ where, additionalProperties: schema.additionalProperties }).toEqual({ where, additionalProperties: false });
        for (const field of schema.required ?? []) {
          expect({ where, field, present: field in (schema.properties ?? {}) }).toEqual({ where, field, present: true });
        }
        for (const [name, child] of Object.entries(schema.properties ?? {})) check(child, `${where}.${name}`);
      }
      if (schema.items) check(schema.items, `${where}[]`);
    };
    for (const tool of tools.tools) check(tool.function.parameters as Schema, tool.function.name);
  });

  it("ask for verbatim quotes wherever they ground a theme", () => {
    const theme = tools.tools.find((t) => t.function.name === "generate_narrative_themes")!;
    expect(JSON.stringify(theme)).toContain("verbatim");
  });
});
