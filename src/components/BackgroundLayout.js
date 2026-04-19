export default function BackgroundLayout({ children }) {
  return (
    <div
      className="relative min-h-screen overflow-hidden"
      style={{
        background: "linear-gradient(135deg, #f5d0fe 0%, #e9d5ff 40%, #c7d2fe 100%)",
      }}
    >
      {/* Background video — gradient above is the fallback if video is slow/fails */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover"
      >
        <source src="/bg.mp4" type="video/mp4" />
      </video>

      {/* Calm overlay */}
      <div className="absolute inset-0 bg-white/20 backdrop-blur-[2px]" />

      {/* Page content */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}
