import { daysUntil, formatShortDate } from "./meter";

export interface Deadline {
  id: string;
  name: string;
  /** ISO date. The user's own deadline for this school, not a published one. */
  date: string;
  detail?: string;
}

/**
 * Application deadlines, soonest first, with the same near/overdue colouring as
 * tasks. Read-only: a deadline is a fact about a school on the user's list, not
 * something to tick off.
 */
export function DeadlineList({ deadlines, today }: { deadlines: Deadline[]; today: Date }) {
  const ordered = [...deadlines].sort((a, b) => a.date.localeCompare(b.date));
  return (
    <ul className="space-y-1.5" aria-label="Application deadlines">
      {ordered.map((d) => {
        const days = daysUntil(d.date, today);
        const tone = days < 0 ? "bg-red-100 text-red-700" : days <= 14 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600";
        const when = days < 0 ? `${-days}d ago` : days === 0 ? "Today" : `${days}d`;
        return (
          <li key={d.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2 text-sm">
            <div className="min-w-0">
              <p className="truncate font-medium text-slate-800">{d.name}</p>
              {d.detail ? <p className="truncate text-xs text-slate-500">{d.detail}</p> : null}
            </div>
            <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-medium tabular-nums ${tone}`}>
              {formatShortDate(d.date)} · {when}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
