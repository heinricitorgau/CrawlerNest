"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * The shortlist, kept in localStorage and shared by every component that shows it.
 *
 * Four components used to read the same key into their own state, each with its own validation, inside an effect:
 * none saw another's changes until a reload, and the rankings page wrote `[]` over the stored list on mount before its
 * own read took effect. Here there is one reader (validated once), one writer, and a subscription, so a toggle on a
 * university page shows up in the rankings sidebar and on /compare without a reload, and in other tabs through the
 * `storage` event. The server snapshot is empty, so server and first client render agree.
 */

export const SHORTLIST_STORAGE_KEY = "crawlernest_shortlist";
const CHANGE_EVENT = "crawlernest:shortlist";

export type ShortlistItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  slug: string;
};

export function isShortlistItem(value: unknown): value is ShortlistItem {
  const item = value as Partial<ShortlistItem> | null;
  return (
    typeof item?.canonicalUniversityId === "number" &&
    typeof item?.universityName === "string" &&
    typeof item?.country === "string" &&
    typeof item?.aggregatedRank === "number" &&
    typeof item?.slug === "string"
  );
}

/** The stored list, keeping only well-formed items; a missing, unreadable or malformed value is an empty list. */
export function parseShortlist(raw: string | null): ShortlistItem[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isShortlistItem) : [];
  } catch {
    return [];
  }
}

const EMPTY: ShortlistItem[] = [];
let cachedRaw: string | null = null;
let cachedItems: ShortlistItem[] = EMPTY;

function readRaw(): string | null {
  try {
    return window.localStorage.getItem(SHORTLIST_STORAGE_KEY);
  } catch {
    return null;
  }
}

/** The current list; the same array object until the stored text changes, as useSyncExternalStore requires. */
export function readShortlist(): ShortlistItem[] {
  const raw = readRaw();
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedItems = parseShortlist(raw);
  }
  return cachedItems;
}

export function writeShortlist(items: ShortlistItem[]): void {
  try {
    window.localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Storage full or blocked: the list stays as it was, which is what every reader will show.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onChange: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === SHORTLIST_STORAGE_KEY) onChange();
  };
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

/** The shortlist and a setter that takes a new list or an updater, like useState's. */
export function useShortlist(): [ShortlistItem[], (next: ShortlistItem[] | ((current: ShortlistItem[]) => ShortlistItem[])) => void] {
  const items = useSyncExternalStore(subscribe, readShortlist, () => EMPTY);
  const setItems = useCallback(
    (next: ShortlistItem[] | ((current: ShortlistItem[]) => ShortlistItem[])) => {
      writeShortlist(typeof next === "function" ? next(readShortlist()) : next);
    },
    [],
  );
  return [items, setItems];
}
