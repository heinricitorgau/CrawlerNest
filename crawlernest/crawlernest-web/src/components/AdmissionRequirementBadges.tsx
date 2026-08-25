import {
  formatDeadline,
  formatDuolingo,
  formatGpa,
  formatIelts,
  formatToefl,
} from "@/lib/format";

/**
 * The entry requirements a university publishes, as every endpoint that carries
 * them shapes it. Each is null when the crawled source published no value, which
 * is the common case rather than the exception.
 */
export type AdmissionRequirementValues = {
  ieltsRequirement?: number | null;
  toeflRequirement?: number | null;
  duolingoRequirement?: number | null;
  gpaRequirement?: number | null;
  /** ISO-8601 `yyyy-MM-dd`. */
  applicationDeadline?: string | null;
};

export type AdmissionRequirementBadgesProps = {
  requirements: AdmissionRequirementValues;
  /**
   * Rendered when the university publishes nothing at all. Pass null to render
   * nothing, which suits a dense list where a row of empty states would be noise.
   */
  emptyMessage?: string | null;
  className?: string;
};

const NEUTRAL_TONE = "border-[#d7d5d0] bg-[#f5f3ee] text-[#3f4640]";

/**
 * Colours a deadline by how close it is, matching the traffic-light tones the
 * recommendation card already uses for its other urgency signals.
 *
 * Compares whole UTC days on both sides. Mixing a UTC deadline against a local
 * "today" makes the count jump by one for anyone outside UTC, which is the
 * difference between "due tomorrow" and "closed" at the moment it matters most.
 */
function deadlineTone(deadline: string): { tone: string; icon: string; note: string } {
  const due = new Date(`${deadline}T00:00:00Z`);
  if (Number.isNaN(due.getTime())) {
    return { tone: NEUTRAL_TONE, icon: "🗓", note: "" };
  }

  const now = new Date();
  const todayUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const days = Math.round((due.getTime() - todayUtc) / 86_400_000);

  if (days < 0) {
    return {
      tone: "border-[#d7d5d0] bg-[#f5f3ee] text-[#6b7068]",
      icon: "⚪",
      note: "closed",
    };
  }
  if (days <= 30) {
    return {
      tone: "border-[#f1c5bc] bg-[#fbefeb] text-[#8b3a2b]",
      icon: "🔴",
      note: days === 0 ? "today" : `${days}d left`,
    };
  }
  if (days <= 90) {
    return {
      tone: "border-[#ead9a7] bg-[#fbf5e4] text-[#8a6116]",
      icon: "🟡",
      note: `${days}d left`,
    };
  }
  return {
    tone: "border-[#cfe5d7] bg-[#edf7f1] text-[#1a3d2e]",
    icon: "🟢",
    note: `${days}d left`,
  };
}

function Badge({
  label,
  value,
  tone,
  icon,
  note,
  title,
}: {
  label: string;
  value: string;
  tone: string;
  icon: string;
  note?: string;
  title?: string;
}) {
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${tone}`}
      title={title}
    >
      <span aria-hidden="true">{icon}</span>
      <span className="uppercase tracking-[0.08em] opacity-70">{label}</span>
      <span>{value}</span>
      {note ? (
        <>
          <span className="opacity-50" aria-hidden="true">
            ·
          </span>
          <span className="font-medium opacity-80">{note}</span>
        </>
      ) : null}
    </div>
  );
}

/**
 * Renders one pill per requirement the university actually published.
 *
 * A requirement with no value is omitted rather than shown as "Not available":
 * a row of five "Not available" pills carries no information and buries the one
 * or two real numbers among them. Whether the university has any data at all is
 * already answered by `emptyMessage`.
 */
export function AdmissionRequirementBadges({
  requirements,
  emptyMessage = "No published entry requirements",
  className,
}: AdmissionRequirementBadgesProps) {
  const badges: React.ReactNode[] = [];

  const push = (key: string, label: string, value: number | null | undefined, format: (v: number | null | undefined) => string) => {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return;
    }
    badges.push(
      <Badge key={key} label={label} value={format(value)} tone={NEUTRAL_TONE} icon="●" />
    );
  };

  push("ielts", "IELTS", requirements.ieltsRequirement, formatIelts);
  push("toefl", "TOEFL", requirements.toeflRequirement, formatToefl);
  push("duolingo", "Duolingo", requirements.duolingoRequirement, formatDuolingo);
  push("gpa", "GPA", requirements.gpaRequirement, formatGpa);

  const deadline = requirements.applicationDeadline;
  if (deadline) {
    const formatted = formatDeadline(deadline);
    if (formatted !== "Not available") {
      const { tone, icon, note } = deadlineTone(deadline);
      badges.push(
        <Badge
          key="deadline"
          label="Deadline"
          value={formatted}
          tone={tone}
          icon={icon}
          note={note}
          title={`Application deadline ${formatted}`}
        />
      );
    }
  }

  if (badges.length === 0) {
    if (!emptyMessage) {
      return null;
    }
    return (
      <p className={`text-xs italic text-[#6b7068] ${className ?? ""}`}>{emptyMessage}</p>
    );
  }

  return <div className={`flex flex-wrap items-center gap-2 ${className ?? ""}`}>{badges}</div>;
}
