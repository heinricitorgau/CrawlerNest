import type { ReactNode } from "react";
import type { NarrativeTheme, Resonance } from "./types";

interface ThemeCardProps extends NarrativeTheme {
  /** "suggested" shows a badge: the theme is the model's proposal until the user accepts it. */
  status?: "suggested" | "accepted";
  /** Accept / dismiss buttons, or anything else the caller wants under the theme. */
  actions?: ReactNode;
}

export function ThemeCard({ title, summary, traits, evidence = [], status, actions }: ThemeCardProps) {
  return (
    <article className="relative overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-blue-300">Your narrative thread</p>
        {status === "suggested" ? (
          <span className="rounded-full bg-amber-300/20 px-2 py-0.5 text-[11px] font-semibold text-amber-200">Suggested</span>
        ) : null}
      </div>
      <h3 className="mt-2 text-xl font-bold leading-snug">&ldquo;{title}&rdquo;</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-300">{summary}</p>
      {traits.length > 0 ? (
        <ul className="mt-4 flex flex-wrap gap-2" aria-label="Traits">
          {traits.map((trait) => (
            <li key={trait} className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-100">
              {trait}
            </li>
          ))}
        </ul>
      ) : null}
      {evidence.length > 0 ? (
        <ul className="mt-4 space-y-1 border-t border-white/10 pt-3 text-xs text-slate-400" aria-label="Evidence">
          {evidence.map((item) => (
            <li key={item}>&ldquo;{item}&rdquo;</li>
          ))}
        </ul>
      ) : null}
      {actions ? <div className="mt-4 flex flex-wrap gap-2">{actions}</div> : null}
    </article>
  );
}

/** The words for a 1-5 resonance level; the same cut the API's levelLabel makes. */
export function resonanceTier(level: number): { label: string; fill: string; text: string } {
  if (level >= 4) return { label: "Strong", fill: "bg-emerald-500", text: "text-emerald-700" };
  if (level === 3) return { label: "Moderate", fill: "bg-blue-500", text: "text-blue-700" };
  return { label: "Emerging", fill: "bg-slate-400", text: "text-slate-600" };
}

/**
 * A 1-5 resonance level as five segments. Deliberately not a percentage: the
 * model can say one fit is stronger than another, not by how many points.
 */
export function ResonanceBar({ institution, trait, level, note }: Resonance) {
  const filled = Math.min(5, Math.max(0, Math.round(level)));
  const tier = resonanceTier(filled);
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-slate-800">
          <span className="font-semibold">{trait}</span>
          <span className="text-slate-500"> × {institution}</span>
        </span>
        <span className={`text-xs font-semibold ${tier.text}`}>{tier.label}</span>
      </div>
      <div
        role="meter"
        aria-label={`${trait} resonance with ${institution}`}
        aria-valuemin={1}
        aria-valuemax={5}
        aria-valuenow={filled}
        aria-valuetext={`${tier.label}, level ${filled} of 5`}
        className="flex h-2 gap-0.5"
      >
        {[1, 2, 3, 4, 5].map((segment) => (
          <div key={segment} className={`flex-1 rounded-sm ${segment <= filled ? tier.fill : "bg-slate-200"}`} />
        ))}
      </div>
      {note ? <p className="text-xs text-slate-500">{note}</p> : null}
    </div>
  );
}
