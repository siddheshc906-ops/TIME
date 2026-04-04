from typing import List, Dict, Any
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TaskRecommender:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        
    async def get_recommendations(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get personalized task recommendations"""
        
        recommendations = {
            "priority_tasks": await self._recommend_priority_tasks(),
            "time_slots": await self._recommend_time_slots(),
            "task_optimizations": await self._recommend_task_optimizations(),
            "productivity_boosters": await self._recommend_productivity_boosters(context),
            "learning_suggestions": await self._recommend_learning(context)
        }
        
        return recommendations
    
    async def _recommend_priority_tasks(self) -> List[Dict]:
        """Recommend which tasks to prioritize"""
        
        # Get pending tasks
        cursor = self.db.tasks.find({
            "user_id": self.user_id,
            "completed": False
        })
        
        pending_tasks = await cursor.to_list(20)
        
        if not pending_tasks:
            return []
        
        # Score tasks based on various factors
        scored_tasks = []
        
        for task in pending_tasks:
            score = 0
            
            # Priority factor
            priority_scores = {"high": 10, "medium": 5, "low": 1}
            score += priority_scores.get(task.get("priority", "medium"), 5)
            
            # Deadline factor (if exists)
            if "deadline" in task:
                days_until = (task["deadline"] - datetime.now()).days
                if days_until < 0:
                    score += 20  # Overdue
                elif days_until == 0:
                    score += 15  # Due today
                elif days_until <= 2:
                    score += 10  # Due soon
                elif days_until <= 5:
                    score += 5   # Due this week
            
            # Difficulty factor
            difficulty_scores = {"hard": 8, "medium": 4, "easy": 2}
            score += difficulty_scores.get(task.get("difficulty", "medium"), 4)
            
            # Time investment factor
            estimated_time = task.get("estimated_time", 1)
            if estimated_time <= 0.5:
                score += 3  # Quick wins
            elif estimated_time <= 1:
                score += 2
            
            scored_tasks.append({
                "task": task,
                "score": score,
                "reason": self._get_priority_reason(score)
            })
        
        # Sort by score
        scored_tasks.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_tasks[:5]  # Top 5 recommendations
    
    def _get_priority_reason(self, score: int) -> str:
        """Get reason for priority score"""
        if score >= 30:
            return "🔥 Top priority - urgent and important"
        elif score >= 20:
            return "⭐ High priority - should do today"
        elif score >= 10:
            return "📌 Medium priority - schedule soon"
        else:
            return "⚡ Low priority - can wait"
    
    async def _recommend_time_slots(self) -> List[Dict]:
        """Recommend optimal time slots for tasks"""
        
        # Get user's productivity patterns
        from .analyzer import ProductivityAnalyzer
        analyzer = ProductivityAnalyzer(self.user_id, self.db)
        patterns = await analyzer.analyze_patterns()
        
        recommendations = []
        
        # Recommend based on peak hours
        peak_hours = patterns.get("peak_hours", {}).get("peak_hours", [])
        if peak_hours:
            recommendations.append({
                "type": "peak_hours",
                "message": f"Your peak productivity hours are around {peak_hours[0]}:00",
                "suggestion": "Schedule your most important tasks during this time"
            })
        
        # Recommend based on energy patterns
        energy_patterns = patterns.get("energy_patterns", {})
        best_slot = energy_patterns.get("best_time_slot")
        if best_slot:
            slot_names = {
                "morning": "morning (5 AM - 12 PM)",
                "afternoon": "afternoon (12 PM - 5 PM)",
                "evening": "evening (5 PM - 10 PM)",
                "night": "night (10 PM - 5 AM)"
            }
            recommendations.append({
                "type": "energy_slot",
                "message": f"You're most productive in the {slot_names.get(best_slot, best_slot)}",
                "suggestion": "Plan deep work sessions during this time"
            })
        
        return recommendations
    
    async def _recommend_task_optimizations(self) -> List[str]:
        """Recommend task optimizations"""
        
        # Get recent tasks
        cursor = self.db.task_history.find({
            "user_id": self.user_id
        }).sort("created_at", -1).limit(20)
        
        recent_tasks = await cursor.to_list(20)
        
        if not recent_tasks:
            return ["Start tracking tasks to get optimization suggestions"]
        
        optimizations = []
        
        # Check for similar tasks that could be batched
        task_names = [t.get("name", "") for t in recent_tasks]
        name_counts = {}
        for name in task_names:
            name_counts[name] = name_counts.get(name, 0) + 1
        
        similar_tasks = [name for name, count in name_counts.items() if count >= 3 and name]
        if similar_tasks:
            optimizations.append(
                f"🔄 You frequently do '{similar_tasks[0]}'. Consider batching similar tasks together."
            )
        
        # Check for task duration patterns
        durations = [t.get("actualTime", 0) for t in recent_tasks if t.get("actualTime")]
        if durations:
            avg_duration = sum(durations) / len(durations)
            if avg_duration > 2:
                optimizations.append(
                    f"⏱️ Your tasks average {avg_duration:.1f} hours. Consider breaking them into smaller chunks."
                )
        
        # Check for task completion patterns
        completed = len([t for t in recent_tasks if t.get("actualTime")])
        if completed < len(recent_tasks) * 0.5:
            optimizations.append(
                "🎯 Your completion rate is low. Try the '2-minute rule' for small tasks."
            )
        
        return optimizations
    
    async def _recommend_productivity_boosters(self, context: Dict) -> List[str]:
        """Recommend productivity boosters based on context"""
        
        boosters = []
        
        # Time-based boosters
        current_hour = datetime.now().hour
        
        if 5 <= current_hour < 9:
            boosters.append(
                "🌅 Great morning for deep work. Start with your most challenging task!"
            )
        elif 12 <= current_hour < 14:
            boosters.append(
                "🍽️ Post-lunch dip? Take a short walk or do light tasks now."
            )
        elif 15 <= current_hour < 17:
            boosters.append(
                "☕ Afternoon energy boost time! Perfect for creative work."
            )
        elif 20 <= current_hour < 23:
            boosters.append(
                "🌙 Evening calm. Great for planning tomorrow or light reading."
            )
        
        # Task-based boosters
        pending_count = context.get("pending_tasks", [])
        if len(pending_count) > 10:
            boosters.append(
                "📋 You have many pending tasks. Try the Eisenhower Matrix to prioritize."
            )
        
        # Streak-based boosters
        if context.get("stats", {}).get("streak", 0) > 5:
            boosters.append(
                f"🔥 {context['stats']['streak']} day streak! Keep the momentum going!"
            )
        
        return boosters[:4]
    
    async def _recommend_learning(self, context: Dict) -> List[str]:
        """Recommend learning opportunities"""
        
        recommendations = []
        
        # Get user's weak areas
        history = context.get("task_history", [])
        
        if not history:
            recommendations.append(
                "📚 Start tracking tasks to get personalized learning recommendations!"
            )
            return recommendations
        
        # Check difficulty areas
        hard_tasks = [t for t in history if t.get("difficulty") == "hard" and t.get("actualTime")]
        if hard_tasks:
            hard_completion = len([t for t in hard_tasks if t.get("actualTime")])
            if hard_completion < len(hard_tasks) * 0.3:
                recommendations.append(
                    "💪 You struggle with hard tasks. Try breaking them into smaller steps."
                )
        
        # Check time estimation
        accuracies = []
        for task in history:
            if task.get("actualTime") and task.get("aiTime"):
                accuracies.append(task["actualTime"] / task["aiTime"])
        
        if accuracies:
            avg_accuracy = sum(accuracies) / len(accuracies)
            if avg_accuracy > 1.2:
                recommendations.append(
                    "⏱️ You tend to underestimate time. Add 25% buffer to your estimates."
                )
            elif avg_accuracy < 0.8:
                recommendations.append(
                    "⏱️ You overestimate time. You're faster than you think!"
                )
        
        # Suggest techniques
        if len(history) > 20:
            recommendations.append(
                "🧠 Try the Pomodoro Technique: 25 min work, 5 min break."
            )
            recommendations.append(
                "📊 Use time blocking to group similar tasks together."
            )
        
        return recommendations[:3]