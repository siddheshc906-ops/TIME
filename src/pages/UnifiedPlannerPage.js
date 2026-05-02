// frontend/src/pages/UnifiedPlannerPage.jsx
import { useState, useEffect, useRef } from "react";
import {
  Plus, Trash2, Edit2, Check, X,
  ListTodo, AlertCircle,
  Flame, Clock, Sparkles
} from "lucide-react";
import { motion, AnimatePresence, useSpring, useTransform } from "framer-motion";
import { toast } from "react-hot-toast";
import BackgroundLayout from "../components/BackgroundLayout";
import { NotificationCenter } from "../components/NotificationCenter";
import { TaskSkeleton } from "../components/LoadingSkeleton";

const BASE_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";

// ✅ FIX 1: Always read token fresh from localStorage (captures OAuth token too)
function authHeaders() {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

const PRIORITY = {
  high:   { label: "High",   bar: "border-l-red-500",    badgeStyle: { background: "rgba(239,68,68,0.15)",    color: "#f87171", outline: "1px solid rgba(239,68,68,0.3)"    } },
  medium: { label: "Medium", bar: "border-l-violet-500", badgeStyle: { background: "rgba(139,92,246,0.15)",  color: "#a78bfa", outline: "1px solid rgba(139,92,246,0.3)"  } },
  low:    { label: "Low",    bar: "border-l-sky-400",    badgeStyle: { background: "rgba(56,189,248,0.15)",   color: "#38bdf8", outline: "1px solid rgba(56,189,248,0.3)"   } },
};

const DAYS = [
  { id: "monday",    label: "Monday",    gradient: "from-indigo-500 to-blue-600"    },
  { id: "tuesday",   label: "Tuesday",   gradient: "from-emerald-500 to-teal-600"   },
  { id: "wednesday", label: "Wednesday", gradient: "from-amber-500 to-orange-600"   },
  { id: "thursday",  label: "Thursday",  gradient: "from-purple-500 to-fuchsia-600" },
  { id: "friday",    label: "Friday",    gradient: "from-rose-500 to-pink-600"      },
  { id: "saturday",  label: "Saturday",  gradient: "from-cyan-500 to-sky-600"       },
  { id: "sunday",    label: "Sunday",    gradient: "from-violet-500 to-indigo-600"  },
];

function AnimatedNumber({ value }) {
  const spring = useSpring(value, { stiffness: 200, damping: 20 });
  const display = useTransform(spring, (v) => Math.round(v));
  const [displayVal, setDisplayVal] = useState(value);

  useEffect(() => {
    spring.set(value);
    const unsub = display.on("change", (v) => setDisplayVal(Math.round(v)));
    return unsub;
  }, [value]);

  return <span>{displayVal}</span>;
}

function ConfettiBurst({ trigger }) {
  return (
    <AnimatePresence>
      {trigger && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-2xl">
          {Array.from({ length: 8 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-2 h-2 rounded-sm"
              style={{
                left: "50%", top: "50%",
                backgroundColor: ["#8b5cf6","#06b6d4","#f59e0b","#10b981","#ef4444"][i % 5],
              }}
              initial={{ x: 0, y: 0, scale: 1, opacity: 1 }}
              animate={{
                x: Math.cos((i / 8) * Math.PI * 2) * 60,
                y: Math.sin((i / 8) * Math.PI * 2) * 60,
                scale: 0, opacity: 0, rotate: 360,
              }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          ))}
        </div>
      )}
    </AnimatePresence>
  );
}

export const UnifiedPlannerPage = () => {
  // ── TODO state - HYBRID: localStorage for speed, backend for persistence ──
  const [tasks, setTasks] = useState(() => {
    try {
      const saved = localStorage.getItem("todo-tasks");
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });
  const [newTask, setNewTask] = useState("");
  const [priority, setPriority] = useState("medium");
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");
  const [loading, setLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState(null);
  const [justCompleted, setJustCompleted] = useState(null);
  const [syncStatus, setSyncStatus] = useState("synced"); // 'synced', 'syncing', 'offline'
  
  // Track pending sync operations
  const pendingSyncRef = useRef([]);
  
  // ── Week planner state (unchanged) ───────────────────────────────────────
  const [weekTasks, setWeekTasks] = useState(() => {
    try {
      const saved = localStorage.getItem("week-planner");
      return saved ? JSON.parse(saved) : Object.fromEntries(DAYS.map(d => [d.id, []]));
    } catch {
      return Object.fromEntries(DAYS.map(d => [d.id, []]));
    }
  });
  const [activeDay, setActiveDay] = useState(null);
  const [dayInput, setDayInput] = useState("");
  const [hoveredTask, setHoveredTask] = useState(null);
  const [activeTab, setActiveTab] = useState("todo");
  const [userId, setUserId] = useState(null);
  const inputRef = useRef(null);

  // ── Load from localStorage first (instant), then sync with backend ────────
  useEffect(() => {
    // Decode user ID from token — supports both email-login (user_id) and google/phone (sub)
    const token = localStorage.getItem("token");
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        // user_id is the MongoDB _id (preferred), sub is email — fall back gracefully
        setUserId(payload.user_id || payload.sub || null);
      } catch { /* invalid token */ }
    }
    
    syncWithBackend();
  }, []);

  // ── Save to localStorage whenever tasks change (automatic backup) ────────
  useEffect(() => {
    localStorage.setItem("todo-tasks", JSON.stringify(tasks));
  }, [tasks]);

  // ── Save week tasks to localStorage ──────────────────────────────────────
  useEffect(() => {
    localStorage.setItem("week-planner", JSON.stringify(weekTasks));
  }, [weekTasks]);

  // ── Sync with backend ─────────────────────────────────────────────────────
  async function syncWithBackend() {
    setSyncStatus("syncing");
    try {
      const res = await fetch(`${BASE_URL}/api/tasks`, {
        headers: authHeaders(),
      });
      
      if (res.ok) {
        const serverTasks = await res.json();
        
        if (Array.isArray(serverTasks)) {
          // ✅ FIX: Merge server tasks with local tasks
          // Local completed state wins over server if server is stale (Render sleep)
          const localTasks = (() => {
            try {
              const saved = localStorage.getItem("todo-tasks");
              return saved ? JSON.parse(saved) : [];
            } catch { return []; }
          })();

          const localMap = {};
          localTasks.forEach(t => { if (t._id) localMap[t._id] = t; });

          const seen = new Set();
          const merged = serverTasks
            .filter(t => {
              const key = t._id || t.id;
              if (seen.has(key)) return false;
              seen.add(key);
              return true;
            })
            .map(serverTask => {
              const local = localMap[serverTask._id];
              // If local has a more recent completed state, keep it
              if (local && local.completed !== serverTask.completed) {
                return { ...serverTask, completed: local.completed };
              }
              return serverTask;
            });

          const sorted = [...merged].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
          setTasks(sorted);
          localStorage.setItem("todo-tasks", JSON.stringify(sorted));
        }
        setSyncStatus("synced");
      } else if (res.status === 401) {
        console.warn("Auth failed during sync - keeping local tasks");
        setSyncStatus("offline");
      } else {
        setSyncStatus("offline");
      }
    } catch (err) {
      console.error("Sync with backend failed:", err);
      setSyncStatus("offline");
    } finally {
      setLoading(false);
    }
  }

  // ── Background sync for individual operations ─────────────────────────────
  async function backgroundSync(operation, task) {
    try {
      if (operation === "add") {
        const res = await fetch(`${BASE_URL}/api/tasks`, {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({
            text: task.text,
            priority: task.priority,
            completed: false,
            difficulty: "medium",
            estimated_time: 1.0,
          }),
        });
        
        if (res.ok) {
          // ✅ FIX 4: Replace temp ID with real backend ID so future updates work
          const savedTask = await res.json();
          if (savedTask && savedTask._id) {
            setTasks(prev =>
              prev.map(t =>
                t._id === task._id
                  ? { ...savedTask, _temp: false }
                  : t
              )
            );
          }
        } else {
          throw new Error(`Server returned ${res.status}`);
        }
      } else if (operation === "update") {
        await fetch(`${BASE_URL}/api/tasks/${task._id}`, {
          method: "PUT",
          headers: authHeaders(),
          body: JSON.stringify({
            completed: task.completed,
            text: task.text,
          }),
        });
      } else if (operation === "delete") {
        await fetch(`${BASE_URL}/api/tasks/${task._id}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
      }
    } catch (err) {
      console.error(`Background sync failed for ${operation}:`, err);
      pendingSyncRef.current.push({ operation, task, timestamp: Date.now() });
      localStorage.setItem("pending-sync", JSON.stringify(pendingSyncRef.current));
    }
  }

  // ── Retry pending syncs periodically ─────────────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      if (pendingSyncRef.current.length > 0 && navigator.onLine) {
        const pending = [...pendingSyncRef.current];
        pendingSyncRef.current = [];
        pending.forEach(async ({ operation, task }) => {
          await backgroundSync(operation, task);
        });
      }
    }, 30000); // Retry every 30 seconds
    
    return () => clearInterval(interval);
  }, []);

  // ── Add task (immediate UI update + background sync) ─────────────────────
  function addTodoTask() {
    if (!newTask.trim()) {
      toast.error("Please enter a task");
      return;
    }

    // ✅ FIX: Prevent double-submission — if already adding, ignore extra clicks
    if (isAdding) return;
    setIsAdding(true);

    const tempId = `temp_${Date.now()}`;
    const newTaskObj = {
      _id: tempId,
      id: tempId,
      text: newTask.trim(),
      priority: priority,
      completed: false,
      created_at: new Date().toISOString(),
      _temp: true,
    };

    // Immediate UI update
    setTasks(prev => [newTaskObj, ...prev]);
    setNewTask("");
    setPriority("medium");
    toast.success("Task added!");
    inputRef.current?.focus();

    // Background sync — unlock button after sync completes
    backgroundSync("add", newTaskObj).finally(() => setIsAdding(false));
  }

  // ── Delete task (immediate UI update + background sync) ───────────────────
  function deleteTodoTask(id) {
    const taskToDelete = tasks.find(t => t._id === id);
    setTasks(prev => prev.filter(t => t._id !== id));
    toast.success("Task deleted");
    
    if (taskToDelete && !taskToDelete._id.toString().startsWith("temp")) {
      backgroundSync("delete", taskToDelete);
    }
  }

  // ── Toggle complete (immediate UI update + background sync) ───────────────
  function toggleTodoComplete(id, current) {
    const task = tasks.find(t => t._id === id);
    if (!task) return;
    
    const updatedTask = { ...task, completed: !current };
    setTasks(prev =>
      prev.map(t => t._id === id ? updatedTask : t)
    );

    // ✅ FIX: Immediately save completed state to localStorage so it survives backend sleep
    const currentTasks = tasks.map(t => t._id === id ? updatedTask : t);
    localStorage.setItem("todo-tasks", JSON.stringify(currentTasks));
    
    if (!current) {
      setJustCompleted(id);
      setTimeout(() => setJustCompleted(null), 700);
      toast.success("Great job!");
    }
    
    if (!task._id.toString().startsWith("temp")) {
      backgroundSync("update", updatedTask);
    }
  }

  // ── Save edit (immediate UI update + background sync) ─────────────────────
  function saveEdit(id) {
    if (!editText.trim()) return;
    
    const task = tasks.find(t => t._id === id);
    if (!task) return;
    
    const updatedTask = { ...task, text: editText };
    setTasks(prev =>
      prev.map(t => t._id === id ? updatedTask : t)
    );
    
    setEditingId(null);
    toast.success("Task updated");
    
    if (!task._id.toString().startsWith("temp")) {
      backgroundSync("update", updatedTask);
    }
  }

  // ── Week planner functions (unchanged) ───────────────────────────────────
  function addWeekTask(dayId) {
    if (!dayInput.trim()) { toast.error("Enter a task"); return; }
    setWeekTasks(prev => ({
      ...prev,
      [dayId]: [{ id: Date.now(), text: dayInput.trim(), completed: false }, ...(prev[dayId] || [])],
    }));
    setDayInput("");
    setActiveDay(null);
    toast.success(`Added to ${DAYS.find(d => d.id === dayId)?.label}`);
  }

  function deleteWeekTask(dayId, taskId) {
    setWeekTasks(prev => ({ ...prev, [dayId]: prev[dayId].filter(t => t.id !== taskId) }));
  }

  function toggleWeekTask(dayId, taskId) {
    setWeekTasks(prev => ({
      ...prev,
      [dayId]: prev[dayId].map(t => t.id === taskId ? { ...t, completed: !t.completed } : t),
    }));
  }

  // ── Stats ─────────────────────────────────────────────────────────────────
  const stats = {
    total: tasks.length,
    completed: tasks.filter(t => t.completed).length,
    pending: tasks.filter(t => !t.completed).length,
    high: tasks.filter(t => t.priority === "high" && !t.completed).length,
  };
  const completionPct = stats.total ? Math.round((stats.completed / stats.total) * 100) : 0;

  const taskVariants = {
    hidden: { opacity: 0, y: -12, scale: 0.97 },
    show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 350, damping: 28 } },
    exit: { opacity: 0, x: -40, scale: 0.95, transition: { duration: 0.22, ease: "easeIn" } },
  };

  const statVariants = {
    hidden: { opacity: 0, y: 16, scale: 0.94 },
    show: (i) => ({ opacity: 1, y: 0, scale: 1, transition: { delay: i * 0.07, type: "spring", stiffness: 260, damping: 22 } }),
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <BackgroundLayout>
      <div className="fixed top-20 right-6 z-50">
        <NotificationCenter userId={userId} />
      </div>

      <div className="py-10 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">

          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="mb-8"
          >
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <motion.h1
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.05, type: "spring", stiffness: 280, damping: 25 }}
                  className="text-3xl font-bold tracking-tight" style={{color:"var(--text-primary)"}}
                >
                  Planner
                </motion.h1>
                <motion.p
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1, type: "spring", stiffness: 280, damping: 25 }}
                  className="mt-1 text-sm" style={{color:"var(--text-secondary)"}}
                >
                  Stay organised, stay ahead
                </motion.p>
              </div>
            </div>
          </motion.div>

          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            {[
              { icon: <ListTodo size={16} />, label: "Total",   value: stats.total,     color: "var(--text-secondary)" },
              { icon: <Check   size={16} />, label: "Done",    value: stats.completed, color: "#34d399"                 },
              { icon: <Clock   size={16} />, label: "Pending", value: stats.pending,   color: "var(--accent)"           },
              { icon: <Flame   size={16} />, label: "Urgent",  value: stats.high,      color: "#f87171"                 },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                custom={i}
                variants={statVariants}
                initial="hidden"
                animate="show"
                whileHover={{ y: -3, scale: 1.02, transition: { type: "spring", stiffness: 400, damping: 20 } }}
                className="rounded-2xl p-4 shadow-sm cursor-default" style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}
              >
                <div className="flex items-center gap-1.5 mb-1 text-xs font-medium" style={{ color: s.color }}>
                  {s.icon} {s.label}
                </div>
                <p className="text-2xl font-bold" style={{color:"var(--text-primary)"}}>
                  <AnimatedNumber value={s.value} />
                </p>
              </motion.div>
            ))}
          </div>

          {/* Progress bar */}
          <AnimatePresence>
            {stats.total > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ type: "spring", stiffness: 260, damping: 24 }}
                className="mb-6 rounded-2xl p-4 shadow-sm" style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}
              >
                <div className="flex justify-between text-sm mb-2" style={{color:"var(--text-secondary)"}}>
                  <span className="font-medium">Today's progress</span>
                  <motion.span
                    key={completionPct}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="font-semibold" style={{color:"var(--accent)"}}
                  >
                    {completionPct}%
                  </motion.span>
                </div>
                <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "var(--divider)" }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${completionPct}%` }}
                    transition={{ duration: 0.8, ease: [0.34, 1.56, 0.64, 1] }}
                    className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full relative"
                  >
                    <motion.div
                      animate={{ x: ["-100%", "200%"] }}
                      transition={{ repeat: Infinity, duration: 2, ease: "linear", repeatDelay: 1 }}
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent skew-x-12"
                    />
                  </motion.div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, height: "auto", marginBottom: 16 }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                transition={{ type: "spring", stiffness: 300, damping: 28 }}
                className="p-4 bg-red-50 border border-red-200 rounded-2xl flex items-center gap-3 text-red-700 text-sm overflow-hidden"
              >
                <AlertCircle size={18} />
                <span className="flex-1">{error}</span>
                <button onClick={() => setError(null)}><X size={16} /></button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Tabs */}
          <div className="flex gap-1 mb-6 p-1 rounded-2xl w-fit" style={{background:"var(--input-bg)"}}>
            {[
              { id: "todo", label: `To-Do${stats.total > 0 ? ` (${stats.total})` : ""}` },
              { id: "week", label: "Week Planner" },
            ].map(tab => (
              <motion.button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                whileTap={{ scale: 0.97 }}
                className="relative px-5 py-2 rounded-xl text-sm font-medium transition-colors duration-200"
                style={{ color: activeTab === tab.id ? "var(--text-primary)" : "var(--text-muted)" }}
              >
                {activeTab === tab.id && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 rounded-xl shadow-sm"
                    style={{ background: "var(--card-bg)" }}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                <span className="relative z-10">{tab.label}</span>
              </motion.button>
            ))}
          </div>

          {/* ══ TODO TAB ══════════════════════════════════════════════════════ */}
          <AnimatePresence mode="wait">
            {activeTab === "todo" && (
              <motion.div
                key="todo"
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 16 }}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
                className="space-y-4"
              >
                {/* Add task form */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05, type: "spring", stiffness: 280, damping: 26 }}
                  className="rounded-2xl shadow-sm p-4" style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}
                >
                  <div className="flex gap-3 flex-wrap sm:flex-nowrap">
                    <input
                      ref={inputRef}
                      value={newTask}
                      onChange={e => setNewTask(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && addTodoTask()}
                      placeholder="What needs to be done?"
                      className="flex-1 min-w-0 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:border-transparent transition-shadow" style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                    />
                    <select
                      value={priority}
                      onChange={e => setPriority(e.target.value)}
                      className="rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2" style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                    >
                      <option value="high">🔴 High</option>
                      <option value="medium">🟣 Medium</option>
                      <option value="low">🔵 Low</option>
                    </select>
                    <button
                      onClick={addTodoTask}
                      disabled={!newTask.trim()}
                      className="disabled:opacity-40 text-white px-5 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2 transition-colors whitespace-nowrap" style={{background:"var(--accent)"}}
                    >
                      <Plus size={16} /> Add Task
                    </button>
                  </div>
                </motion.div>

                {/* Task list */}
                {loading ? (
                  <div className="space-y-3">
                    {[0, 1, 2].map(i => (
                      <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.08 }}>
                        <TaskSkeleton />
                      </motion.div>
                    ))}
                  </div>
                ) : tasks.length === 0 ? (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ type: "spring", stiffness: 260, damping: 24 }}
                    className="text-center py-20 rounded-2xl" style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}
                  >
                    <motion.div
                      animate={{ y: [0, -6, 0] }}
                      transition={{ repeat: Infinity, duration: 2.4, ease: "easeInOut" }}
                      className="text-5xl mb-4"
                    >
                      📋
                    </motion.div>
                    <p className="font-medium" style={{ color: "var(--text-secondary)" }}>No tasks yet</p>
                    <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>Add your first task above</p>
                  </motion.div>
                ) : (
                  <div className="space-y-2">
                    <AnimatePresence initial={false}>
                      {tasks.map(task => (
                        <motion.div
                          key={task._id}
                          variants={taskVariants}
                          initial="hidden"
                          animate="show"
                          exit="exit"
                          layout
                          className={`rounded-2xl border-l-4 ${PRIORITY[task.priority]?.bar || "border-l-violet-500"} shadow-sm relative overflow-hidden`} style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}
                          whileHover={{
                            y: -2,
                            boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
                            transition: { type: "spring", stiffness: 400, damping: 24 },
                          }}
                        >
                          <ConfettiBurst trigger={justCompleted === task._id} />

                          {editingId === task._id ? (
                            <div className="flex gap-3 items-center p-4">
                              <input
                                value={editText}
                                onChange={e => setEditText(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === "Enter") saveEdit(task._id);
                                  if (e.key === "Escape") setEditingId(null);
                                }}
                                autoFocus
                                className="flex-1 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2" style={{background:"var(--input-bg)",border:"1px solid var(--accent)",color:"var(--text-primary)"}}
                              />
                              <button
                                onClick={() => saveEdit(task._id)}
                                className="text-emerald-600 hover:text-emerald-700 p-1"
                              >
                                <Check size={18} />
                              </button>
                              <button
                                onClick={() => setEditingId(null)}
                                className="text-gray-400 hover:text-gray-600 p-1"
                              >
                                <X size={18} />
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-4 p-4">
                              <button
                                onClick={() => toggleTodoComplete(task._id, task.completed)}
                                className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                                  task.completed
                                    ? "bg-violet-600 border-violet-600"
                                    : "border-gray-300 hover:border-violet-500"
                                }`}
                              >
                                {task.completed && (
                                  <Check className="text-white" size={14} />
                                )}
                              </button>

                              <div className="flex-1 min-w-0">
                                <p
                                  className={`text-sm font-medium truncate ${
                                    task.completed ? "line-through" : ""
                                  }`}
                                  style={{ color: task.completed ? "var(--text-muted)" : "var(--text-primary)" }}
                                >
                                  {task.text}
                                </p>
                              </div>

                              <span
                                className="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0"
                                style={PRIORITY[task.priority]?.badgeStyle || PRIORITY.medium.badgeStyle}
                              >
                                {PRIORITY[task.priority]?.label}
                              </span>

                              <div className="flex gap-1 flex-shrink-0">
                                <button
                                  onClick={() => {
                                    setEditingId(task._id);
                                    setEditText(task.text);
                                  }}
                                  className="p-1.5 rounded-lg transition-colors"
                                  style={{ color: "var(--text-muted)" }}
                                  onMouseEnter={e => e.currentTarget.style.color = "var(--accent)"}
                                  onMouseLeave={e => e.currentTarget.style.color = "var(--text-muted)"}
                                >
                                  <Edit2 size={15} />
                                </button>
                                <button
                                  onClick={() => deleteTodoTask(task._id)}
                                  className="p-1.5 rounded-lg transition-colors"
                                  style={{ color: "var(--text-muted)" }}
                                  onMouseEnter={e => e.currentTarget.style.color = "#f87171"}
                                  onMouseLeave={e => e.currentTarget.style.color = "var(--text-muted)"}
                                >
                                  <Trash2 size={15} />
                                </button>
                              </div>
                            </div>
                          )}
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                )}
              </motion.div>
            )}

            {/* ══ WEEK TAB (unchanged) ═══════════════════════════════════════ */}
            {activeTab === "week" && (
              <motion.div
                key="week"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
              >
                {DAYS.map((day, i) => {
                  const dayTasks = weekTasks[day.id] || [];
                  const done = dayTasks.filter(t => t.completed).length;
                  const pct = dayTasks.length ? Math.round((done / dayTasks.length) * 100) : 0;

                  return (
                    <motion.div
                      key={day.id}
                      initial={{ opacity: 0, y: 24, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ delay: i * 0.05, type: "spring", stiffness: 280, damping: 26 }}
                      whileHover={{ y: -3, transition: { type: "spring", stiffness: 400, damping: 24 } }}
                      className="rounded-2xl shadow-sm overflow-hidden flex flex-col" style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}
                    >
                      <div className={`bg-gradient-to-r ${day.gradient} p-4 text-white`}>
                        <div className="flex items-center justify-between">
                          <h3 className="font-bold text-base">{day.label}</h3>
                          <span className="text-white/80 text-xs">{done}/{dayTasks.length}</span>
                        </div>
                        {dayTasks.length > 0 && (
                          <div className="mt-2 h-1 bg-white/30 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${pct}%` }}
                              transition={{ duration: 0.6, ease: [0.34, 1.56, 0.64, 1] }}
                              className="h-full bg-white rounded-full"
                            />
                          </div>
                        )}
                      </div>

                      <div className="p-3 flex-1 overflow-y-auto max-h-60 space-y-2">
                        <AnimatePresence initial={false}>
                          {dayTasks.length === 0 ? (
                            <motion.p
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              className="text-center text-xs py-6"
                              style={{ color: "var(--text-muted)" }}
                            >
                              No tasks yet
                            </motion.p>
                          ) : (
                            dayTasks.map(task => (
                              <motion.div
                                key={task.id}
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                transition={{ type: "spring", stiffness: 300, damping: 28 }}
                                onMouseEnter={() => setHoveredTask(task.id)}
                                onMouseLeave={() => setHoveredTask(null)}
                                className="rounded-xl p-2.5 flex items-center gap-2" style={{background:"var(--input-bg)"}}
                              >
                                <button
                                  onClick={() => toggleWeekTask(day.id, task.id)}
                                  className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                                    task.completed ? "bg-violet-600 border-violet-600" : "border-gray-300"
                                  }`}
                                >
                                  {task.completed && <Check className="text-white" size={10} />}
                                </button>

                                <span
                                  className={`text-xs flex-1 transition-colors ${
                                    task.completed ? "line-through" : ""
                                  }`}
                                  style={{ color: task.completed ? "var(--text-muted)" : "var(--text-primary)" }}
                                >
                                  {task.text}
                                </span>

                                <AnimatePresence>
                                  {hoveredTask === task.id && (
                                    <motion.button
                                      initial={{ opacity: 0, scale: 0.7, x: 4 }}
                                      animate={{ opacity: 1, scale: 1, x: 0 }}
                                      exit={{ opacity: 0, scale: 0.7, x: 4 }}
                                      transition={{ type: "spring", stiffness: 400, damping: 24 }}
                                      onClick={() => deleteWeekTask(day.id, task.id)}
                                      className="p-1 text-red-400 hover:text-red-600 transition-colors"
                                    >
                                      <Trash2 size={12} />
                                    </motion.button>
                                  )}
                                </AnimatePresence>
                              </motion.div>
                            ))
                          )}
                        </AnimatePresence>
                      </div>

                      <div className="p-3" style={{borderTop:"1px solid var(--card-border)"}}>
                        <AnimatePresence mode="wait">
                          {activeDay === day.id ? (
                            <motion.div
                              key="input"
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -6 }}
                              transition={{ type: "spring", stiffness: 360, damping: 28 }}
                              className="space-y-2"
                            >
                              <input
                                value={dayInput}
                                onChange={e => setDayInput(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === "Enter") addWeekTask(day.id);
                                  if (e.key === "Escape") {
                                    setActiveDay(null);
                                    setDayInput("");
                                  }
                                }}
                                placeholder="Task name…"
                                autoFocus
                                className="w-full text-xs rounded-xl px-3 py-2 focus:outline-none focus:ring-2" style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                              />
                              <div className="flex gap-2">
                                <button
                                  onClick={() => addWeekTask(day.id)}
                                  className="flex-1 text-white text-xs py-1.5 rounded-xl transition-colors" style={{background:"var(--accent)"}}
                                >
                                  Add
                                </button>
                                <button
                                  onClick={() => {
                                    setActiveDay(null);
                                    setDayInput("");
                                  }}
                                  className="px-3 text-xs rounded-xl transition-colors"
                                  style={{ color: "var(--text-muted)" }}
                                  onMouseEnter={e => e.currentTarget.style.background = "var(--accent-light)"}
                                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                                >
                                  Cancel
                                </button>
                              </div>
                            </motion.div>
                          ) : (
                            <button
                              onClick={() => setActiveDay(day.id)}
                              className="w-full py-2 text-xs rounded-xl border-2 border-dashed flex items-center justify-center gap-1.5 transition-colors" style={{color:"var(--text-muted)",borderColor:"var(--card-border)"}}
                            >
                              <Plus size={13} /> Add task
                            </button>
                          )}
                        </AnimatePresence>
                      </div>
                    </motion.div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </BackgroundLayout>
  );
};
