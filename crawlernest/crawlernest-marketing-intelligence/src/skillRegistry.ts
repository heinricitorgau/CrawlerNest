import { readFile } from 'node:fs/promises';
import path from 'node:path';

import type { LoadedSkill, SkillDefinition, SkillLibrary } from './types.js';

/** The `skills/` folder of each library. */
export type SkillRoots = Record<SkillLibrary, string>;

/** Where the two libraries sit in this repository (`notfair-plugin/` and `claude-ads/` at the top level). */
export function defaultSkillRoots(repoRoot: string): SkillRoots {
  return {
    notfair: path.join(repoRoot, 'notfair-plugin', 'skills'),
    'claude-ads': path.join(repoRoot, 'claude-ads', 'skills'),
  };
}

export class SkillNotFoundError extends Error {
  readonly skillId: string;
  readonly path: string;

  constructor(skillId: string, filePath: string, reason: string) {
    super(`Skill ${skillId} could not be loaded from ${filePath}: ${reason}`);
    this.name = 'SkillNotFoundError';
    this.skillId = skillId;
    this.path = filePath;
  }
}

/** The `key: value` pairs of a SKILL.md frontmatter, including quoted and `>` folded values. */
export function parseFrontmatter(text: string): { fields: Record<string, string>; body: string } {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(text);
  if (!match) return { fields: {}, body: text };
  const fields: Record<string, string> = {};
  let current: string | null = null;
  for (const line of match[1].split(/\r?\n/)) {
    const field = /^([A-Za-z][\w-]*):\s*(.*)$/.exec(line);
    if (field) {
      current = field[1];
      const value = field[2].trim();
      fields[current] = /^[>|][-+]?$/.test(value) ? '' : value.replace(/^(["'])(.*)\1$/, '$2');
    } else if (current && /^\s+\S/.test(line)) {
      fields[current] = `${fields[current]} ${line.trim()}`.trim();
    }
  }
  return { fields, body: text.slice(match[0].length) };
}

/**
 * Reads SKILL.md files for routed tasks. Skill text is loaded as instructions for the
 * runner and never executed here.
 */
export class SkillRegistry {
  private readonly cache = new Map<string, LoadedSkill>();

  constructor(private readonly roots: SkillRoots) {}

  pathFor(definition: SkillDefinition): string {
    return path.join(this.roots[definition.library], definition.skillName, 'SKILL.md');
  }

  async load(definition: SkillDefinition): Promise<LoadedSkill> {
    const cached = this.cache.get(definition.id);
    if (cached) return cached;

    const filePath = this.pathFor(definition);
    let text: string;
    try {
      text = await readFile(filePath, 'utf8');
    } catch (error) {
      throw new SkillNotFoundError(definition.id, filePath, (error as NodeJS.ErrnoException).code ?? String(error));
    }
    const { fields, body } = parseFrontmatter(text);
    // A renamed or swapped skill directory should fail loudly, not route to the wrong instructions.
    if (fields.name !== definition.skillName) {
      throw new SkillNotFoundError(
        definition.id,
        filePath,
        `frontmatter name is ${JSON.stringify(fields.name ?? null)}, expected "${definition.skillName}"`,
      );
    }
    const skill: LoadedSkill = {
      definition,
      path: filePath,
      name: fields.name,
      description: fields.description ?? '',
      instructions: body.trim(),
    };
    this.cache.set(definition.id, skill);
    return skill;
  }
}
