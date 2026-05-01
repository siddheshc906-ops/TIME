import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";

import { Navigation } from "./components/Navigation";
import ErrorBoundary from "./components/ErrorBoundary";

import { Landing } from "./pages/Landing";
import { FocusPage } from "./pages/FocusPage";
import { AnalyzerPage } from "./pages/AnalyzerPage";
import PerformancePage from "./pages/PerformancePage";
import AIPlannerPage from "./pages/AIPlannerPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import { UnifiedPlannerPage } from "./pages/UnifiedPlannerPage";
import { captureOAuthToken } from "./api/auth";

function ProtectedRoute({ children }) {
  const token = localStorage.getItem("token");

  if (!token) return <Navigate to="/login" />;

  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (Date.now() > (payload.exp * 1000) + 60000) {
      localStorage.removeItem("token");
      return <Navigate to="/login" />;
    }
  } catch (e) {
    console.error("Invalid token");
  }

  return children;
}

function App() {
  useEffect(() => {
    captureOAuthToken();
  }, []);

  return (
    <div className="App">
      <BrowserRouter>
        <Navigation />

        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* Redirects for old routes */}
          <Route path="/todo"      element={<Navigate to="/tasks"      replace />} />
          <Route path="/planner"   element={<Navigate to="/tasks"      replace />} />
          <Route path="/dashboard" element={<Navigate to="/tasks"      replace />} />
          <Route path="/analyzer"  element={<Navigate to="/ai-planner" replace />} />
          <Route path="/about"     element={<Navigate to="/"           replace />} />

          {/* Protected routes */}
          <Route
            path="/tasks"
            element={
              <ProtectedRoute>
                <ErrorBoundary><UnifiedPlannerPage /></ErrorBoundary>
              </ProtectedRoute>
            }
          />
          <Route
            path="/focus"
            element={
              <ProtectedRoute>
                <ErrorBoundary><FocusPage /></ErrorBoundary>
              </ProtectedRoute>
            }
          />
          <Route
            path="/ai-planner"
            element={
              <ProtectedRoute>
                <ErrorBoundary><AIPlannerPage /></ErrorBoundary>
              </ProtectedRoute>
            }
          />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <ErrorBoundary><PerformancePage /></ErrorBoundary>
              </ProtectedRoute>
            }
          />
          <Route
            path="/performance"
            element={
              <ProtectedRoute>
                <ErrorBoundary><PerformancePage /></ErrorBoundary>
              </ProtectedRoute>
            }
          />
          <Route
            path="/unified-planner"
            element={
              <ProtectedRoute>
                <ErrorBoundary><UnifiedPlannerPage /></ErrorBoundary>
              </ProtectedRoute>
            }
          />

          {/* 404 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
