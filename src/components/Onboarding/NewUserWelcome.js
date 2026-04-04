// frontend/src/components/Onboarding/NewUserWelcome.jsx
import { motion } from "framer-motion";
import { Sparkles, ArrowRight, Calendar, Target, Brain, TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";

export const NewUserWelcome = () => {
  const navigate = useNavigate();

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto py-12 px-4"
    >
      {/* Hero Section */}
      <div className="text-center mb-12">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
          className="w-24 h-24 bg-gradient-to-br from-violet-100 to-indigo-100 rounded-full flex items-center justify-center mx-auto mb-6"
        >
          <Sparkles className="text-violet-600" size={40} />
        </motion.div>
        
        <h1 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
          Welcome to TIMEVORA!
        </h1>
        
        <p className="text-xl text-slate-600 max-w-2xl mx-auto">
          Your journey to better productivity starts here. Let's set up your first tasks and unlock AI-powered insights.
        </p>
      </div>

      {/* Features Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-2xl p-6 shadow-lg border border-violet-100"
        >
          <div className="w-12 h-12 bg-violet-100 rounded-xl flex items-center justify-center mb-4">
            <Calendar className="text-violet-600" size={24} />
          </div>
          <h3 className="text-lg font-semibold mb-2">Smart Scheduling</h3>
          <p className="text-slate-600">
            Tell me your tasks naturally—"Study 2 hours, then gym"—and I'll create the perfect schedule.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-white rounded-2xl p-6 shadow-lg border border-indigo-100"
        >
          <div className="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center mb-4">
            <Brain className="text-indigo-600" size={24} />
          </div>
          <h3 className="text-lg font-semibold mb-2">AI That Learns</h3>
          <p className="text-slate-600">
            The more you use TIMEVORA, the smarter it gets—learning your patterns to make better suggestions.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-white rounded-2xl p-6 shadow-lg border border-emerald-100"
        >
          <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center mb-4">
            <Target className="text-emerald-600" size={24} />
          </div>
          <h3 className="text-lg font-semibold mb-2">Track Progress</h3>
          <p className="text-slate-600">
            See detailed analytics about your productivity patterns and watch yourself improve.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
          className="bg-white rounded-2xl p-6 shadow-lg border border-amber-100"
        >
          <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center mb-4">
            <TrendingUp className="text-amber-600" size={24} />
          </div>
          <h3 className="text-lg font-semibold mb-2">Weekly Insights</h3>
          <p className="text-slate-600">
            Get personalized recommendations to optimize your time and boost productivity.
          </p>
        </motion.div>
      </div>

      {/* Call to Action */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7 }}
        className="text-center"
      >
        <button
          onClick={() => navigate('/unified-planner')}
          className="group inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-xl font-semibold text-lg hover:from-violet-700 hover:to-indigo-700 transition-all shadow-lg hover:shadow-xl"
        >
          <span>Add Your First Task</span>
          <ArrowRight className="group-hover:translate-x-1 transition-transform" size={20} />
        </button>
        <p className="text-sm text-slate-500 mt-4">
          Takes less than 2 minutes to set up your first tasks
        </p>
      </motion.div>

      {/* Sample Prompt */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="mt-12 p-6 bg-slate-50 rounded-xl border border-slate-200"
      >
        <p className="text-sm text-slate-500 mb-2">Try typing something like:</p>
        <div className="flex flex-wrap gap-3">
          {[
            
            "Gym at 5pm",
            "Team meeting tomorrow 10am",
            "Finish project report"
          ].map((example, i) => (
            <span
              key={i}
              className="px-4 py-2 bg-white rounded-full text-sm text-slate-700 border border-slate-200"
            >
              "{example}"
            </span>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
};