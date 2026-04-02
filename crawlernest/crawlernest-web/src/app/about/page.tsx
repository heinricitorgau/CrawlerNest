import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About | CrawlerNest",
  description: "Learn about CrawlerNest — the open-source university ranking intelligence platform aggregating QS and THE data for 2,736+ institutions.",
};

// ─── Section wrapper ──────────────────────────────────────────────────────────
function Section({
  children,
  cream = false,
  className = "",
}: {
  children: React.ReactNode;
  cream?: boolean;
  className?: string;
}) {
  return (
    <section
      className={`py-20 ${cream ? "bg-[#f5f3ee]" : "bg-white"} ${className}`}
    >
      <div className="mx-auto max-w-6xl px-6">{children}</div>
    </section>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-3xl font-bold tracking-tight text-[#1a3d2e]">
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
          <span className="inline-block rounded-full border border-[#3d7a5a] px-3 py-1 text-xs text-[#3d7a5a]">
            Open Source · March 2026
          </span>

          {/* Headline */}
          <h1 className="mt-6 text-5xl font-bold leading-tight tracking-tight text-[#1a3d2e] sm:text-6xl">
            The Missing Data Layer
            <br />
            for Global Education
          </h1>

          {/* Subheadline */}
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[#6b7068]">
            CrawlerNest crawls, normalizes, and warehouses ranking and admission
            data from 1,500+ universities — powering a deterministic
            recommendation engine that helps students make data-driven choices.
          </p>

          {/* Pull quote */}
          <blockquote className="mt-8 border-l-4 border-[#3d7a5a] pl-5 italic text-lg text-[#1a3d2e]">
            "If Google organizes information, CrawlerNest structures education data."
          </blockquote>

          {/* CTAs */}
          <div className="mt-10 flex flex-wrap gap-4">
            <Link
              href="/"
              className="rounded-full bg-[#1a3d2e] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
            >
              View Rankings
            </Link>
            <a
              href="https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full border border-[#e0ddd8] px-6 py-3 text-sm font-semibold text-[#1a3d2e] transition hover:bg-[#e8f2ec]"
            >
              GitHub
            </a>
          </div>
        </div>
      </Section>

      {/* ── 2. Stats Bar ────────────────────────────────────────────────── */}
      <Section>
        <div className="rounded-3xl border border-[#e0ddd8] bg-white py-8 shadow-sm">
          <div className="grid grid-cols-2 divide-x divide-[#e0ddd8] md:grid-cols-4">
            {[
              { number: "1,500+", label: "Universities" },
              { number: "31", label: "Countries" },
              { number: "2", label: "Ranking Sources" },
              { number: "v3", label: "Decision Engine" },
            ].map((stat) => (
              <div key={stat.label} className="px-8 py-4 text-center">
                <div className="text-3xl font-bold text-[#1a3d2e]">
                  {stat.number}
                </div>
                <div className="mt-1 text-sm text-[#6b7068]">{stat.label}</div>
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
          <div className="space-y-5 text-[#6b7068] leading-7">
            <p>
              CrawlerNest replaces manual cross-referencing with a single
              queryable data layer. Instead of browsing QS, THE, and university
              sites separately, students query once and get structured,
              comparable results.
            </p>
            <p>
              The recommendation engine generates explainable reach / target /
              safety groupings — replacing expensive consulting with transparent,
              data-driven guidance.
            </p>
          </div>

          {/* Right: flow diagram */}
          <div className="flex flex-col items-stretch gap-3">
            {[
              { emoji: "📊", label: "QS Rankings · THE Rankings", sublabel: "Source data" },
              { emoji: "⚙️", label: "CrawlerNest Pipeline", sublabel: "Crawl · Normalize · Aggregate" },
              { emoji: "🎯", label: "Reach / Target / Safety", sublabel: "Decision output" },
            ].map((step, i) => (
              <div key={step.label}>
                <div className="flex items-center gap-4 rounded-2xl border border-[#e0ddd8] bg-white px-5 py-4 shadow-sm">
                  <span className="text-2xl" aria-hidden="true">{step.emoji}</span>
                  <div>
                    <div className="text-sm font-semibold text-[#1a3d2e]">{step.label}</div>
                    <div className="text-xs text-[#6b7068]">{step.sublabel}</div>
                  </div>
                </div>
                {i < 2 && (
                  <div className="flex justify-center py-1 text-[#e0ddd8] text-xl font-light">
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
        <p className="mt-3 text-[#6b7068]">All core modules are operational.</p>
        <div className="mt-8 overflow-hidden rounded-3xl border border-[#e0ddd8] bg-white shadow-sm">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[#e0ddd8] bg-[#f5f3ee]">
                <th className="px-6 py-4 text-left font-semibold text-[#1a3d2e]">Module</th>
                <th className="px-6 py-4 text-left font-semibold text-[#1a3d2e]">Status</th>
                <th className="px-6 py-4 text-left font-semibold text-[#1a3d2e]">Scale</th>
              </tr>
            </thead>
            <tbody>
              {[
                {
                  module: "Async crawler pipeline",
                  status: "Operational",
                  green: true,
                  scale: "1,500+ universities",
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
                  scale: "/universities /rankings /admissions",
                },
                {
                  module: "Recommendation engine (v3)",
                  status: "Operational",
                  green: true,
                  scale: "Reach / Target / Safety",
                },
                {
                  module: "Next.js consumer website",
                  status: "In Progress",
                  green: false,
                  scale: "Rankings browser + recommendation UI",
                },
              ].map((row, i) => (
                <tr
                  key={row.module}
                  className={i > 0 ? "border-t border-[#e0ddd8]" : ""}
                >
                  <td className="px-6 py-4 font-medium text-[#1a1a1a]">
                    {row.module}
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-2">
                      <span
                        className={`h-2 w-2 rounded-full ${row.green ? "bg-[#3d7a5a]" : "bg-amber-400"}`}
                        aria-hidden="true"
                      />
                      <span className={row.green ? "text-[#3d7a5a]" : "text-amber-600"}>
                        {row.status}
                      </span>
                    </span>
                  </td>
                  <td className="px-6 py-4 text-[#6b7068]">{row.scale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* ── 5. Architecture ─────────────────────────────────────────────── */}
      <Section cream>
        <SectionHeading>Architecture</SectionHeading>
        <p className="mt-3 text-[#6b7068]">A five-layer pipeline from raw web data to student decision.</p>
        <div className="mt-10 flex flex-col items-stretch gap-3 md:flex-row md:items-center">
          {[
            { num: "01", title: "Data Layer", sub: "Crawlers" },
            { num: "02", title: "Canonical Layer", sub: "Normalization" },
            { num: "03", title: "Aggregation Layer", sub: "PostgreSQL" },
            { num: "04", title: "Decision Layer", sub: "Rec Engine" },
            { num: "05", title: "API & Product", sub: "Spring Boot + Next.js" },
          ].map((layer, i) => (
            <div key={layer.num} className="flex flex-row items-center gap-3 md:flex-1">
              <div className="flex-1 rounded-2xl border border-[#e0ddd8] bg-white px-4 py-5 shadow-sm">
                <div className="text-xs font-medium tracking-widest text-[#6b7068]">
                  {layer.num}
                </div>
                <div className="mt-1.5 text-sm font-semibold text-[#1a3d2e]">
                  {layer.title}
                </div>
                <div className="mt-0.5 text-xs text-[#6b7068]">{layer.sub}</div>
              </div>
              {i < 4 && (
                <span className="shrink-0 text-[#c0bdb8] md:text-base">→</span>
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
              className="rounded-2xl border border-[#e0ddd8] bg-white px-5 py-5 shadow-sm"
            >
              <div className="text-sm font-semibold text-[#1a3d2e]">{tech.label}</div>
              <div className="mt-1.5 text-sm text-[#6b7068]">{tech.detail}</div>
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
                "Web platform MVP",
                "Expanded regional coverage",
                "AutoEval integration",
              ],
            },
            {
              phase: "NEXT 6–18 MONTHS",
              filled: false,
              items: [
                "THE + ARWU ranking sources",
                "Program-level analytics",
                "Entity resolution",
              ],
            },
            {
              phase: "FUTURE",
              filled: false,
              items: [
                "Public API",
                "LLM-assisted data verification",
                "AI consulting insights",
              ],
            },
          ].map((step, i) => (
            <div key={step.phase} className="flex gap-6">
              {/* Timeline spine */}
              <div className="flex flex-col items-center">
                <div
                  className={`mt-1 h-4 w-4 shrink-0 rounded-full border-2 ${
                    step.filled
                      ? "border-[#1a3d2e] bg-[#1a3d2e]"
                      : "border-[#3d7a5a] bg-transparent"
                  }`}
                />
                {i < 2 && (
                  <div className="w-0.5 flex-1 bg-[#e0ddd8]" style={{ minHeight: "3rem" }} />
                )}
              </div>
              {/* Content */}
              <div className={i < 2 ? "pb-10" : ""}>
                <div className="text-xs font-semibold uppercase tracking-widest text-[#3d7a5a]">
                  {step.phase}
                </div>
                <ul className="mt-2 space-y-1">
                  {step.items.map((item) => (
                    <li key={item} className="text-sm text-[#6b7068]">
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
              className="rounded-2xl border border-[#e0ddd8] bg-white px-5 py-5 shadow-sm"
            >
              <div className="text-sm font-semibold text-[#1a3d2e]">{person.name}</div>
              <div className="mt-1 text-xs text-[#6b7068]">{person.role}</div>
            </div>
          ))}
        </div>
        <p className="mt-6 text-sm text-[#6b7068]">
          Built with AI-assisted development (Claude, ChatGPT, OpenClaw)
        </p>
      </Section>

      {/* ── 9. Footer CTA ───────────────────────────────────────────────── */}
      <Section cream>
        <div className="text-center">
          <h2 className="text-3xl font-bold text-[#1a3d2e]">Get Involved</h2>
          <p className="mt-3 text-[#6b7068]">
            Open source, open data, open to collaboration.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-6 text-sm">
            <a
              href="https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform"
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-[#1a3d2e] underline-offset-4 hover:underline"
            >
              GitHub Repository
            </a>
            <span className="text-[#e0ddd8]" aria-hidden="true">·</span>
            <a
              href="mailto:ek2412045@gmail.com"
              className="font-semibold text-[#1a3d2e] underline-offset-4 hover:underline"
            >
              ek2412045@gmail.com
            </a>
            <span className="text-[#e0ddd8]" aria-hidden="true">·</span>
            <span className="font-semibold text-[#1a3d2e]">Share This Project</span>
          </div>

          {/* License */}
          <div className="mt-12 border-t border-[#e0ddd8] pt-8">
            <p className="text-xs text-[#6b7068]">
              Licensed under the{" "}
              <a
                href="https://www.apache.org/licenses/LICENSE-2.0"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-[#3d7a5a] underline-offset-4 hover:underline"
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
