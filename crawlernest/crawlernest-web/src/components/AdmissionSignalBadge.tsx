export type AdmissionSignalStatus = "accepted" | "needs_review" | "conflict" | string;

export type AdmissionSignalBadgeProps = {
  label: string;
  value: number | string | Record<string, string>;
  confidence: number;
  sourceCount: number;
  status: AdmissionSignalStatus;
  compact?: boolean;
};

function confidenceLabel(confidence: number) {
  if (confidence >= 0.8) {
    return "High";
  }
  if (confidence >= 0.6) {
    return "Medium";
  }
  return "Low";
}

function confidenceClass(confidence: number) {
  if (confidence >= 0.8) {
    return "text-green-600";
  }
  if (confidence >= 0.6) {
    return "text-blue-600";
  }
  return "text-gray-500";
}

function formatSignalValue(value: AdmissionSignalBadgeProps["value"]) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }
  if (typeof value === "string") {
    return value;
  }

  const ordered = (["early", "final", "rolling"] as const)
    .filter((key) => value[key])
    .map((key) => `${key} ${value[key]}`);
  return ordered.length > 0 ? ordered.join(", ") : "Available";
}

export function AdmissionSignalBadge({
  label,
  value,
  confidence,
  sourceCount,
  status,
  compact = false,
}: AdmissionSignalBadgeProps) {
  const valueText = formatSignalValue(value);
  const baseClass = compact
    ? "flex flex-wrap items-center gap-x-2 gap-y-1 text-xs"
    : "flex flex-col gap-1 rounded-lg border border-[#e0ddd8] bg-white px-3 py-2 text-sm";

  if (status === "needs_review") {
    return (
      <div className={baseClass}>
        <span className="font-medium text-[#1a1a1a]">
          {label} {valueText}
        </span>
        <span className="text-yellow-600">⚠ Needs review</span>
      </div>
    );
  }

  if (status === "conflict") {
    return (
      <div className={baseClass}>
        <span className="font-medium text-[#1a1a1a]">
          {label} {valueText}
        </span>
        <span className="text-red-600">⚠ Conflicting sources</span>
      </div>
    );
  }

  const confidenceText = confidenceLabel(confidence);
  const sourceLabel = sourceCount === 1 ? "source" : "sources";

  return (
    <div className={baseClass}>
      <span className="font-medium text-[#1a1a1a]">
        {label} {valueText}
      </span>
      <span className={confidenceClass(confidence)}>● {confidenceText} confidence</span>
      <span className="text-[#6b7068]">
        {sourceCount} {sourceLabel}
      </span>
    </div>
  );
}
