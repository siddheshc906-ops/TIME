# backend/ai/core.py

from google import genai
from google.genai import types
import json
import logging
import os
import re
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from pathlib import Path

from .scheduler import IntelligentScheduler
from .analyzer import ProductivityAnalyzer
from .learner import AdaptiveLearner
from .recommender import TaskRecommender
from .nlp import NLProcessor

# Load .env before reading any variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

# ── Gemini setup ───────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set in .env - using fallback mode")
    USE_GEMINI = False
else:
    USE_GEMINI = True
    try:
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
        GEMINI_MODEL = "gemini-2.0-flash"
        logger.info("✅ Gemini client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Gemini initialization failed: {e}")
        USE_GEMINI = False
        _genai_client = None

# ── Valid intent names ─────────────────────────────────────────────────────────
VALID_INTENTS = [
    "create_schedule",
    "modify_schedule",
    "analyze_habits",
    "get_advice",
    "ask_question",
    "check_progress",
    "optimize_schedule",
    "general_chat",
    "redirect_to_performance",
]

# ── JSON format blocks ─────────────────────────────────────────────────────────
_SCHEDULE_FORMAT = """
SCHEDULE JSON (use when type = "schedule"):
{
  "type": "schedule",
  "message": "<short confirmation, max 80 words>",
  "tasks_found": ["task1", "task2"],
  "schedule": [
    {
      "task": "<n>",
      "start_time": "<H:MM AM/PM>",
      "end_time": "<H:MM AM/PM>",
      "duration": <float hours>,
      "priority": "high|medium|low",
      "time": "<H:MM AM/PM> - <H:MM AM/PM>"
    }
  ],
  "insights": ["<tip1>", "<tip2>"]
}"""

_ANALYSIS_FORMAT = """
ANALYSIS JSON (use when type = "analysis"):
{
  "type": "analysis",
  "message": "<summary, max 80 words>",
  "stats": {
    "completion_rate": "<XX%>",
    "total_tasks": <int>,
    "completed": <int>,
    "avg_task_duration": "<X.X hours>",
    "streak": <int>,
    "productivity_score": <int 0-100>
  },
  "insight": "<one key personalised insight — must cite a real number from the data>",
  "recommendations": ["<rec1>", "<rec2>", "<rec3>"]
}"""

_ADVICE_FORMAT = """
ADVICE JSON (use when type = "advice"):
{
  "type": "advice",
  "message": "<intro, max 80 words>",
  "advice_points": ["<tip1>", "<tip2>", "<tip3>"],
  "insight": "<personalised closing thought>"
}"""

_PROGRESS_FORMAT = """
PROGRESS JSON (use when type = "progress"):
{
  "type": "progress",
  "message": "<summary, max 80 words>",
  "stats": {
    "productivity_score": <int>,
    "streak": <int>,
    "total_tasks_completed": <int>,
    "completion_rate": "<XX%>",
    "avg_accuracy": <float>
  },
  "trend": "improving|stable|declining"
}"""

_ANSWER_FORMAT = """
ANSWER JSON (use when type = "answer"):
{
  "type": "answer",
  "message": "<answer, max 120 words>",
  "follow_up": "<optional follow-up question>",
  "suggestions": ["<related1>", "<related2>"]
}"""

_CHAT_FORMAT = """
CHAT JSON (use when type = "chat"):
{
  "type": "chat",
  "message": "<response>",
  "suggestions": ["<suggestion1>", "<suggestion2>", "<suggestion3>"]
}"""


# ── Context container ──────────────────────────────────────────────────────────
class AIContext:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        self.user_profile: Dict = {}
        self.productivity_patterns: Dict = {}
        self.task_history: List[Dict] = []
        self.preferences: Dict = {}
        self.accuracy: Dict[str, float] = {"easy": 1.0, "medium": 1.0, "hard": 1.0}
        self.streak: int = 0
        # ── Priority 4 & 5: Profile and chronotype data ──
        self.category_accuracy: Dict[str, float] = {}
        self.chronotype: Dict[str, Any] = {}
        self.insights: List[Dict] = []

    def to_prompt_string(self) -> str:
        total = len(self.task_history)
        completed = sum(1 for h in self.task_history if h.get("actualTime"))
        comp_pct = round((completed / total) * 100) if total else 0

        parts = [f"Tasks tracked: {total} (completion rate: {comp_pct}%)."]

        if self.streak > 0:
            parts.append(f"Current streak: {self.streak} days.")

        acc = self.accuracy
        parts.append(
            f"Time-estimation accuracy — "
            f"easy: {acc.get('easy', 1.0):.2f}x, "
            f"medium: {acc.get('medium', 1.0):.2f}x, "
            f"hard: {acc.get('hard', 1.0):.2f}x "
            f"(1.0 = perfect, >1 = underestimates, <1 = overestimates)."
        )

        peak = self.productivity_patterns.get("peak_hours", {}).get("peak_hours", [])
        if peak:
            readable = [self._decimal_to_readable(h) for h in peak[:3]]
            parts.append(f"Personal peak productive hours: {', '.join(readable)}.")

        best_slot = self.productivity_patterns.get("energy_patterns", {}).get("best_time_slot", "")
        if best_slot:
            parts.append(f"Best energy window: {best_slot}.")

        trend = self.productivity_patterns.get("trends", {}).get("trend", "stable")
        parts.append(f"Productivity trend: {trend}.")

        score = self.productivity_patterns.get("productivity_score", {}).get("overall", 0)
        if score > 0:
            parts.append(f"Productivity score: {score}/100.")

        # ── Priority 4: Include category accuracy in prompt ──
        if self.category_accuracy:
            cat_parts = []
            for cat, acc_val in self.category_accuracy.items():
                if acc_val > 1.2:
                    cat_parts.append(f"{cat}: finishes {int((acc_val-1)*100)}% faster")
                elif acc_val < 0.8:
                    cat_parts.append(f"{cat}: takes {int((1-acc_val)*100)}% longer")
            if cat_parts:
                parts.append(f"Category patterns: {', '.join(cat_parts)}.")

        # ── Priority 5: Include chronotype in prompt ──
        if self.chronotype and self.chronotype.get("type"):
            parts.append(
                f"Chronotype: {self.chronotype['type']} {self.chronotype.get('emoji', '')} "
                f"(peak: {self.chronotype.get('peak', 'unknown')})."
            )

        return " ".join(parts)

    @staticmethod
    def _decimal_to_readable(hour: float) -> str:
        h = int(hour)
        m = int((hour - h) * 60)
        period = "AM" if h < 12 else "PM"
        display = h % 12 or 12
        return f"{display}:{m:02d} {period}"


# ── Main AI class ──────────────────────────────────────────────────────────────
class TimevoraAI:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        self.context = AIContext(user_id, db)

        self.scheduler = IntelligentScheduler(user_id, db)
        self.analyzer = ProductivityAnalyzer(user_id, db)
        self.learner = AdaptiveLearner(user_id, db)
        self.recommender = TaskRecommender(user_id, db)
        self.nlp = NLProcessor()

        if USE_GEMINI:
            self.client = _genai_client
        else:
            self.client = None

    # ── System prompt builder ──────────────────────────────────────────────────
    def _build_system_prompt(self, extra: str = "") -> str:
        context_summary = self.context.to_prompt_string()
        current_time = datetime.now().strftime("%I:%M %p, %A %B %d %Y")

        prompt = f"""You are Timevora AI, an elite productivity coach.

PERSONALITY
- Direct, warm, encouraging, and data-driven.
- Always reference the user's real numbers.

SCHEDULING RULES
- Fixed-time tasks are placed first — never moved or shrunk.
- Hard tasks go at peak hours.
- Apply accuracy multiplier when adjusting times.

ANALYSIS RULES
- Cite at least one specific number from the context.
- Compare performance to user's own baseline.

RESPONSE RULES — CRITICAL
- Return ONE valid JSON object only.
- No markdown fences, no preamble.
- "message" field: max 80 words.

CURRENT USER CONTEXT
{context_summary}

CURRENT DATE / TIME
{current_time}

JSON FORMAT REFERENCE:
{_SCHEDULE_FORMAT}
{_ANALYSIS_FORMAT}
{_ADVICE_FORMAT}
{_PROGRESS_FORMAT}
{_ANSWER_FORMAT}
{_CHAT_FORMAT}
"""
        if extra:
            prompt += f"\nEXTRA INSTRUCTIONS:\n{extra}\n"
        return prompt

    # ── Public entry point ─────────────────────────────────────────────────────
    async def process_message(self, message: str) -> Dict[str, Any]:
        try:
            await self._load_user_context()
            intent = self._rule_based_intent(message)
            relevant_context = await self._get_relevant_context(intent)

            if intent == "analyze_habits":
                result = await self._handle_habit_analysis(relevant_context)
            elif intent == "check_progress":
                result = await self._handle_progress_check(relevant_context)
            elif intent == "create_schedule":
                result = await self._handle_schedule_creation(message, relevant_context)
            elif intent == "modify_schedule":
                result = await self._handle_schedule_modification(message, relevant_context)
            elif intent == "get_advice":
                result = await self._handle_advice_request(message, relevant_context)
            elif intent == "ask_question":
                result = await self._handle_question(message, relevant_context)
            elif intent == "optimize_schedule":
                result = await self._handle_optimization(message, relevant_context)
            elif intent == "redirect_to_performance":
                result = self._handle_redirect_to_performance(message)
            else:
                result = await self._handle_general_chat(message, relevant_context)

            # ── Priority 4: Attach learning insights to every response ──
            result = self._attach_learning_metadata(result)

            return result

        except Exception as e:
            logger.error(f"process_message error: {e}", exc_info=True)
            return {
                "type": "chat",
                "message": "I ran into a small issue. Please try again!",
                "suggestions": ["Plan my day", "Give me advice", "Show my progress"],
            }

    # ── Context loader (UPDATED — Priority 2, 4, 5) ───────────────────────────
    async def _load_user_context(self):
        try:
            user = await self.db.users.find_one({"_id": self.user_id})
            if user:
                self.context.user_profile = user

            cursor = self.db.task_history.find(
                {"user_id": self.user_id}
            ).sort("created_at", -1).limit(100)
            self.context.task_history = await cursor.to_list(100)

            self.context.productivity_patterns = await self.analyzer.analyze_patterns()

            prefs = await self.db.user_preferences.find_one({"user_id": self.user_id})
            self.context.preferences = prefs or {}

            self.context.accuracy = await self._compute_accuracy()
            self.context.streak = await self._calculate_streak()

            # ── Priority 4: Compute category-level accuracy ──
            self.context.category_accuracy = self._compute_category_accuracy(
                self.context.task_history
            )

            # ── Priority 5: Compute chronotype ──
            self.context.chronotype = self._compute_chronotype(
                self.context.task_history, self.context.productivity_patterns
            )

            # ── Priority 4: Generate insights list ──
            self.context.insights = self._generate_learning_insights(
                self.context.task_history,
                self.context.category_accuracy,
                self.context.chronotype,
                self.context.accuracy,
                self.context.productivity_patterns,
            )

            # ── Priority 2: Check if retrain is needed ──
            await self._check_auto_retrain()

        except Exception as e:
            logger.error(f"_load_user_context error: {e}", exc_info=True)

    # ── Intent detection ───────────────────────────────────────────────────────
    # Keywords that signal this message is clearly about productivity/scheduling
    _PRODUCTIVITY_KEYWORDS = {
        "schedule", "plan", "task", "study", "work", "habit", "analyze",
        "analyse", "progress", "streak", "score", "focus", "optimize", "optimise",
        "reorder", "advice", "suggest", "tips", "recommend", "how do", "what is",
        "why", "explain", "change", "move", "modify", "reschedule", "swap", "shift",
        "today", "tomorrow", "create", "add", "block", "book", "i need to",
        "i have to", "set up", "exam", "revision", "break", "time", "hour",
        "minute", "productive", "productivity", "deadline", "priority", "performance",
        "pattern", "trend", "stat", "accuracy",
    }

    def _rule_based_intent(self, message: str) -> str:
        m = message.lower()
        if any(w in m for w in ["optimize", "optimise", "reorder"]):
            return "optimize_schedule"
        if any(w in m for w in ["progress", "how am i", "stats", "score", "streak"]):
            return "check_progress"
        if any(w in m for w in ["analyze", "analyse", "habit", "pattern", "trend"]):
            return "analyze_habits"
        if any(w in m for w in ["advice", "suggest", "tips", "recommend"]):
            return "get_advice"
        if any(w in m for w in ["what is", "how do", "why", "explain", "?"]):
            return "ask_question"
        if any(w in m for w in [
            "plan", "schedule", "create", "i need to", "i have to", "today",
            "tomorrow", "set up", "add", "block", "book"
        ]):
            return "create_schedule"
        if any(w in m for w in ["change", "move", "modify", "reschedule", "swap", "shift"]):
            return "modify_schedule"

        # If the message has no productivity-related keywords at all,
        # redirect the user to the Performance page where the coaching AI lives.
        has_productivity_keyword = any(kw in m for kw in self._PRODUCTIVITY_KEYWORDS)
        if not has_productivity_keyword:
            return "redirect_to_performance"

        return "general_chat"

    # ── Relevant context builder ───────────────────────────────────────────────
    async def _get_relevant_context(self, intent: str) -> Dict[str, Any]:
        ctx = {
            "user_id": self.user_id,
            "current_time": datetime.now().strftime("%I:%M %p"),
            "current_date": datetime.now().strftime("%A, %B %d"),
            "context_summary": self.context.to_prompt_string(),
        }

        if intent in ("create_schedule", "modify_schedule", "optimize_schedule"):
            today = datetime.now().date().isoformat()
            plan = await self.db.daily_plans.find_one(
                {"user_id": self.user_id, "date": today}
            )
            if plan:
                ctx["current_schedule"] = plan.get("schedule", [])
            cursor = self.db.tasks.find({"user_id": self.user_id, "completed": False})
            ctx["pending_tasks"] = await cursor.to_list(50)

        elif intent in ("analyze_habits", "check_progress"):
            ctx["patterns"] = self.context.productivity_patterns
            ctx["task_history_sample"] = self.context.task_history[:10]
            ctx["stats"] = await self._get_user_stats()

        elif intent == "get_advice":
            ctx["recent_tasks"] = self.context.task_history[:5]
            ctx["patterns"] = self.context.productivity_patterns
            ctx["accuracy"] = self.context.accuracy

        return ctx

    # ── Core AI caller (Gemini) ────────────────────────────────────────────────
    def _call_ai(
        self,
        user_prompt: str,
        extra_system: str = "",
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        if not USE_GEMINI or not self.client:
            logger.warning("Gemini not available - returning fallback response")
            return {
                "type": "schedule",
                "message": "AI features limited — add GEMINI_API_KEY to enable full scheduling.",
                "tasks_found": [],
                "schedule": [],
                "insights": ["Add GEMINI_API_KEY to .env file"]
            }

        system = self._build_system_prompt(extra=extra_system)
        full_prompt = f"{system}\n\nUser: {user_prompt}"

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.7,
                ),
            )
            raw = response.text.strip()

            # Log first 200 chars for debugging
            logger.debug(f"Gemini raw response: {raw[:200]}...")

            # Strip any accidental markdown fences
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            # Parse JSON
            result = json.loads(raw)

            # Ensure required fields exist
            if "type" not in result:
                result["type"] = "chat"
            if "message" not in result:
                result["message"] = "I've processed your request."
            if "suggestions" not in result:
                result["suggestions"] = ["Plan my day", "Give me advice", "Show my progress"]

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON parse failed: {e}")
            logger.error(f"Raw response: {raw[:500]}")
            # Return a fallback schedule using NLP extraction
            tasks = self.nlp.extract_tasks(user_prompt)
            if tasks:
                schedule = self._create_simple_schedule(tasks)
                return {
                    "type": "schedule",
                    "message": f"✅ Created schedule with {len(tasks)} tasks!",
                    "tasks_found": [t["name"] for t in tasks],
                    "schedule": schedule,
                    "insights": ["✨ Tasks scheduled with 15-min breaks"]
                }
            return {
                "type": "chat",
                "message": "I'm having trouble understanding. Could you rephrase?",
                "suggestions": ["Plan my day: study 2 hours, gym 1 hour", "Give me advice"],
            }
        except Exception as e:
            logger.error(f"_call_ai error: {e}", exc_info=True)
            return {
                "type": "chat",
                "message": "Something went wrong. Please try again.",
                "suggestions": ["Plan my day", "Give me advice", "Show my progress"],
            }

    # ── Simple schedule creator (fallback) ─────────────────────────────────────
    def _create_simple_schedule(self, tasks: List[Dict]) -> List[Dict]:
        """Create a simple schedule when AI fails"""
        schedule = []
        current_time = 9.0

        for task in tasks:
            duration = task.get("duration", 1.0)
            start_hour = int(current_time)
            start_min = int((current_time - start_hour) * 60)
            end_time = current_time + duration
            end_hour = int(end_time)
            end_min = int((end_time - end_hour) * 60)

            # Format start time
            start_period = "AM" if start_hour < 12 else "PM"
            start_display = start_hour if start_hour <= 12 else start_hour - 12
            if start_display == 0:
                start_display = 12
            start_str = f"{start_display}:{start_min:02d} {start_period}"

            # Format end time
            end_period = "AM" if end_hour < 12 else "PM"
            end_display = end_hour if end_hour <= 12 else end_hour - 12
            if end_display == 0:
                end_display = 12
            end_str = f"{end_display}:{end_min:02d} {end_period}"

            schedule.append({
                "task": task.get("name", "Task"),
                "start_time": start_str,
                "end_time": end_str,
                "duration": round(duration, 1),
                "priority": task.get("priority", "medium"),
                "time": f"{start_str} - {end_str}"
            })

            current_time = end_time + 0.25  # 15 min break

        return schedule

    # ── MAIN SCHEDULE HANDLER ───────────────────────────────────────────────────
    async def _handle_schedule_creation(
        self, message: str, ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Get existing schedule for today
        today = datetime.now().date().isoformat()
        existing_plan = await self.db.daily_plans.find_one({
            "user_id": self.user_id,
            "date": today
        })

        # Extract existing tasks (preserve them exactly)
        existing_tasks = []
        if existing_plan and existing_plan.get("schedule"):
            for item in existing_plan["schedule"]:
                if item.get("type") != "break":
                    existing_tasks.append({
                        "name": item.get("task", ""),
                        "start_time": item.get("start_time", ""),
                        "end_time": item.get("end_time", ""),
                        "duration": item.get("duration", 1),
                        "priority": item.get("priority", "medium"),
                        "is_existing": True,
                        "fixed": True
                    })

        # Extract new tasks using NLP
        new_tasks = self.nlp.extract_tasks(message)

        if not new_tasks:
            return {
                "type": "clarification",
                "message": "I'd love to build your schedule! Try: 'Study 2 hours, gym 1 hour, team meeting at 3 PM'"
            }

        # ── Clean task names: strip leading filler words left by NLP splitting ──
        import re as _re
        _FILLER = _re.compile(
            r"^\s*(?:and|also|then|i\s+(?:have\s+to|need\s+to|want\s+to|will|should)|"
            r"to\s+|i\s+|also\s+|plus\s+|additionally\s+)+",
            _re.IGNORECASE,
        )
        for t in new_tasks:
            cleaned = _FILLER.sub("", t.get("name", "")).strip(" ,.-")
            if cleaned:
                t["name"] = cleaned[0].upper() + cleaned[1:]

        # Enrich new tasks
        for t in new_tasks:
            t.setdefault("difficulty", self.nlp.estimate_difficulty(t["name"]))
            t.setdefault("priority", self.nlp.estimate_priority(t["name"]))
            t.setdefault("category", self.nlp.categorize_task(t["name"]))
            t.setdefault("duration", 1.0)

        # ── Priority 2: Apply accuracy multiplier from learned data ──
        acc = self.context.accuracy
        cat_acc = self.context.category_accuracy
        for t in new_tasks:
            diff = t.get("difficulty", "medium")
            category = t.get("category", "general")

            # Use category-specific accuracy if available, otherwise difficulty-based
            if category in cat_acc and cat_acc[category] != 1.0:
                multiplier = cat_acc[category]
                logger.info(
                    f"Adjusting '{t['name']}' duration by category '{category}' "
                    f"multiplier {multiplier:.2f}"
                )
            else:
                multiplier = acc.get(diff, 1.0)

            t["original_duration"] = t["duration"]
            t["duration"] = round(t["duration"] * multiplier, 1)
            t["adjusted"] = multiplier != 1.0

        # Combine tasks
        all_tasks = existing_tasks + new_tasks

        # Create schedule manually with proper gaps
        schedule = self._create_schedule_manually(all_tasks, existing_tasks)

        # Format schedule
        formatted = self._format_schedule_items(schedule)

        # Generate insights
        insights = []
        if existing_tasks:
            insights.append(f"✓ Preserved {len(existing_tasks)} existing task(s)")

        # Show adjustment insights
        adjusted_tasks = [t for t in new_tasks if t.get("adjusted")]
        if adjusted_tasks:
            for t in adjusted_tasks[:2]:
                orig = t.get("original_duration", t["duration"])
                insights.append(
                    f"🧠 Adjusted '{t['name']}' from {orig}h → {t['duration']}h "
                    f"(based on your history)"
                )

        # ── Priority 5: Add chronotype-based insight ──
        if self.context.chronotype and self.context.chronotype.get("type"):
            chrono = self.context.chronotype
            insights.append(
                f"{chrono.get('emoji', '⚡')} {chrono['type']}: "
                f"hard tasks placed near your {chrono.get('peak', 'peak')} window"
            )

        # Find free time
        gaps = self._find_free_gaps(formatted)
        for gap in gaps[:2]:
            insights.append(
                f"💡 Free: {gap['start']} – {gap['end']} ({gap['duration']:.1f}h)"
            )

        return {
            "type": "schedule",
            "message": f"✅ Created schedule with {len(new_tasks)} new task{'s' if len(new_tasks) != 1 else ''}!",
            "tasks_found": [t["name"] for t in new_tasks],
            "schedule": formatted,
            "insights": insights if insights else ["✨ Tasks scheduled optimally"],
            "optimized": False
        }

    def _create_schedule_manually(
        self, all_tasks: List[Dict], existing_tasks: List[Dict]
    ) -> List[Dict]:
        """Create schedule manually with proper gaps between tasks (15 min buffer)"""
        schedule = []
        BUFFER = 0.25  # 15 minutes buffer between tasks

        # First, add all existing tasks (preserve their times)
        for task in existing_tasks:
            if task.get("start_time") and task.get("end_time"):
                schedule.append({
                    "task": task["name"],
                    "start_time": task["start_time"],
                    "end_time": task["end_time"],
                    "duration": task.get("duration", 1),
                    "priority": task.get("priority", "medium"),
                    "is_existing": True
                })

        # Get new tasks (without times)
        new_tasks = [t for t in all_tasks if not t.get("is_existing")]

        if not new_tasks:
            return schedule

        # ── Priority 5: Sort new tasks — hard tasks first if user is in peak ──
        chrono = self.context.chronotype
        current_hour = datetime.now().hour
        peak_slot = chrono.get("peak_slot", "") if chrono else ""

        # Determine if we're near peak hours
        in_peak = False
        if peak_slot == "morning" and 6 <= current_hour < 12:
            in_peak = True
        elif peak_slot == "afternoon" and 12 <= current_hour < 17:
            in_peak = True
        elif peak_slot == "evening" and 17 <= current_hour < 22:
            in_peak = True

        if in_peak:
            # Place hard tasks first during peak
            new_tasks.sort(key=lambda t: {
                "hard": 0, "medium": 1, "easy": 2
            }.get(t.get("difficulty", "medium"), 1))
        else:
            # Place by priority
            new_tasks.sort(key=lambda t: {
                "high": 0, "medium": 1, "low": 2
            }.get(t.get("priority", "medium"), 1))

        # Parse existing task times to find occupied slots
        occupied = []
        for task in schedule:
            start = self._parse_time(task.get("start_time", ""))
            end = self._parse_time(task.get("end_time", ""))
            if start is not None and end is not None:
                occupied.append((start, end))

        # Sort occupied slots
        occupied.sort()

        # Find gaps and schedule new tasks with buffer
        day_start = 9.0
        day_end = 22.0
        current_time = day_start
        task_index = 0

        for occ_start, occ_end in occupied:
            # Gap before this occupied task
            gap_start = current_time
            gap_end = occ_start

            # If there's a gap, try to fit tasks
            if gap_end > gap_start + BUFFER:
                gap_duration = gap_end - gap_start
                while (
                    task_index < len(new_tasks)
                    and gap_duration >= new_tasks[task_index]["duration"]
                ):
                    task = new_tasks[task_index]
                    task_start = gap_start
                    task_end = task_start + task["duration"]

                    # Only schedule if it fits within the gap
                    if task_end <= gap_end:
                        schedule.append({
                            "task": task["name"],
                            "start_time": self._fmt_hour(task_start),
                            "end_time": self._fmt_hour(task_end),
                            "duration": task["duration"],
                            "priority": task.get("priority", "medium"),
                            "difficulty": task.get("difficulty", "medium"),
                            "category": task.get("category", "general"),
                            "is_existing": False
                        })
                        gap_start = task_end + BUFFER
                        gap_duration = gap_end - gap_start
                        task_index += 1
                    else:
                        break

            # Move current time to after this occupied task plus buffer
            current_time = occ_end + BUFFER

        # Schedule remaining tasks after last occupied task
        while task_index < len(new_tasks):
            task = new_tasks[task_index]
            if current_time + task["duration"] <= day_end:
                task_end = current_time + task["duration"]
                schedule.append({
                    "task": task["name"],
                    "start_time": self._fmt_hour(current_time),
                    "end_time": self._fmt_hour(task_end),
                    "duration": task["duration"],
                    "priority": task.get("priority", "medium"),
                    "difficulty": task.get("difficulty", "medium"),
                    "category": task.get("category", "general"),
                    "is_existing": False
                })
                current_time = task_end + BUFFER
            else:
                # Task doesn't fit — schedule it at the end of the day
                task_end = day_end
                schedule.append({
                    "task": task["name"],
                    "start_time": self._fmt_hour(current_time),
                    "end_time": self._fmt_hour(task_end),
                    "duration": round(day_end - current_time, 1),
                    "priority": task.get("priority", "medium"),
                    "difficulty": task.get("difficulty", "medium"),
                    "category": task.get("category", "general"),
                    "is_existing": False
                })
            task_index += 1

        # Sort schedule by start time
        def get_start_hour(item):
            time_str = item.get("start_time", "")
            if isinstance(time_str, str):
                return self._parse_time(time_str) or 9.0
            return time_str or 9.0

        schedule.sort(key=get_start_hour)

        return schedule

    # ── Priority learning endpoint ─────────────────────────────────────────────
    async def update_task_priority(self, task_name: str, new_priority: str) -> bool:
        """Learn from user's priority changes and update NLP patterns"""
        try:
            await self.db.priority_feedback.insert_one({
                "user_id": self.user_id,
                "task_name": task_name,
                "new_priority": new_priority,
                "created_at": datetime.now(timezone.utc)
            })
            logger.info(f"Priority feedback recorded for '{task_name}': {new_priority}")
            return True
        except Exception as e:
            logger.error(f"Error updating priority: {e}")
            return False

    async def _handle_schedule_modification(
        self, message: str, ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        existing = ctx.get("current_schedule", [])
        if not existing:
            return {
                "type": "info",
                "message": "No schedule for today. Want me to create one?",
                "suggestions": ["Plan my day", "Create a new schedule"],
            }

        prompt = (
            f"Current schedule:\n{json.dumps(existing, indent=2)}\n\n"
            f"User: '{message}'\n\nModify schedule. Return type='schedule' JSON."
        )
        return self._call_ai(prompt)

    async def _handle_habit_analysis(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        patterns = ctx.get("patterns", {})
        stats = ctx.get("stats", {})

        prompt = (
            f"Productivity patterns:\n{json.dumps(patterns, indent=2, default=str)}\n\n"
            f"Stats:\n{json.dumps(stats, indent=2)}\n\n"
            "Analyse patterns. Return type='analysis' JSON. Cite specific numbers."
        )
        return self._call_ai(prompt, max_tokens=1200)

    async def _handle_advice_request(
        self, message: str, ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            rec_ctx = {
                "task_history": ctx.get("recent_tasks", []),
                "pending_tasks": ctx.get("pending_tasks", []),
            }
            recommendations = await self.recommender.get_recommendations(rec_ctx)
            rec_str = json.dumps(recommendations, indent=2, default=str)
        except Exception:
            rec_str = "No recommendation data available."

        prompt = (
            f"Recommendations:\n{rec_str}\n\n"
            f"User: '{message}'\n\n"
            "Give personalised productivity advice. Return type='advice' JSON."
        )
        return self._call_ai(prompt)

    async def _handle_question(
        self, message: str, ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompt = (
            f"Question: '{message}'\n\n"
            "Answer concisely. Return type='answer' JSON. Keep under 120 words."
        )
        return self._call_ai(prompt)

    async def _handle_progress_check(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        stats = ctx.get("stats", {})
        patterns = ctx.get("patterns", {})

        prompt = (
            f"Stats:\n{json.dumps(stats, indent=2)}\n\n"
            f"Trends:\n{json.dumps(patterns.get('trends', {}), indent=2, default=str)}\n\n"
            "Summarise progress. Return type='progress' JSON. Cite a real number."
        )
        return self._call_ai(prompt)

    async def _handle_optimization(
        self, message: str, ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        existing = ctx.get("current_schedule", [])
        if not existing:
            return {
                "type": "info",
                "message": "No schedule found. Want me to create one?",
                "suggestions": ["Plan my day", "Create a schedule"],
            }

        tasks = [
            {
                "name": item.get("task", ""),
                "duration": item.get("duration", 1),
                "priority": item.get("priority", "medium"),
                "difficulty": item.get("difficulty", "medium"),
                "category": item.get("category", "general"),
            }
            for item in existing
            if item.get("task") and item.get("type") != "break"
        ]

        # Recreate schedule with optimization
        schedule = self._create_schedule_manually(tasks, [])
        formatted = self._format_schedule_items(schedule)

        insights = ["Tasks rearranged for better flow"]

        # ── Priority 5: Add chronotype insight to optimization ──
        if self.context.chronotype and self.context.chronotype.get("type"):
            chrono = self.context.chronotype
            insights.append(
                f"{chrono.get('emoji', '')} Optimized for your {chrono['type']} rhythm"
            )

        return {
            "type": "schedule",
            "message": "✨ I've optimized your schedule!",
            "schedule": formatted,
            "insights": insights,
            "optimized": True
        }

    def _handle_redirect_to_performance(self, message: str) -> Dict[str, Any]:
        """
        Called when the user sends a message unrelated to scheduling/productivity.
        Gently redirects them to the Performance page coaching AI.
        """
        import random
        tips = [
            "Try asking me: 'Plan my study day' or 'Schedule Physics 2h, Maths 1h'.",
            "I can schedule tasks, optimize your day, or analyze your habits.",
            "Say something like: 'I have Chemistry and Biology to study — plan it!'",
        ]
        return {
            "type": "chat",
            "message": (
                "I'm your AI Planner — I specialise in scheduling tasks and "
                "organising your day! 📅\n\n"
                "For coaching questions, productivity tips, and performance "
                "analysis, head to the **Performance** page where the AI Study "
                "Coach is waiting for you. 💡\n\n"
                f"{random.choice(tips)}"
            ),
            "suggestions": [
                "Plan my day",
                "Schedule my tasks",
                "Analyze my habits",
                "Show my progress",
            ],
            "redirect_hint": "performance",
        }

    async def _handle_general_chat(
        self, message: str, ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        streak_note = (
            f"The user is on a {self.context.streak}-day streak. "
            if self.context.streak > 0
            else ""
        )

        # ── Priority 5: Include chronotype in chat context ──
        chrono_note = ""
        if self.context.chronotype and self.context.chronotype.get("type"):
            chrono = self.context.chronotype
            chrono_note = (
                f"User is a {chrono['type']} {chrono.get('emoji', '')} "
                f"(peak: {chrono.get('peak', 'varies')}). "
            )

        prompt = (
            f"User: '{message}'\n\n"
            f"{streak_note}{chrono_note}"
            "Have a friendly conversation. Return type='chat' JSON. Suggest 3 next actions."
        )
        return self._call_ai(prompt)

    # ══════════════════════════════════════════════════════════════════════════
    # PRIORITY 2: Auto-retrain check
    # ══════════════════════════════════════════════════════════════════════════

    async def _check_auto_retrain(self):
        """Check if model needs retraining based on feedback count"""
        try:
            feedback_count = await self.db.task_history.count_documents(
                {"user_id": self.user_id}
            )

            if feedback_count >= 10 and feedback_count % 10 == 0:
                # Check if we already trained for this count
                prefs = self.context.preferences
                last_count = prefs.get("last_trained_count", 0)

                if feedback_count > last_count:
                    logger.info(
                        f"🧠 Auto-retrain triggered for user {self.user_id} "
                        f"({feedback_count} feedbacks)"
                    )
                    asyncio.create_task(self._background_retrain(feedback_count))

        except Exception as e:
            logger.error(f"_check_auto_retrain error: {e}")

    async def _background_retrain(self, feedback_count: int):
        """Background ML model retraining"""
        try:
            history = await self.db.task_history.find(
                {"user_id": self.user_id}
            ).to_list(1000)

            if len(history) < 10:
                return

            result = await self.learner.train_model(history)

            # Update preferences with training metadata
            await self.db.user_preferences.update_one(
                {"user_id": self.user_id},
                {"$set": {
                    "last_trained": datetime.now(timezone.utc),
                    "last_trained_count": feedback_count,
                    "training_samples": len(history),
                    "model_accuracy": result.get("accuracy", 0) if isinstance(result, dict) else 0,
                }},
                upsert=True
            )

            logger.info(f"✅ Model retrained for user {self.user_id}: {result}")

        except Exception as e:
            logger.error(f"❌ Background retrain failed for {self.user_id}: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # PRIORITY 4: Category accuracy + learning insights
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_category_accuracy(self, history: List[Dict]) -> Dict[str, float]:
        """Compute accuracy ratio per task category"""
        if not history:
            return {}

        categories: Dict[str, List[float]] = {}
        for record in history:
            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            if ai_time > 0 and actual_time > 0:
                category = record.get("category", "general")
                if category not in categories:
                    categories[category] = []
                categories[category].append(actual_time / ai_time)

        return {
            cat: round(sum(ratios) / len(ratios), 3)
            for cat, ratios in categories.items()
            if len(ratios) >= 2  # Need at least 2 samples
        }

    def _generate_learning_insights(
        self,
        history: List[Dict],
        category_accuracy: Dict[str, float],
        chronotype: Dict[str, Any],
        difficulty_accuracy: Dict[str, float],
        patterns: Dict[str, Any],
    ) -> List[Dict]:
        """Generate human-readable insights from user data"""
        insights = []
        total = len(history)

        # Category-level insights
        for category, acc_val in category_accuracy.items():
            if acc_val > 1.3:
                pct = round((acc_val - 1) * 100)
                insights.append({
                    "type": "underestimate",
                    "icon": "⏰",
                    "title": f"{category.title()} tasks take longer",
                    "text": (
                        f"You take {pct}% longer on {category} tasks than estimated. "
                        f"Schedules are now automatically adjusted for you."
                    ),
                    "detail": (
                        f"You take {pct}% longer on {category} tasks than estimated. "
                        f"Schedules are now automatically adjusted for you."
                    ),
                    "message": (
                        f"You take {pct}% longer on {category} tasks than estimated. "
                        f"Schedules are now automatically adjusted for you."
                    ),
                    "category": category,
                    "severity": "warning",
                })
            elif acc_val < 0.7:
                pct = round((1 - acc_val) * 100)
                insights.append({
                    "type": "overestimate",
                    "icon": "⚡",
                    "title": f"Fast at {category.title()} tasks",
                    "text": f"You finish {category} tasks {pct}% faster than estimated!",
                    "detail": f"You finish {category} tasks {pct}% faster than estimated!",
                    "message": f"You finish {category} tasks {pct}% faster than estimated!",
                    "category": category,
                    "severity": "positive",
                })

        # Difficulty-level insights
        for diff, acc_val in difficulty_accuracy.items():
            if acc_val > 1.4:
                pct = round((acc_val - 1) * 100)
                insights.append({
                    "type": "difficulty_gap",
                    "icon": "📊",
                    "title": f"{diff.title()} tasks underestimated",
                    "text": f"You underestimate {diff} tasks by {pct}%. I'm adding buffer time.",
                    "detail": f"You underestimate {diff} tasks by {pct}%. I'm adding buffer time.",
                    "message": f"You underestimate {diff} tasks by {pct}%. I'm adding buffer time.",
                    "severity": "info",
                })

        # Chronotype insight
        if chronotype and chronotype.get("type"):
            insights.append({
                "type": "chronotype",
                "icon": chronotype.get("emoji", "⚡"),
                "title": f"You're a {chronotype['type']}",
                "text": (
                    f"You're a {chronotype['type']}! "
                    f"Your peak cognitive window is {chronotype.get('peak', 'varies')}."
                ),
                "detail": (
                    f"You're a {chronotype['type']}! "
                    f"Your peak cognitive window is {chronotype.get('peak', 'varies')}."
                ),
                "message": (
                    f"You're a {chronotype['type']}! "
                    f"Your peak cognitive window is {chronotype.get('peak', 'varies')}."
                ),
                "severity": "info",
            })

        # Energy pattern insight
        best_slot = patterns.get("energy_patterns", {}).get("best_time_slot", "")
        if best_slot:
            insights.append({
                "type": "energy",
                "icon": "🔋",
                "title": f"Peak productivity: {best_slot.title()}",
                "text": (
                    f"Your peak productivity is in the {best_slot}. "
                    f"Hard tasks are auto-scheduled here."
                ),
                "detail": (
                    f"Your peak productivity is in the {best_slot}. "
                    f"Hard tasks are auto-scheduled here."
                ),
                "message": (
                    f"Your peak productivity is in the {best_slot}. "
                    f"Hard tasks are auto-scheduled here."
                ),
                "severity": "info",
            })

        # Best day insight
        best_day = patterns.get("energy_patterns", {}).get("best_day", "")
        if best_day:
            insights.append({
                "type": "day",
                "icon": "📅",
                "title": f"Best day: {best_day}",
                "text": f"{best_day}s are your most productive day of the week.",
                "detail": f"{best_day}s are your most productive day of the week.",
                "message": f"{best_day}s are your most productive day of the week.",
                "severity": "info",
            })

        # Milestone insights
        if total >= 50:
            insights.append({
                "type": "milestone",
                "icon": "🏆",
                "title": "Highly personalised",
                "text": f"AI trained on {total} tasks. Predictions are now highly personalized!",
                "detail": f"AI trained on {total} tasks. Predictions are now highly personalized!",
                "message": f"AI trained on {total} tasks. Predictions are now highly personalized!",
                "severity": "positive",
            })
        elif total >= 20:
            insights.append({
                "type": "milestone",
                "icon": "🧠",
                "title": "ML model active",
                "text": f"ML model active! Trained on {total} task completions.",
                "detail": f"ML model active! Trained on {total} task completions.",
                "message": f"ML model active! Trained on {total} task completions.",
                "severity": "positive",
            })
        elif total >= 10:
            insights.append({
                "type": "milestone",
                "icon": "🌱",
                "title": "Learning in progress",
                "text": f"Learning in progress — {total} tasks analyzed so far.",
                "detail": f"Learning in progress — {total} tasks analyzed so far.",
                "message": f"Learning in progress — {total} tasks analyzed so far.",
                "severity": "info",
            })

        # Trend insight
        trend = patterns.get("trends", {}).get("trend", "stable")
        if trend == "improving":
            insights.append({
                "type": "trend",
                "icon": "📈",
                "title": "Trending up!",
                "text": "Your productivity is trending upward! Keep it going.",
                "detail": "Your productivity is trending upward! Keep it going.",
                "message": "Your productivity is trending upward! Keep it going.",
                "severity": "positive",
            })
        elif trend == "declining":
            insights.append({
                "type": "trend",
                "icon": "📉",
                "title": "Productivity dip",
                "text": "Productivity has dipped recently. Consider shorter focus blocks.",
                "detail": "Productivity has dipped recently. Consider shorter focus blocks.",
                "message": "Productivity has dipped recently. Consider shorter focus blocks.",
                "severity": "warning",
            })

        return insights

    def _attach_learning_metadata(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Attach learning metadata to every AI response for the frontend"""
        result["_learning"] = {
            "feedbacks_given": len(self.context.task_history),
            "model_ready": len(self.context.task_history) >= 10,
            "chronotype": self.context.chronotype if self.context.chronotype else None,
            "insights": self.context.insights[:5] if self.context.insights else [],
            "category_accuracy": self.context.category_accuracy,
            "difficulty_accuracy": self.context.accuracy,
            "streak": self.context.streak,
        }
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # PRIORITY 5: Chronotype detection
    # ══════════════════════════════════════════════════════════════════════════

    def _compute_chronotype(
        self, history: List[Dict], patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classify user's chronotype based on task completion patterns"""
        if len(history) < 14:
            return {
                "ready": False,
                "tasks_needed": 14 - len(history),
                "message": f"Complete {14 - len(history)} more tasks to discover your chronotype!",
            }

        # Use energy patterns from analyzer
        best_slot = patterns.get("energy_patterns", {}).get("best_time_slot", "")

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

        result = chronotypes.get(best_slot, default)

        # Add performance stats by time of day
        result["time_stats"] = self._calculate_time_stats(history)
        result["total_tasks_analyzed"] = len(history)

        return result

    def _calculate_time_stats(self, history: List[Dict]) -> Dict[str, Any]:
        """Calculate performance by time of day"""
        slots = {
            "morning": {"hours": list(range(6, 12)), "tasks": 0, "total_accuracy": 0.0},
            "afternoon": {"hours": list(range(12, 17)), "tasks": 0, "total_accuracy": 0.0},
            "evening": {"hours": list(range(17, 22)), "tasks": 0, "total_accuracy": 0.0},
            "night": {
                "hours": list(range(22, 24)) + list(range(0, 6)),
                "tasks": 0,
                "total_accuracy": 0.0,
            },
        }

        for record in history:
            hour = record.get("hour_of_day")
            if hour is None:
                created = record.get("created_at")
                if isinstance(created, datetime):
                    hour = created.hour
                else:
                    continue

            ai_time = record.get("aiTime", 0)
            actual_time = record.get("actualTime", 0)
            accuracy = (ai_time / actual_time) if actual_time > 0 and ai_time > 0 else 1.0

            for slot_name, slot_data in slots.items():
                if hour in slot_data["hours"]:
                    slot_data["tasks"] += 1
                    slot_data["total_accuracy"] += accuracy
                    break

        result = {}
        for slot_name, slot_data in slots.items():
            if slot_data["tasks"] > 0:
                avg_acc = slot_data["total_accuracy"] / slot_data["tasks"]
                result[slot_name] = {
                    "tasks_completed": slot_data["tasks"],
                    "avg_accuracy": round(avg_acc, 2),
                    "efficiency": "high" if avg_acc > 1.1 else ("low" if avg_acc < 0.8 else "normal"),
                }
            else:
                result[slot_name] = {
                    "tasks_completed": 0,
                    "avg_accuracy": 0,
                    "efficiency": "no_data",
                }

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # PRODUCTIVITY PROFILE & CHRONOTYPE (exposed for API endpoints)
    # ══════════════════════════════════════════════════════════════════════════

    async def get_productivity_profile(self) -> Dict[str, Any]:
        """
        Called by main.py /api/ai/productivity-profile endpoint.
        Returns full profile data including chronotype, accuracy,
        insights and productivity score.
        """
        try:
            await self._load_user_context()
            history = self.context.task_history
            total   = len(history)

            if total < 5:
                return {
                    "ready":           False,
                    "feedbacks_given": total,
                    "feedbacks_needed": max(0, 5 - total),
                    "message": (
                        f"Complete {max(0, 5 - total)} more tasks "
                        "to unlock your AI profile!"
                    ),
                    "insights":    [],
                    "chronotype":  None,
                    "streak":      self.context.streak,
                }

            patterns = self.context.productivity_patterns

            return {
                "ready":             True,
                "feedbacks_given":   total,
                "feedbacks_needed":  0,
                "overall_accuracy":  self._compute_overall_accuracy(history),
                "accuracy_trend":    self._compute_accuracy_trend(history),
                "difficulty_accuracy": self.context.accuracy,
                "category_accuracy": self.context.category_accuracy,
                "energy_patterns":   patterns.get("energy_patterns", {}),
                "chronotype":        self.context.chronotype,
                "insights":          self.context.insights,
                "streak":            self.context.streak,
                "productivity_score": patterns.get(
                    "productivity_score", {}
                ).get("overall", 0),
                "peak_hours":        patterns.get("peak_hours", {}),
                "trends":            patterns.get("trends", {}),
                "streaks":           patterns.get("streaks", {}),
                "task_completion":   patterns.get("task_completion", {}),
                "recommendations":   patterns.get("recommendations", []),
                "message": (
                    f"AI has analysed your {total} completed tasks."
                ),
            }

        except Exception as e:
            logger.error(
                f"get_productivity_profile error: {e}", exc_info=True
            )
            return {
                "ready":           False,
                "feedbacks_given": 0,
                "feedbacks_needed": 5,
                "insights":        [],
                "chronotype":      None,
                "message":         "Could not load profile. Try again.",
            }

    async def get_chronotype_data(self) -> Dict[str, Any]:
        """
        Called by main.py /api/ai/chronotype endpoint.
        Returns the user's chronotype detected from task patterns.
        """
        try:
            await self._load_user_context()
            chrono = self.context.chronotype
            total  = len(self.context.task_history)

            if not chrono or not chrono.get("ready", False):
                return {
                    "ready":          False,
                    "tasks_completed": total,
                    "tasks_needed":   max(0, 14 - total),
                    "message": (
                        f"Complete {max(0, 14 - total)} more tasks "
                        "to discover your chronotype!"
                    ),
                }

            return {
                "ready": True,
                **chrono,
                "tasks_analyzed": total,
            }

        except Exception as e:
            logger.error(
                f"get_chronotype_data error: {e}", exc_info=True
            )
            return {"ready": False, "error": str(e)}

    def _compute_overall_accuracy(self, history: List[Dict]) -> float:
        """Overall AI prediction accuracy"""
        ratios = []
        for h in history:
            ai_time = h.get("aiTime", 0)
            actual_time = h.get("actualTime", 0)
            if ai_time > 0 and actual_time > 0:
                ratios.append(ai_time / actual_time)

        if not ratios:
            return 0.0
        return round(sum(ratios) / len(ratios), 3)

    def _compute_accuracy_trend(self, history: List[Dict]) -> str:
        """Is the AI getting more accurate over time?"""
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

    # ── Stats helpers ──────────────────────────────────────────────────────────
    async def _get_user_stats(self) -> Dict[str, Any]:
        history = self.context.task_history
        if not history:
            return {
                "total_tasks": 0,
                "completed": 0,
                "completion_rate": 0,
                "avg_accuracy": 1.0,
                "streak": 0,
            }

        completed = sum(1 for h in history if h.get("actualTime"))
        total = len(history)
        accuracies = [
            h["actualTime"] / h["aiTime"]
            for h in history
            if h.get("actualTime") and h.get("aiTime", 0) > 0
        ]
        avg_acc = round(sum(accuracies) / len(accuracies), 2) if accuracies else 1.0

        return {
            "total_tasks": total,
            "completed": completed,
            "completion_rate": round((completed / total) * 100, 1) if total else 0,
            "avg_accuracy": avg_acc,
            "streak": self.context.streak,
        }

    async def _compute_accuracy(self) -> Dict[str, float]:
        records = self.context.task_history
        if not records:
            return {"easy": 1.0, "medium": 1.0, "hard": 1.0}

        buckets: Dict[str, List[float]] = {"easy": [], "medium": [], "hard": []}
        for r in records:
            if r.get("actualTime") and r.get("aiTime", 0) > 0:
                diff = r.get("difficulty", "medium")
                if diff in buckets:
                    buckets[diff].append(r["actualTime"] / r["aiTime"])

        return {
            k: round(sum(v) / len(v), 2) if v else 1.0
            for k, v in buckets.items()
        }

    async def _calculate_streak(self) -> int:
        try:
            cursor = self.db.daily_plans.find(
                {"user_id": self.user_id}
            ).sort("date", -1).limit(30)
            plans = await cursor.to_list(30)

            streak = 0
            today = datetime.now().date()

            for plan in plans:
                try:
                    plan_date = datetime.fromisoformat(plan["date"]).date()
                except (ValueError, TypeError):
                    continue

                if plan_date == today - timedelta(days=streak):
                    has_tasks = (
                        plan.get("completed_tasks", 0) > 0
                        or len(plan.get("optimizedTasks", [])) > 0
                        or len(plan.get("schedule", [])) > 0
                    )
                    if has_tasks:
                        streak += 1
                    else:
                        break
                else:
                    break

            return streak
        except Exception as e:
            logger.error(f"_calculate_streak error: {e}")
            return 0

    # ── Helper methods ─────────────────────────────────────────────────────────

    def _parse_time(self, time_str: str) -> Optional[float]:
        if not time_str:
            return None
        time_str = time_str.lower().strip()
        match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        return hour + (minute / 60)

    def _find_free_gaps(
        self,
        schedule: List[Dict],
        day_start: float = 9.0,
        day_end: float = 22.0,
    ) -> List[Dict]:
        if not schedule:
            return [{
                "start": self._fmt_hour(day_start),
                "end": self._fmt_hour(day_end),
                "duration": round(day_end - day_start, 1)
            }]

        gaps = []
        current_time = day_start

        sorted_schedule = sorted(
            schedule,
            key=lambda x: self._parse_time(x.get("start_time", "9:00 AM")) or 9.0
        )

        for item in sorted_schedule:
            if item.get("type") == "break":
                continue

            start_hour = self._parse_time(item.get("start_time", "9:00 AM"))
            if start_hour is None:
                continue

            if start_hour > current_time + 0.25:
                gap_duration = start_hour - current_time
                if gap_duration >= 0.5:
                    gaps.append({
                        "start": self._fmt_hour(current_time),
                        "end": self._fmt_hour(start_hour),
                        "duration": round(gap_duration, 1)
                    })

            end_hour = self._parse_time(item.get("end_time", "10:00 AM"))
            current_time = max(current_time, end_hour or current_time)

        if day_end > current_time + 0.25:
            gaps.append({
                "start": self._fmt_hour(current_time),
                "end": self._fmt_hour(day_end),
                "duration": round(day_end - current_time, 1)
            })

        return gaps

    def _fmt_hour(self, hour: Optional[float]) -> str:
        if hour is None:
            return ""
        h = int(hour)
        m = int((hour - h) * 60)
        period = "AM" if h < 12 else "PM"
        display = h % 12 or 12
        return f"{display}:{m:02d} {period}"

    def _format_schedule_items(self, items: List[Dict]) -> List[Dict]:
        formatted = []
        for item in items:
            start = item.get("start_time")
            end = item.get("end_time")

            start_str = start if isinstance(start, str) else self._fmt_hour(start)
            end_str = end if isinstance(end, str) else self._fmt_hour(end)

            formatted.append({
                "task": item.get("task", item.get("name", "")),
                "start_time": start_str,
                "end_time": end_str,
                "duration": round(item.get("duration", 1.0), 1),
                "priority": item.get("priority", "medium"),
                "difficulty": item.get("difficulty", "medium"),
                "category": item.get("category", "general"),
                "focus_score": item.get("focus_score", 5),
                "energy_score": item.get("energy_score", 0.5),
                "time": f"{start_str} - {end_str}",
                "type": item.get("type", "task"),
                "is_existing": item.get("is_existing", False),
            })
        return formatted

    def _fallback_schedule(self, tasks: List[Dict]) -> List[Dict]:
        schedule = []
        current = 9.0

        fixed_tasks = [t for t in tasks if t.get("start_time")]
        flexible_tasks = [t for t in tasks if not t.get("start_time")]

        for task in fixed_tasks:
            start = task.get("start_time", current)
            if isinstance(start, str):
                start = self._parse_time(start) or current
            dur = task.get("duration", 1.0)
            schedule.append({
                "task": task.get("name", task.get("task", "")),
                "start_time": start,
                "end_time": start + dur,
                "duration": dur,
                "priority": task.get("priority", "medium"),
                "difficulty": task.get("difficulty", "medium"),
                "is_existing": task.get("is_existing", False)
            })
            current = max(current, start + dur + 0.25)

        for task in flexible_tasks:
            dur = task.get("duration", 1.0)
            schedule.append({
                "task": task.get("name", task.get("task", "")),
                "start_time": current,
                "end_time": current + dur,
                "duration": dur,
                "priority": task.get("priority", "medium"),
                "difficulty": task.get("difficulty", "medium"),
                "is_existing": task.get("is_existing", False)
            })
            current += dur + 0.25

        return schedule