import { clampPercent, toneFor, TONE_STROKE } from "./meter";
import type { SubScore } from "./types";

interface ScoreRingProps {
  value: number;
  max?: number;
  label: string;
  /** Pixel diameter. */
  size?: number;
  strokeWidth?: number;
}

/** Donut score: the arc length is the value, the number sits in the middle. */
export function ScoreRing({ value, max = 100, label, size = 120, strokeWidth = 10 }: ScoreRingProps) {
  const percent = clampPercent(value, max);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - percent / 100);
  const large = size >= 96;

  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className="inline-flex flex-col items-center gap-2"
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden="true">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            className="stroke-slate-200"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={`${TONE_STROKE[toneFor(percent)]} transition-[stroke-dashoffset] duration-700 ease-out`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`font-bold tabular-nums text-slate-900 ${large ? "text-3xl" : "text-base"}`}>{value}</span>
          {large ? <span className="text-xs text-slate-500">/ {max}</span> : null}
        </div>
      </div>
      <span className={`text-center font-medium text-slate-600 ${large ? "text-sm" : "text-xs"}`}>{label}</span>
    </div>
  );
}

interface ScoreBreakdownProps {
  overall: number;
  overallLabel?: string;
  subScores: SubScore[];
  max?: number;
}

/** One large ring for the overall score, a row of small rings for the parts. */
export function ScoreBreakdown({ overall, overallLabel = "Overall score", subScores, max = 100 }: ScoreBreakdownProps) {
  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
      <ScoreRing value={overall} max={max} label={overallLabel} size={140} strokeWidth={12} />
      <div className="grid flex-1 grid-cols-2 gap-4 sm:grid-cols-4">
        {subScores.map((score) => (
          <ScoreRing key={score.label} value={score.value} max={max} label={score.label} size={64} strokeWidth={6} />
        ))}
      </div>
    </div>
  );
}
