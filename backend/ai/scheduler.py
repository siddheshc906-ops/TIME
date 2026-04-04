# backend/ai/scheduler.py

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Day-start / end boundaries ────────────────────────────────────────────────
DAY_START = 6.0    # 6 AM  – earliest a task can be placed
DAY_END   = 22.0   # 10 PM – latest a task can end

# ── Default ultradian energy curve (6 AM → 10 PM, one entry per hour) ────────
# Based on the well-studied alertness rhythm:
#   morning ramp → 10 AM peak → post-lunch dip → 3-5 PM secondary peak → evening decay
DEFAULT_ENERGY_CURVE: List[float] = [
    0.30,  # 6 AM
    0.50,  # 7 AM
    0.70,  # 8 AM
    0.88,  # 9 AM
    1.00,  # 10 AM  ← primary peak
    0.92,  # 11 AM
    0.80,  # 12 PM
    0.55,  # 1 PM   ← post-lunch dip
    0.48,  # 2 PM
    0.62,  # 3 PM   ← secondary rise
    0.74,  # 4 PM
    0.78,  # 5 PM   ← secondary peak
    0.68,  # 6 PM
    0.52,  # 7 PM
    0.40,  # 8 PM
    0.28,  # 9 PM
    0.18,  # 10 PM
]

# ── Chronotype-shifted energy curves ─────────────────────────────────────────
# Each chronotype has a different peak window — these curves shift energy
# to match the user's natural rhythm.
CHRONOTYPE_ENERGY_CURVES: Dict[str, List[float]] = {
    "morning": [
        0.50,  # 6 AM
        0.72,  # 7 AM
        0.90,  # 8 AM
        1.00,  # 9 AM  ← peak
        0.95,  # 10 AM ← peak
        0.85,  # 11 AM
        0.70,  # 12 PM
        0.50,  # 1 PM
        0.42,  # 2 PM
        0.55,  # 3 PM
        0.60,  # 4 PM
        0.55,  # 5 PM
        0.45,  # 6 PM
        0.35,  # 7 PM
        0.25,  # 8 PM
        0.18,  # 9 PM
        0.10,  # 10 PM
    ],
    "afternoon": [
        0.20,  # 6 AM
        0.35,  # 7 AM
        0.50,  # 8 AM
        0.65,  # 9 AM
        0.75,  # 10 AM
        0.72,  # 11 AM
        0.68,  # 12 PM
        0.60,  # 1 PM
        0.78,  # 2 PM  ← rise
        0.92,  # 3 PM  ← peak
        1.00,  # 4 PM  ← peak
        0.90,  # 5 PM
        0.72,  # 6 PM
        0.55,  # 7 PM
        0.38,  # 8 PM
        0.25,  # 9 PM
        0.15,  # 10 PM
    ],
    "evening": [
        0.15,  # 6 AM
        0.25,  # 7 AM
        0.35,  # 8 AM
        0.45,  # 9 AM
        0.55,  # 10 AM
        0.58,  # 11 AM
        0.55,  # 12 PM
        0.50,  # 1 PM
        0.55,  # 2 PM
        0.62,  # 3 PM
        0.70,  # 4 PM
        0.78,  # 5 PM
        0.88,  # 6 PM
        0.95,  # 7 PM
        1.00,  # 8 PM  ← peak
        0.90,  # 9 PM  ← peak
        0.70,  # 10 PM
    ],
    "night": [
        0.10,  # 6 AM
        0.18,  # 7 AM
        0.28,  # 8 AM
        0.38,  # 9 AM
        0.48,  # 10 AM
        0.50,  # 11 AM
        0.48,  # 12 PM
        0.45,  # 1 PM
        0.50,  # 2 PM
        0.55,  # 3 PM
        0.60,  # 4 PM
        0.68,  # 5 PM
        0.78,  # 6 PM
        0.88,  # 7 PM
        0.95,  # 8 PM
        1.00,  # 9 PM  ← peak
        0.92,  # 10 PM ← peak
    ],
}

# ── Minimum gap (hours) inserted between consecutive tasks ───────────────────
TASK_BUFFER = 0.25   # 15 min

# ── Break threshold: gaps larger than this get a labelled break block ─────────
BREAK_THRESHOLD = 0.5   # 30 min


class IntelligentScheduler:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        # ── Priority 2 + 5: Cached context loaded during scheduling ──
        self._accuracy: Dict[str, float] = {"easy": 1.0, "medium": 1.0, "hard": 1.0}
        self._category_accuracy: Dict[str, float] = {}
        self._chronotype_slot: str = ""  # morning / afternoon / evening / night

    # ══════════════════════════════════════════════════════════════════════════
    # Public entry point (existing — enhanced)
    # ══════════════════════════════════════════════════════════════════════════

    async def create_optimal_schedule(
        self,
        tasks:       List[Dict],
        preferences: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Build an optimally ordered, energy-aligned schedule for the given tasks.

        Returns:
            {
              "schedule":          List[Dict],   # ordered task blocks
              "insights":          List[str],
              "total_focus_time":  float,         # hours
              "energy_aligned":    float,         # 0-1 alignment score
            }
        """
        prefs = preferences or {}

        if not tasks:
            return {
                "schedule":         [],
                "insights":         ["No tasks provided — add some tasks to get started!"],
                "total_focus_time": 0.0,
                "energy_aligned":   0.0,
            }

        # ── Priority 2 + 5: Load user accuracy + chronotype before scheduling ──
        await self._load_user_context()

        # 1. Enrich each task with analysis metadata
        analyzed = await self._analyze_tasks(tasks)

        # 2. Build a personalised energy curve (falls back to default)
        energy_curve = await self._build_energy_curve()

        # 3. Determine the day-start from preferences, chronotype, or default
        day_start = self._determine_day_start(prefs)

        # 4. Place tasks into time slots
        schedule = await self._place_tasks(analyzed, energy_curve, day_start)

        # 5. Insert break / buffer blocks in visible gaps
        schedule = self._insert_breaks(schedule)

        # 6. Generate textual insights
        insights = self._generate_insights(schedule, analyzed, energy_curve)

        return {
            "schedule":         schedule,
            "insights":         insights,
            "total_focus_time": self._total_focus_time(schedule),
            "energy_aligned":   self._energy_alignment_score(schedule, energy_curve),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 2 + 5: Load user context (accuracy + chronotype)
    # ══════════════════════════════════════════════════════════════════════════

    async def _load_user_context(self):
        """
        Load user's accuracy multipliers and chronotype before scheduling.
        This data is used to:
        - Adjust task durations (Priority 2)
        - Select the right energy curve (Priority 5)
        - Determine optimal day start (Priority 5)
        """
        try:
            # ── Priority 2: Load accuracy multipliers ──
            self._accuracy = await self._compute_accuracy()
            self._category_accuracy = await self._compute_category_accuracy()

            # ── Priority 5: Determine chronotype from energy patterns ──
            self._chronotype_slot = await self._detect_chronotype_slot()

            if self._chronotype_slot:
                logger.info(
                    f"User {self.user_id}: chronotype={self._chronotype_slot}, "
                    f"accuracy={self._accuracy}"
                )

        except Exception as e:
            logger.error(f"_load_user_context error: {e}")
            # Safe defaults already set in __init__

    async def _compute_accuracy(self) -> Dict[str, float]:
        """
        Per-difficulty time-estimation accuracy multiplier.
        >1 = user takes longer than estimated, <1 = finishes faster.
        """
        try:
            records = await self.db.task_history.find(
                {"user_id": self.user_id}
            ).to_list(500)

            if not records:
                return {"easy": 1.0, "medium": 1.0, "hard": 1.0}

            buckets: Dict[str, List[float]] = {"easy": [], "medium": [], "hard": []}
            for r in records:
                ai_time = r.get("aiTime", 0)
                actual = r.get("actualTime", 0)
                diff = r.get("difficulty", "medium")
                if ai_time > 0 and actual > 0 and diff in buckets:
                    buckets[diff].append(actual / ai_time)

            return {
                k: round(sum(v) / len(v), 2) if v else 1.0
                for k, v in buckets.items()
            }

        except Exception as e:
            logger.error(f"_compute_accuracy error: {e}")
            return {"easy": 1.0, "medium": 1.0, "hard": 1.0}

    async def _compute_category_accuracy(self) -> Dict[str, float]:
        """
        Per-category time-estimation accuracy multiplier.
        """
        try:
            records = await self.db.task_history.find(
                {"user_id": self.user_id}
            ).to_list(500)

            if not records:
                return {}

            categories: Dict[str, List[float]] = defaultdict(list)
            for r in records:
                ai_time = r.get("aiTime", 0)
                actual = r.get("actualTime", 0)
                category = r.get("category", "general")
                if ai_time > 0 and actual > 0:
                    categories[category].append(actual / ai_time)

            return {
                cat: round(sum(ratios) / len(ratios), 3)
                for cat, ratios in categories.items()
                if len(ratios) >= 2
            }

        except Exception as e:
            logger.error(f"_compute_category_accuracy error: {e}")
            return {}

    async def _detect_chronotype_slot(self) -> str:
        """
        Determine user's peak time slot from task history.
        Returns: 'morning', 'afternoon', 'evening', 'night', or '' if insufficient data.
        """
        try:
            records = await self.db.task_history.find(
                {"user_id": self.user_id}
            ).to_list(500)

            if len(records) < 14:
                return ""

            slots = {
                "morning":   list(range(5, 12)),
                "afternoon": list(range(12, 17)),
                "evening":   list(range(17, 22)),
                "night":     list(range(22, 24)) + list(range(0, 5)),
            }

            slot_efficiency: Dict[str, List[float]] = defaultdict(list)

            for record in records:
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
                    else:
                        continue

                ratio = actual_time / ai_time  # lower = more efficient

                for slot_name, hours in slots.items():
                    if hour in hours:
                        slot_efficiency[slot_name].append(ratio)
                        break

            if not slot_efficiency:
                return ""

            # Best slot = lowest average ratio (most efficient)
            best_slot = min(
                slot_efficiency,
                key=lambda s: sum(slot_efficiency[s]) / len(slot_efficiency[s])
            )

            return best_slot

        except Exception as e:
            logger.error(f"_detect_chronotype_slot error: {e}")
            return ""

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 5: Chronotype-aware day start
    # ══════════════════════════════════════════════════════════════════════════

    def _determine_day_start(self, prefs: Dict) -> float:
        """
        Determine schedule start time based on:
        1. Explicit user preference (highest priority)
        2. Chronotype-based default
        3. Fallback to 9 AM
        """
        # User explicitly set a start time
        if prefs.get("day_start") is not None:
            return float(prefs["day_start"])

        # ── Priority 5: Chronotype-based start ──
        chronotype_starts = {
            "morning":   7.0,   # Morning Lions start early
            "afternoon": 9.0,   # Afternoon Wolves start normally
            "evening":   10.0,  # Night Owls start later
            "night":     11.0,  # Midnight Phoenixes start late
        }

        if self._chronotype_slot and self._chronotype_slot in chronotype_starts:
            return chronotype_starts[self._chronotype_slot]

        return 9.0  # default

    # ══════════════════════════════════════════════════════════════════════════
    # Task analysis (existing — enhanced with accuracy adjustment)
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Add focus_required, energy_required, optimal_time, and history metadata."""
        result = []
        for task in tasks:
            similar        = await self._find_similar_tasks(task)
            avg_time       = self._avg_completion_time(similar)
            focus_required = self._focus_score(task)
            energy_required = self._energy_score(task)
            optimal_time   = await self._optimal_start_time(
                task, focus_required, energy_required
            )

            # If history gives a better duration estimate, use it (weighted blend)
            duration = task.get("duration", 1.0)
            if similar and avg_time > 0:
                duration = round(duration * 0.6 + avg_time * 0.4, 2)

            # ── Priority 2: Apply accuracy multiplier from learned data ──
            original_duration = duration
            duration = self._apply_accuracy_adjustment(task, duration)

            result.append({
                **task,
                "duration":           duration,
                "original_duration":  original_duration,
                "adjusted":           abs(duration - original_duration) > 0.05,
                "focus_required":     focus_required,
                "energy_required":    energy_required,
                "optimal_time":       optimal_time,
                "similar_count":      len(similar),
                "history_avg_time":   avg_time,
            })
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 2: Accuracy-based duration adjustment
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_accuracy_adjustment(self, task: Dict, duration: float) -> float:
        """
        Adjust task duration based on learned accuracy data.
        Uses category-specific accuracy if available, otherwise difficulty-based.
        """
        category = task.get("category", "")
        difficulty = task.get("difficulty", "medium")

        # Try category-specific accuracy first (more granular)
        if category and category in self._category_accuracy:
            multiplier = self._category_accuracy[category]
            if multiplier != 1.0:
                adjusted = round(duration * multiplier, 2)
                logger.debug(
                    f"Duration adjusted by category '{category}': "
                    f"{duration}h → {adjusted}h (×{multiplier})"
                )
                return adjusted

        # Fall back to difficulty-based accuracy
        multiplier = self._accuracy.get(difficulty, 1.0)
        if multiplier != 1.0:
            adjusted = round(duration * multiplier, 2)
            logger.debug(
                f"Duration adjusted by difficulty '{difficulty}': "
                f"{duration}h → {adjusted}h (×{multiplier})"
            )
            return adjusted

        return duration

    # ══════════════════════════════════════════════════════════════════════════
    # Personalised energy curve (existing — enhanced with chronotype)
    # ══════════════════════════════════════════════════════════════════════════

    async def _build_energy_curve(self) -> List[float]:
        """
        Attempt to build a personalised 17-point hourly energy curve (6 AM–10 PM)
        from task history.  Falls back to chronotype curve, then default curve.
        """
        try:
            cursor = self.db.task_history.find({
                "user_id":    self.user_id,
                "actualTime": {"$exists": True},
                "aiTime":     {"$exists": True},
            })
            history = await cursor.to_list(200)

            # ── Priority 5: Choose base curve from chronotype ──
            if self._chronotype_slot and self._chronotype_slot in CHRONOTYPE_ENERGY_CURVES:
                base_curve = list(CHRONOTYPE_ENERGY_CURVES[self._chronotype_slot])
                logger.info(
                    f"Using {self._chronotype_slot} chronotype energy curve "
                    f"for user {self.user_id}"
                )
            else:
                base_curve = list(DEFAULT_ENERGY_CURVE)

            if len(history) < 20:
                return base_curve

            # Efficiency = 1 / ratio  (lower ratio = faster = higher energy)
            hour_eff: Dict[int, List[float]] = defaultdict(list)
            for rec in history:
                ai_time = rec.get("aiTime", 0)
                actual  = rec.get("actualTime")

                if not actual or not ai_time or ai_time <= 0:
                    continue

                # ── Enhanced: Use hour_of_day if available ──
                hour = rec.get("hour_of_day")
                if hour is None:
                    created = rec.get("created_at")
                    if isinstance(created, datetime):
                        hour = created.hour
                    else:
                        continue

                hour_eff[hour].append(actual / ai_time)

            if not hour_eff:
                return base_curve

            # Build curve: for each hour slot 6..22 use personal data or base curve
            personal_curve: List[float] = []
            for h in range(6, 23):
                idx = h - 6
                if h in hour_eff and len(hour_eff[h]) >= 3:
                    avg_ratio = sum(hour_eff[h]) / len(hour_eff[h])
                    eff = min(1.0, round(1.0 / avg_ratio, 3))
                    # ── Blend personal data with base curve (70/30) ──
                    blended = round(eff * 0.7 + base_curve[idx] * 0.3, 3)
                    personal_curve.append(blended)
                else:
                    personal_curve.append(base_curve[idx])

            # Normalise so the peak equals 1.0
            peak = max(personal_curve) or 1.0
            return [round(v / peak, 3) for v in personal_curve]

        except Exception as e:
            logger.error(f"_build_energy_curve error: {e}")
            # ── Priority 5: Still try chronotype curve on error ──
            if self._chronotype_slot and self._chronotype_slot in CHRONOTYPE_ENERGY_CURVES:
                return list(CHRONOTYPE_ENERGY_CURVES[self._chronotype_slot])
            return list(DEFAULT_ENERGY_CURVE)

    # ══════════════════════════════════════════════════════════════════════════
    # Core scheduling algorithm (existing — enhanced with chronotype sorting)
    # ══════════════════════════════════════════════════════════════════════════

    async def _place_tasks(
        self,
        tasks:        List[Dict],
        energy_curve: List[float],
        day_start:    float,
    ) -> List[Dict]:
        """
        Two-pass greedy scheduler:
          Pass 1 – place fixed-time tasks (tasks with start_time set)
          Pass 2 – place remaining tasks in the best available energy slot
        """
        fixed    = [t for t in tasks if t.get("start_time") is not None]
        flexible = [t for t in tasks if t.get("start_time") is None]

        schedule: List[Dict] = []

        # ── Pass 1: fixed-time tasks ──────────────────────────────────────────
        for task in sorted(fixed, key=lambda t: t["start_time"]):
            start    = float(task["start_time"])
            duration = task.get("duration", 1.0)
            end      = task.get("end_time", start + duration)
            schedule.append(self._make_slot(task, start, end))

        # ── Pass 2: flexible tasks ────────────────────────────────────────────
        # Priority 5: Sort order depends on whether we're in peak window
        flexible = self._sort_flexible_tasks(flexible, day_start)

        for task in flexible:
            slot = self._find_best_slot(
                task, day_start, energy_curve, schedule
            )
            if slot:
                schedule.append(slot)
            else:
                # Last resort: append after the latest task
                end_of_schedule = max(
                    (s["end_time"] for s in schedule), default=day_start
                )
                dur = task.get("duration", 1.0)
                schedule.append(
                    self._make_slot(task, end_of_schedule + TASK_BUFFER,
                                    end_of_schedule + TASK_BUFFER + dur)
                )

        schedule.sort(key=lambda s: s["start_time"])
        return schedule

    def _sort_flexible_tasks(
        self,
        tasks:     List[Dict],
        day_start: float,
    ) -> List[Dict]:
        """
        Sort flexible tasks for optimal placement.
        Priority 5: During peak window, place hard tasks first.
        Otherwise, sort by priority × focus (descending).
        """
        priority_w = {"high": 3, "medium": 2, "low": 1}
        difficulty_w = {"hard": 3, "medium": 2, "easy": 1}

        current_hour = datetime.now().hour

        # Check if we're currently in the user's peak window
        in_peak = False
        if self._chronotype_slot:
            peak_windows = {
                "morning":   (7, 12),
                "afternoon": (13, 17),
                "evening":   (17, 22),
                "night":     (21, 24),
            }
            window = peak_windows.get(self._chronotype_slot, (9, 12))
            in_peak = window[0] <= current_hour < window[1]

        if in_peak:
            # During peak: hard + high-priority tasks first
            tasks.sort(
                key=lambda t: (
                    -difficulty_w.get(t.get("difficulty", "medium"), 2),
                    -priority_w.get(t.get("priority", "medium"), 2),
                    -t.get("focus_required", 5),
                )
            )
        else:
            # Default: priority × focus descending (existing behaviour)
            tasks.sort(
                key=lambda t: (
                    -priority_w.get(t.get("priority", "medium"), 2),
                    -t.get("focus_required", 5),
                )
            )

        return tasks

    def _find_best_slot(
        self,
        task:         Dict,
        day_start:    float,
        energy_curve: List[float],
        existing:     List[Dict],
    ) -> Optional[Dict]:
        """
        Score every candidate hour between day_start and DAY_END.
        Score = energy_at_hour × (focus_required / 10)
        Bonus: aligns task with its personal optimal_time window.
        Returns the highest-scoring available slot.
        """
        duration     = task.get("duration", 1.0)
        focus_needed = task.get("focus_required", 5)
        optimal_time = task.get("optimal_time")   # float hour or None

        best_score: float = -1.0
        best_start: Optional[float] = None

        # Step through candidate starts at 15-min resolution
        candidate = day_start
        while candidate + duration <= DAY_END:
            if self._slot_is_free(candidate, duration, existing):
                energy = self._energy_at(candidate, energy_curve)
                score  = energy * (focus_needed / 10.0)

                # Proximity bonus: reward slots close to the personal optimal hour
                if optimal_time is not None:
                    distance = abs(candidate - optimal_time)
                    proximity_bonus = max(0.0, 1.0 - distance / 3.0) * 0.2
                    score += proximity_bonus

                # ── Priority 5: Chronotype alignment bonus ──
                # Extra bonus when placing hard tasks during peak slot
                if self._chronotype_slot and task.get("difficulty") == "hard":
                    chrono_bonus = self._chronotype_alignment_bonus(
                        candidate, self._chronotype_slot
                    )
                    score += chrono_bonus

                if score > best_score:
                    best_score = score
                    best_start = candidate

            candidate = round(candidate + 0.25, 2)   # advance 15 min

        if best_start is None:
            return None

        return self._make_slot(task, best_start, best_start + duration,
                               energy_score=self._energy_at(best_start, energy_curve))

    def _chronotype_alignment_bonus(self, hour: float, chronotype_slot: str) -> float:
        """
        Give a bonus score when a task is placed within the user's
        chronotype peak window.
        """
        peak_ranges = {
            "morning":   (8.0, 11.0),
            "afternoon": (13.0, 16.0),
            "evening":   (18.0, 21.0),
            "night":     (20.0, 23.0),
        }

        peak_range = peak_ranges.get(chronotype_slot)
        if not peak_range:
            return 0.0

        start, end = peak_range
        if start <= hour <= end:
            # Maximum bonus at the center of the peak window
            center = (start + end) / 2
            distance = abs(hour - center)
            max_distance = (end - start) / 2
            return round(0.15 * (1.0 - distance / max_distance), 3)

        return 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # Optimal start time for a task (existing — enhanced with chronotype)
    # ══════════════════════════════════════════════════════════════════════════

    async def _optimal_start_time(
        self,
        task:            Dict,
        focus_required:  int,
        energy_required: int,
    ) -> Optional[float]:
        """
        Return the hour at which similar tasks were completed fastest.
        Falls back to chronotype-aware defaults when history is sparse.
        """
        try:
            task_name = task.get("name", "")
            if not task_name:
                return self._default_optimal_time(focus_required)

            cursor = self.db.task_history.find({
                "user_id":    self.user_id,
                "name":       {"$regex": task_name[:20], "$options": "i"},
                "actualTime": {"$exists": True},
                "aiTime":     {"$exists": True},
            }).limit(30)
            similar = await cursor.to_list(30)

            if not similar:
                # Fallback: query by difficulty
                cursor = self.db.task_history.find({
                    "user_id":    self.user_id,
                    "difficulty": task.get("difficulty", "medium"),
                    "actualTime": {"$exists": True},
                    "aiTime":     {"$exists": True},
                }).limit(50)
                similar = await cursor.to_list(50)

            if not similar:
                return self._default_optimal_time(focus_required)

            # Find the hour with the best (lowest) avg ratio
            hour_ratios: Dict[int, List[float]] = defaultdict(list)
            for rec in similar:
                ai_time = rec.get("aiTime", 0)
                actual  = rec.get("actualTime")

                if not actual or not ai_time or ai_time <= 0:
                    continue

                # ── Enhanced: Use hour_of_day if available ──
                hour = rec.get("hour_of_day")
                if hour is None:
                    created = rec.get("created_at")
                    if isinstance(created, datetime):
                        hour = created.hour
                    else:
                        continue

                hour_ratios[hour].append(actual / ai_time)

            if not hour_ratios:
                return self._default_optimal_time(focus_required)

            best_hour = min(
                hour_ratios,
                key=lambda h: sum(hour_ratios[h]) / len(hour_ratios[h])
            )
            return float(best_hour)

        except Exception as e:
            logger.error(f"_optimal_start_time error: {e}")
            return self._default_optimal_time(focus_required)

    def _default_optimal_time(self, focus_required: int) -> float:
        """
        Rule-based fallback: uses chronotype if available,
        otherwise places hard tasks in the morning peak, easy later.
        """
        # ── Priority 5: Chronotype-aware defaults ──
        if self._chronotype_slot:
            peak_centers = {
                "morning":   9.0,
                "afternoon": 14.0,
                "evening":   19.0,
                "night":     21.0,
            }
            base = peak_centers.get(self._chronotype_slot, 10.0)

            if focus_required >= 8:
                return base           # Hard tasks at peak center
            elif focus_required >= 5:
                return base + 1.0     # Medium tasks slightly after peak
            else:
                return base + 3.0     # Easy tasks well after peak

        # Original fallback
        if focus_required >= 8:
            return 9.0    # 9 AM
        if focus_required >= 5:
            return 10.0   # 10 AM
        return 15.0       # 3 PM

    # ══════════════════════════════════════════════════════════════════════════
    # Similar-task lookup (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    async def _find_similar_tasks(self, task: Dict) -> List[Dict]:
        try:
            name = task.get("name", "")
            if not name:
                return []
            cursor = self.db.task_history.find({
                "user_id": self.user_id,
                "name":    {"$regex": name[:20], "$options": "i"},
            }).limit(15)
            return await cursor.to_list(15)
        except Exception as e:
            logger.error(f"_find_similar_tasks error: {e}")
            return []

    # ══════════════════════════════════════════════════════════════════════════
    # Break insertion (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _insert_breaks(self, schedule: List[Dict]) -> List[Dict]:
        """
        Walk through the schedule and insert labelled break blocks
        wherever consecutive tasks have a gap > BREAK_THRESHOLD.
        """
        if not schedule:
            return []

        result: List[Dict] = []
        for i, task in enumerate(schedule):
            result.append(task)
            if i < len(schedule) - 1:
                gap = schedule[i + 1]["start_time"] - task["end_time"]
                if gap >= BREAK_THRESHOLD:
                    result.append({
                        "task":       "☕ Break",
                        "start_time": task["end_time"],
                        "end_time":   schedule[i + 1]["start_time"],
                        "duration":   round(gap, 2),
                        "type":       "break",
                        "priority":   "low",
                        "focus_score": 0,
                    })
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # Insights generator (existing — enhanced with accuracy + chronotype)
    # ══════════════════════════════════════════════════════════════════════════

    def _generate_insights(
        self,
        schedule:     List[Dict],
        tasks:        List[Dict],
        energy_curve: List[float],
    ) -> List[str]:
        insights: List[str] = []

        work_blocks  = [s for s in schedule if s.get("type") != "break"]
        total_focus  = self._total_focus_time(schedule)
        alignment    = self._energy_alignment_score(schedule, energy_curve)

        # Load warning
        if total_focus > 8:
            insights.append(
                f"⚠️ Heavy day ahead — {total_focus:.1f}h of focused work. "
                "Guard your breaks or you'll hit a wall by mid-afternoon."
            )
        elif total_focus < 3:
            insights.append(
                "✨ Light schedule today. Great opportunity for deep, uninterrupted work "
                "or learning something new."
            )

        # Energy alignment feedback
        if alignment >= 0.75:
            insights.append(
                "🎯 Your hardest tasks are aligned with your peak energy windows — "
                "excellent setup for flow states."
            )
        elif alignment < 0.45:
            insights.append(
                "💡 Some demanding tasks are scheduled during low-energy hours. "
                "Consider shifting hard work to your peak window."
            )

        # High-focus density
        high_focus = [t for t in work_blocks if t.get("focus_score", 0) >= 7]
        if len(high_focus) > 3:
            insights.append(
                f"🧠 {len(high_focus)} high-focus tasks back-to-back is ambitious. "
                "Take at least a 10-min walk between them."
            )

        # History-driven accuracy nudge
        history_adjusted = [t for t in tasks if t.get("similar_count", 0) > 0]
        if history_adjusted:
            insights.append(
                f"📊 Durations for {len(history_adjusted)} task(s) were fine-tuned "
                "using your personal completion history."
            )

        # ── Priority 2: Show accuracy-adjusted tasks ──
        accuracy_adjusted = [t for t in tasks if t.get("adjusted")]
        if accuracy_adjusted:
            names = ", ".join(
                t.get("name", t.get("task", "task"))
                for t in accuracy_adjusted[:3]
            )
            insights.append(
                f"🧠 Adjusted durations for: {names} "
                "(based on your time-estimation patterns)."
            )

        # Fixed-time acknowledgement
        fixed = [t for t in tasks if t.get("start_time") is not None]
        if fixed:
            names = ", ".join(t.get("name", "task") for t in fixed[:2])
            insights.append(
                f"⏰ Fixed time respected for: {names}. "
                "Flexible tasks were arranged around them."
            )

        # ── Priority 5: Chronotype insight ──
        if self._chronotype_slot:
            chronotype_names = {
                "morning":   "Morning Lion 🦁",
                "afternoon": "Afternoon Wolf 🐺",
                "evening":   "Night Owl 🦉",
                "night":     "Midnight Phoenix 🔥",
            }
            chrono_name = chronotype_names.get(self._chronotype_slot, "")
            if chrono_name:
                insights.append(
                    f"⚡ Schedule optimized for your {chrono_name} rhythm — "
                    "hard tasks placed during your peak energy window."
                )

        return insights[:6]  # cap at 6

    # ══════════════════════════════════════════════════════════════════════════
    # Scoring helpers (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _focus_score(self, task: Dict) -> int:
        difficulty_w = {"easy": 3, "medium": 6, "hard": 9}
        priority_w   = {"low": 2, "medium": 5, "high": 8}
        d = difficulty_w.get(task.get("difficulty", "medium"), 6)
        p = priority_w.get(task.get("priority",   "medium"), 5)
        return int((d + p) / 2)

    def _energy_score(self, task: Dict) -> int:
        difficulty_w = {"easy": 2, "medium": 5, "hard": 9}
        return difficulty_w.get(task.get("difficulty", "medium"), 5)

    # ══════════════════════════════════════════════════════════════════════════
    # Slot utilities (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    def _slot_is_free(
        self,
        start:    float,
        duration: float,
        existing: List[Dict],
    ) -> bool:
        end = start + duration
        for block in existing:
            # Overlap check: [start, end) vs [block.start, block.end)
            if start < block["end_time"] and end > block["start_time"]:
                return False
        return True

    @staticmethod
    def _energy_at(hour: float, curve: List[float]) -> float:
        """Interpolate energy value for a fractional hour (e.g. 9.5 = 9:30 AM)."""
        idx = hour - 6.0
        if idx < 0:
            return curve[0]
        if idx >= len(curve) - 1:
            return curve[-1]
        lo  = int(idx)
        frac = idx - lo
        return round(curve[lo] * (1 - frac) + curve[lo + 1] * frac, 3)

    @staticmethod
    def _make_slot(
        task:         Dict,
        start:        float,
        end:          float,
        energy_score: float = 0.5,
    ) -> Dict:
        return {
            "task":         task.get("name", task.get("task", "Unnamed task")),
            "start_time":   round(start, 2),
            "end_time":     round(end,   2),
            "duration":     round(end - start, 2),
            "priority":     task.get("priority",       "medium"),
            "difficulty":   task.get("difficulty",     "medium"),
            "category":     task.get("category",      "general"),
            "focus_score":  task.get("focus_required", 5),
            "energy_score": round(energy_score, 3),
            "type":         "task",
            "is_existing":  task.get("is_existing", False),
        }

    @staticmethod
    def _avg_completion_time(similar_tasks: List[Dict]) -> float:
        times = [
            t.get("actualTime", t.get("aiTime", 0))
            for t in similar_tasks
            if t.get("actualTime") or t.get("aiTime")
        ]
        return round(sum(times) / len(times), 2) if times else 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # Metric calculations (existing — preserved exactly)
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _total_focus_time(schedule: List[Dict]) -> float:
        return round(
            sum(s.get("duration", 0) for s in schedule if s.get("type") != "break"),
            2,
        )

    def _energy_alignment_score(
        self,
        schedule:     List[Dict],
        energy_curve: List[float],
    ) -> float:
        """
        Returns 0-1: how well task focus demands match the energy available.
        Perfect alignment = every high-focus task sits at a high-energy hour.
        """
        scores: List[float] = []
        for block in schedule:
            if block.get("type") == "break":
                continue
            energy = self._energy_at(block["start_time"], energy_curve)
            focus  = block.get("focus_score", 5) / 10.0
            # Alignment is high when both energy and focus demand are high
            scores.append(energy * focus)

        return round(sum(scores) / len(scores), 3) if scores else 0.5