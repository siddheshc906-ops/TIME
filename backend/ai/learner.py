# backend/ai/learner.py

import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import logging
import os
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class AdaptiveLearner:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        self.model = None
        self.scaler = None
        self.model_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "models"
        )
        self.model_path = os.path.join(self.model_dir, f"{user_id}_model.pkl")
        self.scaler_path = os.path.join(self.model_dir, f"{user_id}_scaler.pkl")
        self.metadata_path = os.path.join(self.model_dir, f"{user_id}_meta.pkl")

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
            # Use provided history or fetch from DB
            if history is None:
                history = await self._get_training_data()

            if len(history) < 10:
                logger.info(
                    f"Not enough data for user {self.user_id} "
                    f"({len(history)} records, need 10)"
                )
                return False

            # Prepare features and targets
            X, y = await self._prepare_features(history)

            if len(X) == 0:
                logger.warning(f"No valid features extracted for user {self.user_id}")
                return False

            # Train model
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

            # ── Calculate training metrics ──
            predictions = self.model.predict(X_scaled)
            mae = float(np.mean(np.abs(predictions - y)))
            mean_y = float(np.mean(y)) if len(y) > 0 else 1.0
            accuracy = max(0.0, 1.0 - (mae / mean_y)) if mean_y > 0 else 0.0

            # ── Feature importance (helps understand what matters) ──
            feature_names = [
                "difficulty", "priority", "hour", "day", "month",
                "user_time", "category", "is_weekend", "time_slot",
            ]
            importances = dict(zip(
                feature_names[: len(self.model.feature_importances_)],
                [round(float(v), 4) for v in self.model.feature_importances_],
            ))

            # Save model + metadata
            os.makedirs(self.model_dir, exist_ok=True)
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)

            # ── Priority 2: Save training metadata for the profile endpoint ──
            metadata = {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "samples": len(X),
                "accuracy": round(accuracy, 4),
                "mae_minutes": round(mae, 2),
                "feature_importances": importances,
                "user_id": self.user_id,
            }
            joblib.dump(metadata, self.metadata_path)

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
                # Try to load existing model
                if os.path.exists(self.model_path):
                    self.model = joblib.load(self.model_path)
                    self.scaler = joblib.load(self.scaler_path)
                else:
                    return 1.0  # Default accuracy

            # Prepare features
            features = await self._create_features(task, context)

            # Make prediction
            features_scaled = self.scaler.transform([features])
            prediction = self.model.predict(features_scaled)[0]

            # Ensure prediction is reasonable (0.5 to 2.0)
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

        if len(history) < 10:
            return {
                "status": "learning",
                "message": "Need more data to identify patterns",
                "tasks_completed": len(history),
                "tasks_needed": 10,
            }

        patterns = {
            "status": "ready",
            "tasks_completed": len(history),
            "time_of_day_patterns": await self._analyze_time_patterns(history),
            "day_of_week_patterns": await self._analyze_day_patterns(history),
            "task_type_patterns": await self._analyze_task_patterns(history),
            "accuracy_patterns": await self._analyze_accuracy_patterns(history),
            "recommendations": await self._generate_learning_recommendations(history),
            # ── Priority 4: New pattern types ──
            "category_accuracy": self._compute_category_accuracy(history),
            "difficulty_accuracy": self._compute_difficulty_accuracy(history),
            "time_slot_accuracy": self._compute_time_slot_accuracy(history),
            # ── Priority 2: Model metadata if available ──
            "model_info": self._get_model_metadata(),
        }

        return patterns

    # ══════════════════════════════════════════════════════════════════════════
    # DATA FETCHING
    # ══════════════════════════════════════════════════════════════════════════

    async def _get_training_data(self) -> List[Dict]:
        """Get data for training"""
        cursor = self.db.task_history.find({
            "user_id": self.user_id,
            "actualTime": {"$exists": True},
            "aiTime": {"$exists": True}
        }).sort("created_at", -1).limit(500)

        return await cursor.to_list(500)

    # ══════════════════════════════════════════════════════════════════════════
    # FEATURE ENGINEERING — Priority 2: Enhanced with category + time-slot
    # ══════════════════════════════════════════════════════════════════════════

    async def _prepare_features(self, history: List[Dict]) -> tuple:
        """Prepare features for training — enhanced with category + time-slot"""
        X = []
        y = []

        # Build category mapping from all records
        all_categories = list(set(
            self._categorize_task(t.get("name", ""))
            for t in history
        ))
        # Also include the category field from feedback if available
        for t in history:
            cat = t.get("category", "")
            if cat and cat not in all_categories:
                all_categories.append(cat)

        category_map = {cat: idx for idx, cat in enumerate(all_categories)}

        for task in history:
            ai_time = task.get("aiTime", 0)
            actual_time = task.get("actualTime", 0)

            # Skip invalid records
            if ai_time <= 0 or actual_time <= 0:
                continue

            # Feature: task difficulty (encoded)
            difficulty_map = {"easy": 1, "medium": 2, "hard": 3}
            difficulty = difficulty_map.get(task.get("difficulty", "medium"), 2)

            # Feature: task priority
            priority_map = {"low": 1, "medium": 2, "high": 3}
            priority = priority_map.get(task.get("priority", "medium"), 2)

            # Feature: time of day
            created_at = task.get("created_at", datetime.now())
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    created_at = datetime.now()
            hour = task.get("hour_of_day", created_at.hour)

            # Feature: day of week
            day_str = task.get("day_of_week", "")
            if day_str:
                day_names = [
                    "Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday", "Sunday",
                ]
                day = day_names.index(day_str) if day_str in day_names else created_at.weekday()
            else:
                day = created_at.weekday()

            # Feature: month
            month = created_at.month

            # Feature: user's estimated time
            user_time = task.get("userTime", task.get("aiTime", 1))

            # ── Priority 4: Feature: category (encoded) ──
            task_name = task.get("name", "")
            feedback_category = task.get("category", "")
            category = feedback_category if feedback_category else self._categorize_task(task_name)
            category_encoded = category_map.get(category, 0)

            # ── Priority 5: Feature: is_weekend ──
            is_weekend = 1 if day >= 5 else 0

            # ── Priority 5: Feature: time_slot (morning=0, afternoon=1, evening=2, night=3) ──
            if 6 <= hour < 12:
                time_slot = 0  # morning
            elif 12 <= hour < 17:
                time_slot = 1  # afternoon
            elif 17 <= hour < 22:
                time_slot = 2  # evening
            else:
                time_slot = 3  # night

            # Target: actual time / AI time (accuracy factor)
            accuracy = actual_time / ai_time
            y.append(accuracy)

            # Create feature vector (9 features now)
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
        priority_map = {"low": 1, "medium": 2, "high": 3}

        difficulty = difficulty_map.get(task.get("difficulty", "medium"), 2)
        priority = priority_map.get(task.get("priority", "medium"), 2)

        hour = context.get("hour", datetime.now().hour)
        day = context.get("day", datetime.now().weekday())
        month = context.get("month", datetime.now().month)
        user_time = task.get("time", task.get("estimatedTime", task.get("aiTime", 1)))

        # ── Priority 4: Category feature ──
        task_name = task.get("name", task.get("text", ""))
        feedback_category = task.get("category", "")
        category = feedback_category if feedback_category else self._categorize_task(task_name)
        # Use a simple hash for category encoding during prediction
        category_encoded = hash(category) % 20

        # ── Priority 5: Weekend + time slot features ──
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
    # ANALYSIS METHODS (all existing methods preserved)
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

        # Calculate average accuracy by hour
        hour_avg = {}
        for hour, accuracies in hour_accuracy.items():
            if accuracies:
                hour_avg[hour] = round(sum(accuracies) / len(accuracies), 3)

        # Find best and worst hours
        if hour_avg:
            best_hour = max(hour_avg.items(), key=lambda x: x[1])[0]
            worst_hour = min(hour_avg.items(), key=lambda x: x[1])[0]
        else:
            best_hour = None
            worst_hour = None

        return {
            "best_hour": best_hour,
            "worst_hour": worst_hour,
            "hourly_accuracy": hour_avg
        }

    async def _analyze_day_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns by day of week"""

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_accuracy = {day: [] for day in days}

        for task in history:
            # ── Use stored day_of_week if available ──
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
                day_idx = created_at.weekday()
                day = days[day_idx]

            if task.get("aiTime", 0) > 0 and task.get("actualTime", 0) > 0:
                accuracy = task["actualTime"] / task["aiTime"]
                day_accuracy[day].append(accuracy)

        # Calculate average accuracy by day
        day_avg = {}
        for day, accuracies in day_accuracy.items():
            if accuracies:
                day_avg[day] = round(sum(accuracies) / len(accuracies), 3)

        # Find best and worst days
        if day_avg:
            best_day = max(day_avg.items(), key=lambda x: x[1])[0]
            worst_day = min(day_avg.items(), key=lambda x: x[1])[0]
        else:
            best_day = None
            worst_day = None

        return {
            "best_day": best_day,
            "worst_day": worst_day,
            "daily_accuracy": day_avg
        }

    async def _analyze_task_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns by task type"""

        task_patterns = {}

        for task in history:
            name = task.get("name", "").lower()

            # ── Use feedback category if available, otherwise categorize ──
            category = task.get("category", "") or self._categorize_task(name)

            if category not in task_patterns:
                task_patterns[category] = []

            if task.get("aiTime", 0) > 0 and task.get("actualTime", 0) > 0:
                accuracy = task["actualTime"] / task["aiTime"]
                task_patterns[category].append(accuracy)

        # Calculate average accuracy by category
        category_avg = {}
        for category, accuracies in task_patterns.items():
            if accuracies:
                category_avg[category] = round(sum(accuracies) / len(accuracies), 3)

        return {
            "category_accuracy": category_avg,
            "top_categories": sorted(
                category_avg.items(), key=lambda x: x[1], reverse=True
            )[:3]
        }

    def _categorize_task(self, task_name: str) -> str:
        """Categorize task based on name"""
        categories = {
            "work": ["work", "meeting", "email", "report", "presentation", "call", "project"],
            "study": ["study", "learn", "read", "course", "class", "homework", "research", "exam"],
            "health": ["gym", "workout", "exercise", "run", "yoga", "meditate", "walk", "stretch"],
            "creative": ["write", "design", "create", "draw", "paint", "code", "develop", "build"],
            "personal": ["shop", "clean", "cook", "laundry", "organize", "errands", "chores"],
            "social": ["call", "meet", "friend", "family", "dinner", "lunch", "hangout"],
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

        # Sort by date
        sorted_history = sorted(
            history,
            key=lambda x: x.get("created_at", datetime.min)
        )

        accuracies = []
        for task in sorted_history[-20:]:  # Last 20 tasks
            if task.get("aiTime", 0) > 0 and task.get("actualTime", 0) > 0:
                accuracies.append(task["actualTime"] / task["aiTime"])

        if len(accuracies) < 5:
            return {"trend": "stable"}

        # Calculate moving average
        window = 5
        moving_avg = []
        for i in range(len(accuracies) - window + 1):
            moving_avg.append(sum(accuracies[i:i + window]) / window)

        # Determine trend
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
            "trend": trend,
            "current_accuracy": round(accuracies[-1], 3) if accuracies else 1.0,
            "average_accuracy": round(sum(accuracies) / len(accuracies), 3),
            "accuracy_history": [round(a, 3) for a in accuracies[-10:]],  # Last 10
        }

    async def _generate_learning_recommendations(self, history: List[Dict]) -> List[str]:
        """Generate recommendations based on learned patterns"""
        recommendations = []

        # Get patterns
        time_patterns = await self._analyze_time_patterns(history)
        day_patterns = await self._analyze_day_patterns(history)
        task_patterns = await self._analyze_task_patterns(history)
        accuracy_patterns = await self._analyze_accuracy_patterns(history)

        # Time-based recommendations
        if time_patterns.get("best_hour") is not None:
            best_h = time_patterns["best_hour"]
            period = "AM" if best_h < 12 else "PM"
            display_h = best_h % 12 or 12
            recommendations.append(
                f"⏰ You're most accurate around {display_h}:00 {period}. "
                "Schedule important tasks then!"
            )

        if time_patterns.get("worst_hour") is not None:
            worst_h = time_patterns["worst_hour"]
            period = "AM" if worst_h < 12 else "PM"
            display_h = worst_h % 12 or 12
            recommendations.append(
                f"⚠️ Your accuracy drops around {display_h}:00 {period}. "
                "Take breaks or do easier tasks during this time."
            )

        # Day-based recommendations
        if day_patterns.get("best_day"):
            recommendations.append(
                f"📅 {day_patterns['best_day']} is your most productive day. "
                "Plan your week around it!"
            )

        # Task category recommendations
        if task_patterns.get("top_categories"):
            best_category = task_patterns["top_categories"][0]
            recommendations.append(
                f"🎯 You're most accurate with {best_category[0]} tasks. "
                "You have a natural strength here!"
            )

        # ── Priority 4: Category underestimate warnings ──
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

        # Accuracy trend recommendations
        trend = accuracy_patterns.get("trend", "stable")
        if trend == "improving":
            recommendations.append(
                "📈 Your estimation accuracy is improving! Keep tracking your time."
            )
        elif trend == "declining":
            recommendations.append(
                "📉 Your accuracy has been declining. Try being more mindful of time spent."
            )

        # ── Priority 2: Model status recommendation ──
        model_meta = self._get_model_metadata()
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

        return recommendations[:7]  # Cap at 7 recommendations

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 4: NEW — Category accuracy computation
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_category_accuracy(self, history: List[Dict]) -> Dict[str, float]:
        """Compute per-category accuracy ratios"""
        categories: Dict[str, List[float]] = {}

        for record in history:
            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time <= 0 or actual_time <= 0:
                continue

            # Use stored category or derive from name
            category = record.get("category", "") or self._categorize_task(
                record.get("name", "")
            )
            if category not in categories:
                categories[category] = []
            categories[category].append(actual_time / ai_time)

        return {
            cat: round(sum(ratios) / len(ratios), 3)
            for cat, ratios in categories.items()
            if len(ratios) >= 2  # Need at least 2 samples
        }

    def _compute_difficulty_accuracy(self, history: List[Dict]) -> Dict[str, float]:
        """Compute per-difficulty accuracy ratios"""
        buckets: Dict[str, List[float]] = {"easy": [], "medium": [], "hard": []}

        for record in history:
            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            diff = record.get("difficulty", "medium")
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
            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time <= 0 or actual_time <= 0:
                continue

            # Get hour
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
                    "avg_accuracy": round(avg, 3),
                    "efficiency": (
                        "high" if avg < 0.9 else
                        "low" if avg > 1.3 else
                        "normal"
                    ),
                }
            else:
                result[slot_name] = {
                    "tasks_completed": 0,
                    "avg_accuracy": 0,
                    "efficiency": "no_data",
                }

        # Find best slot
        best_slot = ""
        best_count = 0
        best_efficiency = float("inf")
        for slot_name, data in result.items():
            if data["tasks_completed"] > 0:
                # Best slot = most tasks completed with lowest accuracy ratio
                # (lower ratio means faster completion)
                if data["tasks_completed"] >= best_count and data["avg_accuracy"] < best_efficiency:
                    best_efficiency = data["avg_accuracy"]
                    best_count = data["tasks_completed"]
                    best_slot = slot_name

        result["best_slot"] = best_slot

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 2: NEW — Model metadata retrieval
    # ══════════════════════════════════════════════════════════════════════════

    def _get_model_metadata(self) -> Optional[Dict[str, Any]]:
        """Get stored model training metadata"""
        try:
            if os.path.exists(self.metadata_path):
                return joblib.load(self.metadata_path)
        except Exception as e:
            logger.warning(f"Could not load model metadata: {e}")
        return None

    def is_model_trained(self) -> bool:
        """Check if a trained model exists for this user"""
        return os.path.exists(self.model_path)

    def get_model_age_hours(self) -> Optional[float]:
        """How many hours since the model was last trained"""
        meta = self._get_model_metadata()
        if meta and meta.get("trained_at"):
            try:
                trained_at = datetime.fromisoformat(meta["trained_at"])
                if trained_at.tzinfo is None:
                    trained_at = trained_at.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - trained_at
                return round(age.total_seconds() / 3600, 1)
            except (ValueError, TypeError):
                pass
        return None