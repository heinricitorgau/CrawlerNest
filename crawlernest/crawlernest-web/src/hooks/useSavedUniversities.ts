import { useState, useEffect, useCallback, useRef } from "react";

export type SavedUniversityItem = {
  canonicalUniversityId: number;
  universityName: string;
  slug: string;
  country: string;
  savedAt: string;
};

type SavedResult = { items: SavedUniversityItem[]; expired: boolean };

/** The signed-in user's saved universities; a 401 is an expired session, any other failure an empty list. */
async function requestSaved(): Promise<SavedResult> {
  try {
    const res = await fetch("/api/user/saved-universities", { credentials: "include", cache: "no-store" });
    if (res.ok) {
      const json = (await res.json()) as { data?: SavedUniversityItem[] };
      return { items: Array.isArray(json?.data) ? json.data : [], expired: false };
    }
    return { items: [], expired: res.status === 401 };
  } catch {
    return { items: [], expired: false };
  }
}

const EMPTY_IDS: Set<number> = new Set();
const EMPTY_ITEMS: SavedUniversityItem[] = [];

export function useSavedUniversities(
  authenticated: boolean,
  onSessionExpired?: () => void
) {
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());
  const [savedItems, setSavedItems] = useState<SavedUniversityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Stable ref so a new callback from the caller never re-creates apply.
  const onSessionExpiredRef = useRef(onSessionExpired);
  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  });

  // The result of one request, applied to state by the caller: the effect applies it in a callback, so it never
  // sets state synchronously. Signed out, nothing is fetched and the returned values are empty by derivation.
  const apply = useCallback((result: SavedResult) => {
    setSavedItems(result.items);
    setSavedIds(new Set(result.items.map((i) => i.canonicalUniversityId)));
    setSessionExpired(result.expired);
    setLoading(false);
    if (result.expired) onSessionExpiredRef.current?.();
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    let cancelled = false;
    void requestSaved().then((result) => {
      if (!cancelled) apply(result);
    });
    return () => {
      cancelled = true;
    };
  }, [authenticated, apply]);

  const refresh = useCallback(async () => {
    if (!authenticated) return;
    setLoading(true);
    apply(await requestSaved());
  }, [authenticated, apply]);

  async function toggleSave(item: { canonicalUniversityId: number }) {
    const id = item.canonicalUniversityId;
    const wasSaved = savedIds.has(id);

    // Optimistic update.
    setSavedIds((prev) => {
      const next = new Set(prev);
      if (wasSaved) next.delete(id);
      else next.add(id);
      return next;
    });

    function revert() {
      setSavedIds((prev) => {
        const next = new Set(prev);
        if (wasSaved) next.add(id);
        else next.delete(id);
        return next;
      });
    }

    try {
      const method = wasSaved ? "DELETE" : "POST";
      const res = await fetch(`/api/user/saved-universities/${id}`, {
        method,
        credentials: "include",
      });
      if (res.ok) {
        void refresh();
      } else if (res.status === 401) {
        revert();
        setSessionExpired(true);
        onSessionExpiredRef.current?.();
      } else {
        revert();
      }
    } catch {
      revert();
    }
  }

  if (!authenticated) {
    return { savedIds: EMPTY_IDS, savedItems: EMPTY_ITEMS, loading: false, toggleSave, refresh, sessionExpired: false };
  }
  return { savedIds, savedItems, loading, toggleSave, refresh, sessionExpired };
}
