import { useState, useEffect, useCallback } from "react";
import type { AuthUser } from "@/types/auth";

export interface AuthState {
  authenticated: boolean;
  currentUser: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function useAuth(): AuthState {
  const [authenticated, setAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/auth/me", {
        credentials: "include",
        cache: "no-store",
      });
      if (res.ok) {
        const json = (await res.json()) as { data?: AuthUser };
        setAuthenticated(true);
        setCurrentUser(json?.data ?? null);
      } else {
        setAuthenticated(false);
        setCurrentUser(null);
      }
    } catch {
      setAuthenticated(false);
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  return { authenticated, currentUser, loading, refresh: fetchMe };
}
