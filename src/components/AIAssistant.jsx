// frontend/src/components/AIAssistant.jsx
import { useState, useRef, useEffect, useCallback } from "react";
import {
    Send, Bot, User, Sparkles, Calendar, TrendingUp, Lightbulb,
    X, Maximize2, Minimize2, Clock, Zap, Brain, Target, Award, BarChart,
    ArrowLeft,
} from "lucide-react";

const API = process.env.REACT_APP_API_URL
         || process.env.REACT_APP_BACKEND_URL
         || "http://localhost:8000";

const authHeaders = () => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("token")}`,
});

export default function AIAssistant({
    onClose,
    isOpen,
    onScheduleCreated,
    initialMessages = [],
    setMessages: parentSetMessages,
    mode = "planner",   // "planner" | "coach" — coach routes to /api/ai/guidance
}) {
    const [messages,                setMessages]                = useState(initialMessages);
    const [input,                   setInput]                   = useState("");
    const [isLoading,               setIsLoading]               = useState(false);
    const [isExpanded,              setIsExpanded]              = useState(false);
    const [suggestions,             setSuggestions]             = useState([]);
    const [userContext,             setUserContext]             = useState(null);
    const [showProductivityProfile, setShowProductivityProfile] = useState(false);
    const [productivityProfile,     setProductivityProfile]     = useState(null);
    const [recommendations,         setRecommendations]         = useState([]);
    const [performanceSnapshot,     setPerformanceSnapshot]     = useState(null); // coach mode data

    const messagesEndRef    = useRef(null);
    const inputRef          = useRef(null);
    const assistantRef      = useRef(null);
    const loadingTimeoutRef = useRef(null);
    // ✅ FIX: ref to always get latest isLoading state inside timeouts/closures
    const isLoadingRef      = useRef(false);
    // ✅ FIX: ref to always get latest messages for conversation history
    const messagesRef       = useRef([]);

    // ── Cleanup on unmount ─────────────────────────────────────────────────────
    useEffect(() => {
        return () => {
            if (loadingTimeoutRef.current) {
                clearTimeout(loadingTimeoutRef.current);
            }
            setMessages([]);
            setInput("");
            setIsLoading(false);
            setIsExpanded(false);
            setSuggestions([]);
            setUserContext(null);
        };
    }, []);

    // ── Sync incoming initialMessages (only when they actually change) ─────────
    useEffect(() => {
        if (initialMessages && initialMessages.length > 0) {
            setMessages(initialMessages);
        }
    }, [initialMessages]);

    // ── Notify parent when messages change ─────────────────────────────────────
    const parentSetMessagesRef = useRef(parentSetMessages);
    useEffect(() => { parentSetMessagesRef.current = parentSetMessages; });

    useEffect(() => {
        if (parentSetMessagesRef.current) {
            parentSetMessagesRef.current(messages);
        }
    }, [messages]);

    // ✅ FIX: Keep refs in sync with state
    useEffect(() => { isLoadingRef.current = isLoading; }, [isLoading]);
    useEffect(() => { messagesRef.current = messages; }, [messages]);

    // ── Scroll to bottom ───────────────────────────────────────────────────────
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // ── Data loaders ───────────────────────────────────────────────────────────
    const loadContext = useCallback(async () => {
        try {
            const res  = await fetch(`${API}/api/ai-assistant/context`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
            });
            if (!res.ok) return;
            const data = await res.json();
            setSuggestions(data.suggestions || []);
            setUserContext(data);
        } catch (err) {
            console.error("Failed to load context:", err);
        }
    }, []);

    const loadProductivityProfile = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/ai/productivity-profile`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
            });
            if (!res.ok) return;
            const data = await res.json();
            if (data.success) setProductivityProfile(data.profile);
        } catch (err) {
            console.error("Failed to load productivity profile:", err);
        }
    }, []);

    const loadRecommendations = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/ai/recommendations`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
            });
            if (!res.ok) return;
            const data = await res.json();
            if (data.success) setRecommendations(data.recommendations || []);
        } catch (err) {
            console.error("Failed to load recommendations:", err);
        }
    }, []);

    // ── Load performance snapshot for coach mode ─────────────────────────────
    const loadPerformanceSnapshot = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/ai/guidance`, {
                method:  "POST",
                headers: authHeaders(),
                body:    JSON.stringify({ message: "__snapshot__" }),
            });
            if (!res.ok) return;
            const data = await res.json();
            if (data.data_summary && Object.keys(data.data_summary).length > 0) {
                setPerformanceSnapshot(data.data_summary);
            }
        } catch (err) {
            console.error("Failed to load performance snapshot:", err);
        }
    }, []);

    // ── Load data once when assistant opens ────────────────────────────────────
    useEffect(() => {
        if (!isOpen) return;
        inputRef.current?.focus();
        if (mode === "coach") {
            loadPerformanceSnapshot();
        } else {
            loadContext();
            loadProductivityProfile();
            loadRecommendations();
        }
    }, [isOpen, mode]);

    // ── Train model ────────────────────────────────────────────────────────────
    const trainModel = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/ai/train-model`, {
                method:  "POST",
                headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
            });
            if (!res.ok) return;
            const data = await res.json();
            if (data.success) {
                setMessages(prev => [...prev, {
                    id:        Date.now(),
                    role:      "assistant",
                    content:   data.message,
                    type:      "success",
                    timestamp: new Date().toISOString(),
                }]);
            }
        } catch (err) {
            console.error("Failed to train model:", err);
        }
    }, []);

    // ── Send message ───────────────────────────────────────────────────────────
    const sendMessage = useCallback(async (overrideText, retryCount = 0) => {
        const messageText = (overrideText ?? input).trim();
        if (!messageText || isLoadingRef.current) return; // ✅ FIX: use ref not stale state

        const userMsg = {
            id:        Date.now(),
            role:      "user",
            content:   messageText,
            timestamp: new Date().toISOString(),
        };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsLoading(true);

        // Clear any existing timeout
        if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);

        // ✅ FIX: Safety timeout uses ref so it always reads current value
        loadingTimeoutRef.current = setTimeout(() => {
            if (isLoadingRef.current) {
                console.warn("Loading timeout - forcing stop");
                setIsLoading(false);
            }
        }, 30000);

        try {
            const endpoint = mode === "coach"
                ? `${API}/api/ai/guidance`
                : `${API}/api/ai-assistant/chat`;

            // ✅ FIX: Send full conversation history so AI has context
            const history = messagesRef.current
                .filter(m => m.role === "user" || m.role === "assistant")
                .slice(-10) // last 10 messages max
                .map(m => ({ role: m.role, content: m.content }));

            const res = await fetch(endpoint, {
                method:  "POST",
                headers: authHeaders(),
                body:    JSON.stringify({
                    message:              messageText,
                    conversation_history: history,
                }),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();

            const aiMessage = {
                id:        Date.now() + 1,
                role:      "assistant",
                content:   data.message || "I've processed your request!",
                type:      data.type    || "chat",
                data:      data,
                timestamp: new Date().toISOString(),
            };

            setMessages(prev => [...prev, aiMessage]);

            if (mode === "coach" && data.data_summary && Object.keys(data.data_summary).length > 0) {
                setPerformanceSnapshot(data.data_summary);
            }

            if (data.type === "schedule" && data.schedule && data.schedule.length > 0 && onScheduleCreated) {
                const backendAlreadyMerged = Boolean(data.full_schedule_in_response);
                const addIntent = Boolean(data.add_intent) && !backendAlreadyMerged;

                // ✅ FIX: Strip break items from schedule before sending to the main planner
                // Breaks are shown in the AI chat panel only — they should NOT be saved as
                // separate schedule items (they caused task duplication on re-load)
                const scheduleWithoutBreaks = (data.schedule || []).filter(
                    item => item.type !== "break" && (item.task || "").toLowerCase() !== "short break"
                );

                onScheduleCreated(
                    scheduleWithoutBreaks,
                    data.tasks_found || [],
                    data.insights    || [],
                    addIntent,
                );

                if (data.deferred_tasks && data.deferred_tasks.length > 0) {
                    const deferredNames = data.deferred_tasks.map(t => t.task).join(", ");
                    const highPriority  = data.deferred_tasks.filter(t => t.priority === "high");
                    let deferredMsg = `📅 **Moved to tomorrow:** ${deferredNames}

These tasks don't fit in your free time today.`;
                    if (highPriority.length > 0) {
                        deferredMsg += `

🔴 **${highPriority[0].task}** is high priority — consider removing a lower-priority task today to make room for it.`;
                    }
                    deferredMsg += `

💡 Say "remove [task name]" to free up time, or "do [task] tomorrow" to keep it deferred.`;
                    setTimeout(() => {
                        setMessages(prev => [...prev, {
                            id:        Date.now() + 2,
                            role:      "assistant",
                            content:   deferredMsg,
                            type:      "deferred",
                            timestamp: new Date().toISOString(),
                        }]);
                    }, 600);
                }
            } else if (data.type === "schedule" && (!data.schedule || data.schedule.length === 0)) {
                console.warn("Received empty schedule from AI");
            }

            if (data.type === "schedule") setTimeout(loadRecommendations, 1000);

        } catch (err) {
            console.error("Chat error:", err);
            // ✅ FIX: Auto-retry once before showing error to user
            if (retryCount < 1) {
                console.warn("Retrying sendMessage...");
                setMessages(prev => prev.filter(m => m.id !== userMsg.id)); // remove user msg temporarily
                setIsLoading(false);
                setTimeout(() => sendMessage(messageText, retryCount + 1), 1500);
                if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);
                return;
            }
            setMessages(prev => [...prev, {
                id:        Date.now() + 1,
                role:      "assistant",
                content:   "Something went wrong. Please try again.",
                type:      "error",
                timestamp: new Date().toISOString(),
            }]);
        } finally {
            if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);
            setIsLoading(false);
        }
    }, [input, onScheduleCreated, loadRecommendations, mode]);

    // ── Quick actions ──────────────────────────────────────────────────────────
    // Planner button nudge messages — friendly guidance, not auto-scheduling
    const PLANNER_NUDGES = {
        plan: {
            message: "Just tell me what you want to get done today — tasks, errands, study, gym, work, anything.\n\nIf you also tell me your available time window, I'll schedule everything optimally.\n\nFor example:\n• Physics 2h, Maths 1h — free 4 PM to 10 PM\n• Gym at 6, dinner at 8, need to finish project work\n• Meetings till 3 PM, plan the rest of my day",
            hint: "Type your tasks or just describe your day.",
        },
        advice: {
            message: "What are you working on or struggling with?\n\nShare the context and I'll give you targeted, practical advice — not generic tips.\n\nFor example:\n• How do I prepare for an exam in one day?\n• I keep losing focus after 30 minutes\n• Best strategy for covering 3 subjects in 5 hours",
            hint: "Describe your situation below.",
        },
        analyze: {
            message: "Your habit analysis builds as you use the planner over several days.\n\nFor now, start scheduling — the more tasks you plan and complete, the more accurate and personalised your analysis becomes.\n\nTry: 'Physics 2h, Maths 1h — free 5 PM to 9 PM'",
            hint: "Schedule tasks to start building your data.",
        },
        optimize: {
            message: "To optimise your schedule, tell me your tasks and available window:\n\ne.g. 'Physics 2h, Maths 1.5h, Chemistry 1h — free 4 PM to 10 PM'\n\nI'll arrange them in the most productive order — hardest subjects during peak focus, lighter tasks later, with timed breaks built in.",
            hint: "Type your tasks and time window below.",
        },
        progress: {
            message: "Your progress data appears here as you complete scheduled tasks.\n\nStart by planning today — every completed task adds to your streak, completion rate, and focus score.\n\nTry: 'Physics 2h, Maths 1h — free from 5 PM to 9 PM'",
            hint: "Schedule tasks to start tracking.",
        },
    };

    const COACH_ACTIONS = {
        productive: "How productive am I based on my data?",
        improve:    "What should I improve to be more productive?",
        focus:      "How can I improve my focus score?",
        gaps:       "What's my biggest productivity gap right now?",
        streak:     "How do I build a consistent daily streak?",
    };

    const handleQuickAction = useCallback((action) => {
        if (mode === "coach") {
            const text = COACH_ACTIONS[action] || action;
            sendMessage(text);
        } else {
            // Planner mode: show a friendly nudge message and focus the input
            const nudge = PLANNER_NUDGES[action];
            if (nudge) {
                setMessages(prev => [...prev, {
                    id:        Date.now(),
                    role:      "assistant",
                    content:   nudge.message,
                    type:      "chat",
                    data:      { suggestions: [] },
                    timestamp: new Date().toISOString(),
                }]);
                setTimeout(() => inputRef.current?.focus(), 100);
            }
        }
    }, [mode, sendMessage, setMessages]);

    const handleSuggestionClick = useCallback((suggestion) => {
        // Auto-send suggestion instead of just filling the input
        sendMessage(suggestion);
    }, [sendMessage]);

    const handleSendClick = useCallback(() => {
        sendMessage();
    }, [sendMessage]);

    const handleKeyPress = useCallback((e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }, [sendMessage]);

    // ── Listen for external messages from Planner page ────────────────────────
    useEffect(() => {
        const handleExternalMessage = (event) => {
            const message = event.detail;
            // ✅ FIX: use ref to check loading state — avoids stale closure
            if (message && !isLoadingRef.current) {
                // ✅ FIX: don't setInput first (causes double-send) — just send directly
                sendMessage(message);
            }
        };
        window.addEventListener("sendAIMessage", handleExternalMessage);
        return () => window.removeEventListener("sendAIMessage", handleExternalMessage);
    }, [sendMessage]);

    // ── Message renderer ───────────────────────────────────────────────────────
    const renderMessageContent = (msg) => {
        const { type, data } = msg;

        // ── Daily check-in card ───────────────────────────────────────────────
        if (type === "checkin") {
            return (
                <div className="mt-3">
                    {data?.pending_tasks?.length > 0 && (
                        <div className="mb-3 flex flex-wrap gap-1.5">
                            {data.pending_tasks.map((t, i) => (
                                <span key={i} className="text-xs bg-violet-100 text-violet-700
                                                          px-2 py-1 rounded-full font-medium">
                                    {t}
                                </span>
                            ))}
                        </div>
                    )}
                    <div className="grid grid-cols-1 gap-2 mt-2">
                        {(data?.suggestions || []).map((s, i) => (
                            <button
                                key={i}
                                onClick={() => sendMessage(s)}
                                className="text-left text-sm px-3 py-2 rounded-lg
                                           bg-white border border-violet-200 text-violet-700
                                           hover:bg-violet-50 hover:border-violet-400
                                           transition-all font-medium"
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>
            );
        }

        if (type === "schedule" && data?.schedule && data.schedule.length > 0) {
            return (
                <div className="mt-3 space-y-2">
                    {data.schedule.map((item, idx) => (
                        <div key={idx} className="bg-purple-50 rounded-lg p-3 border border-purple-100">
                            <div className="flex items-center justify-between">
                                <span className="font-medium text-purple-700 text-sm">
                                    {item.task || item.name || "Task"}
                                </span>
                                {item.priority && (
                                    <span className={`text-xs px-2 py-1 rounded-full ${
                                        item.priority === "high" ? "bg-red-200 text-red-700" :
                                        item.priority === "low"  ? "bg-green-200 text-green-700" :
                                                                   "bg-yellow-200 text-yellow-700"
                                    }`}>
                                        {item.priority}
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center gap-2 mt-2 text-xs text-gray-600">
                                <Clock size={12} />
                                <span>{item.time || `${item.start_time || "?"} - ${item.end_time || "?"}`}</span>
                                <span className="ml-auto">{item.duration || 1}h</span>
                            </div>
                        </div>
                    ))}
                    {data.insights?.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-purple-200">
                            <p className="text-xs font-medium text-purple-700 mb-2">✨ Insights:</p>
                            {data.insights.map((insight, idx) => (
                                <p key={idx} className="text-xs text-gray-600 flex items-start gap-1 mb-1">
                                    <span className="text-purple-500">•</span> {insight}
                                </p>
                            ))}
                        </div>
                    )}
                </div>
            );
        }

        if (type === "advice" && data?.advice_points) {
            return (
                <div className="mt-3 space-y-2">
                    {data.advice_points.map((point, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-sm">
                            <Lightbulb size={16} className="text-yellow-500 mt-0.5 flex-shrink-0" />
                            <span className="text-gray-700">{point}</span>
                        </div>
                    ))}
                    {data.insight && (
                        <div className="mt-3 pt-3 border-t border-gray-200">
                            <p className="text-xs italic text-gray-500">{data.insight}</p>
                        </div>
                    )}
                </div>
            );
        }

        if (type === "analysis" && data?.stats) {
            return (
                <div className="mt-3 space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                        {[
                            { label: "Completion", value: data.stats.completion_rate, color: "blue" },
                            { label: "Tasks",      value: data.stats.total_tasks,     color: "green" },
                            { label: "Avg Time",   value: data.stats.avg_task_duration, color: "purple" },
                            { label: "Streak",     value: data.stats.streak || 0,     color: "orange" },
                        ].map(({ label, value, color }) => (
                            <div key={label} className={`bg-${color}-50 p-2 rounded-lg text-center`}>
                                <div className={`text-lg font-bold text-${color}-700`}>{value}</div>
                                <div className={`text-xs text-${color}-600`}>{label}</div>
                            </div>
                        ))}
                    </div>
                    {data.insight && (
                        <div className="bg-gray-50 p-3 rounded-lg">
                            <p className="text-sm text-gray-700">{data.insight}</p>
                        </div>
                    )}
                    {data.recommendations?.length > 0 && (
                        <div>
                            <p className="text-xs font-medium text-gray-700 mb-2">📌 Recommendations:</p>
                            {data.recommendations.map((rec, idx) => (
                                <p key={idx} className="text-xs text-gray-600 flex items-start gap-1 mb-1">
                                    <span className="text-purple-500">•</span> {rec}
                                </p>
                            ))}
                        </div>
                    )}
                </div>
            );
        }

        if (type === "progress" && data) {
            return (
                <div className="mt-3 space-y-2">
                    <p className="text-sm text-gray-700">{msg.content}</p>
                    {data.stats && (
                        <div className="bg-gray-50 p-3 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-gray-600">Productivity Score</span>
                                <span className="text-sm font-bold text-purple-600">{data.stats.overall || 0}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                                <div className="bg-purple-600 h-2 rounded-full"
                                     style={{ width: `${data.stats.overall || 0}%` }} />
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        // Coach mode: render follow-up suggestion chips after any response
        if (mode === "coach" && data?.suggestions && data.suggestions.length > 0 && msg.role === "assistant") {
            return (
                <div>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    {data.advice_points && data.advice_points.length > 0 && (
                        <div className="mt-3 space-y-2">
                            {data.advice_points.map((point, idx) => (
                                <div key={idx} className="flex items-start gap-2 text-sm bg-violet-50 rounded-xl p-2.5">
                                    <Lightbulb size={14} className="text-violet-500 mt-0.5 flex-shrink-0" />
                                    <span className="text-gray-700">{point}</span>
                                </div>
                            ))}
                        </div>
                    )}
                    <div className="mt-3 flex flex-wrap gap-1.5">
                        {data.suggestions.map((s, i) => (
                            <button key={i}
                                    onClick={() => sendMessage(s)}
                                    className="text-xs bg-white border border-violet-200 text-violet-700 rounded-full px-3 py-1 hover:bg-violet-50 hover:border-violet-400 transition font-medium">
                                {s}
                            </button>
                        ))}
                    </div>
                </div>
            );
        }

        // Default chat + redirect hint to Performance page
        if (data?.redirect_hint === "performance") {
            return (
                <div>
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <a
                        href="/performance"
                        className="mt-3 flex items-center gap-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2 hover:bg-indigo-100 transition w-fit"
                    >
                        <TrendingUp size={13} /> Go to Performance Page →
                    </a>
                    {data.suggestions?.length > 0 && (
                        <div className="mt-2">
                            <p className="text-xs text-gray-500 mb-1">Or try asking:</p>
                            <div className="flex flex-wrap gap-1">
                                {data.suggestions.map((s, i) => (
                                    <button
                                        key={i}
                                        onClick={() => { setInput(s); inputRef.current?.focus(); }}
                                        className="text-xs bg-purple-50 text-purple-600 border border-purple-200 rounded-full px-2 py-0.5 hover:bg-purple-100 transition"
                                    >
                                        {s}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        // Deduplicate repeated bullet lines (e.g. routine detection listing same entry multiple times)
        const deduplicatedContent = (() => {
            const lines = msg.content.split("\n");
            const seen = new Set();
            return lines.filter(line => {
                const trimmed = line.trim();
                if (!trimmed) return true; // keep blank lines for spacing
                if (seen.has(trimmed)) return false;
                seen.add(trimmed);
                return true;
            }).join("\n");
        })();

        // Planner mode: render chat message with suggestion chips (no per-chip hints)
        if (mode !== "coach" && data?.suggestions && data.suggestions.length > 0 && msg.role === "assistant") {
            // Only show a single faded example below the message itself for scheduling prompts
            const isSchedulingPrompt = msg.content.toLowerCase().includes("tell me what tasks") ||
                                       msg.content.toLowerCase().includes("what do you want to") ||
                                       msg.content.toLowerCase().includes("what tasks") ||
                                       msg.content.toLowerCase().includes("all set");
            return (
                <div>
                    <p className="text-sm whitespace-pre-wrap">{deduplicatedContent}</p>
                    {isSchedulingPrompt && (
                        <p className="mt-1.5 text-[10px] text-gray-300 italic">
                            e.g. Physics 2h, Maths 1h — free 5 PM to 10 PM
                        </p>
                    )}
                    <div className="mt-3 space-y-1.5">
                        {data.suggestions.map((s, i) => (
                            <button
                                key={i}
                                onClick={() => sendMessage(s)}
                                className="w-full text-left text-xs px-3 py-2 rounded-lg
                                           bg-white border border-violet-200 text-violet-700
                                           hover:bg-violet-50 hover:border-violet-400
                                           transition-all font-medium"
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>
            );
        }

        return <p className="text-sm whitespace-pre-wrap">{deduplicatedContent}</p>;
    };

    if (!isOpen) return null;

    return (
        <>
            <div className="fixed inset-0 z-40" style={{ pointerEvents: "none" }} />

            <div
                ref={assistantRef}
                className={`fixed bottom-6 right-6 z-50 transition-all duration-300 ${
                    isExpanded ? "w-[900px] h-[700px]" : "w-96 h-[600px]"
                }`}
                style={{ pointerEvents: "auto" }}
            >
                <div className="bg-white rounded-2xl shadow-2xl flex flex-col h-full border border-gray-200 overflow-hidden">

                    {/* Header */}
                    <div className="bg-gradient-to-r from-purple-600 to-indigo-600 p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                                <Brain className="text-white" size={24} />
                            </div>
                            <div>
                                <h3 className="text-white font-semibold flex items-center gap-2">
                                    {mode === "coach" ? "AI Performance Coach" : "AI Productivity Coach"}
                                    <Sparkles size={16} className="text-yellow-300" />
                                </h3>
                                <p className="text-white/80 text-xs">
                                    {mode === "coach"
                                        ? "Powered by your real analytics"
                                        : "Powered by Timevora AI"}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            {messages.length > 0 && (
                                <button
                                    onClick={() => setMessages([])}
                                    className="p-2 hover:bg-white/20 rounded-lg transition"
                                    title="Back to home">
                                    <ArrowLeft size={18} className="text-white" />
                                </button>
                            )}
                            {productivityProfile && (
                                <button onClick={() => setShowProductivityProfile(v => !v)}
                                        className="p-2 hover:bg-white/20 rounded-lg transition relative"
                                        title="View Productivity Profile">
                                    <Award size={18} className="text-white" />
                                    {!showProductivityProfile && (
                                        <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-400 rounded-full" />
                                    )}
                                </button>
                            )}
                            <button onClick={() => setIsExpanded(v => !v)}
                                    className="p-2 hover:bg-white/20 rounded-lg transition">
                                {isExpanded
                                    ? <Minimize2 size={18} className="text-white" />
                                    : <Maximize2 size={18} className="text-white" />}
                            </button>
                            <button onClick={onClose} className="p-2 hover:bg-white/20 rounded-lg transition">
                                <X size={18} className="text-white" />
                            </button>
                        </div>
                    </div>

                    {/* Body */}
                    <div className="flex-1 flex overflow-hidden">
                        <div className={`flex-1 flex flex-col ${isExpanded ? "border-r border-gray-200" : ""}`}>
                            <div className="flex-1 overflow-y-auto p-4 bg-gray-50">

                                {messages.length === 0 ? (
                                    <div className="h-full flex flex-col items-center justify-center text-center p-4">
                                        {mode === "coach" ? (
                                            /* ── Coach mode empty state ── */
                                            <div className="w-full space-y-4">
                                                <div className="flex flex-col items-center mb-2">
                                                    <div className="w-16 h-16 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-full flex items-center justify-center mb-3 shadow-lg">
                                                        <Brain size={32} className="text-white" />
                                                    </div>
                                                    <h4 className="text-base font-bold text-gray-800">Your Productivity Coach</h4>
                                                    <p className="text-xs text-gray-500 mt-1">Analysing your real performance data</p>
                                                </div>

                                                {/* Live data snapshot card */}
                                                {performanceSnapshot && (
                                                    <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-200 rounded-2xl p-3 text-left">
                                                        <p className="text-xs font-semibold text-violet-700 mb-2 flex items-center gap-1">
                                                            <TrendingUp size={12} /> Your stats at a glance
                                                        </p>
                                                        <div className="grid grid-cols-3 gap-2">
                                                            {[
                                                                { label: "Completion", value: `${performanceSnapshot.completion_rate ?? 0}%`,    color: "text-green-700"  },
                                                                { label: "Focus hrs",  value: `${performanceSnapshot.focus_hours ?? 0}h`,          color: "text-blue-700"   },
                                                                { label: "Streak",     value: `${performanceSnapshot.streak ?? 0}d`,               color: "text-orange-600" },
                                                                { label: "Tasks done", value: `${performanceSnapshot.task_count ?? 0}`,            color: "text-violet-700" },
                                                                { label: "AI plans",   value: `${performanceSnapshot.ai_schedules ?? 0}`,          color: "text-indigo-700" },
                                                                { label: "Score",      value: `${performanceSnapshot.performance_index ?? 0}/100`, color: "text-purple-700" },
                                                            ].map(({ label, value, color }) => (
                                                                <div key={label} className="bg-white rounded-xl p-2 text-center shadow-sm">
                                                                    <p className={`text-sm font-bold ${color}`}>{value}</p>
                                                                    <p className="text-xs text-gray-400">{label}</p>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Coach quick-action buttons */}
                                                <div className="space-y-2">
                                                    <p className="text-xs text-gray-500 text-left font-medium">Ask me anything:</p>
                                                    {[
                                                        { action: "productive", icon: <TrendingUp size={14} className="text-violet-600" />,  label: "How productive am I?",              cls: "bg-violet-50 border-violet-200 hover:bg-violet-100 text-violet-700" },
                                                        { action: "improve",    icon: <Target size={14} className="text-indigo-600" />,       label: "What should I improve?",            cls: "bg-indigo-50 border-indigo-200 hover:bg-indigo-100 text-indigo-700" },
                                                        { action: "focus",      icon: <Zap size={14} className="text-blue-600" />,            label: "How to improve my focus?",          cls: "bg-blue-50 border-blue-200 hover:bg-blue-100 text-blue-700"       },
                                                        { action: "gaps",       icon: <BarChart size={14} className="text-orange-600" />,     label: "What's my biggest gap?",            cls: "bg-orange-50 border-orange-200 hover:bg-orange-100 text-orange-700" },
                                                        { action: "streak",     icon: <Award size={14} className="text-green-600" />,         label: "How do I build consistency?",       cls: "bg-green-50 border-green-200 hover:bg-green-100 text-green-700"   },
                                                    ].map(({ action, icon, label, cls }) => (
                                                        <button key={action} onClick={() => handleQuickAction(action)}
                                                                className={`w-full flex items-center gap-2 px-3 py-2.5 border rounded-xl transition font-medium text-sm text-left ${cls}`}>
                                                            {icon} {label}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        ) : (
                                            /* ── Planner mode empty state ── */
                                            <div className="w-full space-y-3">
                                                <div className="flex items-center gap-3 mb-1">
                                                    <div className="w-9 h-9 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0">
                                                        <Bot size={18} className="text-white" />
                                                    </div>
                                                    <div>
                                                        <h4 className="text-sm font-semibold text-gray-800">AI Productivity Planner</h4>
                                                        <p className="text-[11px] text-gray-400">Powered by Timevora AI</p>
                                                    </div>
                                                </div>

                                                <p className="text-xs text-gray-500 leading-relaxed">
                                                    Just tell me what's on your mind — studying, work, gym, errands, anything. I'll understand the context and build a smart plan around your day.
                                                </p>

                                                <div className="space-y-1.5">
                                                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Try saying</p>
                                                    {[
                                                        "I have an exam tomorrow, help me prepare",
                                                        "Plan my evening — gym, dinner, some work",
                                                        "I have college till 4 PM, what should I do after?",
                                                        "I'm free today, make me productive",
                                                    ].map((s, i) => (
                                                        <button key={i} onClick={() => handleSuggestionClick(s)}
                                                                className="w-full text-left px-3 py-2 bg-white border border-gray-200 rounded-xl hover:border-violet-300 hover:bg-violet-50 transition text-xs text-gray-700 font-medium leading-snug">
                                                            {s}
                                                        </button>
                                                    ))}
                                                </div>

                                                <div className="grid grid-cols-2 gap-2 pt-1">
                                                    {[
                                                        { action: "plan",     icon: <Calendar size={13} className="text-violet-600" />,  label: "Plan my day",    cls: "bg-violet-50 border-violet-200 hover:bg-violet-100 text-violet-700" },
                                                        { action: "advice",   icon: <Lightbulb size={13} className="text-blue-600" />,    label: "Get advice",     cls: "bg-blue-50 border-blue-200 hover:bg-blue-100 text-blue-700" },
                                                        { action: "analyze",  icon: <TrendingUp size={13} className="text-green-600" />,  label: "My progress",    cls: "bg-green-50 border-green-200 hover:bg-green-100 text-green-700" },
                                                        { action: "optimize", icon: <Zap size={13} className="text-orange-600" />,        label: "Optimize",       cls: "bg-orange-50 border-orange-200 hover:bg-orange-100 text-orange-700" },
                                                    ].map(({ action, icon, label, cls }) => (
                                                        <button key={action} onClick={() => handleQuickAction(action)}
                                                                className={`flex items-center gap-2 p-2.5 border rounded-xl transition font-medium text-xs ${cls}`}>
                                                            {icon} {label}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {messages.map((msg) => (
                                            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                                                <div className={`max-w-[85%] rounded-2xl p-4 ${
                                                    msg.role === "user"
                                                        ? "bg-purple-600 text-white"
                                                        : msg.type === "error"
                                                            ? "bg-red-50 border border-red-200"
                                                            : "bg-white border border-gray-200 shadow-sm"
                                                }`}>
                                                    <div className="flex items-center gap-2 mb-2">
                                                        {msg.role === "assistant" ? (
                                                            <>
                                                                <Bot size={16} className={msg.type === "error" ? "text-red-500" : "text-purple-600"} />
                                                                <span className={`text-xs font-medium ${msg.type === "error" ? "text-red-600" : "text-gray-500"}`}>
                                                                    {msg.type === "schedule" ? "Schedule" :
                                                                     msg.type === "advice"   ? (mode === "coach" ? "Coach" : "Advice") :
                                                                     msg.type === "analysis" ? "Analysis" :
                                                                     msg.type === "progress" ? "Progress" :
                                                                     msg.type === "success"  ? "Success"  : (mode === "coach" ? "Coach" : "AI Coach")}
                                                                </span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <User size={16} className="text-white/80" />
                                                                <span className="text-xs text-white/80">You</span>
                                                            </>
                                                        )}
                                                    </div>
                                                    {renderMessageContent(msg)}
                                                    <div className="mt-2 text-right">
                                                        <span className={`text-xs ${msg.role === "user" ? "text-white/60" : "text-gray-400"}`}>
                                                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                        {isLoading && (
                                            <div className="flex justify-start">
                                                <div className="bg-white border border-gray-200 rounded-2xl p-4">
                                                    <div className="flex items-center gap-2">
                                                        <Bot size={16} className="text-purple-600 animate-pulse" />
                                                        <div className="flex gap-1">
                                                            {[0, 150, 300].map(d => (
                                                                <div key={d} className="w-2 h-2 bg-purple-600 rounded-full animate-bounce"
                                                                     style={{ animationDelay: `${d}ms` }} />
                                                            ))}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        <div ref={messagesEndRef} />
                                    </div>
                                )}
                            </div>

                            {/* Input */}
                            <div className="p-4 border-t bg-white">
                                <div className="flex items-end gap-2">
                                    <textarea
                                        ref={inputRef}
                                        value={input}
                                        onChange={(e) => setInput(e.target.value)}
                                        onKeyPress={handleKeyPress}
                                        placeholder={mode === "coach" ? "Ask about your productivity..." : "Tell me what's on your plate today..."}
                                        className="flex-1 border rounded-xl p-3 max-h-32 min-h-[44px] resize-none focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                        rows="1"
                                        disabled={isLoading}
                                    />
                                    <button 
                                        onClick={handleSendClick}
                                        disabled={!input.trim() || isLoading}
                                        className={`p-3 rounded-xl transition ${
                                            !input.trim() || isLoading
                                                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                                : "bg-purple-600 text-white hover:bg-purple-700"
                                        }`}>
                                        <Send size={18} />
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Side panel — expanded only */}
                        {isExpanded && (
                            <div className="w-80 bg-gray-50 overflow-y-auto p-4">
                                {productivityProfile && (
                                    <div className="mb-6">
                                        <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                                            <Target size={16} className="text-purple-600" /> Productivity Score
                                        </h4>
                                        <div className="bg-white rounded-xl p-4 border border-gray-200">
                                            <div className="text-center mb-3">
                                                <div className="text-3xl font-bold text-purple-600">
                                                    {typeof productivityProfile.productivity_score === 'object'
                                                        ? productivityProfile.productivity_score?.overall || 0
                                                        : productivityProfile.productivity_score || 0}
                                                </div>
                                                <div className="text-xs text-gray-500">out of 100</div>
                                            </div>
                                            <div className="space-y-2">
                                                {Object.entries(
                                                    (typeof productivityProfile.productivity_score === 'object'
                                                        ? productivityProfile.productivity_score?.components
                                                        : {}) || {}
                                                ).map(([k, v]) => (
                                                    <div key={k}>
                                                        <div className="flex justify-between text-xs mb-1">
                                                            <span className="text-gray-600 capitalize">{k}</span>
                                                            <span className="font-medium">{v}%</span>
                                                        </div>
                                                        <div className="w-full bg-gray-200 rounded-full h-1.5">
                                                            <div className="bg-purple-600 h-1.5 rounded-full" style={{ width: `${v}%` }} />
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                )}
                                {productivityProfile?.peak_hours?.peak_hours?.length > 0 && (
                                    <div className="mb-6">
                                        <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                                            <Clock size={16} className="text-purple-600" /> Peak Hours
                                        </h4>
                                        <div className="bg-white rounded-xl p-4 border border-gray-200 flex flex-wrap gap-2">
                                            {productivityProfile.peak_hours.peak_hours.map(h => (
                                                <span key={h} className="bg-purple-100 text-purple-700 px-3 py-1 rounded-full text-xs font-medium">
                                                    {h}:00
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {recommendations.priority_tasks?.length > 0 && (
                                    <div className="mb-6">
                                        <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                                            <Zap size={16} className="text-yellow-500" /> Priority Tasks
                                        </h4>
                                        <div className="space-y-2">
                                            {recommendations.priority_tasks.slice(0, 3).map((item, idx) => (
                                                <div key={idx} className="bg-white rounded-xl p-3 border border-gray-200">
                                                    <div className="flex items-start gap-2">
                                                        <span className="text-xs font-bold text-gray-500 bg-gray-200 rounded-full w-5 h-5 flex items-center justify-center flex-shrink-0">{idx + 1}</span>
                                                        <div>
                                                            <p className="text-sm font-medium text-gray-800">{item.task?.name || "Task"}</p>
                                                            <p className="text-xs text-gray-500 mt-1">{item.reason}</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {recommendations.productivity_boosters?.length > 0 && (
                                    <div className="mb-6">
                                        <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                                            <Lightbulb size={16} className="text-yellow-500" /> Boosters
                                        </h4>
                                        <div className="space-y-2">
                                            {recommendations.productivity_boosters.map((b, i) => (
                                                <div key={i} className="bg-white rounded-xl p-3 border border-gray-200 text-sm">{b}</div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {recommendations.task_optimizations?.length > 0 && (
                                    <div className="mb-6">
                                        <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                                            <BarChart size={16} className="text-green-500" /> Optimizations
                                        </h4>
                                        <div className="space-y-2">
                                            {recommendations.task_optimizations.map((o, i) => (
                                                <div key={i} className="bg-white rounded-xl p-3 border border-gray-200 text-sm">{o}</div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {userContext?.has_history && (
                                    <button onClick={trainModel}
                                            className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl p-3 text-sm font-medium hover:shadow-lg transition">
                                        Train AI Model on My Data
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Productivity Profile Modal */}
            {showProductivityProfile && productivityProfile && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4">
                    <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                        <div className="p-6 border-b sticky top-0 bg-white flex justify-between items-center">
                            <h2 className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-indigo-600 bg-clip-text text-transparent">
                                Your Productivity Profile
                            </h2>
                            <button onClick={() => setShowProductivityProfile(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="p-6 space-y-6">
                            <div className="text-center">
                                <div className="inline-flex w-32 h-32 rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 items-center justify-center mb-4">
                                    <span className="text-3xl font-bold text-white">
                                        {typeof productivityProfile.productivity_score === 'object'
                                            ? productivityProfile.productivity_score?.overall || 0
                                            : productivityProfile.productivity_score || 0}
                                    </span>
                                </div>
                                <p className="text-gray-600">Overall Productivity Score</p>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                {Object.entries(
                                    (typeof productivityProfile.productivity_score === 'object'
                                        ? productivityProfile.productivity_score?.components
                                        : {}) || {}
                                ).map(([k, v]) => (
                                    <div key={k} className="bg-gray-50 p-4 rounded-lg">
                                        <p className="text-sm text-gray-500 capitalize">{k}</p>
                                        <p className="text-2xl font-bold text-gray-800">{v}%</p>
                                    </div>
                                ))}
                            </div>
                            {productivityProfile.peak_hours?.peak_hours?.length > 0 && (
                                <div>
                                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                                        <Clock size={18} className="text-purple-600" /> Peak Productivity Hours
                                    </h3>
                                    <div className="flex flex-wrap gap-2">
                                        {productivityProfile.peak_hours.peak_hours.map(h => (
                                            <span key={h} className="bg-purple-100 text-purple-700 px-4 py-2 rounded-full text-sm font-medium">{h}:00</span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {productivityProfile.recommendations?.length > 0 && (
                                <div>
                                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                                        <Lightbulb size={18} className="text-yellow-500" /> Personalized Recommendations
                                    </h3>
                                    <ul className="space-y-3">
                                        {productivityProfile.recommendations.map((rec, i) => (
                                            <li key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                                                <Sparkles size={16} className="text-purple-600 flex-shrink-0 mt-1" />
                                                <span className="text-gray-700">{rec}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {productivityProfile.trends && (
                                <div className="bg-blue-50 p-4 rounded-lg">
                                    <p className="text-blue-800">{productivityProfile.trends.message}</p>
                                </div>
                            )}
                            {productivityProfile.streaks?.current_streak > 0 && (
                                <div className="bg-green-50 p-4 rounded-lg flex items-center justify-between">
                                    <span className="text-green-800 font-medium">Current Streak</span>
                                    <span className="text-2xl font-bold text-green-600">
                                        {productivityProfile.streaks.current_streak} days
                                    </span>
                                </div>
                            )}
                            <button onClick={() => setShowProductivityProfile(false)}
                                    className="w-full bg-purple-600 text-white py-3 rounded-xl font-medium hover:bg-purple-700 transition">
                                Got it!
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
