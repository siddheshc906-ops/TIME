// frontend/src/components/Navigation.jsx
import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { 
  Home, 
  Clock, 
  Bot, 
  Menu, 
  X, 
  BarChart3,
  LayoutDashboard,
  LogOut
} from "lucide-react";

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

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, []);

  const navItems = [
    { path: "/",           label: "Home",        icon: Home          },
    { path: "/tasks",      label: "Planner",     icon: LayoutDashboard },
    { path: "/focus",      label: "Focus",       icon: Clock         },
    { path: "/ai-planner", label: "AI Planner",  icon: Bot           },
    { path: "/analytics",  label: "Performance", icon: BarChart3     },
  ];

  // ── FIX: also match legacy/redirect paths so highlight works correctly ──
  const isActive = (path) => {
    const current = location.pathname;
    if (current === path) return true;

    // Planner aliases
    if (path === "/tasks" && ["/unified-planner", "/planner", "/dashboard", "/todo"].includes(current)) return true;
    // Performance aliases
    if (path === "/analytics" && ["/performance"].includes(current)) return true;
    // AI Planner aliases
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

  if (isFullscreen) {
    return <div className="h-0" />;
  }

  return (
    <>
      {/* Desktop Navbar */}
      <nav className="hidden md:flex fixed top-0 left-0 right-0 bg-white/80 backdrop-blur-md border-b border-slate-100 z-50">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 w-full flex items-center justify-between h-16">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">Tv</span>
            </div>
            <span className="text-xl font-bold text-slate-900">Timevora</span>
          </Link>

          {/* Right Side */}
          {!token ? (
            <div className="flex items-center gap-4">
              <Link to="/login" className="text-slate-600 hover:text-violet-600 font-medium">
                Login
              </Link>
              <Link
                to="/signup"
                className="bg-violet-600 text-white px-4 py-2 rounded-full font-medium hover:bg-violet-700 transition"
              >
                Sign up
              </Link>
            </div>
          ) : (
            <div className="flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-full font-medium transition-all ${
                      isActive(item.path)
                        ? "bg-violet-600 text-white shadow-lg shadow-violet-500/30"
                        : "text-slate-600 hover:bg-violet-50 hover:text-violet-700"
                    }`}
                  >
                    <Icon size={18} />
                    <span className="hidden lg:inline">{item.label}</span>
                    <span className="lg:hidden">
                      {item.label === "Performance" ? "Stats" :
                       item.label === "AI Planner" ? "AI" :
                       item.label === "Planner" ? "Plan" :
                       item.label === "Focus" ? "Focus" :
                       item.label}
                    </span>
                  </Link>
                );
              })}

              {/* Logout */}
              <button
                onClick={handleLogout}
                className="ml-2 px-3 py-1.5 text-sm rounded-full text-red-500 hover:bg-red-50 transition font-medium flex items-center gap-1"
              >
                <LogOut size={16} />
                <span className="hidden lg:inline">Logout</span>
              </button>
            </div>
          )}
        </div>
      </nav>

      {/* Mobile Navbar */}
      <nav className="md:hidden fixed top-0 left-0 right-0 bg-white/90 backdrop-blur-md border-b border-slate-100 z-50">
        <div className="px-4 flex items-center justify-between h-16">

          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">Tv</span>
            </div>
            <span className="text-lg font-bold text-slate-900">Timevora</span>
          </Link>

          {token && (
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 text-slate-600 hover:text-violet-600"
            >
              {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          )}
        </div>

        {token && mobileMenuOpen && (
          <div className="absolute top-16 left-0 right-0 bg-white border-b border-slate-100 shadow-lg max-h-[80vh] overflow-y-auto">
            <div className="flex flex-col p-4 gap-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.path}
                    onClick={() => handleNavigation(item.path)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all w-full text-left ${
                      isActive(item.path)
                        ? "bg-violet-600 text-white"
                        : "text-slate-600 hover:bg-violet-50 hover:text-violet-700"
                    }`}
                  >
                    <Icon size={20} />
                    <span>{item.label}</span>
                  </button>
                );
              })}

              <button
                onClick={handleLogout}
                className="mt-2 px-4 py-3 text-left text-red-500 font-medium rounded-xl hover:bg-red-50 transition flex items-center gap-3"
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
