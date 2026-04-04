import { useState } from "react";
import BackgroundLayout from "../components/BackgroundLayout";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

const BASE_URL = process.env.REACT_APP_BACKEND_URL;
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

// ─── Tab options ──────────────────────────────────────────────────────────────
const TAB_EMAIL = "email";
const TAB_PHONE = "phone";

export default function SignupPage() {
  const [tab, setTab]           = useState(TAB_EMAIL);

  // Email/password state — all original state preserved
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg]           = useState("");
  const [loading, setLoading]   = useState(false);
  const [success, setSuccess]   = useState(false);

  // Phone OTP state
  const [phone, setPhone]       = useState("");
  const [otp, setOtp]           = useState("");
  const [otpSent, setOtpSent]   = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);

  // ── Email/password signup — original logic unchanged ──────────────────────
  async function signup() {
    if (!email || !password) {
      setMsg("Please enter email and password");
      return;
    }
    setLoading(true);
    setSuccess(false);
    setMsg("");
    try {
      const res  = await fetch(`${BASE_URL}/api/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      console.log("Signup response:", res.status, data);
      if (res.ok) {
        setSuccess(true);
        setMsg(data.message || "Signup successful! Please check your email to verify your account.");
      } else {
        setMsg(data.detail || "Signup failed");
      }
    } catch (err) {
      console.error("Signup error:", err);
      setMsg("Server error. Try again.");
    }
    setLoading(false);
  }

  // ── Google signup (same endpoint as login — backend handles both) ──────────
  async function handleGoogleSuccess(credentialResponse) {
    setLoading(true);
    setMsg("");
    setSuccess(false);
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
        setMsg(data.detail || "Google signup failed");
      }
    } catch {
      setMsg("Server error. Try again.");
    }
    setLoading(false);
  }

  // ── Phone OTP — send ───────────────────────────────────────────────────────
  async function handleSendOtp() {
    if (!phone || phone.length < 10) {
      setMsg("Enter a valid 10-digit phone number");
      return;
    }
    setOtpLoading(true);
    setMsg("");
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
        setMsg(data.detail || "Failed to send OTP");
      }
    } catch {
      setMsg("Server error. Try again.");
    }
    setOtpLoading(false);
  }

  // ── Phone OTP — verify & register ─────────────────────────────────────────
  async function handleVerifyOtp() {
    if (!otp || otp.length !== 6) {
      setMsg("Enter the 6-digit OTP");
      return;
    }
    setLoading(true);
    setMsg("");
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
        setMsg(data.detail || "Invalid OTP");
      }
    } catch {
      setMsg("Server error. Try again.");
    }
    setLoading(false);
  }

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BackgroundLayout>
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="bg-white/80 backdrop-blur p-8 rounded-2xl w-full max-w-sm shadow-xl border">
            <h2 className="text-2xl font-bold mb-4 text-center">Create Account</h2>

            {/* ── Tab switcher ── */}
            <div className="flex rounded-xl overflow-hidden border mb-5">
              {[TAB_EMAIL, TAB_PHONE].map((t) => (
                <button
                  key={t}
                  onClick={() => { setTab(t); setMsg(""); setSuccess(false); setOtpSent(false); }}
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

                <button
                  onClick={signup}
                  disabled={loading}
                  className="bg-violet-600 text-white w-full py-3 rounded-xl hover:bg-violet-700 transition disabled:opacity-60"
                >
                  Create Account
                </button>

                {/* Original loader/tick animation — preserved */}
                <div className="h-8 mt-3 flex justify-center items-center">
                  {loading && <DotLoader />}
                  {success && <CheckMark />}
                </div>

                {msg && (
                  <p className={`mt-1 text-center text-sm ${success ? "text-green-600" : "text-red-500"}`}>
                    {msg}
                  </p>
                )}

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
                    onError={() => setMsg("Google signup failed")}
                    shape="rectangular"
                    width="100%"
                    text="signup_with"
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
                      {loading ? "Verifying…" : "Verify & Create Account"}
                    </button>
                    <button
                      onClick={() => { setOtpSent(false); setOtp(""); }}
                      className="text-violet-500 text-sm w-full mt-2 hover:underline"
                    >
                      Resend OTP
                    </button>
                  </>
                )}

                {msg && (
                  <p className={`mt-3 text-center text-sm ${success ? "text-green-600" : "text-red-500"}`}>
                    {msg}
                  </p>
                )}
              </>
            )}

            {/* Link to login — original preserved */}
            <p className="text-center mt-5 text-sm text-gray-600">
              Already have an account?{" "}
              <a href="/login" className="text-violet-600 hover:underline">Log in</a>
            </p>
          </div>
        </div>
      </BackgroundLayout>
    </GoogleOAuthProvider>
  );
}

/* ---------- Animations — original preserved exactly ---------- */
function DotLoader() {
  return (
    <div className="flex gap-1">
      <span className="w-2 h-2 bg-violet-600 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
      <span className="w-2 h-2 bg-violet-600 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
      <span className="w-2 h-2 bg-violet-600 rounded-full animate-bounce"></span>
    </div>
  );
}

function CheckMark() {
  return (
    <svg
      className="w-6 h-6 text-green-500 animate-check"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}