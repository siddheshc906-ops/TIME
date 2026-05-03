// src/components/Navigation.js
import { useState, useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Home,
  Clock,
  Bot,
  Menu,
  X,
  BarChart3,
  LayoutDashboard,
  LogOut,
  Check,
} from "lucide-react";
import { useMode } from "../context/ModeContext";

// ─────────────────────────────────────────────
// Theme Strip — color line + slide-down panel
// ─────────────────────────────────────────────
function ThemeStrip() {
  const { mode, setMode, themes } = useMode();
  const [open, setOpen] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const ref = useRef(null);
  const currentTheme = themes[mode];

  // First-time tooltip — shows 1.5s after login, disappears after 4s, never shows again
  useEffect(() => {
    const seen = localStorage.getItem("timevora-theme-hint");
    if (!seen) {
      const t = setTimeout(() => {
        setShowTooltip(true);
        setTimeout(() => {
          setShowTooltip(false);
          localStorage.setItem("timevora-theme-hint", "1");
        }, 4000);
      }, 1500);
      return () => clearTimeout(t);
    }
  }, []);

  // Close panel on outside click
  useEffect(() => {
    function handler(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} style={{ position: "absolute", bottom: 0, left: 0, right: 0 }}>

      {/* ── Glowing color strip — always visible, clickable ── */}
      <button
        onClick={() => {
          setOpen((o) => !o);
          setShowTooltip(false);
          localStorage.setItem("timevora-theme-hint", "1");
        }}
        aria-label="Switch theme"
        style={{
          display: "block",
          width: "100%",
          height: open ? 3 : 2,
          background: `linear-gradient(90deg, ${currentTheme.previewColor}66, ${currentTheme.previewColor}, ${currentTheme.previewColor}66)`,
          boxShadow: `0 0 8px ${currentTheme.previewColor}77`,
          border: "none",
          cursor: "pointer",
          padding: 0,
          transition: "height 0.2s ease, background 0.3s ease, box-shadow 0.3s ease",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.height = "3px"; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.height = "2px"; }}
      />

      {/* ── First-time tooltip ── */}
      {showTooltip && (
        <div
          style={{
            position: "fixed",
            top: 72,
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--card-bg)",
            border: `1px solid ${currentTheme.previewColor}44`,
            borderRadius: 99,
            padding: "7px 16px",
            fontSize: 12,
            fontWeight: 500,
            color: "var(--text-primary)",
            whiteSpace: "nowrap",
            zIndex: 9999,
            boxShadow: `0 4px 20px ${currentTheme.previewColor}33`,
            pointerEvents: "none",
            animation: "tvFadeUp 0.3s ease",
          }}
        >
          <span style={{ color: currentTheme.previewColor, marginRight: 6 }}>✦</span>
          Click the glowing line to switch themes
        </div>
      )}

      {/* ── Slide-down mode panel ── */}
      <div
        style={{
          position: "fixed",
          top: 64,
          left: 0,
          right: 0,
          zIndex: 49,
          background: `color-mix(in srgb, ${currentTheme.previewColor} 6%, var(--nav-bg, #0a0a0a))`,
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          boxShadow: `0 4px 24px rgba(0,0,0,0.4), 0 1px 0 ${currentTheme.previewColor}33`,
          maxHeight: open ? 80 : 0,
          opacity: open ? 1 : 0,
          overflow: "hidden",
          visibility: open ? "visible" : "hidden",
          transition: "max-height 0.28s cubic-bezier(0.4,0,0.2,1), opacity 0.2s ease, visibility 0s linear " + (open ? "0s" : "0.28s"),
          pointerEvents: open ? "auto" : "none",
        }}
      >
        <div
          style={{
            maxWidth: 1140,
            margin: "0 auto",
            padding: "12px 48px",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-muted)",
              marginRight: 8,
              whiteSpace: "nowrap",
            }}
          >
            Theme
          </span>

          {Object.entries(themes).map(([key, theme]) => {
            const isActive = mode === key;
            return (
              <button
                key={key}
                onClick={() => { setMode(key); setOpen(false); }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "6px 14px",
                  borderRadius: 99,
                  border: isActive
                    ? `1px solid ${theme.previewColor}66`
                    : "1px solid var(--card-border)",
                  background: isActive ? `${theme.previewColor}14` : "transparent",
                  cursor: "pointer",
                  fontSize: 12,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? theme.previewColor : "var(--text-secondary)",
                  transition: "all 0.15s ease",
                  whiteSpace: "nowrap",
                  outline: "none",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = `${theme.previewColor}10`;
                    e.currentTarget.style.borderColor = `${theme.previewColor}44`;
                    e.currentTarget.style.color = theme.previewColor;
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.borderColor = "var(--card-border)";
                    e.currentTarget.style.color = "var(--text-secondary)";
                  }
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: theme.previewColor,
                    flexShrink: 0,
                    boxShadow: isActive ? `0 0 0 2px ${theme.previewColor}33` : "none",
                  }}
                />
                <span>{theme.emoji}</span>
                <span>{theme.label}</span>
                {isActive && <Check size={12} style={{ color: theme.previewColor }} />}
              </button>
            );
          })}
        </div>


      </div>

      <style>{`
        @keyframes tvFadeUp {
          from { opacity: 0; transform: translateX(-50%) translateY(6px); }
          to   { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `}</style>
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Navigation
// ─────────────────────────────────────────────
export const Navigation = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const { mode, setMode, themes } = useMode();

  const token = localStorage.getItem("token");

  useEffect(() => {
    const handleFullscreenChange = () => {
      const isFull = !!(
        document.fullscreenElement ||
        document.webkitFullscreenElement ||
        document.mozFullScreenElement ||
        document.msFullscreenElement
      );
      setIsFullscreen(isFull);
    };

    handleFullscreenChange();
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("webkitfullscreenchange", handleFullscreenChange);
    document.addEventListener("mozfullscreenchange", handleFullscreenChange);
    document.addEventListener("MSFullscreenChange", handleFullscreenChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", handleFullscreenChange);
      document.removeEventListener("mozfullscreenchange", handleFullscreenChange);
      document.removeEventListener("MSFullscreenChange", handleFullscreenChange);
    };
  }, []);

  const navItems = [
    { path: "/",           label: "Home",        icon: Home            },
    { path: "/tasks",      label: "Planner",     icon: LayoutDashboard },
    { path: "/focus",      label: "Focus",       icon: Clock           },
    { path: "/ai-planner", label: "AI Planner",  icon: Bot             },
    { path: "/analytics",  label: "Performance", icon: BarChart3       },
  ];

  const isActive = (path) => {
    const current = location.pathname;
    if (current === path) return true;
    if (path === "/tasks" && ["/unified-planner", "/planner", "/dashboard", "/todo"].includes(current)) return true;
    if (path === "/analytics" && ["/performance"].includes(current)) return true;
    if (path === "/ai-planner" && ["/analyzer"].includes(current)) return true;
    return false;
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/");
  };

  const handleNavigation = (path) => {
    setMobileMenuOpen(false);
    navigate(path);
  };

  if (isFullscreen) return <div className="h-0" />;

  return (
    <>
      {/* ── Desktop Navbar ── */}
      <nav
        className="hidden md:flex fixed top-0 left-0 right-0 backdrop-blur-md border-b z-50"
        style={{
          background: "var(--nav-bg)",
          borderColor: "var(--nav-border)",
          transition: "background 300ms ease, border-color 300ms ease",
          overflow: "visible",
        }}
      >
        <div className="max-w-7xl mx-auto px-6 lg:px-12 w-full flex items-center justify-between h-16">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-hover))" }}
            >
              <span className="text-white font-bold text-sm">Tv</span>
            </div>
            <span className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              Timevora
            </span>
            <span
              className="ml-1 px-2 py-0.5 text-xs font-semibold rounded-full"
              style={{ background: "var(--badge-bg)", color: "var(--badge-text)" }}
            >
              Beta
            </span>
          </Link>

          {/* Right side */}
          {!token ? (
            <div className="flex items-center gap-4">
              <Link
                to="/login"
                className="font-medium transition"
                style={{ color: "var(--text-secondary)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
              >
                Login
              </Link>
              <Link
                to="/signup"
                className="px-4 py-2 rounded-full font-medium text-white transition"
                style={{ background: "var(--accent)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
              >
                Sign up free
              </Link>
            </div>
          ) : (
            <div className="flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.path);
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className="flex items-center gap-2 px-4 py-2 rounded-full font-medium transition-all"
                    style={{
                      background: active ? "var(--accent)" : "transparent",
                      color: active ? "#ffffff" : "var(--text-secondary)",
                      boxShadow: active ? "0 4px 14px var(--shadow-accent)" : "none",
                    }}
                    onMouseEnter={(e) => {
                      if (!active) {
                        e.currentTarget.style.background = "var(--accent-light)";
                        e.currentTarget.style.color = "var(--accent)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!active) {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.color = "var(--text-secondary)";
                      }
                    }}
                  >
                    <Icon size={18} />
                    <span className="hidden lg:inline">{item.label}</span>
                    <span className="lg:hidden">
                      {item.label === "Performance" ? "Stats"     :
                       item.label === "AI Planner"  ? "AI"        :
                       item.label === "Planner"     ? "Plan"      :
                       item.label}
                    </span>
                  </Link>
                );
              })}

              {/* Logout */}
              <button
                onClick={handleLogout}
                className="ml-1 px-3 py-1.5 text-sm rounded-full transition font-medium flex items-center gap-1"
                style={{ color: "#ef4444" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(239,68,68,0.08)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <LogOut size={16} />
                <span className="hidden lg:inline">Logout</span>
              </button>
            </div>
          )}
        </div>

        {/* Theme strip — only for logged-in users on desktop */}
        {token && <ThemeStrip />}
      </nav>

      {/* ── Mobile Navbar ── */}
      <nav
        className="md:hidden fixed top-0 left-0 right-0 backdrop-blur-md border-b z-50"
        style={{
          background: "var(--nav-bg)",
          borderColor: "var(--nav-border)",
          transition: "background 300ms ease, border-color 300ms ease",
          position: "relative",
        }}
      >
        <div className="px-4 flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-hover))" }}
            >
              <span className="text-white font-bold text-sm">Tv</span>
            </div>
            <span className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
              Timevora
            </span>
            <span
              className="ml-1 px-2 py-0.5 text-xs font-semibold rounded-full"
              style={{ background: "var(--badge-bg)", color: "var(--badge-text)" }}
            >
              Beta
            </span>
          </Link>

          {token && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                style={{ color: "var(--text-secondary)" }}
                className="p-2"
              >
                {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
            </div>
          )}
        </div>

        {/* Mobile color strip */}
        {token && (
          <div
            style={{
              position: "absolute",
              bottom: 0, left: 0, right: 0,
              height: 2,
              background: `linear-gradient(90deg, ${themes[mode].previewColor}66, ${themes[mode].previewColor}, ${themes[mode].previewColor}66)`,
              boxShadow: `0 0 6px ${themes[mode].previewColor}66`,
              transition: "background 0.3s ease",
            }}
          />
        )}

        {token && mobileMenuOpen && (
          <div
            className="absolute top-16 left-0 right-0 border-b shadow-lg max-h-[80vh] overflow-y-auto"
            style={{ background: "var(--nav-bg)", borderColor: "var(--nav-border)" }}
          >
            <div className="flex flex-col p-4 gap-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.path);
                return (
                  <button
                    key={item.path}
                    onClick={() => handleNavigation(item.path)}
                    className="flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all w-full text-left"
                    style={{
                      background: active ? "var(--accent)" : "transparent",
                      color: active ? "#ffffff" : "var(--text-secondary)",
                    }}
                  >
                    <Icon size={20} />
                    <span>{item.label}</span>
                  </button>
                );
              })}

              {/* Mobile theme picker inside hamburger menu */}
              <div style={{ borderTop: "1px solid var(--divider)", marginTop: 4, paddingTop: 12 }}>
                <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8, paddingLeft: 4 }}>
                  Theme
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {Object.entries(themes).map(([key, theme]) => {
                    const isActive = mode === key;
                    return (
                      <button
                        key={key}
                        onClick={() => { setMode(key); setMobileMenuOpen(false); }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "6px 12px",
                          borderRadius: 99,
                          border: isActive ? `1px solid ${theme.previewColor}66` : "1px solid var(--card-border)",
                          background: isActive ? `${theme.previewColor}14` : "transparent",
                          color: isActive ? theme.previewColor : "var(--text-secondary)",
                          fontSize: 12,
                          fontWeight: isActive ? 600 : 400,
                          cursor: "pointer",
                        }}
                      >
                        <span style={{ width: 7, height: 7, borderRadius: "50%", background: theme.previewColor, flexShrink: 0 }} />
                        <span>{theme.emoji}</span>
                        <span>{theme.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <button
                onClick={handleLogout}
                className="mt-2 px-4 py-3 text-left font-medium rounded-xl transition flex items-center gap-3"
                style={{ color: "#ef4444" }}
              >
                <LogOut size={20} />
                Logout
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* Spacer for fixed navbar */}
      <div className="h-16" />
    </>
  );
};
