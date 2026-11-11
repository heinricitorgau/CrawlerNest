import { CaveatBanner } from "@/components/CaveatBanner";

/**
 * The recommendation list's US federal filters (College Scorecard / IPEDS): a cap on average net price and a
 * minimum admission rate.
 *
 * Filters only. The API applies them before scoring and they change no score, rank or confidence; a university
 * without the figure is left out and counted, never treated as passing. They are offered only while the country
 * is the United States, because the list is already limited to the chosen country and no university elsewhere
 * has these figures: a cap there would empty the list.
 */

export type UsFederalFilterValues = {
  /** US dollars a year; "" when not set. */
  maxNetPrice: number | "";
  /** Percent, 0-100, as typed; "" when not set. Sent to the API as a fraction. */
  minAdmissionRatePercent: number | "";
};

export type UsFederalFilterMetadata = {
  applied?: boolean;
  bounds?: { max_net_price_usd?: number; min_admission_rate?: number; max_admission_rate?: number };
  kept?: number;
  excluded?: Partial<Record<"no_federal_record" | "figure_not_reported" | "outside_range", number>>;
  reference_periods?: Record<string, string>;
  caveats?: string[];
};

const US_NAMES = new Set(["united states", "united states of america", "usa", "us", "u.s.", "u.s.a.", "puerto rico"]);

export function isUsCountry(country: string | null | undefined): boolean {
  return US_NAMES.has(String(country ?? "").trim().toLowerCase());
}

/** The query parameters for these values, or none when the country is not the US or nothing is set. */
export function usFederalFilterParams(country: string, values: UsFederalFilterValues): Record<string, string> {
  if (!isUsCountry(country)) return {};
  const params: Record<string, string> = {};
  if (values.maxNetPrice !== "" && Number.isFinite(values.maxNetPrice) && values.maxNetPrice >= 0) {
    params.maxNetPrice = String(Math.round(values.maxNetPrice));
  }
  const rate = values.minAdmissionRatePercent;
  if (rate !== "" && Number.isFinite(rate) && rate >= 0 && rate <= 100) {
    params.minAdmissionRate = String(rate / 100);
  }
  return params;
}

const inputClass =
  "rounded-xl border border-(--color-rule) px-4 py-3 outline-none transition focus:border-(--color-ink) disabled:bg-(--color-paper) disabled:text-(--color-muted)";

type FieldsProps = {
  country: string;
  values: UsFederalFilterValues;
  onChange: (values: UsFederalFilterValues) => void;
};

export function UsFederalFilterFields({ country, values, onChange }: FieldsProps) {
  const enabled = isUsCountry(country);
  return (
    <fieldset className="sm:col-span-2 rounded-xl border border-dashed border-(--color-rule) p-4">
      <legend className="px-1 text-sm font-medium text-(--color-ink)">US federal filters (optional)</legend>
      <p className="mb-3 text-xs text-(--color-muted)">
        {enabled
          ? "College Scorecard and IPEDS figures. They narrow the list and change no score; a university without the figure is left out."
          : "Available when the country is United States: no university elsewhere has these figures."}
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-2">
          <span className="text-sm text-(--color-ink)">Average net price at most (US$ a year)</span>
          <input
            className={inputClass}
            type="number"
            min={0}
            step={1000}
            disabled={!enabled}
            value={values.maxNetPrice}
            onChange={(e) => onChange({ ...values, maxNetPrice: e.target.value === "" ? "" : Number(e.target.value) })}
            placeholder="e.g. 25000"
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-sm text-(--color-ink)">Admission rate at least (%)</span>
          <input
            className={inputClass}
            type="number"
            min={0}
            max={100}
            step={5}
            disabled={!enabled}
            value={values.minAdmissionRatePercent}
            onChange={(e) =>
              onChange({ ...values, minAdmissionRatePercent: e.target.value === "" ? "" : Number(e.target.value) })
            }
            placeholder="e.g. 20"
          />
        </label>
      </div>
    </fieldset>
  );
}

const REASON_TEXT: Record<string, string> = {
  no_federal_record: "with no federal record here",
  figure_not_reported: "without a reported figure",
  outside_range: "outside the range",
};

/** What the filter did, from the API's own counts, with its caveats verbatim. Nothing when it was not applied. */
export function UsFederalFilterSummary({ filter }: { filter: UsFederalFilterMetadata | null | undefined }) {
  if (!filter?.applied) return null;
  const excluded = Object.entries(filter.excluded ?? {}).filter(([, count]) => (count ?? 0) > 0);
  const periods = Object.entries(filter.reference_periods ?? {});
  return (
    <div className="mt-3 rounded-xl border border-(--color-rule) bg-(--color-paper) p-4 text-sm text-(--color-ink-2)">
      <p>
        <span className="font-semibold">US federal filter:</span> {filter.kept ?? 0} candidate
        {filter.kept === 1 ? "" : "s"} kept
        {excluded.length > 0
          ? `; left out ${excluded.map(([reason, count]) => `${count} ${REASON_TEXT[reason] ?? reason}`).join(", ")}.`
          : "."}
      </p>
      {periods.length > 0 ? (
        <p className="mt-1 text-xs text-(--color-muted)">
          {periods.map(([key, period]) => `${key.replace(/_/g, " ")}: ${period}`).join(" · ")}
        </p>
      ) : null}
      <CaveatBanner className="mt-2" caveats={filter.caveats ?? []} />
    </div>
  );
}
