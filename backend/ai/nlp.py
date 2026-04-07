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

AI-UPGRADE:
  If ANTHROPIC_API_KEY is set in your environment, NLProcessor.extract_tasks()
  will call Claude AI for deeper sentence understanding — it understands phrasing
  like "finish that maths thing before dinner" or mixed-language input that the
  regex engine would miss.
  If the key is NOT set, it falls back to the original regex engine automatically.
  No changes needed anywhere else in your codebase.
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── AI config (optional — set ANTHROPIC_API_KEY in your .env) ─────────────────
_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_CLAUDE_MODEL      = "claude-sonnet-4-20250514"
_API_URL           = "https://api.anthropic.com/v1/messages"

# ── Words that are NOT task names ──────────────────────────────────────────────
_STOP_WORDS = {
    "min", "mins", "minute", "minutes", "hour", "hours", "hr", "hrs",
    "utes", "am", "pm", "a", "an", "the", "and", "or", "but",
    "in", "on", "at", "to", "for", "with", "by", "about",
}

# ── Cleanup prefixes that sneak into task names ────────────────────────────────
_NAME_PREFIX_RE = re.compile(
    r"^[\s:,\-]+|"
    r"^\s*(and\s+then|and\s+also|also\s+then|and|also|plus|then|after\s+that"
    r"|i\s+have\s+to|i\s+need\s+to|i\s+want\s+to"
    r"|need\s+to|have\s+to|want\s+to|going\s+to|gonna|will)\s+",
    re.IGNORECASE,
)

# Phrases that are instructions/meta-commands — never task names
_INSTRUCTION_PHRASES = re.compile(
    r"^(add\s+this|include\s+this|do\s+this|schedule\s+this|add\s+it|"
    r"add\s+that|include\s+that|put\s+this|put\s+that|add\s+these|"
    r"also\s+add|also\s+include|also\s+schedule|can\s+you\s+add|"
    r"please\s+add|please\s+include|as\s+well|too|this|that|it)$",
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

# ── Claude AI system prompt for task extraction ────────────────────────────────
_AI_EXTRACTION_PROMPT = """
You are a task extraction engine for a scheduling app called Timevora.
Read the user message and return ONLY a JSON array of task objects. No explanation, no markdown fences.

Each object must have exactly these fields:
{
  "name": "clean task name only — strip ALL filler words",
  "duration": decimal hours or null if not mentioned,
  "start_time": decimal hour (9.0=9am, 14.5=2:30pm) or null,
  "end_time": decimal hour or null,
  "priority": "high" | "medium" | "low",
  "difficulty": "hard" | "medium" | "easy",
  "category": "study" | "work" | "health" | "creative" | "personal" | "social" | "other"
}

Rules you must follow:
1. TASK NAMES: Strip all filler — "i have to do", "also", "add this", "do this", "include this", "put this".
   Example: "i have to do Chemistry also for 1 hour add this" → name: "Chemistry"
2. "add this", "include that", "also", "do this", "add it" are instructions to you — NEVER task names.
3. DURATIONS: "30 minutes"→0.5, "90 mins"→1.5, "1.5 hours"→1.5, "2 hrs"→2.0
4. TIMES: "9 AM"→9.0, "2:30 PM"→14.5, "9 to 4"→start:9.0 end:16.0
5. MULTI-TASK: "study physics 2 hours and gym 1 hour" → two objects in the array.
6. If no real schedulable task exists (greeting, casual chat, holiday info) → return []
7. Never invent a task name. If unsure → return []
""".strip()


def _clean_name(raw: str) -> str:
    """Strip leading/trailing noise from an extracted task name."""
    name = raw.strip()
    # Strip trailing conversational filler
    name = re.sub(r"\s+(also|too|as\s+well)\s*$", "", name, flags=re.IGNORECASE).strip()
    # Strip leading instruction/filler words (including 'do')
    name = re.sub(r"^(also|add|include|schedule|do)\s+", "", name, flags=re.IGNORECASE).strip()
    for _ in range(8):  # multiple passes to catch chained noise
        prev = name
        name = _NAME_PREFIX_RE.sub("", name)
        name = _NAME_SUFFIX_RE.sub("", name)
        # Strip trailing standalone prepositions/articles
        name = re.sub(r"\s+(of|the|a|an|with|and|or|to|into)\s*$", "", name, flags=re.IGNORECASE)
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
    """
    Parse free-form task descriptions into structured task dicts.

    When ANTHROPIC_API_KEY is set, uses Claude AI for richer sentence
    understanding. Falls back to the original regex engine automatically
    when the key is absent or if the API call fails.

    All existing callers continue to work without any changes.
    """

    # ── Public API ─────────────────────────────────────────────────────────────

    def extract_tasks(self, text: str) -> List[Dict[str, Any]]:
        """
        Main entry point. Returns a list of task dicts:
        {name, duration, start_time, end_time, priority, difficulty, category, optimal_slot}

        Uses Claude AI if ANTHROPIC_API_KEY is set, otherwise uses regex engine.
        """
        if _ANTHROPIC_API_KEY:
            try:
                # Handle being called from both sync and async contexts
                try:
                    loop = asyncio.get_running_loop()
                    # Already inside an event loop — use thread pool to avoid deadlock
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, self._ai_extract(text))
                        ai_tasks = future.result(timeout=15)
                except RuntimeError:
                    # No running loop — safe to call asyncio.run directly
                    ai_tasks = asyncio.run(self._ai_extract(text))

                if ai_tasks is not None:
                    return self._enrich_tasks(ai_tasks)
            except Exception as e:
                logger.warning(f"NLProcessor: AI extraction failed, using regex fallback. Reason: {e}")

        return self._regex_extract_tasks(text)

    async def extract_tasks_async(self, text: str) -> List[Dict[str, Any]]:
        """
        Async-native version. Use this inside async route handlers
        to avoid event-loop conflicts.
        """
        if _ANTHROPIC_API_KEY:
            try:
                ai_tasks = await self._ai_extract(text)
                if ai_tasks is not None:
                    return self._enrich_tasks(ai_tasks)
            except Exception as e:
                logger.warning(f"NLProcessor: AI extraction failed, using regex fallback. Reason: {e}")

        return self._regex_extract_tasks(text)

    # ── Claude AI call ─────────────────────────────────────────────────────────

    async def _ai_extract(self, text: str) -> Optional[List[Dict]]:
        """
        Call Claude API and return a parsed list of task dicts.
        Returns None on any failure so caller can fall back to regex.
        """
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed — run: pip install httpx")
            return None

        headers = {
            "x-api-key":         _ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }
        body = {
            "model":      _CLAUDE_MODEL,
            "max_tokens": 800,
            "system":     _AI_EXTRACTION_PROMPT,
            "messages":   [{"role": "user", "content": text}],
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(_API_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            raw  = data["content"][0]["text"].strip()

        # Strip any accidental markdown fences Claude may have added
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])

        parsed = json.loads(raw.strip())
        if not isinstance(parsed, list):
            return None
        return parsed

    def _enrich_tasks(self, ai_tasks: List[Dict]) -> List[Dict[str, Any]]:
        """
        Take the raw list from Claude AI and fill every field so the output
        shape is identical to what the regex engine produces — so nothing
        downstream needs to change.
        """
        enriched = []
        for t in ai_tasks:
            name = (t.get("name") or "").strip()
            if not name or len(name) < 2:
                continue

            cat = t.get("category") or self.categorize_task(name)
            dur = t.get("duration") or 0
            if dur <= 0:
                dur = _CATEGORY_DEFAULT_DURATIONS.get(cat, 1.0)
            dur = round(max(dur, 0.25), 1)
            if dur > 12:
                dur = 3.0

            start = t.get("start_time")
            end   = t.get("end_time")
            if end is None and start is not None:
                end = round(start + dur, 2)

            task = {
                "name":       name,
                "duration":   dur,
                "start_time": start,
                "end_time":   end,
                "priority":   t.get("priority")   or self.estimate_priority(name),
                "difficulty": t.get("difficulty") or self.estimate_difficulty(name),
                "category":   cat,
            }
            if start is None:
                task["optimal_slot"] = _CATEGORY_OPTIMAL_TIMES.get(cat, 10.0)

            enriched.append(task)

        return enriched

    # ── Regex extraction engine (original, fully preserved) ───────────────────

    def _regex_extract_tasks(self, text: str) -> List[Dict[str, Any]]:
        """
        Original regex-based extraction — unchanged.
        Used automatically when AI is unavailable or disabled.

        Pre-splits the input on "and then", "then", "and" connectors so that
        each segment is processed independently — preventing names like
        "Then practice dsa" or tasks being merged/missed.
        """
        # ── Step 1: Strip scheduling preamble ────────────────────────────────
        cleaned = re.sub(
            r"^\s*(plan|schedule|create|organize|set up|make)\s+"
            r"(my\s+)?(day|tasks?|schedule|plan)[\s:,-]*",
            "", text, flags=re.IGNORECASE,
        ).strip()

        # ── Step 2: Also strip leading personal preamble ─────────────────────
        # e.g. "i have to do X ..." → "do X ..."
        cleaned = re.sub(
            r"^\s*(?:i\s+(?:have|need|want|am\s+going)\s+to\s+|"
            r"i\s+(?:will|should|must|got\s+to)\s+)+",
            "", cleaned, flags=re.IGNORECASE,
        ).strip()

        # ── Step 3: Pre-split on connectors if multiple durations present ─────
        _CONNECTOR_SPLIT = re.compile(
            r"\s*,\s*and\s+then\s+|\s+and\s+then\s+|\s*,\s*then\s+|\s+then\s+"
            r"|\s*,\s*and\s+|\s+and\s+|\s*[,;]\s*",
            re.IGNORECASE,
        )
        duration_count = len(re.findall(
            r"\d+(?:\.\d+)?\s*(?:hours?|hrs?|h\b|minutes?|mins?|min\b)",
            cleaned, re.IGNORECASE,
        ))

        if duration_count > 1:
            segments = _CONNECTOR_SPLIT.split(cleaned)
            all_tasks: List[Dict] = []
            for seg in segments:
                seg = seg.strip()
                if not seg or len(seg) < 2:
                    continue
                seg = _NAME_PREFIX_RE.sub("", seg).strip(" ,.-")
                if not seg:
                    continue
                seg_tasks: List[Dict] = []
                seg_used: List[tuple] = []
                self._extract_time_range_tasks(seg, seg_tasks, seg_used)
                self._extract_anchored_tasks(seg, seg_tasks, seg_used)
                self._extract_duration_tasks(seg, seg_tasks, seg_used)
                self._extract_plain_tasks(seg, seg_tasks, seg_used)
                all_tasks.extend(seg_tasks)
            tasks = all_tasks
        else:
            tasks = []
            used_spans: List[tuple] = []
            self._extract_time_range_tasks(cleaned, tasks, used_spans)
            self._extract_anchored_tasks(cleaned, tasks, used_spans)
            self._extract_duration_tasks(cleaned, tasks, used_spans)
            self._extract_plain_tasks(cleaned, tasks, used_spans)

        # ── Step 4: Enrich every task ─────────────────────────────────────────
        for t in tasks:
            cat = self.categorize_task(t["name"])
            t["category"] = cat
            t.setdefault("difficulty", self.estimate_difficulty(t["name"]))
            t.setdefault("priority", self.estimate_priority(t["name"]))

            if t.get("duration", 0) == 0:
                t["duration"] = _CATEGORY_DEFAULT_DURATIONS.get(cat, 1.0)
            else:
                t["duration"] = round(t["duration"], 1)

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
            # Reject instruction phrases that leak through (e.g. "add this", bare "this")
            if _INSTRUCTION_PHRASES.match(name):
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
        name = task.get("name", "").strip()
        if not name:
            return False
        # Reject instruction phrases like "add this", bare "this", "that", "it"
        if _INSTRUCTION_PHRASES.match(name):
            return False
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

    # ── Remaining helpers (all unchanged) ─────────────────────────────────────

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
                "physics", "chemistry", "biology", "maths", "math", "history",
                "english", "geography", "science", "economics", "leetcode",
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
