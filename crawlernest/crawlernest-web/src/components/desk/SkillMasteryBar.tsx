import { clampPercent, toneFor, TONE_FILL } from "./meter";
import type { SkillMastery } from "./types";

interface SkillMasteryBarProps extends SkillMastery {
  focusNext?: boolean;
}

export function SkillMasteryBar({ label, percent, focusNext = false }: SkillMasteryBarProps) {
  const width = clampPercent(percent);
  return (
    <div className={`rounded-lg px-3 py-2 ${focusNext ? "bg-amber-50 ring-1 ring-amber-200" : ""}`}>
      <div className="mb-1.5 flex items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-2 font-medium text-slate-800">
          {label}
          {focusNext ? (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-800">
              Focus next
            </span>
          ) : null}
        </span>
        <span className="tabular-nums text-slate-600">{Math.round(width)}%</span>
      </div>
      <div
        role="meter"
        aria-label={`${label} mastery`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(width)}
        className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
      >
        <div
          className={`h-full rounded-full ${TONE_FILL[toneFor(width)]} transition-[width] duration-700 ease-out`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

interface SkillMasteryListProps {
  skills: SkillMastery[];
  /** Mark the weakest skill as "Focus next". On by default. */
  highlightWeakest?: boolean;
}

export function SkillMasteryList({ skills, highlightWeakest = true }: SkillMasteryListProps) {
  const weakest = highlightWeakest && skills.length > 1
    ? skills.reduce((low, skill) => (skill.percent < low.percent ? skill : low)).label
    : null;
  return (
    <div className="space-y-1">
      {skills.map((skill) => (
        <SkillMasteryBar key={skill.label} {...skill} focusNext={skill.label === weakest} />
      ))}
    </div>
  );
}
