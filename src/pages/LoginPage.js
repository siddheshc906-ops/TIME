import { useState, useEffect } from "react";
import BackgroundLayout from "../components/BackgroundLayout";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

const BASE_URL = process.env.REACT_APP_BACKEND_URL;
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

export default function LoginPage() {
  const [email, setEmail]         = useState("");
  const [password, setPassword]   = useState("");
  const [error, setError]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [unverified, setUnverified] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) window.location.replace("/");
    // Show success if redirected from email verification link
    const params = new URLSearchParams(window.location.search);
    if (params.get("verified") === "1") {
      setTimeout(() => {
        alert("✅ Email verified! You can now log in.");
        window.history.replaceState({}, "", "/login");
      }, 300);
    }
    if (params.get("error") === "invalid_token") {
      setTimeout(() => {
        alert("This verification link has expired or already been used. Please sign up again or use Resend verification email.");
        window.history.replaceState({}, "", "/login");
      }, 300);
    }
  }, []);

  async function handleLogin() {
    if (!email || !password) { setError("Please enter email and password"); return; }
    setLoading(true); setError(""); setUnverified(false);
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
      } else if (res.status === 403) {
        setError("Please verify your email before logging in. Check your inbox.");
        setUnverified(true);
      } else {
        setError(data.detail || "Login failed");
      }
    } catch { setError("Server error. Try again."); }
    setLoading(false);
  }

  async function resendVerification() {
    if (!email) { setError("Enter your email above first"); return; }
    setLoading(true);
    try {
      const res  = await fetch(`${BASE_URL}/api/resend-verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      setError("");
      setUnverified(false);
      alert(data.message || "Verification email sent! Check your inbox.");
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

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BackgroundLayout>
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="backdrop-blur p-8 rounded-2xl w-full max-w-sm shadow-xl"
            style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}>

            <h2 className="text-2xl font-bold mb-1 text-center"
              style={{color:"var(--text-primary)"}}>Welcome back</h2>
            <p className="text-center text-sm mb-6"
              style={{color:"var(--text-secondary)"}}>Sign in to Timevora</p>

            <input
              className="p-3 w-full mb-3 rounded-xl"
              style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
            <input
              className="p-3 w-full mb-1 rounded-xl"
              style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />

            <div className="flex justify-end mb-4">
              <a
                href={`mailto:support@timevora.app?subject=Forgot Password&body=My email: ${email}`}
                className="text-xs text-violet-500 hover:underline"
              >
                Forgot password?
              </a>
            </div>

            {error && <p className="text-red-500 text-sm mb-2 text-center">{error}</p>}
            {unverified && (
              <button
                onClick={resendVerification}
                disabled={loading}
                className="text-violet-600 text-sm font-medium hover:underline w-full text-center mb-3 disabled:opacity-60"
              >
                {loading ? "Sending…" : "Resend verification email →"}
              </button>
            )}

            <button
              onClick={handleLogin}
              disabled={loading}
              className="text-white w-full py-3 rounded-xl transition disabled:opacity-60 font-medium"
              style={{background:"var(--accent)"}}
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
