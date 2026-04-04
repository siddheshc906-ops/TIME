import { useState, useEffect } from "react";
import BackgroundLayout from "../components/BackgroundLayout";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

const BASE_URL = process.env.REACT_APP_BACKEND_URL;
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

// ─── Tab options ──────────────────────────────────────────────────────────────
const TAB_EMAIL = "email";
const TAB_PHONE = "phone";

export default function LoginPage() {
  const [tab, setTab]           = useState(TAB_EMAIL);

  // Email/password state
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");

  // Phone OTP state
  const [phone, setPhone]       = useState("");
  const [otp, setOtp]           = useState("");
  const [otpSent, setOtpSent]   = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);

  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      window.location.replace("/");
    }
  }, []);

  // ── Email/password login ───────────────────────────────────────────────────
  async function handleLogin() {
    if (!email || !password) {
      setError("Please enter email and password");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem("token", data.access_token);
        window.location.replace("/");
      } else {
        setError(data.detail || "Login failed");
      }
    } catch {
      setError("Server error. Try again.");
    }
    setLoading(false);
  }

  // ── Google login ───────────────────────────────────────────────────────────
  async function handleGoogleSuccess(credentialResponse) {
    setLoading(true);
    setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: credentialResponse.credential })
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem("token", data.access_token);
        window.location.replace("/");
      } else {
        setError(data.detail || "Google login failed");
      }
    } catch {
      setError("Server error. Try again.");
    }
    setLoading(false);
  }

  // ── Phone OTP — send ───────────────────────────────────────────────────────
  async function handleSendOtp() {
    if (!phone || phone.length < 10) {
      setError("Enter a valid phone number");
      return;
    }
    setOtpLoading(true);
    setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/otp/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone })
      });
      const data = await res.json();
      if (res.ok) {
        setOtpSent(true);
      } else {
        setError(data.detail || "Failed to send OTP");
      }
    } catch {
      setError("Server error. Try again.");
    }
    setOtpLoading(false);
  }

  // ── Phone OTP — verify ─────────────────────────────────────────────────────
  async function handleVerifyOtp() {
    if (!otp || otp.length !== 6) {
      setError("Enter the 6-digit OTP");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res  = await fetch(`${BASE_URL}/api/otp/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, otp })
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem("token", data.access_token);
        window.location.replace("/");
      } else {
        setError(data.detail || "Invalid OTP");
      }
    } catch {
      setError("Server error. Try again.");
    }
    setLoading(false);
  }

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BackgroundLayout>
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="bg-white/80 backdrop-blur p-8 rounded-2xl w-full max-w-sm shadow-xl border">
            <h2 className="text-2xl font-bold mb-4 text-center">Welcome Back</h2>

            {/* ── Tab switcher ── */}
            <div className="flex rounded-xl overflow-hidden border mb-5">
              {[TAB_EMAIL, TAB_PHONE].map((t) => (
                <button
                  key={t}
                  onClick={() => { setTab(t); setError(""); setOtpSent(false); }}
                  className={`flex-1 py-2 text-sm font-medium transition ${
                    tab === t
                      ? "bg-violet-600 text-white"
                      : "bg-white text-gray-500 hover:bg-violet-50"
                  }`}
                >
                  {t === TAB_EMAIL ? "Email" : "Phone OTP"}
                </button>
              ))}
            </div>

            {/* ── Email tab ── */}
            {tab === TAB_EMAIL && (
              <>
                <input
                  className="border p-3 w-full mb-3 rounded-xl bg-white/70"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <input
                  className="border p-3 w-full mb-3 rounded-xl bg-white/70"
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />

                {error && <p className="text-red-500 text-sm mb-3 text-center">{error}</p>}

                <button
                  onClick={handleLogin}
                  disabled={loading}
                  className="bg-violet-600 text-white w-full py-3 rounded-xl hover:bg-violet-700 transition disabled:opacity-60"
                >
                  {loading ? "Logging in…" : "Login"}
                </button>

                {/* Divider */}
                <div className="flex items-center my-4 gap-2">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-gray-400 text-xs">or</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>

                {/* Google */}
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

            {/* ── Phone OTP tab ── */}
            {tab === TAB_PHONE && (
              <>
                <input
                  className="border p-3 w-full mb-3 rounded-xl bg-white/70"
                  placeholder="Phone number (e.g. 9876543210)"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                  maxLength={10}
                />

                {!otpSent ? (
                  <button
                    onClick={handleSendOtp}
                    disabled={otpLoading}
                    className="bg-violet-600 text-white w-full py-3 rounded-xl hover:bg-violet-700 transition disabled:opacity-60"
                  >
                    {otpLoading ? "Sending…" : "Send OTP"}
                  </button>
                ) : (
                  <>
                    <p className="text-green-600 text-sm mb-3 text-center">
                      OTP sent to +91 {phone}
                    </p>
                    <input
                      className="border p-3 w-full mb-3 rounded-xl bg-white/70 tracking-widest text-center text-lg"
                      placeholder="Enter 6-digit OTP"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                      maxLength={6}
                    />
                    <button
                      onClick={handleVerifyOtp}
                      disabled={loading}
                      className="bg-violet-600 text-white w-full py-3 rounded-xl hover:bg-violet-700 transition disabled:opacity-60"
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

            {/* Link to signup */}
            <p className="text-center mt-5 text-sm text-gray-600">
              Don't have an account?{" "}
              <a href="/signup" className="text-violet-600 hover:underline">Sign up</a>
            </p>
          </div>
        </div>
      </BackgroundLayout>
    </GoogleOAuthProvider>
  );
}