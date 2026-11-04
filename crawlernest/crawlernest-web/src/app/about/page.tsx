import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "About | CrawlerNest",
  description:
    "Learn about CrawlerNest — the open-source university ranking intelligence platform structuring global ranking, admission, preview, and agent-ready education data.",
};

// ─── Section wrapper ──────────────────────────────────────────────────────────
function Section({
  children,
  cream = false,
  className = "",
}: {
  children: ReactNode;
  cream?: boolean;
  className?: string;
}) {
  return (
    <section
      className={`py-20 ${cream ? "bg-(--color-paper)" : "bg-white"} ${className}`}
    >
      <div className="mx-auto max-w-6xl px-6">{children}</div>
    </section>
  );
}

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-3xl font-bold tracking-tight text-(--color-ink)">
      {children}
    </h2>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function AboutPage() {
  return (
    <main>

      {/* ── 1. Hero ─────────────────────────────────────────────────────── */}
      <Section cream className="py-28">
        <div className="max-w-3xl">
          {/* Eyebrow */}
          <span className="inline-block border border-(--color-ink-2) px-3 py-1 text-xs text-(--color-ink-2)">
            Open Source · April 2026
          </span>

          {/* Headline */}
          <h1 className="mt-6 text-5xl font-bold leading-tight tracking-tight text-(--color-ink) sm:text-6xl">
            The Missing Data Layer
            <br />
            for Global Education
          </h1>

          {/* Subheadline */}
          <p className="mt-6 max-w-2xl text-lg leading-8 text-(--color-muted)">
            CrawlerNest crawls, normalizes, and warehouses ranking and admission
            data into a shared university intelligence layer — powering rankings,
            preview profiles, recommendations, and an emerging agent interface for
            education search.
          </p>

          {/* Pull quote */}
          <blockquote className="mt-8 border-l-4 border-(--color-ink-2) pl-5 italic text-lg text-(--color-ink)">
            "If Google organizes information, CrawlerNest structures education data."
          </blockquote>

          {/* CTAs */}
          <div className="mt-10 flex flex-wrap gap-4">
            <Link
              href="/"
              className="bg-(--color-ink) px-6 py-3 text-sm font-semibold text-white transition hover:bg-(--color-ink-2)"
            >
              View Rankings
            </Link>
            <a
              href="https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform"
              target="_blank"
              rel="noopener noreferrer"
              className="border border-(--color-rule) px-6 py-3 text-sm font-semibold text-(--color-ink) transition hover:bg-(--color-paper-2)"
            >
              GitHub
            </a>
          </div>
        </div>
      </Section>

      {/* ── 2. Stats Bar ────────────────────────────────────────────────── */}
      <Section>
        <div className="rounded-3xl border border-(--color-rule) bg-white py-8 shadow-sm">
          <div className="grid grid-cols-2 divide-x divide-(--color-rule) md:grid-cols-4">
            {[
              { number: "2,767", label: "Tracked ranking matches" },
              { number: "2026", label: "Current live edition" },
              { number: "Preview + Agent", label: "Product layers" },
              { number: "v3", label: "Decision Engine" },
            ].map((stat) => (
              <div key={stat.label} className="px-8 py-4 text-center">
                <div className="text-3xl font-bold text-(--color-ink)">
                  {stat.number}
                </div>
                <div className="mt-1 text-sm text-(--color-muted)">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── 3. What It Does ─────────────────────────────────────────────── */}
      <Section cream>
        <SectionHeading>From scattered data to decision intelligence</SectionHeading>
        <div className="mt-10 grid gap-12 md:grid-cols-2">
          {/* Left: description */}
          <div className="space-y-5 text-(--color-muted) leading-7">
            <p>
              CrawlerNest replaces manual cross-referencing with a single
              queryable data layer. Instead of browsing QS, THE, and university
              sites separately, students query once and get structured,
              comparable results across rankings, admission signals, and preview
              profiles.
            </p>
            <p>
              The recommendation engine generates explainable reach / target /
              safety groupings, while the preview and agent layers expose the same
              canonical university model through user-facing interfaces.
            </p>
          </div>

          {/* Right: flow diagram */}
          <div className="flex flex-col items-stretch gap-3">
            {[
              { emoji: "📊", label: "Ranking · Admission Sources", sublabel: "QS · THE · university pages" },
              { emoji: "⚙️", label: "CrawlerNest Pipeline", sublabel: "Crawl · Normalize · Resolve · Aggregate" },
              { emoji: "🧭", label: "Preview + Rankings Browser", sublabel: "Queryable product surface" },
              { emoji: "🤖", label: "Web / Dev Agent Layer", sublabel: "Shared intelligence, separate policies" },
            ].map((step, i) => (
              <div key={step.label}>
                <div className="flex items-center gap-4 rounded-2xl border border-(--color-rule) bg-white px-5 py-4 shadow-sm">
                  <span className="text-2xl" aria-hidden="true">{step.emoji}</span>
                  <div>
                    <div className="text-sm font-semibold text-(--color-ink)">{step.label}</div>
                    <div className="text-xs text-(--color-muted)">{step.sublabel}</div>
                  </div>
                </div>
                {i < 3 && (
                  <div className="flex justify-center py-1 text-(--color-rule) text-xl font-light">
                    ↓
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── 4. Current Status ───────────────────────────────────────────── */}
      <Section>
        <SectionHeading>Current Status</SectionHeading>
        <p className="mt-3 text-(--color-muted)">
          The core data pipeline is operational, and the product layer now includes
          rankings, preview profiles, and a first user-facing agent interface.
        </p>
        <div className="mt-8 overflow-hidden rounded-3xl border border-(--color-rule) bg-white shadow-sm">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-(--color-rule) bg-(--color-paper)">
                <th className="px-6 py-4 text-left font-semibold text-(--color-ink)">Module</th>
                <th className="px-6 py-4 text-left font-semibold text-(--color-ink)">Status</th>
                <th className="px-6 py-4 text-left font-semibold text-(--color-ink)">Scale</th>
              </tr>
            </thead>
            <tbody>
              {[
                {
                  module: "Async crawler pipeline",
                  status: "Operational",
                  green: true,
                  scale: "Ranking + admission ingestion",
                },
                {
                  module: "PostgreSQL warehouse",
                  status: "Operational",
                  green: true,
                  scale: "Transaction-safe with rollback",
                },
                {
                  module: "Normalization engine (Python + C)",
                  status: "Operational",
                  green: true,
                  scale: "250,000+ lines · 14/14 tests",
                },
                {
                  module: "Java Spring Boot API",
                  status: "Operational",
                  green: true,
                  scale: "/rankings + preview query surfaces",
                },
                {
                  module: "Recommendation engine (v3)",
                  status: "Operational",
                  green: true,
                  scale: "Reach / Target / Safety",
                },
                {
                  module: "Next.js consumer website",
                  status: "Operational",
                  green: true,
                  scale: "Rankings browser + preview + agent UI",
                },
                {
                  module: "Split agent runtime",
                  status: "Operational",
                  green: true,
                  scale: "Web Agent + Dev Agent with shared core",
                },
              ].map((row, i) => (
                <tr
                  key={row.module}
                  className={i > 0 ? "border-t border-(--color-rule)" : ""}
                >
                  <td className="px-6 py-4 font-medium text-(--color-ink)">
                    {row.module}
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className={`h-2 w-2 ${row.green ? "bg-(--color-ink-2)" : "bg-amber-400"}`}
                        aria-hidden="true"
                      />
                      <span className={row.green ? "text-(--color-ink-2)" : "text-amber-600"}>
                        {row.status}
                      </span>
                    </span>
                  </td>
                  <td className="px-6 py-4 text-(--color-muted)">{row.scale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* ── 5. Architecture ─────────────────────────────────────────────── */}
      <Section cream>
        <SectionHeading>Architecture</SectionHeading>
        <p className="mt-3 text-(--color-muted)">
          A six-layer pipeline from raw web data to rankings, preview, recommendations,
          and agent-driven interactions.
        </p>
        <div className="mt-10 flex flex-col items-stretch gap-3 md:flex-row md:items-center">
          {[
            { num: "01", title: "Data Layer", sub: "Crawlers" },
            { num: "02", title: "Canonical Layer", sub: "Normalization" },
            { num: "03", title: "Aggregation Layer", sub: "PostgreSQL" },
            { num: "04", title: "Decision Layer", sub: "Rec Engine" },
            { num: "05", title: "API & Preview Layer", sub: "Spring Boot + product read models" },
            { num: "06", title: "Agent Layer", sub: "Web Agent + Dev Agent" },
          ].map((layer, i) => (
            <div key={layer.num} className="flex flex-row items-center gap-3 md:flex-1">
              <div className="flex-1 rounded-2xl border border-(--color-rule) bg-white px-4 py-5 shadow-sm">
                <div className="text-xs font-medium text-(--color-muted)">
                  {layer.num}
                </div>
                <div className="mt-1.5 text-sm font-semibold text-(--color-ink)">
                  {layer.title}
                </div>
                <div className="mt-0.5 text-xs text-(--color-muted)">{layer.sub}</div>
              </div>
              {i < 5 && (
                <span className="shrink-0 text-(--color-rule) md:text-base">→</span>
              )}
            </div>
          ))}
        </div>
      </Section>

      {/* ── 6. Tech Stack ───────────────────────────────────────────────── */}
      <Section>
        <SectionHeading>Technology Stack</SectionHeading>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { label: "Crawler", detail: "Python · AsyncIO · compliance-aware throttling" },
            { label: "Normalization", detail: "Python + C hybrid engine" },
            { label: "Storage", detail: "PostgreSQL (transaction-safe)" },
            { label: "Backend API", detail: "Java Spring Boot" },
            { label: "Frontend", detail: "Next.js (React)" },
            { label: "Testing", detail: "PyTest · JUnit · 14/14 tests passing" },
          ].map((tech) => (
            <div
              key={tech.label}
              className="rounded-2xl border border-(--color-rule) bg-white px-5 py-5 shadow-sm"
            >
              <div className="text-sm font-semibold text-(--color-ink)">{tech.label}</div>
              <div className="mt-1.5 text-sm text-(--color-muted)">{tech.detail}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 7. Roadmap ──────────────────────────────────────────────────── */}
      <Section cream>
        <SectionHeading>Roadmap</SectionHeading>
        <div className="mt-10 flex flex-col gap-0">
          {[
            {
              phase: "NOW",
              filled: true,
              items: [
                "Global rankings browser backed by warehouse data",
                "University preview page and preview API",
                "Web Agent + Dev Agent split with shared core",
              ],
            },
            {
              phase: "NEXT 6–18 MONTHS",
              filled: false,
              items: [
                "Conversational agent with stronger intent routing",
                "Recommendation UI integrated into the agent flow",
                "Program-level and deeper admission analytics",
              ],
            },
            {
              phase: "FUTURE",
              filled: false,
              items: [
                "Public API",
                "LLM-assisted data verification",
                "AI consulting and comparative planning workflows",
              ],
            },
          ].map((step, i) => (
            <div key={step.phase} className="flex gap-6">
              {/* Timeline spine */}
              <div className="flex flex-col items-center">
                <div
                  className={`mt-1 h-4 w-4 shrink-0 border-2 ${
                    step.filled
                      ? "border-(--color-ink) bg-(--color-ink)"
                      : "border-(--color-ink-2) bg-transparent"
                  }`}
                />
                {i < 2 && (
                  <div className="w-0.5 flex-1 bg-(--color-paper-2)" style={{ minHeight: "3rem" }} />
                )}
              </div>
              {/* Content */}
              <div className={i < 2 ? "pb-10" : ""}>
                <div className="text-xs font-semibold text-(--color-ink-2)">
                  {step.phase}
                </div>
                <ul className="mt-2 space-y-1">
                  {step.items.map((item) => (
                    <li key={item} className="text-sm text-(--color-muted)">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 8. Team ─────────────────────────────────────────────────────── */}
      <Section>
        <SectionHeading>Built by</SectionHeading>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 max-w-xl">
          {[
            { name: "KAO EN-TSAI", role: "Founder & System Architect" },
            { name: "shika tina", role: "Co-Developer & Data Engineer" },
          ].map((person) => (
            <div
              key={person.name}
              className="rounded-2xl border border-(--color-rule) bg-white px-5 py-5 shadow-sm"
            >
              <div className="text-sm font-semibold text-(--color-ink)">{person.name}</div>
              <div className="mt-1 text-xs text-(--color-muted)">{person.role}</div>
            </div>
          ))}
        </div>
        <p className="mt-6 text-sm text-(--color-muted)">
          Built with AI-assisted development (Claude, ChatGPT, OpenClaw)
        </p>
      </Section>

      {/* ── 9. Footer CTA ───────────────────────────────────────────────── */}
      <Section cream>
        <div className="text-center">
          <h2 className="text-3xl font-bold text-(--color-ink)">Get Involved</h2>
          <p className="mt-3 text-(--color-muted)">
            Open source, open data, open to collaboration.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-6 text-sm">
            <a
              href="https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform"
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-(--color-ink) underline-offset-4 hover:underline"
            >
              GitHub Repository
            </a>
            <span className="text-(--color-rule)" aria-hidden="true">·</span>
            <a
              href="mailto:ek2412045@gmail.com"
              className="font-semibold text-(--color-ink) underline-offset-4 hover:underline"
            >
              ek2412045@gmail.com
            </a>
            <span className="text-(--color-rule)" aria-hidden="true">·</span>
            <span className="font-semibold text-(--color-ink)">Share This Project</span>
          </div>

          {/* License */}
          <div className="mt-12 border-t border-(--color-rule) pt-8">
            <p className="text-xs text-(--color-muted)">
              Licensed under the{" "}
              <a
                href="https://www.apache.org/licenses/LICENSE-2.0"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-(--color-ink-2) underline-offset-4 hover:underline"
              >
                Apache License 2.0
              </a>
              . You may use, modify, and distribute this software in compliance
              with the license terms.
            </p>
          </div>
        </div>
      </Section>

    </main>
  );
}
