// frontend/src/components/Onboarding/GrowingUserPrompt.jsx
import { motion } from "framer-motion";
import { TrendingUp, Target, Award, ChevronRight, X } from "lucide-react";
import { useState } from "react";

export const GrowingUserPrompt = ({ taskCount, onDismiss }) => {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const getMessage = () => {
    if (taskCount < 5) {
      return {
        title: "You're getting started!",
        message: "Add 5 more tasks to unlock detailed analytics about your productivity patterns.",
        progress: taskCount * 10,
        next: "Add 5 tasks"
      };
    } else if (taskCount < 10) {
      return {
        title: "Great progress!",
        message: "You're close to unlocking AI-powered insights. Keep going!",
        progress: taskCount * 5,
        next: "Add 3 tasks"
      };
    } else {
      return {
        title: "You're on fire! 🔥",
        message: "You have enough data for basic analytics. Add more tasks for personalized AI recommendations!",
        progress: Math.min(taskCount, 20),
        next: "Reach 20 tasks"
      };
    }
  };

  const msg = getMessage();

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-8 bg-gradient-to-r from-violet-50 to-indigo-50 rounded-2xl p-6 border border-violet-200 relative"
    >
      <button
        onClick={() => {
          setDismissed(true);
          onDismiss?.();
        }}
        className="absolute top-4 right-4 p-1 hover:bg-white rounded-full transition"
      >
        <X size={18} className="text-slate-400" />
      </button>

      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-violet-100 rounded-xl flex items-center justify-center flex-shrink-0">
          <Target className="text-violet-600" size={24} />
        </div>
        
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-slate-800 mb-1">{msg.title}</h3>
          <p className="text-slate-600 mb-4">{msg.message}</p>
          
          {/* Progress Bar */}
          <div className="w-full bg-white rounded-full h-2 mb-2">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${msg.progress}%` }}
              transition={{ duration: 0.5 }}
              className="bg-gradient-to-r from-violet-600 to-indigo-600 h-2 rounded-full"
            />
          </div>
          
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">Current: {taskCount} tasks</span>
            <span className="text-violet-600 font-medium">Next: {msg.next}</span>
          </div>
        </div>

        <button className="flex items-center gap-1 text-violet-600 hover:text-violet-700 font-medium">
          View Goals <ChevronRight size={16} />
        </button>
      </div>
    </motion.div>
  );
};