# backend/ai/nlp.py
"""
Natural Language Processor for Timevora.

Handles:
  - Task extraction from free-form text (durations, fixed times, priorities)
  - Keyword extraction
  - Sentiment detection
  - Date reference extraction
  - Task categorisation / difficulty / priority estimation
  - Scientifically-based optimal time suggestions per task category
"""

import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Words that are NOT task names ──────────────────────────────────────────────
_STOP_WORDS = {
    "min", "mins", "minute", "minutes", "hour", "hours", "hr", "hrs",
    "utes", "am", "pm", "a", "an", "the", "and", "or", "but",
    "in", "on", "at", "to", "for", "with", "by", "about",
}

# ── Cleanup prefixes that sneak into task names ────────────────────────────────
_NAME_PREFIX_RE = re.compile(
    r"^[\s:,\-]+|"
    r"^\s*(also|plus|then|after\s+that|i\s+have\s+to|i\s+need\s+to|i\s+want\s+to"
    r"|need\s+to|have\s+to|want\s+to|going\s+to|gonna|will)\s+",
    re.IGNORECASE,
)
_NAME_SUFFIX_RE = re.compile(
    r"\s+(for|at|from|in|during|minutes?|hours?|hrs?|of|the|a|an|about|around|approximately)$",
    re.IGNORECASE,
)

# ── Scientifically optimal time windows per task category ─────────────────────
_CATEGORY_OPTIMAL_TIMES: Dict[str, float] = {
    "study":    9.0,
    "work":     9.5,
    "creative": 10.0,
    "health":   16.0,
    "personal": 13.0,
    "social":   17.0,
    "other":    10.0,
}

# ── Default durations when NO duration is mentioned ───────────────────────────
_CATEGORY_DEFAULT_DURATIONS: Dict[str, float] = {
    "study":    2.0,
    "work":     1.5,
    "creative": 1.5,
    "health":   1.0,
    "personal": 0.5,
    "social":   1.0,
    "other":    1.0,
}


def _clean_name(raw: str) -> str:
    """Strip leading/trailing noise from an extracted task name."""
    name = raw.strip()
    for _ in range(8):  # more passes to catch chained suffixes
        prev = name
        name = _NAME_PREFIX_RE.sub("", name)
        name = _NAME_SUFFIX_RE.sub("", name)
        # Also strip trailing standalone prepositions/articles with word boundary
        name = re.sub(r"\s+(of|the|a|an|with|and|or|to|into)\s*$", "", name, flags=re.IGNORECASE)
        name = name.strip(" .,;:-")
        if name == prev:
            break
    return name


def _parse_time_str(time_str: str) -> Optional[float]:
    """Convert a time string to a decimal hour."""
    if not time_str:
        return None
    s = time_str.lower().strip()
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    period = m.group(3)

    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0

    return hour + minute / 60.0


class NLProcessor:
    """Parse free-form task descriptions into structured task dicts."""

    # ── Public API ─────────────────────────────────────────────────────────────

    def extract_tasks(self, text: str) -> List[Dict[str, Any]]:
        """
        Main entry point. Returns a list of task dicts:
        {name, duration, start_time, end_time, priority, difficulty, category, optimal_slot}
        """
        cleaned = re.sub(
            r"^\s*(plan|schedule|create|organize|set up|make)\s+"
            r"(my\s+)?(day|tasks?|schedule|plan)[\s:,-]*",
            "", text, flags=re.IGNORECASE,
        ).strip()

        tasks: List[Dict] = []
        used_spans: List[tuple] = []

        # Pass 1: fixed time ranges ("X from H to H")
        self._extract_time_range_tasks(cleaned, tasks, used_spans)

        # Pass 2: "at Hpm for Yh" (single anchor + duration)
        self._extract_anchored_tasks(cleaned, tasks, used_spans)

        # Pass 3: duration-only ("X for Y hours/minutes") - MOST IMPORTANT
        self._extract_duration_tasks(cleaned, tasks, used_spans)

        # Pass 4: plain comma/and-separated segments with no time info
        self._extract_plain_tasks(cleaned, tasks, used_spans)

        # Enrich every task with category, difficulty, priority, optimal_slot
        for t in tasks:
            cat = self.categorize_task(t["name"])
            t["category"] = cat
            t.setdefault("difficulty", self.estimate_difficulty(t["name"]))
            t.setdefault("priority", self.estimate_priority(t["name"]))

            # IMPORTANT: Only set default duration if NO duration was specified
            # If duration is 0 (meaning no duration found), use default
            # If duration > 0, keep the user-specified value
            if t.get("duration", 0) == 0:
                t["duration"] = _CATEGORY_DEFAULT_DURATIONS.get(cat, 1.0)
            else:
                # User specified a duration, keep it as is
                t["duration"] = round(t["duration"], 1)

            # Inject optimal_slot so scheduler can use it
            if t.get("start_time") is None:
                t["optimal_slot"] = _CATEGORY_OPTIMAL_TIMES.get(cat, 10.0)

        tasks = self._deduplicate(tasks)
        return [t for t in tasks if self._is_valid_task(t)]

    # ── Extraction passes ──────────────────────────────────────────────────────

    def _extract_time_range_tasks(
        self, text: str, tasks: list, used: list
    ) -> None:
        """Match 'TASK from/at/between START to/until/- END'."""
        pattern = re.compile(
            r"(.+?)\s+(?:from|between|at)\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
            r"\s*(?:to|until|-|and)\s*"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            if self._overlaps(m.span(), used):
                continue
            name = _clean_name(m.group(1))
            start = _parse_time_str(m.group(2))
            end = _parse_time_str(m.group(3))
            if start is None or end is None or end <= start:
                continue
            tasks.append({
                "name": name,
                "duration": round(end - start, 2),
                "start_time": start,
                "end_time": end,
                "priority": self.estimate_priority(name),
                "difficulty": self.estimate_difficulty(name),
            })
            used.append(m.span())

    def _extract_anchored_tasks(
        self, text: str, tasks: list, used: list
    ) -> None:
        """Match 'TASK at H[:MM][am/pm] for Y [hours|mins]' and 'TASK at Hpm'."""
        p_with_dur = re.compile(
            r"([^,]+?)\s+at\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))"
            r"\s+for\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)",
            re.IGNORECASE,
        )
        p_no_dur = re.compile(
            r"([^,]+?)\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))(?!\s*(?:to|until|-))",
            re.IGNORECASE,
        )
        for pattern, has_dur in [(p_with_dur, True), (p_no_dur, False)]:
            for m in pattern.finditer(text):
                if self._overlaps(m.span(), used):
                    continue
                name = _clean_name(m.group(1))
                if not self._is_valid_name(name):
                    continue
                start = _parse_time_str(m.group(2))
                if start is None:
                    continue
                if has_dur:
                    raw = float(m.group(3))
                    unit = m.group(4).lower()
                    dur = raw / 60.0 if unit.startswith("min") else raw
                else:
                    cat = self.categorize_task(name)
                    dur = _CATEGORY_DEFAULT_DURATIONS.get(cat, 1.0)
                tasks.append({
                    "name": name,
                    "duration": round(dur, 2),
                    "start_time": start,
                    "end_time": round(start + dur, 2),
                    "priority": self.estimate_priority(name),
                    "difficulty": self.estimate_difficulty(name),
                })
                used.append(m.span())

    def _extract_duration_tasks(
        self, text: str, tasks: list, used: list
    ) -> None:
        """
        Match patterns like:
          'read books for 1 hour' → duration: 1.0
          'practice DSA for 3 hours' → duration: 3.0
          'study for 2 hours'
          'gym for 1hr'
          'read 30 minutes'
        """
        # Pattern 1: "X for/of Y hours/minutes" (MOST RELIABLE)
        p1 = re.compile(
            r"([^,]+?)\s+(?:for|of)\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|minutes?|mins?|m\b)",
            re.IGNORECASE,
        )
        
        for m in p1.finditer(text):
            if self._overlaps(m.span(), used):
                continue
            name = _clean_name(m.group(1))
            if not self._is_valid_name(name):
                continue
            raw = float(m.group(2))
            unit = m.group(3).lower()
            dur = raw / 60.0 if unit.startswith("min") else raw
            
            tasks.append({
                "name": name,
                "duration": round(max(dur, 0.25), 1),
                "start_time": None,
                "end_time": None,
                "priority": self.estimate_priority(name),
                "difficulty": self.estimate_difficulty(name),
            })
            used.append(m.span())
            logger.info(f"Duration task: '{name}' = {dur}h")

        # Pattern 2: "X Y hours/minutes" (without "for")
        p2 = re.compile(
            r"([^,]{2,40}?)\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|minutes?|mins?)",
            re.IGNORECASE,
        )
        
        for m in p2.finditer(text):
            if self._overlaps(m.span(), used):
                continue
            name = _clean_name(m.group(1))
            if not self._is_valid_name(name):
                continue
            # Skip if already captured
            if any(t["name"].lower() == name.lower() for t in tasks):
                continue
            raw = float(m.group(2))
            unit = m.group(3).lower()
            dur = raw / 60.0 if unit.startswith("min") else raw
            
            tasks.append({
                "name": name,
                "duration": round(max(dur, 0.25), 1),
                "start_time": None,
                "end_time": None,
                "priority": self.estimate_priority(name),
                "difficulty": self.estimate_difficulty(name),
            })
            used.append(m.span())
            logger.info(f"Duration task (no 'for'): '{name}' = {dur}h")

        # Pattern 3: "for Y hours X" (like "for 2 hours study")
        p3 = re.compile(
            r"for\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|minutes?|mins?)\s+([^,]+?)(?=$|,|\.|and)",
            re.IGNORECASE,
        )
        
        for m in p3.finditer(text):
            if self._overlaps(m.span(), used):
                continue
            raw = float(m.group(1))
            unit = m.group(2).lower()
            dur = raw / 60.0 if unit.startswith("min") else raw
            name = _clean_name(m.group(3))
            if not self._is_valid_name(name):
                continue
            tasks.append({
                "name": name,
                "duration": round(max(dur, 0.25), 1),
                "start_time": None,
                "end_time": None,
                "priority": self.estimate_priority(name),
                "difficulty": self.estimate_difficulty(name),
            })
            used.append(m.span())
            logger.info(f"Duration task (reverse): '{name}' = {dur}h")

    def _extract_plain_tasks(
        self, text: str, tasks: list, used: list
    ) -> None:
        """
        Split whatever remains by comma / 'and' / newline and treat each
        non-empty segment as a task with category-based default duration.
        ONLY used when no duration tasks were found.
        """
        masked = list(text)
        for start, end in used:
            for i in range(start, min(end, len(masked))):
                masked[i] = " "
        remaining = "".join(masked)

        segments = re.split(r",|\band\b|\n", remaining, flags=re.IGNORECASE)
        for seg in segments:
            name = _clean_name(seg)
            if not self._is_valid_name(name):
                continue
            if any(name.lower() in t["name"].lower() or
                   t["name"].lower() in name.lower()
                   for t in tasks):
                continue
            cat = self.categorize_task(name)
            tasks.append({
                "name": name,
                "duration": 0,  # Will be set to default later
                "start_time": None,
                "end_time": None,
                "priority": self.estimate_priority(name),
                "difficulty": self.estimate_difficulty(name),
            })

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _overlaps(span: tuple, used: list) -> bool:
        s, e = span
        return any(not (e <= us or s >= ue) for us, ue in used)

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        if not name or len(name) < 2:
            return False
        if name.lower() in _STOP_WORDS:
            return False
        if not re.search(r"[a-zA-Z]", name):
            return False
        return True

    @staticmethod
    def _is_valid_task(task: dict) -> bool:
        name = task.get("name", "")
        return NLProcessor._is_valid_name(name) and task.get("duration", 0) > 0

    @staticmethod
    def _deduplicate(tasks: list) -> list:
        """Remove tasks whose names are subsets of earlier tasks."""
        seen: List[str] = []
        unique = []
        for t in tasks:
            lower = t["name"].lower()
            if any(lower in s or s in lower for s in seen):
                continue
            seen.append(lower)
            unique.append(t)
        return unique

    # ── Difficulty estimation ─────────────────────────────────────────────────

    def estimate_difficulty(self, task_name: str) -> str:
        t = task_name.lower()

        hard_kw = {
            "complex", "difficult", "hard", "challenging", "intense",
            "major", "critical", "exam", "test", "assignment", "thesis",
            "research", "analysis", "essay", "report", "presentation",
            "project", "study", "revise", "revision", "learn", "practice",
            "prepare", "preparation", "develop", "build", "implement",
            "code", "debug", "design", "architecture", "deploy", "configure",
            "interview", "marathon", "triathlon", "competition", "tournament",
        }
        easy_kw = {
            "simple", "easy", "quick", "fast", "small", "minor",
            "routine", "brief", "check", "reply", "send", "read", "watch",
            "browse", "scroll", "listen", "walk", "stretch", "meditate",
            "nap", "rest", "buy", "pick up", "drop off", "pay bill",
        }

        if any(k in t for k in hard_kw):
            return "hard"
        if any(k in t for k in easy_kw):
            return "easy"

        cat = self.categorize_task(task_name)
        category_difficulty = {
            "study": "hard",
            "work": "medium",
            "creative": "medium",
            "health": "medium",
            "personal": "easy",
            "social": "easy",
        }
        return category_difficulty.get(cat, "medium")

    # ── Priority estimation ───────────────────────────────────────────────────

    def estimate_priority(self, task_name: str) -> str:
        t = task_name.lower()

        high_kw = {
            "urgent", "important", "critical", "asap", "immediately",
            "emergency", "priority", "must", "deadline", "due",
            "exam", "test", "interview", "presentation", "submission",
            "meeting", "appointment", "doctor", "hospital",
            "project", "client", "report",
        }
        low_kw = {
            "optional", "maybe", "someday", "later", "whenever",
            "if possible", "leisure", "fun", "relax", "chill",
            "browse", "scroll", "watch", "netflix", "youtube",
            "nap", "rest",
        }
        medium_high = {
            "study", "revise", "learn", "gym", "workout", "exercise",
            "finish", "complete", "write", "prepare",
        }

        if any(k in t for k in high_kw):
            return "high"
        if any(k in t for k in low_kw):
            return "low"
        if any(k in t for k in medium_high):
            return "medium"
        return "medium"

    # ── Remaining helpers ─────────────────────────────────────────────────────

    def extract_keywords(self, text: str) -> List[str]:
        words = text.lower().split()
        stop = {
            "a", "an", "the", "and", "or", "but", "in", "on",
            "at", "to", "for", "with", "by", "about", "like",
            "through", "during", "without",
        }
        return list({w for w in words if w not in stop and len(w) > 3})

    def detect_sentiment(self, text: str) -> str:
        pos = {
            "good", "great", "excellent", "amazing", "awesome", "love",
            "happy", "productive", "focused", "energetic", "motivated",
        }
        neg = {
            "bad", "terrible", "awful", "hate", "sad", "tired",
            "exhausted", "overwhelmed", "stressed", "anxious", "procrastinate",
        }
        words = set(text.lower().split())
        p = len(words & pos)
        n = len(words & neg)
        return "positive" if p > n else "negative" if n > p else "neutral"

    def extract_dates(self, text: str) -> List[str]:
        patterns = [
            r"(today|tomorrow|yesterday)",
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}",
        ]
        dates = []
        lower = text.lower()
        for p in patterns:
            dates.extend(re.findall(p, lower))
        return dates

    def categorize_task(self, task_name: str) -> str:
        t = task_name.lower()
        categories = {
            "work": [
                "work", "meeting", "email", "emails", "report", "presentation",
                "call", "office", "project", "client", "task", "deadline",
                "interview", "conference", "standup", "sprint",
            ],
            "study": [
                "study", "studies", "studying", "learn", "learning", "read", "reading",
                "course", "class", "homework", "assignment", "exam", "test",
                "research", "revise", "revision", "lecture", "tutorial",
                "practice", "college", "school", "university", "dsa", "book",
            ],
            "health": [
                "gym", "workout", "exercise", "run", "running", "yoga",
                "meditate", "meditation", "walk", "walking", "health", "jog",
                "jogging", "swim", "swimming", "cycling", "cycle", "lift",
                "weights", "fitness", "sport", "sports", "training",
            ],
            "creative": [
                "write", "writing", "design", "designing", "create", "creating",
                "draw", "drawing", "paint", "painting", "code", "coding",
                "develop", "developing", "build", "building", "compose",
                "composing", "edit", "editing", "film", "photograph",
            ],
            "personal": [
                "shop", "shopping", "clean", "cleaning", "cook", "cooking",
                "laundry", "organize", "organise", "pay", "bill", "bills",
                "errands", "errand", "chores", "chore", "grocery", "groceries",
                "appointment", "doctor", "dentist",
            ],
            "social": [
                "call", "meet", "friend", "friends", "family", "dinner",
                "lunch", "breakfast", "party", "hangout", "catch up",
                "visit", "date",
            ],
        }
        for cat, kws in categories.items():
            if any(k in t for k in kws):
                return cat
        return "other"

    def get_optimal_time_for_task(self, task_name: str) -> float:
        """Return the scientifically optimal start hour for a task."""
        cat = self.categorize_task(task_name)
        return _CATEGORY_OPTIMAL_TIMES.get(cat, 10.0)