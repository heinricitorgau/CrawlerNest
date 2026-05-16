import { useState, useEffect, useCallback } from "react";

export type SavedUniversityItem = {
  canonicalUniversityId: number;
  universityName: string;
  slug: string;
  country: string;
  savedAt: string;
};

export function useSavedUniversities(authenticated: boolean) {
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());
  const [savedItems, setSavedItems] = useState<SavedUniversityItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchSaved = useCallback(async () => {
    if (!authenticated) {
      setSavedIds(new Set());
      setSavedItems([]);
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

    setSavedIds((prev) => {
      const next = new Set(prev);
      if (wasSaved) next.delete(id);
      else next.add(id);
      return next;
    });

    try {
      const method = wasSaved ? "DELETE" : "POST";
      const res = await fetch(`/api/user/saved-universities/${id}`, {
        method,
        credentials: "include",
      });
      if (res.ok) {
        fetchSaved();
      } else {
        setSavedIds((prev) => {
          const next = new Set(prev);
          if (wasSaved) next.add(id);
          else next.delete(id);
          return next;
        });
      }
    } catch {
      setSavedIds((prev) => {
        const next = new Set(prev);
        if (wasSaved) next.add(id);
        else next.delete(id);
        return next;
      });
    }
  }

  return { savedIds, savedItems, loading, toggleSave, refresh: fetchSaved };
}
