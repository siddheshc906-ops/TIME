// frontend/src/pages/AIPlannerPage.js

import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "react-hot-toast";
import { motion, AnimatePresence } from "framer-motion";
import BackgroundLayout from "../components/BackgroundLayout";
import AIAssistant from "../components/AIAssistant";
import { Link } from "react-router-dom";
import {
  Bot, MessageCircle, Calendar, Clock, Sparkles,
  TrendingUp, Lightbulb, X, Zap, ChevronRight,
  Coffee, Brain, Target, BarChart2, RefreshCw,
  CheckCircle, Sun, Moon, Sunset, Sunrise,
  Award, Activity, BookOpen, Loader2, Trash2, ArrowRight
} from "lucide-react";

const API = process.env.REACT_APP_API_URL
         || process.env.REACT_APP_BACKEND_URL
         || "http://localhost:8000";

const authHeaders = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${localStorage.getItem("token")}`,
});

const today = () => new Date().toISOString().split("T")[0];

/** Normalize a schedule item coming from ANY backend endpoint */
function normaliseItem(item, index) {
  const startStr =
    item.start_time && typeof item.start_time === "string"
      ? item.start_time
      : item.start_time != null
      ? decimalToTime(item.start_time)
      : null;

  const endStr =
    item.end_time && typeof item.end_time === "string"
      ? item.end_time
      : item.end_time != null
      ? decimalToTime(item.end_time)
      : null;

  let timeDisplay = "";
  if (startStr && endStr) {
    timeDisplay = `${startStr} – ${endStr}`;
  } else if (item.time && item.time.includes("-")) {
    timeDisplay = item.time.replace("-", "–");
  } else if (item.time) {
    timeDisplay = item.time;
  } else {
    timeDisplay = `${9 + index}:00 – ${10 + index}:00`;
  }

  return {
    ...item,
    task:        item.task || item.name || "Unnamed task",
    timeDisplay,
    duration:    item.duration ?? 1,
    priority:    item.priority ?? "medium",
    difficulty:  item.difficulty ?? "medium",
    category:    item.category ?? "general",
    isBreak:     item.type === "break",
    isExisting:  item.is_existing ?? false,
    focusScore:  item.focus_score ?? item.focusScore ?? 5,
    energyScore: item.energy_score ?? item.energyScore ?? 0.5,
    completed:   item.completed || false,
  };
}

function decimalToTime(hour) {
  if (hour == null) return "";
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  const period = h < 12 ? "AM" : "PM";
  const display = h % 12 || 12;
  return `${display}:${String(m).padStart(2, "0")} ${period}`;
}

function priorityColor(p) {
  return p === "high"
    ? "bg-rose-50 text-rose-700 border border-rose-200"
    : p === "low"
    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
    : "bg-amber-50 text-amber-700 border border-amber-200";
}

function energyBarColor(score) {
  if (score >= 0.8) return "bg-emerald-400";
  if (score >= 0.55) return "bg-amber-400";
  return "bg-rose-400";
}

function chronotypeIcon(type) {
  const icons = {
    "Morning Lion":     <Sunrise  size={18} className="text-amber-500"  />,
    "Afternoon Wolf":   <Sun      size={18} className="text-purple-500" />,
    "Night Owl":        <Moon     size={18} className="text-blue-500"   />,
    "Midnight Phoenix": <Sunset   size={18} className="text-red-500"    />,
    "Balanced Bear":    <Activity size={18} className="text-emerald-500"/>,
  };
  return icons[type] || <Activity size={18} className="text-gray-400" />;
}

// ── component ──────────────────────────────────────────────────────────────────
export default function AIPlannerPage() {
  const [schedule,       setSchedule]       = useState([]);
  const [insights,       setInsights]       = useState([]);
  const [aiInsights,     setAiInsights]     = useState([]);
  const [stats,          setStats]          = useState({ totalTasks: 0, totalHours: 0, focusScore: 0 });
  const [profile,        setProfile]        = useState(null);
  const [selectedDate,   setSelectedDate]   = useState(today());
  const [showAssistant,  setShowAssistant]  = useState(false);
  const [loading,        setLoading]        = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [error,          setError]          = useState("");

  const [learningData,    setLearningData]    = useState(null);
  const [learningLoading, setLearningLoading] = useState(false);

  // ── Derived productivity score from profile ──────────────────────────────
  const productivityScore = (() => {
    if (!profile) return 0;
    const ps = profile.productivity_score;
    if (!ps) return 0;
    if (typeof ps === "object") return ps.overall || 0;
    return ps || 0;
  })();

  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [selectedTask,      setSelectedTask]      = useState(null);
  const [actualTime,        setActualTime]        = useState("");
  const [feedbackInsight,   setFeedbackInsight]   = useState("");

  const [pendingTasks,         setPendingTasks]         = useState([]);
  const [dragOverIndex,        setDragOverIndex]        = useState(null);
  const [showPendingBanner,    setShowPendingBanner]    = useState(false);
  const [selectedPendingTasks, setSelectedPendingTasks] = useState([]);

  const [learningInsights, setLearningInsights] = useState([]);
  const [chronotype,       setChronotype]       = useState(null);
  const [feedbackSummary,  setFeedbackSummary]  = useState(null);
  const [totalTasksTracked, setTotalTasksTracked] = useState(0);

  // ── User routine/preferences state ──────────────────────────────────────
  const [showRoutineModal, setShowRoutineModal] = useState(false);
  const [routine, setRoutine] = useState(() => {
    try {
      const saved = localStorage.getItem("user-routine");
      return saved ? JSON.parse(saved) : {
        occupation: "student",
        wakeTime: "07:00",
        sleepTime: "23:00",
        busyStart: "09:00",
        busyEnd: "17:00",
        busyLabel: "College",
        hasBusy: true,
      };
    } catch { return { occupation: "student", wakeTime: "07:00", sleepTime: "23:00", busyStart: "09:00", busyEnd: "17:00", busyLabel: "College", hasBusy: true }; }
  });
  const [routineSaving, setRoutineSaving] = useState(false);

  // ── fetch today's plan ───────────────────────────────────────────────────
  // ✅ FIX: ref so callbacks can always call latest fetchPlan without circular deps
  const fetchPlanRef = useRef(null);

  const fetchPlan = useCallback(async (retryCount = 0) => {
    setLoading(true);
    setError("");
    try {
      // ✅ FIX: Use date-specific endpoint first (faster, more reliable)
      const res = await fetch(
        `${API}/api/daily-plans/${selectedDate}`,
        { headers: authHeaders() }
      );

      // ✅ FIX: If specific endpoint fails, fall back to fetching all plans
      if (!res.ok) {
        const fallback = await fetch(`${API}/api/daily-plans`, { headers: authHeaders() });
        if (!fallback.ok) throw new Error(`HTTP ${fallback.status}`);
        const plans = await fallback.json();
        const plan  = Array.isArray(plans) ? plans.find((p) => p.date === selectedDate) : null;
        if (plan?.schedule?.length) {
          applySchedule(plan.schedule, plan.optimizedTasks || [], plan.insights || []);
        } else {
          clearAll();
        }
        return;
      }

      const data = await res.json();
      // /{plan_date} returns a single plan object or { schedule: [] } if not found
      if (data?.schedule?.length) {
        applySchedule(data.schedule, data.optimizedTasks || [], data.insights || []);
      } else {
        clearAll();
      }
    } catch (e) {
      console.error("fetchPlan error:", e);
      // ✅ FIX: Auto-retry once silently before showing error
      if (retryCount < 1) {
        setTimeout(() => fetchPlan(retryCount + 1), 2000);
        return;
      }
      // ✅ FIX: Don't block the whole page — just show a dismissible warning
      setError("Could not load your plan. Please refresh.");
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);
  fetchPlanRef.current = fetchPlan;

  // ── fetch productivity profile ────────────────────────────────────────────
  const fetchProfile = useCallback(async () => {
    setProfileLoading(true);
    try {
      const res = await fetch(`${API}/api/ai/productivity-profile`, {
        headers: authHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();

      if (data.success || data.ready) {
        setProfile(data.profile || data);
        if (data.insights && data.insights.length > 0) setLearningInsights(data.insights);
        if (data.chronotype && data.chronotype.ready !== false) setChronotype(data.chronotype);
        setTotalTasksTracked(data.feedbacks_given || data.total_tasks || 0);
      } else if (data.message) {
        setProfile({
          _notReady:        true,
          feedbacks_given:  data.feedbacks_given  || data.total_tasks || 0,
          feedbacks_needed: data.feedbacks_needed || 5,
          message:          data.message,
        });
        setTotalTasksTracked(data.feedbacks_given || data.total_tasks || 0);
      }
    } catch (e) {
      console.error("Profile fetch error:", e);
    } finally {
      setProfileLoading(false);
    }
  }, []);

  // ── Fetch learning insights ───────────────────────────────────────────────
  const fetchLearningInsights = useCallback(async () => {
    setLearningLoading(true);
    try {
      const res = await fetch(`${API}/api/ai/insights`, { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      if (data.success) setLearningData(data);
    } catch (e) {
      console.error("Learning insights error:", e);
    } finally {
      setLearningLoading(false);
    }
  }, []);

  const fetchAIInsights = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/ai/insights`, { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      if (data.success && data.ready && data.insights) {
        if (learningInsights.length === 0) setLearningInsights(data.insights);
      }
    } catch (e) {
      console.debug("AI insights endpoint not available:", e.message);
    }
  }, [learningInsights.length]);

  const fetchChronotype = useCallback(async () => {
    if (chronotype) return;
    try {
      const res = await fetch(`${API}/api/ai/chronotype`, { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      if (data.success && data.ready) setChronotype(data);
    } catch (e) {
      console.debug("Chronotype endpoint not available:", e.message);
    }
  }, [chronotype]);

  // ── Fetch pending tasks — always fresh from server ───────────────────────
  const fetchPendingTasks = useCallback(async () => {
    try {
      const res  = await fetch(`${API}/api/pending-tasks`, { headers: authHeaders() });
      const data = await res.json();
      if (data.success && data.tasks && data.tasks.length > 0) {
        setPendingTasks(data.tasks);
        setShowPendingBanner(true);
      } else {
        setPendingTasks([]);
        setShowPendingBanner(false);
      }
    } catch (err) {
      console.error("Failed to fetch pending tasks:", err);
    }
  }, []);

  const fetchFeedbackSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/task-feedback`, { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      if (data.summary) setFeedbackSummary(data.summary);
      if (data.history) setTotalTasksTracked(data.history.length);
    } catch (e) {
      console.debug("Feedback summary not available:", e.message);
    }
  }, []);

  // ── Save user routine to backend ─────────────────────────────────────────
  // Convert HH:MM (24h) to "H:MM AM/PM" so the AI backend always parses correctly
  const to12h = (hhmm) => {
    if (!hhmm) return "";
    const [h, m] = hhmm.split(":").map(Number);
    const period = h < 12 ? "AM" : "PM";
    const hour   = h % 12 || 12;
    return `${hour}:${String(m).padStart(2, "0")} ${period}`;
  };

  const saveRoutine = async () => {
    setRoutineSaving(true);
    try {
      localStorage.setItem("user-routine", JSON.stringify(routine));
      const occupationLabels = { student: "student", professional: "working professional", freelancer: "freelancer", other: "other" };
      const busyLabel  = routine.hasBusy ? routine.busyLabel || "college" : "";
      const wakeStr    = to12h(routine.wakeTime);
      const sleepStr   = to12h(routine.sleepTime);
      const busyStart  = to12h(routine.busyStart);
      const busyEnd    = to12h(routine.busyEnd);
      const message = routine.hasBusy
        ? `I wake up at ${wakeStr}. I have ${busyLabel} from ${busyStart} to ${busyEnd}. I sleep at ${sleepStr}. I am a ${occupationLabels[routine.occupation] || routine.occupation}.`
        : `I wake up at ${wakeStr}. I sleep at ${sleepStr}. I am a ${occupationLabels[routine.occupation] || routine.occupation}. I am free all day.`;
      await fetch(`${API}/api/ai-assistant/chat`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message }),
      });
      setShowRoutineModal(false);
      toast && toast.success ? toast.success("Routine saved! AI will now schedule around your hours.") : alert("Routine saved!");
    } catch (e) {
      console.error("Failed to save routine:", e);
    } finally {
      setRoutineSaving(false);
    }
  };

  // ── Pending task selection ────────────────────────────────────────────────
  const togglePendingTask = (task) => {
    setSelectedPendingTasks((prev) => {
      const exists = prev.find((t) => t.id === task.id);
      return exists ? prev.filter((t) => t.id !== task.id) : [...prev, task];
    });
  };

  const selectAllPendingTasks = () => {
    setSelectedPendingTasks(
      selectedPendingTasks.length === pendingTasks.length ? [] : [...pendingTasks]
    );
  };

  // ── Dismiss a single pending task ────────────────────────────────────────
  const dismissPendingTask = useCallback(async (taskId) => {
    setPendingTasks(prev => {
      const updated = prev.filter(t => t.id !== taskId);
      if (updated.length === 0) setShowPendingBanner(false);
      return updated;
    });
    setSelectedPendingTasks(prev => prev.filter(t => t.id !== taskId));

    try {
      await fetch(`${API}/api/pending-tasks/${taskId}/dismiss`, {
        method: "POST",
        headers: authHeaders(),
      });
    } catch (err) {
      console.error("Failed to dismiss task:", err);
      fetchPendingTasks();
    }
  }, [fetchPendingTasks]);

  // ── Dismiss all pending tasks ────────────────────────────────────────────
  const dismissAllPendingTasks = useCallback(async () => {
    const ids = pendingTasks.map(t => t.id);
    setPendingTasks([]);
    setShowPendingBanner(false);
    setSelectedPendingTasks([]);

    await Promise.allSettled(
      ids.map(id =>
        fetch(`${API}/api/pending-tasks/${id}/dismiss`, {
          method: "POST",
          headers: authHeaders(),
        })
      )
    );
  }, [pendingTasks]);

  const schedulePendingTasks = (tasksToSchedule = null) => {
    const tasks = tasksToSchedule || selectedPendingTasks;
    if (!tasks.length && pendingTasks.length) { scheduleAllPendingTasks(); return; }
    if (!tasks.length) return;

    const taskDescriptions = tasks.map(task =>
      `${task.name} for ${task.estimated_time ? `${task.estimated_time} hours` : "1 hour"}`
    ).join(", ");

    setShowAssistant(true);
    localStorage.setItem("pendingAIMessage", `Plan my day: ${taskDescriptions}`);
  };

  const scheduleAllPendingTasks = () => {
    if (!pendingTasks.length) return;
    const taskDescriptions = pendingTasks.map(task =>
      `${task.name} for ${task.estimated_time ? `${task.estimated_time} hours` : "1 hour"}`
    ).join(", ");
    setShowAssistant(true);
    localStorage.setItem("pendingAIMessage", `Plan my day: ${taskDescriptions}`);
  };

  /**
   * Find the next free start time (in decimal hours, e.g. 14.25 = 2:15 PM)
   * given the current schedule, considering 15-min buffers between tasks.
   */
  // ── Time utilities ──────────────────────────────────────────────────────────

  /**
   * Parse ANY time representation to decimal hours.
   * Handles: number (14.25), "2:15 PM", "14:15", "9:00 AM - 10:00 AM" (takes start).
   */
  function timeToDecimal(val) {
    if (val == null) return null;
    if (typeof val === "number") return val;
    const s = String(val).trim();
    // "HH:MM AM/PM"
    let m = s.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
    if (m) {
      let h = parseInt(m[1]), mn = parseInt(m[2]);
      const p = m[3].toUpperCase();
      if (p === "PM" && h !== 12) h += 12;
      if (p === "AM" && h === 12) h = 0;
      return h + mn / 60;
    }
    // "HH:MM" 24-hour
    m = s.match(/^(\d{1,2}):(\d{2})$/);
    if (m) return parseInt(m[1]) + parseInt(m[2]) / 60;
    // plain hour number stored as string
    if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
    return null;
  }

  /**
   * Get the decimal start time of a schedule item, trying every field.
   */
  function itemStartDec(item) {
    // Numeric field
    let v = timeToDecimal(item.start_time);
    if (v !== null) return v;
    // From timeDisplay "9:00 AM – 10:00 AM"
    const td = (item.timeDisplay || "").split("–")[0].trim();
    v = timeToDecimal(td);
    if (v !== null) return v;
    // From time "9:00 AM - 10:00 AM"
    const tf = (item.time || "").split("-")[0].trim();
    v = timeToDecimal(tf);
    if (v !== null) return v;
    return 9.0;
  }

  /**
   * Get the decimal end time of a schedule item, trying every field.
   */
  function itemEndDec(item) {
    let v = timeToDecimal(item.end_time);
    if (v !== null) return v;
    // From timeDisplay "9:00 AM – 10:00 AM"
    const parts = (item.timeDisplay || "").split("–");
    if (parts.length === 2) {
      v = timeToDecimal(parts[1].trim());
      if (v !== null) return v;
    }
    // From time "9:00 AM - 10:00 AM"
    const tparts = (item.time || "").split("-");
    if (tparts.length === 2) {
      v = timeToDecimal(tparts[1].trim());
      if (v !== null) return v;
    }
    // Fallback: start + duration
    return itemStartDec(item) + (item.duration || 1);
  }

  /**
   * Find the next free start slot after all existing schedule items.
   * Adds a 15-min buffer after the last task.
   */
  function findNextFreeSlot(currentSchedule) {
    const workItems = currentSchedule.filter(i => !i.isBreak);
    if (!workItems.length) return 9.0;
    const latestEnd = Math.max(...workItems.map(itemEndDec));
    return latestEnd + 0.25; // 15-min buffer
  }

  /**
   * Merge newRawItems into existingItems.
   *
   * Key fix: we rebuild the new items sequentially from nextSlot, each
   * task starting immediately after the previous one (+ 15-min buffer),
   * instead of applying a flat offset that leaves them all at the same time.
   */
  function mergeSchedules(existingItems, newRawItems) {
    if (!existingItems.length) {
      // No existing tasks — rebuild from 9 AM sequentially
      return buildSequentialSchedule(newRawItems, 9.0);
    }

    const nextSlot = findNextFreeSlot(existingItems);
    const shiftedNew = buildSequentialSchedule(newRawItems, nextSlot);

    const merged = [...existingItems, ...shiftedNew].sort(
      (a, b) => itemStartDec(a) - itemStartDec(b)
    );
    return merged;
  }

  /**
   * Lay tasks out sequentially starting at `fromDecimal`, each task placed
   * right after the previous one with a 15-min buffer.
   * This is the core fix — no flat offset, proper sequential placement.
   */
  function buildSequentialSchedule(rawItems, fromDecimal) {
    let cursor = fromDecimal;
    return rawItems.map((item, idx) => {
      const dur = item.duration || 1;
      const startDec = cursor;
      const endDec   = cursor + dur;
      const startStr = decimalToTime(startDec);
      const endStr   = decimalToTime(endDec);
      cursor = endDec + 0.25; // 15-min buffer before next task
      return normaliseItem({
        ...item,
        start_time:  startDec,
        end_time:    endDec,
        time:        `${startStr} - ${endStr}`,
        timeDisplay: `${startStr} – ${endStr}`,
      }, idx);
    });
  }

  const generateScheduleDirectly = async () => {
    const tasks = selectedPendingTasks.length > 0 ? selectedPendingTasks : pendingTasks;
    if (!tasks.length) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API}/api/daily-plans/generate`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          tasks: tasks.map(t => ({
            name:          t.name,
            estimatedTime: t.estimated_time || 1.0,
            priority:      t.priority       || "medium",
            difficulty:    t.difficulty     || "medium",
            category:      t.category       || "general",
            task_id:       t.id,
          })),
          date: selectedDate,
          // Tell backend about existing schedule so it can find the free slot
          existing_schedule: schedule,
        }),
      });

      if (!res.ok) throw new Error("Failed to generate schedule");
      const data = await res.json();

      if (data.success && data.schedule && data.schedule.length > 0) {
        // ✅ FIX: Merge new tasks into existing schedule instead of replacing
        const merged = mergeSchedules(schedule, data.schedule);
        setSchedule(merged);
        computeStats(merged);
        computeLocalInsights(merged);

        // Persist the merged schedule to backend
        try {
          await fetch(`${API}/api/daily-plans/update-schedule`, {
            method:  "POST",
            headers: authHeaders(),
            body:    JSON.stringify({ date: selectedDate, schedule: merged }),
          });
        } catch (persistErr) {
          console.warn("Could not persist merged schedule:", persistErr);
        }

        setShowPendingBanner(false);
        setSelectedPendingTasks([]);
        if (data.patterns_used) {
          setAiInsights(prev => [
            "🧠 Schedule optimized using your personal productivity patterns!",
            ...prev,
          ]);
        }
      } else {
        setError(data.message || "Could not generate schedule.");
      }
    } catch (e) {
      console.error(e);
      setError("Failed to generate schedule. Try the AI Assistant instead.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (showAssistant) {
      const pendingMsg = localStorage.getItem("pendingAIMessage");
      if (pendingMsg) {
        localStorage.removeItem("pendingAIMessage");
        window.dispatchEvent(new CustomEvent("sendAIMessage", { detail: pendingMsg }));
      }
    }
  }, [showAssistant]);

  useEffect(() => { fetchPlan();             }, [fetchPlan]);
  useEffect(() => { fetchProfile();          }, [fetchProfile]);
  useEffect(() => { fetchPendingTasks();     }, [fetchPendingTasks]);
  useEffect(() => { fetchFeedbackSummary();  }, [fetchFeedbackSummary]);
  useEffect(() => { fetchLearningInsights(); }, [fetchLearningInsights]);

  useEffect(() => {
    if (!profileLoading) {
      fetchAIInsights();
      fetchChronotype();
    }
  }, [profileLoading, fetchAIInsights, fetchChronotype]);

  useEffect(() => () => { setShowAssistant(false); }, []);

  // ✅ FIX: Auto-dismiss error banner after 8 seconds
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(""), 8000);
    return () => clearTimeout(t);
  }, [error]);

  // ── helpers ────────────────────────────────────────────────────────────────
  function applySchedule(rawSchedule, rawTasks, backendInsights) {
    const items = rawSchedule.map(normaliseItem);
    setSchedule(items);
    computeStats(items);
    computeLocalInsights(rawTasks.length ? rawTasks : rawSchedule);
    setAiInsights(backendInsights || []);
  }

  function clearAll() {
    setSchedule([]);
    setInsights([]);
    setAiInsights([]);
    setStats({ totalTasks: 0, totalHours: 0, focusScore: 0 });
  }

  // ── FIX: clearAll + persist empty schedule to backend ────────────────────
  const clearAllAndPersist = useCallback(async () => {
    clearAll();
    try {
      const res = await fetch(`${API}/api/daily-plans`, {
        method:  "DELETE",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body:    JSON.stringify({ date: selectedDate }),
      });
      if (!res.ok) {
        await fetch(`${API}/api/daily-plans/update-schedule`, {
          method:  "POST",
          headers: authHeaders(),
          body:    JSON.stringify({ date: selectedDate, schedule: [] }),
        });
      }
    } catch (e) {
      try {
        await fetch(`${API}/api/daily-plans/update-schedule`, {
          method:  "POST",
          headers: authHeaders(),
          body:    JSON.stringify({ date: selectedDate, schedule: [] }),
        });
      } catch (e2) {
        console.debug("Could not clear plan on server:", e2.message);
      }
    }
  }, [selectedDate]);

  function computeStats(items) {
    const workItems  = items.filter((i) => !i.isBreak);
    const totalHours = workItems.reduce((s, i) => s + (i.duration || 1), 0);
    setStats({
      totalTasks: workItems.length,
      totalHours: totalHours.toFixed(1),
      focusScore: Math.min(Math.round((totalHours / 8) * 100), 100),
    });
  }

  function computeLocalInsights(tasks) {
    const out  = [];
    const high = tasks.filter((t) => t.priority === "high").length;
    if (high > 2) out.push("⚠️ Multiple high-priority tasks today. Tackle the hardest one first.");
    const hard = tasks.filter((t) => t.difficulty === "hard").length;
    if (hard > 1) out.push("💪 Multiple hard tasks. Rest 10 min between each one.");
    const hrs = tasks.reduce((s, t) => s + (t.aiTime || t.duration || 1), 0);
    if (hrs > 8)      out.push("📊 Heavy day — consider dropping a low-priority task.");
    else if (hrs < 4) out.push("✨ Light day — great for deep work or learning something new.");
    setInsights(out);
  }

  // handleScheduleCreated — called by AIAssistant whenever the AI returns a schedule.
  //
  // addIntent = false → the backend already built the complete final schedule
  //   (either a full new plan, OR an add-task where the backend merged old+new).
  //   We just normalise and replace the local state directly — no frontend merge.
  //
  // addIntent = true → the backend returned ONLY the new tasks (rare legacy path).
  //   We merge them after the existing local schedule.
  const handleScheduleCreated = useCallback((newSchedule, tasks, backendInsights, addIntent = false) => {
    if (!newSchedule || newSchedule.length === 0) {
      console.warn("Empty schedule received");
      return;
    }

    setSchedule(prevSchedule => {
      let merged;

      if (addIntent && prevSchedule.length > 0) {
        // Legacy path: backend sent only new items, frontend must merge
        merged = mergeSchedules(prevSchedule, newSchedule);
      } else {
        // Normal path: backend sent the complete schedule — just use it as-is.
        // This covers: full new plan, add-task-with-backend-merge, optimised plan.
        merged = newSchedule.map((item, idx) => normaliseItem(item, idx));
      }

      // Persist the final schedule immediately
      fetch(`${API}/api/daily-plans/update-schedule`, {
        method:  "POST",
        headers: authHeaders(),
        body:    JSON.stringify({ date: selectedDate, schedule: merged }),
      }).catch(err => console.warn("Could not persist AI schedule:", err));

      computeStats(merged);
      computeLocalInsights(tasks || merged);
      setAiInsights(backendInsights || []);
      fetchPendingTasks();
      // ✅ FIX: Re-fetch from DB after 1.5s to ensure main panel is in sync with AI chat
      setTimeout(() => fetchPlanRef.current?.(), 1500);
      return merged;
    });
  }, [fetchPendingTasks, selectedDate]);

  // ── Task completion feedback ───────────────────────────────────────────────
  const submitFeedback = async () => {
    if (!selectedTask || !actualTime) return;

    try {
      const res = await fetch(`${API}/api/task-feedback`, {
        method:  "POST",
        headers: authHeaders(),
        body:    JSON.stringify({
          name:       selectedTask.task,
          difficulty: selectedTask.difficulty || "medium",
          priority:   selectedTask.priority,
          category:   selectedTask.category   || "general",
          aiTime:     selectedTask.duration,
          actualTime: parseFloat(actualTime),
          task_id:    selectedTask.task_id    || null,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.insight) {
          setFeedbackInsight(data.insight);
          setTimeout(() => setFeedbackInsight(""), 5000);
        }
        if (data.retrain_triggered) {
          setFeedbackInsight(prev =>
            (prev ? prev + " " : "") + "🧠 AI model is updating based on your data!"
          );
        }

        setShowFeedbackModal(false);
        setSelectedTask(null);
        setActualTime("");

        setSchedule(prev =>
          prev.map(item =>
            item.task === selectedTask.task && item.timeDisplay === selectedTask.timeDisplay
              ? { ...item, completed: true }
              : item
          )
        );

        // ── Refresh profile + score after every feedback submission ──────────
        fetchProfile();
        fetchFeedbackSummary();
        fetchLearningInsights();

        // ── Update stats.focusScore to reflect completed tasks ───────────────
        setSchedule(prev => {
          const workItems  = prev.filter(i => !i.isBreak);
          const totalHours = workItems.reduce((s, i) => s + (i.duration || 1), 0);
          const completedCount = workItems.filter(i => i.completed).length;
          const completionRate = workItems.length > 0
            ? Math.round((completedCount / workItems.length) * 100)
            : 0;
          setStats(s => ({
            ...s,
            focusScore: Math.min(Math.round((totalHours / 8) * 100), 100),
          }));
          return prev;
        });

      } else {
        toast.error("Failed to save feedback. Please try again.");
      }
    } catch (err) {
      console.error("Failed to save feedback:", err);
      toast.error("Error saving feedback. Please try again.");
    }
  };

  const handleTaskComplete = (task) => {
    setSelectedTask(task);
    setShowFeedbackModal(true);
  };

  // ── Priority change ────────────────────────────────────────────────────────
  const handlePriorityChange = useCallback(async (task, newPriority) => {
    setSchedule(prevSchedule =>
      prevSchedule.map(item =>
        item.task === task.task && item.timeDisplay === task.timeDisplay
          ? { ...item, priority: newPriority }
          : item
      )
    );
    try {
      await fetch(`${API}/api/task-priority`, {
        method:  "POST",
        headers: authHeaders(),
        body:    JSON.stringify({
          task_name:    task.task,
          old_priority: task.priority,
          new_priority: newPriority,
        }),
      });
    } catch (err) {
      console.error("Failed to save priority change:", err);
    }
  }, []);

  // ── FIX: Delete task — compute filtered list first, then persist ──────────
  const handleDeleteTask = useCallback(async (taskToDelete) => {
    const updatedSchedule = schedule.filter(
      item =>
        !(item.task === taskToDelete.task && item.timeDisplay === taskToDelete.timeDisplay)
    );

    setSchedule(updatedSchedule);

    const workItems  = updatedSchedule.filter(i => !i.isBreak);
    const totalHours = workItems.reduce((s, i) => s + (i.duration || 1), 0);
    setStats({
      totalTasks: workItems.length,
      totalHours: totalHours.toFixed(1),
      focusScore: Math.min(Math.round((totalHours / 8) * 100), 100),
    });

    try {
      await fetch(`${API}/api/daily-plans/update-schedule`, {
        method:  "POST",
        headers: authHeaders(),
        body:    JSON.stringify({
          date:     selectedDate,
          schedule: updatedSchedule,
        }),
      });
    } catch (err) {
      console.debug("Could not persist schedule deletion:", err.message);
    }
  }, [schedule, selectedDate]);

  // ── Drag-and-drop reorder ─────────────────────────────────────────────────
  const handleReorder = useCallback(async (fromIndex, toIndex) => {
    if (fromIndex === toIndex) return;
    const reordered = [...schedule];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);

    // Rebuild times sequentially from 9 AM preserving durations
    let cursor = 9.0;
    const rebuilt = reordered.map((item) => {
      if (item.isBreak) return item;
      const dur = item.duration || 1;
      const startDec = cursor;
      const endDec = cursor + dur;
      cursor = endDec + 0.25;
      const startStr = decimalToTime(startDec);
      const endStr = decimalToTime(endDec);
      return {
        ...item,
        start_time: startDec,
        end_time: endDec,
        time: `${startStr} - ${endStr}`,
        timeDisplay: `${startStr} – ${endStr}`,
      };
    });

    setSchedule(rebuilt);
    computeStats(rebuilt);
    setDragOverIndex(null);

    try {
      await fetch(`${API}/api/daily-plans/update-schedule`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ date: selectedDate, schedule: rebuilt }),
      });
    } catch (err) {
      console.debug("Could not persist reorder:", err.message);
    }
  }, [schedule, selectedDate]);

  const allInsights = [...aiInsights, ...insights].slice(0, 5);
  const isToday     = selectedDate === today();

  // Get streak from profile
  const streak = profile?.streak || feedbackSummary?.streak || 0;

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <BackgroundLayout>
      <div className="min-h-screen py-8 px-4 md:px-6 font-sans">
        <div className="max-w-7xl mx-auto">
          <div className={`transition-all duration-300 ease-in-out ${
            showAssistant ? "lg:mr-[380px]" : "lg:mr-0"
          }`}>

            {/* Header */}
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600
                                flex items-center justify-center shadow-lg shadow-violet-200">
                  <Bot className="text-white" size={28} />
                </div>
                <div>
                  <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-gray-900">
                    AI Productivity Planner
                  </h1>
                  <p className="text-sm text-gray-500 mt-0.5 flex items-center gap-1.5">
                    <Sparkles size={13} className="text-violet-500" />
                    Intelligent scheduling, personalised to you
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="border border-gray-200 rounded-xl px-3 py-2 text-sm bg-white
                             shadow-sm focus:ring-2 focus:ring-violet-400 focus:border-transparent
                             text-gray-700 cursor-pointer"
                />
                <button
                  onClick={fetchPlan}
                  disabled={loading}
                  title="Refresh plan"
                  className="p-2.5 rounded-xl border border-gray-200 bg-white shadow-sm
                             hover:bg-gray-50 transition-colors text-gray-500 hover:text-violet-600"
                >
                  <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
                </button>
                <button
                  onClick={() => setShowRoutineModal(true)}
                  title="Set your daily schedule so AI plans around your hours"
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100 transition-colors shadow-sm"
                >
                  <Clock size={15} />
                  My Routine
                </button>
                <button
                  onClick={() => setShowAssistant((v) => !v)}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium
                              transition-all duration-200 shadow-sm
                              ${showAssistant
                                ? "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                : "bg-gradient-to-r from-violet-600 to-indigo-600 text-white hover:shadow-violet-200 hover:shadow-md"
                              }`}
                >
                  <MessageCircle size={16} />
                  {showAssistant ? "Close Assistant" : "Open AI Assistant"}
                </button>
              </div>
            </header>

            {/* Error banner */}
            {error && (
              <div className="mb-6 px-4 py-3 bg-rose-50 border border-rose-200 rounded-xl
                              text-rose-700 text-sm flex items-center gap-2">
                <span>⚠️</span> {error}
                {/* ✅ FIX: Retry button so user doesn't have to manually refresh */}
                <button
                  onClick={() => { setError(""); fetchPlan(); }}
                  className="ml-2 text-xs underline text-rose-600 hover:text-rose-800 font-medium"
                >
                  Retry
                </button>
                <button onClick={() => setError("")} className="ml-auto text-rose-400 hover:text-rose-600">
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Feedback insight toast */}
            {feedbackInsight && (
              <div className="mb-6 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl
                              text-emerald-700 text-sm flex items-center gap-2 animate-fade-in">
                <CheckCircle size={16} className="text-emerald-500 flex-shrink-0" />
                <span>{feedbackInsight}</span>
                <button onClick={() => setFeedbackInsight("")}
                        className="ml-auto text-emerald-400 hover:text-emerald-600">
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Pending Tasks Banner */}
            {showPendingBanner && pendingTasks.length > 0 && (
              <PendingTasksBanner
                pendingTasks={pendingTasks}
                selectedPendingTasks={selectedPendingTasks}
                onToggleTask={togglePendingTask}
                onSelectAll={selectAllPendingTasks}
                onScheduleSelected={() => schedulePendingTasks()}
                onScheduleAll={scheduleAllPendingTasks}
                onGenerateDirectly={generateScheduleDirectly}
                onDismissTask={dismissPendingTask}
                onDismiss={dismissAllPendingTasks}
                loading={loading}
              />
            )}

            {/* Stats cards */}
            {schedule.filter((i) => !i.isBreak).length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
                {[
                  { label: "Tasks planned", value: stats.totalTasks,       icon: <Target    size={20} className="text-violet-500"  />, bg: "bg-violet-50"  },
                  { label: "Focus hours",   value: `${stats.totalHours}h`, icon: <Clock     size={20} className="text-blue-500"    />, bg: "bg-blue-50"    },
                  { label: "Day load",      value: `${stats.focusScore}%`, icon: <BarChart2 size={20} className="text-emerald-500" />, bg: "bg-emerald-50" },
                ].map(({ label, value, icon, bg }) => (
                  <div key={label}
                       className="bg-white/90 backdrop-blur-sm rounded-2xl p-5 shadow-sm
                                  border border-gray-100 flex items-center gap-4">
                    <div className={`w-11 h-11 ${bg} rounded-xl flex items-center justify-center`}>
                      {icon}
                    </div>
                    <div>
                      <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</p>
                      <p className="text-2xl font-bold text-gray-800 leading-tight">{value}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-6">

              {/* Schedule Timeline */}
              <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="flex items-center justify-between px-6 py-5 border-b border-gray-50">
                  <div className="flex items-center gap-2.5">
                    <Calendar size={20} className="text-violet-500" />
                    <h2 className="font-semibold text-gray-800">
                      {isToday ? "Today's plan" : `Plan for ${selectedDate}`}
                    </h2>
                    {isToday && (
                      <span className="ml-1 text-xs font-medium px-2 py-0.5 bg-violet-100
                                       text-violet-700 rounded-full">
                        Today
                      </span>
                    )}
                  </div>
                  {schedule.length > 0 && (
                    <button
                      onClick={clearAllAndPersist}
                      className="flex items-center gap-1 text-xs text-gray-400
                                 hover:text-rose-500 transition-colors px-2 py-1
                                 rounded-lg hover:bg-rose-50"
                    >
                      <X size={13} /> Clear
                    </button>
                  )}
                </div>

                {/* Loading skeleton */}
                {loading && (
                  <div className="p-6 space-y-4">
                    {[1, 2, 3].map((n) => (
                      <div key={n} className="flex gap-4 animate-pulse">
                        <div className="w-36 h-8 bg-gray-100 rounded-xl" />
                        <div className="w-3 h-3 bg-gray-100 rounded-full mt-2.5" />
                        <div className="flex-1 h-20 bg-gray-100 rounded-xl" />
                      </div>
                    ))}
                  </div>
                )}

                {/* Empty state */}
                {!loading && schedule.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
                    <div className="w-20 h-20 bg-violet-50 rounded-full flex items-center
                                    justify-center mb-5 ring-8 ring-violet-50/50">
                      <Bot size={36} className="text-violet-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-gray-700 mb-2">No plan yet</h3>
                    <p className="text-sm text-gray-400 max-w-xs mb-2">
                      Open the AI Assistant and describe your day. I'll build
                      a personalised schedule in seconds.
                    </p>
                    <p className="text-xs text-violet-400 max-w-xs mb-8 italic">
                      The more you use it, the smarter it gets about your personal rhythm.
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-xl">
                      {[
                        { icon: <Calendar   size={16} />, text: '"Study 2h, gym 1h, team meeting at 3 PM"' },
                        { icon: <Lightbulb  size={16} />, text: '"Give me deep work productivity tips"'     },
                        { icon: <TrendingUp size={16} />, text: '"Analyse my habits this week"'             },
                      ].map(({ icon, text }, i) => (
                        <button
                          key={i}
                          onClick={() => setShowAssistant(true)}
                          className="flex flex-col items-center gap-2 p-4 rounded-xl border
                                     border-gray-100 bg-gray-50 hover:border-violet-200
                                     hover:bg-violet-50 transition-all text-xs text-gray-500
                                     hover:text-violet-700 text-center"
                        >
                          <span className="text-violet-400">{icon}</span>
                          {text}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Timeline */}
                {!loading && schedule.length > 0 && (
                  <div className="relative px-6 py-6">
                    <div className="absolute left-[10.5rem] top-0 bottom-0 w-px bg-gradient-to-b
                                    from-transparent via-violet-200 to-transparent" />
                    <div className="space-y-4">
                      <AnimatePresence initial={false}>
                        {schedule.map((item, idx) => (
                          <DraggableScheduleRow
                            key={`${item.task}-${item.timeDisplay}-${idx}`}
                            item={item}
                            index={idx}
                            isDragOver={dragOverIndex === idx}
                            onComplete={handleTaskComplete}
                            onPriorityChange={handlePriorityChange}
                            onDelete={handleDeleteTask}
                            onReorder={handleReorder}
                            onDragOver={setDragOverIndex}
                          />
                        ))}
                      </AnimatePresence>
                    </div>
                  </div>
                )}
              </div>

              {/* Only show insights if there are any - kept for quick tips */}
              {allInsights.length > 0 && <QuickInsightsCard insights={allInsights} />}

              {/* REPLACEMENT: Single AI Profile Teaser Card (instead of 4 separate cards) */}
              {(chronotype || totalTasksTracked > 0 || streak > 0) && (
                <AITeaserCard
                  chronotype={chronotype}
                  streak={streak}
                  totalTasksTracked={totalTasksTracked}
                  modelReady={feedbackSummary?.model_ready || (totalTasksTracked >= 10)}
                />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* AI Assistant drawer */}
      <div className={`fixed top-0 right-0 h-full z-50 transition-all duration-300 ease-in-out ${
        showAssistant ? "translate-x-0" : "translate-x-full"
      }`}>
        <AIAssistant
          key={selectedDate}
          isOpen={showAssistant}
          onClose={() => setShowAssistant(false)}
          onScheduleCreated={handleScheduleCreated}
        />
      </div>

      {/* Task Completion Feedback Modal */}
      {showFeedbackModal && selectedTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-violet-100 rounded-full flex items-center justify-center">
                <CheckCircle size={20} className="text-violet-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Task Completed! 🎉</h3>
                <p className="text-xs text-gray-400">Help the AI learn from your data</p>
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-3 mb-4">
              <p className="text-sm text-gray-600">
                Task: <strong>{selectedTask.task}</strong>
              </p>
              <div className="flex items-center gap-3 mt-1">
                <p className="text-xs text-gray-400">
                  Planned: <span className="font-semibold text-gray-600">{selectedTask.duration}h</span>
                </p>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${priorityColor(selectedTask.priority)}`}>
                  {selectedTask.priority}
                </span>
                {selectedTask.category && selectedTask.category !== "general" && (
                  <span className="text-[10px] font-medium text-gray-500 bg-gray-200 px-2 py-0.5 rounded-full">
                    {selectedTask.category}
                  </span>
                )}
              </div>
            </div>

            <label className="block text-sm font-medium text-gray-700 mb-2">
              Actual time spent (hours):
            </label>
            <input
              type="number"
              step="0.25"
              min="0.25"
              value={actualTime}
              onChange={(e) => setActualTime(e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-2.5 mb-2
                         focus:outline-none focus:ring-2 focus:ring-violet-500
                         focus:border-transparent text-lg font-semibold text-center"
              placeholder="e.g., 1.5"
              autoFocus
            />

            <div className="flex gap-2 mb-4 justify-center">
              {[0.5, 1, 1.5, 2, 3].map(t => (
                <button
                  key={t}
                  onClick={() => setActualTime(String(t))}
                  className={`px-3 py-1 rounded-lg text-xs font-medium border transition
                    ${actualTime === String(t)
                      ? "bg-violet-100 border-violet-300 text-violet-700"
                      : "bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100"
                    }`}
                >
                  {t}h
                </button>
              ))}
            </div>

            {actualTime && selectedTask.duration > 0 && (
              <div className="text-xs text-gray-500 mb-4 text-center">
                {parseFloat(actualTime) < selectedTask.duration * 0.8
                  ? "⚡ Faster than estimated! Great efficiency."
                  : parseFloat(actualTime) > selectedTask.duration * 1.3
                  ? "⏰ Took longer than expected. AI will adjust next time."
                  : "✨ Close to the estimate. Good calibration!"}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={submitFeedback}
                disabled={!actualTime}
                className="flex-1 bg-violet-600 text-white py-2.5 rounded-xl font-medium
                           hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed
                           transition flex items-center justify-center gap-2"
              >
                <CheckCircle size={16} />
                Save Feedback
              </button>
              <button
                onClick={() => { setShowFeedbackModal(false); setSelectedTask(null); setActualTime(""); }}
                className="flex-1 bg-gray-100 text-gray-600 py-2.5 rounded-xl font-medium
                           hover:bg-gray-200 transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      {/* ── User Routine Modal ─────────────────────────────────────────────── */}
      {showRoutineModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md p-6 animate-fade-in">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-xl font-bold text-gray-900">My Daily Routine</h2>
                <p className="text-sm text-gray-500 mt-0.5">AI will schedule tasks around your real hours</p>
              </div>
              <button onClick={() => setShowRoutineModal(false)} className="p-2 rounded-xl hover:bg-gray-100 text-gray-400">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4">
              {/* Occupation */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">I am a</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: "student", label: "🎓 Student" },
                    { value: "professional", label: "💼 Professional" },
                    { value: "freelancer", label: "💻 Freelancer" },
                    { value: "other", label: "✨ Other" },
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setRoutine(r => ({ ...r, occupation: opt.value, busyLabel: opt.value === "student" ? "College" : opt.value === "professional" ? "Work" : opt.value === "freelancer" ? "Work" : "Busy" }))}
                      className={`py-2.5 px-3 rounded-xl text-sm font-medium border transition-colors ${routine.occupation === opt.value ? "bg-violet-600 text-white border-violet-600" : "bg-gray-50 text-gray-700 border-gray-200 hover:border-violet-300"}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Wake / Sleep */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">🌅 Wake up</label>
                  <input type="time" value={routine.wakeTime} onChange={e => setRoutine(r => ({ ...r, wakeTime: e.target.value }))}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">🌙 Sleep at</label>
                  <input type="time" value={routine.sleepTime} onChange={e => setRoutine(r => ({ ...r, sleepTime: e.target.value }))}
                    className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400" />
                </div>
              </div>

              {/* Busy block toggle */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-700">
                    {routine.occupation === "student" ? "🏫 College hours" : "🏢 Work hours"}
                  </label>
                  <button
                    onClick={() => setRoutine(r => ({ ...r, hasBusy: !r.hasBusy }))}
                    className={`relative w-11 h-6 rounded-full transition-colors ${routine.hasBusy ? "bg-violet-600" : "bg-gray-200"}`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${routine.hasBusy ? "translate-x-5" : ""}`} />
                  </button>
                </div>
                {routine.hasBusy && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Start</label>
                      <input type="time" value={routine.busyStart} onChange={e => setRoutine(r => ({ ...r, busyStart: e.target.value }))}
                        className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">End</label>
                      <input type="time" value={routine.busyEnd} onChange={e => setRoutine(r => ({ ...r, busyEnd: e.target.value }))}
                        className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400" />
                    </div>
                  </div>
                )}
              </div>

              {/* Preview */}
              <div className="bg-violet-50 rounded-xl p-3 text-xs text-violet-700">
                <span className="font-semibold">AI will schedule tasks: </span>
                {routine.wakeTime} – {routine.hasBusy ? `${routine.busyStart} (before ${routine.busyLabel || "busy"})` : routine.sleepTime}
                {routine.hasBusy && ` and ${routine.busyEnd} – ${routine.sleepTime} (after ${routine.busyLabel || "busy"})`}
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowRoutineModal(false)}
                className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">
                Cancel
              </button>
              <button onClick={saveRoutine} disabled={routineSaving}
                className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold hover:opacity-90 disabled:opacity-60 transition-opacity">
                {routineSaving ? "Saving..." : "Save Routine"}
              </button>
            </div>
          </div>
        </div>
      )}

    </BackgroundLayout>
  );
}

// ╔══════════════════════════════════════════════════════════════════════════════
// ║  Quick Insights Card (simplified)
// ╚══════════════════════════════════════════════════════════════════════════════

function QuickInsightsCard({ insights }) {
  if (!insights || insights.length === 0) return null;
  return (
    <div className="bg-gradient-to-br from-violet-600 via-violet-600 to-indigo-700
                    rounded-2xl shadow-md p-5 text-white">
      <div className="flex items-center gap-2 mb-3">
        <Zap size={16} className="text-yellow-300" />
        <h3 className="font-semibold text-sm">Quick Tips</h3>
      </div>
      <ul className="space-y-2">
        {insights.slice(0, 3).map((ins, i) => (
          <li key={i}
              className="flex gap-2 text-xs text-white/90 bg-white/10 rounded-xl
                         px-3 py-2 leading-relaxed">
            <ChevronRight size={12} className="flex-shrink-0 mt-0.5 text-yellow-300" />
            {ins}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ╔══════════════════════════════════════════════════════════════════════════════
// ║  AI TEASER CARD — Single card linking to Performance page
// ╚══════════════════════════════════════════════════════════════════════════════

function AITeaserCard({ chronotype, streak, totalTasksTracked, modelReady }) {
  const chronoType = chronotype?.type || "Learning";
  const chronoEmoji = chronotype?.emoji || "🧠";
  const streakDisplay = streak || 0;

  return (
    <Link to="/analytics" className="block group">
      <div className="bg-gradient-to-r from-violet-50 to-indigo-50 rounded-2xl border border-violet-200 p-5
                      hover:shadow-lg transition-all duration-300 group-hover:border-violet-300
                      group-hover:from-violet-100 group-hover:to-indigo-100 cursor-pointer">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-violet-500 to-indigo-500 rounded-xl
                            flex items-center justify-center shadow-md">
              <Brain size={24} className="text-white" />
            </div>
            <div>
              <h3 className="font-bold text-gray-800 text-lg">Your AI Profile</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-sm">{chronoEmoji} {chronoType}</span>
                {streakDisplay > 0 && (
                  <span className="text-xs text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full">
                    🔥 {streakDisplay}-day streak
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="bg-white/60 rounded-full p-2 group-hover:bg-white transition-colors">
            <ArrowRight size={20} className="text-violet-600" />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-1.5">
            <CheckCircle size={14} className="text-emerald-500" />
            <span>{totalTasksTracked || 0} tasks analyzed</span>
          </div>
          {modelReady && (
            <div className="flex items-center gap-1.5">
              <Sparkles size={14} className="text-violet-500" />
              <span className="text-violet-600 font-medium">ML active</span>
            </div>
          )}
        </div>

        <div className="mt-3 text-xs text-gray-500">
          {modelReady 
            ? "Your AI has learned your patterns. Click to see full analysis →"
            : `${10 - (totalTasksTracked || 0)} more tasks to unlock AI insights →`}
        </div>
      </div>
    </Link>
  );
}


// ╔══════════════════════════════════════════════════════════════════════════════
// ║  Pending Tasks Banner
// ╚══════════════════════════════════════════════════════════════════════════════

function PendingTasksBanner({
  pendingTasks, selectedPendingTasks, onToggleTask, onSelectAll,
  onScheduleSelected, onScheduleAll, onGenerateDirectly,
  onDismissTask, onDismiss, loading,
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mb-6 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200
                    rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center">
            <BookOpen size={20} className="text-amber-600" />
          </div>
          <div>
            <h4 className="font-semibold text-amber-800">
              {pendingTasks.length} pending task{pendingTasks.length !== 1 ? "s" : ""} from Planner
            </h4>
            <p className="text-xs text-amber-600">
              {selectedPendingTasks.length > 0
                ? `${selectedPendingTasks.length} selected`
                : "Select tasks or schedule all"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded(v => !v)}
            className="text-xs text-amber-600 hover:text-amber-800 px-2 py-1 rounded-lg
                       hover:bg-amber-100 transition"
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
          <button
            onClick={onGenerateDirectly}
            disabled={loading}
            className="px-4 py-2 bg-amber-600 text-white rounded-xl font-medium text-sm
                       hover:bg-amber-700 transition shadow-sm flex items-center gap-2
                       disabled:opacity-50"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            {selectedPendingTasks.length > 0 ? `Schedule ${selectedPendingTasks.length}` : "Schedule All"}
          </button>
          <button
            onClick={onDismiss}
            title="Dismiss all pending tasks"
            className="text-amber-400 hover:text-amber-600 p-1"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-amber-200/50 pt-3">
          <div className="flex items-center justify-between mb-2">
            <button
              onClick={onSelectAll}
              className="text-xs text-amber-600 hover:text-amber-800 underline"
            >
              {selectedPendingTasks.length === pendingTasks.length ? "Deselect all" : "Select all"}
            </button>
            {selectedPendingTasks.length > 0 && (
              <button
                onClick={onScheduleSelected}
                className="text-xs bg-violet-600 text-white px-3 py-1 rounded-lg
                           hover:bg-violet-700 transition flex items-center gap-1"
              >
                <MessageCircle size={10} />
                Chat to schedule {selectedPendingTasks.length}
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {pendingTasks.map((task) => {
              const isSelected = selectedPendingTasks.some(t => t.id === task.id);
              return (
                <div key={task.id} className="flex items-center gap-1">
                  <button
                    onClick={() => onToggleTask(task)}
                    className={`px-3 py-1.5 rounded-lg text-xs border transition-all
                      flex items-center gap-1.5
                      ${isSelected
                        ? "bg-violet-100 border-violet-300 text-violet-700 shadow-sm"
                        : "bg-white border-amber-200 text-amber-700 hover:border-amber-300"
                      }`}
                  >
                    {isSelected ? (
                      <CheckCircle size={12} className="text-violet-500" />
                    ) : (
                      <span className="w-3 h-3 rounded-full border border-amber-300" />
                    )}
                    <span className="font-medium">{task.name}</span>
                    {task.priority === "high" && <span className="text-rose-500">🔥</span>}
                    {task.estimated_time && (
                      <span className="text-gray-400">{task.estimated_time}h</span>
                    )}
                  </button>
                  <button
                    onClick={() => onDismissTask(task.id)}
                    title="Remove this task from pending"
                    className="p-1 text-amber-300 hover:text-amber-600 transition-colors"
                  >
                    <X size={11} />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


// ╔══════════════════════════════════════════════════════════════════════════════
// ║  DraggableScheduleRow — wraps ScheduleRow with smooth drag-and-drop
// ╚══════════════════════════════════════════════════════════════════════════════

function DraggableScheduleRow({ item, index, isDragOver, onComplete, onPriorityChange, onDelete, onReorder, onDragOver }) {
  const dragRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragStart = (e) => {
    if (item.isBreak) { e.preventDefault(); return; }
    setIsDragging(true);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(index));
    // Ghost image — use the card itself but faded
    if (dragRef.current) {
      e.dataTransfer.setDragImage(dragRef.current, 20, 20);
    }
  };

  const handleDragEnd = () => {
    setIsDragging(false);
    onDragOver(null);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    onDragOver(index);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const fromIndex = parseInt(e.dataTransfer.getData("text/plain"), 10);
    onDragOver(null);
    if (!isNaN(fromIndex) && fromIndex !== index) {
      onReorder(fromIndex, index);
    }
  };

  const handleDragLeave = (e) => {
    // Only clear if leaving the row entirely (not entering a child)
    if (!e.currentTarget.contains(e.relatedTarget)) {
      onDragOver(null);
    }
  };

  return (
    <motion.div
      ref={dragRef}
      layout
      layoutId={`task-${item.task}-${index}`}
      initial={{ opacity: 0, y: -10 }}
      animate={{
        opacity: isDragging ? 0.4 : 1,
        y: 0,
        scale: isDragging ? 0.97 : 1,
      }}
      exit={{ opacity: 0, x: -80, scale: 0.9, transition: { duration: 0.25 } }}
      transition={{ type: "spring", stiffness: 350, damping: 30 }}
      draggable={!item.isBreak}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onDragLeave={handleDragLeave}
      className="relative"
      style={{ cursor: item.isBreak ? "default" : "grab" }}
    >
      {/* Drop indicator line — appears above when dragging over */}
      <AnimatePresence>
        {isDragOver && !isDragging && (
          <motion.div
            initial={{ opacity: 0, scaleX: 0 }}
            animate={{ opacity: 1, scaleX: 1 }}
            exit={{ opacity: 0, scaleX: 0 }}
            transition={{ duration: 0.15 }}
            className="absolute -top-2 left-0 right-0 h-0.5 bg-violet-500 rounded-full z-10
                       shadow-[0_0_8px_2px_rgba(139,92,246,0.4)]"
          />
        )}
      </AnimatePresence>

      {/* Drag handle hint — shows on hover for non-break items */}
      {!item.isBreak && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 z-10
                        opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          <div className="flex flex-col gap-0.5 px-0.5">
            {[0,1,2].map(i => (
              <div key={i} className="flex gap-0.5">
                <div className="w-0.5 h-0.5 rounded-full bg-gray-300" />
                <div className="w-0.5 h-0.5 rounded-full bg-gray-300" />
              </div>
            ))}
          </div>
        </div>
      )}

      <ScheduleRow
        item={item}
        onComplete={onComplete}
        onPriorityChange={onPriorityChange}
        onDelete={onDelete}
      />
    </motion.div>
  );
}

// ╔══════════════════════════════════════════════════════════════════════════════
// ║  Schedule Row
// ╚══════════════════════════════════════════════════════════════════════════════

function ScheduleRow({ item, onComplete, onPriorityChange, onDelete }) {
  const [completed,     setCompleted]     = useState(item.completed || false);
  const [priority,      setPriority]      = useState(item.priority  || "medium");
  const [isHovered,     setIsHovered]     = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleComplete = () => {
    const newCompleted = !completed;
    setCompleted(newCompleted);
    if (newCompleted && onComplete) onComplete(item);
  };

  const handlePriorityChange = (e) => {
    const newPriority = e.target.value;
    setPriority(newPriority);
    if (onPriorityChange) onPriorityChange(item, newPriority);
  };

  const handleDelete = () => {
    if (confirmDelete) {
      if (onDelete) onDelete(item);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000);
    }
  };

  if (item.isBreak) {
    return (
      <motion.div
        layout
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, x: -60, scale: 0.95, transition: { duration: 0.25 } }}
        className="flex items-center gap-3 opacity-50 py-1"
      >
        <div className="w-36 flex-shrink-0 text-right pr-2">
          <span className="text-xs text-gray-400 tabular-nums whitespace-nowrap">
            {item.timeDisplay}
          </span>
        </div>
        <div className="w-2.5 h-2.5 rounded-full bg-gray-300 flex-shrink-0" />
        <div className="flex items-center gap-1.5 text-xs text-gray-400 italic">
          <Coffee size={12} /> {item.task}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: -80, scale: 0.9, transition: { duration: 0.3, ease: "easeIn" } }}
      transition={{ type: "spring", stiffness: 350, damping: 30 }}
      className="flex items-start gap-3 group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => { setIsHovered(false); setConfirmDelete(false); }}
    >
      <div className="w-36 flex-shrink-0 text-right pr-2 pt-3.5">
        <span className="inline-block text-[11px] font-semibold text-violet-600
                         bg-violet-50 border border-violet-100 rounded-lg
                         px-2 py-1 leading-tight tabular-nums whitespace-nowrap">
          {item.timeDisplay}
        </span>
      </div>

      <div className="flex-shrink-0 mt-[1.05rem]">
        <div className={`w-3 h-3 rounded-full ring-[3px] ring-white shadow-sm
                         transition-colors group-hover:scale-110
                         ${completed
                           ? "bg-emerald-500"
                           : item.isExisting
                           ? "bg-blue-400"
                           : "bg-violet-400 group-hover:bg-violet-600"}`} />
      </div>

      <div className={`flex-1 min-w-0 border rounded-xl px-4 py-3.5 shadow-sm
                       transition-all duration-200 relative
                       ${completed
                         ? "bg-emerald-50/60 border-emerald-200"
                         : item.isExisting
                         ? "bg-blue-50/60 border-blue-200"
                         : "bg-white border-gray-100 hover:border-violet-100 hover:shadow-md"}`}>

        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <input
              type="checkbox"
              checked={completed}
              onChange={handleComplete}
              className="w-4 h-4 rounded border-gray-300 text-emerald-600
                         focus:ring-emerald-500 cursor-pointer flex-shrink-0"
            />
            <h4 className={`font-semibold text-sm leading-snug
                            ${completed ? "line-through text-gray-400" : "text-gray-800"}`}>
              {item.task}
            </h4>
            {item.isExisting && !completed && (
              <span className="text-[9px] font-medium text-blue-600 bg-blue-100
                               px-2 py-0.5 rounded-full flex-shrink-0">
                Existing
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            <AnimatePresence>
              {isHovered && (
                <motion.button
                  initial={{ opacity: 0, scale: 0.5, width: 0 }}
                  animate={{ opacity: 1, scale: 1, width: "auto" }}
                  exit={{ opacity: 0, scale: 0.5, width: 0 }}
                  transition={{ type: "spring", stiffness: 400, damping: 25 }}
                  onClick={handleDelete}
                  className={`flex items-center gap-1 px-2 py-0.5 rounded-full
                              text-[10px] font-medium transition-colors overflow-hidden
                              ${confirmDelete
                                ? "bg-rose-100 text-rose-700 border border-rose-300 hover:bg-rose-200"
                                : "bg-gray-50 text-gray-400 border border-gray-200 hover:bg-rose-50 hover:text-rose-500 hover:border-rose-200"
                              }`}
                  title={confirmDelete ? "Click again to confirm" : "Delete task"}
                >
                  <Trash2 size={11} />
                  {confirmDelete && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      className="whitespace-nowrap"
                    >
                      Confirm?
                    </motion.span>
                  )}
                </motion.button>
              )}
            </AnimatePresence>

            <select
              value={priority}
              onChange={handlePriorityChange}
              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border
                          cursor-pointer transition-all
                          ${priority === "high"
                            ? "bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100"
                            : priority === "low"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100"
                            : "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"}`}
            >
              <option value="high"   className="bg-white text-rose-700">🔥 High</option>
              <option value="medium" className="bg-white text-amber-700">⚡ Medium</option>
              <option value="low"    className="bg-white text-emerald-700">💤 Low</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-4 flex-wrap ml-6">
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <Clock size={11} /> {item.duration}h
          </span>
          {item.energyScore > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-gray-300 uppercase tracking-wide font-medium">energy</span>
              <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${energyBarColor(item.energyScore)} transition-all`}
                  style={{ width: `${Math.round(item.energyScore * 100)}%` }}
                />
              </div>
            </div>
          )}
          {item.focusScore > 0 && (
            <span className="flex items-center gap-1 text-[10px] text-gray-400">
              <Brain size={10} /> {item.focusScore}/10
            </span>
          )}
          {item.category && item.category !== "general" && (
            <span className="text-[9px] font-medium text-gray-400 bg-gray-100
                             px-1.5 py-0.5 rounded-full capitalize">
              {item.category}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
