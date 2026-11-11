"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/**
 * False during the server render and the hydrating client render, true after; for content that must not differ
 * between the two (anything read from localStorage, the clock or the window). Replaces a `useState(false)` flag set
 * from an effect, which costs an extra render and is what react-hooks/set-state-in-effect flags.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(subscribe, () => true, () => false);
}
