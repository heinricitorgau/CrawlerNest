import { CaveatBanner } from "@/components/CaveatBanner";
import type { UsFederalMetric, UsInstitution } from "@/types/university";

/**
 * A US university's College Scorecard and IPEDS figures.
 *
 * Every value is shown with its own reference period, because they differ by a decade
 * (an admission rate is one fall; earnings follow a cohort that entered years earlier).
 * A value without a figure says why -- withheld for privacy, not in the file -- and is
 * never drawn as zero. The caveats are the API's, rendered verbatim.
 */
type UsFederalDataProps = { data: UsInstitution };

type Row = { key: string; label: string; metrics: UsFederalMetric[] };

const GROUPS: { title: string; rows: { label: string; keys: string[] }[] }[] = [
  {
    title: "Admissions",
    rows: [
      { label: "Admission rate", keys: ["admission_rate"] },
      { label: "Applicants", keys: ["applicants_total"] },
      { label: "Admitted", keys: ["admitted_total"] },
      { label: "Enrolled first-year students", keys: ["enrolled_first_year_total"] },
      { label: "Test scores", keys: ["test_score_policy"] },
      { label: "SAT reading, 25th–75th percentile", keys: ["sat_reading_25", "sat_reading_75"] },
      { label: "SAT math, 25th–75th percentile", keys: ["sat_math_25", "sat_math_75"] },
      { label: "ACT composite, 25th–75th percentile", keys: ["act_composite_25", "act_composite_75"] },
      { label: "Entrants submitting SAT scores", keys: ["sat_submitters_percent"] },
      { label: "Entrants submitting ACT scores", keys: ["act_submitters_percent"] },
    ],
  },
  {
    title: "Cost",
    rows: [
      { label: "Average cost of attendance", keys: ["cost_of_attendance"] },
      { label: "Tuition and fees, in-state", keys: ["tuition_in_state"] },
      { label: "Tuition and fees, out-of-state", keys: ["tuition_out_of_state"] },
      { label: "Average net price", keys: ["average_net_price"] },
      { label: "Undergraduates receiving a Pell Grant", keys: ["pell_share"] },
    ],
  },
  {
    title: "Outcomes",
    rows: [
      { label: "Completion rate (four-year, within 150% time)", keys: ["completion_rate_4yr"] },
      { label: "First-year retention rate", keys: ["retention_rate_4yr"] },
      { label: "Median earnings 10 years after entry", keys: ["median_earnings_10yr"] },
      { label: "Median debt of completers", keys: ["median_debt_completers"] },
    ],
  },
  {
    title: "Enrollment and institution",
    rows: [
      { label: "Undergraduate enrollment", keys: ["undergraduate_enrollment"] },
      { label: "12-month enrollment, all students", keys: ["total_enrollment_12mo"] },
      { label: "12-month enrollment, graduate", keys: ["graduate_enrollment_12mo"] },
      { label: "Control", keys: ["control"] },
      { label: "Part of", keys: ["system_name"] },
      { label: "Carnegie Classification (2021 basic)", keys: ["carnegie_basic_2021"] },
      { label: "Carnegie research designation (2025)", keys: ["carnegie_research_2025"] },
    ],
  },
];

const SOURCE_SHORT: Record<string, string> = { COLLEGE_SCORECARD: "College Scorecard", IPEDS: "IPEDS" };

function hasFigure(metric: UsFederalMetric): boolean {
  return metric.status === "reported" || metric.status === "imputed";
}

/** A figure in its unit. Fixed locale: the server renders this. */
export function formatFigure(metric: UsFederalMetric): string {
  if (metric.unit === "code" || metric.unit === "text") return metric.valueText ?? String(metric.value ?? "");
  const value = metric.value;
  if (value == null) return "";
  switch (metric.unit) {
    case "ratio":
      return `${(value * 100).toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
    case "percent":
      return `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
    case "usd":
      return `$${Math.round(value).toLocaleString("en-US")}`;
    default:
      return value.toLocaleString("en-US");
  }
}

/** What a value with no figure shows instead. Never a zero, never a dash that reads as one. */
export function statusText(metric: UsFederalMetric): string {
  switch (metric.status) {
    case "privacy_suppressed":
      return "Withheld by the source for privacy";
    case "not_applicable":
      return "Not applicable";
    default:
      return "Not available";
  }
}

function Value({ metric }: { metric: UsFederalMetric }) {
  if (!hasFigure(metric)) {
    return (
      <span className="italic text-slate-500" title={metric.statusDetail ?? undefined}>
        {statusText(metric)}
      </span>
    );
  }
  return (
    <span className="font-semibold text-slate-900">
      {formatFigure(metric)}
      {metric.status === "imputed" ? (
        <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-bold text-amber-800 ring-1 ring-amber-200"
          title={metric.statusDetail ?? undefined}>
          NCES estimate
        </span>
      ) : null}
    </span>
  );
}

function RowValue({ row }: { row: Row }) {
  const [low, high] = row.metrics;
  // A 25th–75th pair reads as one range when both ends are figures; otherwise each end says what it is.
  if (row.metrics.length === 2 && hasFigure(low) && hasFigure(high) && low.status === high.status) {
    return (
      <span className="font-semibold text-slate-900">
        {formatFigure(low)}–{formatFigure(high)}
        {low.status === "imputed" ? <span className="ml-2 text-[10px] font-bold text-amber-800">NCES estimate</span> : null}
      </span>
    );
  }
  if (row.metrics.length === 2) {
    return (
      <span className="space-x-2">
        <Value metric={low} /> <span className="text-slate-400">to</span> <Value metric={high} />
      </span>
    );
  }
  return <Value metric={low} />;
}

function rowsFor(byKey: Map<string, UsFederalMetric>, keys: string[], label: string): Row | null {
  const metrics = keys.map((key) => byKey.get(key)).filter((m): m is UsFederalMetric => m !== undefined);
  if (metrics.length !== keys.length) return null;
  // "Not applicable" says nothing about the institution worth a line (a standalone college has no system).
  if (metrics.every((m) => m.status === "not_applicable")) return null;
  return { key: keys.join("+"), label, metrics };
}

export function UsFederalData({ data }: UsFederalDataProps) {
  const byKey = new Map(data.metrics.map((metric) => [metric.key, metric]));
  const place = [data.city, data.stateCode].filter(Boolean).join(", ");

  return (
    <div className="space-y-6">
      {GROUPS.map((group) => {
        const rows = group.rows
          .map((row) => rowsFor(byKey, row.keys, row.label))
          .filter((row): row is Row => row !== null);
        if (rows.length === 0) return null;
        return (
          <div key={group.title}>
            <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">{group.title}</h3>
            <dl className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {rows.map((row) => (
                <div key={row.key} className="grid grid-cols-1 gap-1 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:gap-4">
                  <dt className="text-sm text-slate-700">{row.label}</dt>
                  <dd className="text-sm">
                    <RowValue row={row} />
                    <div className="mt-0.5 text-[11px] leading-4 text-slate-400 [overflow-wrap:anywhere]">
                      {SOURCE_SHORT[row.metrics[0].source] ?? row.metrics[0].source} · {row.metrics[0].referencePeriod}
                    </div>
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        );
      })}

      <CaveatBanner caveats={data.caveats} title="About these figures" />

      <p className="text-xs leading-5 text-slate-500">
        Federal record: {data.institutionName}
        {place ? ` (${place})` : ""}, IPEDS UNITID {data.unitid}. Sources:{" "}
        {data.sources.map((source, index) => (
          <span key={source.code}>
            {index > 0 ? "; " : ""}
            <a href={source.url} className="underline hover:text-blue-700" rel="noopener noreferrer" target="_blank">
              {source.name}
            </a>{" "}
            ({source.publisher})
          </span>
        ))}
        . {data.sources[0]?.license ?? ""}.
      </p>
    </div>
  );
}
