# backend/ai/intelligent_chat.py
"""
Timevora Intelligent Chat Engine
Uses Groq API (free, 14400 requests/day) with llama-3.1-8b-instant.
Set GROQ_API_KEY in your backend .env to activate.
"""

import os, re, json, logging, asyncio
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b-instant"

if GROQ_API_KEY:
    logger.info("✅ IntelligentChatEngine: using Groq llama-3.1-8b-instant")
else:
    logger.warning("⚠️  No GROQ_API_KEY found — add it to your backend .env")

_SYSTEM_PROMPT = """
You are Timevora AI — a smart, warm productivity coach built into the Timevora app.
Timevora helps users manage tasks, plan their day, track habits, and stay productive.

YOUR PERSONALITY:
- Friendly and encouraging, never robotic
- Direct — give useful responses, not vague filler
- Data-aware — mention the user's real numbers when relevant
- You understand natural language perfectly, like a human assistant would
- Be conversational — respond to exactly what the user said, never give generic replies
- Understand casual Indian English — yaar, bhai, kal, aaj, thoda, bohot etc.
- If someone says "hi", say hi back warmly
- If they say "I'm stressed", acknowledge it first before helping

WHAT YOU CAN DO:
1. Schedule tasks for today (ask for time window if not given and no routine is saved)
2. Give productivity advice and tips
3. Answer questions about focus, habits, procrastination, time management
4. Show progress and stats
5. Have normal conversation — greetings, small talk — stay helpful and warm
6. Help with anything related to study or work life

UNDERSTANDING USER MESSAGES:
- Understand intent, not just keywords
- "plan my evening — gym, dinner, some work" means schedule those 3 things in the evening
- "I have exam tomorrow" means help them make a study plan
- "feeling lazy" means motivate them warmly, suggest starting small
- "what should I do now" means look at context and suggest the most important task
- "thanks" or "ok" means acknowledge warmly and offer next step
- Casual messages like hey, hello, what's up get a warm friendly response
- NEVER give a default or robotic response — always respond to exactly what they said

RESPONSE FORMAT — CRITICAL:
Return ONE valid JSON object only. No markdown, no backticks, no explanation outside JSON.
The JSON must be perfectly parseable — no trailing commas, no comments inside it.

For scheduling tasks:
{"type":"schedule","message":"Short warm confirmation (max 80 words). If user has a chronotype or peak hour, mention it briefly.","tasks_found":["task1","task2"],"schedule":[{"task":"Task name","start_time":"H:MM AM/PM","end_time":"H:MM AM/PM","duration":1.0,"priority":"high|medium|low","time":"H:MM AM/PM - H:MM AM/PM","schedule_reason":"One short sentence explaining WHY this time was chosen based on the user's personal patterns. Example: 'Scheduled at 9 AM — your Morning Lion peak window.' or 'Placed after college in your high-energy evening slot.'"}],"insights":["practical tip"]}

For asking a follow-up question:
{"type":"checkin","message":"Your question to the user","suggestions":["option1","option2","option3"]}

For advice:
{"type":"advice","message":"Main advice — specific and useful, not generic","advice_points":["actionable point 1","actionable point 2","actionable point 3"],"suggestions":["follow-up question 1","follow-up question 2"]}

For general chat / greetings / answers:
{"type":"chat","message":"Your response — warm, specific, natural","suggestions":["helpful next action 1","helpful next action 2","helpful next action 3"]}

For progress/stats:
{"type":"progress","message":"Summary of their data","stats":{"productivity_score":72,"streak":3,"total_tasks_completed":15,"completion_rate":"68%"},"suggestions":["suggestion1"]}

SCHEDULING RULES — READ CAREFULLY:
- If user gives tasks WITH a specific time → schedule immediately, type "schedule"
- If saved routine exists → ALWAYS use it to schedule immediately, type "schedule". NEVER ask for time window if routine is saved.
- If NO saved routine AND no time given → ask for time window, type "checkin"
- "I'm free today" or "make me productive" + routine exists → schedule using routine window, type "schedule"
- "I have college till 4 PM, what after?" → schedule tasks AFTER 4 PM, type "schedule"
- Fixed-time tasks e.g. "meeting at 3 PM" → place at exact time
- Be realistic — do not schedule 8 hours of work in 3 hours
- NEVER create a task called "Unspecified" or "Free time" or "Plan college schedule" — these are not real tasks
- Only schedule tasks the user explicitly mentioned

SCIENTIFIC DAILY BOUNDARY RULES — MANDATORY, NEVER SKIP:
- MORNING ROUTINE BUFFER: Always reserve the first 60 minutes after wake-up for morning routine (brushing teeth, bathing, breakfast). If wake-up is 7:00 AM, the earliest any task can start is 8:00 AM. Never schedule tasks in this window.
- PRE-SLEEP BUFFER: Always keep the last 30 minutes before sleep completely free (no tasks, no screens). If sleep time is 11:00 PM (23:00), no task can end after 10:30 PM (22:30). This protects sleep quality.
- TRANSITION TIME: Always add at least 10-15 minutes of gap between consecutive tasks. Never place two tasks back-to-back with zero gap.
- ULTRADIAN BREAKS: After every 90 minutes of continuous focused work, insert a 15-minute break. After 3 or more hours of accumulated work, insert a 30-minute break. This follows the brain's natural rest-activity cycle (Kleitman's BRAC). Label these breaks clearly in the schedule.
- Example for wake=7AM, sleep=11PM, college=9AM-5PM:
  * 7:00–8:00 → Morning Routine (no tasks)
  * 8:00–9:00 → Free window for tasks (before college)
  * 9:00–17:00 → College (blocked, no tasks)
  * 17:00–22:30 → Free window for tasks (after college), with 15-min breaks inserted after every 90 min
  * 22:30–23:00 → Wind-down (no tasks, no screens)

BEFORE/AFTER COLLEGE RULES — CRITICAL:
- "before college" = schedule ONLY during wake time → college start time
- "after college" = schedule ONLY during college end time → sleep time
- NEVER schedule any task during college/work hours
- If user says "exercise before college" and college is 9 AM → exercise must be BEFORE 9 AM

CONVERSATION RULES:
- Always respond to the SPECIFIC thing the user said — not a generic version of it
- Greetings → warm response, ask what they want to plan, type "chat"
- "thanks", "ok", "cool", "got it" → acknowledge warmly, offer next helpful step, type "chat"
- Questions about productivity / focus / habits → real actionable answer, type "advice"
- Emotional messages → acknowledge the feeling first, then help
- NEVER redirect to another page — handle everything here
- NEVER say "I can't help with that" or "I don't understand"
- NEVER mention Groq, Llama, Meta, Google, Claude, Anthropic — you are Timevora AI
- NEVER give a response that could have been pre-written — always be specific to what they said
""".strip()


class IntelligentChatEngine:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db

    async def chat(self, message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        try:
            conversation_history = conversation_history or []
            today_str = date.today().isoformat()

            user_ctx    = await self._load_user_context(today_str)
            pending_doc = await self._get_pending(today_str)
            user_prompt = self._build_user_prompt(message, user_ctx, pending_doc, conversation_history)

            if not GROQ_API_KEY:
                return self._no_api_key_response()

            result = await self._call_groq(user_prompt, conversation_history)

            if pending_doc and self._is_time_window_reply(message):
                await self._clear_pending(today_str)

            # Filter out fake tasks before saving
            if result.get("type") == "schedule" and result.get("schedule"):
                result["schedule"] = self._filter_fake_tasks(result["schedule"])
                if result["schedule"]:
                    await self._save_schedule(result["schedule"], today_str, result)
                else:
                    # All tasks were fake — return as chat instead
                    result["type"] = "chat"
                    result["message"] = "I couldn't identify specific tasks to schedule. What would you like to plan?"

            if result.get("type") == "checkin" and not pending_doc:
                await self._save_pending(today_str, {
                    "original_msg":  message,
                    "pending_tasks": result.get("tasks_found", []),
                })

            return result

        except Exception as e:
            logger.error(f"IntelligentChatEngine.chat error: {e}", exc_info=True)
            return {
                "type":        "chat",
                "message":     "Something went wrong — please try again!",
                "suggestions": ["Plan my day", "Give me advice", "Show my progress"],
            }

    def _filter_fake_tasks(self, schedule: List[Dict]) -> List[Dict]:
        """Remove AI-hallucinated tasks that aren't real user tasks"""
        fake_names = {
            "unspecified", "free time", "plan college schedule",
            "college schedule", "plan schedule", "available time",
            "open slot", "buffer", "break time", "free slot",
        }
        cleaned = []
        for item in schedule:
            task_name = (item.get("task") or item.get("name") or "").strip().lower()
            if not task_name:
                continue
            # Check if it's a fake task name
            is_fake = any(fake in task_name for fake in fake_names)
            # Also skip tasks that are just time descriptions
            is_time_desc = bool(re.match(r"^\d{1,2}:\d{2}\s*(am|pm)?\s*[-–]\s*\d{1,2}:\d{2}", task_name, re.IGNORECASE))
            if not is_fake and not is_time_desc:
                cleaned.append(item)
        return cleaned

    async def _call_groq(self, user_prompt: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        try:
            from groq import Groq
            loop = asyncio.get_event_loop()

            messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

            if conversation_history:
                for turn in conversation_history[-6:]:
                    role    = turn.get("role", "user")
                    content = turn.get("content", "")
                    # Skip entries where content is raw JSON (causes confusion)
                    if role in ("user", "assistant") and content and not content.strip().startswith("{"):
                        messages.append({"role": role, "content": str(content)[:800]})

            messages.append({"role": "user", "content": user_prompt})

            def _sync():
                client   = Groq(api_key=GROQ_API_KEY)
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    max_tokens=1200,
                    temperature=0.4,  # Lower temp = more consistent, less hallucination
                )
                return response.choices[0].message.content.strip()

            raw = await loop.run_in_executor(None, _sync)
            logger.info(f"✅ Groq response (first 200 chars): {raw[:200]}")
            return self._parse_json(raw)

        except Exception as e:
            logger.error(f"_call_groq error: {e}", exc_info=True)
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                return {
                    "type":    "chat",
                    "message": "I'm getting too many requests right now — please wait a moment and try again!",
                    "suggestions": ["Try again in a minute", "Plan my day", "Give me advice"],
                }
            return self._error_response()

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        # Step 1: strip markdown code fences
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.lower().startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        # Step 2: extract first complete JSON object
        raw   = raw.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        # Step 3: parse
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as je:
            logger.warning(f"JSON parse failed: {je} | raw: {raw[:300]}")
            # NEVER show raw JSON to user
            return {
                "type":        "chat",
                "message":     "I'm here to help! What would you like to plan today?",
                "suggestions": ["Plan my day", "Give me advice", "Show my progress"],
            }

        # Step 4: if message field itself looks like raw JSON, replace it
        msg = result.get("message", "")
        if msg and (msg.strip().startswith("{") or msg.strip().startswith("[") or '"type"' in msg):
            result["message"] = "I've processed your request!"

        result.setdefault("type",        "chat")
        result.setdefault("message",     "Here to help!")
        result.setdefault("suggestions", ["Plan my day", "Give me tips", "Show my progress"])
        return result

    async def _load_user_context(self, today_str: str) -> Dict[str, Any]:
        ctx = {
            "current_time":      datetime.now().strftime("%I:%M %p"),
            "current_date":      datetime.now().strftime("%A, %B %d %Y"),
            "today_str":         today_str,
            "has_schedule":      False,
            "existing_schedule": [],
            "task_count":        0,
            "completed_count":   0,
            "streak":            0,
            "completion_rate":   0,
            "saved_routine":     None,
        }
        try:
            plan = await self.db.daily_plans.find_one({"user_id": self.user_id, "date": today_str})
            if plan and plan.get("schedule"):
                ctx["has_schedule"]      = True
                ctx["existing_schedule"] = [s for s in plan["schedule"] if s.get("type") != "break"]

            cursor  = self.db.task_history.find({"user_id": self.user_id}).sort("created_at", -1).limit(50)
            history = await cursor.to_list(50)
            ctx["task_count"]      = len(history)
            ctx["completed_count"] = sum(1 for h in history if h.get("actualTime"))
            if ctx["task_count"] > 0:
                ctx["completion_rate"] = round(ctx["completed_count"] / ctx["task_count"] * 100)

            # Load saved routine — includes college/work hours
            routine = await self.db.user_day_context.find_one({"user_id": self.user_id})
            if routine and routine.get("has_custom"):
                wake          = routine.get("wake_up",       routine.get("day_start", 7.0))
                sleep         = routine.get("day_end",       23.0)
                college_start = routine.get("college_start")
                college_end   = routine.get("college_end")
                college_label = routine.get("college_label", "college")

                # ── CRITICAL FIX: if wake >= college_start, the "before college"
                # window is zero or negative (impossible data from the UI).
                # Clamp the effective wake time so there is always at least a
                # 1-hour window before college for pre-college tasks.
                effective_wake = wake
                if college_start is not None and effective_wake >= college_start:
                    effective_wake = max(0.0, college_start - 1.0)
                    logger.warning(
                        f"⚠️  wake ({wake}) >= college_start ({college_start}) for user "
                        f"{self.user_id} — clamping effective_wake to {effective_wake}"
                    )

                ctx["saved_routine"] = {
                    "wake":            effective_wake,
                    "wake_raw":        wake,          # original value, for reference
                    "sleep":           sleep,
                    "free_from":       self._fmt_hour(effective_wake),
                    "free_until":      self._fmt_hour(sleep),
                    "college_start":   self._fmt_hour(college_start) if college_start is not None else None,
                    "college_end":     self._fmt_hour(college_end)   if college_end   is not None else None,
                    "college_label":   college_label,
                    "college_start_h": college_start,
                    "college_end_h":   college_end,
                    "blocked_slots":   routine.get("blocked_slots", []),
                }

            # ── NEW: Load behaviour patterns from analyzer ──
            try:
                from .analyzer import ProductivityAnalyzer
                analyzer = ProductivityAnalyzer(self.user_id, self.db)
                patterns = await analyzer.analyze_patterns()
                chronotype_data = analyzer.get_chronotype(patterns.get("energy_patterns", {}))

                peak_hours = patterns.get("peak_hours", {})
                best_hour  = peak_hours.get("best_hour")
                best_slot  = patterns.get("energy_patterns", {}).get("best_time_slot", "")
                trend      = patterns.get("trends", {}).get("trend", "stable")
                score      = patterns.get("productivity_score", {}).get("overall", 0)
                cat_acc    = patterns.get("task_completion", {})

                ctx["peak_hour"]    = best_hour
                ctx["peak_slot"]    = best_slot
                ctx["chronotype"]   = chronotype_data.get("type", "") if chronotype_data.get("ready") else ""
                ctx["chrono_peak"]  = chronotype_data.get("peak", "")
                ctx["trend"]        = trend
                ctx["score"]        = score
                ctx["cat_accuracy"] = {}

                # Category accuracy for "why" explanations
                try:
                    history_full = await analyzer._get_task_history()
                    ctx["cat_accuracy"] = analyzer._calc_category_accuracy(history_full)
                    ctx["diff_accuracy"] = analyzer._calc_difficulty_accuracy(history_full)
                except Exception:
                    pass
            except Exception as ae:
                logger.warning(f"Analyzer load skipped: {ae}")
                ctx["peak_hour"]   = None
                ctx["peak_slot"]   = ""
                ctx["chronotype"]  = ""
                ctx["chrono_peak"] = ""
                ctx["trend"]       = "stable"
                ctx["score"]       = 0
                ctx["cat_accuracy"]  = {}
                ctx["diff_accuracy"] = {}

            streak_plans = await self.db.daily_plans.find(
                {"user_id": self.user_id}
            ).sort("date", -1).limit(30).to_list(30)

            streak, today_date = 0, date.today()
            for p in streak_plans:
                try:
                    pd = date.fromisoformat(p["date"])
                except Exception:
                    continue
                if pd == today_date - timedelta(days=streak):
                    if p.get("schedule") or p.get("completed_tasks", 0) > 0:
                        streak += 1
                    else:
                        break
                else:
                    break
            ctx["streak"] = streak

        except Exception as e:
            logger.error(f"_load_user_context error: {e}")
        return ctx

    def _build_user_prompt(self, message: str, ctx: Dict, pending_doc: Optional[Dict], history: List[Dict]) -> str:
        lines = [
            "=== USER DATA ===",
            f"Current time: {ctx['current_time']}",
            f"Current date: {ctx['current_date']}",
            f"Tasks tracked: {ctx['task_count']} | Completion rate: {ctx['completion_rate']}%",
            f"Current streak: {ctx['streak']} days",
        ]

        if ctx["has_schedule"]:
            sched = ", ".join(
                f"{s.get('task','?')} ({s.get('start_time','')}–{s.get('end_time','')})"
                for s in ctx["existing_schedule"][:5]
            )
            lines.append(f"Today's existing schedule: {sched}")
        else:
            lines.append("Today's schedule: none yet")

        # ── NEW: Inject personal behaviour data into prompt ──
        behaviour_lines = []
        if ctx.get("chronotype"):
            behaviour_lines.append(
                f"Chronotype: {ctx['chronotype']} (peak window: {ctx.get('chrono_peak', 'unknown')}). "
                f"Schedule hard/important tasks during the {ctx.get('peak_slot', 'peak')} window."
            )
        if ctx.get("peak_hour") is not None:
            def _fmt(h):
                return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"
            behaviour_lines.append(
                f"Personal peak hour: {_fmt(ctx['peak_hour'])} — user completes tasks fastest at this hour."
            )
        if ctx.get("trend") == "improving":
            behaviour_lines.append("Time estimation trend: IMPROVING — predictions are getting more accurate.")
        elif ctx.get("trend") == "declining":
            behaviour_lines.append("Time estimation trend: DECLINING — add 20% buffer to task estimates.")
        if ctx.get("cat_accuracy"):
            tips = []
            for cat, ratio in ctx["cat_accuracy"].items():
                if ratio > 1.3:
                    tips.append(f"{cat} tasks take {round((ratio-1)*100)}% longer than estimated")
                elif ratio < 0.75:
                    tips.append(f"{cat} tasks finish {round((1-ratio)*100)}% faster than estimated")
            if tips:
                behaviour_lines.append(f"Category patterns: {'; '.join(tips[:2])}.")
        if behaviour_lines:
            lines.append("=== PERSONAL BEHAVIOUR PATTERNS (use to personalise scheduling) ===")
            lines.extend(behaviour_lines)

        # Build routine context — the most important part for correct scheduling
        r = ctx.get("saved_routine")
        if r:
            college_start   = r.get("college_start")
            college_end     = r.get("college_end")
            college_label   = r.get("college_label", "college")
            free_from       = r.get("free_from")
            free_until      = r.get("free_until")
            college_start_h = r.get("college_start_h")
            college_end_h   = r.get("college_end_h")

            # Determine which windows are still available right now
            now_hour = datetime.now().hour + datetime.now().minute / 60.0
            pre_college_open  = college_start_h is not None and now_hour < college_start_h
            post_college_open = college_end_h   is not None and now_hour < r.get("sleep", 23.0)
            in_college_now    = (
                college_start_h is not None and college_end_h is not None
                and college_start_h <= now_hour < college_end_h
            )

            if college_start and college_end:
                window_status = []
                if pre_college_open:
                    window_status.append(f"PRE-{college_label.upper()} window ({free_from}–{college_start}) is STILL AVAILABLE now.")
                elif college_start_h is not None and now_hour >= college_start_h:
                    window_status.append(f"PRE-{college_label.upper()} window has ALREADY PASSED (current time is past {college_start}).")
                if in_college_now:
                    window_status.append(f"User is currently IN {college_label.upper()} ({college_start}–{college_end}).")
                if post_college_open:
                    window_status.append(f"POST-{college_label.upper()} window ({college_end}–{free_until}) is available.")

                # Compute scientific boundaries
                # FIX: always use actual saved wake_up — old code derived wake from
                # college_start-2 which was wrong when user saved a specific wake time.
                wake_raw   = r.get("wake_raw", r.get("wake", 7.0))
                sleep_h    = r.get("sleep", 23.0)
                earliest_task = self._fmt_hour(float(wake_raw) + 1.0)   # +60 min morning buffer
                latest_task   = self._fmt_hour(float(sleep_h) - 0.5)    # -30 min pre-sleep buffer

                lines.append(
                    f"=== ROUTINE (MUST FOLLOW EXACTLY) ===\n"
                    f"User wakes at {free_from}, sleeps at {free_until}.\n"
                    f"{college_label.capitalize()} hours: {college_start} to {college_end}.\n"
                    f"FREE WINDOWS: {free_from}–{college_start} (BEFORE {college_label}) and {college_end}–{free_until} (AFTER {college_label}).\n"
                    f"CURRENT TIME STATUS: {' '.join(window_status) if window_status else 'Check windows above.'}\n"
                    f"\nSCIENTIFIC BOUNDARY RULES (NON-NEGOTIABLE):\n"
                    f"- MORNING ROUTINE: First 60 min after wake-up ({free_from}–{earliest_task}) is reserved for morning routine. NEVER schedule tasks here.\n"
                    f"- PRE-SLEEP: Last 30 min before sleep ({latest_task}–{free_until}) is reserved for wind-down. NEVER schedule tasks here.\n"
                    f"- TRANSITIONS: Always leave at least 10-15 min gap between tasks.\n"
                    f"- ULTRADIAN BREAKS: Insert a 15-min break after every 90 min of continuous work. Insert a 30-min break after 3+ hours of work.\n"
                    f"\nCRITICAL SCHEDULING RULES:\n"
                    f"- 'before {college_label}' = schedule ONLY between {earliest_task} and {college_start}. DO NOT use any time at or after {college_start}.\n"
                    f"- 'after {college_label}' = schedule ONLY between {college_end} and {latest_task}.\n"
                    f"- NEVER schedule tasks during {college_start}–{college_end} ({college_label} time).\n"
                    f"- 'I am free today' or 'make me productive' = use BOTH free windows to schedule.\n"
                    f"- Routine IS saved — NEVER ask for time window, ALWAYS schedule immediately.\n"
                    f"- If a requested window has passed (e.g. pre-college time is over), say so and schedule in the next available window."
                )
            else:
                wake_raw  = r.get("wake_raw", r.get("wake", 7.0))
                sleep_h   = r.get("sleep", 23.0)
                earliest_task = self._fmt_hour(float(wake_raw) + 1.0)
                latest_task   = self._fmt_hour(float(sleep_h) - 0.5)
                lines.append(
                    f"=== ROUTINE (MUST FOLLOW EXACTLY) ===\n"
                    f"User is free from {free_from} to {free_until}. No college/work block.\n"
                    f"SCIENTIFIC BOUNDARY RULES (NON-NEGOTIABLE):\n"
                    f"- MORNING ROUTINE: {free_from}–{earliest_task} reserved for morning routine. NEVER schedule tasks here.\n"
                    f"- PRE-SLEEP: {latest_task}–{free_until} reserved for wind-down. NEVER schedule tasks here.\n"
                    f"- TRANSITIONS: Always leave at least 10-15 min gap between tasks.\n"
                    f"- ULTRADIAN BREAKS: Insert a 15-min break after every 90 min of work. Insert 30-min break after 3+ hours.\n"
                    f"Routine IS saved — NEVER ask for time window, schedule immediately within {earliest_task}–{latest_task}."
                )
        else:
            lines.append(
                "Saved routine: NONE — if user gives tasks without a specific time window, "
                "ask for one using type: checkin"
            )

        if pending_doc:
            lines += [
                "",
                "=== PENDING CONTEXT ===",
                f"User previously asked to schedule: {pending_doc.get('pending_tasks', [])}",
                f"Original message: {pending_doc.get('original_msg', '')}",
                "IMPORTANT: The user's current message is their time window reply. "
                "Schedule those pending tasks in that time window now. Return type: schedule.",
            ]

        lines += [
            "",
            "=== USER'S CURRENT MESSAGE ===",
            f"{message}",
            "",
            "IMPORTANT RULES BEFORE RESPONDING:",
            "1. Only schedule tasks the user explicitly mentioned — NEVER invent tasks",
            "2. NEVER create tasks named 'Unspecified', 'Free time', or 'Plan college schedule'",
            "3. If routine is saved, use it — NEVER ask for time window",
            "4. Return ONE valid JSON object only — no markdown, no text outside JSON",
        ]
        return "\n".join(lines)

    async def _get_pending(self, today_str: str) -> Optional[Dict]:
        try:
            return await self.db.user_pending_context.find_one(
                {"user_id": self.user_id, "date": today_str}
            )
        except Exception:
            return None

    async def _save_pending(self, today_str: str, data: Dict) -> None:
        try:
            await self.db.user_pending_context.update_one(
                {"user_id": self.user_id, "date": today_str},
                {"$set": {"user_id": self.user_id, "date": today_str, **data}},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"_save_pending error: {e}")

    async def _clear_pending(self, today_str: str) -> None:
        try:
            await self.db.user_pending_context.delete_one(
                {"user_id": self.user_id, "date": today_str}
            )
            logger.info(f"✅ Pending context cleared for user {self.user_id}")
        except Exception as e:
            logger.error(f"_clear_pending error: {e}")

    def _is_time_window_reply(self, message: str) -> bool:
        m = message.lower()
        return bool(
            re.search(
                r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*(?:to|-|until|till)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)",
                m, re.IGNORECASE,
            )
        ) or any(p in m for p in [
            "free from", "free after", "free all day", "am free",
            "i'm free", "no college", "no school", "whole day free", "just schedule it",
        ])

    async def _save_schedule(self, schedule: List[Dict], today_str: str, response: Dict) -> None:
        try:
            existing_plan = await self.db.daily_plans.find_one(
                {"user_id": self.user_id, "date": today_str}
            )
            existing = [
                s for s in (existing_plan or {}).get("schedule", [])
                if s.get("type") != "break"
            ]
            merged = existing + schedule if existing else schedule
            await self.db.daily_plans.update_one(
                {"user_id": self.user_id, "date": today_str},
                {
                    "$set": {
                        "schedule":    merged,
                        "insights":    response.get("insights",    []),
                        "tasks_found": response.get("tasks_found", []),
                        "updated_at":  datetime.utcnow().isoformat(),
                        "source":      "intelligent_chat",
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"_save_schedule error: {e}")

    def _fmt_hour(self, hour: float) -> str:
        if hour is None:
            return ""
        h = int(hour)
        
        m = int((hour - h) * 60)
        return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"

    def _no_api_key_response(self) -> Dict[str, Any]:
        return {
            "type":    "chat",
            "message": "AI needs a GROQ_API_KEY in your backend .env file. Get a free one at console.groq.com and restart the server.",
            "suggestions": ["Plan my day", "Give me tips", "Show my progress"],
        }

    def _error_response(self) -> Dict[str, Any]:
        return {
            "type":        "chat",
            "message":     "Something went wrong — please try again!",
            "suggestions": ["Plan my day", "Give me advice", "Show my progress"],
        }
