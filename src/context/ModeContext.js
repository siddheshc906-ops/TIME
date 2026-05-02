// src/context/ModeContext.js
import { createContext, useContext, useEffect, useState, useCallback } from "react";

// ─────────────────────────────────────────────
// Theme Definitions
// ─────────────────────────────────────────────
export const MODES = {

  // ── 1. STUDENT ───────────────────────────────────────────────────────────
  // Warm lavender gradient, friendly rounded cards, violet accents.
  // Identical to the original design — this is the baseline.
  student: {
    label: "Scholar",
    emoji: "🎓",
    previewColor: "#7c3aed",
    vars: {
      // Background & overlay
      "--bg-gradient":        "linear-gradient(135deg, #f5d0fe 0%, #e9d5ff 40%, #c7d2fe 100%)",
      "--overlay-bg":         "rgba(255,255,255,0.20)",
      "--overlay-blur":       "2px",

      // Navigation
      "--nav-bg":             "rgba(255,255,255,0.80)",
      "--nav-border":         "rgba(226,232,240,1)",

      // Accent palette
      "--accent":             "#7c3aed",
      "--accent-hover":       "#6d28d9",
      "--accent-light":       "#ede9fe",
      "--accent-text":        "#5b21b6",

      // Cards
      "--card-bg":            "rgba(255,255,255,0.70)",
      "--card-border":        "rgba(139,92,246,0.15)",
      "--card-radius":        "16px",
      "--card-shadow":        "0 4px 24px rgba(124,58,237,0.08)",

      // Typography
      "--text-primary":       "#0f172a",
      "--text-secondary":     "#475569",
      "--text-muted":         "#94a3b8",
      "--font-body":          "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      "--font-mono":          "'Fira Code', monospace",
      "--font-display":       "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      "--heading-weight":     "700",
      "--letter-spacing":     "0em",

      // Inputs
      "--input-bg":           "rgba(255,255,255,0.8)",
      "--input-border":       "rgba(139,92,246,0.3)",
      "--input-radius":       "12px",

      // Misc
      "--particle-color":     "#a78bfa",
      "--badge-bg":           "#ede9fe",
      "--badge-text":         "#5b21b6",
      "--scrollbar-thumb":    "#c4b5fd",
      "--scrollbar-track":    "rgba(237,233,254,0.4)",
      "--shadow-accent":      "rgba(124,58,237,0.25)",
      "--divider":            "rgba(139,92,246,0.12)",
      "--selection-bg":       "#ddd6fe",
      "--selection-text":     "#4c1d95",
    },
  },

  // ── 2. DEVELOPER ─────────────────────────────────────────────────────────
  // GitHub-dark base, monospace everything, matrix-green accents.
  // Cards look like IDE panels. Badge/tag feel like terminal output.
  developer: {
    label: "Dev Mode",
    emoji: "💻",
    previewColor: "#00ff88",
    vars: {
      "--bg-gradient":        "#0d1117",
      "--overlay-bg":         "rgba(0,0,0,0.60)",
      "--overlay-blur":       "0px",

      "--nav-bg":             "rgba(13,17,23,0.96)",
      "--nav-border":         "rgba(48,54,61,1)",

      "--accent":             "#00ff88",
      "--accent-hover":       "#00e07a",
      "--accent-light":       "rgba(0,255,136,0.10)",
      "--accent-text":        "#00ff88",

      "--card-bg":            "#161b22",
      "--card-border":        "rgba(48,54,61,1)",
      "--card-radius":        "8px",
      "--card-shadow":        "0 0 0 1px rgba(0,255,136,0.06)",

      "--text-primary":       "#e6edf3",
      "--text-secondary":     "#8b949e",
      "--text-muted":         "#484f58",
      "--font-body":          "'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace",
      "--font-mono":          "'Fira Code', monospace",
      "--font-display":       "'Fira Code', monospace",
      "--heading-weight":     "600",
      "--letter-spacing":     "-0.01em",

      "--input-bg":           "#0d1117",
      "--input-border":       "rgba(48,54,61,1)",
      "--input-radius":       "6px",

      "--particle-color":     "#00ff88",
      "--badge-bg":           "rgba(0,255,136,0.10)",
      "--badge-text":         "#00ff88",
      "--scrollbar-thumb":    "#30363d",
      "--scrollbar-track":    "#161b22",
      "--shadow-accent":      "rgba(0,255,136,0.15)",
      "--divider":            "rgba(48,54,61,1)",
      "--selection-bg":       "rgba(0,255,136,0.20)",
      "--selection-text":     "#00ff88",
    },
  },

  // ── 3. FOUNDER ───────────────────────────────────────────────────────────
  // Deep navy + gold. Serif display font for headings. Sharp corners.
  // Executive/boardroom aesthetic — minimal, authoritative, expensive.
  founder: {
    label: "Empire",
    emoji: "🏛️",
    previewColor: "#f59e0b",
    vars: {
      "--bg-gradient":        "linear-gradient(160deg, #050810 0%, #0a0f1e 60%, #0d1228 100%)",
      "--overlay-bg":         "rgba(0,0,0,0.50)",
      "--overlay-blur":       "1px",

      "--nav-bg":             "rgba(5,8,16,0.96)",
      "--nav-border":         "rgba(245,158,11,0.18)",

      "--accent":             "#f59e0b",
      "--accent-hover":       "#d97706",
      "--accent-light":       "rgba(245,158,11,0.08)",
      "--accent-text":        "#fbbf24",

      "--card-bg":            "rgba(10,15,30,0.92)",
      "--card-border":        "rgba(245,158,11,0.14)",
      "--card-radius":        "4px",
      "--card-shadow":        "0 1px 0 rgba(245,158,11,0.10), 0 8px 32px rgba(0,0,0,0.40)",

      "--text-primary":       "#f1f5f9",
      "--text-secondary":     "#94a3b8",
      "--text-muted":         "#475569",
      "--font-body":          "Georgia, 'Times New Roman', serif",
      "--font-mono":          "'Fira Code', monospace",
      "--font-display":       "'Playfair Display', 'Cormorant Garamond', Georgia, serif",
      "--heading-weight":     "700",
      "--letter-spacing":     "0.04em",

      "--input-bg":           "rgba(5,8,16,0.98)",
      "--input-border":       "rgba(245,158,11,0.20)",
      "--input-radius":       "4px",

      "--particle-color":     "#f59e0b",
      "--badge-bg":           "rgba(245,158,11,0.10)",
      "--badge-text":         "#fbbf24",
      "--scrollbar-thumb":    "rgba(245,158,11,0.30)",
      "--scrollbar-track":    "rgba(10,15,30,0.80)",
      "--shadow-accent":      "rgba(245,158,11,0.18)",
      "--divider":            "rgba(245,158,11,0.10)",
      "--selection-bg":       "rgba(245,158,11,0.18)",
      "--selection-text":     "#fbbf24",
    },
  },

  // ── 4. NIGHT OWL ─────────────────────────────────────────────────────────
  // Near-black indigo canvas, starfield particles, soft periwinkle glow.
  // Calm and meditative — built for late-night deep work sessions.
  nightOwl: {
    label: "Night Mode",
    emoji: "🦉",
    previewColor: "#818cf8",
    vars: {
      "--bg-gradient":        "linear-gradient(160deg, #05050f 0%, #080812 50%, #05050f 100%)",
      "--overlay-bg":         "rgba(8,8,18,0.55)",
      "--overlay-blur":       "1px",

      "--nav-bg":             "rgba(5,5,15,0.92)",
      "--nav-border":         "rgba(129,140,248,0.12)",

      "--accent":             "#818cf8",
      "--accent-hover":       "#6366f1",
      "--accent-light":       "rgba(129,140,248,0.10)",
      "--accent-text":        "#a5b4fc",

      "--card-bg":            "rgba(10,10,28,0.90)",
      "--card-border":        "rgba(129,140,248,0.10)",
      "--card-radius":        "14px",
      "--card-shadow":        "0 0 0 1px rgba(129,140,248,0.06), 0 8px 32px rgba(0,0,0,0.50)",

      "--text-primary":       "#e2e8f0",
      "--text-secondary":     "#8892a4",
      "--text-muted":         "#3d4663",
      "--font-body":          "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      "--font-mono":          "'Fira Code', monospace",
      "--font-display":       "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      "--heading-weight":     "500",
      "--letter-spacing":     "0.01em",

      "--input-bg":           "rgba(8,8,22,0.98)",
      "--input-border":       "rgba(129,140,248,0.18)",
      "--input-radius":       "10px",

      "--particle-color":     "#818cf8",
      "--badge-bg":           "rgba(129,140,248,0.10)",
      "--badge-text":         "#a5b4fc",
      "--scrollbar-thumb":    "rgba(129,140,248,0.25)",
      "--scrollbar-track":    "rgba(10,10,28,0.80)",
      "--shadow-accent":      "rgba(129,140,248,0.15)",
      "--divider":            "rgba(129,140,248,0.08)",
      "--selection-bg":       "rgba(129,140,248,0.18)",
      "--selection-text":     "#a5b4fc",
    },
  },

  // ── 5. FOCUS BEAST ───────────────────────────────────────────────────────
  // Dark charcoal, red-to-orange gradient accents, heavy font weight.
  // Aggressive, high-contrast, zero distractions — beast mode only.
  focusBeast: {
    label: "Beast Mode",
    emoji: "🔥",
    previewColor: "#ef4444",
    vars: {
      "--bg-gradient":        "#0e0e0e",
      "--overlay-bg":         "rgba(0,0,0,0.55)",
      "--overlay-blur":       "0px",

      "--nav-bg":             "rgba(14,14,14,0.97)",
      "--nav-border":         "rgba(239,68,68,0.18)",

      "--accent":             "#ef4444",
      "--accent-hover":       "#dc2626",
      "--accent-light":       "rgba(239,68,68,0.10)",
      "--accent-text":        "#f97316",

      "--card-bg":            "#181010",
      "--card-border":        "rgba(239,68,68,0.14)",
      "--card-radius":        "10px",
      "--card-shadow":        "0 0 0 1px rgba(239,68,68,0.08), 0 4px 24px rgba(0,0,0,0.60)",

      "--text-primary":       "#fafafa",
      "--text-secondary":     "#a3a3a3",
      "--text-muted":         "#525252",
      "--font-body":          "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      "--font-mono":          "'Fira Code', monospace",
      "--font-display":       "'Inter', -apple-system, sans-serif",
      "--heading-weight":     "800",
      "--letter-spacing":     "-0.02em",

      "--input-bg":           "#0e0e0e",
      "--input-border":       "rgba(239,68,68,0.22)",
      "--input-radius":       "8px",

      "--particle-color":     "#ef4444",
      "--badge-bg":           "rgba(239,68,68,0.12)",
      "--badge-text":         "#f97316",
      "--scrollbar-thumb":    "rgba(239,68,68,0.35)",
      "--scrollbar-track":    "#181010",
      "--shadow-accent":      "rgba(239,68,68,0.22)",
      "--divider":            "rgba(239,68,68,0.10)",
      "--selection-bg":       "rgba(239,68,68,0.20)",
      "--selection-text":     "#f97316",
    },
  },
};

const STORAGE_KEY = "timevora-mode";

// ─────────────────────────────────────────────
// CSS Variable Injection
// ─────────────────────────────────────────────
function applyModeToDOM(modeKey) {
  const theme = MODES[modeKey];
  if (!theme) return;

  const root = document.documentElement;

  // Inject every CSS custom property
  Object.entries(theme.vars).forEach(([prop, value]) => {
    root.style.setProperty(prop, value);
  });

  // Body font — applied directly so it works outside Tailwind too
  document.body.style.fontFamily = theme.vars["--font-body"];

  // ::selection — injected via a <style> tag so pseudo-elements work
  const selId = "timevora-selection-style";
  let selStyle = document.getElementById(selId);
  if (!selStyle) {
    selStyle = document.createElement("style");
    selStyle.id = selId;
    document.head.appendChild(selStyle);
  }
  selStyle.textContent = `
    ::selection {
      background: ${theme.vars["--selection-bg"]};
      color: ${theme.vars["--selection-text"]};
    }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: ${theme.vars["--scrollbar-track"]}; }
    ::-webkit-scrollbar-thumb {
      background: ${theme.vars["--scrollbar-thumb"]};
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover { opacity: 0.8; }
  `;

  // data-mode attribute on <html> — lets you write CSS like:
  // html[data-mode="developer"] .my-class { ... }
  root.setAttribute("data-mode", modeKey);
}

// ─────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────
const ModeContext = createContext(null);

export function ModeProvider({ children }) {
  const [mode, setModeState] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved && MODES[saved] ? saved : "student";
  });

  // Apply on first render
  useEffect(() => {
    applyModeToDOM(mode);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setMode = useCallback((newMode) => {
    if (!MODES[newMode]) return;
    setModeState(newMode);
    localStorage.setItem(STORAGE_KEY, newMode);
    applyModeToDOM(newMode);
  }, []);

  return (
    <ModeContext.Provider value={{ mode, setMode, themes: MODES }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error("useMode must be used inside ModeProvider");
  return ctx;
}