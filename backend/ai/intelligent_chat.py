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
{"type":"schedule","message":"Short warm confirmation (max 80 words)","tasks_found":["task1","task2"],"schedule":[{"task":"Task name","start_time":"H:MM AM/PM","end_time":"H:MM AM/PM","duration":1.0,"priority":"high|medium|low","time":"H:MM AM/PM - H:MM AM/PM"}],"insights":["practical tip"]}

For asking a follow-up question:
{"type":"checkin","message":"Your question to the user","suggestions":["option1","option2","option3"]}

For advice:
{"type":"advice","message":"Main advice — specific and useful, not generic","advice_points":["actionable point 1","actionable point 2","actionable point 3"],"suggestions":["follow-up question 1","follow-up question 2"]}

For general chat / greetings / answers:
{"type":"chat","message":"Your response — warm, specific, natural","suggestions":["helpful next action 1","helpful next action 2","helpful next action 3"]}

For progress/stats:
{"type":"progress","message":"Summary of their data","stats":{"productivity_score":72,"streak":3,"total_tasks_completed":15,"completion_rate":"68%"},"suggestions":["suggestion1"]}

SCHEDULING RULES:
- Tasks WITH time window → schedule immediately, type "schedule"
- Tasks WITHOUT time window AND no saved routine → ask for time window, type "checkin"
- Saved routine exists → use it to schedule immediately, type "schedule"
- Fixed-time tasks e.g. "meeting at 3 PM" → place at that exact time
- Add 15-min breaks between tasks longer than 1.5 hours
- Be realistic — do not schedule 8 hours of work in 3 hours

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

            if result.get("type") == "schedule" and result.get("schedule"):
                await self._save_schedule(result["schedule"], today_str, result)

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

    async def _call_groq(self, user_prompt: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        try:
            from groq import Groq
            loop = asyncio.get_event_loop()

            # Build proper multi-turn messages
            messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

            if conversation_history:
                for turn in conversation_history[-6:]:
                    role    = turn.get("role", "user")
                    content = turn.get("content", "")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": str(content)[:800]})

            messages.append({"role": "user", "content": user_prompt})

            def _sync():
                client   = Groq(api_key=GROQ_API_KEY)
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    max_tokens=1200,
                    temperature=0.7,
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
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.lower().startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        raw   = raw.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as je:
            logger.warning(f"JSON parse failed: {je} | raw: {raw[:300]}")
            return {
                "type":        "chat",
                "message":     raw[:400] if len(raw) > 10 else "I'm here to help! What would you like to plan?",
                "suggestions": ["Plan my day", "Give me advice", "Show my progress"],
            }

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

            routine = await self.db.user_day_context.find_one({"user_id": self.user_id})
            if routine and routine.get("has_custom"):
                ds = routine.get("day_start", 16.0)
                de = routine.get("day_end",   23.0)
                ctx["saved_routine"] = {
                    "day_start":     ds,
                    "day_end":       de,
                    "free_from":     self._fmt_hour(ds),
                    "free_until":    self._fmt_hour(de),
                    "blocked_slots": routine.get("blocked_slots", []),
                }

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

        if ctx["saved_routine"]:
            r = ctx["saved_routine"]
            lines.append(
                f"Saved routine: free from {r['free_from']} to {r['free_until']}. "
                "Use this window when scheduling unless user specifies otherwise."
            )
        else:
            lines.append(
                "Saved routine: none — if user gives tasks without a time window, "
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
            "Respond to exactly what the user said above.",
            "Return ONE valid JSON object only — no markdown, no extra text outside the JSON:",
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