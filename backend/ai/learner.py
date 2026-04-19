# backend/ai/learner.py
# ── CHANGE: Model save/load/check now uses MongoDB instead of disk .pkl files
# ── This fixes the Vercel serverless issue where disk files are wiped on redeploy
# ── Everything else is identical to the original

import numpy as np
import base64
import pickle
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging
import os

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Minimum samples raised from 10 → 30 for meaningful predictions
MIN_TRAINING_SAMPLES = 30


class AdaptiveLearner:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        self.model = None
        self.scaler = None
        # No more disk paths — models stored in MongoDB collection: user_models

    # ══════════════════════════════════════════════════════════════════════════
    # MONGODB SAVE / LOAD — replaces joblib disk storage
    # ══════════════════════════════════════════════════════════════════════════

    async def _save_model_to_db(self, metadata: Dict) -> bool:
        """Serialize model + scaler to base64 and save in MongoDB"""
        try:
            model_bytes  = base64.b64encode(pickle.dumps(self.model)).decode("utf-8")
            scaler_bytes = base64.b64encode(pickle.dumps(self.scaler)).decode("utf-8")

            await self.db.user_models.update_one(
                {"user_id": self.user_id},
                {"$set": {
                    "user_id":    self.user_id,
                    "model":      model_bytes,
                    "scaler":     scaler_bytes,
                    "metadata":   metadata,
                    "updated_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            logger.info(f"✅ Model saved to MongoDB for user {self.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save model to MongoDB: {e}", exc_info=True)
            return False

    async def _load_model_from_db(self) -> bool:
        """Load model + scaler from MongoDB"""
        try:
            doc = await self.db.user_models.find_one({"user_id": self.user_id})
            if not doc:
                return False
            self.model  = pickle.loads(base64.b64decode(doc["model"]))
            self.scaler = pickle.loads(base64.b64decode(doc["scaler"]))
            logger.info(f"✅ Model loaded from MongoDB for user {self.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model from MongoDB: {e}", exc_info=True)
            return False

    async def _get_model_metadata(self) -> Optional[Dict]:
        """Get model metadata from MongoDB"""
        try:
            doc = await self.db.user_models.find_one(
                {"user_id": self.user_id},
                {"metadata": 1, "updated_at": 1}
            )
            if doc:
                return doc.get("metadata")
        except Exception as e:
            logger.warning(f"Could not load model metadata: {e}")
        return None

    async def is_model_trained(self) -> bool:
        """Check if a trained model exists for this user in MongoDB"""
        doc = await self.db.user_models.find_one(
            {"user_id": self.user_id},
            {"_id": 1}
        )
        return doc is not None

    async def get_model_age_hours(self) -> Optional[float]:
        """How many hours since the model was last trained"""
        try:
            doc = await self.db.user_models.find_one(
                {"user_id": self.user_id},
                {"updated_at": 1}
            )
            if doc and doc.get("updated_at"):
                updated_at = doc["updated_at"]
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - updated_at
                return round(age.total_seconds() / 3600, 1)
        except Exception as e:
            logger.warning(f"Could not get model age: {e}")
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # TRAINING — Priority 2: Enhanced with category features + metadata
    # ══════════════════════════════════════════════════════════════════════════

    async def train_model(self, history: Optional[List[Dict]] = None) -> Any:
        """
        Train ML model on user's task history.
        Accepts optional pre-fetched history (used by background retrain in core.py).
        Returns True/dict on success, False on failure.
        """
        try:
            if history is None:
                history = await self._get_training_data()

            # Raised from 10 → 30 for meaningful predictions
            if len(history) < MIN_TRAINING_SAMPLES:
                logger.info(
                    f"Not enough data for user {self.user_id} "
                    f"({len(history)} records, need {MIN_TRAINING_SAMPLES})"
                )
                return False

            X, y = await self._prepare_features(history)

            if len(X) == 0:
                logger.warning(f"No valid features extracted for user {self.user_id}")
                return False

            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                min_samples_split=3,
                min_samples_leaf=2,
            )

            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)

            predictions = self.model.predict(X_scaled)
            mae = float(np.mean(np.abs(predictions - y)))
            mean_y = float(np.mean(y)) if len(y) > 0 else 1.0
            accuracy = max(0.0, 1.0 - (mae / mean_y)) if mean_y > 0 else 0.0

            feature_names = [
                "difficulty", "priority", "hour", "day", "month",
                "user_time", "category", "is_weekend", "time_slot",
            ]
            importances = dict(zip(
                feature_names[: len(self.model.feature_importances_)],
                [round(float(v), 4) for v in self.model.feature_importances_],
            ))

            metadata = {
                "trained_at":          datetime.now(timezone.utc).isoformat(),
                "samples":             len(X),
                "accuracy":            round(accuracy, 4),
                "mae_minutes":         round(mae, 2),
                "feature_importances": importances,
                "user_id":             self.user_id,
            }

            # Save to MongoDB instead of disk
            await self._save_model_to_db(metadata)

            logger.info(
                f"✅ Model trained for user {self.user_id} — "
                f"samples={len(X)}, accuracy={accuracy:.3f}, MAE={mae:.2f}"
            )

            return metadata

        except Exception as e:
            logger.error(f"Model training error for {self.user_id}: {e}", exc_info=True)
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # PREDICTION — Enhanced with category + time-slot features
    # ══════════════════════════════════════════════════════════════════════════

    async def predict_accuracy(self, task: Dict, context: Dict) -> float:
        """Predict task accuracy based on user's patterns"""
        try:
            if not self.model:
                loaded = await self._load_model_from_db()
                if not loaded:
                    return 1.0

            features = await self._create_features(task, context)
            features_scaled = self.scaler.transform([features])
            prediction = self.model.predict(features_scaled)[0]
            prediction = max(0.5, min(2.0, prediction))
            return round(prediction, 2)

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 1.0

    # ══════════════════════════════════════════════════════════════════════════
    # PATTERNS — Enhanced with category + chronotype patterns
    # ══════════════════════════════════════════════════════════════════════════

    async def get_productivity_patterns(self) -> Dict[str, Any]:
        """Get learned productivity patterns"""

        history = await self._get_training_data()

        if len(history) < MIN_TRAINING_SAMPLES:
            return {
                "status":          "learning",
                "message":         f"Need {MIN_TRAINING_SAMPLES - len(history)} more completed tasks to identify your patterns",
                "tasks_completed": len(history),
                "tasks_needed":    MIN_TRAINING_SAMPLES,
            }

        metadata = await self._get_model_metadata()

        patterns = {
            "status":              "ready",
            "tasks_completed":     len(history),
            "time_of_day_patterns": await self._analyze_time_patterns(history),
            "day_of_week_patterns": await self._analyze_day_patterns(history),
            "task_type_patterns":   await self._analyze_task_patterns(history),
            "accuracy_patterns":    await self._analyze_accuracy_patterns(history),
            "recommendations":      await self._generate_learning_recommendations(history),
            # Priority 4: New pattern types
            "category_accuracy":   self._compute_category_accuracy(history),
            "difficulty_accuracy": self._compute_difficulty_accuracy(history),
            "time_slot_accuracy":  self._compute_time_slot_accuracy(history),
            # Priority 2: Model metadata if available
            "model_info":          metadata,
        }

        return patterns

    # ══════════════════════════════════════════════════════════════════════════
    # DATA FETCHING
    # ══════════════════════════════════════════════════════════════════════════

    async def _get_training_data(self) -> List[Dict]:
        """Get data for training"""
        cursor = self.db.task_history.find({
            "user_id":    self.user_id,
            "actualTime": {"$exists": True},
            "aiTime":     {"$exists": True}
        }).sort("created_at", -1).limit(500)

        return await cursor.to_list(500)

    # ══════════════════════════════════════════════════════════════════════════
    # FEATURE ENGINEERING — Priority 2: Enhanced with category + time-slot
    # ══════════════════════════════════════════════════════════════════════════

    async def _prepare_features(self, history: List[Dict]) -> tuple:
        """Prepare features for training — enhanced with category + time-slot"""
        X = []
        y = []

        all_categories = list(set(
            self._categorize_task(t.get("name", ""))
            for t in history
        ))
        for t in history:
            cat = t.get("category", "")
            if cat and cat not in all_categories:
                all_categories.append(cat)

        category_map = {cat: idx for idx, cat in enumerate(all_categories)}

        for task in history:
            ai_time     = task.get("aiTime", 0)
            actual_time = task.get("actualTime", 0)

            if ai_time <= 0 or actual_time <= 0:
                continue

            difficulty_map = {"easy": 1, "medium": 2, "hard": 3}
            difficulty = difficulty_map.get(task.get("difficulty", "medium"), 2)

            priority_map = {"low": 1, "medium": 2, "high": 3}
            priority = priority_map.get(task.get("priority", "medium"), 2)

            created_at = task.get("created_at", datetime.now())
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    created_at = datetime.now()
            hour = task.get("hour_of_day", created_at.hour)

            day_str = task.get("day_of_week", "")
            if day_str:
                day_names = [
                    "Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday",
                ]
                day = day_names.index(day_str) if day_str in day_names else created_at.weekday()
            else:
                day = created_at.weekday()

            month     = created_at.month
            user_time = task.get("userTime", task.get("aiTime", 1))

            task_name         = task.get("name", "")
            feedback_category = task.get("category", "")
            category          = feedback_category if feedback_category else self._categorize_task(task_name)
            category_encoded  = category_map.get(category, 0)

            is_weekend = 1 if day >= 5 else 0

            if 6 <= hour < 12:
                time_slot = 0
            elif 12 <= hour < 17:
                time_slot = 1
            elif 17 <= hour < 22:
                time_slot = 2
            else:
                time_slot = 3

            accuracy = actual_time / ai_time
            y.append(accuracy)

            X.append([
                difficulty,
                priority,
                hour,
                day,
                month,
                user_time,
                category_encoded,
                is_weekend,
                time_slot,
            ])

        if not X:
            return np.array([]), np.array([])

        return np.array(X), np.array(y)

    async def _create_features(self, task: Dict, context: Dict) -> List[float]:
        """Create feature vector for prediction — matches training features"""

        difficulty_map = {"easy": 1, "medium": 2, "hard": 3}
        priority_map   = {"low": 1, "medium": 2, "high": 3}

        difficulty = difficulty_map.get(task.get("difficulty", "medium"), 2)
        priority   = priority_map.get(task.get("priority", "medium"), 2)

        hour      = context.get("hour", datetime.now().hour)
        day       = context.get("day", datetime.now().weekday())
        month     = context.get("month", datetime.now().month)
        user_time = task.get("time", task.get("estimatedTime", task.get("aiTime", 1)))

        task_name         = task.get("name", task.get("text", ""))
        feedback_category = task.get("category", "")
        category          = feedback_category if feedback_category else self._categorize_task(task_name)
        category_encoded  = hash(category) % 20

        is_weekend = 1 if day >= 5 else 0

        if 6 <= hour < 12:
            time_slot = 0
        elif 12 <= hour < 17:
            time_slot = 1
        elif 17 <= hour < 22:
            time_slot = 2
        else:
            time_slot = 3

        return [
            difficulty,
            priority,
            hour,
            day,
            month,
            user_time,
            category_encoded,
            is_weekend,
            time_slot,
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # ANALYSIS METHODS (all original methods — unchanged)
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_time_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns by time of day"""

        hour_accuracy = {i: [] for i in range(24)}

        for task in history:
            created_at = task.get("created_at", datetime.now())
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    created_at = datetime.now()
            hour = task.get("hour_of_day", created_at.hour)

            if task.get("aiTime", 0) > 0 and task.get("actualTime", 0) > 0:
                accuracy = task["actualTime"] / task["aiTime"]
                hour_accuracy[hour].append(accuracy)

        hour_avg = {}
        for hour, accuracies in hour_accuracy.items():
            if accuracies:
                hour_avg[hour] = round(sum(accuracies) / len(accuracies), 3)

        if hour_avg:
            best_hour  = max(hour_avg.items(), key=lambda x: x[1])[0]
            worst_hour = min(hour_avg.items(), key=lambda x: x[1])[0]
        else:
            best_hour  = None
            worst_hour = None

        return {
            "best_hour":       best_hour,
            "worst_hour":      worst_hour,
            "hourly_accuracy": hour_avg
        }

    async def _analyze_day_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns by day of week"""

        days         = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_accuracy = {day: [] for day in days}

        for task in history:
            day_str = task.get("day_of_week", "")
            if day_str and day_str in days:
                day = day_str
            else:
                created_at = task.get("created_at", datetime.now())
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except (ValueError, TypeError):
                        created_at = datetime.now()
                day = days[created_at.weekday()]

            if task.get("aiTime", 0) > 0 and task.get("actualTime", 0) > 0:
                accuracy = task["actualTime"] / task["aiTime"]
                day_accuracy[day].append(accuracy)

        day_avg = {}
        for day, accuracies in day_accuracy.items():
            if accuracies:
                day_avg[day] = round(sum(accuracies) / len(accuracies), 3)

        if day_avg:
            best_day  = max(day_avg.items(), key=lambda x: x[1])[0]
            worst_day = min(day_avg.items(), key=lambda x: x[1])[0]
        else:
            best_day  = None
            worst_day = None

        return {
            "best_day":       best_day,
            "worst_day":      worst_day,
            "daily_accuracy": day_avg
        }

    async def _analyze_task_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns by task type"""

        task_patterns = {}

        for task in history:
            name     = task.get("name", "").lower()
            category = task.get("category", "") or self._categorize_task(name)

            if category not in task_patterns:
                task_patterns[category] = []

            if task.get("aiTime", 0) > 0 and task.get("actualTime", 0) > 0:
                accuracy = task["actualTime"] / task["aiTime"]
                task_patterns[category].append(accuracy)

        category_avg = {}
        for category, accuracies in task_patterns.items():
            if accuracies:
                category_avg[category] = round(sum(accuracies) / len(accuracies), 3)

        return {
            "category_accuracy": category_avg,
            "top_categories":    sorted(
                category_avg.items(), key=lambda x: x[1], reverse=True
            )[:3]
        }

    def _categorize_task(self, task_name: str) -> str:
        """Categorize task based on name"""
        categories = {
            "work":     ["work", "meeting", "email", "report", "presentation", "call", "project"],
            "study":    ["study", "learn", "read", "course", "class", "homework", "research", "exam"],
            "health":   ["gym", "workout", "exercise", "run", "yoga", "meditate", "walk", "stretch"],
            "creative": ["write", "design", "create", "draw", "paint", "code", "develop", "build"],
            "personal": ["shop", "clean", "cook", "laundry", "organize", "errands", "chores"],
            "social":   ["call", "meet", "friend", "family", "dinner", "lunch", "hangout"],
        }

        task_lower = task_name.lower()
        for category, keywords in categories.items():
            if any(keyword in task_lower for keyword in keywords):
                return category

        return "other"

    async def _analyze_accuracy_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze accuracy patterns over time"""

        if len(history) < 10:
            return {"trend": "stable"}

        sorted_history = sorted(
            history,
            key=lambda x: x.get("created_at", datetime.min)
        )

        accuracies = []
        for task in sorted_history[-20:]:
            if task.get("aiTime", 0) > 0 and task.get("actualTime", 0) > 0:
                accuracies.append(task["actualTime"] / task["aiTime"])

        if len(accuracies) < 5:
            return {"trend": "stable"}

        window     = 5
        moving_avg = []
        for i in range(len(accuracies) - window + 1):
            moving_avg.append(sum(accuracies[i:i + window]) / window)

        if len(moving_avg) >= 2:
            if moving_avg[-1] > moving_avg[0] * 1.1:
                trend = "improving"
            elif moving_avg[-1] < moving_avg[0] * 0.9:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "trend":            trend,
            "current_accuracy": round(accuracies[-1], 3) if accuracies else 1.0,
            "average_accuracy": round(sum(accuracies) / len(accuracies), 3),
            "accuracy_history": [round(a, 3) for a in accuracies[-10:]],
        }

    async def _generate_learning_recommendations(self, history: List[Dict]) -> List[str]:
        """Generate recommendations based on learned patterns"""
        recommendations = []

        time_patterns     = await self._analyze_time_patterns(history)
        day_patterns      = await self._analyze_day_patterns(history)
        task_patterns     = await self._analyze_task_patterns(history)
        accuracy_patterns = await self._analyze_accuracy_patterns(history)

        if time_patterns.get("best_hour") is not None:
            best_h    = time_patterns["best_hour"]
            period    = "AM" if best_h < 12 else "PM"
            display_h = best_h % 12 or 12
            recommendations.append(
                f"⏰ You're most accurate around {display_h}:00 {period}. "
                "Schedule important tasks then!"
            )

        if time_patterns.get("worst_hour") is not None:
            worst_h   = time_patterns["worst_hour"]
            period    = "AM" if worst_h < 12 else "PM"
            display_h = worst_h % 12 or 12
            recommendations.append(
                f"⚠️ Your accuracy drops around {display_h}:00 {period}. "
                "Take breaks or do easier tasks during this time."
            )

        if day_patterns.get("best_day"):
            recommendations.append(
                f"📅 {day_patterns['best_day']} is your most productive day. "
                "Plan your week around it!"
            )

        if task_patterns.get("top_categories"):
            best_category = task_patterns["top_categories"][0]
            recommendations.append(
                f"🎯 You're most accurate with {best_category[0]} tasks. "
                "You have a natural strength here!"
            )

        category_acc = task_patterns.get("category_accuracy", {})
        for cat, acc_val in category_acc.items():
            if acc_val > 1.4:
                pct = round((acc_val - 1) * 100)
                recommendations.append(
                    f"📊 You underestimate {cat} tasks by {pct}%. "
                    "I'm adding extra buffer time for these."
                )
            elif acc_val < 0.6:
                pct = round((1 - acc_val) * 100)
                recommendations.append(
                    f"⚡ You overestimate {cat} tasks by {pct}%. "
                    "You can schedule these more tightly."
                )

        trend = accuracy_patterns.get("trend", "stable")
        if trend == "improving":
            recommendations.append(
                "📈 Your estimation accuracy is improving! Keep tracking your time."
            )
        elif trend == "declining":
            recommendations.append(
                "📉 Your accuracy has been declining. Try being more mindful of time spent."
            )

        # Model status recommendation — now async
        model_meta = await self._get_model_metadata()
        if model_meta:
            acc = model_meta.get("accuracy", 0)
            if acc > 0.8:
                recommendations.append(
                    f"🧠 Your AI model is performing well ({round(acc * 100)}% accuracy). "
                    "Predictions are highly personalized!"
                )
            elif acc > 0.5:
                recommendations.append(
                    f"🌱 Your AI model is learning ({round(acc * 100)}% accuracy). "
                    "Keep completing tasks to improve predictions."
                )

        return recommendations[:7]

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 4: NEW — Category accuracy computation
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_category_accuracy(self, history: List[Dict]) -> Dict[str, float]:
        """Compute per-category accuracy ratios"""
        categories: Dict[str, List[float]] = {}

        for record in history:
            ai_time     = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time <= 0 or actual_time <= 0:
                continue

            category = record.get("category", "") or self._categorize_task(record.get("name", ""))
            if category not in categories:
                categories[category] = []
            categories[category].append(actual_time / ai_time)

        return {
            cat: round(sum(ratios) / len(ratios), 3)
            for cat, ratios in categories.items()
            if len(ratios) >= 2
        }

    def _compute_difficulty_accuracy(self, history: List[Dict]) -> Dict[str, float]:
        """Compute per-difficulty accuracy ratios"""
        buckets: Dict[str, List[float]] = {"easy": [], "medium": [], "hard": []}

        for record in history:
            ai_time     = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            diff        = record.get("difficulty", "medium")
            if ai_time > 0 and actual_time > 0 and diff in buckets:
                buckets[diff].append(actual_time / ai_time)

        return {
            k: round(sum(v) / len(v), 3) if v else 1.0
            for k, v in buckets.items()
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 5: NEW — Time-slot accuracy for chronotype support
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_time_slot_accuracy(self, history: List[Dict]) -> Dict[str, Any]:
        """Compute accuracy by time slot (morning, afternoon, evening, night)"""
        slots = {
            "morning":   {"hours": list(range(6, 12)),  "accuracies": []},
            "afternoon": {"hours": list(range(12, 17)), "accuracies": []},
            "evening":   {"hours": list(range(17, 22)), "accuracies": []},
            "night":     {"hours": list(range(22, 24)) + list(range(0, 6)), "accuracies": []},
        }

        for record in history:
            ai_time     = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time <= 0 or actual_time <= 0:
                continue

            hour = record.get("hour_of_day")
            if hour is None:
                created_at = record.get("created_at")
                if isinstance(created_at, datetime):
                    hour = created_at.hour
                elif isinstance(created_at, str):
                    try:
                        hour = datetime.fromisoformat(created_at).hour
                    except (ValueError, TypeError):
                        continue
                else:
                    continue

            accuracy = actual_time / ai_time

            for slot_name, slot_data in slots.items():
                if hour in slot_data["hours"]:
                    slot_data["accuracies"].append(accuracy)
                    break

        result = {}
        for slot_name, slot_data in slots.items():
            accs = slot_data["accuracies"]
            if accs:
                avg = sum(accs) / len(accs)
                result[slot_name] = {
                    "tasks_completed": len(accs),
                    "avg_accuracy":    round(avg, 3),
                    "efficiency": (
                        "high"   if avg < 0.9 else
                        "low"    if avg > 1.3 else
                        "normal"
                    ),
                }
            else:
                result[slot_name] = {
                    "tasks_completed": 0,
                    "avg_accuracy":    0,
                    "efficiency":      "no_data",
                }

        best_slot       = ""
        best_count      = 0
        best_efficiency = float("inf")
        for slot_name, data in result.items():
            if data["tasks_completed"] > 0:
                if data["tasks_completed"] >= best_count and data["avg_accuracy"] < best_efficiency:
                    best_efficiency = data["avg_accuracy"]
                    best_count      = data["tasks_completed"]
                    best_slot       = slot_name

        result["best_slot"] = best_slot

        return result
