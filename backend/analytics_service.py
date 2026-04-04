# backend/analytics_service.py
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import numpy as np
from bson import ObjectId
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self, db):
        self.db = db
    
    async def get_user_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user analytics based on real user data only"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            analytics = {
                'overview': {
                    'total_tasks': 0,
                    'completed': 0,
                    'completion_rate': 0,
                    'high_priority_tasks': 0,
                    'avg_task_duration': 0
                },
                'daily': [],
                'tasks_by_priority': {'high': 0, 'medium': 0, 'low': 0},
                'tasks_by_difficulty': {'easy': 0, 'medium': 0, 'hard': 0},
                'ai_performance': {
                    'avg_error': 0,
                    'max_error': 0,
                    'min_error': 0,
                    'accuracy_trend': []
                },
                'focus_analysis': {
                    'peak_hours': [],
                    'focus_score': 0,
                    'avg_focus_duration': 0
                },
                'recommendations': []
            }
            
            # Get task history from database
            history = []
            try:
                cursor = self.db.task_history.find({
                    "user_id": user_id,
                    "created_at": {"$gte": start_date.isoformat()}
                }).sort("created_at", 1)
                
                async for task in cursor:
                    history.append(task)
            except Exception as e:
                logger.error(f"Error fetching task history: {e}")

            # Also get tasks from tasks collection
            tasks_list = []
            try:
                cursor2 = self.db.tasks.find({
                    "user_id": user_id,
                    "is_deleted": {"$ne": True}
                })
                async for task in cursor2:
                    tasks_list.append(task)
            except Exception as e:
                logger.error(f"Error fetching tasks: {e}")

            # If no data at all, return empty analytics
            if not history and not tasks_list:
                logger.info(f"No data found for user {user_id}, returning empty analytics")
                analytics['recommendations'] = [
                    "🚀 Add your first task to get started!",
                    "📋 Create tasks and complete them to see your analytics here.",
                    "🎯 Track your productivity by logging task completion times."
                ]
                return analytics
            
            # Process tasks collection for overview
            if tasks_list:
                total_tasks = len(tasks_list)
                completed = sum(1 for t in tasks_list if t.get('completed', False) or t.get('status') == 'completed')
                high_priority = sum(1 for t in tasks_list if t.get('priority') == 'high')
                
                durations = [t.get('duration', t.get('estimated_time', 0)) for t in tasks_list if t.get('duration') or t.get('estimated_time')]
                avg_duration = float(np.mean(durations)) / 60 if durations else 0  # convert minutes to hours

                analytics['overview'] = {
                    'total_tasks': total_tasks,
                    'completed': completed,
                    'completion_rate': round((completed / total_tasks) * 100, 1) if total_tasks else 0,
                    'high_priority_tasks': high_priority,
                    'avg_task_duration': round(avg_duration, 1)
                }

                # Tasks by priority
                for task in tasks_list:
                    priority = task.get('priority', 'medium')
                    if priority in analytics['tasks_by_priority']:
                        analytics['tasks_by_priority'][priority] += 1

                # Tasks by difficulty
                for task in tasks_list:
                    difficulty = task.get('difficulty', 'medium')
                    if difficulty in analytics['tasks_by_difficulty']:
                        analytics['tasks_by_difficulty'][difficulty] += 1

            # Process real task history data
            if history:
                try:
                    # Daily breakdown
                    daily_stats = {}
                    for task in history:
                        created_at = task.get('created_at', '')
                        if isinstance(created_at, str):
                            date = created_at[:10]
                        else:
                            date = created_at.strftime('%Y-%m-%d')
                        
                        if date not in daily_stats:
                            daily_stats[date] = {'total': 0, 'completed': 0, 'focus_hours': 0}
                        
                        daily_stats[date]['total'] += 1
                        if task.get('completed'):
                            daily_stats[date]['completed'] += 1
                        
                        task_duration = task.get('actual_time', task.get('ai_time', 0))
                        daily_stats[date]['focus_hours'] += task_duration
                    
                    analytics['daily'] = [
                        {'date': date, **stats} for date, stats in sorted(daily_stats.items())
                    ]
                    
                    # AI performance analysis
                    predictions = [
                        t for t in history 
                        if t.get('ai_time') and t.get('actual_time') and t.get('ai_time') > 0
                    ]
                    
                    if predictions:
                        errors = [
                            abs(p['ai_time'] - p['actual_time']) / p['actual_time'] * 100 
                            for p in predictions
                        ]
                        analytics['ai_performance'] = {
                            'avg_error': round(float(np.mean(errors)), 1),
                            'max_error': round(float(np.max(errors)), 1),
                            'min_error': round(float(np.min(errors)), 1),
                            'accuracy_trend': [
                                {
                                    'date': p.get('created_at', '')[:10] if isinstance(p.get('created_at'), str) else '',
                                    'error': round(abs(p['ai_time'] - p['actual_time']), 1)
                                }
                                for p in predictions[-20:]
                            ]
                        }
                    
                    # Peak hours analysis
                    hour_completion = {}
                    for task in history:
                        if task.get('completed'):
                            created_at = task.get('created_at', '')
                            if isinstance(created_at, str):
                                try:
                                    hour = datetime.fromisoformat(created_at.replace('Z', '+00:00')).hour
                                    hour_completion[hour] = hour_completion.get(hour, 0) + 1
                                except:
                                    pass
                    
                    if hour_completion:
                        sorted_hours = sorted(hour_completion.items(), key=lambda x: x[1], reverse=True)
                        analytics['focus_analysis']['peak_hours'] = [h for h, _ in sorted_hours[:3]]
                    
                    # Focus score calculation
                    total = analytics['overview']['total_tasks']
                    comp = analytics['overview']['completed']
                    if total > 0:
                        analytics['focus_analysis']['focus_score'] = round((comp / total) * 100)
                    
                except Exception as e:
                    logger.error(f"Error processing analytics data: {e}")
            
            # Generate recommendations
            analytics['recommendations'] = await self.generate_recommendations(analytics, history)
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error in get_user_analytics: {e}")
            return {
                'overview': {'total_tasks': 0, 'completed': 0, 'completion_rate': 0, 'high_priority_tasks': 0, 'avg_task_duration': 0},
                'daily': [],
                'tasks_by_priority': {'high': 0, 'medium': 0, 'low': 0},
                'tasks_by_difficulty': {'easy': 0, 'medium': 0, 'hard': 0},
                'ai_performance': {'avg_error': 0, 'max_error': 0, 'min_error': 0, 'accuracy_trend': []},
                'focus_analysis': {'peak_hours': [], 'focus_score': 0, 'avg_focus_duration': 0},
                'recommendations': ["🚀 Start adding tasks to track your productivity!"]
            }
    
    async def generate_recommendations(self, analytics: Dict, history: List = None) -> List[str]:
        """Generate recommendations based on real analytics"""
        recommendations = []
        
        try:
            overview = analytics.get('overview', {})
            completion_rate = overview.get('completion_rate', 0)
            total_tasks = overview.get('total_tasks', 0)

            if total_tasks == 0:
                return [
                    "🚀 Add your first task to get started!",
                    "📋 Complete tasks to see your productivity analytics.",
                    "🎯 Set priorities on your tasks for better insights."
                ]
            
            # Completion rate based recommendations
            if completion_rate < 30:
                recommendations.append("📉 Your completion rate is low. Start with just 3 small tasks daily to build momentum.")
            elif completion_rate < 50:
                recommendations.append("📊 You're making progress! Try breaking larger tasks into smaller chunks.")
            elif completion_rate < 70:
                recommendations.append("👍 Good progress! Challenge yourself by adding one extra task each day.")
            elif completion_rate < 90:
                recommendations.append("🚀 Excellent! You're very productive. Consider taking on more challenging tasks.")
            else:
                recommendations.append("🌟 Outstanding! You're crushing your goals. Time to set higher targets!")
            
            # Priority-based recommendations
            high_priority = analytics['tasks_by_priority'].get('high', 0)
            if total_tasks > 0 and high_priority / total_tasks > 0.4:
                recommendations.append("🎯 You have many high-priority tasks. Start your day with the most important one.")
            
            # AI accuracy recommendations
            ai_performance = analytics.get('ai_performance', {})
            avg_error = ai_performance.get('avg_error', 0)
            if avg_error > 30:
                recommendations.append("🤖 Help me improve! Please provide feedback on task completion times.")
            elif 0 < avg_error < 10:
                recommendations.append(f"🎯 I'm {100 - avg_error:.0f}% accurate at predicting your tasks!")
            
            # Peak hours recommendations
            peak_hours = analytics['focus_analysis'].get('peak_hours', [])
            if peak_hours:
                hour_str = ', '.join([f"{h}:00" for h in peak_hours[:2]])
                recommendations.append(f"⏰ You're most productive at {hour_str}. Schedule important work then.")
            
            # Task duration recommendations
            avg_duration = overview.get('avg_task_duration', 0)
            if avg_duration > 2:
                recommendations.append("💡 Your tasks take longer than average. Consider breaking them into smaller chunks.")
            elif 0 < avg_duration < 0.5:
                recommendations.append("⚡ Quick tasks! Try batching similar small tasks together for efficiency.")
            
            # General tip
            tips = [
                "🧠 Take short breaks between tasks to maintain focus",
                "💧 Stay hydrated - it improves cognitive function",
                "🎵 Try focus music or white noise for deep work",
                "📵 Put your phone away during focus sessions",
                "🌅 Plan your most important task the night before",
                "🎯 Use the 2-minute rule: if it takes <2 mins, do it now"
            ]
            recommendations.append(random.choice(tips))
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations = ["📊 Keep adding and completing tasks to get personalized recommendations!"]
        
        # Return unique recommendations, limited to 5
        seen = set()
        unique_recs = []
        for rec in recommendations:
            if rec not in seen and len(unique_recs) < 5:
                seen.add(rec)
                unique_recs.append(rec)
        
        return unique_recs
    
    async def get_productivity_trend(self, user_id: str, days: int = 30) -> List[Dict]:
        """Get productivity trend over time"""
        try:
            analytics = await self.get_user_analytics(user_id, days)
            return analytics.get('daily', [])
        except Exception as e:
            logger.error(f"Error getting productivity trend: {e}")
            return []
    
    async def get_peak_hours(self, user_id: str) -> List[int]:
        """Get user's peak productivity hours"""
        try:
            analytics = await self.get_user_analytics(user_id, 30)
            return analytics['focus_analysis'].get('peak_hours', [])
        except Exception as e:
            logger.error(f"Error getting peak hours: {e}")
            return []
    
    async def get_ai_accuracy_summary(self, user_id: str) -> Dict:
        """Get AI accuracy summary"""
        try:
            analytics = await self.get_user_analytics(user_id, 30)
            return analytics.get('ai_performance', {
                'avg_error': 0,
                'max_error': 0,
                'min_error': 0
            })
        except Exception as e:
            logger.error(f"Error getting AI accuracy: {e}")
            return {'avg_error': 0, 'max_error': 0, 'min_error': 0}
