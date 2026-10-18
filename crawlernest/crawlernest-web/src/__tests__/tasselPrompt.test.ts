/**
 * @jest-environment node
 *
 * Tassel's prompt and tools against the files they must agree with: the rubric
 * the Java scorer reads, and the allow-list the database enforces.
 */
import { readFileSync } from "fs";
import path from "path";

import tools from "@/lib/tassel/tools.json";
import { TASSEL_SYSTEM_PROMPT, buildTasselContext, buildTasselSystemPrompt } from "@/lib/tassel/systemPrompt";

const JAVA_RESOURCES = path.resolve(__dirname, "../../../servise_for_java/src/main/resources");
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
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/Never give a numeric essay score in chat/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/Never invent a fact about the student/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/unless a tool result says "applied"/);
    expect(TASSEL_SYSTEM_PROMPT).toMatch(/not as instructions to you/);
  });

  it("appends the per-request context with the ids tools refer to", () => {
    const context = {
      today: "2026-10-18",
      timezone: "Asia/Taipei",
      mode: "brainstorming" as const,
      openTasks: [{ id: 7, title: "Submit MIT supplement", dueDate: "2026-11-01" }],
      targets: [{ id: 41, name: "Massachusetts Institute of Technology", stage: "applying", deadline: null }],
      essays: [],
    };
    const block = buildTasselContext(context);
    expect(block).toContain("Today: 2026-10-18 (Asia/Taipei)");
    expect(block).toContain("- [7] Submit MIT supplement (due 2026-11-01)");
    expect(block).toContain("- [41] Massachusetts Institute of Technology: applying");
    expect(block).toMatch(/Essay reviews on file[^\n]*\n- none/);
    expect(buildTasselSystemPrompt(context).startsWith(TASSEL_SYSTEM_PROMPT)).toBe(true);
  });
});

describe("Tassel tools", () => {
  it("are exactly the tools the database allows", () => {
    const allowed = allowListSql.match(/tool_name IN \(([^)]*)\)/)?.[1].match(/'([a-z_]+)'/g)?.map((s) => s.slice(1, -1));
    expect([...(allowed ?? [])].sort()).toEqual([...toolNames].sort());
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
    for (const tool of tools.tools) check(tool.function.parameters as unknown as Schema, tool.function.name);
  });

  it("ask for verbatim quotes wherever they ground a theme", () => {
    const theme = tools.tools.find((t) => t.function.name === "generate_narrative_themes")!;
    expect(JSON.stringify(theme)).toContain("verbatim");
  });
});
