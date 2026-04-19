import { useEffect, useState } from "react";
import { CircularProgressbar, buildStyles } from "react-circular-progressbar";
import "react-circular-progressbar/dist/styles.css";
import { AlertCircle, RefreshCw } from "lucide-react";

const BASE_URL = process.env.REACT_APP_BACKEND_URL || process.env.REACT_APP_API_URL || "http://localhost:8000";

export default function ProductivityScoreCard() {
  const [scoreData, setScoreData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchScore = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BASE_URL}/api/productivity-score`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
      });

      if (!res.ok) throw new Error(`Server responded with ${res.status}`);

      const data = await res.json();
      setScoreData(data);
    } catch (err) {
      setError("Could not load your score right now.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScore();
  }, []);

  // Loading state
  if (loading) {
    return (
      <div className="bg-white/90 rounded-2xl p-8 border shadow-md text-center animate-pulse">
        <div className="h-6 bg-slate-200 rounded w-2/3 mx-auto mb-6" />
        <div className="w-48 h-48 bg-slate-200 rounded-full mx-auto mb-6" />
        <div className="h-4 bg-slate-200 rounded w-1/2 mx-auto mb-3" />
        <div className="h-4 bg-slate-200 rounded w-1/3 mx-auto" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-white/90 rounded-2xl p-8 border shadow-md text-center">
        <AlertCircle className="mx-auto mb-3 text-slate-400" size={40} />
        <p className="text-slate-500 text-sm mb-4">{error}</p>
        <button
          onClick={fetchScore}
          className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-xl text-sm font-medium hover:bg-violet-700 transition"
        >
          <RefreshCw size={14} />
          Try again
        </button>
      </div>
    );
  }

  // No data yet
  if (!scoreData) return null;

  return (
    <div className="bg-white/90 rounded-2xl p-8 border shadow-md text-center">
      <h2 className="text-2xl font-bold mb-6">Today's Productivity Score</h2>

      <div className="w-48 mx-auto mb-6">
        <CircularProgressbar
          value={scoreData.score}
          text={`${scoreData.score}`}
          styles={buildStyles({
            pathColor: "#7c3aed",
            textColor: "#7c3aed",
            trailColor: "#e5e7eb",
            textSize: "22px",
          })}
        />
      </div>

      <div className="space-y-2 text-gray-700">
        <p>
          Focus Hours:{" "}
          <span className="font-semibold">{scoreData.focus_hours} hrs</span>
        </p>
        <p>
          Tasks Completed:{" "}
          <span className="font-semibold">
            {Math.round(scoreData.completion_rate * 100)}%
          </span>
        </p>
      </div>
    </div>
  );
}
