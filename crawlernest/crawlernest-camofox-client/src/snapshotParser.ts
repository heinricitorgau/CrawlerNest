/**
 * Turns a Camofox snapshot into a CrawlPage.
 *
 * The snapshot text is Playwright's aria-snapshot YAML, one element per line,
 * nested by two-space indentation. Camofox inserts the element ref right after
 * the accessible name:
 *
 *   - heading "QS World University Rankings" [level=1]
 *   - link "Next page" [e14]:
 *     - /url: https://example.org/?page=2
 *   - textbox "Search" [e3]: current value
 *   - paragraph: Some text
 *   - table "Rankings":
 *     - row "Rank University":
 *       - columnheader "Rank"
 *
 * A truncated snapshot carries a "[... truncated at char N of M ...]" marker
 * line; it is skipped here and reported through `completeness`.
 */
import type {
  CrawlPage,
  InteractiveElement,
  PageHeading,
  PageLink,
  PageNode,
  PageTable,
  SnapshotResponse,
} from './types.js';

const TRUNCATION_MARKER = /^\[\.\.\. truncated at char \d+ of \d+\./;
const REF = /^e\d+$/;
const VALUE_ROLES = new Set(['textbox', 'searchbox', 'combobox', 'spinbutton', 'slider']);
const TEXT_ROLES = new Set(['paragraph', 'text', 'listitem', 'blockquote', 'caption', 'note', 'term', 'definition', 'cite']);
const TABLE_ROLES = new Set(['table', 'grid', 'treegrid']);
const CELL_ROLES = new Set(['cell', 'gridcell', 'columnheader', 'rowheader']);

export interface ParsedAriaSnapshot {
  tree: PageNode[];
  warnings: string[];
}

/** Parse the snapshot YAML into a node tree. Never throws; unreadable lines become warnings. */
export function parseAriaSnapshot(text: string): ParsedAriaSnapshot {
  const tree: PageNode[] = [];
  const warnings: string[] = [];
  const stack: { indent: number; node: PageNode }[] = [];

  for (const [index, line] of text.split('\n').entries()) {
    if (!line.trim() || TRUNCATION_MARKER.test(line.trim())) continue;
    const match = /^(\s*)-\s?(.*)$/.exec(line);
    if (!match) {
      warnings.push(`line ${index + 1}: not a list item: ${line.slice(0, 120)}`);
      continue;
    }
    const indent = match[1].length;
    const content = match[2];
    while (stack.length && stack[stack.length - 1].indent >= indent) stack.pop();
    const parent = stack.length ? stack[stack.length - 1].node : null;

    if (content.startsWith('/')) {
      const prop = /^\/([\w-]+):\s?(.*)$/.exec(content);
      if (prop && parent) parent.props[prop[1]] = unquote(prop[2].trim());
      else warnings.push(`line ${index + 1}: property without an element: ${line.slice(0, 120)}`);
      continue;
    }

    const node = parseEntry(content);
    if (!node) {
      warnings.push(`line ${index + 1}: unreadable element: ${line.slice(0, 120)}`);
      continue;
    }
    (parent ? parent.children : tree).push(node);
    stack.push({ indent, node });
  }
  return { tree, warnings };
}

/** Parse one entry: `role "name" [attr] [e1]: inline text`, possibly wrapped in single quotes. */
function parseEntry(content: string): PageNode | null {
  let key = content;
  let rest = '';
  if (content.startsWith("'")) {
    // YAML single-quoted key; '' is an escaped quote.
    let i = 1;
    let unwrapped = '';
    for (; i < content.length; i += 1) {
      if (content[i] === "'") {
        if (content[i + 1] === "'") {
          unwrapped += "'";
          i += 1;
          continue;
        }
        break;
      }
      unwrapped += content[i];
    }
    if (i >= content.length) return null;
    key = unwrapped;
    rest = content.slice(i + 1);
  }

  const cursor = { pos: 0 };
  const role = /^[A-Za-z][\w-]*/.exec(key)?.[0];
  if (!role) return null;
  cursor.pos = role.length;

  const node: PageNode = { role, name: null, ref: null, attributes: {}, text: null, props: {}, children: [] };

  skipSpaces(key, cursor);
  if (key[cursor.pos] === '"') {
    const name = readDoubleQuoted(key, cursor);
    if (name === null) return null;
    node.name = name;
  }

  for (skipSpaces(key, cursor); key[cursor.pos] === '['; skipSpaces(key, cursor)) {
    const end = key.indexOf(']', cursor.pos);
    if (end < 0) return null;
    const attribute = key.slice(cursor.pos + 1, end).trim();
    cursor.pos = end + 1;
    const eq = attribute.indexOf('=');
    const attrKey = eq < 0 ? attribute : attribute.slice(0, eq);
    const attrValue = eq < 0 ? true : attribute.slice(eq + 1);
    if (REF.test(attribute)) node.ref = attribute;
    else if (attrKey === 'ref' && typeof attrValue === 'string') node.ref = attrValue;
    else node.attributes[attrKey] = attrValue;
  }

  rest = (key.slice(cursor.pos) + rest).trim();
  if (rest.startsWith(':')) {
    const inline = rest.slice(1).trim();
    if (inline) node.text = unquote(inline);
  } else if (rest) {
    return null;
  }
  return node;
}

function skipSpaces(text: string, cursor: { pos: number }): void {
  while (text[cursor.pos] === ' ') cursor.pos += 1;
}

function readDoubleQuoted(text: string, cursor: { pos: number }): string | null {
  let i = cursor.pos + 1;
  for (; i < text.length; i += 1) {
    if (text[i] === '\\') i += 1;
    else if (text[i] === '"') break;
  }
  if (i >= text.length) return null;
  const literal = text.slice(cursor.pos, i + 1);
  cursor.pos = i + 1;
  try {
    return JSON.parse(literal) as string;
  } catch {
    return literal.slice(1, -1);
  }
}

/** Strip YAML quoting from an inline value; plain values are returned as-is. */
function unquote(value: string): string {
  if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
    try {
      return JSON.parse(value) as string;
    } catch {
      return value.slice(1, -1);
    }
  }
  if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
    return value.slice(1, -1).replace(/''/g, "'");
  }
  return value;
}

/** Visible text of a node: its name, else its inline text, else its children's text. */
export function nodeText(node: PageNode): string {
  if (node.name) return node.name;
  if (node.text) return node.text;
  return node.children.map(nodeText).filter(Boolean).join(' ').trim();
}

export interface ParseSnapshotOptions {
  /** Defaults to now. */
  capturedAt?: Date;
}

/** Convert a GET /tabs/:id/snapshot response into the CrawlerNest page format. */
export function parseSnapshot(response: SnapshotResponse, options: ParseSnapshotOptions = {}): CrawlPage {
  const { tree, warnings } = parseAriaSnapshot(response.snapshot ?? '');
  const truncated = Boolean(response.truncated);

  const headings: PageHeading[] = [];
  const links: PageLink[] = [];
  const interactive: InteractiveElement[] = [];
  const textBlocks: string[] = [];
  const ariaTables: PageTable[] = [];

  const visit = (node: PageNode, inTable: boolean): void => {
    if (node.role === 'heading') {
      const level = typeof node.attributes.level === 'string' ? Number.parseInt(node.attributes.level, 10) : NaN;
      headings.push({ level: Number.isFinite(level) ? level : null, text: nodeText(node) });
    }
    if (node.role === 'link') {
      links.push({ text: nodeText(node), href: node.props.url ?? null, ref: node.ref });
    }
    if (node.ref) {
      interactive.push({
        ref: node.ref,
        role: node.role,
        name: node.name,
        value: VALUE_ROLES.has(node.role) ? node.text : null,
        states: { ...node.attributes },
      });
    }
    if (!inTable && TEXT_ROLES.has(node.role) && node.text) textBlocks.push(node.text);
    if (TABLE_ROLES.has(node.role)) ariaTables.push(tableFromNode(node, truncated));

    const childInTable = inTable || TABLE_ROLES.has(node.role);
    for (const child of node.children) visit(child, childInTable);
  };
  for (const node of tree) visit(node, false);

  const domTables: PageTable[] = (response.structure?.tables ?? []).map((table) => ({
    origin: 'dom',
    label: table.label ?? null,
    headers: table.headers,
    rows: table.rows,
    rowsTruncated: table.rowsTruncated,
  }));

  return {
    source: 'camofox',
    url: response.url,
    capturedAt: (options.capturedAt ?? new Date()).toISOString(),
    primaryHeading: (headings.find((h) => h.level === 1) ?? headings[0])?.text ?? null,
    headings,
    links,
    interactive,
    textBlocks,
    // The DOM summary reads <table> elements directly, so prefer it; the aria
    // tree is the fallback for role="grid" widgets and the SERP fast path.
    tables: domTables.length ? domTables : ariaTables,
    forms: response.structure?.forms ?? [],
    completeness: {
      truncated,
      totalChars: response.totalChars ?? (response.snapshot ?? '').length,
      hasMore: Boolean(response.hasMore),
      nextOffset: response.nextOffset ?? null,
    },
    screenshot: response.screenshot ?? null,
    tree,
    warnings,
  };
}

function tableFromNode(table: PageNode, snapshotTruncated: boolean): PageTable {
  const rows: PageNode[] = [];
  const collect = (node: PageNode): void => {
    for (const child of node.children) {
      if (child.role === 'row') rows.push(child);
      else if (!TABLE_ROLES.has(child.role)) collect(child); // rowgroups; nested tables are their own
    }
  };
  collect(table);

  let headers: string[] = [];
  const body: string[][] = [];
  for (const row of rows) {
    const cells = row.children.filter((c) => CELL_ROLES.has(c.role));
    if (!cells.length) continue;
    const values = cells.map(nodeText);
    if (!headers.length && !body.length && cells.every((c) => c.role === 'columnheader')) headers = values;
    else body.push(values);
  }
  return { origin: 'aria', label: table.name, headers, rows: body, rowsTruncated: snapshotTruncated };
}
