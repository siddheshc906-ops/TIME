// frontend/src/components/LoadingSkeleton.jsx
import { motion } from "framer-motion";

export const TaskSkeleton = () => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="animate-pulse bg-white/80 rounded-xl p-4 border shadow-sm"
  >
    <div className="flex gap-4 items-start">
      <div className="w-6 h-6 bg-slate-200 rounded-full"></div>
      <div className="flex-1">
        <div className="h-5 bg-slate-200 rounded w-3/4 mb-3"></div>
        <div className="h-4 bg-slate-200 rounded w-1/2 mb-2"></div>
        <div className="h-3 bg-slate-200 rounded w-1/3"></div>
      </div>
    </div>
  </motion.div>
);

export const StatsCardSkeleton = () => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    className="bg-white rounded-xl p-6 shadow-lg border border-slate-100"
  >
    <div className="flex items-center justify-between mb-4">
      <div className="h-10 w-10 bg-slate-200 rounded-lg"></div>
      <div className="h-8 w-16 bg-slate-200 rounded"></div>
    </div>
    <div className="h-4 bg-slate-200 rounded w-2/3 mb-2"></div>
    <div className="h-3 bg-slate-200 rounded w-1/2"></div>
  </motion.div>
);

export const WeekCardSkeleton = () => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    className="bg-white/80 rounded-2xl border overflow-hidden shadow-lg"
  >
    <div className="bg-gradient-to-r from-slate-300 to-slate-400 p-4">
      <div className="h-6 bg-white/30 rounded w-1/2 mb-2"></div>
      <div className="h-4 bg-white/30 rounded w-1/3"></div>
    </div>
    <div className="p-4 space-y-2">
      <div className="h-10 bg-slate-200 rounded"></div>
      <div className="h-10 bg-slate-200 rounded"></div>
      <div className="h-10 bg-slate-200 rounded"></div>
    </div>
  </motion.div>
);

export const ChartSkeleton = () => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    className="bg-white rounded-2xl p-6 border shadow-lg"
  >
    <div className="h-6 bg-slate-200 rounded w-1/3 mb-6"></div>
    <div className="h-64 bg-slate-100 rounded-lg flex items-center justify-center">
      <span className="text-slate-400">Loading chart...</span>
    </div>
  </motion.div>
);

export const PageSkeleton = () => (
  <div className="space-y-6">
    <div className="h-12 bg-slate-200 rounded w-1/3 mb-8"></div>
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <StatsCardSkeleton />
      <StatsCardSkeleton />
      <StatsCardSkeleton />
      <StatsCardSkeleton />
    </div>
    <ChartSkeleton />
  </div>
);