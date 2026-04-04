export default function BackgroundLayout({ children }) {
  return (
    <div className="relative min-h-screen overflow-hidden">

      {/* Background video (CONTENT ONLY) */}
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
      <div className="absolute inset-0 bg-white/20 backdrop-blur-[2px]"></div>


      {/* Page content */}
      <div className="relative z-10">
        {children}
      </div>

    </div>
  );
}
