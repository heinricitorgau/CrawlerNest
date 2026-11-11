import { useState, useEffect, useCallback } from "react";
import type { AuthUser } from "@/types/auth";

export interface AuthState {
  authenticated: boolean;
  currentUser: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

type Me = { authenticated: boolean; user: AuthUser | null };

/** Who is signed in, per the API; any failure reads as signed out. Sets no state, so an effect can call it. */
async function requestMe(): Promise<Me> {
  try {
    const res = await fetch("/api/auth/me", { credentials: "include", cache: "no-store" });
    if (!res.ok) return { authenticated: false, user: null };
    const json = (await res.json()) as { data?: AuthUser };
    return { authenticated: true, user: json?.data ?? null };
  } catch {
    return { authenticated: false, user: null };
  }
}

export function useAuth(): AuthState {
  const [me, setMe] = useState<Me>({ authenticated: false, user: null });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void requestMe().then((result) => {
      if (cancelled) return;
      setMe(result);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // From an event (sign-in, sign-out): show loading, then ask again.
  const refresh = useCallback(async () => {
    setLoading(true);
    setMe(await requestMe());
    setLoading(false);
  }, []);

  return { authenticated: me.authenticated, currentUser: me.user, loading, refresh };
}
