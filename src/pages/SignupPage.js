import { useState } from "react";
import BackgroundLayout from "../components/BackgroundLayout";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

const BASE_URL = process.env.REACT_APP_BACKEND_URL;
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

export default function SignupPage() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg]           = useState("");
  const [loading, setLoading]   = useState(false);
  const [success, setSuccess]   = useState(false);

  async function signup() {
    if (!email || !password) { setMsg("Please enter email and password"); return; }
    setLoading(true); setSuccess(false); setMsg("");
    try {
      const res  = await fetch(`${BASE_URL}/api/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok) {
        setSuccess(true);
      } else {
        setMsg(data.detail || "Signup failed");
      }
    } catch {
      setMsg("Server error. Try again.");
    }
    setLoading(false);
  }

  async function resendVerification() {
    setLoading(true);
    try {
      const res  = await fetch(`${BASE_URL}/api/resend-verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      setMsg(data.message || "Verification email sent!");
    } catch {
      setMsg("Server error. Try again.");
    }
    setLoading(false);
  }

  async function handleGoogleSuccess(credentialResponse) {
    setLoading(true); setMsg("");
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

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <BackgroundLayout>
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="backdrop-blur p-8 rounded-2xl w-full max-w-sm shadow-xl"
            style={{background:"var(--card-bg)",border:"1px solid var(--card-border)"}}>

            <h2 className="text-2xl font-bold mb-6 text-center"
              style={{color:"var(--text-primary)"}}>Create Account</h2>

            {success ? (
              <div className="text-center py-4">
                <div className="text-5xl mb-4">📬</div>
                <h3 className="font-bold text-lg mb-2" style={{color:"var(--text-primary)"}}>
                  Check your inbox!
                </h3>
                <p className="text-sm mb-4" style={{color:"var(--text-secondary)"}}>
                  We sent a verification link to <strong>{email}</strong>.
                  Click it to activate your account.
                </p>
                <p className="text-xs mb-3" style={{color:"var(--text-secondary)"}}>
                  Didn't get it? Check spam or
                </p>
                <button
                  onClick={resendVerification}
                  disabled={loading}
                  className="text-violet-600 text-sm font-medium hover:underline disabled:opacity-60"
                >
                  {loading ? "Sending…" : "Resend verification email"}
                </button>
                {msg && <p className="mt-3 text-sm text-green-600">{msg}</p>}
              </div>
            ) : (
              <>
                <input
                  className="p-3 w-full mb-3 rounded-xl"
                  style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && signup()}
                />
                <input
                  className="p-3 w-full mb-3 rounded-xl"
                  style={{background:"var(--input-bg)",border:"1px solid var(--input-border)",color:"var(--text-primary)"}}
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && signup()}
                />
                <button
                  onClick={signup}
                  disabled={loading}
                  className="text-white w-full py-3 rounded-xl transition disabled:opacity-60 font-medium"
                  style={{background:"var(--accent)"}}
                >
                  {loading ? "Creating account…" : "Create Account"}
                </button>
                <div className="h-6 mt-2 flex justify-center items-center">
                  {loading && <DotLoader />}
                </div>
                {msg && <p className="mt-1 text-center text-sm text-red-500">{msg}</p>}

                <div className="flex items-center my-4 gap-2">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-gray-400 text-xs">or</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>
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

            <p className="text-center mt-5 text-sm" style={{color:"var(--text-secondary)"}}>
              Already have an account?{" "}
              <a href="/login" className="text-violet-600 hover:underline font-medium">Log in</a>
            </p>
          </div>
        </div>
      </BackgroundLayout>
    </GoogleOAuthProvider>
  );
}

function DotLoader() {
  return (
    <div className="flex gap-1">
      <span className="w-2 h-2 bg-violet-600 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
      <span className="w-2 h-2 bg-violet-600 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
      <span className="w-2 h-2 bg-violet-600 rounded-full animate-bounce"></span>
    </div>
  );
}
