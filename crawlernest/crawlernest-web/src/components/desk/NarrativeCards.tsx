import { clampPercent } from "./meter";
import type { NarrativeTheme, Resonance } from "./types";

export function ThemeCard({ title, summary, traits, evidence = [] }: NarrativeTheme) {
  return (
    <article className="relative overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-blue-300">Your narrative thread</p>
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
            <li key={item}>• {item}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export function resonanceTier(level: number): { label: string; fill: string; text: string } {
  if (level >= 75) return { label: "Strong", fill: "bg-emerald-500", text: "text-emerald-700" };
  if (level >= 50) return { label: "Moderate", fill: "bg-blue-500", text: "text-blue-700" };
  return { label: "Emerging", fill: "bg-slate-400", text: "text-slate-600" };
}

export function ResonanceBar({ institution, trait, level, note }: Resonance) {
  const width = clampPercent(level);
  const tier = resonanceTier(width);
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
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(width)}
        aria-valuetext={`${tier.label}, ${Math.round(width)} of 100`}
        className="flex h-2 gap-0.5"
      >
        {/* Five segments read as a level, not a precise measurement. */}
        {[0, 1, 2, 3, 4].map((segment) => {
          const segmentFill = Math.min(1, Math.max(0, width / 20 - segment));
          return (
            <div key={segment} className="relative flex-1 overflow-hidden rounded-sm bg-slate-200">
              <div className={`h-full ${tier.fill}`} style={{ width: `${segmentFill * 100}%` }} />
            </div>
          );
        })}
      </div>
      {note ? <p className="text-xs text-slate-500">{note}</p> : null}
    </div>
  );
}
