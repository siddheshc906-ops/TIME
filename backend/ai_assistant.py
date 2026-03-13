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

logger = logging.getLogger(__name__)

class IntentType(str, Enum):
    CREATE_SCHEDULE = "create_schedule"
    MODIFY_SCHEDULE = "modify_schedule"
    ASK_QUESTION = "ask_question"
    GET_ADVICE = "get_advice"
    ANALYZE_HABITS = "analyze_habits"
    CHECK_PROGRESS = "check_progress"
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

class AIAssistant:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        # Initialize OpenAI client
        openai.api_key = os.getenv("OPENAI_API_KEY")
    
    async def process_message(self, message: str) -> Dict[str, Any]:
        """Main entry point for processing user messages with AI"""
        
        try:
            # Try AI first
            intent = await self._detect_intent(message)
            user_context = await self._get_user_context()
            
            # Create AI prompt
            system_prompt = self._create_ai_prompt(intent, user_context)
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            ai_message = response.choices[0].message.content
            
            # Try to parse AI response as JSON
            try:
                ai_response = json.loads(ai_message)
                return ai_response
            except:
                # If AI response isn't JSON, fall back to rule-based
                return await self._rule_based_processing(message)
                
        except Exception as e:
            logger.error(f"AI error: {e}")
            # Fall back to rule-based system
            return await self._rule_based_processing(message)
    
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
        {"time": "9:00 AM - 11:00 AM", "task": "Task description"},
        {"time": "11:30 AM - 12:30 PM", "task": "Another task"}
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
        "avg_task_duration": "X.X hours"
    },
    "insight": "Personalized insight"
}"""
        
        else:
            return base_prompt + """Have a friendly conversation about productivity.
Respond with:
{
    "type": "chat",
    "message": "Friendly response",
    "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3"]
}"""
    
    async def _rule_based_processing(self, message: str) -> Dict[str, Any]:
        """Your original rule-based processing (kept exactly as is)"""
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
        """Detect user intent (your original method)"""
        message_lower = message.lower()
        
        # STRONG SCHEDULE DETECTION
        # Check for time indicators
        has_time = any(word in message_lower for word in ["am", "pm", ":", "from", "to", "hour", "minute"])
        # Check for activities
        has_activity = any(word in message_lower for word in [
            "college", "school", "work", "study", "exercise", "gym", 
            "read", "book", "meeting", "class", "task", "do"
        ])
        
        # If message has both time and activity, it's a schedule
        if has_time and has_activity:
            return IntentType.CREATE_SCHEDULE
        
        # Check for explicit schedule keywords
        if any(phrase in message_lower for phrase in [
            "plan", "schedule", "create", "organize", "tasks for",
            "i need to", "i have to", "to do", "my day"
        ]):
            return IntentType.CREATE_SCHEDULE
        
        # Other intents
        if any(phrase in message_lower for phrase in ["advice", "suggest", "recommend", "tips"]):
            return IntentType.GET_ADVICE
        
        if any(phrase in message_lower for phrase in ["what is", "how do", "why", "when", "explain"]):
            return IntentType.ASK_QUESTION
        
        if any(phrase in message_lower for phrase in ["analyze", "habits", "patterns", "progress"]):
            return IntentType.ANALYZE_HABITS
        
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
        """Create schedule from natural language"""
        
        tasks = await self._extract_tasks_naturally(message)
        
        if not tasks:
            return {
                "type": "clarification",
                "message": "I'd love to help you plan! Could you tell me what tasks you need to do? For example: 'Study for 2 hours, go to the gym, and finish the report' or 'I have college from 8:30 AM to 4 PM'"
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
        """Provide productivity advice"""
        
        advice_list = [
            "Start with your most important task (Eat that frog!) 🐸",
            "Use the Pomodoro Technique: 25 min work, 5 min break",
            "Plan your day the night before to reduce decision fatigue",
            "Take a 5-minute break every hour to maintain focus",
            "Group similar tasks together to stay in flow state",
            "The first 2 hours of your day are your most productive - use them wisely!"
        ]
        
        return {
            "type": "advice",
            "message": "Here are my top productivity tips:",
            "advice_points": random.sample(advice_list, 3),
            "insight": "You're most productive when you tackle difficult tasks early in the day!"
        }
    
    async def _handle_question(self, message: str) -> Dict[str, Any]:
        """Answer questions"""
        
        knowledge_base = {
            "pomodoro": "The Pomodoro Technique uses 25-minute focused work sessions with 5-minute breaks. After 4 pomodoros, take a longer 15-30 minute break. It's great for maintaining focus!",
            "procrastination": "To beat procrastination, try the 5-minute rule: commit to working for just 5 minutes. Starting is often the hardest part. Also, break large tasks into smaller steps.",
            "priority": "Use the Eisenhower Matrix: Urgent & Important (do first), Important Not Urgent (schedule), Urgent Not Important (delegate), Neither (eliminate).",
            "focus": "To improve focus: eliminate distractions, use website blockers, try background music, and practice mindfulness. Also, ensure you're getting enough sleep!"
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
            "message": "That's a great question! While I specialize in productivity, I can help you with scheduling and task management. Could you rephrase or ask about something specific?",
            "suggestions": [
                "How do I beat procrastination?",
                "What's the best way to prioritize?",
                "Tell me about the Pomodoro technique"
            ]
        }
    
    async def _handle_habit_analysis(self) -> Dict[str, Any]:
        """Analyze user habits"""
        
        # Get task history from database
        collection = self.db['task_history']
        cursor = collection.find({"user_id": self.user_id}).sort("date", -1).limit(20)
        history = await cursor.to_list(length=20)
        
        if not history:
            return {
                "type": "analysis",
                "message": "I need more data to analyze your habits! Start using the planner for a few days, and I'll give you personalized insights.",
                "suggestions": ["Plan my day", "Add some tasks"]
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
            "insight": "You complete tasks faster in the morning. Schedule important work before noon!" if completion_rate > 50 else "Try planning your most important tasks for your peak energy hours."
        }
    
    async def _handle_general_chat(self, message: str) -> Dict[str, Any]:
        """Handle general conversation"""
        
        responses = {
            "hello": "Hi there! 👋 Ready to boost your productivity today? I can help you plan your day, answer questions, or give personalized advice.",
            "hi": "Hello! How can I help you organize your day?",
            "thanks": "You're welcome! Happy to help you stay productive! 🚀",
            "thank you": "My pleasure! Let me know if you need anything else.",
            "help": "I can help you with:\n• Planning your day (try: 'Plan my day: study 2h, gym')\n• Productivity advice (try: 'Give me tips')\n• Answering questions (try: 'What is pomodoro?')\n• Analyzing habits (try: 'Analyze my progress')"
        }
        
        message_lower = message.lower()
        
        for key, response in responses.items():
            if key in message_lower:
                return {
                    "type": "chat",
                    "message": response,
                    "suggestions": [
                        "Plan my day: study 2 hours, go to gym",
                        "Give me productivity advice",
                        "Analyze my habits"
                    ]
                }
        
        return {
            "type": "chat",
            "message": "I'm here to help with productivity! Would you like to plan your day, get some tips, or ask a question?",
            "suggestions": ["Plan my day", "Give me tips", "What is pomodoro?"]
        }

async def get_ai_context(user_id: str, db):
    """Get AI context for frontend"""
    
    # Get user's recent activity
    collection = db['task_history']
    count = await collection.count_documents({"user_id": user_id})
    
    suggestions = [
        "Plan my day: study for 2 hours, go to the gym at 4pm, and finish project by evening",
        "Give me productivity advice for deep work",
        "How can I improve my focus?",
        "Analyze my productivity habits this week"
    ]
    
    if count > 0:
        suggestions.insert(0, "Show me my progress")
    
    return {
        "suggestions": suggestions,
        "has_history": count > 0,
        "quick_actions": ["Create Schedule", "Get Advice", "Analyze Habits"]
    }
