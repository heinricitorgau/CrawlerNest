import { clampPercent, toneFor, TONE_FILL } from "./meter";
import type { SkillMastery } from "./types";

interface SkillMasteryBarProps extends SkillMastery {
  focusNext?: boolean;
  /** Shown on the Focus next row as a "Log practice" button. */
  onPractice?: (label: string) => void;
}

export function SkillMasteryBar({ label, percent, focusNext = false, onPractice }: SkillMasteryBarProps) {
  const width = clampPercent(percent);
  return (
    <div className={`rounded-lg px-3 py-2 ${focusNext ? "bg-amber-50 ring-1 ring-amber-200" : ""}`}>
      <div className="mb-1.5 flex items-center justify-between gap-2 text-sm">
        <span className="flex items-center gap-2 font-medium text-slate-800">
          {label}
          {focusNext ? (
            <span className="bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
              Focus next
            </span>
          ) : null}
        </span>
        <span className="flex items-center gap-2">
          {focusNext && onPractice ? (
            <button type="button" onClick={() => onPractice(label)}
              className="rounded-md px-1.5 py-0.5 text-xs font-semibold text-amber-800 hover:bg-amber-100">
              Log practice →
            </button>
          ) : null}
          <span className="tabular-nums text-slate-600">{Math.round(width)}%</span>
        </span>
      </div>
      <div
        role="meter"
        aria-label={`${label} mastery`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(width)}
        className="h-2 w-full overflow-hidden bg-slate-200"
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
  onPractice?: (label: string) => void;
}

export function SkillMasteryList({ skills, highlightWeakest = true, onPractice }: SkillMasteryListProps) {
  const weakest = highlightWeakest && skills.length > 1
    ? skills.reduce((low, skill) => (skill.percent < low.percent ? skill : low)).label
    : null;
  return (
    <div className="space-y-1">
      {skills.map((skill) => (
        <SkillMasteryBar key={skill.label} {...skill} focusNext={skill.label === weakest} onPractice={onPractice} />
      ))}
    </div>
  );
}
