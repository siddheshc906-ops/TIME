# backend/ml_service.py
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from datetime import datetime, timedelta
import joblib
import os
from typing import List, Dict, Any, Optional
import asyncio
from bson import ObjectId
import pandas as pd
import json

class TimevoraLearner:
    def __init__(self, user_id: str, db=None):
        self.user_id = user_id
        self.db = db
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = [
            'hour_of_day', 'day_of_week', 'month', 'is_weekend',
            'priority_score', 'difficulty_score', 'task_length',
            'similar_tasks_avg', 'time_since_last_task', 'completed_yesterday',
            'energy_level', 'focus_score', 'interruptions'
        ]
        
        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)
        
        self.model_path = f"models/user_{user_id}_model.pkl"
        self.scaler_path = f"models/user_{user_id}_scaler.pkl"
        
    async def load_or_train_model(self):
        """Load existing model or train new one"""
        if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
            try:
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                return True
            except:
                pass
        
        # Train new model
        return await self.train_model()
    
    async def get_training_data(self) -> Optional[pd.DataFrame]:
        """Fetch and prepare training data from user history"""
        if not self.db:
            return None
            
        # Get task history
        history = []
        cursor = self.db.task_history.find({"user_id": self.user_id}).sort("created_at", -1).limit(500)
        async for task in cursor:
            history.append(task)
        
        if len(history) < 10:
            return None
        
        data = []
        for i, task in enumerate(history):
            try:
                # Features
                created_at = task.get('created_at', datetime.now().isoformat())
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                
                # Time features
                hour = created_at.hour
                day = created_at.weekday()
                month = created_at.month
                is_weekend = 1 if day >= 5 else 0
                
                # Task features
                priority_scores = {'low': 1, 'medium': 2, 'high': 3}
                difficulty_scores = {'easy': 1, 'medium': 2, 'hard': 3}
                
                priority_score = priority_scores.get(task.get('priority', 'medium'), 2)
                difficulty_score = difficulty_scores.get(task.get('difficulty', 'medium'), 2)
                task_length = len(task.get('name', task.get('text', '')))
                
                # Similar tasks average
                similar_tasks = [t for t in history if t.get('name', '')[:10] == task.get('name', '')[:10]]
                similar_avg = np.mean([t.get('actual_time', t.get('ai_time', 1)) for t in similar_tasks]) if similar_tasks else 1
                
                # Time since last task
                if i > 0:
                    prev_time = history[i-1].get('created_at', datetime.now().isoformat())
                    if isinstance(prev_time, str):
                        prev_time = datetime.fromisoformat(prev_time.replace('Z', '+00:00'))
                    time_since = (created_at - prev_time).total_seconds() / 3600  # in hours
                else:
                    time_since = 8  # default
                
                # Completed yesterday
                completed_yesterday = 1 if i > 0 and created_at.day != datetime.now().day else 0
                
                # Energy level (time-based heuristic)
                if 5 <= hour <= 11:
                    energy = 0.9
                elif 12 <= hour <= 14:
                    energy = 0.6
                elif 15 <= hour <= 18:
                    energy = 0.8
                else:
                    energy = 0.5
                
                # Focus score
                focus = 1.0 - (difficulty_score / 5) * (min(task_length, 50) / 50)
                
                # Interruptions
                interruptions = 0.2 if 9 <= hour <= 11 or 15 <= hour <= 17 else 0.5
                
                # Target: actual duration vs estimated
                actual = task.get('actual_time', task.get('ai_time', 1))
                estimated = task.get('ai_time', 1)
                accuracy_ratio = actual / estimated if estimated > 0 else 1
                
                data.append([
                    hour, day, month, is_weekend,
                    priority_score, difficulty_score, task_length,
                    similar_avg, time_since, completed_yesterday,
                    energy, focus, interruptions,
                    accuracy_ratio
                ])
            except Exception as e:
                print(f"Error processing task: {e}")
                continue
        
        if len(data) < 10:
            return None
        
        columns = self.feature_columns + ['accuracy_ratio']
        return pd.DataFrame(data, columns=columns)
    
    async def train_model(self):
        """Train the ML model on user history"""
        try:
            df = await self.get_training_data()
            if df is None or len(df) < 10:
                return False
            
            X = df[self.feature_columns].values
            y = df['accuracy_ratio'].values
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            self.model.fit(X_scaled, y)
            
            # Save model
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            
            return True
        except Exception as e:
            print(f"Error training model: {e}")
            return False
    
    async def predict_accuracy(self, task: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Predict how accurate the AI will be for this task"""
        try:
            if self.model is None:
                await self.load_or_train_model()
            
            if self.model is None:
                return 1.0  # Default if no model
            
            # Extract features
            hour = context.get('hour', datetime.now().hour)
            day = context.get('day', datetime.now().weekday())
            month = context.get('month', datetime.now().month)
            is_weekend = 1 if day >= 5 else 0
            
            priority_scores = {'low': 1, 'medium': 2, 'high': 3}
            difficulty_scores = {'easy': 1, 'medium': 2, 'hard': 3}
            
            priority_score = priority_scores.get(task.get('priority', 'medium'), 2)
            difficulty_score = difficulty_scores.get(task.get('difficulty', 'medium'), 2)
            task_length = len(task.get('name', task.get('text', '')))
            
            # Get similar tasks average (simplified)
            similar_avg = 1.0
            
            time_since = context.get('time_since_last', 8)
            completed_yesterday = context.get('completed_yesterday', 0)
            
            # Energy and focus
            if 5 <= hour <= 11:
                energy = 0.9
            elif 12 <= hour <= 14:
                energy = 0.6
            elif 15 <= hour <= 18:
                energy = 0.8
            else:
                energy = 0.5
            
            focus = 1.0 - (difficulty_score / 5) * (min(task_length, 50) / 50)
            interruptions = 0.2 if 9 <= hour <= 11 or 15 <= hour <= 17 else 0.5
            
            # Create feature vector
            features = np.array([[
                hour, day, month, is_weekend,
                priority_score, difficulty_score, task_length,
                similar_avg, time_since, completed_yesterday,
                energy, focus, interruptions
            ]])
            
            # Scale and predict
            features_scaled = self.scaler.transform(features)
            prediction = self.model.predict(features_scaled)[0]
            
            return max(0.5, min(1.5, float(prediction)))
        except Exception as e:
            print(f"Error predicting accuracy: {e}")
            return 1.0
    
    async def get_productivity_patterns(self) -> Dict[str, Any]:
        """Analyze user's productivity patterns"""
        patterns = {
            'peak_hours': [9, 15],
            'best_day': 'Tuesday',
            'avg_completion_rate': 75,
            'task_distribution': {'easy': 30, 'medium': 45, 'hard': 25},
            'accuracy_trend': [],
            'productivity_score': 78
        }
        
        if not self.db:
            return patterns
        
        try:
            # Get task history
            history = []
            cursor = self.db.task_history.find({"user_id": self.user_id}).sort("created_at", -1).limit(200)
            async for task in cursor:
                history.append(task)
            
            if not history:
                return patterns
            
            # Peak hours analysis
            hour_completion = {}
            for task in history:
                if task.get('completed'):
                    created_at = task.get('created_at', datetime.now().isoformat())
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            hour = created_at.hour
                            hour_completion[hour] = hour_completion.get(hour, 0) + 1
                        except:
                            pass
            
            if hour_completion:
                sorted_hours = sorted(hour_completion.items(), key=lambda x: x[1], reverse=True)
                patterns['peak_hours'] = [h for h, _ in sorted_hours[:3]]
            
            # Best day analysis
            day_completion = {}
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for task in history:
                if task.get('completed'):
                    created_at = task.get('created_at', datetime.now().isoformat())
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            day = created_at.weekday()
                            day_completion[day] = day_completion.get(day, 0) + 1
                        except:
                            pass
            
            if day_completion:
                best_day_num = max(day_completion, key=day_completion.get)
                patterns['best_day'] = days[best_day_num]
            
            # Completion rate
            completed = sum(1 for t in history if t.get('completed'))
            patterns['avg_completion_rate'] = (completed / len(history)) * 100 if history else 75
            
            # Task distribution
            for task in history:
                difficulty = task.get('difficulty', 'medium')
                patterns['task_distribution'][difficulty] = patterns['task_distribution'].get(difficulty, 0) + 1
            
            # Productivity score
            patterns['productivity_score'] = int(patterns['avg_completion_rate'] * 0.7 + 30)
            
        except Exception as e:
            print(f"Error analyzing patterns: {e}")
        
        return patterns