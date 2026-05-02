import { useState, useEffect } from "react";
import BackgroundLayout from "../components/BackgroundLayout";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

const BASE_URL = process.env.REACT_APP_BACKEND_URL;
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

const TAB_EMAIL = "email";
const TAB_PHONE = "phone";

export default function LoginPage() {
  const [tab, setTab]               = useState(TAB_EMAIL);
  const [email, setEmail]           = useState("");
  const [password, setPassword]     = useState("");
  const [phone, setPhone]           = useState("");
  const [otp, setOtp]               = useState("");
  const [otpSent, setOtpSent]       = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [error, setError]           = useState("");
  const [loading, setLoading]       = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) window.location.replace("/");
  }, []);

  async function handleLogin() {
    if (!email || !password) { setError("Please enter email and password"); return; }
    setLoading(true); setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem("token", data.access_token);
        window.location.replace("/");
      } else {
        setError(data.detail || "Login failed");
      }
    } catch { setError("Server error. Try again."); }
    setLoading(false);
  }

  async function handleGoogleSuccess(credentialResponse) {
    setLoading(true); setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: credentialResponse.credential }),
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem("token", data.access_token);
        window.location.replace("/");
      } else { setError(data.detail || "Google login failed"); }
    } catch { setError("Server error. Try again."); }
    setLoading(false);
  }

  async function handleSendOtp() {
    if (!phone || phone.length < 10) { setError("Enter a valid phone number"); return; }
    setOtpLoading(true); setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/otp/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      const data = await res.json();
      if (res.ok) { setOtpSent(true); }
      else { setError(data.detail || "Failed to send OTP"); }
    } catch { setError("Server error. Try again."); }
    setOtpLoading(false);
  }

  async function handleVerifyOtp() {
    if (!otp || otp.length !== 6) { setError("Enter the 6-digit OTP"); return; }
    setLoading(true); setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/otp/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, otp }),
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem("token", data.access_token);
        window.location.replace("/");
      } else { setError(data.detail || "Invalid OTP"); }
    } catch { setError("Server error. Try again."); }
    setLoading(false);
  }

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BackgroundLayout>
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="backdrop-blur p-8 rounded-2xl w-full max-w-sm shadow-xl" style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}>

            <h2 className="text-2xl font-bold mb-1 text-center" style={{color:"var(--text-primary)"}}>Welcome back</h2>
            <p className="text-center text-sm mb-5" style={{color:"var(--text-secondary)"}}>Sign in to Timevora</p>

            {/* Tab switcher */}
            <div className="flex rounded-xl overflow-hidden border mb-5">
              {[TAB_EMAIL, TAB_PHONE].map((t) => (
                <button
                  key={t}
                  onClick={() => { setTab(t); setError(""); setOtpSent(false); }}
                  className="flex-1 py-2 text-sm font-medium transition"
                  style={
                    tab === t
                      ? { background: "var(--accent)", color: "#fff" }
                      : { background: "var(--input-bg)", color: "var(--text-secondary)" }
                  }
                >
                  {t === TAB_EMAIL ? "Email" : "Phone OTP"}
                </button>
              ))}
            </div>

            {/* Email tab */}
            {tab === TAB_EMAIL && (
              <>
                <input
                  className="p-3 w-full mb-3 rounded-xl" style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                />
                <input
                  className="p-3 w-full mb-1 rounded-xl" style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                />

                {/* Forgot password */}
                <div className="flex justify-end mb-3">
                  <a
                    href={`mailto:support@timevora.app?subject=Forgot Password&body=My email: ${email}`}
                    className="text-xs text-violet-500 hover:underline"
                  >
                    Forgot password?
                  </a>
                </div>

                {error && <p className="text-red-500 text-sm mb-3 text-center">{error}</p>}

                <button
                  onClick={handleLogin}
                  disabled={loading}
                  className="text-white w-full py-3 rounded-xl transition disabled:opacity-60 font-medium" style={{background:"var(--accent)"}}
                >
                  {loading ? "Logging in…" : "Login"}
                </button>

                <div className="flex items-center my-4 gap-2">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-gray-400 text-xs">or</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>

                <div className="flex justify-center">
                  <GoogleLogin
                    onSuccess={handleGoogleSuccess}
                    onError={() => setError("Google login failed")}
                    shape="rectangular"
                    width="100%"
                    text="signin_with"
                  />
                </div>
              </>
            )}

            {/* Phone OTP tab */}
            {tab === TAB_PHONE && (
              <>
                <input
                  className="p-3 w-full mb-3 rounded-xl" style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                  placeholder="Phone number (e.g. 9876543210)"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                  maxLength={10}
                />

                {!otpSent ? (
                  <button
                    onClick={handleSendOtp}
                    disabled={otpLoading}
                    className="text-white w-full py-3 rounded-xl transition disabled:opacity-60" style={{background:"var(--accent)"}}
                  >
                    {otpLoading ? "Sending…" : "Send OTP"}
                  </button>
                ) : (
                  <>
                    <p className="text-green-600 text-sm mb-3 text-center">OTP sent to +91 {phone}</p>
                    <input
                      className="p-3 w-full mb-3 rounded-xl tracking-widest text-center text-lg" style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                      placeholder="Enter 6-digit OTP"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                      maxLength={6}
                    />
                    <button
                      onClick={handleVerifyOtp}
                      disabled={loading}
                      className="text-white w-full py-3 rounded-xl transition disabled:opacity-60" style={{background:"var(--accent)"}}
                    >
                      {loading ? "Verifying…" : "Verify & Login"}
                    </button>
                    <button
                      onClick={() => { setOtpSent(false); setOtp(""); }}
                      className="text-violet-500 text-sm w-full mt-2 hover:underline"
                    >
                      Resend OTP
                    </button>
                  </>
                )}

                {error && <p className="text-red-500 text-sm mt-3 text-center">{error}</p>}
              </>
            )}

            <p className="text-center mt-5 text-sm" style={{color:"var(--text-secondary)"}}>
              Don't have an account?{" "}
              <a href="/signup" className="text-violet-600 hover:underline font-medium">Sign up free</a>
            </p>
          </div>
        </div>
      </BackgroundLayout>
    </GoogleOAuthProvider>
  );
}
