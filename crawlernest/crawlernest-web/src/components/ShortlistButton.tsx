"use client";

import { useShortlist, type ShortlistItem } from "@/lib/shortlistStore";

type Props = {
  item: ShortlistItem;
};

/** Adds or removes one university from the shared shortlist (lib/shortlistStore). */
export default function ShortlistButton({ item }: Props) {
  // Checked before any hook is called -- in a child component -- so the hooks run in the same order on every
  // render. Returning early above a hook made React throw if `item` ever turned invalid between renders.
  if (!item || typeof item.canonicalUniversityId !== "number") {
    return null;
  }
  return <ShortlistToggle item={item} />;
}

function ShortlistToggle({ item }: Props) {
  const [shortlist, setShortlist] = useShortlist();
  const inList = shortlist.some((s) => s.canonicalUniversityId === item.canonicalUniversityId);

  function toggle() {
    setShortlist((current) =>
      current.some((s) => s.canonicalUniversityId === item.canonicalUniversityId)
        ? current.filter((s) => s.canonicalUniversityId !== item.canonicalUniversityId)
        : [...current, item],
    );
  }

  return (
    <button
      onClick={toggle}
      className={`text-xs font-bold px-4 py-1.5 rounded border transition-colors ${
        inList
          ? "border-green-300 bg-green-50 text-green-700 hover:bg-green-100"
          : "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
      }`}
    >
      {inList ? "✓ Shortlisted" : "+ Shortlist"}
    </button>
  );
}
