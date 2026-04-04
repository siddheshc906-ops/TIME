// frontend/src/pages/FocusPage.jsx
import { useState, useEffect, useRef } from "react";
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Maximize2, 
  Minimize2,
  Volume2,
  VolumeX,
  Sunset,
  Sun,
  Moon,
  Cloud,
  Sparkles,
  Clock,
  Star,
  Flame,
  Zap,
  Target,
  Layers,
  Check,
  X,
  ChevronLeft
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

const BASE_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  };
}

// Background options with clearer gradients and beautiful images
const backgrounds = [
  { 
    id: "default", 
    name: "Default", 
    url: "", 
    gradient: "from-violet-200/30 to-indigo-200/30",
    icon: Sun,
    description: "Clean and minimal",
    color: "violet",
    sound: null, // no sound for default clean mode
    soundLabel: "No Sound"
  },
  { 
    id: "sunset", 
    name: "Sunset", 
    url: "https://images.unsplash.com/photo-1506815444479-bfdb1e96c566?q=80&w=2070&auto=format&fit=crop",
    gradient: "from-orange-200/30 to-rose-200/30",
    icon: Sunset,
    description: "Warm and inspiring",
    color: "orange",
    sound: "/sounds/Sunset.mp3",
    soundLabel: "Sunset Vibes"
  },
  { 
    id: "ocean", 
    name: "Ocean", 
    url: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=2073&auto=format&fit=crop",
    gradient: "from-blue-200/30 to-cyan-200/30",
    icon: Moon,
    description: "Calm and productive",
    color: "blue",
    sound: "/sounds/Ocean.mp3",
    soundLabel: "Ocean Waves"
  },
  { 
    id: "forest", 
    name: "Forest", 
    url: "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=2070&auto=format&fit=crop",
    gradient: "from-green-200/30 to-emerald-200/30",
    icon: Cloud,
    description: "Natural and grounding",
    color: "green",
    sound: "/sounds/Forest.mp3",
    soundLabel: "Forest Sounds"
  },
  { 
    id: "fireplace", 
    name: "Fireplace", 
    url: "https://i.pinimg.com/originals/6b/82/f3/6b82f339588a17c8ad4a8d147aa45fe2.jpg",
    gradient: "from-amber-200/30 to-orange-200/30",
    icon: Flame,
    description: "Warm and cozy",
    color: "amber",
    sound: "/sounds/Fireplace.mp3",
    soundLabel: "Crackling Fire"
  },
  { 
    id: "flowers", 
    name: "Flowers", 
    url: "https://images.pexels.com/photos/6985293/pexels-photo-6985293.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2",
    gradient: "from-pink-200/30 to-rose-200/30",
    icon: Flame,
    description: "Calm and beautiful",
    color: "amber",
    sound: "/sounds/Flowers.mp3",
    soundLabel: "Gentle Breeze"
  },
  { 
    id: "study", 
    name: "Study", 
    url: "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?q=80&w=2073&auto=format&fit=crop",
    gradient: "from-stone-200/30 to-slate-200/30",
    icon: Target,
    description: "Focused and productive",
    color: "stone",
    sound: "/sounds/Study.mp3",
    soundLabel: "Study Ambiance"
  },
];

// Motivational messages
const motivationalMessages = [
  { message: "You're one session away from greatness", icon: Star },
  { message: "Small steps lead to big results", icon: Target },
  { message: "Focus on today, shape your tomorrow", icon: Sparkles },
  { message: "Every minute counts, make it matter", icon: Clock },
  { message: "Your future self will thank you", icon: Flame },
  { message: "Consistency beats intensity", icon: Zap },
];

export const FocusPage = () => {
  // Timer state
  const [currentScreen, setCurrentScreen] = useState("setup");
  const [customHours, setCustomHours] = useState(0);
  const [customMinutes, setCustomMinutes] = useState(0);
  const [customSeconds, setCustomSeconds] = useState(0);
  
  // Timer running state
  const [totalSeconds, setTotalSeconds] = useState(0);
  const [initialTotalSeconds, setInitialTotalSeconds] = useState(0);
  const [isActive, setIsActive] = useState(false);
  const [sessions, setSessions] = useState(0);
  const [randomMessage, setRandomMessage] = useState(motivationalMessages[4]); // "Your future self will thank you"
  
  // Focus score tracking
  const [focusScore, setFocusScore] = useState(0);
  const [totalFocusMinutes, setTotalFocusMinutes] = useState(0);
  const [dailyGoal, setDailyGoal] = useState(60); // 60 minutes daily goal
  const [weeklyGoal, setWeeklyGoal] = useState(300); // 5 hours weekly goal
  const [weeklyFocusMinutes, setWeeklyFocusMinutes] = useState(0);
  const [streak, setStreak] = useState(0);
  const [lastFocusDate, setLastFocusDate] = useState(null);
  
  // Flipping animation state
  const [prevMinutes, setPrevMinutes] = useState(0);
  const [prevSeconds, setPrevSeconds] = useState(0);
  const [isFlipping, setIsFlipping] = useState(false);
  
  // UI state
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedBg, setSelectedBg] = useState(backgrounds[0]);
  const [showBgSelector, setShowBgSelector] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [volume, setVolume] = useState(0.35);
  const [isMinimized, setIsMinimized] = useState(false); // minimized pill mode
  
  // Refs
  const intervalRef = useRef(null);
  const selectorRef = useRef(null);
  const sessionStartTimeRef = useRef(null);
  const ambientAudioRef = useRef(null); // ref for ambient bg sound

  // Load user's focus stats from backend
  useEffect(() => {
    loadFocusStats();
    loadFocusHistory();
    setRandomMessage(motivationalMessages[Math.floor(Math.random() * motivationalMessages.length)]);
  }, []);

  // Save focus stats to localStorage and backend
  const saveFocusStats = async (minutes) => {
    try {
      // Save to backend
      await fetch(`${BASE_URL}/api/task-feedback`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          name: "Focus Session",
          difficulty: "medium",
          priority: "medium",
          aiTime: minutes / 60,
          actualTime: minutes / 60
        })
      });
      
      // Also store in localStorage for quick access
      const storedStats = localStorage.getItem("focusStats");
      let stats = storedStats ? JSON.parse(storedStats) : {
        totalMinutes: 0,
        weeklyMinutes: 0,
        dailyMinutes: 0,
        streak: 0,
        lastFocusDate: null,
        sessions: []
      };
      
      stats.totalMinutes += minutes;
      stats.weeklyMinutes += minutes;
      stats.dailyMinutes += minutes;
      stats.sessions.push({
        date: new Date().toISOString(),
        duration: minutes,
        timestamp: Date.now()
      });
      
      // Keep only last 30 days of sessions
      const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
      stats.sessions = stats.sessions.filter(s => s.timestamp > thirtyDaysAgo);
      
      // Update streak
      const today = new Date().toDateString();
      if (stats.lastFocusDate === today) {
        // Already focused today, don't increase streak
      } else if (stats.lastFocusDate === new Date(Date.now() - 86400000).toDateString()) {
        stats.streak += 1;
      } else {
        stats.streak = 1;
      }
      stats.lastFocusDate = today;
      
      // Reset daily minutes if new day
      const lastDate = stats.lastFocusDate;
      if (lastDate !== today) {
        stats.dailyMinutes = minutes;
      }
      
      // Reset weekly minutes if new week
      const currentWeek = getWeekNumber(new Date());
      if (stats.currentWeek !== currentWeek) {
        stats.weeklyMinutes = minutes;
        stats.currentWeek = currentWeek;
      }
      
      localStorage.setItem("focusStats", JSON.stringify(stats));
      
      // Update state
      setTotalFocusMinutes(stats.totalMinutes);
      setWeeklyFocusMinutes(stats.weeklyMinutes);
      setStreak(stats.streak);
      
      // Calculate focus score
      calculateFocusScore(stats);
      
    } catch (err) {
      console.error("Failed to save focus stats:", err);
    }
  };
  
  const getWeekNumber = (date) => {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  };
  
  const calculateFocusScore = (stats) => {
    // Calculate score based on multiple factors
    let score = 0;
    
    // Factor 1: Daily goal achievement (max 30 points)
    const dailyProgress = Math.min(stats.dailyMinutes / dailyGoal, 1);
    score += dailyProgress * 30;
    
    // Factor 2: Weekly goal achievement (max 25 points)
    const weeklyProgress = Math.min(stats.weeklyMinutes / weeklyGoal, 1);
    score += weeklyProgress * 25;
    
    // Factor 3: Consistency (streak) (max 20 points)
    const streakBonus = Math.min(stats.streak / 30, 1) * 20;
    score += streakBonus;
    
    // Factor 4: Total focus time (max 15 points)
    const totalHours = stats.totalMinutes / 60;
    const totalBonus = Math.min(totalHours / 100, 1) * 15;
    score += totalBonus;
    
    // Factor 5: Recent activity (last 7 days) (max 10 points)
    const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const recentSessions = stats.sessions.filter(s => s.timestamp > sevenDaysAgo);
    const recentMinutes = recentSessions.reduce((sum, s) => sum + s.duration, 0);
    const recentBonus = Math.min(recentMinutes / 210, 1) * 10; // 3.5 hours = 210 minutes max
    score += recentBonus;
    
    setFocusScore(Math.min(Math.round(score), 100));
  };
  
  const loadFocusStats = async () => {
    try {
      // Try to load from backend first
      const res = await fetch(`${BASE_URL}/api/productivity-score`, {
        headers: authHeaders()
      });
      const data = await res.json();
      
      if (data && data.focus_hours) {
        setTotalFocusMinutes(data.focus_hours * 60);
        setFocusScore(data.score || 0);
      }
      
      // Also load from localStorage for additional stats
      const storedStats = localStorage.getItem("focusStats");
      if (storedStats) {
        const stats = JSON.parse(storedStats);
        setWeeklyFocusMinutes(stats.weeklyMinutes || 0);
        setStreak(stats.streak || 0);
        setTotalFocusMinutes(stats.totalMinutes || 0);
        calculateFocusScore(stats);
      }
    } catch (err) {
      console.error("Failed to load focus stats:", err);
      
      // Fallback to localStorage only
      const storedStats = localStorage.getItem("focusStats");
      if (storedStats) {
        const stats = JSON.parse(storedStats);
        setTotalFocusMinutes(stats.totalMinutes || 0);
        setWeeklyFocusMinutes(stats.weeklyMinutes || 0);
        setStreak(stats.streak || 0);
        calculateFocusScore(stats);
      }
    }
  };
  
  const loadFocusHistory = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/task-history`, {
        headers: authHeaders()
      });
      if (res.ok) {
        const history = await res.json();
        // Process history to get focus sessions
        const focusSessions = history.filter(h => h.name === "Focus Session" || h.name?.includes("Focus"));
        const totalMinutes = focusSessions.reduce((sum, s) => sum + (s.actualTime || s.aiTime || 0) * 60, 0);
        setTotalFocusMinutes(totalMinutes);
      }
    } catch (err) {
      console.error("Failed to load focus history:", err);
    }
  };

  // Timer logic
  useEffect(() => {
    if (isActive && totalSeconds > 0) {
      intervalRef.current = setInterval(() => {
        setTotalSeconds(prev => {
          if (prev <= 1) {
            handleTimerComplete();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      clearInterval(intervalRef.current);
    }

    return () => clearInterval(intervalRef.current);
  }, [isActive]);

  // ── Ambient sound: play/pause with timer, switch on bg change ──────────────
  useEffect(() => {
    // Stop any existing ambient sound first
    if (ambientAudioRef.current) {
      ambientAudioRef.current.pause();
      ambientAudioRef.current = null;
    }

    if (!soundEnabled || !selectedBg.sound) return;

    const audio = new Audio(selectedBg.sound);
    audio.loop = true;
    audio.volume = volume;
    ambientAudioRef.current = audio;

    if (isActive) {
      audio.play().catch(() => {});
    }

    return () => {
      audio.pause();
      ambientAudioRef.current = null;
    };
  }, [selectedBg, soundEnabled]);

  // ── Play/pause ambient sound when timer starts or pauses ───────────────────
  useEffect(() => {
    if (!ambientAudioRef.current) return;
    if (isActive && soundEnabled) {
      ambientAudioRef.current.play().catch(() => {});
    } else {
      ambientAudioRef.current.pause();
    }
  }, [isActive, soundEnabled]);

  // ── Live volume control ─────────────────────────────────────────────────────
  useEffect(() => {
    if (ambientAudioRef.current) {
      ambientAudioRef.current.volume = soundEnabled ? volume : 0;
    }
  }, [volume, soundEnabled]);

  // ── Stop ambient sound when timer completes or resets ──────────────────────
  useEffect(() => {
    if (currentScreen === "setup" && ambientAudioRef.current) {
      ambientAudioRef.current.pause();
      ambientAudioRef.current.currentTime = 0;
    }
  }, [currentScreen]);
  useEffect(() => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    
    if (mins !== prevMinutes || secs !== prevSeconds) {
      setIsFlipping(true);
      setTimeout(() => setIsFlipping(false), 300);
    }
    
    setPrevMinutes(mins);
    setPrevSeconds(secs);
  }, [totalSeconds]);

  const handleTimerComplete = () => {
    setIsActive(false);
    playAlarm();

    const sessionDuration = initialTotalSeconds;
    const minutesCompleted = Math.round(sessionDuration / 60);
    
    // Save the completed session
    saveFocusStats(minutesCompleted);
    
    setSessions((s) => s + 1);
    
    toast.success(`🎉 Amazing! You completed a ${minutesCompleted} minute focus session!`, {
      duration: 5000,
      icon: "🌟",
      style: {
        background: '#ffffff',
        color: '#1f2937',
        border: '1px solid #e5e7eb'
      }
    });
    
    setRandomMessage(motivationalMessages[Math.floor(Math.random() * motivationalMessages.length)]);
    
    setTimeout(() => {
      setCurrentScreen("setup");
    }, 2000);
  };

  const playAlarm = () => {
    if (!soundEnabled) return;
    
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.setValueAtTime(880, audioContext.currentTime);
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    
    oscillator.start();
    oscillator.stop(audioContext.currentTime + 0.5);
  };

  const startTimer = () => {
    const totalSecs = customHours * 3600 + customMinutes * 60 + customSeconds;
    
    if (totalSecs <= 0) {
      toast.error("Please set a time greater than 0", {
        style: {
          background: '#ffffff',
          color: '#1f2937',
          border: '1px solid #e5e7eb'
        }
      });
      return;
    }
    
    setInitialTotalSeconds(totalSecs);
    setTotalSeconds(totalSecs);
    setCurrentScreen("timer");
    setIsActive(true);

    // ── Start ambient sound directly on user click (bypasses browser autoplay block) ──
    if (soundEnabled && selectedBg.sound) {
      if (ambientAudioRef.current) {
        ambientAudioRef.current.pause();
        ambientAudioRef.current = null;
      }
      const audio = new Audio(selectedBg.sound);
      audio.loop = true;
      audio.volume = volume;
      ambientAudioRef.current = audio;
      audio.play().catch((e) => console.warn("Audio play failed:", e));
    }
    
    toast.success(`Ready to focus for ${formatTime(totalSecs)}!`, {
      style: {
        background: '#ffffff',
        color: '#1f2937',
        border: '1px solid #e5e7eb'
      }
    });
  };

  const formatTime = (totalSecs) => {
    const hours = Math.floor(totalSecs / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${mins}m`;
    }
    return `${mins}m`;
  };

  const getDisplayTime = () => {
    const hours = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    
    if (hours > 0) {
      return {
        hours: String(hours).padStart(2, "0"),
        minutes: String(mins).padStart(2, "0"),
        seconds: String(secs).padStart(2, "0")
      };
    }
    return {
      hours: null,
      minutes: String(mins).padStart(2, "0"),
      seconds: String(secs).padStart(2, "0")
    };
  };

  const toggleTimer = () => {
    const newActive = !isActive;
    setIsActive(newActive);
    // Directly play/pause on user click — avoids browser autoplay restrictions
    if (ambientAudioRef.current) {
      if (newActive && soundEnabled) {
        ambientAudioRef.current.play().catch((e) => console.warn("Audio play failed:", e));
      } else {
        ambientAudioRef.current.pause();
      }
    }
  };

  const resetTimer = () => {
    setIsActive(false);
    setCurrentScreen("setup");
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  };

  const MessageIcon = randomMessage.icon;
  const timeDisplay = getDisplayTime();
  
  // Calculate daily progress percentage
  const dailyProgress = Math.min((totalFocusMinutes / dailyGoal) * 100, 100);
  const weeklyProgress = Math.min((weeklyFocusMinutes / weeklyGoal) * 100, 100);

  // Get accent color
  const getAccentColor = () => {
    const colors = {
      violet: "from-violet-500 to-indigo-500",
      orange: "from-orange-500 to-rose-500",
      blue: "from-blue-500 to-cyan-500",
      green: "from-green-500 to-emerald-500",
      amber: "from-amber-500 to-orange-500",
      stone: "from-stone-500 to-slate-500"
    };
    return colors[selectedBg.color] || colors.violet;
  };

  // Animation variants
  const timerVariants = {
    initial: { scale: 0.8, opacity: 0 },
    animate: { 
      scale: 1, 
      opacity: 1,
      transition: { 
        type: "spring", 
        stiffness: 200, 
        damping: 20 
      }
    },
    exit: { 
      scale: 0.8, 
      opacity: 0,
      transition: { duration: 0.3 }
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-x-hidden">
      {/* Fixed Background Layer */}
      <div className="fixed inset-0 -z-10">
        <div 
          className="absolute inset-0 transition-opacity duration-1000"
          style={{
            backgroundImage: selectedBg.url ? `url(${selectedBg.url})` : 'none',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            backgroundRepeat: 'no-repeat',
            opacity: selectedBg.url ? 0.95 : 0,
            filter: 'contrast(1.1) brightness(1.05) saturate(1.1)',
          }}
        />
        <div className={`absolute inset-0 bg-gradient-to-br ${selectedBg.gradient} transition-opacity duration-1000 ${
          selectedBg.url ? 'opacity-20' : 'opacity-100'
        }`} />
      </div>

      {/* Main content */}
      <div className="relative z-10 min-h-screen w-full pt-16">
        <div className={`w-full transition-all duration-500 ${
          currentScreen === "timer" 
            ? "flex items-center justify-center min-h-[calc(100vh-4rem)] p-4" 
            : "py-8 px-4 md:px-8 lg:px-12"
        }`}>
          <div className={currentScreen === "timer" ? "w-full max-w-md" : "max-w-2xl mx-auto"}>
            
            {/* Header with controls - Only show in setup mode */}
            {currentScreen === "setup" && (
              <motion.div 
                initial={{ y: -50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ type: "spring", stiffness: 100 }}
                className="flex justify-between items-center mb-8"
              >
                <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
                  TimeVora
                </h1>
                
                <div className="flex gap-3">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setShowBgSelector(!showBgSelector)}
                    className={`relative px-4 py-2 bg-white/90 backdrop-blur rounded-lg shadow-md hover:shadow-lg transition-all duration-300 flex items-center gap-2 border ${
                      showBgSelector ? 'border-violet-400' : 'border-white/20'
                    }`}
                  >
                    <Layers size={18} className="text-violet-600" />
                    <span className="text-sm font-medium text-gray-700">Ambiance</span>
                    <div className={`w-2 h-2 rounded-full bg-${selectedBg.color}-500`} />
                  </motion.button>
                </div>
              </motion.div>
            )}

            {/* Background Selector Panel */}
            {currentScreen === "setup" && (
              <AnimatePresence>
                {showBgSelector && (
                  <motion.div
                    ref={selectorRef}
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    transition={{ duration: 0.2 }}
                    className="mb-6 bg-white/95 backdrop-blur-xl rounded-xl shadow-2xl border border-gray-100 overflow-hidden"
                  >
                    {/* Panel Header */}
                    <div className="px-5 py-4 border-b border-gray-100">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-violet-50 rounded-lg">
                            <Layers size={18} className="text-violet-600" />
                          </div>
                          <div>
                            <h3 className="font-semibold text-gray-800">Choose Your Ambiance</h3>
                            <p className="text-xs text-gray-500 mt-0.5">Select a background that matches your mood</p>
                          </div>
                        </div>
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={() => setShowBgSelector(false)}
                          className="p-1.5 hover:bg-gray-100 rounded-lg transition"
                        >
                          <X size={16} className="text-gray-400" />
                        </motion.button>
                      </div>
                    </div>

                    {/* Background Grid */}
                    <div className="p-5">
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-3">
                        {backgrounds.map((bg) => {
                          const Icon = bg.icon;
                          const isSelected = selectedBg.id === bg.id;
                          
                          return (
                            <motion.button
                              key={bg.id}
                              whileHover={{ y: -2 }}
                              whileTap={{ scale: 0.98 }}
                              onClick={() => setSelectedBg(bg)}
                              className="group relative"
                            >
                              <div className={`relative rounded-xl overflow-hidden transition-all duration-300 ${
                                isSelected 
                                  ? 'ring-2 ring-violet-500 ring-offset-2' 
                                  : 'hover:ring-2 hover:ring-gray-300 hover:ring-offset-2'
                              }`}>
                                <div className={`w-full h-20 bg-gradient-to-br ${bg.gradient}`}>
                                  {bg.url && (
                                    <div 
                                      className="w-full h-full opacity-95 group-hover:opacity-100 transition-opacity"
                                      style={{
                                        backgroundImage: `url(${bg.url})`,
                                        backgroundSize: 'cover',
                                        backgroundPosition: 'center',
                                        filter: 'contrast(1.05) brightness(1.02)',
                                      }}
                                    />
                                  )}
                                </div>
                                
                                <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/5 transition">
                                  <Icon 
                                    size={24} 
                                    className={`${
                                      isSelected 
                                        ? 'text-violet-600' 
                                        : 'text-gray-600 group-hover:text-gray-800'
                                    } transition-colors`}
                                  />
                                </div>

                                {isSelected && (
                                  <div className="absolute top-2 right-2 w-4 h-4 bg-violet-500 rounded-full flex items-center justify-center">
                                    <Check size={10} className="text-white" />
                                  </div>
                                )}
                              </div>
                              
                              <div className="mt-2 text-center">
                                <p className={`text-xs font-medium ${
                                  isSelected ? 'text-violet-600' : 'text-gray-600'
                                }`}>
                                  {bg.name}
                                </p>
                                <p className="text-[10px] text-gray-400 mt-0.5">
                                  {bg.description}
                                </p>
                              </div>
                            </motion.button>
                          );
                        })}
                      </div>

                      <div className="mt-4 pt-3 border-t border-gray-100">
                        <p className="text-xs text-gray-400 flex items-center justify-center gap-1">
                          <span>✨</span>
                          The ambiance changes automatically based on your selection
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            )}

            {/* Main Card - Setup or Timer */}
            <AnimatePresence mode="wait">
              {currentScreen === "setup" ? (
                /* ========== SETUP SCREEN ========== */
                <motion.div
                  key="setup"
                  variants={timerVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  className="bg-white/80 backdrop-blur rounded-3xl p-8 shadow-2xl border border-white/50"
                >
                  <div className="space-y-6">
                    {/* Motivational Message */}
                    <motion.div
                      variants={{
                        animate: {
                          scale: [1, 1.02, 1],
                          transition: {
                            duration: 3,
                            repeat: Infinity,
                            ease: "easeInOut"
                          }
                        }
                      }}
                      animate="animate"
                      className="text-center"
                    >
                      <div className="inline-flex items-center justify-center gap-3 mb-3">
                        <MessageIcon className={`text-${selectedBg.color}-600`} size={32} />
                      </div>
                      <h2 className="text-2xl font-semibold text-gray-800 mb-2">
                        {randomMessage.message}
                      </h2>
                      <motion.p 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.5 }}
                        className="text-gray-500 text-sm"
                      >
                        {sessions} sessions completed today
                      </motion.p>
                    </motion.div>

                    {/* Timer Setup Card */}
                    <motion.div
                      initial={{ y: 50, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      transition={{ delay: 0.3, type: "spring" }}
                      className={`bg-gradient-to-br from-${selectedBg.color}-50 to-${selectedBg.color}-50/50 p-6 rounded-2xl border-2 border-${selectedBg.color}-200`}
                    >
                      <h3 className="font-semibold text-center mb-4 text-gray-700">
                        Set Your Focus Time
                      </h3>
                      
                      <div className="grid grid-cols-3 gap-3 mb-4">
                        <motion.div whileHover={{ scale: 1.02 }}>
                          <label className="block text-xs text-gray-500 mb-1">Hours</label>
                          <input
                            type="number"
                            min="0"
                            max="23"
                            value={customHours}
                            onChange={(e) => setCustomHours(parseInt(e.target.value) || 0)}
                            className={`w-full px-3 py-2 text-center border rounded-xl focus:ring-2 focus:ring-${selectedBg.color}-500 bg-white/80`}
                          />
                        </motion.div>
                        <motion.div whileHover={{ scale: 1.02 }}>
                          <label className="block text-xs text-gray-500 mb-1">Minutes</label>
                          <input
                            type="number"
                            min="0"
                            max="59"
                            value={customMinutes}
                            onChange={(e) => setCustomMinutes(parseInt(e.target.value) || 0)}
                            className={`w-full px-3 py-2 text-center border rounded-xl focus:ring-2 focus:ring-${selectedBg.color}-500 bg-white/80`}
                          />
                        </motion.div>
                        <motion.div whileHover={{ scale: 1.02 }}>
                          <label className="block text-xs text-gray-500 mb-1">Seconds</label>
                          <input
                            type="number"
                            min="0"
                            max="59"
                            value={customSeconds}
                            onChange={(e) => setCustomSeconds(parseInt(e.target.value) || 0)}
                            className={`w-full px-3 py-2 text-center border rounded-xl focus:ring-2 focus:ring-${selectedBg.color}-500 bg-white/80`}
                          />
                        </motion.div>
                      </div>

                      {/* Quick suggestions */}
                      <div className="flex justify-center gap-2 mb-4">
                        {[5, 15, 25, 45].map((mins) => (
                          <motion.button
                            key={mins}
                            whileHover={{ scale: 1.05, y: -1 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={() => {
                              setCustomHours(0);
                              setCustomMinutes(mins);
                              setCustomSeconds(0);
                            }}
                            className={`px-3 py-1 bg-white/90 rounded-full text-xs border hover:border-${selectedBg.color}-500 transition shadow-sm text-gray-600`}
                          >
                            {mins}m
                          </motion.button>
                        ))}
                      </div>

                      <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={startTimer}
                        className={`w-full py-3 bg-gradient-to-r ${getAccentColor()} text-white rounded-xl font-semibold shadow-lg hover:shadow-xl transition flex items-center justify-center gap-2`}
                      >
                        <Play size={20} />
                        Begin Your Focus Session
                      </motion.button>
                    </motion.div>

                    {/* Sound toggle */}
                    <motion.div 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.6 }}
                      className="flex justify-center gap-4 text-sm text-gray-500"
                    >
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        onClick={() => setSoundEnabled(!soundEnabled)}
                        className="flex items-center gap-1 hover:text-gray-700"
                      >
                        {soundEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
                        {soundEnabled
                          ? `${selectedBg.soundLabel || "Sound"} On`
                          : "Sound Off"}
                      </motion.button>
                    </motion.div>
                  </div>
                </motion.div>
              ) : (
                /* ========== TIMER SCREEN — draggable + minimizable ========== */
                <motion.div
                  key="timer"
                  drag
                  dragMomentum={false}
                  dragElastic={0}
                  dragTransition={{ power: 0, timeConstant: 0 }}
                  whileDrag={{ scale: 1.02, boxShadow: "0 30px 60px rgba(0,0,0,0.2)" }}
                  variants={timerVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  style={{ cursor: "grab", position: "relative", touchAction: "none" }}
                  className={`bg-white/30 backdrop-blur-md border border-white/40 shadow-xl select-none transition-all duration-300 ${
                    isMinimized
                      ? "rounded-full px-5 py-3 w-fit mx-auto"
                      : "rounded-3xl p-8"
                  }`}
                >
                  {/* ── Top-right action buttons ── */}
                  <div className="absolute top-3 right-3 flex gap-1.5 z-50">
                    {/* Minimize / Expand toggle */}
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={() => setIsMinimized(!isMinimized)}
                      className="p-1.5 bg-white/80 backdrop-blur rounded-lg shadow-md hover:shadow-lg transition-all"
                      title={isMinimized ? "Expand timer" : "Minimise timer"}
                    >
                      {isMinimized
                        ? <Maximize2 size={15} className="text-gray-600" />
                        : <Minimize2 size={15} className="text-gray-600" />
                      }
                    </motion.button>

                    {/* Fullscreen toggle — only in expanded mode */}
                    {!isMinimized && (
                      <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={toggleFullscreen}
                        className="p-1.5 bg-white/80 backdrop-blur rounded-lg shadow-md hover:shadow-lg transition-all"
                        title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
                      >
                        {isFullscreen
                          ? <Minimize2 size={15} className="text-gray-600" />
                          : <Maximize2 size={15} className="text-gray-600" />
                        }
                      </motion.button>
                    )}
                  </div>

                  {/* ── MINIMIZED PILL VIEW ── */}
                  {isMinimized ? (
                    <div
                      className="flex items-center gap-3 pr-14"
                      onPointerDown={(e) => e.stopPropagation()}
                    >
                      {/* Mini play/pause */}
                      <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={toggleTimer}
                        className={`p-1.5 bg-gradient-to-r ${getAccentColor()} text-white rounded-full shadow flex-shrink-0`}
                      >
                        {isActive ? <Pause size={14} /> : <Play size={14} />}
                      </motion.button>

                      {/* Mini timer digits */}
                      <span className="text-xl font-bold font-mono text-gray-800 tracking-wider">
                        {timeDisplay.minutes}:{timeDisplay.seconds}
                      </span>

                      {/* Mini sound mute */}
                      {selectedBg.sound && (
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={() => setSoundEnabled(!soundEnabled)}
                          className="text-gray-500 hover:text-gray-800 flex-shrink-0"
                        >
                          {soundEnabled && volume > 0
                            ? <Volume2 size={14} />
                            : <VolumeX size={14} />
                          }
                        </motion.button>
                      )}
                    </div>
                  ) : (
                  /* ── EXPANDED FULL VIEW ── */
                  <div onPointerDown={(e) => e.stopPropagation()}>
                    {/* Drag hint */}
                    <div className="flex justify-center mb-2 mt-1">
                      <div className="w-8 h-1 bg-white/40 rounded-full" title="Drag to move" />
                    </div>

                    {/* Motivational message */}
                    <motion.div
                      initial={{ y: -20, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      className="text-center mb-8 mt-2"
                    >
                      <p className="text-lg text-gray-700 font-light italic">
                        "{randomMessage.message.toLowerCase()}"
                      </p>
                    </motion.div>

                    {/* Timer Display */}
                    <motion.div
                      className="flex justify-center mb-10"
                      animate={{ scale: isActive ? [1, 1.02, 1] : 1 }}
                      transition={{ duration: 2, repeat: isActive ? Infinity : 0 }}
                    >
                      <div className="text-center">
                        <div className="flex items-center justify-center">
                          <span className="text-8xl font-bold text-gray-800 font-mono tracking-wider">
                            {timeDisplay.minutes}
                          </span>
                          <span className="text-6xl text-gray-600 mx-1">:</span>
                          <span className="text-8xl font-bold text-gray-800 font-mono tracking-wider">
                            {timeDisplay.seconds}
                          </span>
                        </div>
                      </div>
                    </motion.div>

                    {/* Controls */}
                    <div className="flex justify-center gap-4 mb-6">
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={toggleTimer}
                        className={`px-8 py-3 bg-gradient-to-r ${getAccentColor()} text-white rounded-full font-semibold shadow-lg flex items-center justify-center gap-2 min-w-[120px]`}
                      >
                        {isActive ? <><Pause size={20} />Pause</> : <><Play size={20} />Start</>}
                      </motion.button>

                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={resetTimer}
                        className="px-8 py-3 bg-white/80 text-gray-700 rounded-full font-semibold shadow-lg hover:shadow-xl flex items-center justify-center gap-2 border border-gray-200"
                      >
                        <RotateCcw size={20} /> Reset
                      </motion.button>
                    </div>

                    {/* Ambient Sound Control */}
                    {selectedBg.sound && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="mx-auto mb-4 px-5 py-3 bg-white/20 backdrop-blur-md rounded-2xl border border-white/30 shadow-inner flex items-center gap-3 max-w-xs"
                      >
                        <motion.button
                          whileHover={{ scale: 1.15 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={() => {
                            const newEnabled = !soundEnabled;
                            setSoundEnabled(newEnabled);
                            if (ambientAudioRef.current) {
                              if (newEnabled) {
                                ambientAudioRef.current.volume = volume;
                                ambientAudioRef.current.play().catch(() => {});
                              } else {
                                ambientAudioRef.current.pause();
                              }
                            }
                          }}
                          className="text-gray-700 hover:text-gray-900 flex-shrink-0"
                        >
                          {soundEnabled && volume > 0 ? <Volume2 size={18} /> : <VolumeX size={18} />}
                        </motion.button>
                        <div className="flex-1">
                          <input
                            type="range" min="0" max="1" step="0.01"
                            value={soundEnabled ? volume : 0}
                            onPointerDown={(e) => e.stopPropagation()}
                            onMouseDown={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value);
                              setVolume(val);
                              // directly set on audio object immediately — no useEffect delay
                              if (ambientAudioRef.current) {
                                ambientAudioRef.current.volume = val;
                              }
                              if (val > 0 && !soundEnabled) {
                                setSoundEnabled(true);
                                if (ambientAudioRef.current) {
                                  ambientAudioRef.current.play().catch(() => {});
                                }
                              }
                              if (val === 0) {
                                setSoundEnabled(false);
                                if (ambientAudioRef.current) {
                                  ambientAudioRef.current.pause();
                                }
                              }
                            }}
                            className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                            style={{
                              background: `linear-gradient(to right, rgba(139,92,246,0.8) 0%, rgba(139,92,246,0.8) ${(soundEnabled ? volume : 0) * 100}%, rgba(255,255,255,0.3) ${(soundEnabled ? volume : 0) * 100}%, rgba(255,255,255,0.3) 100%)`
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-600 flex-shrink-0 font-medium">
                          {selectedBg.soundLabel}
                        </span>
                      </motion.div>
                    )}

                    {/* Back button */}
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.5 }}
                      className="text-center"
                    >
                      <motion.button
                        whileHover={{ x: -5 }}
                        onClick={() => setCurrentScreen("setup")}
                        className="text-gray-500 hover:text-gray-700 text-sm flex items-center gap-1 mx-auto"
                      >
                        <ChevronLeft size={16} />
                        Set new timer
                      </motion.button>
                    </motion.div>
                  </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
};