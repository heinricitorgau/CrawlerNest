"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";
import type { DeskTab } from "./types";

export const DESK_TABS: DeskTab[] = [
  { id: "desk", label: "Your desk" },
  { id: "colleges", label: "College list" },
  { id: "activities", label: "Activities" },
  { id: "test-prep", label: "Test prep" },
  { id: "essay-review", label: "Essay review" },
  { id: "brainstorming", label: "Brainstorming" },
  { id: "application", label: "Whole application" },
];

interface DeskTabBarProps {
  tabs?: DeskTab[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

/** Bottom tab bar. Arrow keys move between tabs, per the WAI-ARIA tabs pattern. */
export function DeskTabBar({ tabs = DESK_TABS, activeTab, onChange }: DeskTabBarProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function handleKeyDown(event: KeyboardEvent, index: number) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    const next = (index + step + tabs.length) % tabs.length;
    onChange(tabs[next].id);
    refs.current[next]?.focus();
    event.preventDefault();
  }

  return (
    <nav className="border-t border-slate-200 bg-white/95 backdrop-blur-sm">
      <div role="tablist" aria-label="Application sections" className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 py-2">
        {tabs.map((tab, index) => {
          const active = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              ref={(el) => { refs.current[index] = el; }}
              type="button"
              role="tab"
              id={`desk-tab-${tab.id}`}
              aria-selected={active}
              aria-controls={`desk-panel-${tab.id}`}
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(tab.id)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

interface DeskLayoutProps {
  chat: ReactNode;
  panel: ReactNode;
  tabBar: ReactNode;
  activeTab: string;
}

/**
 * Two columns over a bottom tab bar. The chat column keeps its height and scrolls
 * inside; the right panel scrolls on its own. Below `lg` the columns stack.
 * 4rem is the site NavBar's height.
 */
export function DeskLayout({ chat, panel, tabBar, activeTab }: DeskLayoutProps) {
  return (
    <div className="flex h-[calc(100dvh-4rem)] flex-col bg-slate-50">
      <div
        role="tabpanel"
        id={`desk-panel-${activeTab}`}
        aria-labelledby={`desk-tab-${activeTab}`}
        className="mx-auto grid min-h-0 w-full max-w-7xl flex-1 grid-cols-1 gap-4 overflow-y-auto p-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:overflow-hidden"
      >
        <div className="min-h-[28rem] lg:min-h-0">{chat}</div>
        <div className="min-h-0 space-y-4 lg:overflow-y-auto lg:pr-1">{panel}</div>
      </div>
      {tabBar}
    </div>
  );
}
