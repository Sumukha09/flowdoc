"use client";

import { useState } from "react";

/* ─────────────────────────────────────────────────────────
 * FILTER TABLE
 * ───────────────────────────────────────────────────────── */

export default function FilterTable({ filters, rows, columns }) {
  const [filter, setFilter] = useState("all");

  return (
    <div className="w-full">
      {/* filter chips */}
      <div
        className="-mx-1 mb-1 flex items-center gap-1 overflow-x-auto px-1 py-1"
        style={{ scrollbarWidth: "none" }}
      >
        {filters.map((f) => {
          const active = filter === f.key;
          return (
            <button
              key={f.key}
              type="button"
              aria-pressed={active}
              onClick={() => setFilter(f.key)}
              className={`flex h-6.5 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-[12px]
                font-medium transition-[background-color,box-shadow,color] duration-200
                ${active ? "bg-surface text-ink shadow-btn" : "text-ink-2 hover:bg-hover"}`}
            >
              {f.dot && <span className="size-1.5 rounded-full" style={{ background: f.dot }} />}
              {f.label}
              <span
                className={`rounded-[4px] px-1 text-[10.5px] tabular-nums
                  ${active ? "bg-field text-ink-2" : "text-ink-3"}`}
              >
                {f.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Compact labeled rows on phones */}
      <div className="space-y-2 lg:hidden">
        {rows.filter((row) => filter === "all" || row.statusKey === filter).map((row, rowIndex) => (
          <div key={rowIndex} className="grid grid-cols-1 gap-2 rounded-card border border-line bg-surface p-3 shadow-card">
            {row.cells.map((cell, cellIndex) => (
              <div key={cellIndex} className="grid min-w-0 grid-cols-[minmax(5.5rem,auto)_minmax(0,1fr)] items-start gap-3 text-sm">
                <span className="text-xs font-medium text-ink-3">{columns.headers[cellIndex]}</span>
                <span className="min-w-0 break-words text-right text-ink-2">{cell}</span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Full table at tablet and desktop sizes */}
      <div className="hidden overflow-x-auto rounded-card bg-surface shadow-card lg:block" style={{ scrollbarWidth: "thin" }}>
        <div className="min-w-full">
          <div className="grid border-b border-line px-3 py-2 text-[11.5px] font-medium text-ink-3" style={{ gridTemplateColumns: columns.template }}>
            {columns.headers.map((h, i) => <span key={i} className="min-w-0 truncate">{h}</span>)}
          </div>

          {rows.map((row, i) => {
            const shown = filter === "all" || row.statusKey === filter;
            return (
              <div
                key={i}
                className="grid transition-[grid-template-rows,opacity] duration-300"
                style={{
                  gridTemplateRows: shown ? "1fr" : "0fr",
                  opacity: shown ? 1 : 0,
                  transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)",
                }}
              >
                <div className="overflow-hidden">
                  <div className="grid min-w-0 items-center border-b border-line px-3 py-3 text-xs transition-colors duration-100 last:border-0 hover:bg-hover" style={{ gridTemplateColumns: columns.template }}>
                    {row.cells.map((cell, idx) => (
                      <span key={idx} className={`min-w-0 truncate pr-2 ${idx === 0 ? "font-medium text-ink" : "text-ink-2"}`}>
                        {cell}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
