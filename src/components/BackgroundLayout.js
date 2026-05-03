// src/components/BackgroundLayout.js
import { useEffect, useRef } from "react";
import { useMode } from "../context/ModeContext";

// ─────────────────────────────────────────────
// Particle canvas — renders only for non-student modes
// The student mode relies on the video bg + gradient fallback.
// ─────────────────────────────────────────────
function ParticleCanvas({ color, style }) {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    let w = (canvas.width  = canvas.offsetWidth);
    let h = (canvas.height = canvas.offsetHeight);

    // Particle configs per style
    const configs = {
      matrix: { count: 60, shape: "char",  speed: 0.8, size: 13, opacity: 0.55 },
      stars:  { count: 120, shape: "star",  speed: 0.15, size: 1.5, opacity: 0.7 },
      sparks: { count: 55,  shape: "spark", speed: 0.6, size: 2.5, opacity: 0.6 },
      dots:   { count: 80,  shape: "dot",   speed: 0.3, size: 2,   opacity: 0.4 },
    };

    const cfg = configs[style] || configs.dots;
    const chars = "01アイウエオ</>{}[];";

    const particles = Array.from({ length: cfg.count }, (_, i) => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vy: cfg.speed * (0.5 + Math.random() * 0.8) * (style === "matrix" ? 1 : (Math.random() > 0.5 ? 1 : -1)),
      vx: style === "sparks" ? (Math.random() - 0.5) * 0.6 : 0,
      size: cfg.size * (0.6 + Math.random() * 0.8),
      opacity: cfg.opacity * (0.5 + Math.random() * 0.5),
      char: chars[Math.floor(Math.random() * chars.length)],
      twinkle: Math.random() * Math.PI * 2,
      twinkleSpeed: 0.02 + Math.random() * 0.03,
    }));

    function draw() {
      ctx.clearRect(0, 0, w, h);

      particles.forEach((p) => {
        // Movement
        p.y += p.vy;
        p.x += p.vx;
        if (p.y > h + 20) p.y = -20;
        if (p.y < -20)    p.y = h + 20;
        if (p.x > w + 20) p.x = -20;
        if (p.x < -20)    p.x = w + 20;
        p.twinkle += p.twinkleSpeed;

        const alpha = style === "stars"
          ? p.opacity * (0.5 + 0.5 * Math.sin(p.twinkle))
          : p.opacity;

        ctx.globalAlpha = alpha;

        if (style === "matrix") {
          ctx.fillStyle = color;
          ctx.font = `${p.size}px 'Fira Code', monospace`;
          ctx.fillText(p.char, p.x, p.y);
          if (Math.random() < 0.005) p.char = chars[Math.floor(Math.random() * chars.length)];
        } else if (style === "stars") {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size * (0.5 + 0.5 * Math.sin(p.twinkle * 0.5)), 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          // Glow
          ctx.shadowBlur = 6;
          ctx.shadowColor = color;
          ctx.fill();
          ctx.shadowBlur = 0;
        } else if (style === "sparks") {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.shadowBlur = 8;
          ctx.shadowColor = color;
          ctx.fill();
          ctx.shadowBlur = 0;
        } else {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        }

        ctx.globalAlpha = 1;
      });

      animRef.current = requestAnimationFrame(draw);
    }

    draw();

    const onResize = () => {
      w = canvas.width  = canvas.offsetWidth;
      h = canvas.height = canvas.offsetHeight;
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", onResize);
    };
  }, [color, style]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ opacity: 0.45 }}
    />
  );
}

// ─────────────────────────────────────────────
// Particle style per mode
// ─────────────────────────────────────────────
const PARTICLE_STYLES = {
  student:    null,        // no canvas — video bg only
  developer:  "matrix",
  founder:    "dots",
  nightOwl:   "stars",
  focusBeast: "sparks",
};

// ─────────────────────────────────────────────
// BackgroundLayout
// ─────────────────────────────────────────────
export default function BackgroundLayout({ children }) {
  const { mode, themes } = useMode();
  const theme = themes[mode];
  const particleStyle = PARTICLE_STYLES[mode];

  return (
    <div
      className="relative min-h-screen overflow-x-hidden"
      style={{
        background: "var(--bg-gradient)",
        transition: "background 300ms ease",
      }}
    >
      {/* Video — always present, sits under overlay.
          Only visible/useful in student mode (gradient covers other modes).
          DO NOT remove or alter video or its sounds. */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover"
        style={{
          // Hide video in dark modes so the solid gradient bg shows cleanly
          opacity: mode === "student" ? 1 : 0,
          transition: "opacity 300ms ease",
        }}
      >
        <source src="/bg.mp4" type="video/mp4" />
      </video>

      {/* Overlay — tint + blur, intensity varies per mode */}
      <div
        className="absolute inset-0"
        style={{
          background: "var(--overlay-bg)",
          backdropFilter: `blur(var(--overlay-blur))`,
          transition: "background 300ms ease",
        }}
      />

      {/* Mode-specific particle canvas */}
      {particleStyle && (
        <ParticleCanvas
          key={mode}               /* remount when mode changes */
          color={theme.vars["--particle-color"]}
          style={particleStyle}
        />
      )}

      {/* Page content — fades in on mode change via key trick in App.js */}
      <div
        className="relative z-10"
        style={{ fontFamily: "var(--font-body)", transition: "font-family 300ms ease" }}
      >
        {children}
      </div>
    </div>
  );
}
