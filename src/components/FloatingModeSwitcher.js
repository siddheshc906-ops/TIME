// src/components/FloatingModeSwitcher.js
// Drop this component anywhere on a page (Landing, etc.) — it renders as a
// fixed floating panel on the right edge. Remove <ModeSelector> from Navigation
// if you want this to be the sole mode-switcher.

import { useState, useEffect, useRef } from "react";
import { useMode } from "../context/ModeContext";
import { Check } from "lucide-react";

// ─── Tiny SVG icon for the toggle trigger ────────────────────────────────────
function PaletteIcon() {
  return (
    <svg
      width="20" height="20" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round"
    >
      <circle cx="13.5" cy="6.5" r=".5" fill="currentColor" stroke="none" />
      <circle cx="17.5" cy="10.5" r=".5" fill="currentColor" stroke="none" />
      <circle cx="8.5" cy="7.5" r=".5" fill="currentColor" stroke="none" />
      <circle cx="6.5" cy="12.5" r=".5" fill="currentColor" stroke="none" />
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688
               0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64
               1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554
               C21.965 6.012 17.461 2 12 2z" />
    </svg>
  );
}

// ─── Mode ring decoration ─────────────────────────────────────────────────────
function ModeRing({ color, active }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 12,
        height: 12,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
        boxShadow: active ? `0 0 0 3px ${color}33` : "none",
        transition: "box-shadow 0.2s ease",
      }}
    />
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function FloatingModeSwitcher() {
  const { mode, setMode, themes } = useMode();
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(null);
  const ref = useRef(null);

  // Close on outside click
  useEffect(() => {
    function handler(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Close on Escape
  useEffect(() => {
    function handler(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const currentTheme = themes[mode];

  return (
    <div
      ref={ref}
      style={{
        position: "fixed",
        right: 20,
        bottom: 80,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: 10,
        fontFamily: "var(--font-body, system-ui, sans-serif)",
      }}
    >
      {/* ── Panel ─────────────────────────────────────────────────────── */}
      <div
        style={{
          background: "var(--card-bg, rgba(255,255,255,0.92))",
          border: "1px solid var(--card-border, rgba(0,0,0,0.08))",
          borderRadius: 20,
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          boxShadow: open
            ? "0 20px 60px rgba(0,0,0,0.18), 0 4px 16px rgba(0,0,0,0.08)"
            : "0 8px 32px rgba(0,0,0,0.10)",
          overflow: "hidden",
          // Animate open/close
          maxHeight: open ? 420 : 0,
          opacity: open ? 1 : 0,
          transform: open ? "translateY(0) scale(1)" : "translateY(12px) scale(0.96)",
          transformOrigin: "bottom right",
          transition:
            "max-height 0.32s cubic-bezier(0.4,0,0.2,1), opacity 0.22s ease, transform 0.22s cubic-bezier(0.4,0,0.2,1), box-shadow 0.2s ease",
          pointerEvents: open ? "auto" : "none",
          width: 220,
          marginBottom: 4,
        }}
        aria-hidden={!open}
      >
        {/* Header label */}
        <div
          style={{
            padding: "14px 16px 8px",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--text-secondary, #888)",
          }}
        >
          Visual Mode
        </div>

        {/* Mode list */}
        <div style={{ padding: "0 8px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
          {Object.entries(themes).map(([key, theme]) => {
            const isActive = mode === key;
            const isHov = hovered === key;

            return (
              <button
                key={key}
                onClick={() => { setMode(key); setOpen(false); }}
                onMouseEnter={() => setHovered(key)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "9px 10px",
                  borderRadius: 12,
                  border: "none",
                  cursor: "pointer",
                  width: "100%",
                  textAlign: "left",
                  background: isActive
                    ? "var(--accent-light, rgba(139,92,246,0.10))"
                    : isHov
                    ? "var(--accent-light, rgba(139,92,246,0.06))"
                    : "transparent",
                  transition: "background 0.15s ease",
                  outline: "none",
                }}
              >
                <ModeRing color={theme.previewColor} active={isActive} />

                {/* Emoji + label */}
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    flex: 1,
                    fontSize: 13,
                    fontWeight: isActive ? 600 : 400,
                    color: isActive
                      ? "var(--accent, #7c3aed)"
                      : "var(--text-primary, #111)",
                    transition: "color 0.15s ease, font-weight 0.15s ease",
                  }}
                >
                  <span style={{ fontSize: 15 }}>{theme.emoji}</span>
                  <span>{theme.label}</span>
                </span>

                {/* Active checkmark */}
                {isActive && (
                  <Check
                    size={14}
                    style={{
                      color: "var(--accent, #7c3aed)",
                      flexShrink: 0,
                    }}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom hint */}
        <div
          style={{
            margin: "0 16px 14px",
            padding: "8px 10px",
            borderRadius: 10,
            background: "var(--accent-light, rgba(139,92,246,0.06))",
            fontSize: 11,
            color: "var(--text-secondary, #888)",
            lineHeight: 1.5,
          }}
        >
          Each mode changes colors, fonts, and particles across the whole app.
        </div>
      </div>

      {/* ── Trigger pill ───────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Switch visual mode"
        aria-expanded={open}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          padding: "10px 16px",
          borderRadius: 999,
          border: "1px solid var(--card-border, rgba(0,0,0,0.10))",
          background: open
            ? "var(--accent, #7c3aed)"
            : "var(--card-bg, rgba(255,255,255,0.9))",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          boxShadow: open
            ? `0 8px 28px ${currentTheme.previewColor}55`
            : "0 4px 20px rgba(0,0,0,0.12)",
          cursor: "pointer",
          color: open ? "#fff" : "var(--text-primary, #111)",
          fontSize: 13,
          fontWeight: 600,
          outline: "none",
          transition:
            "background 0.2s ease, box-shadow 0.2s ease, color 0.2s ease, transform 0.15s ease",
          transform: open ? "scale(1.04)" : "scale(1)",
          userSelect: "none",
        }}
        onMouseEnter={(e) => {
          if (!open) e.currentTarget.style.transform = "scale(1.06)";
        }}
        onMouseLeave={(e) => {
          if (!open) e.currentTarget.style.transform = "scale(1)";
        }}
      >
        {/* Animated accent dot */}
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: open ? "rgba(255,255,255,0.8)" : currentTheme.previewColor,
            boxShadow: open
              ? "none"
              : `0 0 0 3px ${currentTheme.previewColor}33`,
            flexShrink: 0,
            transition: "background 0.2s, box-shadow 0.2s",
          }}
        />

        {/* Palette icon */}
        <span
          style={{
            display: "flex",
            alignItems: "center",
            opacity: open ? 0.9 : 0.7,
            transition: "opacity 0.2s",
          }}
        >
          <PaletteIcon />
        </span>

        {/* Current mode label */}
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          <span>{currentTheme.emoji}</span>
          <span>{currentTheme.label}</span>
        </span>
      </button>
    </div>
  );
}