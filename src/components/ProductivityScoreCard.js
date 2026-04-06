import { useEffect, useState } from "react";
import { CircularProgressbar, buildStyles } from "react-circular-progressbar";
import "react-circular-progressbar/dist/styles.css";

const BASE_URL = process.env.REACT_APP_BACKEND_URL || process.env.REACT_APP_API_URL || "http://localhost:8000";

export default function ProductivityScoreCard() {
  const [scoreData, setScoreData] = useState(null);

  useEffect(() => {
    const fetchScore = async () => {
      const res = await fetch(`${BASE_URL}/api/productivity-score`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
      });

      const data = await res.json();
      setScoreData(data);
    };

    fetchScore();
  }, []);

  if (!scoreData) return null;

  return (
    <div className="bg-white/90 rounded-2xl p-8 border shadow-md text-center">
      <h2 className="text-2xl font-bold mb-6">
        Today's Productivity Score
      </h2>

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
          <span className="font-semibold">
            {scoreData.focus_hours} hrs
          </span>
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
