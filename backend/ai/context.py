# backend/ai/context.py
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class UserContext:
    user_id: str
    history_count: int = 0
    recent_tasks: List[Dict] = field(default_factory=list)
    pending_tasks: List[Dict] = field(default_factory=list)
    patterns: Dict[str, Any] = field(default_factory=dict)
    streak: int = 0
    accuracy: Dict[str, float] = field(default_factory=dict)
    preferences: Dict = field(default_factory=dict)

    def to_prompt_string(self) -> str:
        """Convert context to a compact string for AI prompts"""
        parts = [f"User has {self.history_count} tasks tracked."]
        if self.streak > 0:
            parts.append(f"Current streak: {self.streak} days.")
        if self.accuracy:
            parts.append(f"Time accuracy: easy={self.accuracy.get('easy',1):.2f}x, "
                         f"medium={self.accuracy.get('medium',1):.2f}x, "
                         f"hard={self.accuracy.get('hard',1):.2f}x")
        if self.patterns.get("peak_hours", {}).get("peak_hours"):
            peaks = self.patterns["peak_hours"]["peak_hours"]
            parts.append(f"Most productive hours: {peaks}")
        return " ".join(parts)