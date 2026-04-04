# backend/ai/analyzer.py

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ProductivityAnalyzer:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db

    # ══════════════════════════════════════════════════════════════════════════
    # Public entry point (existing)
    # ══════════════════════════════════════════════════════════════════════════

    async def analyze_patterns(self) -> Dict[str, Any]:
        """
        Full productivity analysis.  Every key is always present so callers
        never have to guard against missing keys.
        """
        try:
            history = await self._get_task_history()
            plans   = await self._get_daily_plans()

            peak_hours   = self._calc_peak_hours(history)
            completion   = self._calc_completion(history)
            energy       = self._calc_energy_patterns(history)
            focus        = self._calc_focus_patterns(plans)
            streaks      = self._calc_streaks(plans)
            trends       = self._calc_trends(history)
            score        = self._calc_productivity_score(history, plans, streaks)
            recs         = self._build_recommendations(
                               history, peak_hours, energy, trends, score)

            return {
                "peak_hours":         peak_hours,
                "task_completion":    completion,
                "energy_patterns":    energy,
                "focus_patterns":     focus,
                "productivity_score": score,
                "recommendations":   recs,
                "streaks":           streaks,
                "trends":            trends,
            }

        except Exception as e:
            logger.error(f"analyze_patterns error: {e}", exc_info=True)
            return self._empty_result()

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 4: Full profile — called by TimevoraAI.get_productivity_profile()
    # ══════════════════════════════════════════════════════════════════════════

    async def get_full_profile(self, history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Get complete productivity profile for the frontend.
        Builds on analyze_patterns() and adds category accuracy,
        overall accuracy, accuracy trend, and chronotype data.
        """
        try:
            if history is None:
                history = await self._get_task_history()

            # Base analysis
            base = await self.analyze_patterns()

            # ── Priority 4: Category accuracy ──
            base["category_accuracy"] = self._calc_category_accuracy(history)

            # ── Priority 4: Difficulty accuracy ──
            base["difficulty_accuracy"] = self._calc_difficulty_accuracy(history)

            # ── Priority 4: Overall accuracy ──
            overall_acc = self._calc_overall_accuracy(history)
            base["overall_accuracy"] = overall_acc

            # ── Priority 4: Accuracy trend (improving / stable / declining) ──
            base["accuracy_trend"] = self._calc_accuracy_trend(history)

            # ── Priority 5: Time-slot performance ──
            base["time_slot_performance"] = self._calc_time_slot_performance(history)

            # ── Priority 5: Best day of the week ──
            base["best_day"] = self._calc_best_day(history)

            # Total tasks
            base["total_tasks"] = len(history)

            return base

        except Exception as e:
            logger.error(f"get_full_profile error: {e}", exc_info=True)
            base = self._empty_result()
            base["category_accuracy"] = {}
            base["difficulty_accuracy"] = {"easy": 1.0, "medium": 1.0, "hard": 1.0}
            base["overall_accuracy"] = 0
            base["accuracy_trend"] = "insufficient_data"
            base["time_slot_performance"] = {}
            base["best_day"] = ""
            base["total_tasks"] = 0
            return base

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 5: Chronotype detection — called by TimevoraAI._compute_chronotype()
    # and directly by core.py
    # ══════════════════════════════════════════════════════════════════════════

    def get_chronotype(self, energy_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify user's chronotype based on their energy patterns.
        Called by core.py with the output of _calc_energy_patterns().
        """
        best_slot = energy_patterns.get("best_time_slot", "")

        chronotypes = {
            "morning": {
                "type": "Morning Lion",
                "emoji": "🦁",
                "peak": "9–11 AM",
                "peak_slot": "morning",
                "description": (
                    "You're at your sharpest in the morning. "
                    "Schedule complex tasks before lunch."
                ),
                "color": "#F59E0B",
                "ready": True,
            },
            "afternoon": {
                "type": "Afternoon Wolf",
                "emoji": "🐺",
                "peak": "2–4 PM",
                "peak_slot": "afternoon",
                "description": (
                    "You hit your stride after lunch. "
                    "Use mornings for light tasks, save deep work for afternoon."
                ),
                "color": "#8B5CF6",
                "ready": True,
            },
            "evening": {
                "type": "Night Owl",
                "emoji": "🦉",
                "peak": "8–10 PM",
                "peak_slot": "evening",
                "description": (
                    "Your creative energy peaks in the evening. "
                    "Protect those late hours for important work."
                ),
                "color": "#3B82F6",
                "ready": True,
            },
            "night": {
                "type": "Midnight Phoenix",
                "emoji": "🔥",
                "peak": "10 PM – 1 AM",
                "peak_slot": "night",
                "description": (
                    "You do your best work when the world is quiet. "
                    "Embrace your late-night power hours."
                ),
                "color": "#EF4444",
                "ready": True,
            },
        }

        default = {
            "type": "Balanced Bear",
            "emoji": "🐻",
            "peak": "Varies",
            "peak_slot": "",
            "description": (
                "You perform consistently throughout the day. "
                "Flexible scheduling works best for you."
            ),
            "color": "#10B981",
            "ready": True,
        }

        return chronotypes.get(best_slot, default)

    def get_chronotype_from_history(self, history: List[Dict]) -> Dict[str, Any]:
        """
        Compute chronotype directly from task history.
        Used when energy_patterns haven't been pre-computed.
        """
        if len(history) < 14:
            return {
                "ready": False,
                "tasks_needed": 14 - len(history),
                "message": f"Complete {14 - len(history)} more tasks to discover your chronotype!",
            }

        energy = self._calc_energy_patterns(history)
        chrono = self.get_chronotype(energy)

        # Add time-slot performance stats
        chrono["time_stats"] = self._calc_time_slot_performance(history)
        chrono["total_tasks_analyzed"] = len(history)

        return chrono

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 4: Category accuracy
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_category_accuracy(self, history: List[Dict]) -> Dict[str, float]:
        """
        Compute average actual/ai ratio per task category.
        >1.0 means user takes longer than estimated (underestimate).
        <1.0 means user finishes faster (overestimate).
        """
        categories: Dict[str, List[float]] = defaultdict(list)

        for record in history:
            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time <= 0 or actual_time <= 0:
                continue

            # Use stored category, or derive from task name
            category = record.get("category", "")
            if not category or category == "general":
                category = self._categorize_task(record.get("name", ""))

            categories[category].append(actual_time / ai_time)

        return {
            cat: round(sum(ratios) / len(ratios), 3)
            for cat, ratios in categories.items()
            if len(ratios) >= 2  # Need at least 2 data points
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 4: Difficulty accuracy
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_difficulty_accuracy(self, history: List[Dict]) -> Dict[str, float]:
        """
        Compute average actual/ai ratio per difficulty level.
        """
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
    # Priority 4: Overall accuracy + trend
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_overall_accuracy(self, history: List[Dict]) -> float:
        """
        Overall AI prediction accuracy as a single number.
        Returns ratio of aiTime/actualTime averaged across all tasks.
        Closer to 1.0 = more accurate predictions.
        """
        ratios = []
        for h in history:
            ai_time = h.get("aiTime", 0)
            actual_time = h.get("actualTime", 0)
            if ai_time > 0 and actual_time > 0:
                ratios.append(ai_time / actual_time)

        if not ratios:
            return 0.0
        return round(sum(ratios) / len(ratios), 3)

    def _calc_accuracy_trend(self, history: List[Dict]) -> str:
        """
        Is the AI getting more accurate over time?
        Compares first-half error vs second-half error.
        """
        valid = [
            h for h in history
            if h.get("aiTime", 0) > 0 and h.get("actualTime", 0) > 0
        ]

        if len(valid) < 10:
            return "insufficient_data"

        # Sort by creation date (oldest first)
        sorted_history = sorted(
            valid,
            key=lambda x: x.get("created_at", datetime.min)
        )
        mid = len(sorted_history) // 2

        first_half = [h["aiTime"] / h["actualTime"] for h in sorted_history[:mid]]
        second_half = [h["aiTime"] / h["actualTime"] for h in sorted_history[mid:]]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        # Closer to 1.0 = more accurate
        first_error = abs(first_avg - 1.0)
        second_error = abs(second_avg - 1.0)

        if second_error < first_error * 0.8:
            return "improving"
        elif second_error > first_error * 1.2:
            return "declining"
        else:
            return "stable"

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 5: Time-slot performance (for chronotype details)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_time_slot_performance(self, history: List[Dict]) -> Dict[str, Any]:
        """
        Calculate performance metrics by time slot (morning/afternoon/evening/night).
        Used for chronotype detail cards in the frontend.
        """
        slots = {
            "morning":   {"hours": list(range(6, 12)),  "tasks": 0, "total_accuracy": 0.0, "total_time": 0.0},
            "afternoon": {"hours": list(range(12, 17)), "tasks": 0, "total_accuracy": 0.0, "total_time": 0.0},
            "evening":   {"hours": list(range(17, 22)), "tasks": 0, "total_accuracy": 0.0, "total_time": 0.0},
            "night":     {"hours": list(range(22, 24)) + list(range(0, 6)), "tasks": 0, "total_accuracy": 0.0, "total_time": 0.0},
        }

        for record in history:
            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time <= 0 or actual_time <= 0:
                continue

            # Determine hour
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

            accuracy = ai_time / actual_time  # >1 = faster than expected

            for slot_name, slot_data in slots.items():
                if hour in slot_data["hours"]:
                    slot_data["tasks"] += 1
                    slot_data["total_accuracy"] += accuracy
                    slot_data["total_time"] += actual_time
                    break

        result = {}
        for slot_name, slot_data in slots.items():
            if slot_data["tasks"] > 0:
                avg_acc = slot_data["total_accuracy"] / slot_data["tasks"]
                result[slot_name] = {
                    "tasks_completed": slot_data["tasks"],
                    "avg_accuracy": round(avg_acc, 3),
                    "total_time_hours": round(slot_data["total_time"] / 60, 1),
                    "efficiency": (
                        "high" if avg_acc > 1.1 else
                        "low" if avg_acc < 0.8 else
                        "normal"
                    ),
                }
            else:
                result[slot_name] = {
                    "tasks_completed": 0,
                    "avg_accuracy": 0,
                    "total_time_hours": 0,
                    "efficiency": "no_data",
                }

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 5: Best day of the week
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_best_day(self, history: List[Dict]) -> str:
        """Find the day of the week where the user performs best."""
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]
        day_performance: Dict[str, List[float]] = defaultdict(list)

        for record in history:
            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time <= 0 or actual_time <= 0:
                continue

            # Get day of week
            day_str = record.get("day_of_week", "")
            if not day_str or day_str not in day_names:
                created_at = record.get("created_at")
                if isinstance(created_at, datetime):
                    day_str = day_names[created_at.weekday()]
                elif isinstance(created_at, str):
                    try:
                        day_str = day_names[datetime.fromisoformat(created_at).weekday()]
                    except (ValueError, TypeError):
                        continue
                else:
                    continue

            accuracy = ai_time / actual_time  # >1 = faster than expected
            day_performance[day_str].append(accuracy)

        if not day_performance:
            return ""

        # Find day with highest average accuracy
        best_day = ""
        best_avg = 0
        for day, accs in day_performance.items():
            avg = sum(accs) / len(accs)
            if avg > best_avg:
                best_avg = avg
                best_day = day

        return best_day

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 4: Task categorization (used by category accuracy)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _categorize_task(task_name: str) -> str:
        """Categorize task based on name keywords."""
        categories = {
            "work": [
                "work", "meeting", "email", "report", "presentation",
                "call", "project", "deadline", "client", "office",
            ],
            "study": [
                "study", "learn", "read", "course", "class", "homework",
                "research", "exam", "assignment", "lecture", "review",
            ],
            "health": [
                "gym", "workout", "exercise", "run", "yoga", "meditate",
                "walk", "stretch", "swim", "sport", "health",
            ],
            "creative": [
                "write", "design", "create", "draw", "paint", "code",
                "develop", "build", "compose", "edit", "blog",
            ],
            "personal": [
                "shop", "clean", "cook", "laundry", "organize", "errands",
                "chores", "groceries", "bank", "appointment",
            ],
            "social": [
                "call", "meet", "friend", "family", "dinner", "lunch",
                "hangout", "party", "gathering", "visit",
            ],
        }

        task_lower = task_name.lower()
        for category, keywords in categories.items():
            if any(keyword in task_lower for keyword in keywords):
                return category

        return "other"

    # ══════════════════════════════════════════════════════════════════════════
    # Data fetchers (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    async def _get_task_history(self) -> List[Dict]:
        """Last 200 completed-feedback tasks for this user."""
        try:
            cursor = self.db.task_history.find(
                {"user_id": self.user_id}
            ).sort("created_at", -1).limit(200)
            return await cursor.to_list(200)
        except Exception as e:
            logger.error(f"_get_task_history error: {e}")
            return []

    async def _get_daily_plans(self) -> List[Dict]:
        """Last 60 daily plans for this user."""
        try:
            cursor = self.db.daily_plans.find(
                {"user_id": self.user_id}
            ).sort("date", -1).limit(60)
            return await cursor.to_list(60)
        except Exception as e:
            logger.error(f"_get_daily_plans error: {e}")
            return []

    # ══════════════════════════════════════════════════════════════════════════
    # Peak hours (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_peak_hours(self, history: List[Dict]) -> Dict[str, Any]:
        """
        Find the hours of day where the user completes tasks *most efficiently*
        (lowest actual/ai ratio = faster than expected = peak performance).
        """
        hour_ratios: Dict[int, List[float]] = defaultdict(list)

        for task in history:
            created_at = task.get("created_at")
            ai_time    = task.get("aiTime", 0)
            actual     = task.get("actualTime")

            if not actual or not ai_time or ai_time <= 0:
                continue

            # ── Enhanced: Use hour_of_day if available ──
            hour = task.get("hour_of_day")
            if hour is None:
                if isinstance(created_at, datetime):
                    hour = created_at.hour
                elif isinstance(created_at, str):
                    try:
                        hour = datetime.fromisoformat(created_at).hour
                    except (ValueError, TypeError):
                        continue
                else:
                    continue

            ratio = actual / ai_time          # <1 = faster than expected
            hour_ratios[hour].append(ratio)

        if not hour_ratios:
            return {
                "peak_hours": [],
                "hourly_efficiency": {},
                "best_hour": None,
                "worst_hour": None,
                "message": "Complete more tasks to unlock peak-hour insights.",
            }

        # Efficiency = inverse of ratio (higher = better)
        hourly_efficiency: Dict[int, float] = {
            h: round(1.0 / (sum(v) / len(v)), 3)
            for h, v in hour_ratios.items()
        }

        sorted_hours = sorted(hourly_efficiency, key=hourly_efficiency.get, reverse=True)
        peak_hours   = sorted_hours[:3]
        best_hour    = sorted_hours[0]
        worst_hour   = sorted_hours[-1]

        return {
            "peak_hours":         peak_hours,
            "hourly_efficiency":  hourly_efficiency,
            "best_hour":          best_hour,
            "worst_hour":         worst_hour,
            "message": (
                f"You perform best around {self._fmt_hour(best_hour)}. "
                f"Schedule important tasks then."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Task completion (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_completion(self, history: List[Dict]) -> Dict[str, Any]:
        total     = len(history)
        completed = sum(1 for h in history if h.get("actualTime"))

        if total == 0:
            return {
                "total_tasks":    0,
                "completed_tasks": 0,
                "overall_rate":   0,
                "by_difficulty":  {},
                "by_priority":    {},
            }

        by_difficulty: Dict[str, Dict] = {}
        by_priority:   Dict[str, Dict] = {}

        for label, key in [("difficulty", "by_difficulty"), ("priority", "by_priority")]:
            buckets: Dict[str, List] = defaultdict(list)
            for t in history:
                buckets[t.get(label, "medium")].append(bool(t.get("actualTime")))
            result = {}
            for cat, values in buckets.items():
                done = sum(values)
                result[cat] = {
                    "total":     len(values),
                    "completed": done,
                    "rate":      round((done / len(values)) * 100, 1),
                }
            if label == "difficulty":
                by_difficulty = result
            else:
                by_priority = result

        return {
            "total_tasks":    total,
            "completed_tasks": completed,
            "overall_rate":   round((completed / total) * 100, 1),
            "by_difficulty":  by_difficulty,
            "by_priority":    by_priority,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Energy patterns (existing — enhanced with hour_of_day support)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_energy_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """
        Group tasks into morning / afternoon / evening / night and find which
        slot has the best efficiency.
        """
        slots = {
            "morning":   list(range(5, 12)),
            "afternoon": list(range(12, 17)),
            "evening":   list(range(17, 22)),
            "night":     list(range(22, 24)) + list(range(0, 5)),
        }

        slot_ratios: Dict[str, List[float]] = defaultdict(list)

        for task in history:
            created_at = task.get("created_at")
            ai_time    = task.get("aiTime", 0)
            actual     = task.get("actualTime")

            if not actual or not ai_time or ai_time <= 0:
                continue

            # ── Enhanced: Use hour_of_day if available ──
            hour = task.get("hour_of_day")
            if hour is None:
                if isinstance(created_at, datetime):
                    hour = created_at.hour
                elif isinstance(created_at, str):
                    try:
                        hour = datetime.fromisoformat(created_at).hour
                    except (ValueError, TypeError):
                        continue
                else:
                    continue

            ratio = actual / ai_time

            for slot, hours in slots.items():
                if hour in hours:
                    slot_ratios[slot].append(ratio)
                    break

        if not slot_ratios:
            return {
                "best_time_slot":    "morning",
                "slot_efficiency":   {},
                "slot_task_counts":  {},
                "best_day":          "",
                "message": "Track more tasks to discover your best energy window.",
            }

        slot_efficiency: Dict[str, float] = {
            slot: round(1.0 / (sum(v) / len(v)), 3)
            for slot, v in slot_ratios.items()
        }

        best_slot = max(slot_efficiency, key=slot_efficiency.get)

        # ── Priority 5: Also compute best day here ──
        best_day = self._calc_best_day(history) if history else ""

        return {
            "best_time_slot":   best_slot,
            "slot_efficiency":  slot_efficiency,
            "slot_task_counts": {s: len(v) for s, v in slot_ratios.items()},
            "best_day":         best_day,
            "message": (
                f"Your energy peaks in the {best_slot}. "
                "Schedule deep-work sessions then."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Focus patterns (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_focus_patterns(self, plans: List[Dict]) -> Dict[str, Any]:
        """
        Derive focus patterns from daily plans — how long are planned sessions,
        and how many tasks per day on average.
        """
        if not plans:
            return {
                "average_tasks_per_day":  0,
                "average_focus_time":     0,
                "max_focus_day":          None,
                "focus_consistency":      0,
                "message": "Start planning days to see focus insights.",
            }

        daily_tasks:  List[int]   = []
        daily_focus:  List[float] = []
        date_labels:  List[str]   = []

        for plan in plans:
            tasks = plan.get("optimizedTasks", plan.get("schedule", []))
            if not tasks:
                continue
            n_tasks    = len(tasks)
            focus_time = sum(t.get("aiTime", t.get("duration", 1)) for t in tasks)
            daily_tasks.append(n_tasks)
            daily_focus.append(focus_time)
            date_labels.append(plan.get("date", ""))

        if not daily_tasks:
            return {
                "average_tasks_per_day": 0,
                "average_focus_time":    0,
                "max_focus_day":         None,
                "focus_consistency":     0,
                "message": "Add tasks to your plans to see focus data.",
            }

        avg_tasks      = round(sum(daily_tasks) / len(daily_tasks), 1)
        avg_focus      = round(sum(daily_focus) / len(daily_focus), 1)
        max_idx        = daily_focus.index(max(daily_focus))
        max_focus_date = date_labels[max_idx] if date_labels else None

        # Consistency = what % of planned days have at least 2 tasks
        consistent_days = sum(1 for n in daily_tasks if n >= 2)
        consistency     = round((consistent_days / len(daily_tasks)) * 100, 1)

        return {
            "average_tasks_per_day": avg_tasks,
            "average_focus_time":    avg_focus,
            "max_focus_day":         max_focus_date,
            "focus_consistency":     consistency,
            "message": (
                f"You plan ~{avg_tasks} tasks/day with ~{avg_focus}h of focused work."
            ),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Streaks (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_streaks(self, plans: List[Dict]) -> Dict[str, Any]:
        """Calculate current and longest streak of days with planned tasks."""
        if not plans:
            return {
                "current_streak":  0,
                "longest_streak":  0,
                "last_active_date": None,
            }

        # Build a set of active dates
        active_dates = set()
        for plan in plans:
            tasks = plan.get("optimizedTasks", plan.get("schedule", []))
            if tasks:
                try:
                    active_dates.add(
                        datetime.fromisoformat(plan["date"]).date()
                    )
                except (ValueError, KeyError):
                    pass

        if not active_dates:
            return {"current_streak": 0, "longest_streak": 0, "last_active_date": None}

        today   = datetime.now().date()
        sorted_dates = sorted(active_dates, reverse=True)

        # Current streak (working backwards from today or yesterday)
        current = 0
        check   = today
        # Allow today OR yesterday as the start (user may not have planned today yet)
        if check not in active_dates and (check - timedelta(days=1)) in active_dates:
            check = check - timedelta(days=1)

        while check in active_dates:
            current += 1
            check -= timedelta(days=1)

        # Longest streak ever
        longest = 0
        run     = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i - 1] - sorted_dates[i]).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1
        longest = max(longest, current)

        return {
            "current_streak":   current,
            "longest_streak":   longest,
            "last_active_date": sorted_dates[0].isoformat() if sorted_dates else None,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Trends (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_trends(self, history: List[Dict]) -> Dict[str, Any]:
        """
        Determine whether the user's time-estimation accuracy is improving,
        stable, or declining using a simple moving-average comparison.
        """
        if len(history) < 10:
            return {
                "trend":   "stable",
                "message": "Start using the app to see your trends!",
                "data_points": 0,
            }

        sorted_h = sorted(
            history,
            key=lambda x: x.get("created_at", datetime.min)
        )

        ratios: List[float] = []
        for t in sorted_h:
            ai_time = t.get("aiTime", 0)
            actual  = t.get("actualTime")
            if actual and ai_time > 0:
                ratios.append(actual / ai_time)

        if len(ratios) < 5:
            return {
                "trend":      "stable",
                "message":    "Keep completing tasks to reveal your trend.",
                "data_points": len(ratios),
            }

        window = min(5, len(ratios) // 2)
        early  = sum(ratios[:window])  / window
        recent = sum(ratios[-window:]) / window

        # A falling ratio means faster completion = improving
        if recent < early * 0.92:
            trend   = "improving"
            message = "📈 Your task accuracy is getting better. Keep it up!"
        elif recent > early * 1.08:
            trend   = "declining"
            message = "📉 You've been underestimating task times lately. Try adding a 20 % buffer."
        else:
            trend   = "stable"
            message = "Your productivity is steady. Push for a new peak!"

        return {
            "trend":           trend,
            "message":         message,
            "early_avg_ratio": round(early, 3),
            "recent_avg_ratio": round(recent, 3),
            "data_points":     len(ratios),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Productivity score (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _calc_productivity_score(
        self,
        history: List[Dict],
        plans:   List[Dict],
        streaks: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Composite 0-100 score:
          40 % task completion rate
          35 % time-estimation accuracy (closeness to 1.0)
          15 % streak bonus (capped at 30 days)
          10 % planning consistency
        """
        if not history:
            return {"overall": 0, "components": {
                "completion": 0, "accuracy": 0,
                "streak": 0, "consistency": 0,
            }}

        # Completion
        completed       = sum(1 for h in history if h.get("actualTime"))
        completion_pct  = (completed / len(history)) * 100

        # Accuracy (penalise deviation from 1.0)
        ratios = [
            h["actualTime"] / h["aiTime"]
            for h in history
            if h.get("actualTime") and h.get("aiTime", 0) > 0
        ]
        if ratios:
            avg_ratio     = sum(ratios) / len(ratios)
            deviation     = abs(1.0 - avg_ratio)          # 0 = perfect
            accuracy_pct  = max(0, 100 - deviation * 100)
        else:
            accuracy_pct  = 50.0

        # Streak (max contribution at 30 days)
        streak_score = min(streaks.get("current_streak", 0), 30) / 30 * 100

        # Planning consistency from focus patterns
        consistent_days = sum(
            1 for p in plans
            if len(p.get("optimizedTasks", p.get("schedule", []))) >= 2
        )
        consistency_pct = (consistent_days / max(len(plans), 1)) * 100

        overall = round(
            completion_pct  * 0.40
            + accuracy_pct  * 0.35
            + streak_score  * 0.15
            + consistency_pct * 0.10
        )

        return {
            "overall": min(overall, 100),
            "components": {
                "completion":   round(completion_pct,  1),
                "accuracy":     round(accuracy_pct,    1),
                "streak":       round(streak_score,    1),
                "consistency":  round(consistency_pct, 1),
            },
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Recommendations (existing — enhanced with category + chronotype tips)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_recommendations(
        self,
        history:    List[Dict],
        peak_hours: Dict[str, Any],
        energy:     Dict[str, Any],
        trends:     Dict[str, Any],
        score:      Dict[str, Any],
    ) -> List[str]:
        """
        Data-driven recommendations ordered by impact.
        Each string is short and actionable.
        """
        recs: List[str] = []

        # 1. Peak-hour scheduling
        best_hour = peak_hours.get("best_hour")
        if best_hour is not None:
            recs.append(
                f"⏰ Schedule your hardest task around {self._fmt_hour(best_hour)} "
                f"— that's when you finish work fastest."
            )

        worst_hour = peak_hours.get("worst_hour")
        if worst_hour is not None:
            recs.append(
                f"☕ Avoid deep work around {self._fmt_hour(worst_hour)}. "
                "Use that slot for admin or emails instead."
            )

        # 2. Energy slot
        best_slot = energy.get("best_time_slot")
        if best_slot:
            recs.append(
                f"⚡ Your energy peaks in the {best_slot}. "
                "Block that window for focus sessions first."
            )

        # 3. Accuracy / trend
        trend = trends.get("trend", "stable")
        if trend == "improving":
            recs.append("📈 Your time estimates are getting sharper — great calibration!")
        elif trend == "declining":
            recs.append(
                "📉 Your tasks are taking longer than estimated. "
                "Add a 20 % buffer when scheduling hard tasks."
            )

        # 4. Score-based nudges
        components = score.get("components", {})
        if components.get("completion", 100) < 60:
            recs.append(
                "✅ Completion rate is below 60 %. "
                "Try the 2-minute rule: if it takes under 2 min, do it now."
            )
        if components.get("consistency", 100) < 50:
            recs.append(
                "📅 You're skipping planning on many days. "
                "Even a 3-task plan beats none — try planning the night before."
            )
        if score.get("overall", 0) >= 80:
            recs.append(
                "🏆 Productivity score above 80! Challenge yourself with a harder goal this week."
            )

        # ── Priority 4: Category-specific recommendations ──
        if history:
            cat_accuracy = self._calc_category_accuracy(history)
            for cat, acc_val in cat_accuracy.items():
                if acc_val > 1.4:
                    pct = round((acc_val - 1) * 100)
                    recs.append(
                        f"📊 You underestimate {cat} tasks by {pct}%. "
                        "I'm adding buffer time for these automatically."
                    )
                    break  # Only one category tip to avoid spam
                elif acc_val < 0.6:
                    pct = round((1 - acc_val) * 100)
                    recs.append(
                        f"⚡ You overestimate {cat} tasks by {pct}%. "
                        "You can schedule these more tightly."
                    )
                    break

        # ── Priority 5: Best day recommendation ──
        best_day = energy.get("best_day", "")
        if best_day:
            recs.append(
                f"📅 {best_day}s are your most productive day. "
                "Schedule your biggest tasks then!"
            )

        # Limit to 6 most relevant
        return recs[:6]

    # ══════════════════════════════════════════════════════════════════════════
    # Helpers (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _fmt_hour(hour: int) -> str:
        """Convert 24h int to '9 AM' / '2 PM' string."""
        if hour == 0:
            return "12 AM"
        if hour < 12:
            return f"{hour} AM"
        if hour == 12:
            return "12 PM"
        return f"{hour - 12} PM"

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "peak_hours":        {"peak_hours": [], "hourly_efficiency": {},
                                  "best_hour": None, "worst_hour": None,
                                  "message": "Not enough data yet."},
            "task_completion":   {"total_tasks": 0, "completed_tasks": 0,
                                  "overall_rate": 0, "by_difficulty": {},
                                  "by_priority": {}},
            "energy_patterns":   {"best_time_slot": "morning", "slot_efficiency": {},
                                  "slot_task_counts": {}, "best_day": "",
                                  "message": "Not enough data yet."},
            "focus_patterns":    {"average_tasks_per_day": 0, "average_focus_time": 0,
                                  "max_focus_day": None, "focus_consistency": 0,
                                  "message": "Not enough data yet."},
            "productivity_score": {"overall": 0, "components": {
                                   "completion": 0, "accuracy": 0,
                                   "streak": 0, "consistency": 0}},
            "recommendations":   ["Start adding and completing tasks to unlock insights!"],
            "streaks":           {"current_streak": 0, "longest_streak": 0,
                                  "last_active_date": None},
            "trends":            {"trend": "stable",
                                  "message": "Start using the app to see your trends!",
                                  "data_points": 0},
        }