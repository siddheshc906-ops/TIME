// frontend/src/pages/PerformancePage.jsx
// Redesigned — matches Timevora's warm/light aesthetic, professional & elevated

import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, AreaChart, Area
} from "recharts";
import {
  TrendingUp, Brain, Clock, Target, Award, Sparkles, Calendar,
  ChevronRight, Download, RefreshCw, AlertCircle, Zap, Sun,
  Loader2, ArrowRight, CheckCircle, Activity, MessageCircle,
  Send, X, Lightbulb, Flame, Eye, Star, Layers, BookOpen, Bot,
  ChevronDown
} from "lucide-react";
import BackgroundLayout from "../components/BackgroundLayout";
import ProductivityScoreCard from "../components/ProductivityScoreCard";
import { NewUserWelcome } from "../components/Onboarding/NewUserWelcome";
import { GrowingUserPrompt } from "../components/Onboarding/GrowingUserPrompt";
import { toast } from "react-hot-toast";
import { useNavigate } from "react-router-dom";

const BASE_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return { "Content-Type": "application/json", "Authorization": `Bearer ${token}` };
}

function decimalToTime(hour) {
  if (hour == null) return "";
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  const period = h < 12 ? "AM" : "PM";
  const display = h % 12 || 12;
  return `${display}:${String(m).padStart(2, "0")} ${period}`;
}

// ─────────────────────────────────────────────────────────────
// AI Guidance Chat
// ─────────────────────────────────────────────────────────────
function AIGuidanceChat({ userContext, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const messagesEndRef = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const isSchedulingRequest = (text) => {
    const lower = text.toLowerCase();
    return ["schedule", "plan my day", "create schedule", "add task", "book time",
      "plan for", "set up my", "i need to study", "i have to"].some(kw => lower.includes(kw));
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMessage = input.trim();
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setInput(""); setLoading(true); setShowWelcome(false);

    if (isSchedulingRequest(userMessage)) {
      setTimeout(() => {
        setMessages(prev => [...prev, {
          role: "assistant",
          content: "For scheduling, use the AI Planner — it's purpose-built for that. This space is for analysing your results and coaching.",
          redirectToPlanner: true,
        }]);
        setLoading(false);
      }, 400);
      return;
    }

    try {
      const response = await fetch(`${BASE_URL}/api/ai/guidance`, {
        method: "POST", headers: authHeaders(),
        body: JSON.stringify({ message: userMessage })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.success) {
        setMessages(prev => [...prev, {
          role: "assistant", content: data.message,
          contextUsed: data.context_used,
          advicePoints: data.advice_points || [],
          suggestions: data.suggestions || [],
        }]);
      } else {
        setMessages(prev => [...prev, { role: "assistant", content: data.message || "I'm having trouble right now.", isError: true }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Connection issue. Please try again.", isError: true }]);
    } finally { setLoading(false); }
  };

  const handleKeyPress = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } };
  const suggestedQuestions = [
    "How can I improve my focus?",
    "What's my biggest productivity gap?",
    "How do I study more effectively?",
    "How should I structure my week?",
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.35)", backdropFilter: "blur(6px)" }}>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.97 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        style={{
          width: "100%", maxWidth: 640, height: 600,
          display: "flex", flexDirection: "column",
          background: "white", borderRadius: 20,
          boxShadow: "0 32px 80px rgba(109,40,217,0.18), 0 8px 32px rgba(0,0,0,0.12)",
          overflow: "hidden", border: "1px solid rgba(109,40,217,0.12)",
        }}
      >
        <div style={{
          padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between",
          background: "linear-gradient(135deg, #6d28d9, #4f46e5)", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 10, background: "rgba(255,255,255,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Brain size={17} color="white" />
            </div>
            <div>
              <p style={{ color: "white", fontWeight: 700, fontSize: 14 }}>AI Performance Coach</p>
              <p style={{ color: "rgba(255,255,255,0.6)", fontSize: 11 }}>Powered by your data</p>
            </div>
          </div>
          <button onClick={onClose} style={{ width: 30, height: 30, borderRadius: 8, background: "rgba(255,255,255,0.15)", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <X size={15} color="white" />
          </button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "20px", background: "#fafaf9" }}>
          {showWelcome && messages.length === 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ paddingTop: 24 }}>
              <p style={{ fontWeight: 700, fontSize: 15, color: "#1e1b4b", marginBottom: 6 }}>What would you like to explore?</p>
              <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 20 }}>Ask anything about your performance, habits, or how to improve.</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {suggestedQuestions.map((q, i) => (
                  <button key={i} onClick={() => setInput(q)} style={{
                    padding: "8px 14px", borderRadius: 20, fontSize: 12, cursor: "pointer",
                    background: "white", border: "1px solid #e0e0f0", color: "#4f46e5", fontWeight: 500,
                    boxShadow: "0 1px 4px rgba(0,0,0,0.06)"
                  }}>{q}</button>
                ))}
              </div>
            </motion.div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {messages.map((msg, idx) => (
              <motion.div key={idx} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
                <div style={{
                  maxWidth: "80%", padding: "12px 16px",
                  borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
                  background: msg.role === "user" ? "linear-gradient(135deg, #6d28d9, #4f46e5)" : msg.isError ? "#fef2f2" : "white",
                  border: msg.role !== "user" ? (msg.isError ? "1px solid #fecaca" : "1px solid #e5e7eb") : "none",
                  boxShadow: msg.role !== "user" ? "0 2px 8px rgba(0,0,0,0.06)" : "none",
                }}>
                  <p style={{ fontSize: 13, lineHeight: 1.65, color: msg.role === "user" ? "white" : msg.isError ? "#dc2626" : "#374151", whiteSpace: "pre-wrap" }}>
                    {msg.content}
                  </p>
                  {msg.advicePoints?.length > 0 && (
                    <ul style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                      {msg.advicePoints.map((pt, i) => (
                        <li key={i} style={{ display: "flex", gap: 8, fontSize: 12, color: "#4b5563" }}>
                          <span style={{ color: "#7c3aed" }}>→</span>{pt}
                        </li>
                      ))}
                    </ul>
                  )}
                  {msg.redirectToPlanner && (
                    <a href="/ai-planner" style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "#4f46e5", textDecoration: "none", fontWeight: 600 }}>
                      Open AI Planner <ArrowRight size={11} />
                    </a>
                  )}
                  {msg.contextUsed && !msg.isError && (
                    <p style={{ marginTop: 8, fontSize: 10, color: "#9ca3af", display: "flex", alignItems: "center", gap: 4 }}>
                      <Sparkles size={9} /> Personalised from your data
                    </p>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: "flex", gap: 5, marginTop: 12 }}>
              {[0, 120, 240].map(d => (
                <div key={d} style={{ width: 7, height: 7, borderRadius: "50%", background: "#7c3aed", animation: `bounce 1s ${d}ms infinite` }} />
              ))}
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div style={{ padding: "14px 18px", borderTop: "1px solid #f0f0f5", background: "white", flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
            <textarea value={input} onChange={e => setInput(e.target.value)} onKeyPress={handleKeyPress}
              placeholder="Ask your coach..." rows={1}
              style={{
                flex: 1, resize: "none", background: "#f9f9fc", border: "1.5px solid #e5e7eb",
                borderRadius: 12, padding: "11px 14px", fontSize: 13, color: "#1f2937",
                outline: "none", maxHeight: 100, fontFamily: "inherit",
              }}
            />
            <button onClick={sendMessage} disabled={loading || !input.trim()} style={{
              width: 40, height: 40, borderRadius: 12,
              background: "linear-gradient(135deg, #7c3aed, #4f46e5)",
              border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              opacity: (loading || !input.trim()) ? 0.4 : 1, flexShrink: 0
            }}>
              <Send size={15} color="white" />
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Insight Card
// ─────────────────────────────────────────────────────────────
function InsightCard({ icon: Icon, label, observation, detail, accent = "violet", delay = 0, metric, metricLabel }) {
  const palette = {
    violet: { bg: "#f5f3ff", border: "#ddd6fe", icon: "#7c3aed", label: "#7c3aed", metricColor: "#6d28d9" },
    amber:  { bg: "#fffbeb", border: "#fde68a", icon: "#d97706", label: "#b45309", metricColor: "#92400e" },
    emerald:{ bg: "#ecfdf5", border: "#a7f3d0", icon: "#059669", label: "#047857", metricColor: "#065f46" },
    rose:   { bg: "#fff1f2", border: "#fecdd3", icon: "#e11d48", label: "#be123c", metricColor: "#9f1239" },
    sky:    { bg: "#f0f9ff", border: "#bae6fd", icon: "#0284c7", label: "#0369a1", metricColor: "#075985" },
    indigo: { bg: "#eef2ff", border: "#c7d2fe", icon: "#4f46e5", label: "#4338ca", metricColor: "#3730a3" },
  };
  const c = palette[accent] || palette.violet;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: "spring", stiffness: 220, damping: 24 }}
      whileHover={{ y: -2, boxShadow: "0 8px 28px rgba(109,40,217,0.10)", transition: { duration: 0.18 } }}
      style={{
        background: "white", border: "1px solid #ede9f4",
        borderRadius: 14, padding: "20px 22px",
        boxShadow: "0 1px 6px rgba(0,0,0,0.05)",
        position: "relative", overflow: "hidden",
      }}
    >
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: c.icon, borderRadius: "14px 0 0 14px", opacity: 0.7 }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: c.bg, display: "flex", alignItems: "center", justifyContent: "center", border: `1px solid ${c.border}` }}>
            <Icon size={14} color={c.icon} />
          </div>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.09em", textTransform: "uppercase", color: c.label }}>{label}</span>
        </div>
        {metric != null && (
          <div style={{ textAlign: "right" }}>
            <p style={{ fontSize: 22, fontWeight: 800, color: c.metricColor, lineHeight: 1, letterSpacing: "-0.03em" }}>{metric}</p>
            {metricLabel && <p style={{ fontSize: 10, color: "#9ca3af", marginTop: 2 }}>{metricLabel}</p>}
          </div>
        )}
      </div>
      <p style={{ fontSize: 14, fontWeight: 600, color: "#111827", lineHeight: 1.45, marginBottom: detail ? 7 : 0 }}>{observation}</p>
      {detail && <p style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.55 }}>{detail}</p>}
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────
// Section Panel
// ─────────────────────────────────────────────────────────────
function AnalysisPanel({ title, subtitle, icon: Icon, barColor, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 100, damping: 20 }}
      style={{
        background: "white", borderRadius: 20,
        boxShadow: "0 2px 16px rgba(109,40,217,0.07), 0 1px 4px rgba(0,0,0,0.05)",
        border: "1px solid rgba(109,40,217,0.09)", overflow: "hidden",
      }}
    >
      <div style={{ background: barColor, padding: "16px 24px", display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(255,255,255,0.22)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon size={18} color="white" />
        </div>
        <div>
          <p style={{ color: "white", fontWeight: 700, fontSize: 15 }}>{title}</p>
          {subtitle && <p style={{ color: "rgba(255,255,255,0.72)", fontSize: 12, marginTop: 1 }}>{subtitle}</p>}
        </div>
      </div>
      <div style={{ padding: "24px" }}>{children}</div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────
// KPI Stat Tile
// ─────────────────────────────────────────────────────────────
function StatTile({ value, label, sub, accentColor }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2, transition: { duration: 0.15 } }}
      style={{
        background: "white", borderRadius: 14, padding: "20px 22px",
        boxShadow: "0 1px 8px rgba(109,40,217,0.07)",
        border: "1px solid rgba(109,40,217,0.09)",
      }}
    >
      <p style={{ fontSize: 30, fontWeight: 800, color: "#111827", letterSpacing: "-0.04em", lineHeight: 1 }}>{value}</p>
      <p style={{ fontSize: 12, fontWeight: 700, color: accentColor, marginTop: 8 }}>{label}</p>
      {sub && <p style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>{sub}</p>}
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────
// Chart Tooltip
// ─────────────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "white", border: "1px solid #e5e7eb", borderRadius: 10,
      padding: "10px 14px", fontSize: 12, color: "#374151",
      boxShadow: "0 4px 16px rgba(0,0,0,0.10)"
    }}>
      <p style={{ marginBottom: 4, color: "#9ca3af", fontSize: 11 }}>{label}</p>
      {payload.map((p, i) => <p key={i} style={{ color: p.color || "#7c3aed", fontWeight: 700 }}>{p.name}: {p.value}</p>)}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────
export default function PerformancePage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [userState, setUserState] = useState(() => {
    return localStorage.getItem('tv_userState') || 'new';
  });
  const [taskCount, setTaskCount] = useState(0);
  const [chartData, setChartData] = useState([]);
  const [patterns, setPatterns] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [timeRange, setTimeRange] = useState(30);
  const [training, setTraining] = useState(false);
  const [productivityScore, setProductivityScore] = useState(null);
  const [error, setError] = useState(null);
  const [hasDismissedPrompt, setHasDismissedPrompt] = useState(false);
  const [chronotype, setChronotype] = useState(null);
  const [aiInsights, setAiInsights] = useState([]);
  const [categoryAccuracy, setCategoryAccuracy] = useState({});
  const [feedbackSummary, setFeedbackSummary] = useState(null);
  const [focusStats, setFocusStats] = useState(null);
  const [plannerStats, setPlannerStats] = useState(null);
  const [showGuidanceChat, setShowGuidanceChat] = useState(false);

  // ✅ FIX: Persist userState so backend sleep doesn't reset to 'new'
  function updateUserState(state) {
    if (state !== 'new') {
      localStorage.setItem('tv_userState', state);
    }
    setUserState(state);
  }

  useEffect(() => { fetchAllData(); }, [timeRange]);

  const fetchAllData = async () => {
    setLoading(true); setError(null);
    try {
      // Run all fetches in parallel, collect key counts for userState decision
      const [taskCount, focusData, plannerData, feedbackData] = await Promise.all([
        fetchTasks(),
        fetchFocusStats(),
        fetchPlannerStats(),
        fetchFeedbackData(),
      ]);
      // Run remaining fetches that don't affect userState
      await Promise.all([
        fetchAccuracy(), fetchPatterns(), fetchAnalytics(),
        fetchProductivityScore(), fetchChronotypeData(),
        fetchAIInsightsData(), fetchProductivityProfile(),
      ]);

      // Determine userState from ALL pages — not just Planner task count
      const hasPlanner   = (taskCount || 0) > 0;
      const hasFocus     = (focusData?.totalMinutes || 0) > 0 || (focusData?.sessionCount || 0) > 0;
      const hasAIPlanner = (plannerData?.planCount || 0) > 0;
      const hasFeedback  = (feedbackData?.total || 0) > 0;

      // ✅ FIX: If backend returned null (failed/sleeping), don't reset userState
      if (taskCount === null) {
        // Backend is sleeping — keep whatever userState we have from localStorage
      } else if (!hasPlanner && !hasFocus && !hasAIPlanner && !hasFeedback && taskCount === 0) {
        // Only set 'new' if localStorage also doesn't have a saved state
        if (!localStorage.getItem('tv_userState')) {
          updateUserState('new');
        }
      } else if ((taskCount || 0) < 5) {
        updateUserState('beginner');
      } else if ((taskCount || 0) < 15) {
        updateUserState('intermediate');
      } else {
        updateUserState('active');
      }
    } catch (err) {
      setError("Failed to load performance data");
      toast.error("Failed to load performance data");
    } finally { setLoading(false); }
  };

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/tasks`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        const count = Array.isArray(data) ? data.filter(t => !t.is_deleted).length : 0;
        setTaskCount(count);
        return count;
      }
      return null; // ✅ FIX: null means backend failed, not genuinely empty
    } catch (err) { console.error(err); return null; }
  };

  const fetchAccuracy = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/ml/accuracy`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        if (data.by_difficulty) {
          const formatted = Object.entries(data.by_difficulty).map(([difficulty, accuracy]) => ({
            difficulty, accuracy: Math.round(accuracy * 100),
          }));
          setChartData(formatted);
        }
      }
    } catch (err) { console.error(err); }
  };

  const fetchPatterns = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/ml/patterns`, { headers: authHeaders() });
      if (res.ok) { const data = await res.json(); setPatterns(data); }
    } catch (err) { console.error(err); }
  };

  const fetchAnalytics = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/analytics?days=${timeRange}`, { headers: authHeaders() });
      if (res.ok) { const data = await res.json(); setAnalytics(data); }
    } catch (err) { console.error(err); }
  };

  const fetchProductivityScore = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/productivity-score`, { headers: authHeaders() });
      if (res.ok) { const data = await res.json(); setProductivityScore(data); }
    } catch { }
  };

  const fetchChronotypeData = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/ai/chronotype`, { headers: authHeaders() });
      if (res.ok) { const data = await res.json(); if (data.success) setChronotype(data); }
    } catch { }
  };

  const fetchAIInsightsData = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/ai/insights`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      if (data.success && data.insights) setAiInsights(data.insights);
    } catch { }
  };

  const fetchFeedbackData = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/task-feedback`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      setFeedbackSummary(data.summary);
      if (data.history?.length > 0) {
        const categoryMap = {};
        data.history.forEach(record => {
          const cat = record.category || 'general';
          const ratio = record.accuracy_ratio || 1;
          if (!categoryMap[cat]) categoryMap[cat] = { total: 0, count: 0 };
          categoryMap[cat].total += ratio; categoryMap[cat].count += 1;
        });
        const fc = {};
        Object.entries(categoryMap).forEach(([cat, { total, count }]) => { fc[cat] = (total / count).toFixed(2); });
        setCategoryAccuracy(fc);
      }
      return { total: data.history?.length || 0 };
    } catch { return { total: 0 }; }
  };

  const fetchProductivityProfile = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/ai/productivity-profile`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      if (data.success || data.ready) {
        if (data.chronotype && !chronotype) setChronotype(data.chronotype);
      }
    } catch { }
  };

  const fetchFocusStats = async () => {
    try {
      // Use user-scoped key so different accounts don't share focus stats
      let userId = 'default';
      try {
        const token = localStorage.getItem("token");
        if (token) userId = JSON.parse(atob(token.split('.')[1])).sub || 'default';
      } catch {}
      const storedStats = localStorage.getItem(`focusStats_${userId}`) || localStorage.getItem("focusStats");
      const localData = storedStats ? JSON.parse(storedStats) : null;
      if (localData) setFocusStats(localData);

      // Also read from backend task-feedback for AI Planner recorded sessions
      const res = await fetch(`${BASE_URL}/api/task-feedback`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        const history = data.history || [];
        const focusSessions = history.filter(h => h.name === "Focus Session" || h.name?.includes("Focus"));
        const totalMinutes = focusSessions.reduce((sum, s) => sum + (s.actualTime || s.aiTime || 0) * 60, 0);
        const merged = {
          totalMinutes: Math.max(totalMinutes, localData?.totalMinutes || 0),
          sessionCount: Math.max(focusSessions.length, localData?.sessions?.length || localData?.sessionCount || 0),
          streak: localData?.streak || 0,
          sessions: localData?.sessions || [],
        };
        setFocusStats(merged);
        return merged;
      }
      return localData;
    } catch { return null; }
  };

  const fetchPlannerStats = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/daily-plans`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        const plans = Array.isArray(data) ? data : data.plans || [];
        const totalScheduled = plans.reduce((sum, p) => sum + (p.schedule?.length || p.task_count || 0), 0);
        const result = { planCount: plans.length, totalScheduled, recentPlan: plans[0] || null };
        setPlannerStats(result);
        return result;
      }
      return { planCount: 0, totalScheduled: 0 };
    } catch { return { planCount: 0, totalScheduled: 0 }; }
  };

  const trainModel = async () => {
    setTraining(true);
    toast.loading("Training AI model...", { id: "train" });
    try {
      const res = await fetch(`${BASE_URL}/api/ml/train`, { method: "POST", headers: authHeaders() });
      const data = await res.json();
      if (data.success) { toast.success("Model updated.", { id: "train" }); fetchAllData(); }
      else toast.error("Training failed", { id: "train" });
    } catch { toast.error("Training error", { id: "train" }); }
    finally { setTraining(false); }
  };

  const exportData = () => {
    const dataStr = JSON.stringify({ analytics, patterns, chartData, productivityScore, chronotype, aiInsights, focusStats, plannerStats }, null, 2);
    const link = document.createElement('a');
    link.setAttribute('href', 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr));
    link.setAttribute('download', `timevora-analytics-${new Date().toISOString().slice(0, 10)}.json`);
    link.click();
    toast.success("Export complete.");
  };

  // ── Observation builders ──────────────────────────────────

  const buildFocusObs = () => {
    const obs = [];
    const totalMins = focusStats?.totalMinutes || 0;
    const streak = focusStats?.streak || 0;
    const sessions = focusStats?.sessionCount || focusStats?.sessions?.length || 0;
    const hrs = Math.floor(totalMins / 60); const mins = totalMins % 60;
    if (totalMins > 0) obs.push({ icon: Clock, accent: "violet", label: "Deep Work", observation: `${hrs > 0 ? `${hrs}h ${mins}m` : `${mins} minutes`} of intentional focus logged.`, detail: hrs >= 10 ? "Substantial deep work hours — this is where compounding begins." : "Every session contributes. Keep building.", metric: hrs > 0 ? `${hrs}h` : `${mins}m`, metricLabel: "total focus", delay: 0.05 });
    if (streak > 0) obs.push({ icon: Flame, accent: "amber", label: "Streak", observation: `${streak} consecutive day${streak !== 1 ? 's' : ''} of consistent work.`, detail: streak >= 7 ? "A week-long streak signals identity, not just habit." : "Momentum is building. Protect this.", metric: streak, metricLabel: "day streak", delay: 0.10 });
    if (sessions > 0) obs.push({ icon: Target, accent: "emerald", label: "Sessions", observation: `${sessions} focus session${sessions !== 1 ? 's' : ''} tracked.`, detail: sessions >= 20 ? "Twenty sessions makes this non-negotiable." : "Consistency over intensity.", metric: sessions, metricLabel: "completed", delay: 0.15 });
    if (obs.length === 0) obs.push({ icon: Eye, accent: "sky", label: "No Data Yet", observation: "No focus sessions recorded.", detail: "Open the Focus page and start your first timed session.", delay: 0.05 });
    return obs;
  };

  const buildPlannerObs = () => {
    const obs = [];
    const completed = analytics?.overview?.completed || feedbackSummary?.total_feedbacks || 0;
    const rate = analytics?.overview?.completion_rate;
    const bestDay = patterns?.best_day;
    const peakHours = patterns?.peak_hours;
    if (completed > 0) obs.push({ icon: CheckCircle, accent: "emerald", label: "Task Execution", observation: `${completed} task${completed !== 1 ? 's' : ''} completed and tracked.`, detail: rate ? `${rate.toFixed(0)}% completion rate. ${rate >= 80 ? "Execution at this level is rare." : "There's room to close the gap."}` : null, metric: completed, metricLabel: "completed", delay: 0.05 });
    if (bestDay) obs.push({ icon: Star, accent: "amber", label: "Peak Day", observation: `${bestDay} is your highest-output day, consistently.`, detail: "Weight your most demanding work here.", delay: 0.10 });
    if (peakHours?.length > 0) obs.push({ icon: Zap, accent: "violet", label: "Peak Hours", observation: `Flow state occurs around ${peakHours.map(h => decimalToTime(h)).join(" and ")}.`, detail: "Protect this window. Eliminate interruptions.", delay: 0.15 });
    if (obs.length === 0) obs.push({ icon: BookOpen, accent: "indigo", label: "Awaiting Data", observation: "Complete tasks to unlock planning insights.", detail: "Each task teaches the system your patterns.", delay: 0.05 });
    return obs;
  };

  const buildAIPlannerObs = () => {
    const obs = [];
    const aiAccuracy = feedbackSummary?.avg_accuracy;
    const planCount = plannerStats?.planCount || 0;
    if (planCount > 0) obs.push({ icon: Bot, accent: "indigo", label: "AI Scheduling", observation: `${planCount} AI-generated schedule${planCount !== 1 ? 's' : ''} — ${plannerStats.totalScheduled || 0} tasks planned.`, detail: "You're offloading planning cognitive load to AI. Smart.", metric: planCount, metricLabel: "schedules", delay: 0.05 });
    if (aiAccuracy != null) { const pct = Math.round(aiAccuracy * 100); obs.push({ icon: Brain, accent: pct >= 80 ? "emerald" : pct >= 60 ? "amber" : "rose", label: "Prediction Accuracy", observation: `Time estimation accuracy: ${pct}%.`, detail: pct >= 85 ? "The model has genuinely learned your work patterns." : "More data improves this further.", metric: `${pct}%`, metricLabel: "accuracy", delay: 0.10 }); }
    if (chronotype?.type) obs.push({ icon: Sun, accent: "amber", label: "Chronotype", observation: `Identified as: ${chronotype.type}.`, detail: `Demanding tasks are auto-scheduled during your ${chronotype.peak_slot || "peak"} window.`, delay: 0.15 });
    if (obs.length === 0) obs.push({ icon: Calendar, accent: "sky", label: "No Schedules Yet", observation: "No AI schedules generated.", detail: "Open the AI Planner to generate your first intelligent schedule.", delay: 0.05 });
    return obs;
  };

  const buildOverallObs = () => {
    const obs = [];
    const score = productivityScore?.score || patterns?.productivity_score;
    const focusMins = focusStats?.totalMinutes || 0;
    const completed = analytics?.overview?.completed || 0;
    const planCount = plannerStats?.planCount || 0;
    const activeAreas = [focusMins > 0, completed > 0, planCount > 0].filter(Boolean).length;
    if (activeAreas === 3) obs.push({ icon: Sparkles, accent: "violet", label: "System Coverage", observation: "All three productivity dimensions are active.", detail: "Focus, Planning, and AI scheduling working together — this is where compounding begins.", delay: 0.05 });
    else if (activeAreas === 2) obs.push({ icon: TrendingUp, accent: "amber", label: "Coverage Gap", observation: "Two of three dimensions are active.", detail: `Add ${focusMins === 0 ? "focus sessions" : planCount === 0 ? "AI planning" : "task tracking"} to unlock compounding performance effects.`, delay: 0.05 });
    else obs.push({ icon: Activity, accent: "sky", label: "Early Stage", observation: "System is in observation mode.", detail: "Each action — session, task, or plan — adds intelligence to your model.", delay: 0.05 });
    if (score != null) obs.push({ icon: Award, accent: score >= 70 ? "emerald" : score >= 40 ? "amber" : "rose", label: "Performance Index", observation: `Performance index: ${score} / 100.`, detail: score >= 80 ? "Operating at a level most never reach." : "Foundation is forming. Focus on daily execution.", metric: score, metricLabel: "index", delay: 0.10 });
    if (aiInsights.length > 0) { const text = aiInsights[0].text || aiInsights[0]; obs.push({ icon: Lightbulb, accent: "indigo", label: "Key Finding", observation: text, detail: "Derived from your behavioural patterns — not generic heuristics.", delay: 0.15 }); }
    return obs;
  };

  // ─────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────

  if (loading) return (
    <BackgroundLayout>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <div style={{ textAlign: "center" }}>
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
            style={{ width: 36, height: 36, border: "2.5px solid #ede9fe", borderTopColor: "#7c3aed", borderRadius: "50%", margin: "0 auto 14px" }}
          />
          <p style={{ color: "#9ca3af", fontSize: 13 }}>Loading analytics…</p>
        </div>
      </div>
    </BackgroundLayout>
  );

  if (error) return (
    <BackgroundLayout>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <div style={{ textAlign: "center" }}>
          <AlertCircle color="#e11d48" size={36} style={{ margin: "0 auto 12px" }} />
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "#111827", marginBottom: 8 }}>Failed to load data</h2>
          <p style={{ color: "#6b7280", marginBottom: 20 }}>{error}</p>
          <button onClick={fetchAllData} style={{ padding: "10px 24px", background: "linear-gradient(135deg, #7c3aed, #4f46e5)", color: "white", border: "none", borderRadius: 10, cursor: "pointer", fontSize: 14, fontWeight: 600 }}>Retry</button>
        </div>
      </div>
    </BackgroundLayout>
  );

  if (userState === 'new') return (
    <BackgroundLayout>
      <NewUserWelcome />
      <div style={{
        maxWidth: 560,
        margin: "-16px auto 40px",
        background: "rgba(109,40,217,0.07)",
        border: "1px solid rgba(109,40,217,0.18)",
        borderRadius: 14,
        padding: "14px 20px",
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
      }}>
        <span style={{ fontSize: 20 }}>💡</span>
        <div>
          <p style={{ fontSize: 13, fontWeight: 700, color: "#4c1d95", marginBottom: 3 }}>
            How Performance tracking works
          </p>
          <p style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.6 }}>
            Add tasks in the Planner, complete them, and your AI performance insights will unlock automatically. The more you use Timevora, the smarter your analysis gets.
          </p>
        </div>
      </div>
    </BackgroundLayout>
  );

  const focusObs = buildFocusObs();
  const plannerObs = buildPlannerObs();
  const aiPlannerObs = buildAIPlannerObs();
  const overallObs = buildOverallObs();
  const totalFocusHrs = Math.floor((focusStats?.totalMinutes || 0) / 60);
  const aiAccuracyPct = feedbackSummary?.avg_accuracy ? Math.round(feedbackSummary.avg_accuracy * 100) : null;

  return (
    <BackgroundLayout>
      <AnimatePresence>
        {showGuidanceChat && (
          <AIGuidanceChat userContext={{ taskCount, patterns, chronotype, feedbackSummary }} onClose={() => setShowGuidanceChat(false)} />
        )}
      </AnimatePresence>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ maxWidth: 1020, margin: "0 auto", padding: "48px 24px 72px" }}>

        {/* ── Header ─────────────────────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: -14 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: 40 }}>

          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "5px 13px", background: "rgba(109,40,217,0.08)", border: "1px solid rgba(109,40,217,0.18)", borderRadius: 100, marginBottom: 16 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#7c3aed", display: "inline-block" }} />
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.09em", color: "#7c3aed", textTransform: "uppercase" }}>Live Analysis</span>
          </div>

          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 20, marginBottom: 28 }}>
            <div>
              <h1 style={{ fontSize: 38, fontWeight: 800, color: "#0f0a23", letterSpacing: "-0.035em", lineHeight: 1.1, margin: 0 }}>
                Your Performance,<br />
                <span style={{ background: "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Decoded</span>
              </h1>
              <p style={{ color: "#6b7280", marginTop: 12, fontSize: 14, maxWidth: 460, lineHeight: 1.65 }}>
                Every session, task, and plan builds a model calibrated to your specific patterns — not population averages.
              </p>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ position: "relative" }}>
                <select value={timeRange} onChange={e => setTimeRange(parseInt(e.target.value))} style={{ appearance: "none", padding: "9px 34px 9px 14px", borderRadius: 10, fontSize: 13, background: "white", border: "1px solid #e5e7eb", color: "#374151", cursor: "pointer", outline: "none", fontWeight: 500, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
                  <option value={7}>Last 7 days</option>
                  <option value={30}>Last 30 days</option>
                  <option value={90}>Last 90 days</option>
                </select>
                <ChevronDown size={13} color="#9ca3af" style={{ position: "absolute", right: 11, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} />
              </div>

              <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={() => setShowGuidanceChat(true)} style={{ padding: "9px 16px", background: "linear-gradient(135deg, #7c3aed, #4f46e5)", border: "none", borderRadius: 10, color: "white", fontSize: 13, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 7, boxShadow: "0 2px 10px rgba(109,40,217,0.3)" }}>
                <MessageCircle size={14} /> AI Coach
              </motion.button>

              <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={trainModel} disabled={training || taskCount < 5} style={{ padding: "9px 16px", background: "white", border: "1px solid #e5e7eb", borderRadius: 10, color: taskCount < 5 ? "#d1d5db" : "#374151", fontSize: 13, fontWeight: 500, cursor: taskCount < 5 ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 7, boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}>
                <Brain size={14} className={training ? "animate-pulse" : ""} />
                {training ? "Training…" : taskCount < 5 ? `Need ${5 - taskCount} more` : "Retrain"}
              </motion.button>

              <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={exportData} style={{ padding: "9px 14px", background: "white", border: "1px solid #e5e7eb", borderRadius: 10, color: "#6b7280", fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", gap: 7, boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}>
                <Download size={14} /> Export
              </motion.button>

              <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={fetchAllData} style={{ padding: "9px 14px", background: "white", border: "1px solid #e5e7eb", borderRadius: 10, color: "#6b7280", fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", gap: 7, boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}>
                <RefreshCw size={14} /> Refresh
              </motion.button>
            </div>
          </div>

          {/* KPI strip */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            {[
              { value: `${totalFocusHrs}h`, label: "Focus Hours", sub: "lifetime total", accentColor: "#d97706" },
              { value: analytics?.overview?.completed || 0, label: "Tasks Completed", sub: `of ${taskCount} logged`, accentColor: "#059669" },
              { value: plannerStats?.planCount || 0, label: "AI Schedules", sub: "generated", accentColor: "#7c3aed" },
              { value: aiAccuracyPct ? `${aiAccuracyPct}%` : "—", label: "Prediction Fit", sub: "AI accuracy", accentColor: "#0284c7" },
            ].map((s, i) => <StatTile key={i} {...s} />)}
          </div>
        </motion.div>

        {/* Growing user prompt */}
        {userState !== 'active' && !hasDismissedPrompt && (
          <div style={{ marginBottom: 28 }}>
            <GrowingUserPrompt taskCount={taskCount} onDismiss={() => setHasDismissedPrompt(true)} />
          </div>
        )}

        {/* ── Analysis Sections ─────────────────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

          <AnalysisPanel title="Focus Sessions" subtitle="What your timer data reveals about your concentration patterns" icon={Flame} barColor="linear-gradient(135deg, #f59e0b, #ef4444)">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
              {focusObs.map((obs, i) => <InsightCard key={i} {...obs} />)}
            </div>
          </AnalysisPanel>

          <AnalysisPanel title="Task Planner" subtitle="Patterns extracted from your planning and execution behaviour" icon={BookOpen} barColor="linear-gradient(135deg, #7c3aed, #4f46e5)">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12, marginBottom: 20 }}>
              {plannerObs.map((obs, i) => <InsightCard key={i} {...obs} />)}
            </div>
            {taskCount >= 5 && analytics?.daily && analytics.daily.length > 0 && (
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 14 }}>Completion curve — last 14 days</p>
                <ResponsiveContainer width="100%" height={155}>
                  <AreaChart data={analytics.daily.slice(-14)}>
                    <defs>
                      <linearGradient id="plannerGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="date" stroke="#e5e7eb" tick={{ fontSize: 10, fill: "#9ca3af" }} />
                    <YAxis stroke="#e5e7eb" tick={{ fontSize: 10, fill: "#9ca3af" }} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area type="monotone" dataKey="completed" name="Completed" stroke="#7c3aed" fill="url(#plannerGrad)" strokeWidth={2} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
            {taskCount >= 5 && Object.keys(categoryAccuracy).length > 0 && (
              <div style={{ marginTop: 22 }}>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 14 }}>Accuracy by category</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {Object.entries(categoryAccuracy).map(([cat, acc]) => {
                    const pct = Math.round(parseFloat(acc) * 100);
                    const color = pct >= 85 ? "#059669" : pct >= 70 ? "#d97706" : "#e11d48";
                    return (
                      <div key={cat}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                          <span style={{ fontSize: 12, color: "#6b7280", textTransform: "capitalize" }}>{cat}</span>
                          <span style={{ fontSize: 12, fontWeight: 700, color }}>{pct}%</span>
                        </div>
                        <div style={{ height: 4, background: "#f3f4f6", borderRadius: 4, overflow: "hidden" }}>
                          <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.8 }} style={{ height: "100%", background: color, borderRadius: 4 }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </AnalysisPanel>

          <AnalysisPanel title="AI Planner" subtitle="What the intelligent scheduler has learned about your work style" icon={Bot} barColor="linear-gradient(135deg, #0ea5e9, #4f46e5)">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12, marginBottom: 20 }}>
              {aiPlannerObs.map((obs, i) => <InsightCard key={i} {...obs} />)}
            </div>
            {taskCount >= 5 && chartData.length > 0 && (
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 14 }}>Prediction accuracy by difficulty</p>
                <ResponsiveContainer width="100%" height={150}>
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="difficulty" stroke="#e5e7eb" tick={{ fontSize: 11, fill: "#9ca3af" }} />
                    <YAxis tickFormatter={v => `${v}%`} stroke="#e5e7eb" tick={{ fontSize: 10, fill: "#9ca3af" }} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="accuracy" name="Accuracy" fill="#4f46e5" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {/* ── Chronotype Card — prominent, personalised ── */}
            {chronotype && chronotype.ready !== false && taskCount >= 5 ? (
              <div style={{
                marginTop: 20,
                borderRadius: 16,
                overflow: "hidden",
                border: "1px solid #e0e7ff",
                boxShadow: "0 4px 24px rgba(99,102,241,0.08)",
              }}>
                {/* Header strip */}
                <div style={{
                  background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
                  padding: "14px 20px",
                  display: "flex", alignItems: "center", gap: 12,
                }}>
                  <span style={{ fontSize: 32 }}>{chronotype.emoji || "🧠"}</span>
                  <div>
                    <p style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 2 }}>
                      Your Chronotype
                    </p>
                    <p style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>
                      {chronotype.type || "Analyzing…"}
                    </p>
                  </div>
                  <div style={{ marginLeft: "auto", textAlign: "right" }}>
                    <p style={{ fontSize: 10, color: "rgba(255,255,255,0.6)", marginBottom: 3 }}>Peak window</p>
                    <p style={{ fontSize: 14, fontWeight: 700, color: "#a5f3fc", textTransform: "capitalize", background: "rgba(255,255,255,0.15)", padding: "3px 10px", borderRadius: 8 }}>
                      {chronotype.peak || chronotype.peak_slot || "—"}
                    </p>
                  </div>
                </div>
                {/* Body */}
                <div style={{ background: "#fafafe", padding: "14px 20px", display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center" }}>
                  <p style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.6, flex: 1, minWidth: 220 }}>
                    {chronotype.description || "Model is learning your energy pattern."}
                  </p>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <div style={{ background: "#ede9fe", borderRadius: 10, padding: "8px 14px", textAlign: "center" }}>
                      <p style={{ fontSize: 10, color: "#7c3aed", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em" }}>Best for</p>
                      <p style={{ fontSize: 12, color: "#1e1b4b", fontWeight: 600, marginTop: 2 }}>Deep work</p>
                    </div>
                    <div style={{ background: "#ecfdf5", borderRadius: 10, padding: "8px 14px", textAlign: "center" }}>
                      <p style={{ fontSize: 10, color: "#059669", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em" }}>AI schedules</p>
                      <p style={{ fontSize: 12, color: "#1e1b4b", fontWeight: 600, marginTop: 2, textTransform: "capitalize" }}>Around your {chronotype.peak_slot || "peak"}</p>
                    </div>
                  </div>
                </div>
              </div>
            ) : taskCount < 5 ? (
              <div style={{ marginTop: 20, borderRadius: 12, padding: "14px 18px", background: "#f5f3ff", border: "1px dashed #c4b5fd", display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 24 }}>🧠</span>
                <div>
                  <p style={{ fontWeight: 700, color: "#4c1d95", fontSize: 13 }}>Chronotype locked</p>
                  <p style={{ color: "#7c3aed", fontSize: 12, marginTop: 2 }}>Complete {5 - taskCount} more tasks to discover your chronotype and unlock personalised scheduling.</p>
                </div>
              </div>
            ) : null}
          </AnalysisPanel>

          <AnalysisPanel title="Full Picture" subtitle="Holistic synthesis across all productivity dimensions" icon={Layers} barColor="linear-gradient(135deg, #10b981, #059669)">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12, marginBottom: 24 }}>
              {overallObs.map((obs, i) => <InsightCard key={i} {...obs} />)}
            </div>
            {taskCount >= 5 && analytics?.daily && analytics.daily.length > 0 && (
              <div>
                <p style={{ fontSize: 11, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 14 }}>Weekly breakdown</p>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid #f3f4f6" }}>
                        {["Date", "Tasks", "Done", "Focus", "Rate"].map(h => (
                          <th key={h} style={{ textAlign: "left", padding: "8px 12px", fontSize: 11, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: "0.07em" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {analytics.daily.slice(-7).map((day, i) => {
                        const safeFocus = typeof day.focus_hours === 'number' && !isNaN(day.focus_hours) ? day.focus_hours : 0;
                        const total = day.total || 0; const done = day.completed || 0;
                        const pct = total > 0 ? Math.round((done / total) * 100) : 0;
                        const rateColor = pct >= 80 ? "#059669" : pct >= 60 ? "#d97706" : "#e11d48";
                        return (
                          <tr key={i} style={{ borderBottom: "1px solid #f9fafb" }}>
                            <td style={{ padding: "11px 12px", fontSize: 13, color: "#6b7280" }}>{day.date ? new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'N/A'}</td>
                            <td style={{ padding: "11px 12px", fontSize: 13, color: "#374151" }}>{total}</td>
                            <td style={{ padding: "11px 12px", fontSize: 13, color: "#374151" }}>{done}</td>
                            <td style={{ padding: "11px 12px", fontSize: 13, color: "#6b7280" }}>{safeFocus.toFixed(1)}h</td>
                            <td style={{ padding: "11px 12px" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <div style={{ width: 60, height: 4, background: "#f3f4f6", borderRadius: 4, overflow: "hidden" }}>
                                  <div style={{ width: `${pct}%`, height: "100%", background: rateColor, borderRadius: 4 }} />
                                </div>
                                <span style={{ fontSize: 12, fontWeight: 700, color: rateColor }}>{pct}%</span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </AnalysisPanel>
        </div>

        {/* ── Footer CTA ─────────────────────────────────────── */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
          style={{ marginTop: 44, display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          {[
            { label: "Start Focus Session", icon: Flame, action: () => navigate('/focus'), bg: "linear-gradient(135deg, #f59e0b, #ef4444)" },
            { label: "Open Planner", icon: BookOpen, action: () => navigate('/unified-planner'), bg: "linear-gradient(135deg, #7c3aed, #4f46e5)" },
            { label: "AI Planner", icon: Bot, action: () => navigate('/ai-planner'), bg: "linear-gradient(135deg, #0ea5e9, #4f46e5)" },
          ].map((btn, i) => (
            <motion.button key={i} whileHover={{ scale: 1.03, y: -1 }} whileTap={{ scale: 0.97 }} onClick={btn.action}
              style={{ padding: "12px 22px", background: btn.bg, border: "none", borderRadius: 12, color: "white", fontSize: 13, fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: 8, boxShadow: "0 4px 16px rgba(109,40,217,0.2)" }}>
              <btn.icon size={15} /> {btn.label}
            </motion.button>
          ))}
        </motion.div>

      </motion.div>
    </BackgroundLayout>
  );
}
