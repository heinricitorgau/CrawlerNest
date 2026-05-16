import { useState, useEffect, useCallback, useRef } from "react";

export type SavedUniversityItem = {
  canonicalUniversityId: number;
  universityName: string;
  slug: string;
  country: string;
  savedAt: string;
};

export function useSavedUniversities(
  authenticated: boolean,
  onSessionExpired?: () => void
) {
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());
  const [savedItems, setSavedItems] = useState<SavedUniversityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Stable ref so the callback never forces fetchSaved to re-create.
  const onSessionExpiredRef = useRef(onSessionExpired);
  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  });

  const fetchSaved = useCallback(async () => {
    if (!authenticated) {
      setSavedIds(new Set());
      setSavedItems([]);
      setSessionExpired(false);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/user/saved-universities", {
        credentials: "include",
        cache: "no-store",
      });
      if (res.ok) {
        const json = (await res.json()) as { data?: SavedUniversityItem[] };
        const items = Array.isArray(json?.data) ? json.data : [];
        setSavedItems(items);
        setSavedIds(new Set(items.map((i) => i.canonicalUniversityId)));
        setSessionExpired(false);
      } else if (res.status === 401) {
        setSavedIds(new Set());
        setSavedItems([]);
        setSessionExpired(true);
        onSessionExpiredRef.current?.();
      } else {
        setSavedIds(new Set());
        setSavedItems([]);
      }
    } catch {
      setSavedIds(new Set());
      setSavedItems([]);
    } finally {
      setLoading(false);
    }
  }, [authenticated]);

  useEffect(() => {
    fetchSaved();
  }, [fetchSaved]);

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
        fetchSaved();
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

  return { savedIds, savedItems, loading, toggleSave, refresh: fetchSaved, sessionExpired };
}
