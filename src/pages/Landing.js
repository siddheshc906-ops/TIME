import { Link } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { motion, useScroll, useTransform, useSpring, AnimatePresence } from "framer-motion";
import { 
  CheckSquare, Calendar, Clock, Brain, TrendingUp, ArrowRight, 
  Sparkles, Star, Zap, Target, Award, BarChart3, Users, 
  Rocket, ChevronRight, Play, Circle, 
  CheckCircle2, Moon, Sun, Cloud, Heart, Coffee, Gift,
  Layout, PieChart, Activity, Settings
} from "lucide-react";
import BackgroundLayout from "../components/BackgroundLayout";

export const Landing = () => {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);
  const [counters, setCounters] = useState({ satisfaction: 0, availability: 0 });
  const [isVisible, setIsVisible] = useState(false);
  const statsRef = useRef(null);
  
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 100, damping: 30 });

  // Parallax values
  const y1 = useTransform(scrollYProgress, [0, 1], [0, -200]);
  const y2 = useTransform(scrollYProgress, [0, 1], [0, 300]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0.3]);

  // Mouse move effect for hero
  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  // Intersection Observer for stats counter
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.5 }
    );
    
    if (statsRef.current) {
      observer.observe(statsRef.current);
    }
    
    return () => {
      if (statsRef.current) {
        observer.unobserve(statsRef.current);
      }
    };
  }, []);

  // Animate counters
  useEffect(() => {
    if (isVisible) {
      const duration = 2000;
      const interval = 20;
      const steps = duration / interval;
      let step = 0;
      
      const timer = setInterval(() => {
        step++;
        const progress = step / steps;
        setCounters({
          satisfaction: Math.min(Math.floor(95 * progress), 95),
          availability: Math.min(Math.floor(24 * progress), 24)
        });
        
        if (step >= steps) {
          clearInterval(timer);
        }
      }, interval);
      
      return () => clearInterval(timer);
    }
  }, [isVisible]);

  // Updated features - Time Blocks as main feature
  const features = [
    {
      icon: Layout,
      title: "Time Blocks",
      description: "Visual time-blocking for your day. Morning, afternoon, evening made simple and structured.",
      color: "from-indigo-500 to-blue-600",
      link: "/planner",
      image: "https://images.unsplash.com/photo-1758691736804-4e88c52ad58b?w=800&q=80",
      gradient: "from-indigo-500/20 to-blue-600/20",
      delay: 0,
      badge: "New",
    },
    {
      icon: Clock,
      title: "Deep Work",
      description: "Pomodoro timer with focus analytics. Stay in flow, track sessions, and boost concentration.",
      color: "from-purple-500 to-pink-600",
      link: "/focus",
      image: "https://images.unsplash.com/photo-1690106505816-6ba357b09c45?w=800&q=80",
      gradient: "from-purple-500/20 to-pink-600/20",
      delay: 0.1,
      badge: "Hot",
    },
    {
      icon: Brain,
      title: "AI Scheduler",
      description: "AI-powered schedule optimization. Get intelligent recommendations based on your habits and energy patterns.",
      color: "from-violet-600 to-indigo-700",
      link: "/ai-planner",
      image: "https://images.unsplash.com/photo-1760278041709-e54cb1dca123?w=800&q=80",
      gradient: "from-violet-600/20 to-indigo-700/20",
      delay: 0.2,
      badge: "AI Powered",
    },
    {
      icon: BarChart3,
      title: "Analytics Hub",
      description: "Deep insights into your productivity patterns. Track streaks, focus scores, and growth trends.",
      color: "from-emerald-500 to-teal-600",
      link: "/analytics",
      image: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&q=80",
      gradient: "from-emerald-500/20 to-teal-600/20",
      delay: 0.3,
      badge: "Insights",
    },
  ];

  // Floating particles for hero
  const particles = Array.from({ length: 20 }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 4 + 2,
    duration: Math.random() * 10 + 5,
    delay: Math.random() * 5,
  }));

  return (
    <>
      {/* Progress bar */}
      <motion.div
        className="fixed top-0 left-0 right-0 h-1 bg-gradient-to-r from-violet-500 to-indigo-500 z-50 origin-left"
        style={{ scaleX }}
      />

      <BackgroundLayout>
        {/* Hero Section */}
        <section className="relative pt-20 pb-32 px-6 md:px-12 lg:px-24 overflow-hidden">
          {/* Animated Gradient Background */}
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

          {/* Floating Particles */}
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
                animate={{
                  y: [0, -30, 0],
                  x: [0, 20, -20, 0],
                  opacity: [0, 0.5, 0],
                }}
                transition={{
                  duration: particle.duration,
                  repeat: Infinity,
                  delay: particle.delay,
                  ease: "easeInOut",
                }}
              />
            ))}
          </div>

          {/* Floating 3D Elements */}
          <motion.div
            className="absolute top-20 left-10 hidden lg:block"
            style={{ y: y1 }}
            animate={{ rotate: 360 }}
            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          >
            <div className="w-32 h-32 bg-gradient-to-r from-violet-500/20 to-purple-500/20 rounded-full blur-2xl" />
          </motion.div>
          
          <motion.div
            className="absolute bottom-20 right-10 hidden lg:block"
            style={{ y: y2 }}
            animate={{ rotate: -360 }}
            transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          >
            <div className="w-40 h-40 bg-gradient-to-r from-indigo-500/20 to-blue-500/20 rounded-full blur-2xl" />
          </motion.div>

          <div className="max-w-7xl mx-auto text-center relative z-10">
            {/* Animated Badge */}
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
                Your productivity companion
              </motion.div>
            </motion.div>

            {/* Main Title with Animation */}
            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="text-5xl md:text-7xl font-bold text-slate-900 mb-6 leading-tight"
            >
              Master Your Time,{" "}
              <motion.span
                className="text-violet-600 inline-block"
                animate={{
                  backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"],
                }}
                transition={{ duration: 5, repeat: Infinity }}
                style={{
                  background: "linear-gradient(135deg, #8b5cf6, #6366f1, #8b5cf6)",
                  backgroundSize: "200% auto",
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  color: "transparent",
                }}
              >
                Multiply Your Results
              </motion.span>
            </motion.h1>

            {/* Description */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="text-lg md:text-xl text-slate-700 mb-10 max-w-4xl mx-auto"
            >
              A beautifully designed productivity suite that helps you plan, focus, and achieve more.
            </motion.p>

            {/* Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.6 }}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Link
                  to="/planner"
                  className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-full font-semibold shadow-lg hover:shadow-xl transition-all"
                >
                  Get Started Free <ArrowRight size={20} />
                </Link>
              </motion.div>

              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Link
                  to="/ai-planner"
                  className="inline-flex items-center gap-2 px-8 py-4 bg-white/80 backdrop-blur border border-gray-200 rounded-full font-semibold hover:bg-white hover:shadow-lg transition-all"
                >
                  Analyze My Productivity <Brain size={20} />
                </Link>
              </motion.div>
            </motion.div>

            {/* Hint Link */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
            >
              <Link
                to="/planner"
                className="block mt-12 text-sm text-slate-700 hover:text-violet-600 transition-colors"
              >
                Start by organizing your day with Time Blocks →
              </Link>
            </motion.div>

            {/* Stats with Animation */}
            <motion.div
              ref={statsRef}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1, duration: 0.6 }}
              className="grid grid-cols-2 gap-10 mt-24 max-w-md mx-auto"
            >
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="relative"
              >
                <div className="text-4xl font-bold bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
                  {counters.satisfaction}%
                </div>
                <div className="text-sm text-slate-600 mt-1">Satisfaction Rate</div>
                <motion.div
                  className="absolute -top-2 -right-2"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                </motion.div>
              </motion.div>
              
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="relative"
              >
                <div className="text-4xl font-bold bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
                  {counters.availability}/7
                </div>
                <div className="text-sm text-slate-600 mt-1">Always Available</div>
                <motion.div
                  className="absolute -top-2 -right-2"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <Circle className="w-3 h-3 text-green-400 fill-green-400" />
                </motion.div>
              </motion.div>
            </motion.div>
          </div>
        </section>

        {/* Features Section - Now only 4 cards */}
        <section className="py-20 px-6 md:px-12 lg:px-24 relative overflow-hidden">
          {/* Background Pattern */}
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
                Everything You Need to Stay{" "}
                <span className="text-violet-600">Productive</span>
              </h2>
              <p className="text-slate-600 max-w-2xl mx-auto">
                Powerful tools designed to help you focus, organize, and achieve your goals.
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
                    <Link
                      to={feature.link}
                      className="block group relative overflow-hidden"
                    >
                      <div className="relative rounded-2xl overflow-hidden shadow-lg transition-all duration-500 group-hover:shadow-2xl">
                        <div className="relative h-64">
                          <motion.img
                            src={feature.image}
                            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                            alt=""
                          />
                          <div className={`absolute inset-0 bg-gradient-to-t ${feature.color} opacity-70`} />
                          
                          {/* Badge */}
                          {feature.badge && (
                            <div className="absolute top-4 right-4 bg-white/90 backdrop-blur rounded-full px-2 py-1 text-xs font-semibold text-violet-600 shadow-md">
                              {feature.badge}
                            </div>
                          )}
                          
                          {/* Icon with Pulse Effect */}
                          <motion.div
                            className="absolute bottom-4 left-4 bg-white/30 backdrop-blur rounded-xl p-3"
                            whileHover={{ scale: 1.1 }}
                            animate={{ scale: [1, 1.05, 1] }}
                            transition={{ duration: 2, repeat: Infinity }}
                          >
                            <Icon className="text-white w-6 h-6" />
                          </motion.div>
                          
                          {/* Glow Effect */}
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
                          <p className="text-slate-600 mb-4">
                            {feature.description}
                          </p>
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

        {/* Benefits Section */}
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
              {/* Animated Background */}
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
              >
                <TrendingUp size={48} className="mx-auto mb-6" />
              </motion.div>
              
              <h2 className="text-4xl font-bold mb-6">
                Boost Your Productivity by 3x
              </h2>
              <p className="text-violet-100 mb-8">
                Join thousands improving their workflow with Timevora.
              </p>
              
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Link
                  to="/planner"
                  className="inline-flex items-center gap-2 bg-white text-violet-600 px-8 py-4 rounded-full font-semibold hover:shadow-xl transition-all"
                >
                  Start Your Journey <ArrowRight size={20} />
                </Link>
              </motion.div>
            </motion.div>
          </div>
        </section>
      </BackgroundLayout>

      {/* Footer - Single footer only */}
      <motion.footer
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="py-12 bg-slate-50 border-t text-center relative overflow-hidden"
      >
        {/* Animated Border */}
        <motion.div
          className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-violet-500 to-transparent"
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 3, repeat: Infinity, repeatDelay: 2 }}
        />
        
        <div className="flex justify-center items-center gap-2 mb-4">
          <motion.div
            whileHover={{ rotate: 360 }}
            transition={{ duration: 0.5 }}
            className="w-8 h-8 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-lg text-white flex items-center justify-center font-bold"
          >
            Tv
          </motion.div>
          <span className="text-xl font-bold bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
            Timevora
          </span>
        </div>
        <p className="text-slate-500 text-sm">
          © 2026 Timevora. Built with <motion.span
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
            className="inline-block"
          >
            ❤️
          </motion.span> for productivity.
        </p>
      </motion.footer>
    </>
  );
};