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
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


# ── Message categories ────────────────────────────────────────────────────────

class MessageCategory(str, Enum):
    GREETING         = "greeting"          # "Hi", "Hello", "Hey"
    GRATITUDE        = "gratitude"         # "Thanks", "Thank you"
    CASUAL_CHAT      = "casual_chat"       # "How are you", random conversation
    CONTEXT_INFO     = "context_info"      # "I have holiday tomorrow", "No college today"
    TASK_SCHEDULING  = "task_scheduling"   # "Study physics 2 hours"
    TASK_ADD         = "task_add"          # "Add meditation 30 min"
    ROUTINE_INFO     = "routine_info"      # "I have college 9 to 4"
    QUESTION         = "question"          # "How do I focus better?"
    ADVICE_REQUEST   = "advice_request"    # "Give me tips"
    PROGRESS_CHECK   = "progress_check"    # "How am I doing?"
    SCHEDULE_MANAGE  = "schedule_manage"   # "Optimize my schedule", "Clear today"
    AMBIGUOUS        = "ambiguous"         # Not sure — needs confirmation


# ── Patterns ──────────────────────────────────────────────────────────────────

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

# Context info: user is sharing information about their day — NOT requesting scheduling
_CONTEXT_INFO_PATTERNS = [
    r"i\s+have\s+(holiday|vacation|day\s*off|break|leave|rest)",
    r"(holiday|vacation|day\s*off|no\s+college|no\s+school|no\s+work)\s*(tomorrow|today|on)",
    r"tomorrow\s+i\s+have\s+(holiday|vacation|day\s*off|no\s+college)",
    r"i'?m\s+(free|off|on\s+leave|on\s+vacation)\s*(today|tomorrow|all\s*day)",
    r"(today|tomorrow)\s+is\s+(holiday|vacation|a\s+day\s*off|free)",
    r"no\s+(class|college|school|work|office)\s*(today|tomorrow)",
    r"cancelled?\s+(class|college|school|work)",
]

# True task indicators — these strongly suggest the user wants something SCHEDULED
_STRONG_TASK_SIGNALS = [
    r"\d+\s*(hour|hr|h\b|minute|min|mins?)",            # duration mentioned
    r"(from|between)\s+\d{1,2}(:\d{2})?\s*(am|pm)",    # time range
    r"at\s+\d{1,2}(:\d{2})?\s*(am|pm)",                # fixed time
    r"(study|revise|practice|code|exercise|gym|workout|"
    r"read|write|design|prepare|finish|complete|work\s+on)\s+\w+",  # verb + subject
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
    # Single letters / very short
    "a", "b", "c", "d", "e", "f", "g", "h",
}

# Minimum meaningful task name length (chars)
_MIN_TASK_NAME_LEN = 3

# Known real task keywords — if present, extraction is worth trusting
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


# ── Main classifier ───────────────────────────────────────────────────────────

class MessageClassifier:
    """
    Classifies an incoming message into a MessageCategory
    so the assistant can respond appropriately instead of
    blindly trying to schedule everything.
    """

    def classify(self, message: str) -> Tuple[MessageCategory, float]:
        """
        Returns (category, confidence) where confidence is 0.0–1.0.
        Low confidence → should trigger a clarification question.
        """
        msg = message.strip()
        msg_lower = msg.lower()

        # ── Hard: very short messages (≤ 3 words) ────────────────────────────
        words = msg_lower.split()
        if len(words) <= 2:
            if _GREETING_PATTERNS.match(msg):
                return MessageCategory.GREETING, 1.0
            if _GRATITUDE_PATTERNS.match(msg):
                return MessageCategory.GRATITUDE, 1.0
            if _CASUAL_CHAT_PATTERNS.match(msg):
                return MessageCategory.CASUAL_CHAT, 1.0
            # Single word that looks like a task keyword
            if len(words) == 1 and words[0] in _REAL_TASK_KEYWORDS:
                return MessageCategory.AMBIGUOUS, 0.4   # "gym" alone — ambiguous
            # Short but not recognized → casual chat, don't schedule
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
            # Still check that there's something real to add
            if self._has_real_task_content(msg_lower):
                return MessageCategory.TASK_ADD, 0.9
            return MessageCategory.AMBIGUOUS, 0.5

        # ── Task scheduling signals ───────────────────────────────────────────
        has_strong_signal = any(
            re.search(p, msg_lower) for p in _STRONG_TASK_SIGNALS
        )
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
            # e.g. "physics tomorrow" — has a task word but no duration/time
            return MessageCategory.AMBIGUOUS, 0.5

        if has_strong_signal and not has_task_keyword:
            # e.g. "for 2 hours" — duration but no task identified
            return MessageCategory.AMBIGUOUS, 0.45

        # ── Catch-all ─────────────────────────────────────────────────────────
        if _CASUAL_CHAT_PATTERNS.match(msg):
            return MessageCategory.CASUAL_CHAT, 0.8

        return MessageCategory.CASUAL_CHAT, 0.6

    def _has_real_task_content(self, msg_lower: str) -> bool:
        """Check if there's genuine task content in the message."""
        has_kw = any(kw in msg_lower for kw in _REAL_TASK_KEYWORDS)
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
        """
        Returns only the tasks that look genuinely schedulable.
        """
        valid = []
        msg_lower = original_message.lower()

        for task in tasks:
            name = (task.get("name") or "").strip()

            # ── Reject invalid names ──────────────────────────────────────────
            if not self._is_valid_name(name):
                logger.info(f"TaskValidator: rejected task '{name}' — invalid name")
                continue

            # ── Reject if task name is exactly what the user typed (likely
            #    the whole message was treated as a task name) ─────────────────
            if name.lower() == msg_lower.strip():
                logger.info(f"TaskValidator: rejected task '{name}' — name == full message")
                continue

            # ── Reject suspiciously short single-word names that aren't
            #    recognized task keywords ──────────────────────────────────────
            words = name.lower().split()
            if len(words) == 1 and name.lower() not in _REAL_TASK_KEYWORDS:
                logger.info(f"TaskValidator: rejected task '{name}' — single unknown word")
                continue

            # ── Reject if duration is 0 or negative ──────────────────────────
            duration = task.get("duration", 0)
            if duration <= 0:
                logger.info(f"TaskValidator: rejected task '{name}' — zero duration")
                continue

            # ── Reject absurd durations (> 12 hours for a single task) ────────
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
        # Must contain at least one letter
        if not re.search(r"[a-zA-Z]", name):
            return False
        # Must not be only stopwords/punctuation
        words = [w.strip(".,!?") for w in name_lower.split()]
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

        # Holiday / day off detection
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
                "message": f"Got it! I'll note that {date_word} is a free day. "
                           f"Want me to help you plan some personal time or learning goals?",
                "suggestions": [
                    "Plan some light activities for tomorrow",
                    "Study something I enjoy",
                    "Schedule rest and relaxation",
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
            return None  # Confident enough — proceed normally

        msg_lower = message.lower().strip()
        words     = msg_lower.split()

        # Single known task keyword (e.g. "gym", "yoga", "read")
        if len(words) == 1 and words[0] in _REAL_TASK_KEYWORDS:
            return {
                "type": "clarification",
                "message": f"Sure! How long would you like to schedule **{message.strip()}** for?",
                "suggestions": [
                    f"{message.strip()} for 30 minutes",
                    f"{message.strip()} for 1 hour",
                    f"{message.strip()} for 2 hours",
                ]
            }

        # Task keyword present but no time/duration
        if category == MessageCategory.AMBIGUOUS:
            return {
                "type": "clarification",
                "message": f"I'd love to help! Do you want me to **schedule** something, or are you just sharing info?\n\n"
                           f"For example:\n"
                           f"• 'Study physics for 2 hours'\n"
                           f"• 'I have a holiday tomorrow' (I'll note it but not schedule)",
                "suggestions": [
                    "Schedule something for me",
                    "Just giving you information",
                    "Give me productivity tips",
                ]
            }

        return None


# ── Main SmartBrain entry point ───────────────────────────────────────────────

class SmartBrain:
    """
    Drop this into AIAssistant.process_message() as the FIRST step.

    Usage:
        brain  = SmartBrain()
        result = await brain.pre_process(message, existing_schedule_count)
        if result["action"] == "respond":
            return result["response"]          # return this directly to frontend
        elif result["action"] == "proceed":
            category = result["category"]      # use this to guide intent detection
            # continue with normal flow ...
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
           "validated_message": ...}                  → continue normal flow
        """
        msg = message.strip()

        # ── 1. Classify the message ───────────────────────────────────────────
        category, confidence = self.classifier.classify(msg)
        logger.info(f"SmartBrain: '{msg[:60]}' → {category} (confidence={confidence:.2f})")

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
                    "message": "Happy to help! 🚀 What else would you like to plan or ask?",
                    "suggestions": [
                        "Add a task to my schedule",
                        "Give me productivity tips",
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

        # ── 3. Ambiguity gate — ask before scheduling ─────────────────────────
        clarification = self.conf_gate.get_clarification(msg, category, confidence)
        if clarification:
            return {"action": "respond", "response": clarification}

        # ── 4. Proceed with normal flow ───────────────────────────────────────
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

    # ── Private helpers ───────────────────────────────────────────────────────

    def _greeting_response(self, has_schedule: bool) -> Dict[str, Any]:
        if has_schedule:
            return {
                "type": "chat",
                "message": "Hey! 👋 You already have tasks scheduled today. Want to add more, or need tips?",
                "suggestions": [
                    "Add a task to my schedule",
                    "Give me productivity tips",
                    "Show my progress",
                ],
            }
        return {
            "type": "chat",
            "message": "Hey! 👋 What would you like to work on today? Tell me your tasks and I'll schedule them!",
            "suggestions": [
                "Study Physics 2 hours and Maths 1 hour",
                "Add gym for 1 hour",
                "Plan my day",
            ],
        }

    def _casual_response(self, msg_lower: str) -> Dict[str, Any]:
        # Specific casual replies for common phrases
        if any(p in msg_lower for p in ["how are you", "how r u"]):
            return {
                "type": "chat",
                "message": "I'm doing great and ready to help you be productive! 💪 What tasks shall we tackle today?",
                "suggestions": ["Plan my study session", "Add a task", "Give me tips"],
            }
        if any(p in msg_lower for p in ["who are you", "what are you"]):
            return {
                "type": "chat",
                "message": "I'm your AI Productivity Coach, powered by Timevora! 🧠 I help you schedule tasks, track progress, and stay focused. What can I help you plan?",
                "suggestions": ["Schedule tasks for today", "Give me productivity tips"],
            }
        # Generic fallback
        return {
            "type": "chat",
            "message": "I'm here to help you stay productive! 🎯 Tell me what you need to do and I'll build you a schedule.",
            "suggestions": [
                "Study Physics 2 hours",
                "Plan my day",
                "Give me focus tips",
            ],
        }