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
  Palette,
  Check,
} from "lucide-react";
import { useMode, MODES } from "../context/ModeContext";

// ─────────────────────────────────────────────
// ModeSelector dropdown
// ─────────────────────────────────────────────
function ModeSelector() {
  const { mode, setMode, themes } = useMode();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on outside click
  useEffect(() => {
    function handler(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      {/* Trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        title="Switch visual mode"
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-all font-medium text-sm"
        style={{
          color: "var(--accent)",
          background: open ? "var(--accent-light)" : "transparent",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-light)")}
        onMouseLeave={(e) =>
          !open && (e.currentTarget.style.background = "transparent")
        }
      >
        <Palette size={16} />
        <span className="hidden lg:inline" style={{ color: "var(--accent)" }}>
          {themes[mode]?.emoji} {themes[mode]?.label}
        </span>
        <span className="lg:hidden" style={{ color: "var(--accent)" }}>
          {themes[mode]?.emoji}
        </span>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="absolute right-0 mt-2 w-52 rounded-2xl shadow-xl border overflow-hidden z-50"
          style={{
            background: "var(--card-bg)",
            borderColor: "var(--card-border)",
            backdropFilter: "blur(16px)",
            boxShadow: "0 8px 32px var(--shadow-accent)",
          }}
        >
          <div className="p-1.5">
            {Object.entries(themes).map(([key, theme]) => (
              <button
                key={key}
                onClick={() => {
                  setMode(key);
                  setOpen(false);
                }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-left"
                style={{
                  background: mode === key ? "var(--accent-light)" : "transparent",
                  color: "var(--text-primary)",
                }}
                onMouseEnter={(e) =>
                  mode !== key &&
                  (e.currentTarget.style.background = "var(--accent-light)")
                }
                onMouseLeave={(e) =>
                  mode !== key && (e.currentTarget.style.background = "transparent")
                }
              >
                {/* Preview dot */}
                <span
                  className="w-4 h-4 rounded-full flex-shrink-0"
                  style={{ background: theme.previewColor, boxShadow: `0 0 6px ${theme.previewColor}88` }}
                />
                <span className="flex items-center gap-1.5 text-sm font-medium flex-1">
                  <span>{theme.emoji}</span>
                  <span>{theme.label}</span>
                </span>
                {mode === key && (
                  <Check size={14} style={{ color: "var(--accent)" }} />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
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
        }}
      >
        <div className="max-w-7xl mx-auto px-6 lg:px-12 w-full flex items-center justify-between h-16">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
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

              {/* Mode Switcher */}
              <ModeSelector />

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
      </nav>

      {/* ── Mobile Navbar ── */}
      <nav
        className="md:hidden fixed top-0 left-0 right-0 backdrop-blur-md border-b z-50"
        style={{
          background: "var(--nav-bg)",
          borderColor: "var(--nav-border)",
          transition: "background 300ms ease, border-color 300ms ease",
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
              <ModeSelector />
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

      {/* Spacer */}
      <div className="h-16" />
    </>
  );
};
