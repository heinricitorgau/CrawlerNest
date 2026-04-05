"use client";

import { useEffect, useState } from "react";

const SHORTLIST_STORAGE_KEY = "crawlernest_shortlist";

type ShortlistItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  slug: string;
};

type Props = {
  item: ShortlistItem;
};

function isShortlistItemArray(value: unknown): value is ShortlistItem[] {
  return Array.isArray(value);
}

function readStoredShortlist(): ShortlistItem[] {
  try {
    const stored = window.localStorage.getItem(SHORTLIST_STORAGE_KEY);
    if (!stored) {
      return [];
    }

    const parsed = JSON.parse(stored) as unknown;
    return isShortlistItemArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function ShortlistButton({ item }: Props) {
  const [inList, setInList] = useState(false);

  if (!item || typeof item.canonicalUniversityId !== "number") {
    return null;
  }

  useEffect(() => {
    const parsed = readStoredShortlist();
    setInList(
      parsed.some((s) => s.canonicalUniversityId === item.canonicalUniversityId)
    );
  }, [item.canonicalUniversityId]);

  function toggle() {
    try {
      const current = readStoredShortlist();

      let next: ShortlistItem[];
      if (inList) {
        next = current.filter(
          (s) => s.canonicalUniversityId !== item.canonicalUniversityId
        );
      } else {
        next = [...current, item];
      }

      window.localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(next));
      setInList(!inList);
    } catch {
      // ignore
    }
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
