const BASE_URL = process.env.REACT_APP_BACKEND_URL;

// ✅ Call this once in your App.js (top level) to capture Google OAuth token from URL
export function captureOAuthToken() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token") || params.get("access_token");

    if (token) {
        localStorage.setItem("token", token);
        // Clean the token out of the URL so it doesn't linger
        const cleanUrl = window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);
        console.log("OAuth token captured and saved.");
    }
}

export function getToken() {
    return localStorage.getItem("token");
}

export async function login(email, password) {
    try {
        const res = await fetch(`${BASE_URL}/api/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();
        console.log("Login response:", res.status, data);

        if (res.ok && data.access_token) {
            localStorage.setItem("token", data.access_token);
        }

        return data;
    } catch (error) {
        console.error("Login error:", error);
        throw error;
    }
}

export function logout() {
    localStorage.removeItem("token");
}