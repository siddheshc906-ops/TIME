import { Link } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { motion, useScroll, useTransform, useSpring, AnimatePresence } from "framer-motion";
import { 
  Brain, TrendingUp, ArrowRight, 
  Sparkles, Clock,
  Layout, BarChart3,
} from "lucide-react";
import BackgroundLayout from "../components/BackgroundLayout";

export const Landing = () => {
  const [wordIndex, setWordIndex] = useState(0);
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 100, damping: 30 });
  const y1 = useTransform(scrollYProgress, [0, 1], [0, -200]);
  const y2 = useTransform(scrollYProgress, [0, 1], [0, 300]);

  const rotatingWords = ["students.", "developers.", "founders.", "you."];

  // Typewriter word rotation
  useEffect(() => {
    const interval = setInterval(() => {
      setWordIndex(prev => (prev + 1) % rotatingWords.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const features = [
    {
      icon: Layout,
      title: "Time Blocks",
      description: "Plan your whole week in minutes. See every task laid out by day so nothing slips through the cracks.",
      color: "from-indigo-500 to-blue-600",
      link: "/tasks",
      image: "https://images.unsplash.com/photo-1484480974693-6ca0a78fb36b?w=800&q=80",
      delay: 0,
      badge: "New",
    },
    {
      icon: Clock,
      title: "Deep Work",
      description: "Pomodoro timer with ambient sounds — Ocean, Forest, Fireplace. Stay in flow and track every focus session.",
      color: "from-purple-500 to-pink-600",
      link: "/focus",
      image: "https://images.unsplash.com/photo-1528716321680-815a8cdb8cbe?w=800&q=80",
      delay: 0.1,
      badge: "Hot",
    },
    {
      icon: Brain,
      title: "AI Scheduler",
      description: "Type what you need to do. The AI finds the best time based on your personal energy patterns — automatically.",
      color: "from-violet-600 to-indigo-700",
      link: "/ai-planner",
      image: "https://images.unsplash.com/photo-1531746790731-6c087fecd65a?w=800&q=80",
      delay: 0.2,
      badge: "AI Powered",
    },
    {
      icon: BarChart3,
      title: "Analytics Hub",
      description: "See your streaks, focus scores, and peak productivity hours. Know exactly when and how you work best.",
      color: "from-emerald-500 to-teal-600",
      link: "/analytics",
      image: "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&q=80",
      delay: 0.3,
      badge: "Insights",
    },
  ];

  // Reduced to 6 particles (was 20 — too heavy on mobile)
  const particles = Array.from({ length: 6 }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 4 + 2,
    duration: Math.random() * 10 + 5,
    delay: Math.random() * 5,
  }));

  return (
    <>
      {/* Scroll progress bar */}
      <motion.div
        className="fixed top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 to-indigo-500 z-50 origin-left"
        style={{ scaleX }}
      />

      <BackgroundLayout>
        {/* ── Hero ── */}
        <section className="relative pt-20 pb-24 px-6 md:px-12 lg:px-24 overflow-hidden">
          {/* Animated gradient blob */}
          <motion.div
            className="absolute inset-0 -z-10"
            animate={{
              background: [
                "radial-gradient(circle at 0% 0%, rgba(139,92,246,0.1) 0%, transparent 50%)",
                "radial-gradient(circle at 100% 100%, rgba(99,102,241,0.1) 0%, transparent 50%)",
                "radial-gradient(circle at 50% 50%, rgba(139,92,246,0.15) 0%, transparent 50%)",
              ],
            }}
            transition={{ duration: 8, repeat: Infinity, repeatType: "reverse" }}
          />

          {/* Floating particles (6 only) */}
          <div className="absolute inset-0 -z-10 overflow-hidden">
            {particles.map((particle) => (
              <motion.div
                key={particle.id}
                className="absolute rounded-full bg-violet-400/30"
                style={{
                  left: `${particle.x}%`,
                  top: `${particle.y}%`,
                  width: particle.size,
                  height: particle.size,
                }}
                animate={{ y: [0, -30, 0], x: [0, 20, -20, 0], opacity: [0, 0.5, 0] }}
                transition={{ duration: particle.duration, repeat: Infinity, delay: particle.delay, ease: "easeInOut" }}
              />
            ))}
          </div>

          {/* Floating blobs */}
          <motion.div className="absolute top-20 left-10 hidden lg:block" style={{ y: y1 }}>
            <div className="w-32 h-32 bg-gradient-to-r from-violet-500/20 to-purple-500/20 rounded-full blur-2xl" />
          </motion.div>
          <motion.div className="absolute bottom-20 right-10 hidden lg:block" style={{ y: y2 }}>
            <div className="w-40 h-40 bg-gradient-to-r from-indigo-500/20 to-blue-500/20 rounded-full blur-2xl" />
          </motion.div>

          <div className="max-w-7xl mx-auto text-center relative z-10">

            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-block mb-6"
            >
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="px-4 py-2 bg-white/80 backdrop-blur-sm border border-violet-200 rounded-full text-violet-700 text-sm font-medium shadow-lg"
              >
                <Sparkles className="inline w-4 h-4 mr-2" />
                Now in beta — free for everyone
              </motion.div>
            </motion.div>

            {/* Main headline */}
            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-5xl md:text-7xl font-bold text-slate-900 mb-4 leading-tight"
            >
              Your AI planner that{" "}
              <motion.span
                style={{
                  background: "linear-gradient(135deg, #8b5cf6, #6366f1, #8b5cf6)",
                  backgroundSize: "200% auto",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  color: "transparent",
                }}
                animate={{ backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"] }}
                transition={{ duration: 5, repeat: Infinity }}
              >
                thinks for you
              </motion.span>
            </motion.h1>

            {/* Subheadline with typewriter */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.35 }}
              className="text-xl md:text-2xl text-slate-600 mb-3 font-medium"
            >
              Built for{" "}
              <AnimatePresence mode="wait">
                <motion.span
                  key={wordIndex}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.3 }}
                  className="text-violet-600 font-semibold"
                >
                  {rotatingWords[wordIndex]}
                </motion.span>
              </AnimatePresence>
            </motion.div>

            {/* Description */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.45 }}
              className="text-base md:text-lg text-slate-500 mb-10 max-w-2xl mx-auto"
            >
              No manual planning. No guesswork. Timevora learns when your brain works best and schedules your tasks automatically — getting smarter every day.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              {/* Primary CTA with shimmer */}
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Link
                  to="/signup"
                  className="relative overflow-hidden inline-flex items-center gap-2 px-8 py-4 bg-violet-600 text-white rounded-full font-semibold shadow-lg shadow-violet-500/30 hover:bg-violet-700 transition-colors group"
                >
                  {/* Shimmer sweep on hover */}
                  <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent group-hover:translate-x-full transition-transform duration-700" />
                  Get Started Free <ArrowRight size={20} />
                </Link>
              </motion.div>

              {/* Secondary CTA */}
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <a
                  href="#features"
                  className="inline-flex items-center gap-2 px-8 py-4 bg-white/80 backdrop-blur border border-gray-200 rounded-full font-semibold hover:bg-white hover:shadow-lg transition-all text-slate-700"
                >
                  See how it works →
                </a>
              </motion.div>
            </motion.div>

            {/* Trust pills — honest, no fake stats */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
              className="flex flex-wrap justify-center gap-3 mt-10"
            >
              {[
                "✓ Free during beta",
                "✓ You’re good, no charge until you love it",
                "✓ Built by a student, for students",
              ].map((pill) => (
                <span
                  key={pill}
                  className="px-4 py-1.5 bg-white/70 backdrop-blur border border-violet-100 rounded-full text-sm text-slate-600 font-medium"
                >
                  {pill}
                </span>
              ))}
            </motion.div>
          </div>
        </section>

        {/* ── Features ── */}
        <section id="features" className="py-20 px-6 md:px-12 lg:px-24 relative overflow-hidden">
          <div className="absolute inset-0 opacity-5">
            <div className="absolute top-0 left-0 w-96 h-96 bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full blur-3xl" />
            <div className="absolute bottom-0 right-0 w-96 h-96 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full blur-3xl" />
          </div>

          <div className="max-w-7xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              className="text-center mb-12"
            >
              <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
                Everything you need to stay{" "}
                <span className="text-violet-600">productive</span>
              </h2>
              <p className="text-slate-600 max-w-2xl mx-auto">
                Four powerful tools, one place. Designed around how your brain actually works.
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 gap-8">
              {features.map((feature, i) => {
                const Icon = feature.icon;
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 50 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: feature.delay, duration: 0.6 }}
                    whileHover={{ y: -8, transition: { duration: 0.3 } }}
                  >
                    <Link to={feature.link} className="block group relative overflow-hidden">
                      <div className="relative rounded-2xl overflow-hidden shadow-lg transition-all duration-500 group-hover:shadow-2xl">
                        <div className="relative h-64 bg-slate-100">
                          <img
                            src={feature.image}
                            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                            alt={feature.title}
                            onError={(e) => {
                              // Fallback gradient if screenshot not yet added
                              e.target.style.display = "none";
                              e.target.parentNode.style.background = `linear-gradient(135deg, #8b5cf6, #6366f1)`;
                            }}
                          />
                          <div className={`absolute inset-0 bg-gradient-to-t ${feature.color} opacity-70`} />

                          {feature.badge && (
                            <div className="absolute top-4 right-4 bg-white/90 backdrop-blur rounded-full px-2 py-1 text-xs font-semibold text-violet-600 shadow-md">
                              {feature.badge}
                            </div>
                          )}

                          <motion.div
                            className="absolute bottom-4 left-4 bg-white/30 backdrop-blur rounded-xl p-3"
                            whileHover={{ scale: 1.1 }}
                            animate={{ scale: [1, 1.05, 1] }}
                            transition={{ duration: 2, repeat: Infinity }}
                          >
                            <Icon className="text-white w-6 h-6" />
                          </motion.div>

                          {/* Shimmer sweep */}
                          <motion.div
                            className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0"
                            animate={{ x: ["-100%", "200%"] }}
                            transition={{ duration: 1.5, repeat: Infinity, delay: 1 }}
                          />
                        </div>

                        <div className="p-6 bg-white/90 backdrop-blur-sm">
                          <h3 className="text-2xl font-semibold mb-2 group-hover:text-violet-600 transition-colors">
                            {feature.title}
                          </h3>
                          <p className="text-slate-600 mb-4">{feature.description}</p>
                          <motion.span
                            className="inline-flex items-center gap-1 text-violet-600 font-medium group-hover:gap-2 transition-all"
                            whileHover={{ x: 5 }}
                          >
                            Explore <ArrowRight size={18} />
                          </motion.span>
                        </div>
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Bottom CTA — honest version ── */}
        <section className="py-20 px-6 md:px-12 lg:px-24">
          <div className="max-w-5xl mx-auto">
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
              whileHover={{ scale: 1.02 }}
              className="relative bg-gradient-to-r from-violet-600 via-violet-700 to-indigo-700 text-white rounded-3xl p-16 text-center overflow-hidden"
            >
              {/* Animated background */}
              <motion.div
                className="absolute inset-0"
                animate={{
                  background: [
                    "radial-gradient(circle at 20% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)",
                    "radial-gradient(circle at 80% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)",
                    "radial-gradient(circle at 50% 50%, rgba(255,255,255,0.1) 0%, transparent 50%)",
                  ],
                }}
                transition={{ duration: 5, repeat: Infinity, repeatType: "reverse" }}
              />
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                className="absolute top-10 right-10 w-20 h-20 bg-white/10 rounded-full blur-xl"
              />
              <motion.div
                animate={{ rotate: -360 }}
                transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                className="absolute bottom-10 left-10 w-32 h-32 bg-white/10 rounded-full blur-xl"
              />

              <motion.div
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 3, repeat: Infinity }}
                className="text-5xl mb-6"
              >
                🧠
              </motion.div>

              <h2 className="text-4xl font-bold mb-4">
                Built during first year of college.
              </h2>
              <p className="text-violet-100 mb-2 text-lg">
                Tested by real students. Free to try — always.
              </p>
              <p className="text-violet-200 mb-8 text-sm">
                No fake stats. No inflated numbers. Just a tool that actually works.
              </p>

              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Link
                  to="/signup"
                  className="inline-flex items-center gap-2 bg-white text-violet-600 px-8 py-4 rounded-full font-semibold hover:shadow-xl transition-all"
                >
                  Start free  <ArrowRight size={20} />
                </Link>
              </motion.div>
            </motion.div>
          </div>
        </section>
      </BackgroundLayout>

      {/* ── Footer ── */}
      <motion.footer
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="py-12 bg-slate-50 border-t text-center relative overflow-hidden"
      >
        <motion.div
          className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-violet-500 to-transparent"
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 3, repeat: Infinity, repeatDelay: 2 }}
        />

        <div className="flex justify-center items-center gap-2 mb-3">
          <motion.div
            whileHover={{ rotate: 360 }}
            transition={{ duration: 0.5 }}
            className="w-8 h-8 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-lg text-white flex items-center justify-center font-bold text-sm"
          >
            Tv
          </motion.div>
          <span className="text-xl font-bold bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
            Timevora
          </span>
        </div>

        <p className="text-slate-400 text-sm mb-1">
          © 2026 Timevora. Built with{" "}
          <motion.span
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
            className="inline-block"
          >
            ❤️
          </motion.span>{" "}
          for productivity.
        </p>
        <p className="text-slate-400 text-xs">
          Free during beta
        </p>
      </motion.footer>
    </>
  );
};
