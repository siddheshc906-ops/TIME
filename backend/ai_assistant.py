# backend/ai_assistant.py
from datetime import datetime, timedelta
import re
from typing import List, Dict, Any, Optional
from enum import Enum
import random
import openai
import os
import json
import logging

# Import new AI components
from ai.core import TimevoraAI
from ai.scheduler import IntelligentScheduler
from ai.analyzer import ProductivityAnalyzer
from ai.learner import AdaptiveLearner
from ai.recommender import TaskRecommender

logger = logging.getLogger(__name__)

class IntentType(str, Enum):
    CREATE_SCHEDULE = "create_schedule"
    ADD_TASK = "add_task"            # add task(s) to existing schedule
    MODIFY_SCHEDULE = "modify_schedule"
    ASK_QUESTION = "ask_question"
    GET_ADVICE = "get_advice"
    ANALYZE_HABITS = "analyze_habits"
    CHECK_PROGRESS = "check_progress"
    OPTIMIZE_SCHEDULE = "optimize_schedule"
    GENERAL_CHAT = "general_chat"

class TaskComplexity(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class ExtractedTask:
    def __init__(self, name, duration=1.0, priority="medium", 
                 complexity=TaskComplexity.MEDIUM, 
                 start_time=None, end_time=None):
        self.name = name
        self.duration = duration
        self.priority = priority
        self.complexity = complexity
        self.start_time = start_time
        self.end_time = end_time



# ── Module-level task extraction helpers ───────────────────────────────────────

_FILLER_RE = re.compile(
    r"^\s*(?:and|also|then|plus|additionally|"
    r"i\s+(?:have\s+to|need\s+to|want\s+to|should|will|am\s+going\s+to)|"
    r"to\s+(?=\w))+\s*",
    re.IGNORECASE,
)


def _strip_filler(name: str) -> str:
    """Strip leading filler words and capitalise the result."""
    cleaned = _FILLER_RE.sub("", name).strip(" ,.-")
    return (cleaned[0].upper() + cleaned[1:]) if cleaned else ""


def _regex_extract_tasks(message: str) -> List[Dict]:
    """
    Robust regex task extractor.
    Splits on natural connectors FIRST, then extracts name + duration from each
    clean segment — so 'and X' can never appear as a task name.
    """
    # Strip common preamble so it doesn't become a task name
    preamble_re = re.compile(
        r"^\s*(?:i\s+(?:have|need|want)\s+to|please|can\s+you|help\s+me|"
        r"today\s+i\s+(?:have|need|want)\s+to|set\s+up\s+my\s+(?:day|schedule)|"
        r"create\s+(?:a\s+)?schedule\s+for\s+(?:me\s+)?(?:to\s+)?|"
        r"plan\s+my\s+day\s*[:\-]?\s*)",
        re.IGNORECASE,
    )
    cleaned_msg = preamble_re.sub("", message).strip()

    # Split on task boundaries
    segments = re.split(
        r"\s*,\s*(?:and\s+)?|\s+and\s+|\s*;\s*|\s+then\s+",
        cleaned_msg,
        flags=re.IGNORECASE,
    )

    tasks: List[Dict] = []
    dur_re = re.compile(
        r"(?:for\s+)?(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|minutes?|mins?|min\b)",
        re.IGNORECASE,
    )

    for seg in segments:
        seg = seg.strip()
        if not seg or len(seg) < 2:
            continue
        seg = _strip_filler(seg)
        if not seg:
            continue

        dur_match = dur_re.search(seg)
        if dur_match:
            raw_dur = float(dur_match.group(1))
            unit = dur_match.group(2).lower()
            duration = raw_dur / 60 if "min" in unit else raw_dur
            name = dur_re.sub("", seg).strip(" ,.-")
            name = re.sub(r"\s+for\s*$", "", name, flags=re.IGNORECASE).strip()
        else:
            duration = 1.0
            name = seg

        name = _strip_filler(name)
        if not name or len(name) < 2:
            continue

        tasks.append({
            "name": name,
            "duration": round(duration, 1),
            "priority": "medium",
        })

    return tasks


class AIAssistant:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        
        # Initialize new AI components
        self.timevora_ai = TimevoraAI(user_id, db)
        self.scheduler = IntelligentScheduler(user_id, db)
        self.analyzer = ProductivityAnalyzer(user_id, db)
        self.learner = AdaptiveLearner(user_id, db)
        self.recommender = TaskRecommender(user_id, db)
        
        # Initialize NLP processor
        self.nlp = None
        try:
            from ai.nlp import NLProcessor
            self.nlp = NLProcessor()
            logger.info("NLP Processor loaded successfully")
        except ImportError as e:
            logger.warning(f"NLP processor not available: {e}")
        
        # Initialize OpenAI client
        openai.api_key = os.getenv("OPENAI_API_KEY")
    
    async def process_message(self, message: str) -> Dict[str, Any]:
        """
        Main entry point.
        Intent detection is now smart enough to handle natural messages like:
          "meditation for 30 minutes"  → ADD_TASK
          "physics 2hr and maths 1hr"  → CREATE_SCHEDULE
          "plan my day"                → CREATE_SCHEDULE
          "i have college 9 to 4"      → MODIFY_SCHEDULE (save routine)
        """
        try:
            from datetime import datetime as _dt
            today_str = _dt.now().date().isoformat()

            intent = await self._detect_intent(message)
            logger.info(f"Detected intent: {intent} for message: '{message[:60]}'")

            # ── Check for daily check-in reply first ──────────────────────────
            # If there are pending tasks saved from a previous check-in, and
            # the user is now describing their day, schedule those tasks.
            pending_doc = None
            try:
                pending_doc = await self.db.user_pending_context.find_one(
                    {"user_id": self.user_id, "date": today_str}
                )
            except Exception:
                pass

            if pending_doc:
                _checkin_reply_phrases = [
                    "free all day", "just schedule it", "no college",
                    "no school", "college from", "school from", "work from",
                    "busy from", "free from", "free after", "i'm free", "i am free",
                    "free all", "whole day free",
                ]
                if any(p in message.lower() for p in _checkin_reply_phrases):
                    return await self._get_pending_tasks_and_schedule(message)

            # ── Route by intent ───────────────────────────────────────────────
            if intent == IntentType.ADD_TASK:
                return await self._handle_add_task(message)

            if intent == IntentType.MODIFY_SCHEDULE:
                return await self._parse_and_save_routine(message)

            if intent == IntentType.CREATE_SCHEDULE:
                return await self._create_schedule_with_nlp(message)

            # All other intents → enhanced rule-based
            return await self._enhanced_rule_based_processing(message)

        except Exception as e:
            logger.error(f"process_message error: {e}", exc_info=True)
            return {
                "type":    "chat",
                "message": "I ran into an issue. Please try again!",
                "suggestions": [
                    "Study Physics 2 hours and Maths 1 hour",
                    "Add meditation for 30 minutes",
                    "Give me productivity tips",
                ],
            }
    
    async def _create_schedule_with_nlp(self, message: str) -> Dict[str, Any]:
        """Create schedule using NLP for task extraction"""
        
        tasks = []
        
        # Try NLP extraction first
        if self.nlp:
            try:
                extracted = self.nlp.extract_tasks(message)
                if extracted:
                    for task in extracted:
                        name = _strip_filler(task.get("name", "").strip()) or task.get("name", "")
                        tasks.append({
                            "name": name,
                            "duration": task.get("duration", 1.0),
                            "priority": task.get("priority", "medium"),
                            "difficulty": task.get("difficulty", "medium")
                        })
                    logger.info(f"NLP extracted {len(tasks)} tasks: {[t['name'] for t in tasks]}")
            except Exception as e:
                logger.error(f"NLP extraction error: {e}")
        
        # Fallback to manual extraction if NLP fails
        if not tasks:
            tasks = await self._manual_extract_tasks(message)
            logger.info(f"Manual extraction found {len(tasks)} tasks")
        
        if not tasks:
            return {
                "type": "clarification",
                "message": "I'd love to help! Try: 'Study Physics 2 hours, Maths 1 hour, revision at 3 PM'"
            }

        today_str = datetime.now().date().isoformat()

        # ── Daily check-in: ask what today looks like before scheduling ──────
        # Only ask once per day, and only if we have no date-specific context
        should_ask = await self._should_ask_daily_checkin()
        if should_ask:
            return await self._daily_checkin_response(message, tasks)

        # Use day context + existing schedule to find genuinely free slots
        day_ctx = await self._get_day_context(today_str)
        existing_plan = await self.db.daily_plans.find_one(
            {"user_id": self.user_id, "date": today_str}
        )
        existing_schedule = (existing_plan or {}).get("schedule", [])

        schedule = self._find_free_slots(day_ctx, existing_schedule, tasks)

        # Generate insights
        insights = []
        total_hours = sum(t.get("duration", 1) for t in tasks)
        source = day_ctx.get("source", "")

        if total_hours > 8:
            insights.append("⚠️ This is a packed day! Make sure to take breaks.")
        elif total_hours < 4:
            insights.append("✨ You have a light day. Great for deep work!")

        if "smart_default" in source:
            insights.append(
                "💡 I scheduled around typical college hours. "
                "Tell me your actual day next time for a perfect fit!"
            )
        elif "learned" in source:
            insights.append(
                f"🧠 Scheduled based on your usual {day_ctx.get('weekday_name', 'day')} pattern!"
            )
        elif "saved_routine" in source:
            insights.append("📅 Scheduled around your saved daily routine!")

        return {
            "type":        "schedule",
            "message":     f"✅ Created schedule with {len(tasks)} tasks!",
            "tasks_found": [t.get("name", "Task") for t in tasks],
            "schedule":    schedule,
            "insights":    insights if insights else ["💡 Remember to take short breaks between tasks"],
        }
    
    async def _manual_extract_tasks(self, message: str) -> List[Dict]:
        """
        Smart task extractor — tries Gemini first for natural language understanding,
        then falls back to a clean regex pipeline that never produces 'and X' artifacts.
        """
        import os as _os, json as _json

        # ── 1. Try Gemini for smart extraction ───────────────────────────────
        GEMINI_API_KEY = _os.getenv("GEMINI_API_KEY")
        if GEMINI_API_KEY:
            try:
                from google import genai as _genai
                from google.genai import types as _types

                client = _genai.Client(api_key=GEMINI_API_KEY)
                prompt = f"""Extract ALL tasks from the user's message. Return ONLY a JSON array — no extra text, no markdown fences.

Each item must have:
  "name":     clean task name (strip any leading filler: and, also, then, i have to, i need to, i want to, i should, i will, to)
  "duration": hours as a number (default 1.0 if not mentioned; convert minutes to hours e.g. 30 min → 0.5)
  "priority": "high" | "medium" | "low"

Rules:
- Capitalise the first letter of each name.
- Never include connector words like "and" or "also" in the name.
- If no duration is mentioned use 1.0.

Message: "{message}"

Example output:
[{{"name": "Read books", "duration": 1.0, "priority": "medium"}}, {{"name": "Practice DSA", "duration": 3.0, "priority": "high"}}]"""

                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=_types.GenerateContentConfig(
                        max_output_tokens=400,
                        temperature=0.2,
                    ),
                )
                raw = response.text.strip()
                if raw.startswith("```"):
                    parts = raw.split("```")
                    raw = parts[1] if len(parts) > 1 else raw
                    if raw.startswith("json"):
                        raw = raw[4:]
                raw = raw.strip()

                extracted = _json.loads(raw)
                if isinstance(extracted, list) and extracted:
                    tasks = []
                    for item in extracted:
                        name = _strip_filler(item.get("name", "").strip())
                        if name:
                            tasks.append({
                                "name": name,
                                "duration": round(float(item.get("duration", 1.0)), 1),
                                "priority": item.get("priority", "medium"),
                            })
                    if tasks:
                        logger.info(f"Gemini extracted {len(tasks)} tasks: {[t['name'] for t in tasks]}")
                        return tasks
            except Exception as e:
                logger.warning(f"Gemini task extraction failed, using regex fallback: {e}")

        # ── 2. Clean regex fallback ───────────────────────────────────────────
        return _regex_extract_tasks(message)
    
    def _dec_to_str(self, decimal_h: float) -> str:
        """Convert decimal hour (14.25) to '2:15 PM' string."""
        h  = int(decimal_h)
        mn = round((decimal_h - h) * 60)
        if mn == 60:          # handle rounding edge case
            h += 1; mn = 0
        period = "AM" if h < 12 else "PM"
        dh = h % 12 or 12
        return f"{dh}:{mn:02d} {period}"

    def _create_schedule_from_tasks(self, tasks: List[Dict], start_at: float = 9.0) -> List[Dict]:
        """
        Build a sequential schedule from tasks.
        Tasks are laid out one after another with a 15-min buffer between each.
        Returns numeric start_time / end_time fields so the frontend never has
        to parse time strings — it can use them directly for merge-offset math.
        """
        schedule = []
        cursor = start_at  # decimal hours, e.g. 9.0 = 9:00 AM

        for task in tasks:
            duration   = round(float(task.get("duration", 1.0)), 2)
            start_dec  = cursor
            end_dec    = cursor + duration
            start_str  = self._dec_to_str(start_dec)
            end_str    = self._dec_to_str(end_dec)

            schedule.append({
                "task":       task.get("name", "Task"),
                "start_time": start_dec,   # ← numeric for easy frontend math
                "end_time":   end_dec,     # ← numeric
                "duration":   duration,
                "priority":   task.get("priority", "medium"),
                "difficulty": task.get("difficulty", "medium"),
                "category":   task.get("category", "general"),
                "time":       f"{start_str} - {end_str}",
                # These string fields are kept for any legacy consumers
                "start_time_str": start_str,
                "end_time_str":   end_str,
            })

            cursor = end_dec + 0.25  # 15-min buffer before next task

        return schedule
    
    async def _should_use_advanced_ai(self, message: str) -> bool:
        """Determine if we should use advanced AI processing"""
        
        # Use advanced AI for complex requests
        complex_patterns = [
            r'optimize',
            r'analyze.*pattern',
            r'productivity.*profile',
            r'recommend',
            r'suggest',
            r'improve',
            r'learn',
            r'trend',
            r'peak.*hour',
            r'energy.*pattern',
            r'focus.*score'
        ]
        
        message_lower = message.lower()
        
        for pattern in complex_patterns:
            if re.search(pattern, message_lower):
                logger.info(f"Complex pattern detected: {pattern}")
                return True
        
        # Check if we have enough data for ML
        try:
            history_count = await self.db.task_history.count_documents({"user_id": self.user_id})
            if history_count > 20:
                # Check if message is about analysis or optimization
                analysis_keywords = ['analyze', 'pattern', 'habit', 'trend', 'progress', 'performance']
                if any(keyword in message_lower for keyword in analysis_keywords):
                    return True
        except Exception as e:
            logger.error(f"Error checking history count: {e}")
        
        return False
    
    def _create_ai_prompt(self, intent: IntentType, context: str) -> str:
        """Create AI prompt based on intent"""
        
        base_prompt = f"""You are Timevora AI, an elite productivity planner and cognitive performance coach.
Current user context: {context}

"""
        
        if intent == IntentType.CREATE_SCHEDULE:
            return base_prompt + """The user wants to create a schedule. Extract tasks with durations and times.
Respond with a JSON object in this exact format:
{
    "type": "schedule",
    "message": "I've created your schedule!",
    "tasks_found": ["task1", "task2", "task3"],
    "schedule": [
        {"time": "9:00 AM - 11:00 AM", "task": "Task description", "priority": "medium", "duration": 2},
        {"time": "11:30 AM - 12:30 PM", "task": "Another task", "priority": "high", "duration": 1}
    ],
    "insights": ["Tip 1", "Tip 2"]
}"""
        
        elif intent == IntentType.GET_ADVICE:
            return base_prompt + """The user wants productivity advice. Provide personalized tips.
Respond with:
{
    "type": "advice",
    "message": "Here are my top tips",
    "advice_points": ["Tip 1", "Tip 2", "Tip 3"],
    "insight": "Personalized insight"
}"""
        
        elif intent == IntentType.ASK_QUESTION:
            return base_prompt + """Answer the user's question about productivity.
Respond with:
{
    "type": "answer",
    "message": "Detailed answer",
    "follow_up": "Follow-up question",
    "suggestions": ["Related 1", "Related 2"]
}"""
        
        elif intent == IntentType.ANALYZE_HABITS:
            return base_prompt + """Analyze the user's habits based on context.
Respond with:
{
    "type": "analysis",
    "message": "Analysis summary",
    "stats": {
        "completion_rate": "XX%",
        "total_tasks": X,
        "completed": X,
        "avg_task_duration": "X.X hours",
        "streak": X
    },
    "insight": "Personalized insight",
    "recommendations": ["Rec 1", "Rec 2"]
}"""
        
        elif intent == IntentType.CHECK_PROGRESS:
            return base_prompt + """Check the user's progress and provide a summary.
Respond with:
{
    "type": "progress",
    "message": "Progress summary",
    "stats": {
        "productivity_score": XX,
        "streak": X,
        "total_tasks_completed": X
    },
    "trend": "improving/stable/declining"
}"""
        
        elif intent == IntentType.OPTIMIZE_SCHEDULE:
            return base_prompt + """Optimize the user's current schedule for better productivity.
Respond with:
{
    "type": "schedule",
    "message": "I've optimized your schedule!",
    "schedule": [
        {"time": "9:00 AM - 11:00 AM", "task": "Task description"},
        {"time": "11:30 AM - 12:30 PM", "task": "Another task"}
    ],
    "insights": ["Optimization tip 1", "Optimization tip 2"],
    "optimized": true
}"""
        
        else:
            return base_prompt + """Have a friendly conversation about productivity.
Respond with:
{
    "type": "chat",
    "message": "Friendly response",
    "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3"]
}"""
    
    async def _enhanced_rule_based_processing(self, message: str) -> Dict[str, Any]:
        """Enhanced rule-based processing with new features"""
        
        intent = await self._detect_intent(message)
        logger.info(f"Detected intent: {intent}")
        
        if intent == IntentType.ADD_TASK:
            return await self._handle_add_task(message)
        elif intent == IntentType.MODIFY_SCHEDULE:
            return await self._parse_and_save_routine(message)
        elif intent == IntentType.CREATE_SCHEDULE:
            return await self._enhanced_schedule_creation(message)
        elif intent == IntentType.OPTIMIZE_SCHEDULE:
            return await self._handle_schedule_optimization(message)
        elif intent == IntentType.GET_ADVICE:
            return await self._enhanced_advice_request()
        elif intent == IntentType.ASK_QUESTION:
            return await self._enhanced_question(message)
        elif intent == IntentType.ANALYZE_HABITS:
            return await self._enhanced_habit_analysis()
        elif intent == IntentType.CHECK_PROGRESS:
            return await self._handle_progress_check()
        else:
            return await self._enhanced_general_chat(message)
    
    async def _enhanced_schedule_creation(self, message: str) -> Dict[str, Any]:
        """Enhanced schedule creation using new scheduler"""
        
        # Use your existing task extraction
        tasks = await self._extract_tasks_naturally(message)
        
        if not tasks:
            return {
                "type": "clarification",
                "message": "I'd love to help you plan! Could you tell me what tasks you need to do? For example: 'Study Physics 2 hours, Maths 1 hour, revision at 3 PM' or 'I have college from 8:30 AM to 4 PM'"
            }
        
        # Convert to format expected by new scheduler
        scheduler_tasks = []
        for task in tasks:
            scheduler_tasks.append({
                "name": task.name,
                "duration": task.duration,
                "priority": task.priority,
                "difficulty": task.complexity.value,
                "start_time": task.start_time,
                "end_time": task.end_time
            })
        
        # Use new intelligent scheduler
        try:
            schedule_result = await self.scheduler.create_optimal_schedule(scheduler_tasks)
            
            # Format for your frontend
            formatted_schedule = []
            for item in schedule_result["schedule"]:
                formatted_schedule.append({
                    "task": item["task"],
                    "start_time": self._format_time(item["start_time"]),
                    "end_time": self._format_time(item["end_time"]),
                    "duration": round(item["duration"], 1),
                    "priority": item.get("priority", "medium"),
                    "time": f"{self._format_time(item['start_time'])} - {self._format_time(item['end_time'])}"
                })
        except Exception as e:
            logger.error(f"Error using intelligent scheduler: {e}")
            # Fall back to your original schedule generation
            formatted_schedule = await self._generate_smart_schedule(tasks)
            schedule_result = {"insights": []}
        
        # Get user's accuracy for insights
        accuracy = await self._get_user_accuracy()
        
        # Generate enhanced insights
        insights = schedule_result.get("insights", [])
        
        # Add basic insights if none from scheduler
        if not insights:
            total_hours = sum(t.duration for t in tasks)
            if total_hours > 8:
                insights.append("⚠️ This is a packed day! Make sure to take breaks.")
            elif total_hours < 4:
                insights.append("✨ You have a light day. Great for deep work!")
            
            high_priority = sum(1 for t in tasks if t.priority == 'high')
            if high_priority > 2:
                insights.append("🎯 Multiple high-priority tasks. Start with the most important one.")
            
            has_fixed_times = any(t.start_time is not None for t in tasks)
            if has_fixed_times:
                insights.append("⏰ I've respected your specific time requests for certain tasks.")
        
        # Add accuracy-based insight if available
        if accuracy:
            if accuracy.get('hard', 1) > 1.2:
                insights.append("📊 You tend to underestimate hard tasks - I've added extra buffer.")
            elif accuracy.get('easy', 1) < 0.8:
                insights.append("⚡ You're faster at easy tasks than you think!")
        
        return {
            "type": "schedule",
            "message": f"✅ I've created your schedule with {len(tasks)} tasks!",
            "tasks_found": [t.name for t in tasks],
            "schedule": formatted_schedule,
            "insights": insights if insights else ["💡 Remember to take short breaks between tasks"],
            "metrics": {
                "focus_score": round(schedule_result.get("total_focus_time", 0), 1),
                "energy_alignment": round(schedule_result.get("energy_aligned", 0), 2)
            } if schedule_result.get("total_focus_time") else None
        }
    
    async def _should_ask_daily_checkin(self) -> bool:
        """
        Returns True if we should ask the user about today's schedule.
        We ask ONLY when ALL of these are true:
          - No check-in has been done today yet
          - No date-specific override exists for today
          - No general saved routine exists
          - Today is a weekday (weekends are assumed free)
        This avoids interrupting the user every time they add a single task.
        """
        from datetime import datetime as _dt
        today_dt  = _dt.now()
        today_str = today_dt.date().isoformat()
        weekday   = today_dt.weekday()

        # Never ask on weekends — assume free day
        if weekday >= 5:
            return False

        try:
            # Already asked today?
            asked = await self.db.user_day_context.find_one(
                {"user_id": self.user_id, "checkin_date": today_str}
            )
            if asked:
                return False

            # Date-specific override already set?
            override = await self.db.user_day_context.find_one(
                {"user_id": self.user_id, "date_override": today_str}
            )
            if override:
                return False

            # General saved routine already set? (means user told us once)
            general = await self.db.user_day_context.find_one(
                {"user_id": self.user_id, "date_override": {"$exists": False},
                 "has_custom": True}
            )
            if general:
                return False

            return True
        except Exception:
            return False

    async def _mark_checkin_done(self, today_str: str) -> None:
        """Record that we've done the daily check-in so we don't ask again."""
        try:
            await self.db.user_day_context.update_one(
                {"user_id": self.user_id, "checkin_date": today_str},
                {"$set": {"user_id": self.user_id, "checkin_date": today_str}},
                upsert=True,
            )
        except Exception:
            pass

    async def _daily_checkin_response(self, original_message: str,
                                       tasks: List[Dict]) -> Dict[str, Any]:
        """
        Instead of scheduling immediately, ask the user what today looks like
        and store the tasks temporarily so we can schedule after they reply.
        """
        from datetime import datetime as _dt
        today_str   = _dt.now().date().isoformat()
        ctx         = await self._get_day_context(today_str)
        weekday     = ctx.get("weekday_name", "today")
        source      = ctx.get("source", "")
        is_assumed  = "smart_default" in source
        is_learned  = "learned" in source

        # Mark that we asked today so we don't loop
        await self._mark_checkin_done(today_str)

        # Save pending tasks so next message can use them
        try:
            await self.db.user_pending_context.update_one(
                {"user_id": self.user_id},
                {"$set": {
                    "user_id":       self.user_id,
                    "pending_tasks": tasks,
                    "original_msg":  original_message,
                    "date":          today_str,
                }},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"Could not save pending tasks: {e}")

        if is_learned:
            assumed_start = self._dec_to_str(ctx.get("day_start", 16.0))
            note = (
                f"Based on your past {weekday}s I'll assume you're free from "
                f"around **{assumed_start}** — but is that right today?"
            )
        elif is_assumed:
            note = (
                f"Since it's {weekday} I've assumed you might have college "
                f"until around 4 PM — but every day is different!"
            )
        else:
            note = f"Just checking since every {weekday} can be different!"

        task_names = [t.get("name", "task") for t in tasks]
        task_list  = ", ".join(task_names)

        newline = "\n"
        checkin_msg = (
            f"Got it \u2014 I'll schedule **{task_list}** for you. "
            + note
            + newline + newline
            + f"**What does your {weekday} look like today?**" + newline
            + "Just tell me in one line, e.g.:" + newline
            + "\u2022 'College 9 AM to 2 PM, free after that'" + newline
            + "\u2022 'Free all day'" + newline
            + "\u2022 'Work from 10 to 6, dinner at 7'" + newline + newline
            + "Or say **'just schedule it'** and I'll use my best guess!"
        )
        return {
            "type":    "checkin",
            "message": checkin_msg,
            "suggestions": [
                "Free all day",
                "College 9 AM to 4 PM",
                "Just schedule it",
            ],
            "pending_tasks": task_names,
        }

    async def _get_pending_tasks_and_schedule(self, message: str) -> Dict[str, Any]:
        """
        Called when user replies to the daily check-in.
        Retrieves saved pending tasks, parses today's context from the reply,
        then schedules everything.
        """
        from datetime import datetime as _dt
        today_str = _dt.now().date().isoformat()

        try:
            pending_doc = await self.db.user_pending_context.find_one(
                {"user_id": self.user_id, "date": today_str}
            )
        except Exception:
            pending_doc = None

        # Parse context from the reply
        msg_lower = message.lower()
        if "free all day" in msg_lower or "just schedule it" in msg_lower or "no college" in msg_lower:
            # Use weekend-style defaults — free all day
            ctx = {
                "wake_up": 7.0, "day_start": 9.0,
                "lunch_start": 13.0, "lunch_end": 14.0,
                "dinner_start": 19.0, "day_end": 23.0,
                "blocked_slots": [], "has_custom": True,
                "date_override": today_str,
            }
        else:
            # Parse routine from their reply and save as date-specific override
            routine_response = await self._parse_and_save_routine(message)
            ctx = await self._get_day_context(today_str)
            ctx["date_override"] = today_str

        # Save as today's override
        await self._save_day_context({**ctx, "date_override": today_str})

        # Now schedule the pending tasks
        tasks = (pending_doc or {}).get("pending_tasks", [])
        if not tasks:
            return {
                "type":    "chat",
                "message": "All set! Now tell me what tasks you want to schedule today.",
            }

        existing_plan = await self.db.daily_plans.find_one(
            {"user_id": self.user_id, "date": today_str}
        )
        existing_schedule = (existing_plan or {}).get("schedule", [])
        schedule = self._find_free_slots(ctx, existing_schedule, tasks)

        task_names = [t.get("name", "task") for t in tasks]
        return {
            "type":        "schedule",
            "message":     f"✅ Scheduled {len(tasks)} task(s) in your free slots today!",
            "tasks_found": task_names,
            "schedule":    schedule,
            "insights":    [
                f"📅 Scheduled around your day — tasks placed in your free time only!"
            ],
        }

    async def _parse_and_save_routine(self, message: str) -> Dict[str, Any]:
        """
        Parse natural language routine descriptions and save them as day context.
        Examples:
          "I have college 9 AM to 4 PM, lunch at 1 PM"
          "I wake up at 7, work from 10 AM to 6 PM"
          "My day starts at 8:30 AM"
        """
        import re

        def parse_time(s: str) -> Optional[float]:
            """Parse a time string to decimal hour."""
            if not s:
                return None
            s = s.strip().lower()
            m = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', s)
            if not m:
                return None
            h = int(m[1])
            mn = int(m[2]) if m.group(2) else 0
            period = m.group(3)
            if period == 'pm' and h != 12:
                h += 12
            elif period == 'am' and h == 12:
                h = 0
            elif not period and h < 7:
                h += 12  # assume PM for ambiguous afternoon hours
            return h + mn / 60

        msg = message.lower()
        ctx = await self._get_day_context()

        # Parse blocked slots (college, work, school, meetings)
        blocked_patterns = [
            r'(?:college|school|work|class|office|meeting|gym|coaching)\s+(?:from\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-|until|–)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
            r'(?:busy|blocked|not available|unavailable)\s+(?:from\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-|until)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
        ]
        blocked_slots = list(ctx.get("blocked_slots", []))
        labels = ["college", "school", "work", "class", "office", "meeting", "gym", "coaching", "busy", "blocked"]

        for pattern in blocked_patterns:
            for match in re.finditer(pattern, msg):
                s = parse_time(match.group(1))
                e = parse_time(match.group(2))
                if s is not None and e is not None and e > s:
                    # Find label
                    label = next((l for l in labels if l in match.group(0)), "blocked")
                    blocked_slots.append({"start": s, "end": e, "label": label})

        if blocked_slots:
            ctx["blocked_slots"] = blocked_slots
            # First available free slot after all blocked times
            all_ends = [slot["end"] for slot in blocked_slots]
            ctx["day_start"] = max(all_ends) + 0.25 if all_ends else ctx.get("day_start", 9.0)

        # Parse wake up time
        m = re.search(r'wake\s+up\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', msg)
        if m:
            v = parse_time(m.group(1))
            if v:
                ctx["wake_up"] = v
                ctx["day_start"] = max(ctx.get("day_start", 9.0), v + 1.0)

        # Parse explicit day start
        m = re.search(r'(?:day starts?|free from|available from|start(?:s)? at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', msg)
        if m:
            v = parse_time(m.group(1))
            if v:
                ctx["day_start"] = v

        # Parse lunch
        m = re.search(r'lunch\s+(?:at|from)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', msg)
        if m:
            v = parse_time(m.group(1))
            if v:
                ctx["lunch_start"] = v
                ctx["lunch_end"]   = v + 1.0

        # Parse dinner
        m = re.search(r'dinner\s+(?:at|from)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', msg)
        if m:
            v = parse_time(m.group(1))
            if v:
                ctx["dinner_start"] = v

        # Parse sleep / day end
        m = re.search(r'(?:sleep|bed|day ends?|stop at|finish at)\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', msg)
        if m:
            v = parse_time(m.group(1))
            if v:
                ctx["day_end"] = v

        await self._save_day_context(ctx)

        # Build a human-readable summary
        summary_parts = []
        if blocked_slots:
            for slot in blocked_slots:
                summary_parts.append(
                    f"• {slot['label'].title()}: {self._dec_to_str(slot['start'])} – {self._dec_to_str(slot['end'])}"
                )
        if ctx.get("lunch_start"):
            summary_parts.append(f"• Lunch: {self._dec_to_str(ctx['lunch_start'])} – {self._dec_to_str(ctx['lunch_end'])}")
        summary_parts.append(f"• Free for tasks: from {self._dec_to_str(ctx.get('day_start', 9.0))}")
        summary_parts.append(f"• Day ends: {self._dec_to_str(ctx.get('day_end', 22.0))}")

        return {
            "type":    "chat",
            "message": (
                "✅ Got it! I've saved your daily routine. From now on I'll schedule your tasks "
                "around your real day:\n\n"
                + "\n".join(summary_parts)
                + "\n\nJust tell me what tasks you want to do and I'll fit them into your free slots!"
            ),
            "suggestions": [
                "Add meditation for 30 minutes",
                "I need to study Physics for 2 hours",
                "Plan my remaining tasks for today",
            ],
        }

        # ── Day Context: store & retrieve the user's daily structure ─────────────

    async def _get_day_context(self, target_date: str = None) -> Dict:
        """
        Get the day context for a specific date (or today).

        Priority order:
          1. A date-specific override the user set for this exact date
          2. A weekly pattern for this day-of-week learned from history
          3. The user's saved general routine
          4. Smart student defaults (avoid 9 AM–4 PM typical college hours)
        """
        from datetime import datetime as _dt
        import calendar as _cal

        today_str  = target_date or _dt.now().date().isoformat()
        today_dt   = _dt.fromisoformat(today_str)
        weekday    = today_dt.weekday()          # 0=Mon … 6=Sun
        weekday_name = _cal.day_name[weekday]    # "Monday" etc.

        # ── 1. Date-specific override ─────────────────────────────────────────
        try:
            date_doc = await self.db.user_day_context.find_one(
                {"user_id": self.user_id, "date_override": today_str}
            )
            if date_doc:
                logger.info(f"Using date-specific context for {today_str}")
                return date_doc
        except Exception:
            pass

        # ── 2. Weekly pattern learned from history ───────────────────────────
        learned = await self._learn_weekly_pattern(weekday)

        # ── 3. User's saved general routine ──────────────────────────────────
        try:
            general_doc = await self.db.user_day_context.find_one(
                {"user_id": self.user_id, "date_override": {"$exists": False}}
            )
        except Exception:
            general_doc = None

        # ── 4. Smart student defaults ────────────────────────────────────────
        # Weekdays: assume college 9–4 (safe default for students)
        # Weekends: assume free day
        is_weekend = weekday >= 5
        if is_weekend:
            smart_defaults = {
                "wake_up":       8.0,
                "day_start":     9.0,   # free day — start at 9 AM
                "lunch_start":   13.0,
                "lunch_end":     14.0,
                "dinner_start":  19.0,
                "day_end":       23.0,
                "blocked_slots": [],
                "has_custom":    False,
                "source":        "smart_default_weekend",
                "weekday_name":  weekday_name,
            }
        else:
            smart_defaults = {
                "wake_up":       7.0,
                "day_start":     16.25,  # 4:15 PM — after typical college
                "lunch_start":   13.0,
                "lunch_end":     14.0,
                "dinner_start":  19.0,
                "day_end":       23.0,
                "blocked_slots": [
                    {"start": 9.0, "end": 16.0, "label": "college (assumed)"}
                ],
                "has_custom":    False,
                "source":        "smart_default_weekday",
                "weekday_name":  weekday_name,
            }

        # Merge: learned pattern overrides defaults; saved routine overrides learned
        base = {**smart_defaults}

        if learned:
            base.update(learned)
            base["source"] = f"learned_{weekday_name.lower()}"

        if general_doc:
            # User's saved routine overrides everything but keep weekday_name
            merged = {**base, **{k: v for k, v in general_doc.items()
                                  if k not in ("_id", "user_id", "date_override")}}
            merged["weekday_name"] = weekday_name
            merged["source"] = "saved_routine"
            return merged

        return base

    async def _learn_weekly_pattern(self, weekday: int) -> Optional[Dict]:
        """
        Look at the user's past daily_plans for this day-of-week and infer
        when they typically start tasks.  Requires at least 3 data points.
        """
        import calendar as _cal
        weekday_name = _cal.day_name[weekday]
        try:
            # Fetch plans from last 8 weeks
            from datetime import datetime as _dt, timedelta as _td
            cutoff = (_dt.now() - _td(weeks=8)).date().isoformat()
            cursor = self.db.daily_plans.find(
                {"user_id": self.user_id, "date": {"$gte": cutoff}}
            )
            plans = await cursor.to_list(56)

            same_weekday_plans = []
            for p in plans:
                try:
                    d = _dt.fromisoformat(p["date"])
                    if d.weekday() == weekday and p.get("schedule"):
                        same_weekday_plans.append(p)
                except Exception:
                    continue

            if len(same_weekday_plans) < 3:
                return None

            # Find average earliest task start time
            starts = []
            for p in same_weekday_plans:
                for item in p["schedule"]:
                    s = item.get("start_time")
                    if isinstance(s, (int, float)):
                        starts.append(float(s))
                        break   # only take the first task per day

            if not starts:
                return None

            avg_start = sum(starts) / len(starts)
            return {
                "day_start":  round(avg_start, 2),
                "has_custom": True,
            }

        except Exception as e:
            logger.debug(f"Weekly pattern learning error: {e}")
            return None

    async def _save_day_context(self, ctx: Dict) -> None:
        """Persist updated day context for this user."""
        try:
            ctx["user_id"] = self.user_id
            ctx["has_custom"] = True
            await self.db.user_day_context.update_one(
                {"user_id": self.user_id},
                {"$set": ctx},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"Could not save day context: {e}")

    def _find_free_slots(self, day_ctx: Dict, existing_schedule: List[Dict],
                         tasks: List[Dict]) -> List[Dict]:
        """
        Place tasks in genuinely free slots respecting:
          • user's day_start / day_end
          • lunch & dinner blocks
          • custom blocked_slots
          • existing scheduled items
        Returns a new schedule list with correct sequential times.
        """
        # Build a list of occupied intervals from the day context
        blocked = []

        lunch_s = day_ctx.get("lunch_start", 13.0)
        lunch_e = day_ctx.get("lunch_end",   14.0)
        if lunch_s < lunch_e:
            blocked.append((lunch_s, lunch_e))

        dinner_s = day_ctx.get("dinner_start", 19.0)
        dinner_e = dinner_s + 0.5  # 30-min dinner break
        if dinner_s < dinner_e:
            blocked.append((dinner_s, dinner_e))

        for slot in day_ctx.get("blocked_slots", []):
            blocked.append((slot["start"], slot["end"]))

        # Add existing scheduled tasks
        for item in existing_schedule:
            s = item.get("start_time")
            e = item.get("end_time")
            if isinstance(s, (int, float)) and isinstance(e, (int, float)):
                blocked.append((float(s), float(e)))
            else:
                # Try to parse string times
                def _p(t):
                    import re
                    if not t: return None
                    m = re.match(r'(\d+):(\d+)\s*(AM|PM)', str(t), re.I)
                    if not m: return None
                    h, mn, p = int(m[1]), int(m[2]), m[3].upper()
                    if p == "PM" and h != 12: h += 12
                    if p == "AM" and h == 12: h = 0
                    return h + mn / 60
                sv = _p(s); ev = _p(e)
                if sv is not None and ev is not None:
                    blocked.append((sv, ev))

        blocked.sort(key=lambda x: x[0])

        day_start = day_ctx.get("day_start", 9.0)
        day_end   = day_ctx.get("day_end",   22.0)

        def is_free(start, end):
            """True if [start,end) doesn't overlap any blocked interval."""
            if start < day_start or end > day_end:
                return False
            for bs, be in blocked:
                if start < be and end > bs:
                    return False
            return True

        schedule = []
        cursor = day_start

        for task in tasks:
            dur = round(float(task.get("duration", 1.0)), 2)
            # Advance cursor past any blocked slots
            max_tries = 48  # up to 24h in 30-min steps
            tries = 0
            while tries < max_tries:
                if is_free(cursor, cursor + dur):
                    break
                # Skip to end of the blocking interval
                overlapping = [be for bs, be in blocked if cursor < be and cursor + dur > bs]
                if overlapping:
                    cursor = max(overlapping) + 0.25
                else:
                    cursor += 0.25
                tries += 1

            if cursor + dur > day_end:
                logger.warning(f"Task '{task.get('name')}' doesn't fit before day_end — appending anyway")

            end_dec  = cursor + dur
            start_str = self._dec_to_str(cursor)
            end_str   = self._dec_to_str(end_dec)

            schedule.append({
                "task":           task.get("name", "Task"),
                "start_time":     cursor,
                "end_time":       end_dec,
                "duration":       dur,
                "priority":       task.get("priority",   "medium"),
                "difficulty":     task.get("difficulty", "medium"),
                "category":       task.get("category",   "general"),
                "time":           f"{start_str} - {end_str}",
                "start_time_str": start_str,
                "end_time_str":   end_str,
            })

            # Add to blocked so the next task doesn't overlap
            blocked.append((cursor, end_dec))
            blocked.sort(key=lambda x: x[0])
            cursor = end_dec + 0.25  # 15-min buffer

        return schedule

    async def _handle_add_task(self, message: str) -> Dict[str, Any]:
        """
        Handle ADD_TASK intent — extract the task(s), find the next free slot
        after whatever is already scheduled today, and return with add_intent=True
        so the backend merges instead of replacing.

        If no schedule exists yet for today, falls back to _create_schedule_with_nlp
        so the daily check-in fires correctly.
        """
        from datetime import datetime as _dt
        today_str = _dt.now().date().isoformat()

        # Check if there is already a schedule today
        existing_plan = await self.db.daily_plans.find_one(
            {"user_id": self.user_id, "date": today_str}
        )
        existing_schedule = (existing_plan or {}).get("schedule", [])

        # No schedule yet → use full create flow (triggers check-in if needed)
        if not existing_schedule:
            return await self._create_schedule_with_nlp(message)

        # Extract task(s) from the message
        tasks = []
        if self.nlp:
            try:
                extracted = self.nlp.extract_tasks(message)
                if extracted:
                    for t in extracted:
                        name = _strip_filler(t.get("name", "").strip()) or t.get("name", "")
                        if name:
                            tasks.append({
                                "name":     name,
                                "duration": t.get("duration", 1.0),
                                "priority": t.get("priority", "medium"),
                            })
            except Exception as e:
                logger.error(f"NLP extraction in add_task: {e}")

        if not tasks:
            tasks = await self._manual_extract_tasks(message)

        if not tasks:
            return {
                "type":    "clarification",
                "message": "What task would you like to add? Try: 'meditation 30 min' or 'read for 1 hour'",
            }

        # Place tasks after existing schedule using day context
        day_ctx  = await self._get_day_context(today_str)
        schedule = self._find_free_slots(day_ctx, existing_schedule, tasks)

        task_names = [t["name"] for t in tasks]
        plural = "tasks" if len(tasks) > 1 else "task"
        return {
            "type":        "schedule",
            "add_intent":  True,
            "message":     f"✅ Added {len(tasks)} {plural}: {', '.join(task_names)}",
            "tasks_found": task_names,
            "schedule":    schedule,
            "insights":    ["💡 Added to your existing schedule!"],
        }

    async def _handle_schedule_optimization(self, message: str) -> Dict[str, Any]:
        """Optimize existing schedule"""
        
        # Get today's schedule
        today = datetime.now().date().isoformat()
        plan = await self.db.daily_plans.find_one({
            "user_id": self.user_id,
            "date": today
        })
        
        if not plan or not plan.get("schedule"):
            return {
                "type": "info",
                "message": "You don't have a schedule for today yet. Would you like me to create one?",
                "suggestions": [
                    "I have Physics, Maths and Chemistry to study today — plan it",
                    "Plan my study day",
                ]
            }
        
        # Convert to tasks
        tasks = []
        for item in plan["schedule"]:
            tasks.append({
                "name": item["task"],
                "duration": item.get("duration", 1),
                "priority": item.get("priority", "medium"),
                "difficulty": "medium"
            })
        
        # Optimize using scheduler
        try:
            schedule_result = await self.scheduler.create_optimal_schedule(tasks)
            
            # Format response
            formatted_schedule = []
            for item in schedule_result["schedule"]:
                formatted_schedule.append({
                    "task": item["task"],
                    "start_time": self._format_time(item["start_time"]),
                    "end_time": self._format_time(item["end_time"]),
                    "duration": round(item["duration"], 1),
                    "priority": item.get("priority", "medium"),
                    "time": f"{self._format_time(item['start_time'])} - {self._format_time(item['end_time'])}"
                })
            
            return {
                "type": "schedule",
                "message": "✨ I've optimized your schedule for maximum productivity!",
                "schedule": formatted_schedule,
                "insights": schedule_result["insights"],
                "optimized": True
            }
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return {
                "type": "error",
                "message": "I couldn't optimize your schedule right now. Please try again later."
            }
    
    async def _enhanced_habit_analysis(self) -> Dict[str, Any]:
        """Enhanced habit analysis using new analyzer"""
        
        try:
            # Use new analyzer
            analysis = await self.analyzer.analyze_patterns()
            
            # Get learning patterns if available
            learning_patterns = None
            history_count = await self.db.task_history.count_documents({"user_id": self.user_id})
            if history_count > 10:
                learning_patterns = await self.learner.get_productivity_patterns()
            
            # Format stats for your frontend
            stats = {
                "completion_rate": f"{analysis.get('task_completion', {}).get('overall_rate', 0)}%",
                "total_tasks": analysis.get('task_completion', {}).get('total_tasks', 0),
                "completed": analysis.get('task_completion', {}).get('completed_tasks', 0),
                "avg_task_duration": f"{analysis.get('focus_patterns', {}).get('average_focus_time', 0)} hours",
                "streak": analysis.get('streaks', {}).get('current_streak', 0),
                "productivity_score": analysis.get('productivity_score', {}).get('overall', 0)
            }
            
            # Generate recommendations
            recommendations = analysis.get('recommendations', [])
            if learning_patterns and 'recommendations' in learning_patterns:
                recommendations.extend(learning_patterns['recommendations'])
            
            # Get peak hours for display
            peak_hours = analysis.get('peak_hours', {}).get('peak_hours', [])
            
            return {
                "type": "analysis",
                "message": f"📊 Here's your productivity analysis:",
                "stats": stats,
                "insight": analysis.get('trends', {}).get('message', 'Keep up the great work!'),
                "recommendations": recommendations[:5],
                "peak_hours": peak_hours,
                "detailed_analysis": {
                    "peak_hours": analysis.get('peak_hours', {}),
                    "energy_patterns": analysis.get('energy_patterns', {}),
                    "focus_patterns": analysis.get('focus_patterns', {})
                } if history_count > 10 else None
            }
            
        except Exception as e:
            logger.error(f"Enhanced habit analysis error: {e}")
            # Fall back to original habit analysis
            return await self._handle_habit_analysis()
    
    async def _handle_progress_check(self) -> Dict[str, Any]:
        """Check user's progress"""
        
        try:
            # Get stats from analyzer
            analysis = await self.analyzer.analyze_patterns()
            stats = analysis.get('productivity_score', {})
            
            # Get streak info
            streaks = analysis.get('streaks', {})
            
            # Get recent trend
            trend = analysis.get('trends', {})
            
            progress_message = []
            
            if streaks.get('current_streak', 0) > 0:
                progress_message.append(f"🔥 You're on a {streaks['current_streak']}-day streak!")
            
            if stats.get('overall', 0) > 0:
                progress_message.append(f"📈 Your productivity score is {stats['overall']}/100")
            
            if stats.get('components', {}).get('completion', 0) > 0:
                progress_message.append(f"✅ Task completion rate: {stats['components']['completion']}%")
            
            if trend.get('trend') == 'improving':
                progress_message.append("📊 You're improving! Keep it up!")
            elif trend.get('trend') == 'declining':
                progress_message.append("📊 Your productivity has dipped. Let's get back on track!")
            
            return {
                "type": "progress",
                "message": " ".join(progress_message) or "Start using the planner to track your progress!",
                "stats": {
                    "overall": stats.get('overall', 0),
                    "completion": stats.get('components', {}).get('completion', 0),
                    "accuracy": stats.get('components', {}).get('accuracy', 0),
                    "focus": stats.get('components', {}).get('focus', 0)
                },
                "streak": streaks.get('current_streak', 0),
                "trend": trend.get('trend', 'stable')
            }
            
        except Exception as e:
            logger.error(f"Progress check error: {e}")
            return {
                "type": "progress",
                "message": "Start using the planner to track your progress!",
                "suggestions": [
                    "I have Physics, Maths and Chemistry to study today — plan it",
                    "Give me tips to stay focused while studying",
                ]
            }
    
    async def _enhanced_advice_request(self) -> Dict[str, Any]:
        """Enhanced advice with personalization"""
        
        try:
            # Get context for personalized advice
            context = {
                "task_history": await self.db.task_history.find(
                    {"user_id": self.user_id}
                ).sort("created_at", -1).to_list(20),
                "pending_tasks": await self.db.tasks.find(
                    {"user_id": self.user_id, "completed": False}
                ).to_list(10)
            }
            
            # Get recommendations from recommender
            recommendations = await self.recommender.get_recommendations(context)
            
            # Student-friendly advice
            advice_list = [
                "Start with your hardest subject when your brain is freshest 🧠",
                "Use the Pomodoro Technique: 25 min study, 5 min break",
                "Review your notes within 24 hours to retain 80% more",
                "Take a 5-minute break every hour to maintain focus",
                "Study similar subjects back-to-back to stay in flow",
                "The first 2 hours of your day are your most productive — use them for hard subjects!",
                "Teach what you learned to a friend — it's the best way to remember",
                "Switch subjects every 90 minutes to avoid mental fatigue",
            ]
            
            # Add personalized advice from recommender
            personalized_advice = []
            if recommendations.get('productivity_boosters'):
                personalized_advice.extend(recommendations['productivity_boosters'])
            
            if recommendations.get('task_optimizations'):
                personalized_advice.extend(recommendations['task_optimizations'])
            
            # Combine and select top advice
            all_advice = advice_list + personalized_advice
            selected_advice = random.sample(all_advice, min(4, len(all_advice)))
            
            return {
                "type": "advice",
                "message": "Here are your personalised study tips:",
                "advice_points": selected_advice,
                "insight": "Consistency beats intensity — 2 hours every day beats 10 hours once a week!",
                "personalized": len(personalized_advice) > 0
            }
            
        except Exception as e:
            logger.error(f"Enhanced advice error: {e}")
            # Fall back to original advice
            return await self._handle_advice_request()
    
    async def _enhanced_question(self, message: str) -> Dict[str, Any]:
        """Enhanced question answering with context"""
        
        # Try OpenAI for complex questions
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a productivity expert. Answer questions concisely and helpfully. Keep responses under 150 words."},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            answer = response.choices[0].message.content
            
            return {
                "type": "answer",
                "message": answer,
                "follow_up": "Would you like to know more about this topic?",
                "suggestions": [
                    "How to stay focused while studying",
                    "Best study techniques for exams",
                    "How to beat procrastination",
                ]
            }
            
        except Exception as e:
            logger.error(f"OpenAI question error: {e}")
            # Fall back to your existing knowledge base
            return await self._handle_question(message)
    
    async def _enhanced_general_chat(self, message: str) -> Dict[str, Any]:
        """
        Last-resort handler. Before giving a generic response, make one more
        attempt to treat the message as a task/schedule request — catches
        anything the intent detector might have missed (e.g. very short messages,
        typos, unusual phrasing).
        """
        # Final attempt: try to extract tasks from the message
        tasks = await self._manual_extract_tasks(message)
        if tasks:
            # Managed to extract at least one task — treat as ADD_TASK
            logger.info(f"General-chat fallback extracted tasks: {[t['name'] for t in tasks]}")
            return await self._handle_add_task(message)

        # Genuinely a chat message — give a helpful contextual response
        msg_lower = message.lower()

        # Greetings
        if any(g in msg_lower for g in ["hello", "hi", "hey", "good morning",
                                         "good afternoon", "good evening"]):
            try:
                streak = await self._calculate_streak()
                if streak > 0:
                    return {
                        "type": "chat",
                        "message": f"Hey! You're on a {streak}-day streak 🔥 What are you working on today?",
                        "suggestions": [
                            "Study Physics 2 hours and Maths 1 hour",
                            "Add meditation for 30 minutes",
                            "Show me my productivity progress",
                        ]
                    }
            except Exception:
                pass
            return {
                "type": "chat",
                "message": "Hey! 👋 What would you like to work on today? Just tell me your tasks and I'll schedule them for you.",
                "suggestions": [
                    "Study Physics 2 hours and Maths 1 hour",
                    "Add meditation for 30 minutes",
                    "Plan my day",
                ]
            }

        # Thanks
        if any(t in msg_lower for t in ["thanks", "thank you", "thx", "ty"]):
            return {
                "type": "chat",
                "message": "Happy to help! 🚀 Anything else you want to schedule or ask?",
                "suggestions": [
                    "Add another task",
                    "Show my productivity tips",
                ]
            }

        # Default — nudge toward scheduling
        default_msg = (
            "I can help you schedule tasks, track productivity, or give study tips!\n\n"
            "Try saying something like:\n"
            "\u2022 'Study Physics 2 hours'\n"
            "\u2022 'Add meditation for 30 minutes'\n"
            "\u2022 'Plan my day'"
        )
        return {
            "type": "chat",
            "message": default_msg,
            "suggestions": [
                "Study Physics 2 hours and Maths 1 hour",
                "Add meditation for 30 minutes",
                "Give me productivity tips",
            ]
        }
    
    async def _rule_based_processing(self, message: str) -> Dict[str, Any]:
        """Original rule-based processing - kept for backward compatibility"""
        intent = await self._detect_intent(message)
        
        if intent == IntentType.CREATE_SCHEDULE:
            return await self._handle_schedule_creation(message)
        elif intent == IntentType.GET_ADVICE:
            return await self._handle_advice_request()
        elif intent == IntentType.ASK_QUESTION:
            return await self._handle_question(message)
        elif intent == IntentType.ANALYZE_HABITS:
            return await self._handle_habit_analysis()
        else:
            return await self._handle_general_chat(message)
    
    async def _detect_intent(self, message: str) -> IntentType:
        """
        Smart intent detection.
        Key insight: ANY message that mentions a task + duration is a scheduling
        request — even without "add" or "plan" keywords.
        e.g. "meditation for 30 minutes" → ADD_TASK (has existing schedule)
             "physics 2 hours maths 1 hour" → CREATE_SCHEDULE
        """
        import re as _re
        msg = message.lower().strip()

        # ── 1. ROUTINE: user describing their daily structure ─────────────────
        _routine_phrases = [
            "i have college", "i have school", "i have work", "i have class",
            "my college is", "my school is", "my work is",
            "i wake up", "i sleep at", "i finish at", "i get home",
            "my lunch", "my dinner", "my break",
            "my day starts", "my day ends", "i'm free from", "i am free from",
            "blocked from", "busy from", "not available",
            "tell you my routine", "my routine is",
            "i study from", "i work from",
        ]
        if any(p in msg for p in _routine_phrases):
            return IntentType.MODIFY_SCHEDULE

        # ── 2. PROGRESS / ANALYSIS ────────────────────────────────────────────
        if any(p in msg for p in ['progress', 'how am i doing', 'stats', 'performance']):
            return IntentType.CHECK_PROGRESS
        if any(p in msg for p in ['analyze', 'analyse', 'habits', 'patterns']):
            return IntentType.ANALYZE_HABITS

        # ── 3. OPTIMIZATION ───────────────────────────────────────────────────
        if any(p in msg for p in ['optimize', 'optimise', 'reschedule', 'redo my']):
            return IntentType.OPTIMIZE_SCHEDULE

        # ── 4. ADVICE ─────────────────────────────────────────────────────────
        if any(p in msg for p in ['advice', 'tips', 'recommend', 'suggest', 'help me focus',
                                   'how to', 'what should']):
            return IntentType.GET_ADVICE

        # ── 5. QUESTION ───────────────────────────────────────────────────────
        if any(p in msg for p in ['what is', 'how do', 'why ', 'explain', 'tell me about']):
            return IntentType.ASK_QUESTION

        # ── 6. FULL PLAN keywords → CREATE_SCHEDULE ───────────────────────────
        _full_plan_kws = [
            "plan my day", "plan my whole", "plan my entire",
            "create a schedule", "create schedule", "make a schedule",
            "make my schedule", "start over", "start fresh",
            "organise my day", "organize my day",
        ]
        if any(p in msg for p in _full_plan_kws):
            return IntentType.CREATE_SCHEDULE

        # ── 7. EXPLICIT ADD keywords → ADD_TASK ──────────────────────────────
        _add_kws = [
            "add ", "also add", "also schedule", "include ",
            "one more", "add task", "add a task", "add another",
            "i also need", "i also have", "put ",
        ]
        if any(p in msg for p in _add_kws):
            return IntentType.ADD_TASK

        # ── 8. SMART TASK DETECTION ───────────────────────────────────────────
        # If the message looks like it contains a task description
        # (something + duration OR something + time), treat it as scheduling.
        # This catches: "meditation for 30 minutes", "walk 45 min", "physics 2hr"
        _has_duration = bool(_re.search(
            r'\d+(\.\d+)?\s*(hour|hr|h|minute|min|mins?)', msg
        ))
        _has_time_of_day = bool(_re.search(
            r'\d{1,2}:\d{2}\s*(am|pm)|\d{1,2}\s*(am|pm)', msg
        ))
        _has_activity = bool(_re.search(
            r'(study|read|exercise|walk|run|gym|meditat|yoga|code|coding|'
            r'work|practice|revision|revise|homework|assignment|project|'
            r'physics|maths?|chemistry|biology|english|history|geography|'
            r'dsa|leetcode|language|music|draw|write|meet|call|'
            r'cook|eat|sleep|nap|break|rest)', msg
        ))

        # Task + duration → definitely scheduling
        if _has_duration and _has_activity:
            # Check if message mentions MULTIPLE tasks → full plan
            # Simple heuristic: commas or "and" between task words = multiple tasks
            task_count = len(_re.findall(
                r'(study|read|exercise|walk|run|gym|meditat|yoga|code|work|'
                r'practice|revision|physics|maths?|chemistry|biology|dsa)', msg
            ))
            if task_count >= 2:
                return IntentType.CREATE_SCHEDULE
            return IntentType.ADD_TASK   # single task → add to existing

        # Has time of day + activity → schedule it
        if _has_time_of_day and _has_activity:
            return IntentType.CREATE_SCHEDULE

        # Just a duration mentioned (e.g. "30 minutes of meditation") → add task
        if _has_duration:
            return IntentType.ADD_TASK

        # Just an activity name (e.g. "meditation", "a walk") → add task
        if _has_activity:
            return IntentType.ADD_TASK

        # Explicit "i need to / i have to" → create schedule
        if any(p in msg for p in ["i need to", "i have to", "plan", "schedule",
                                   "tasks for", "to do", "my day"]):
            return IntentType.CREATE_SCHEDULE

        return IntentType.GENERAL_CHAT
    
    async def _get_user_context(self) -> str:
        """Get user context for AI"""
        context_parts = []
        
        # Get tasks
        try:
            tasks_cursor = self.db.tasks.find({"user_id": self.user_id}).limit(5)
            tasks = await tasks_cursor.to_list(5)
            if tasks:
                task_list = [f"- {t.get('text', '')} (Priority: {t.get('priority', 'medium')})" for t in tasks if t.get('text')]
                if task_list:
                    context_parts.append("Current tasks:\n" + "\n".join(task_list))
        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")
        
        # Get plans
        try:
            plans_cursor = self.db.daily_plans.find({"user_id": self.user_id}).sort("created_at", -1).limit(3)
            plans = await plans_cursor.to_list(3)
            if plans:
                context_parts.append(f"Recent plans: {len(plans)} plans saved")
        except Exception as e:
            logger.error(f"Error fetching plans: {e}")
        
        # Get accuracy
        accuracy = await self._get_user_accuracy()
        if accuracy:
            context_parts.append(f"Accuracy: Easy {accuracy.get('easy', 1)}x, Medium {accuracy.get('medium', 1)}x, Hard {accuracy.get('hard', 1)}x")
        
        # Get streak
        streak = await self._calculate_streak()
        if streak > 0:
            context_parts.append(f"Current streak: {streak} days")
        
        return "\n".join(context_parts) if context_parts else "New user with no history yet."
    
    async def _get_user_accuracy(self):
        """Get user's task estimation accuracy"""
        try:
            records_cursor = self.db.task_history.find({"user_id": self.user_id}).sort("created_at", -1).limit(50)
            records = await records_cursor.to_list(50)
            
            if not records:
                return None
            
            stats = {"easy": [], "medium": [], "hard": []}
            for r in records:
                if r.get("actualTime") and r.get("aiTime") and r["aiTime"] > 0:
                    ratio = r["actualTime"] / r["aiTime"]
                    difficulty = r.get("difficulty", "medium")
                    if difficulty in stats:
                        stats[difficulty].append(ratio)
            
            result = {}
            for k, v in stats.items():
                if v:
                    result[k] = round(sum(v) / len(v), 2)
                else:
                    result[k] = 1
            return result
        except Exception as e:
            logger.error(f"Error calculating accuracy: {e}")
            return None
    
    async def _calculate_streak(self) -> int:
        """Calculate current streak"""
        try:
            cursor = self.db.daily_plans.find(
                {"user_id": self.user_id}
            ).sort("date", -1).limit(30)
            
            plans = await cursor.to_list(30)
            
            streak = 0
            current_date = datetime.now().date()
            
            for plan in plans:
                try:
                    plan_date = datetime.fromisoformat(plan["date"]).date()
                    if plan_date == current_date - timedelta(days=streak):
                        if plan.get("optimizedTasks") and len(plan.get("optimizedTasks", [])) > 0:
                            streak += 1
                        else:
                            break
                    else:
                        break
                except:
                    continue
            
            return streak
            
        except Exception as e:
            logger.error(f"Streak calculation error: {e}")
            return 0
    
    def _parse_time(self, time_str: str) -> Optional[float]:
        """Convert time string like '8:30am' or '4pm' to hour number (e.g., 8.5 or 16.0)"""
        if not time_str:
            return None
        
        time_str = time_str.lower().strip()
        
        # Extract hours and minutes
        match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
        if not match:
            return None
        
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        
        # Convert to 24-hour format
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        
        return hour + (minute / 60)
    
    async def _extract_tasks_naturally(self, message: str) -> List[ExtractedTask]:
        """Extract tasks from natural language including specific times"""
        tasks = []
        
        # Clean the message
        message = re.sub(r'^(plan|schedule|create|organize)\s+(my day|tasks?|schedule)?\s*', '', message, flags=re.IGNORECASE)
        message = message.strip()
        
        # MORE FLEXIBLE time range pattern
        time_range_pattern = r'(.+?)\s+(?:at|from|between)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|until|-|and)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)'
        
        # Process time-specific tasks first
        remaining_message = message
        time_specific_tasks = []
        
        for match in re.finditer(time_range_pattern, message, re.IGNORECASE):
            task_name = match.group(1).strip()
            start_time_str = match.group(2)
            end_time_str = match.group(3)
            
            start_hour = self._parse_time(start_time_str)
            end_hour = self._parse_time(end_time_str)
            
            if start_hour is not None and end_hour is not None and end_hour > start_hour:
                duration = end_hour - start_hour
                
                task = ExtractedTask(
                    name=task_name,
                    duration=duration,
                    priority="medium",
                    complexity=TaskComplexity.MEDIUM,
                    start_time=start_hour,
                    end_time=end_hour
                )
                time_specific_tasks.append(task)
                remaining_message = remaining_message.replace(match.group(0), '')
        
        tasks.extend(time_specific_tasks)
        
        # Look for "then X for Y minutes/hours" patterns
        then_pattern = r'then\s+(.+?)\s+for\s+(\d+)\s*(min|minute|hour|hr)s?'
        for match in re.finditer(then_pattern, remaining_message, re.IGNORECASE):
            task_name = match.group(1).strip()
            duration_value = int(match.group(2))
            duration_unit = match.group(3).lower()
            
            duration = duration_value / 60 if 'min' in duration_unit else duration_value
            
            # Clean up task name
            task_name = re.sub(r'^(?:for|to|and|then|after that|i have to|i need to)\s+', '', task_name, flags=re.IGNORECASE)
            task_name = task_name.strip()
            
            task = ExtractedTask(
                name=task_name,
                duration=duration,
                priority="medium"
            )
            tasks.append(task)
            remaining_message = remaining_message.replace(match.group(0), '')
        
        # Split remaining by common separators
        separators = r'(?:and|,|\.|also|plus|then|after that)'
        raw_segments = re.split(separators, remaining_message)
        
        for segment in raw_segments:
            segment = segment.strip()
            if not segment or len(segment) < 3:
                continue
            
            # Skip if already processed
            if any(task.name.lower() in segment.lower() for task in tasks):
                continue
            
            # Extract duration
            duration = 1.0
            name = segment
            
            # Check for "X hours" pattern with word boundary
            hour_match = re.search(r'(\d+\.?\d*)\s*(?:hour|hr|h)\b', segment.lower())
            if hour_match:
                duration = float(hour_match.group(1))
                name = re.sub(r'\d+\.?\d*\s*(?:hour|hr|h)s?\b', '', segment, flags=re.IGNORECASE).strip()
            else:
                # Check for "X minutes" pattern with word boundary
                minute_match = re.search(r'(\d+)\s*(min|minute)\b', segment.lower())
                if minute_match:
                    duration = float(minute_match.group(1)) / 60
                    # Remove the entire duration phrase
                    name = re.sub(r'\d+\s*(?:min|minute)s?\b', '', segment, flags=re.IGNORECASE).strip()
                else:
                    # Check for patterns like "for X hours" at the end
                    for_hours_match = re.search(r'for\s+(\d+\.?\d*)\s*(?:hour|hr|h)\b', segment.lower())
                    if for_hours_match:
                        duration = float(for_hours_match.group(1))
                        name = re.sub(r'for\s+\d+\.?\d*\s*(?:hour|hr|h)\b', '', segment, flags=re.IGNORECASE).strip()
            
            # Clean up name - remove common prefixes and suffixes
            name = re.sub(r'^(?:for|to|and|then|after that|i have to|i need to)\s+', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s+(?:for|at|from|minutes?|hours?)$', '', name, flags=re.IGNORECASE)
            name = name.strip(' .,')
            
            # Don't add if name is too short or is just time units
            if name and len(name) > 2 and name.lower() not in ['min', 'mins', 'minute', 'minutes', 'hour', 'hours', 'hr', 'hrs']:
                # Check if this task name is already in tasks (case insensitive)
                is_duplicate = False
                for existing_task in tasks:
                    if (existing_task.name.lower() in name.lower() or 
                        name.lower() in existing_task.name.lower()):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    tasks.append(ExtractedTask(
                        name=name,
                        duration=duration,
                        priority="medium"
                    ))
        
        # Final filter - remove any tasks with invalid names
        tasks = [t for t in tasks if t.name.lower() not in ['min', 'mins', 'minute', 'minutes', 'hour', 'hours', 'hr', 'hrs', 'utes']]
        
        return tasks
    
    def _format_time(self, hour: float) -> str:
        """Format hour to time string (e.g., 8.5 -> 8:30 AM)"""
        if hour is None:
            return ""
            
        hour_int = int(hour)
        minute = int((hour - hour_int) * 60)
        
        period = "AM"
        display_hour = hour_int
        
        if hour_int >= 12:
            period = "PM"
            if hour_int > 12:
                display_hour = hour_int - 12
        if hour_int == 0:
            display_hour = 12
            
        return f"{display_hour}:{minute:02d} {period}"
    
    async def _generate_smart_schedule(self, tasks: List[ExtractedTask]) -> List[Dict]:
        """Generate intelligent schedule respecting specific time requests"""
        
        if not tasks:
            return []
        
        # Separate tasks with specific times and without
        fixed_time_tasks = [t for t in tasks if t.start_time is not None]
        flexible_tasks = [t for t in tasks if t.start_time is None]
        
        # Sort fixed time tasks by start time
        fixed_time_tasks.sort(key=lambda x: x.start_time)
        
        # Sort flexible tasks by priority
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        flexible_tasks.sort(key=lambda x: -priority_order.get(x.priority, 2))
        
        schedule = []
        
        # If there are fixed time tasks, we need to place flexible tasks around them
        if fixed_time_tasks:
            # Add all fixed tasks to schedule
            for task in fixed_time_tasks:
                schedule.append({
                    "task": task.name,
                    "start_time": self._format_time(task.start_time),
                    "end_time": self._format_time(task.end_time),
                    "duration": round(task.duration, 1),
                    "priority": task.priority,
                    "time": f"{self._format_time(task.start_time)} - {self._format_time(task.end_time)}"
                })
            
            # Now place flexible tasks in gaps
            # Get all occupied time blocks
            occupied = [(task.start_time, task.end_time) for task in fixed_time_tasks]
            
            # Find gaps and place flexible tasks
            for task in flexible_tasks:
                placed = False
                
                # Try to place in gaps between fixed tasks
                for i in range(len(occupied) + 1):
                    if i == 0:
                        # Gap before first fixed task
                        gap_start = 9.0
                        gap_end = occupied[0][0] if occupied else 24.0
                    elif i == len(occupied):
                        # Gap after last fixed task
                        gap_start = occupied[-1][1] + 0.25
                        gap_end = 24.0
                    else:
                        # Gap between fixed tasks
                        gap_start = occupied[i-1][1] + 0.25
                        gap_end = occupied[i][0]
                    
                    # If there's enough time in this gap
                    if gap_end - gap_start >= task.duration:
                        schedule.append({
                            "task": task.name,
                            "start_time": self._format_time(gap_start),
                            "end_time": self._format_time(gap_start + task.duration),
                            "duration": round(task.duration, 1),
                            "priority": task.priority,
                            "time": f"{self._format_time(gap_start)} - {self._format_time(gap_start + task.duration)}"
                        })
                        # Update occupied list with this new task
                        occupied.append((gap_start, gap_start + task.duration))
                        occupied.sort()
                        placed = True
                        break
                
                if not placed:
                    # Place at the end of the day
                    last_time = occupied[-1][1] + 0.25 if occupied else 9.0
                    schedule.append({
                        "task": task.name,
                        "start_time": self._format_time(last_time),
                        "end_time": self._format_time(last_time + task.duration),
                        "duration": round(task.duration, 1),
                        "priority": task.priority,
                        "time": f"{self._format_time(last_time)} - {self._format_time(last_time + task.duration)}"
                    })
        else:
            # No fixed tasks, just schedule all flexible tasks in order
            current_time = 9.0
            
            for task in flexible_tasks:
                schedule.append({
                    "task": task.name,
                    "start_time": self._format_time(current_time),
                    "end_time": self._format_time(current_time + task.duration),
                    "duration": round(task.duration, 1),
                    "priority": task.priority,
                    "time": f"{self._format_time(current_time)} - {self._format_time(current_time + task.duration)}"
                })
                current_time += task.duration + 0.25
        
        # Sort final schedule by start time
        def get_start_time(item):
            time_str = item['start_time']
            return self._parse_time(time_str) or 0
        
        schedule.sort(key=get_start_time)
        
        return schedule
    
    async def _handle_schedule_creation(self, message: str) -> Dict[str, Any]:
        """Original schedule creation - kept for backward compatibility"""
        
        tasks = await self._extract_tasks_naturally(message)
        
        if not tasks:
            return {
                "type": "clarification",
                "message": "I'd love to help you plan! Could you tell me what tasks you need to do? For example: 'Study Physics 2 hours, Maths 1 hour, revision at 3 PM' or 'I have college from 8:30 AM to 4 PM'"
            }
        
        # Generate schedule
        schedule = await self._generate_smart_schedule(tasks)
        
        # Generate insights
        insights = []
        total_hours = sum(t.duration for t in tasks)
        
        if total_hours > 8:
            insights.append("⚠️ This is a packed day! Make sure to take breaks.")
        elif total_hours < 4:
            insights.append("✨ You have a light day. Great for deep work!")
        
        high_priority = sum(1 for t in tasks if t.priority == 'high')
        if high_priority > 2:
            insights.append("🎯 Multiple high-priority tasks. Start with the most important one.")
        
        # Check if any task has specific times
        has_fixed_times = any(t.start_time is not None for t in tasks)
        if has_fixed_times:
            insights.append("⏰ I've respected your specific time requests for certain tasks.")
        
        return {
            "type": "schedule",
            "message": f"✅ I've created your schedule with {len(tasks)} tasks!",
            "tasks_found": [t.name for t in tasks],
            "schedule": schedule,
            "insights": insights if insights else ["💡 Remember to take short breaks between tasks"]
        }
    
    async def _handle_advice_request(self) -> Dict[str, Any]:
        """Original advice request - kept for backward compatibility"""
        
        # Student-friendly advice (fallback version)
        advice_list = [
            "Start with your hardest subject when your brain is freshest 🧠",
            "Use the Pomodoro Technique: 25 min study, 5 min break",
            "Review your notes within 24 hours to retain 80% more",
            "Take a 5-minute break every hour to maintain focus",
            "Study similar subjects back-to-back to stay in flow",
            "The first 2 hours of your day are your most productive — use them for hard subjects!",
        ]
        
        return {
            "type": "advice",
            "message": "Here are my top study tips:",
            "advice_points": random.sample(advice_list, 3),
            "insight": "Consistency beats intensity — 2 hours every day beats 10 hours once a week!"
        }
    
    async def _handle_question(self, message: str) -> Dict[str, Any]:
        """Original question handling - kept for backward compatibility"""
        
        knowledge_base = {
            "pomodoro": "The Pomodoro Technique uses 25-minute focused work sessions with 5-minute breaks. After 4 pomodoros, take a longer 15-30 minute break. It's great for maintaining focus!",
            "procrastination": "To beat procrastination, try the 5-minute rule: commit to working for just 5 minutes. Starting is often the hardest part. Also, break large tasks into smaller steps.",
            "priority": "Use the Eisenhower Matrix: Urgent & Important (do first), Important Not Urgent (schedule), Urgent Not Important (delegate), Neither (eliminate).",
            "focus": "To improve focus: eliminate distractions, use website blockers, try background music, and practice mindfulness. Also, ensure you're getting enough sleep!",
            "study": "Active recall and spaced repetition are the most effective study techniques. Test yourself often instead of just re-reading notes.",
            "exam": "Start revising at least 3 days before. Use past papers, summarise each chapter in your own words, and get enough sleep the night before.",
            "revision": "Break your revision into 25-minute blocks per topic. Alternate subjects to keep your brain engaged. Use flashcards for key facts.",
        }
        
        message_lower = message.lower()
        
        for key, answer in knowledge_base.items():
            if key in message_lower:
                return {
                    "type": "answer",
                    "message": answer,
                    "follow_up": "Would you like to know more about this topic?"
                }
        
        return {
            "type": "answer",
            "message": "That's a great question! While I specialize in productivity, I can help you with scheduling and study planning. Could you rephrase or ask about something specific?",
            "suggestions": [
                "How do I beat procrastination?",
                "Best study techniques for exams",
                "Tell me about the Pomodoro technique",
            ]
        }
    
    async def _handle_habit_analysis(self) -> Dict[str, Any]:
        """Original habit analysis - kept for backward compatibility"""
        
        # Get task history from database
        collection = self.db['task_history']
        cursor = collection.find({"user_id": self.user_id}).sort("date", -1).limit(20)
        history = await cursor.to_list(length=20)
        
        if not history:
            return {
                "type": "analysis",
                "message": "I need more data to analyze your habits! Start using the planner for a few days, and I'll give you personalised insights.",
                "suggestions": [
                    "I have Physics, Maths and Chemistry to study today — plan it",
                    "Give me tips to stay focused while studying",
                ]
            }
        
        completed = len([h for h in history if h.get('actualTime')])
        completion_rate = (completed / len(history)) * 100 if history else 0
        
        # Calculate average task duration
        avg_duration = sum(h.get('aiTime', 1) for h in history) / len(history)
        
        return {
            "type": "analysis",
            "message": f"📊 Based on your last {len(history)} tasks:",
            "stats": {
                "completion_rate": f"{int(completion_rate)}%",
                "total_tasks": len(history),
                "completed": completed,
                "avg_task_duration": f"{avg_duration:.1f} hours"
            },
            "insight": "You complete tasks faster in the morning. Schedule important study sessions before noon!" if completion_rate > 50 else "Try planning your most important subjects for your peak energy hours."
        }
    
    async def _handle_general_chat(self, message: str) -> Dict[str, Any]:
        """Original general chat - kept for backward compatibility"""
        
        responses = {
            "hello": "Hi there! 👋 Ready to crush your study goals today? I can help you plan your day, answer questions, or give personalised advice.",
            "hi": "Hello! How can I help you organise your study day?",
            "thanks": "You're welcome! Happy to help you stay productive! 🚀",
            "thank you": "My pleasure! Let me know if you need anything else.",
            "help": "I can help you with:\n• Planning your day (try: 'Study Physics 2h, Maths 1h')\n• Study tips (try: 'Give me tips to focus')\n• Answering questions (try: 'Best study techniques')\n• Analysing habits (try: 'Analyze my study patterns')"
        }
        
        message_lower = message.lower()
        
        for key, response in responses.items():
            if key in message_lower:
                return {
                    "type": "chat",
                    "message": response,
                    "suggestions": [
                        "I have Physics, Maths and Chemistry to study today — plan it",
                        "Give me tips to stay focused while studying",
                        "Analyze my study patterns this week",
                    ]
                }
        
        return {
            "type": "chat",
            "message": "I'm here to help with your productivity! Would you like to plan your study day, get some tips, or ask a question?",
            "suggestions": [
                "I have Physics, Maths and Chemistry to study today — plan it",
                "Give me tips to stay focused while studying",
                "Analyze my study patterns this week",
            ]
        }


async def get_ai_context(user_id: str, db):
    """Get AI context for frontend (enhanced with student-friendly suggestions)"""
    
    # Get user's recent activity
    collection = db['task_history']
    count = await collection.count_documents({"user_id": user_id})
    
    # Get streak
    streak = 0
    if count > 0:
        try:
            cursor = db.daily_plans.find({"user_id": user_id}).sort("date", -1).limit(30)
            plans = await cursor.to_list(30)
            
            current_date = datetime.now().date()
            for plan in plans:
                try:
                    plan_date = datetime.fromisoformat(plan["date"]).date()
                    if plan_date == current_date - timedelta(days=streak):
                        if plan.get("optimizedTasks") and len(plan.get("optimizedTasks", [])) > 0:
                            streak += 1
                        else:
                            break
                    else:
                        break
                except:
                    continue
        except:
            pass
    
    # Student-friendly suggestions
    suggestions = [
        "I have Physics, Maths and Chemistry to study today — plan it",
        "Exam in 3 days, help me plan my revision schedule",
        "I study best in the morning, plan 6 hours of study for today",
        "Give me tips to stay focused while studying",
        "Analyze my study patterns this week",
    ]

    if count > 0:
        suggestions.insert(0, "Show me my productivity progress")
    if streak > 0:
        suggestions.insert(1, f"I'm on a {streak}-day study streak — what's next?")
    
    return {
        "suggestions": suggestions,
        "has_history": count > 0,
        "quick_actions": ["Create Schedule", "Get Advice", "Analyze Habits", "Check Progress"],
        "streak": streak,
        "total_tasks": count
    }


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GUIDANCE AI FOR PERFORMANCE PAGE
# ╚══════════════════════════════════════════════════════════════════════════════

async def get_guidance_response(
    user_id: str,
    db,
    question: str,
) -> Dict[str, Any]:
    """
    Performance page AI Coach — fully data-aware.
    Loads ALL of the user's analytics (tasks, focus, AI schedules, prediction
    accuracy, peak hours, completion rate, streak, performance index) and injects
    them into Gemini so every answer is personalised to the user's actual data.
    """
    import os, json
    from datetime import datetime as _dt, timedelta
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")

    # ── Redirect scheduling requests to AI Planner ────────────────────────────
    _SCHEDULE_KEYWORDS = [
        "schedule", "plan my day", "plan for", "create schedule",
        "add task", "book time", "set up my", "i need to study",
        "i have to", "i need to do",
    ]
    q_lower = question.lower()
    if any(kw in q_lower for kw in _SCHEDULE_KEYWORDS):
        return {
            "success": True,
            "message": (
                "📅 For scheduling and planning tasks, head to the **AI Planner** page — "
                "that's where I build your full daily schedule. "
                "Here on the Performance page I'm your Productivity Coach: "
                "ask me about your stats, focus habits, improvement areas, or how to beat procrastination!"
            ),
            "context_used": False,
            "data_points": 0,
            "redirect_hint": "planner",
            "suggestions": [
                "How productive am I based on my data?",
                "What should I improve to be more productive?",
                "How can I improve my focus score?",
            ],
        }

    # ── Snapshot-only request (frontend init, no LLM needed) ────────────────
    if question.strip() == "__snapshot__":
        # Just collect data and return it — no Gemini call needed
        pass  # will fall through to data collection and return at the end

    # ── Gather ALL user analytics for rich context ────────────────────────────
    now        = _dt.now()
    today      = now.date()
    context_used = False

    # 1. Basic task counts
    task_count       = 0
    completed_count  = 0
    completion_rate  = 0
    try:
        task_count      = await db.tasks.count_documents({"user_id": user_id})
        completed_count = await db.tasks.count_documents({"user_id": user_id, "completed": True})
        if task_count > 0:
            completion_rate = round((completed_count / task_count) * 100)
            context_used = True
    except Exception:
        pass

    # 2. Task history for deeper patterns
    history_count = 0
    avg_actual_time = 0.0
    difficulty_breakdown = {}
    priority_breakdown   = {}
    try:
        history_docs = await db.task_history.find({"user_id": user_id}).to_list(500)
        history_count = len(history_docs)
        if history_docs:
            context_used = True
            times = [d.get("actualTime", 0) for d in history_docs if d.get("actualTime")]
            avg_actual_time = round(sum(times) / len(times), 1) if times else 0

            for d in history_docs:
                diff = d.get("difficulty", "medium")
                difficulty_breakdown[diff] = difficulty_breakdown.get(diff, 0) + 1
                pri  = d.get("priority", "medium")
                priority_breakdown[pri]   = priority_breakdown.get(pri, 0) + 1
    except Exception:
        pass

    # 3. Streak calculation
    streak = 0
    try:
        plans = await db.daily_plans.find({"user_id": user_id}).sort("date", -1).limit(30).to_list(30)
        for i, plan in enumerate(plans):
            try:
                pd = _dt.fromisoformat(plan["date"]).date()
                if pd == today - timedelta(days=i) and (
                    len(plan.get("schedule", [])) > 0 or
                    len(plan.get("optimizedTasks", [])) > 0
                ):
                    streak += 1
                else:
                    break
            except Exception:
                break
    except Exception:
        pass

    # 4. AI schedules generated
    ai_schedules_count = 0
    ai_tasks_planned   = 0
    try:
        all_plans = await db.daily_plans.find({"user_id": user_id}).to_list(200)
        ai_schedules_count = len(all_plans)
        for p in all_plans:
            ai_tasks_planned += len(p.get("schedule", []) or p.get("optimizedTasks", []))
        if ai_schedules_count > 0:
            context_used = True
    except Exception:
        pass

    # 5. Focus sessions
    focus_hours_total = 0.0
    focus_sessions    = 0
    avg_focus_min     = 0
    try:
        focus_docs = await db.focus_sessions.find({"user_id": user_id}).to_list(200)
        focus_sessions = len(focus_docs)
        for f in focus_docs:
            focus_hours_total += f.get("duration_minutes", 0) / 60
        focus_hours_total = round(focus_hours_total, 1)
        if focus_sessions > 0:
            avg_focus_min = round((focus_hours_total * 60) / focus_sessions)
            context_used  = True
    except Exception:
        pass

    # 6. Prediction accuracy (AI vs actual time)
    prediction_accuracy = None
    accuracy_by_diff    = {}
    try:
        acc_docs = await db.task_history.find(
            {"user_id": user_id, "aiTime": {"$exists": True}, "actualTime": {"$exists": True}}
        ).to_list(200)
        if acc_docs:
            ratios = []
            by_diff: dict = {}
            for d in acc_docs:
                ai_t = d.get("aiTime", 0)
                ac_t = d.get("actualTime", 0)
                diff = d.get("difficulty", "medium")
                if ai_t > 0 and ac_t > 0:
                    r = ac_t / ai_t
                    ratios.append(r)
                    by_diff.setdefault(diff, []).append(r)
            if ratios:
                prediction_accuracy = round((sum(ratios) / len(ratios)) * 100)
                accuracy_by_diff    = {k: round((sum(v)/len(v))*100) for k, v in by_diff.items()}
    except Exception:
        pass

    # 7. Peak productivity hours
    peak_hours = []
    try:
        hour_counts: dict = {}
        hist2 = await db.task_history.find({"user_id": user_id}).to_list(200)
        for d in hist2:
            try:
                ts = d.get("created_at") or d.get("completed_at")
                if ts:
                    h = _dt.fromisoformat(str(ts)).hour
                    hour_counts[h] = hour_counts.get(h, 0) + 1
            except Exception:
                pass
        if hour_counts:
            sorted_hours = sorted(hour_counts.items(), key=lambda x: -x[1])
            peak_hours   = [h for h, _ in sorted_hours[:3]]
    except Exception:
        pass

    # 8. Performance index (composite score)
    performance_index = 0
    try:
        base = 0
        weight = 0
        if task_count > 0:
            base   += completion_rate * 0.4
            weight += 0.4
        if focus_sessions > 0:
            focus_score = min(100, focus_hours_total * 10)
            base   += focus_score * 0.3
            weight += 0.3
        if ai_schedules_count > 0:
            base   += 70 * 0.2      # having schedules = good habit
            weight += 0.2
        if streak > 0:
            streak_score = min(100, streak * 10)
            base   += streak_score * 0.1
            weight += 0.1
        if weight > 0:
            performance_index = round(base / weight)
    except Exception:
        pass

    # 9. Recent tasks (last 7 days) for trend
    recent_tasks_done = 0
    try:
        week_ago = now - timedelta(days=7)
        recent_tasks_done = await db.tasks.count_documents({
            "user_id": user_id,
            "completed": True,
            "created_at": {"$gte": week_ago},
        })
    except Exception:
        pass

    # ── Build rich context string for Gemini ──────────────────────────────────
    if not context_used:
        ctx_str = "Brand new user — no data yet. Give warm, encouraging, general productivity advice."
        data_summary = {}
    else:
        peak_str = (
            f"{', '.join([f'{h}:00' for h in peak_hours])} (these are their best hours)"
            if peak_hours else "not yet determined"
        )
        acc_str = (
            f"{prediction_accuracy}% (AI predictions vs actual time)"
            if prediction_accuracy else "not enough data yet"
        )
        acc_diff_str = (
            ", ".join([f"{k}: {v}%" for k, v in accuracy_by_diff.items()])
            if accuracy_by_diff else "N/A"
        )

        ctx_str = f"""REAL USER ANALYTICS (use these to personalise every answer):

TASK PERFORMANCE
- Total tasks created: {task_count}
- Tasks completed: {completed_count}
- Completion rate: {completion_rate}%
- Tasks completed this week: {recent_tasks_done}
- Tasks tracked in history: {history_count}
- Average actual task duration: {avg_actual_time}h
- Priority breakdown: {json.dumps(priority_breakdown)}
- Difficulty breakdown: {json.dumps(difficulty_breakdown)}

FOCUS & DEEP WORK
- Total focus hours logged: {focus_hours_total}h
- Number of focus sessions: {focus_sessions}
- Average session length: {avg_focus_min} minutes
{"- NOTE: User has 0 focus hours — this is a major improvement opportunity!" if focus_sessions == 0 else ""}

AI PLANNER USAGE
- AI schedules generated: {ai_schedules_count}
- Total tasks AI has planned: {ai_tasks_planned}

CONSISTENCY
- Current streak: {streak} days

AI PREDICTION ACCURACY
- Overall: {acc_str}
- By difficulty: {acc_diff_str}
{"- NOTE: Accuracy >100% means tasks take longer than AI predicted (user underestimates time)." if prediction_accuracy and prediction_accuracy > 100 else ""}
{"- NOTE: Accuracy <100% means user finishes tasks faster than AI predicted." if prediction_accuracy and prediction_accuracy < 95 else ""}

PEAK HOURS
- Most productive hours: {peak_str}

PERFORMANCE INDEX
- Composite score: {performance_index}/100
{"- Missing: Focus sessions (0 logged) — biggest gap to close." if focus_sessions == 0 else ""}
"""
        data_summary = {
            "task_count": task_count,
            "completion_rate": completion_rate,
            "focus_hours": focus_hours_total,
            "focus_sessions": focus_sessions,
            "streak": streak,
            "ai_schedules": ai_schedules_count,
            "prediction_accuracy": prediction_accuracy,
            "peak_hours": peak_hours,
            "performance_index": performance_index,
        }

    # ── For snapshot requests, return data only (no LLM call) ──────────────
    if question.strip() == "__snapshot__":
        return {
            "success":      True,
            "message":      "",
            "advice_points": [],
            "suggestions":  [],
            "context_used": context_used,
            "data_points":  task_count,
            "data_summary": data_summary if context_used else {},
            "type":         "snapshot",
        }

    # ── Shared system prompt ─────────────────────────────────────────────────
    coaching_system_prompt = f"""You are an expert productivity coach — like a combination of a behavioral psychologist, a time-management consultant, and a supportive mentor. You give advice the way a great human coach would: practical, evidence-based, warm, and direct.

CORE PHILOSOPHY
- Your advice draws from proven productivity science: deep work, time-blocking, Pomodoro technique, habit stacking, Parkinson's Law, the 2-minute rule, energy management, cognitive load theory, Eisenhower matrix, MoSCoW prioritisation, implementation intentions, and more.
- You treat the user as an intelligent adult who can apply real strategies — not just someone who needs to "use the app more."
- The user's data below is context that helps you personalise advice. It is NOT the advice itself.
- NEVER make the answer primarily about the app's features. Make it about the USER and what will genuinely help them in real life.
- When recommending techniques, explain WHY they work — briefly. People follow advice they understand.

PERSONALISATION RULES (use data as evidence, not as the recommendation)
- If completion rate is low → explain task sizing psychology, the planning fallacy, or Parkinson's Law. Suggest the 1-3-5 rule or time-boxing. Reference their % only to ground the tip.
- If focus hours are 0 → teach the Pomodoro method, the concept of deep work blocks, or distraction batching. Don't just say "use the focus timer."
- If streak is short → explain habit anchoring, the "never miss twice" rule, or implementation intentions ("I will do X at Y time in Z place"). Reference their streak to make it personal.
- If prediction accuracy is off → explain the planning fallacy, suggest padding buffers, reference their actual accuracy number.
- If peak hours are known → explain chronotypes and energy management, tell them to schedule their hardest work then.
- For stress / overwhelm → validate first, then suggest a brain dump, the "3 MITs" (Most Important Tasks) method, or the shutdown ritual.
- For procrastination → explain the neuropsychology briefly, suggest the 5-second rule, temptation bundling, or "eat the frog."

{ctx_str}

RESPONSE RULES
- Keep main message under 130 words — punchy, not padded.
- Give 2-4 concrete advice_points. Each should be a real technique the user can apply TODAY — in any area of their life, not just this app.
- advice_points should lead with the technique name, then one sentence on how to apply it to their situation.
- suggestions = 3 natural follow-up questions the user would actually want to ask next.
- Never start with "Great question!" or hollow affirmations.
- Never suggest a feature as the primary advice. Features can appear as a secondary tool at most.
- Return ONLY a valid JSON object. No markdown. No extra text.

JSON FORMAT:
{{{{
  "message": "<warm, specific, coaching response grounded in their data>",
  "advice_points": ["<technique name: how to apply it to their situation>", "<second technique>", "<third technique>"],
  "suggestions": ["<follow-up 1>", "<follow-up 2>", "<follow-up 3>"]
}}}}

advice_points can be [] for purely conversational messages."""

    def _parse_ai_response(raw):
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    # ── 1. Try Claude first (primary — no daily quota, generous rate limits) ──
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    if CLAUDE_API_KEY:
        try:
            import anthropic
            claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            claude_resp = claude_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=700,
                system=coaching_system_prompt,
                messages=[{"role": "user", "content": question}],
            )
            parsed = _parse_ai_response(claude_resp.content[0].text)
            return {
                "success":       True,
                "message":       parsed.get("message", "Ask me anything about your productivity."),
                "advice_points": parsed.get("advice_points", []),
                "suggestions":   parsed.get("suggestions", [
                    "What's my biggest productivity gap?",
                    "How can I improve my completion rate?",
                    "How do I build a focus habit?",
                ]),
                "context_used": context_used,
                "data_points":  task_count,
                "data_summary": data_summary,
                "type":         "advice",
            }
        except Exception as e:
            logger.error(f"Claude coaching call failed: {e}", exc_info=True)

    # ── 2. Fall back to Gemini (secondary) ───────────────────────────────────
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            full_prompt = f"{coaching_system_prompt}\n\nUser question: {question}"
            gemini_resp = gemini_client.models.generate_content(
                model="gemini-1.5-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(max_output_tokens=700, temperature=0.75),
            )
            parsed = _parse_ai_response(gemini_resp.text)
            return {
                "success":       True,
                "message":       parsed.get("message", "Ask me anything about your productivity."),
                "advice_points": parsed.get("advice_points", []),
                "suggestions":   parsed.get("suggestions", [
                    "What's my biggest productivity gap?",
                    "How can I improve my completion rate?",
                    "How do I build a focus habit?",
                ]),
                "context_used": context_used,
                "data_points":  task_count,
                "data_summary": data_summary,
                "type":         "advice",
            }
        except Exception as e:
            logger.error(f"Gemini coaching call failed: {e}", exc_info=True)

    # ── Smart rule-based fallback (no Gemini or Gemini failed) ───────────────
    q = question.lower()

    if any(w in q for w in ["productive", "improve", "better", "score", "result", "how am i", "my data", "analysis", "analyse", "analyze", "performance", "completion", "rate", "low", "why", "increase", "boost", "tips", "advice", "suggest", "help me", "what should"]):
        if context_used:
            weakest = []
            if focus_sessions == 0:
                weakest.append("Time-blocking: schedule a 25-minute deep work block today — you have 0 focus sessions logged, and structured time is the single fastest way to lift your score")
            if completion_rate < 70:
                weakest.append(f"Task sizing: your {completion_rate}% completion rate suggests tasks are too big — break each task into steps under 30 minutes using the '1-3-5 rule' (1 big, 3 medium, 5 small tasks per day)")
            if streak == 0:
                weakest.append("Habit anchoring: attach one small daily action to something you already do (e.g. 'After breakfast, I open my planner') — this builds streak without relying on motivation")
            msg = (
                f"Your performance index is {performance_index}/100. "
                f"You've completed {completed_count} of {task_count} tasks ({completion_rate}% rate), "
                f"logged {focus_hours_total}h of focus, and have a {streak}-day streak. "
                + (f"Biggest lever to pull: {weakest[0].split(':')[0]}." if weakest else "You're building solid habits — now it's about consistency.")
            )
            tips = weakest[:3] if weakest else [
                f"Raise the floor: at {completion_rate}% completion, aim for 85%+ by using the '1-3-5 rule' — plan 1 big task, 3 medium, 5 small each day",
                "Weekly review: every Sunday, spend 15 minutes reviewing what you finished and what blocked you — this alone improves follow-through by ~40%",
                "Energy management: match task difficulty to your energy level, not just your schedule. Hard tasks in peak hours, admin in low-energy slots.",
            ]
        else:
            msg = "No data yet — but the fundamentals work regardless. Start with three things: write down your top 3 tasks each morning (not 10, just 3), protect one 25-minute block from interruption, and review what you finished each evening."
            tips = [
                "The 1-3-5 rule: each day, commit to 1 big task, 3 medium tasks, 5 small tasks — no more. Constraints create focus.",
                "Implementation intention: decide now 'I will work on [task] at [time] in [place]' — this increases follow-through by 2-3x vs vague intentions.",
                "Evening shutdown ritual: spend 5 minutes at day's end noting what's done and writing tomorrow's top 3 — this reduces next-morning friction dramatically.",
            ]
    elif any(w in q for w in ["focus", "distract", "concentrat", "deep work"]):
        if focus_sessions == 0:
            msg = f"With 0 logged focus sessions, you're likely working in reactive mode — switching tasks as things come up. The fix isn't willpower, it's structure. Try time-blocking: pick one task, set a 25-minute timer, and treat that block as non-negotiable." + (f" Your data shows your best hours may be around {peak_hours[0]}:00 — that's your prime slot." if peak_hours else "")
        else:
            msg = f"You've built {focus_sessions} focus sessions ({focus_hours_total}h total) — that's a real habit forming. Now deepen it: longer blocks (50 min work / 10 min break) unlock deeper thinking than short ones."
        tips = [
            "Pomodoro technique: 25 min focused work, 5 min break — repeat 4 cycles, then take a 20 min break. The timer creates urgency that crushes procrastination.",
            "Distraction batching: check messages only at fixed times (e.g. 12pm and 5pm). Random checking costs 23 minutes of recovery per interruption.",
            "Environment design: put your phone in another room. Out of sight reduces usage by 30% without any willpower needed." + (f" Schedule deep work at {peak_hours[0]}:00 — your peak hour from your data." if peak_hours else ""),
        ]
    elif any(w in q for w in ["procrastinat", "lazy", "motivat", "start", "begin", "cant start", "difficult to start"]):
        msg = "Procrastination is almost never laziness — it's usually fear of failure, perfectionism, or a task that's too vague to start. The fix is making the first step so small it's impossible to say no to."
        tips = [
            "The 5-minute rule: tell yourself you'll work for just 5 minutes, then stop if you want. You almost never stop — starting is the hardest part.",
            "Shrink the task: if you can't start, the task is too big. Break it down until the next step takes under 10 minutes. 'Write essay' → 'Write one sentence of the intro'.",
            "Temptation bundling: pair the task you're avoiding with something you enjoy (specific playlist, favourite drink, comfortable spot). Your brain starts associating the task with reward.",
        ]
    elif any(w in q for w in ["stress", "anxious", "overwhelm", "pressure", "exam", "worried", "burnout", "tired"]):
        msg = "Feeling overwhelmed is a signal your system needs restructuring, not more effort. The brain can only hold 7 things in working memory — when everything feels urgent, nothing gets done."
        tips = [
            "Brain dump: spend 10 minutes writing every task, worry, and obligation on paper. Getting it out of your head and onto paper reduces anxiety immediately and lets you see what's actually there.",
            "Pick your MIT: from that list, choose your 1 Most Important Task for today. Just one. Do that first before anything else.",
            "7-8 hours of sleep beats an extra hour of studying every time — sleep is when your brain consolidates learning and restores decision-making capacity.",
        ]
    elif any(w in q for w in ["streak", "consistent", "habit", "daily"]):
        if streak > 0:
            msg = f"You're on a {streak}-day streak — that's real momentum. Neuroscience backs this: each repetition strengthens the neural pathway, making the next day easier. The goal now is 'never miss twice' — one missed day is a mistake, two is a new habit."
        else:
            msg = "No streak yet — but streaks are built with identity, not motivation. Start by asking 'what would a productive person do today?' and do just that one thing. Day 1 is the hardest; day 2 is easier."
        tips = [
            "Habit anchoring: attach your daily planning to something you already do every day (e.g. 'After morning coffee, I write my 3 tasks') — this removes the decision of when.",
            "The 'never miss twice' rule: missing once is human; missing twice is starting a bad habit. If you miss, your only job is to show up tomorrow.",
            f"Make it tiny: a 2-minute micro-habit (write one task) counts as a streak day and keeps the chain alive. At {streak} days — aim for 7, then 21.",
        ]
    elif any(w in q for w in ["accuracy", "prediction", "ai time", "estimate"]):
        if prediction_accuracy:
            over = prediction_accuracy > 100
            msg = (
                f"Your AI prediction accuracy is {prediction_accuracy}%. "
                + ("The AI slightly overestimates your task time — you're a fast executor. Use this: when you think a task will take 2 hours, try scheduling 1.5h and use the pressure positively." if not over else
                   f"Tasks are taking longer than predicted ({prediction_accuracy}% of estimated time) — this is the planning fallacy: humans chronically underestimate time needed, especially for complex tasks.")
            )
            tips = [
                "Add a 25% buffer: whatever time you think a task takes, add 25%. This single habit eliminates most schedule overruns." if over else "Use your speed: since you finish faster than planned, batch similar small tasks together for a satisfying high-completion day.",
                "Segment before estimating: break tasks into sub-steps, estimate each sub-step, then add them up. This is 40% more accurate than estimating the whole task.",
                "Track your actual vs planned time for 2 weeks consciously — the awareness itself improves future estimates significantly.",
            ]
        else:
            msg = "No prediction data yet. The most common mistake in time management is the planning fallacy — we all underestimate how long things take. A simple fix: always add a 25% buffer to your time estimates."
            tips = ["Add a 25% time buffer to every estimate — it's the single most effective scheduling habit", "Break tasks into sub-steps before estimating — step-level estimates are far more accurate than whole-task guesses", "Track actual vs planned time for 1 week — the awareness alone improves your estimates"]
    else:
        if context_used:
            # Give genuinely useful advice based on their weakest area
            if focus_sessions == 0:
                msg = f"Looking at your data ({completion_rate}% completion, {focus_hours_total}h focus, {streak}-day streak), the biggest unlock is structured focus time. Most productivity problems aren't about effort — they're about working in reactive mode instead of intentional blocks."
                tips = [
                    "Pomodoro technique: set a 25-minute timer, work on ONE task only, then 5-minute break. The constraint creates urgency that defeats procrastination.",
                    "Time-blocking: assign specific tasks to specific time slots in your day — don't just have a to-do list, have a schedule.",
                    "Phone in another room during work blocks — out of sight reduces distractions by ~30% without any willpower.",
                ]
            elif completion_rate < 70:
                msg = f"Your data shows {completion_rate}% completion — the most common cause isn't laziness, it's task sizing. When tasks are too vague or too big, your brain resists starting them."
                tips = [
                    "2-minute rule: if defining the next action takes less than 2 minutes, do it immediately. Vague tasks ('work on project') become specific ones ('write intro paragraph').",
                    "The 1-3-5 rule: each day plan exactly 1 big task, 3 medium, 5 small. This forces prioritisation and creates realistic daily targets.",
                    "Never put 'Study' or 'Work on X' on your list — always write the specific next physical action: 'Read pages 10-30', 'Write 200 words of section 2'.",
                ]
            else:
                msg = f"You're at {completion_rate}% completion with a {streak}-day streak — solid foundation. The next level is about deepening quality, not just quantity."
                tips = [
                    "Weekly review: every Sunday, 15 minutes reviewing what you finished, what blocked you, and your top 3 priorities for the coming week. This alone improves output significantly.",
                    "Energy management: schedule your hardest task during your peak energy hours, not just whenever — most people waste their best hours on email.",
                    "The shutdown ritual: at day's end, write tomorrow's top 3 tasks and say 'shutdown complete'. This stops work thoughts from bleeding into rest time.",
                ]
        else:
            msg = "The fundamentals of productivity work regardless of where you are. Start here: each morning write your top 3 tasks (not 10, just 3), protect one 25-minute block from all interruptions, and do a 5-minute review each evening."
            tips = [
                "The 1-3-5 rule: commit to 1 big task, 3 medium, 5 small per day — constraints create focus.",
                "Implementation intention: 'I will do [task] at [time] in [place]' — this phrasing increases follow-through by 2-3x vs vague plans.",
                "Evening shutdown ritual: 5 minutes at day's end reviewing what's done and writing tomorrow's top 3 reduces next-morning friction dramatically.",
            ]

    return {
        "success":      True,
        "message":      msg,
        "advice_points": tips,
        "suggestions":  [
            "What's my biggest productivity gap right now?",
            "How can I improve my focus?",
            "How do I beat procrastination?",
        ],
        "context_used": context_used,
        "data_points":  task_count,
        "data_summary": data_summary if context_used else {},
        "type":         "advice",
    }