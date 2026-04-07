# backend/ai/smart_brain.py
"""
SmartBrain — Pre-processor that adds genuine understanding to Timevora AI.

THE PROBLEM it solves:
  - "Hi"              was being scheduled as a task named "Hi"
  - "I have holiday tomorrow" was misunderstood
  - Any text was blindly treated as a schedulable item
  - No distinction between chat, context, and real tasks

HOW IT WORKS:
  1. MessageClassifier  — decides what kind of message this really is
  2. TaskValidator      — rejects non-task extractions before they reach the scheduler
  3. ConfirmationGate   — for ambiguous messages, asks before scheduling
  4. ContextExtractor   — handles "I have holiday tomorrow" as INFO, not a task

AI-UPGRADE:
  If ANTHROPIC_API_KEY is set, SmartBrain.pre_process() uses Claude AI
  to classify the message — meaning it understands sentences a human would,
  not just keyword matches. Falls back to the original classifier automatically
  if the key is absent or the API call fails. No other code needs to change.
"""

import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

# ── AI config (optional — set ANTHROPIC_API_KEY in your .env) ─────────────────
_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_CLAUDE_MODEL      = "claude-sonnet-4-20250514"
_API_URL           = "https://api.anthropic.com/v1/messages"

# ── Claude AI system prompt for message classification ────────────────────────
_AI_CLASSIFY_PROMPT = """
You are a message classifier for a scheduling assistant app called Timevora.
Read the user's message and return ONLY a JSON object — no explanation, no markdown.

Return this structure:
{
  "category": one of the values listed below,
  "confidence": 0.0 to 1.0,
  "routine": {"label": "college"|"school"|"work"|"other", "start": decimal_hour_or_null, "end": decimal_hour_or_null} or null,
  "context": {"type": "free_day"|"cancelled"|"free_time", "date": "today"|"tomorrow"|"string"} or null
}

Category values and when to use them:
- "greeting"        → "hi", "hello", "hey", "good morning" etc.
- "gratitude"       → "thanks", "thank you", "awesome", "perfect" etc.
- "casual_chat"     → general conversation, "how are you", "i'm bored", unrecognised small talk
- "context_info"    → user sharing info about their day — "I have holiday tomorrow", "no college today", "class cancelled"
- "task_scheduling" → user wants to schedule something — "study physics 2 hours", "plan my day"
- "task_add"        → user adding to existing schedule — "also add gym 30 mins", "i also need to do chemistry"
- "routine_info"    → user telling you their fixed daily schedule — "I have college 9 to 4", "I wake up at 7"
- "question"        → asking a question unrelated to scheduling — "what is pomodoro technique"
- "advice_request"  → asking for productivity advice — "give me tips", "how to focus"
- "progress_check"  → asking about their own progress — "how am I doing", "my stats"
- "schedule_manage" → managing existing schedule — "optimize my schedule", "clear today", "delete task"
- "ambiguous"       → message has task keywords but not enough info to schedule (no duration, no time)

Rules:
- "i have college 9 to 4" → routine_info, fill routine object with label:"college" start:9.0 end:16.0
- "i have holiday tomorrow" → context_info, fill context object
- Times: "9 AM"→9.0, "4 PM"→16.0, "9 to 4" means 9.0 to 16.0
- If message has a real subject AND a duration/time → task_scheduling (confidence 0.9)
- If message has a subject but NO duration/time → ambiguous (confidence 0.5)
- Short single-word messages that are task keywords (gym, yoga) → ambiguous (confidence 0.4)
""".strip()


# ── Message categories ────────────────────────────────────────────────────────

class MessageCategory(str, Enum):
    GREETING         = "greeting"
    GRATITUDE        = "gratitude"
    CASUAL_CHAT      = "casual_chat"
    CONTEXT_INFO     = "context_info"
    TASK_SCHEDULING  = "task_scheduling"
    TASK_ADD         = "task_add"
    ROUTINE_INFO     = "routine_info"
    QUESTION         = "question"
    ADVICE_REQUEST   = "advice_request"
    PROGRESS_CHECK   = "progress_check"
    SCHEDULE_MANAGE  = "schedule_manage"
    AMBIGUOUS        = "ambiguous"


# ── Patterns (used by regex classifier fallback) ───────────────────────────────

_GREETING_PATTERNS = re.compile(
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening|night)|what'?s\s*up|"
    r"howdy|greetings|yo|sup|hiya)[\s!?.]*$",
    re.IGNORECASE,
)

_GRATITUDE_PATTERNS = re.compile(
    r"^(thanks?|thank\s*you|thx|ty|cheers|appreciate\s*(it|that)|"
    r"awesome|great|perfect|amazing|cool|nice|wow|ok(ay)?|sounds\s*good)[\s!.]*$",
    re.IGNORECASE,
)

_CASUAL_CHAT_PATTERNS = re.compile(
    r"^(how\s*are\s*you|how\s*r\s*u|what\s*are\s*you|who\s*are\s*you|"
    r"are\s*you\s*(there|alive|ok)|i'?m\s*(bored|tired|hungry|sleepy|happy|sad)|"
    r"nothing|never\s*mind|nvm|ok|okay|lol|haha|hmm+|umm+|ugh|idk|"
    r"same|right|exactly|yes|no|nope|yep|yeah|sure|fine)[\s!?.]*$",
    re.IGNORECASE,
)

_CONTEXT_INFO_PATTERNS = [
    r"i\s+have\s+(holiday|vacation|day\s*off|break|leave|rest)",
    r"(holiday|vacation|day\s*off|no\s+college|no\s+school|no\s+work)\s*(tomorrow|today|on)",
    r"tomorrow\s+i\s+have\s+(holiday|vacation|day\s*off|no\s+college)",
    r"i'?m\s+(free|off|on\s+leave|on\s+vacation)\s*(today|tomorrow|all\s*day)",
    r"(today|tomorrow)\s+is\s+(holiday|vacation|a\s+day\s*off|free)",
    r"no\s+(class|college|school|work|office)\s*(today|tomorrow)",
    r"cancelled?\s+(class|college|school|work)",
]

_STRONG_TASK_SIGNALS = [
    r"\d+\s*(hour|hr|h\b|minute|min|mins?)",
    r"(from|between)\s+\d{1,2}(:\d{2})?\s*(am|pm)",
    r"at\s+\d{1,2}(:\d{2})?\s*(am|pm)",
    r"(study|revise|practice|code|exercise|gym|workout|"
    r"read|write|design|prepare|finish|complete|work\s+on)\s+\w+",
]

# Words that are NEVER valid task names by themselves
_INVALID_TASK_NAMES = {
    "hi", "hello", "hey", "ok", "okay", "yes", "no", "nope", "yep", "yeah",
    "sure", "fine", "right", "exactly", "same", "lol", "haha", "hmm", "umm",
    "ugh", "idk", "thanks", "thank", "bye", "goodbye", "cya", "later",
    "what", "why", "how", "when", "where", "who", "which",
    "good", "bad", "nice", "great", "perfect", "awesome", "cool",
    "morning", "afternoon", "evening", "night",
    "nothing", "something", "anything", "everything",
    "me", "my", "i", "we", "you", "it", "this", "that", "these", "those",
    "some", "any", "all", "none", "many", "few", "more", "less",
    "a", "b", "c", "d", "e", "f", "g", "h",
    "add", "include", "also", "too", "schedule", "plan", "create",
    "add this", "add it", "add that", "do this", "include this",
    "put this", "this too", "as well",
}

# Multi-word instruction phrases that are never task names
_INVALID_TASK_PHRASES = re.compile(
    r"^(add\s+this|add\s+it|add\s+that|include\s+this|include\s+that|"
    r"do\s+this|put\s+this|this\s+too|as\s+well|also\s+add|"
    r"can\s+you\s+add|please\s+add|please\s+include|schedule\s+this)$",
    re.IGNORECASE,
)

_MIN_TASK_NAME_LEN = 3

# Known real task keywords — used by regex classifier and ConfirmationGate
_REAL_TASK_KEYWORDS = {
    "study", "studies", "revise", "revision", "read", "write", "practice",
    "exercise", "gym", "workout", "run", "yoga", "meditate", "walk",
    "code", "coding", "develop", "design", "build", "debug",
    "work", "meeting", "email", "report", "presentation", "project",
    "cook", "clean", "shop", "laundry", "errands",
    "physics", "maths", "math", "chemistry", "biology", "history",
    "english", "geography", "science", "economics", "dsa", "leetcode",
    "homework", "assignment", "exam", "test", "quiz", "lecture",
    "call", "meet", "dinner", "lunch", "breakfast",
    "sleep", "nap", "rest", "break",
}


# ── AI classifier ─────────────────────────────────────────────────────────────

class AIClassifier:
    """
    Uses Claude API to classify messages with genuine language understanding.
    Used by MessageClassifier when ANTHROPIC_API_KEY is available.
    """

    async def classify_async(
        self, message: str
    ) -> Optional[Tuple[MessageCategory, float, Optional[Dict], Optional[Dict]]]:
        """
        Returns (category, confidence, routine_dict_or_None, context_dict_or_None)
        or None if the API call fails (caller falls back to regex).
        """
        try:
            import httpx
        except ImportError:
            return None

        headers = {
            "x-api-key":         _ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }
        body = {
            "model":      _CLAUDE_MODEL,
            "max_tokens": 300,
            "system":     _AI_CLASSIFY_PROMPT,
            "messages":   [{"role": "user", "content": message}],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(_API_URL, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                raw  = data["content"][0]["text"].strip()

            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:])
            if raw.endswith("```"):
                raw = "\n".join(raw.split("\n")[:-1])

            parsed = json.loads(raw.strip())
            cat_str = parsed.get("category", "casual_chat")
            conf    = float(parsed.get("confidence", 0.7))
            routine = parsed.get("routine")
            context = parsed.get("context")

            # Map string to enum safely
            try:
                cat = MessageCategory(cat_str)
            except ValueError:
                cat = MessageCategory.CASUAL_CHAT

            return cat, conf, routine, context

        except Exception as e:
            logger.warning(f"AIClassifier: API call failed — {e}")
            return None


# ── Main classifier ───────────────────────────────────────────────────────────

class MessageClassifier:
    """
    Classifies an incoming message into a MessageCategory.
    Uses Claude AI when available, falls back to regex patterns.
    """

    def __init__(self):
        self._ai = AIClassifier() if _ANTHROPIC_API_KEY else None

    def classify(self, message: str) -> Tuple[MessageCategory, float]:
        """
        Sync classify — uses regex engine.
        For AI classification use classify_async().
        """
        return self._regex_classify(message)

    async def classify_async(
        self, message: str
    ) -> Tuple[MessageCategory, float, Optional[Dict], Optional[Dict]]:
        """
        Async classify — tries AI first, falls back to regex.
        Returns (category, confidence, routine, context).
        routine and context are only populated by the AI classifier.
        """
        if self._ai:
            result = await self._ai.classify_async(message)
            if result is not None:
                return result  # (cat, conf, routine, context)

        # Regex fallback — routine/context will be None (handled by SmartBrain separately)
        cat, conf = self._regex_classify(message)
        return cat, conf, None, None

    def _regex_classify(self, message: str) -> Tuple[MessageCategory, float]:
        """Original regex-based classifier — fully preserved."""
        msg       = message.strip()
        msg_lower = msg.lower()
        words     = msg_lower.split()

        # ── Very short messages ───────────────────────────────────────────────
        if len(words) <= 2:
            if _GREETING_PATTERNS.match(msg):
                return MessageCategory.GREETING, 1.0
            if _GRATITUDE_PATTERNS.match(msg):
                return MessageCategory.GRATITUDE, 1.0
            if _CASUAL_CHAT_PATTERNS.match(msg):
                return MessageCategory.CASUAL_CHAT, 1.0
            if len(words) == 1 and words[0] in _REAL_TASK_KEYWORDS:
                return MessageCategory.AMBIGUOUS, 0.4
            return MessageCategory.CASUAL_CHAT, 0.85

        # ── Context / info messages ───────────────────────────────────────────
        for pattern in _CONTEXT_INFO_PATTERNS:
            if re.search(pattern, msg_lower):
                return MessageCategory.CONTEXT_INFO, 0.9

        # ── Routine info ──────────────────────────────────────────────────────
        routine_phrases = [
            "i have college", "i have school", "i have work", "i have class",
            "i wake up", "my day starts", "my routine", "i'm usually free",
            "i study from", "i work from", "college from", "school from",
        ]
        if any(p in msg_lower for p in routine_phrases):
            return MessageCategory.ROUTINE_INFO, 0.9

        # ── Progress / analysis ───────────────────────────────────────────────
        if any(p in msg_lower for p in ["how am i doing", "my progress", "my stats",
                                         "productivity score", "my streak"]):
            return MessageCategory.PROGRESS_CHECK, 0.95
        if any(p in msg_lower for p in ["analyze", "analyse", "my habits", "my patterns"]):
            return MessageCategory.SCHEDULE_MANAGE, 0.9

        # ── Advice / question ─────────────────────────────────────────────────
        advice_phrases = ["give me tips", "any advice", "how to focus", "how should i",
                          "what should i", "recommend", "suggest", "help me focus",
                          "best way to", "how can i"]
        if any(p in msg_lower for p in advice_phrases):
            return MessageCategory.ADVICE_REQUEST, 0.9

        question_phrases = ["what is", "what are", "how do i", "how does", "why ",
                            "explain", "tell me about", "can you tell"]
        if any(p in msg_lower for p in question_phrases):
            return MessageCategory.QUESTION, 0.85

        # ── Schedule management ───────────────────────────────────────────────
        manage_phrases = ["optimize", "reschedule", "clear my schedule", "delete",
                          "remove task", "cancel task", "redo my"]
        if any(p in msg_lower for p in manage_phrases):
            return MessageCategory.SCHEDULE_MANAGE, 0.9

        # ── Explicit add keywords ─────────────────────────────────────────────
        add_phrases = ["add ", "also add", "include ", "one more task", "add a task",
                       "add another", "put in", "i also need to", "i also have to"]
        if any(p in msg_lower for p in add_phrases):
            if self._has_real_task_content(msg_lower):
                return MessageCategory.TASK_ADD, 0.9
            return MessageCategory.AMBIGUOUS, 0.5

        # ── Task scheduling signals ───────────────────────────────────────────
        has_strong_signal = any(re.search(p, msg_lower) for p in _STRONG_TASK_SIGNALS)
        has_task_keyword  = any(kw in msg_lower for kw in _REAL_TASK_KEYWORDS)
        has_plan_keyword  = any(p in msg_lower for p in [
            "plan my day", "plan my", "schedule my", "create a schedule",
            "organize my day", "make a schedule",
        ])

        if has_plan_keyword:
            return MessageCategory.TASK_SCHEDULING, 0.95
        if has_strong_signal and has_task_keyword:
            return MessageCategory.TASK_SCHEDULING, 0.9
        if has_task_keyword and not has_strong_signal:
            return MessageCategory.AMBIGUOUS, 0.5
        if has_strong_signal and not has_task_keyword:
            return MessageCategory.AMBIGUOUS, 0.45

        if _CASUAL_CHAT_PATTERNS.match(msg):
            return MessageCategory.CASUAL_CHAT, 0.8

        return MessageCategory.CASUAL_CHAT, 0.6

    def _has_real_task_content(self, msg_lower: str) -> bool:
        """Check if there's genuine task content in the message."""
        has_kw  = any(kw in msg_lower for kw in _REAL_TASK_KEYWORDS)
        has_dur = bool(re.search(r'\d+\s*(hour|hr|h\b|minute|min)', msg_lower))
        return has_kw or has_dur


# ── Task validator ────────────────────────────────────────────────────────────

class TaskValidator:
    """
    Validates extracted task objects before they reach the scheduler.
    Filters out noise like {"name": "Hi", "duration": 1.0}.
    """

    def validate_tasks(self, tasks: List[Dict[str, Any]],
                       original_message: str) -> List[Dict[str, Any]]:
        """Returns only the tasks that look genuinely schedulable."""
        valid     = []
        msg_lower = original_message.lower()

        for task in tasks:
            name = (task.get("name") or "").strip()

            if not self._is_valid_name(name):
                logger.info(f"TaskValidator: rejected '{name}' — invalid name")
                continue

            if name.lower() == msg_lower.strip():
                logger.info(f"TaskValidator: rejected '{name}' — name == full message")
                continue

            words = name.lower().split()
            if len(words) == 1 and name.lower() not in _REAL_TASK_KEYWORDS:
                logger.info(f"TaskValidator: rejected '{name}' — single unknown word")
                continue

            duration = task.get("duration", 0)
            if duration <= 0:
                logger.info(f"TaskValidator: rejected '{name}' — zero duration")
                continue

            if duration > 12:
                logger.info(f"TaskValidator: capped duration for '{name}' from {duration}h to 3h")
                task["duration"] = 3.0

            valid.append(task)

        return valid

    def _is_valid_name(self, name: str) -> bool:
        if not name or len(name) < _MIN_TASK_NAME_LEN:
            return False
        name_lower = name.lower().strip()
        if name_lower in _INVALID_TASK_NAMES:
            return False
        if _INVALID_TASK_PHRASES.match(name_lower):
            return False
        if not re.search(r"[a-zA-Z]", name):
            return False
        words      = [w.strip(".,!?") for w in name_lower.split()]
        meaningful = [w for w in words if w not in _INVALID_TASK_NAMES and len(w) > 1]
        return len(meaningful) > 0


# ── Context extractor ─────────────────────────────────────────────────────────

class ContextExtractor:
    """
    Extracts non-task information from messages like:
    "I have holiday tomorrow" → {type: "holiday", date: "tomorrow"}
    "No college today" → {type: "free_day", date: "today"}
    """

    def extract_context(self, message: str) -> Optional[Dict[str, Any]]:
        msg = message.lower()

        holiday_match = re.search(
            r"(today|tomorrow|this\s+\w+day).*?(holiday|vacation|day\s*off|no\s+college|"
            r"no\s+school|no\s+work|free\s+day|off\s+day)|"
            r"(holiday|vacation|day\s*off|no\s+college|no\s+school)\s*"
            r"(today|tomorrow|this\s+\w+day)",
            msg
        )
        if holiday_match:
            date_word = "tomorrow" if "tomorrow" in msg else "today"
            return {
                "type": "free_day",
                "date": date_word,
                "message": (
                    f"Got it — {date_word} is a free day. "
                    f"Want to use some of that time productively, or keep it as proper rest?"
                ),
                "suggestions": [
                    f"Plan something light for {date_word}",
                    "Schedule rest and recovery",
                    f"Use {date_word} to catch up on something",
                ]
            }

        cancelled_match = re.search(
            r"(class|lecture|college|school|work|meeting)\s+(is\s+)?(cancelled?|canceled?|off|not\s+happening)",
            msg
        )
        if cancelled_match:
            return {
                "type": "free_time",
                "message": "Unexpected free time — the best kind. What do you want to do with it?",
                "suggestions": [
                    "Catch up on pending work",
                    "Do something I've been putting off",
                    "Rest and recharge",
                ]
            }

        return None


# ── Confirmation gate ─────────────────────────────────────────────────────────

class ConfirmationGate:
    """
    For ambiguous messages, generates a clarification question
    instead of blindly scheduling.
    """

    def get_clarification(self, message: str,
                          category: MessageCategory,
                          confidence: float) -> Optional[Dict[str, Any]]:
        """
        Returns a clarification response dict if the message is ambiguous,
        or None if we should proceed normally.
        Only triggers when confidence < 0.6.
        """
        if confidence >= 0.6:
            return None

        msg_lower = message.lower().strip()
        words     = msg_lower.split()

        if len(words) == 1 and words[0] in _REAL_TASK_KEYWORDS:
            task_name = message.strip()
            return {
                "type": "clarification",
                "message": f"How long do you want to schedule {task_name} for, and when are you free?",
                "suggestions": [
                    f"{task_name} 30 minutes",
                    f"{task_name} 1 hour",
                    f"{task_name} 1 hour from 6 PM",
                ]
            }

        if category == MessageCategory.AMBIGUOUS:
            mentioned = [kw for kw in _REAL_TASK_KEYWORDS if kw in msg_lower]
            if mentioned:
                subject = mentioned[0].capitalize()
                return {
                    "type": "clarification",
                    "message": f"Want me to schedule {subject}? If so, how long and when are you free?",
                    "suggestions": [
                        f"{subject} for 1 hour",
                        f"{subject} 2 hours this evening",
                        "Just giving you information",
                    ]
                }
            return {
                "type": "clarification",
                "message": "Do you want me to schedule something, or are you sharing some context about your day?",
                "suggestions": [
                    "Yes, schedule it for me",
                    "Just sharing info",
                    "Give me productivity tips",
                ]
            }

        return None


# ── Main SmartBrain entry point ───────────────────────────────────────────────

class SmartBrain:
    """
    Drop this into AIAssistant.process_message() as the FIRST step.

    Usage (unchanged from before):
        brain  = SmartBrain()
        result = await brain.pre_process(message, existing_schedule_count)
        if result["action"] == "respond":
            return result["response"]
        elif result["action"] == "proceed":
            category = result["category"]
            # continue with normal flow ...

    If ANTHROPIC_API_KEY is set, pre_process() will use Claude AI to classify
    the message. Otherwise it uses the original regex-based logic.
    """

    def __init__(self):
        self.classifier = MessageClassifier()
        self.validator  = TaskValidator()
        self.context_ex = ContextExtractor()
        self.conf_gate  = ConfirmationGate()

    async def pre_process(
        self,
        message: str,
        has_existing_schedule: bool = False,
    ) -> Dict[str, Any]:
        """
        Returns:
          {"action": "respond",  "response": {...}}   → return this to the user
          {"action": "proceed",  "category": ...,
           "confidence": ...}                          → continue normal flow
        """
        msg = message.strip()

        # ── 1. Classify the message (AI or regex) ─────────────────────────────
        category, confidence, ai_routine, ai_context = \
            await self.classifier.classify_async(msg)

        logger.info(
            f"SmartBrain: '{msg[:60]}' → {category} "
            f"(confidence={confidence:.2f}, ai={'yes' if _ANTHROPIC_API_KEY else 'no'})"
        )

        # ── 2. Handle clear non-task categories immediately ───────────────────

        if category == MessageCategory.GREETING:
            return {
                "action": "respond",
                "response": self._greeting_response(has_existing_schedule),
            }

        if category == MessageCategory.GRATITUDE:
            return {
                "action": "respond",
                "response": {
                    "type": "chat",
                    "message": "Happy to help. What else do you need?",
                    "suggestions": [
                        "Add something to my plan",
                        "Give me productivity advice",
                        "Show my progress",
                    ],
                },
            }

        if category == MessageCategory.CASUAL_CHAT:
            return {
                "action": "respond",
                "response": self._casual_response(msg),
            }

        if category == MessageCategory.CONTEXT_INFO:
            # Prefer AI-extracted context, fall back to regex ContextExtractor
            if ai_context:
                date_word = ai_context.get("date", "today")
                ctx_type  = ai_context.get("type", "free_day")
                if ctx_type in ("free_day", "holiday"):
                    return {
                        "action": "respond",
                        "response": {
                            "type": "chat",
                            "message": (
                                f"Got it — {date_word} is a free day. "
                                f"Want to use some of that time productively, or keep it as proper rest?"
                            ),
                            "suggestions": [
                                f"Plan something light for {date_word}",
                                "Schedule rest and recovery",
                                f"Use {date_word} to catch up on something",
                            ],
                        },
                    }
                return {
                    "action": "respond",
                    "response": {
                        "type": "chat",
                        "message": "Unexpected free time — the best kind. What do you want to do with it?",
                        "suggestions": [
                            "Catch up on pending work",
                            "Do something I've been putting off",
                            "Rest and recharge",
                        ],
                    },
                }
            ctx = self.context_ex.extract_context(msg)
            if ctx:
                return {
                    "action": "respond",
                    "response": {
                        "type": "chat",
                        "message": ctx["message"],
                        "suggestions": ctx.get("suggestions", []),
                    },
                }
            # Fall through to normal processing if extraction didn't match

        if category == MessageCategory.ROUTINE_INFO:
            routine_response = self._handle_routine_info(msg, ai_routine)
            if routine_response:
                return {"action": "respond", "response": routine_response}

        # ── 3. Ambiguity gate — ask before scheduling ─────────────────────────
        clarification = self.conf_gate.get_clarification(msg, category, confidence)
        if clarification:
            return {"action": "respond", "response": clarification}

        # ── 4. Time window check — if scheduling intent is clear but no time
        #       range given, ask for it so we don't silently use defaults ────────
        if category in (MessageCategory.TASK_SCHEDULING, MessageCategory.TASK_ADD):
            time_window_response = self._check_time_window(msg, category)
            if time_window_response:
                return {"action": "respond", "response": time_window_response}

        # ── 5. Proceed with normal flow ───────────────────────────────────────
        return {
            "action":   "proceed",
            "category": category,
            "confidence": confidence,
        }

    def validate_extracted_tasks(
        self,
        tasks: List[Dict[str, Any]],
        original_message: str,
    ) -> List[Dict[str, Any]]:
        """
        Call this AFTER task extraction, BEFORE passing to the scheduler.
        Filters out garbage like {"name": "Hi", "duration": 1.0}.
        """
        return self.validator.validate_tasks(tasks, original_message)

    def _check_time_window(self, msg: str, category: MessageCategory) -> Optional[Dict[str, Any]]:
        """
        If the user has clearly stated tasks but given NO time window,
        ask for their available window before scheduling.
        """
        msg_lower = msg.lower()

        has_time_range = bool(re.search(
            r"(from\s+\d{1,2}(:\d{2})?\s*(am|pm)\s*(to|-)\s*\d{1,2}|"
            r"free\s+(from|after|till|until)|"
            r"available\s+(from|after|till)|"
            r"\d{1,2}(:\d{2})?\s*(am|pm)\s*(to|-)\s*\d{1,2}(:\d{2})?\s*(am|pm)|"
            r"(till|until|before)\s+\d{1,2}(:\d{2})?\s*(am|pm))",
            msg_lower
        ))
        if has_time_range:
            return None

        has_fixed_time = bool(re.search(r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)", msg_lower))
        if has_fixed_time:
            return None

        plan_phrases = ["plan my day", "plan my evening", "plan my morning",
                        "plan my afternoon", "plan my night", "plan my week"]
        if any(p in msg_lower for p in plan_phrases):
            period   = next((p.split("my ")[1] for p in plan_phrases if p in msg_lower), "day")
            mentioned = [kw for kw in _REAL_TASK_KEYWORDS if kw in msg_lower]
            task_str  = ", ".join(mentioned[:3]) if mentioned else "your tasks"
            return {
                "type": "checkin",
                "message": (
                    f"I can plan your {period} around {task_str}.\n\n"
                    f"📅 What is your available time window?\n\n"
                    f"e.g. 'Free from 5 PM to 10 PM' or '6 PM till midnight'"
                ),
                "suggestions": [
                    "Free from 5 PM to 10 PM",
                    "6 PM to 11 PM",
                    "Free all evening",
                ],
                "pending_tasks": mentioned,
            }

        has_tasks    = any(kw in msg_lower for kw in _REAL_TASK_KEYWORDS)
        has_duration = bool(re.search(r"\d+\s*(hour|hr|h\b|minute|min)", msg_lower))

        if has_tasks and not has_duration and category == MessageCategory.TASK_SCHEDULING:
            mentioned = [kw for kw in _REAL_TASK_KEYWORDS if kw in msg_lower]
            task_str  = ", ".join(m.capitalize() for m in mentioned[:3]) if mentioned else "these tasks"
            return {
                "type": "checkin",
                "message": (
                    f"Got it — {task_str}.\n\n"
                    f"📅 What's your available time window today? Give me a start and end time and I'll schedule everything.\n\n"
                    f"e.g. '4 PM to 9 PM' or 'Free from 6 PM till 11 PM'"
                ),
                "suggestions": [
                    "4 PM to 9 PM",
                    "Free from 6 PM to 11 PM",
                    "Free all evening",
                ],
                "pending_tasks": mentioned,
            }

        return None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _handle_routine_info(
        self, msg: str, ai_routine: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        When the user tells us their fixed routine (e.g. "I have college 9 to 4"),
        extract the blocked time and ask what they want to do in their free time.
        Prefers AI-extracted routine dict, falls back to regex extraction.
        """
        msg_lower = msg.lower()

        # ── Try AI-provided routine first ─────────────────────────────────────
        if ai_routine:
            label = ai_routine.get("label", "your schedule")
            start = ai_routine.get("start")
            end   = ai_routine.get("end")
        else:
            # ── Regex fallback: extract time range from message ────────────────
            time_match = re.search(
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-|till|until)\s*"
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
                msg_lower
            )
            routine_labels = {
                "college": "college", "school": "school", "work": "work",
                "class": "class", "office": "office", "university": "university",
            }
            label = next(
                (lbl for key, lbl in routine_labels.items() if key in msg_lower),
                "your schedule"
            )
            if time_match:
                raw_start = time_match.group(1).strip()
                raw_end   = time_match.group(2).strip()
                # Convert to decimal for storage, keep raw strings for display
                from nlp import _parse_time_str
                start = _parse_time_str(raw_start)
                end   = _parse_time_str(raw_end)
            else:
                start = None
                end   = None

        def _fmt(h: Optional[float]) -> str:
            if h is None:
                return "?"
            hour   = int(h)
            mins   = int((h - hour) * 60)
            period = "AM" if hour < 12 else "PM"
            h12    = hour if hour <= 12 else hour - 12
            if h12 == 0:
                h12 = 12
            return f"{h12}:{mins:02d} {period}" if mins else f"{h12} {period}"

        if start is not None and end is not None:
            return {
                "type": "routine_popup",
                "message": (
                    f"Got it — {label} from {_fmt(start)} to {_fmt(end)}. "
                    f"I've noted that as a blocked time.\n\n"
                    f"📅 What do you want to do in your free time outside {label}? "
                    f"Tell me and I'll schedule around it."
                ),
                "routine": {"label": label, "start": start, "end": end},
                "suggestions": [
                    f"Plan my evening after {_fmt(end)}",
                    f"Add study tasks after {label}",
                    "Schedule gym and study in free time",
                ],
            }

        # No time range found — ask for it
        return {
            "type": "routine_popup",
            "message": (
                f"Got it — you have {label}. "
                f"What time does it start and end? I'll block that out and plan your free time."
            ),
            "suggestions": [
                f"{label.capitalize()} from 9 AM to 4 PM",
                f"{label.capitalize()} from 10 AM to 5 PM",
                "Tell me the time and I'll plan the rest",
            ],
        }

    def _greeting_response(self, has_schedule: bool) -> Dict[str, Any]:
        if has_schedule:
            return {
                "type": "chat",
                "message": "Hey! You already have things scheduled today. Want to add more, adjust the plan, or need advice on something?",
                "suggestions": [
                    "Add something to my schedule",
                    "Optimize what I have",
                    "Give me productivity tips",
                ],
            }
        return {
            "type": "chat",
            "message": "Hey! What's on your plate today? Just tell me — studying, work, gym, errands, anything — and I'll build a plan around your available time.",
            "suggestions": [
                "Plan my day",
                "I have an exam tomorrow",
                "I'm free this evening, make me productive",
            ],
        }

    def _casual_response(self, msg_lower: str) -> Dict[str, Any]:
        m = msg_lower.lower()
        if any(p in m for p in ["how are you", "how r u"]):
            return {
                "type": "chat",
                "message": "Doing well! What are you working on today? Tell me and I'll help you plan it.",
                "suggestions": ["Plan my day", "Help me prioritise tasks", "Give me productivity tips"],
            }
        if any(p in m for p in ["who are you", "what are you"]):
            return {
                "type": "chat",
                "message": "I'm your AI Productivity Planner, powered by Timevora. I understand what you need to do, ask the right questions, and build you a smart schedule — whether it's studying, work, gym, or anything else. What do you want to plan?",
                "suggestions": ["Plan my day", "Schedule tasks for today", "Give me productivity tips"],
            }
        if any(p in m for p in ["i'm bored", "im bored", "nothing to do"]):
            return {
                "type": "chat",
                "message": "Boredom is an opportunity. What's something you've been putting off — a skill to learn, a task to finish, or a habit to build? Tell me and I'll put it on the calendar.",
                "suggestions": ["Plan something productive", "Give me ideas", "What should I do today?"],
            }
        if any(p in m for p in ["i'm tired", "im tired", "i'm sleepy", "im sleepy"]):
            return {
                "type": "chat",
                "message": "Noted. Want me to build a lighter plan for today with built-in rest, or would you rather focus on just one key task?",
                "suggestions": ["Light schedule for today", "Just one important task", "Schedule a nap first"],
            }
        return {
            "type": "chat",
            "message": "I'm here to help you plan your day and stay on track. What do you want to tackle?",
            "suggestions": [
                "Plan my day",
                "Help me prioritise",
                "Give me productivity tips",
            ],
        }
