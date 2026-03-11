import sys
from pathlib import Path

# Make backend folder importable
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from auth import hash_password, verify_password
from security import generate_verification_token
from email_service import send_verification_email
from jwt_service import create_access_token
from core.dependencies import get_current_user
from fastapi.responses import RedirectResponse, JSONResponse

# Import AI Assistant
from ai_assistant import AIAssistant, get_ai_context

# Import WebSocket manager
from websocket import manager, websocket_endpoint

# Import ML services
from ml_service import TimevoraLearner
from analytics_service import AnalyticsService

import os
import uuid
import logging
import json
import traceback

# -------------------- SETUP LOGGING --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- LOAD ENV --------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# -------------------- MONGODB --------------------
import certifi

try:
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        logger.error("MONGO_URL environment variable not set!")
        raise ValueError("MONGO_URL not set")
    
    logger.info(f"Connecting to MongoDB...")
    
    client = AsyncIOMotorClient(
        mongo_url,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000
    )
    
    db = client[os.environ.get("DB_NAME", "timevora")]
    
    users = db.users
    tasks = db.tasks
    status_checks = db.status_checks
    task_history = db.task_history
    daily_plans = db.daily_plans
    
    logger.info("✅ MongoDB client created successfully")
    
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {str(e)}")
    logger.error(traceback.format_exc())

# -------------------- APP --------------------

app = FastAPI(title="Timevora API", description="Timevora Backend API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# -------------------- ROOT ENDPOINTS --------------------

@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {
        "message": "Timevora API is running",
        "status": "healthy",
        "version": "1.0.0",
        "endpoints": {
            "api_root": "/api/",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

@app.head("/")
async def root_head():
    """HEAD request handler for root endpoint - helps with Render health checks"""
    return JSONResponse(content={}, status_code=200)

@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    mongo_status = "connected" if 'client' in globals() and client is not None else "disconnected"
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mongodb": mongo_status
    }

@app.head("/health")
async def health_head():
    """HEAD request handler for health endpoint"""
    return JSONResponse(content={}, status_code=200)

# -------------------- MODELS --------------------

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class Task(BaseModel):
    text: str
    priority: str
    completed: bool = False

class SignupRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AIPlanningData(BaseModel):
    tasks: list
    totalLoad: float
    focusHours: float
    overloaded: bool
    energyDistribution: dict

class TaskAnalyzeInput(BaseModel):
    name: str
    priority: str
    difficulty: str
    time: float

class AnalyzeDayRequest(BaseModel):
    tasks: List[TaskAnalyzeInput]

class TaskFeedback(BaseModel):
    name: str
    difficulty: str
    priority: str
    aiTime: float
    actualTime: float

# AI Assistant Models
class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None

# Notification Model
class NotificationRequest(BaseModel):
    type: str
    title: str
    message: str
    icon: Optional[str] = None
    data: Optional[dict] = None

# -------------------- API ROUTES --------------------

@api_router.get("/")
async def api_root():
    """API root endpoint"""
    return {
        "message": "API running",
        "endpoints": [
            "/api/status",
            "/api/tasks",
            "/api/signup",
            "/api/login",
            "/api/ai-insight",
            "/api/analyze-day",
            "/api/task-feedback",
            "/api/daily-plans",
            "/api/accuracy",
            "/api/productivity-score",
            "/api/ai-assistant/chat",
            "/api/ml/patterns",
            "/api/analytics"
        ]
    }

@api_router.get("/status")
async def get_status():
    """Simple status check"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.model_dump())

    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()

    await status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status/all", response_model=List[StatusCheck])
async def get_status_checks():
    results = await status_checks.find({}, {"_id": 0}).to_list(1000)

    for r in results:
        r["timestamp"] = datetime.fromisoformat(r["timestamp"])

    return results

# -------------------- TASK ROUTES (PROTECTED) --------------------

@api_router.post("/tasks")
async def create_task(
    task: Task,
    current_user=Depends(get_current_user)
):
    task_data = task.model_dump()
    task_data["user_id"] = str(current_user["_id"])

    result = await tasks.insert_one(task_data)
    created_task = {
        "_id": str(result.inserted_id),
        **task_data
    }

    await manager.broadcast_to_user(str(current_user["_id"]), {
        "type": "task:created",
        "task": created_task,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return created_task

@api_router.get("/tasks")
async def get_tasks(current_user=Depends(get_current_user)):
    results = []

    async for task in tasks.find({"user_id": str(current_user["_id"])}):
        task["_id"] = str(task["_id"])
        results.append(task)

    return results

@api_router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    current_user=Depends(get_current_user)
):
    await tasks.delete_one({
        "_id": ObjectId(task_id),
        "user_id": str(current_user["_id"])
    })

    await manager.broadcast_to_user(str(current_user["_id"]), {
        "type": "task:deleted",
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"status": "deleted"}

@api_router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    data: dict,
    current_user=Depends(get_current_user)
):
    await tasks.update_one(
        {
            "_id": ObjectId(task_id),
            "user_id": str(current_user["_id"])
        },
        {"$set": data}
    )

    updated_task = await tasks.find_one({"_id": ObjectId(task_id)})
    updated_task["_id"] = str(updated_task["_id"])

    await manager.broadcast_to_user(str(current_user["_id"]), {
        "type": "task:updated",
        "task": updated_task,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    if data.get("completed"):
        streak = await calculate_streak(str(current_user["_id"]))
        if streak and streak % 5 == 0:
            await manager.broadcast_notification(str(current_user["_id"]), {
                "type": "achievement",
                "title": "🎯 Achievement Unlocked!",
                "message": f"🔥 {streak} day streak! You're on fire!",
                "icon": "🏆"
            })

    return {"status": "updated"}

async def calculate_streak(user_id: str) -> int:
    user_tasks = []
    async for task in tasks.find({"user_id": user_id, "completed": True}).sort("created_at", -1).limit(10):
        user_tasks.append(task)
    return len(user_tasks)

# -------------------- AI INSIGHT ROUTE --------------------

@api_router.post("/ai-insight")
async def ai_insight(
    planning: AIPlanningData,
    current_user=Depends(get_current_user)
):
    accuracy = await get_user_accuracy(str(current_user["_id"]))
    print("USER ACCURACY:", accuracy)

    ai_message = timevora_ai(planning.model_dump())

    return {"message": ai_message}

# -------------------- ANALYZE DAY ROUTE --------------------

@api_router.post("/analyze-day")
async def analyze_day(
    data: AnalyzeDayRequest,
    current_user=Depends(get_current_user)
):

    difficulty_factor = {
        "easy": 1.1,
        "medium": 1.35,
        "hard": 1.9,
    }

    priority_factor = {
        "low": 1,
        "medium": 1.3,
        "high": 1.7,
    }

    accuracy = await get_user_accuracy(str(current_user["_id"]))

    enriched = []

    for t in data.tasks:
        base_time = t.time * difficulty_factor[t.difficulty]
        adjustment = accuracy.get(t.difficulty, 1)
        ai_time = round(base_time * adjustment, 1)

        score = (
            difficulty_factor[t.difficulty]
            * priority_factor[t.priority]
            * t.time
        )

        enriched.append({
            "id": str(uuid.uuid4()),
            "name": t.name,
            "priority": t.priority,
            "difficulty": t.difficulty,
            "userTime": t.time,
            "aiTime": ai_time,
            "score": score
        })

    ordered = sorted(enriched, key=lambda x: x["score"], reverse=True)

    hour = 9
    schedule = []

    for task in ordered:
        remaining = int(round(task["aiTime"]))
        while remaining > 0:
            schedule.append({
                "time": f"{hour}:00 - {hour+1}:00",
                "task": task["name"]
            })
            hour += 1
            remaining -= 1

    from datetime import date
    today = date.today().isoformat()

    await daily_plans.update_one(
        {
            "user_id": str(current_user["_id"]),
            "date": today
        },
        {
            "$set": {
                "optimizedTasks": ordered,
                "schedule": schedule,
                "created_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

    await manager.broadcast_to_user(str(current_user["_id"]), {
        "type": "schedule:ready",
        "date": today,
        "task_count": len(ordered),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {
        "optimizedTasks": ordered,
        "schedule": schedule
    }

# -------------------- TASK FEEDBACK ROUTE --------------------

@api_router.post("/task-feedback")
async def task_feedback(
    feedback: TaskFeedback,
    current_user=Depends(get_current_user)
):
    print("TASK FEEDBACK ROUTE CALLED")

    await task_history.insert_one({
        "user_id": str(current_user["_id"]),
        "name": feedback.name,
        "difficulty": feedback.difficulty,
        "priority": feedback.priority,
        "aiTime": feedback.aiTime,
        "actualTime": feedback.actualTime,
        "created_at": datetime.now(timezone.utc)
    })

    return {"status": "saved"}

# -------------------- DAILY PLANS ROUTES --------------------

@api_router.get("/daily-plans")
async def get_daily_plans(current_user=Depends(get_current_user)):
    plans = []

    async for p in daily_plans.find(
        {"user_id": str(current_user["_id"])}
    ).sort("created_at", -1):

        p["_id"] = str(p["_id"])
        plans.append(p)

    return plans

@api_router.delete("/daily-plans/{plan_id}")
async def delete_plan(plan_id: str, current_user=Depends(get_current_user)):
    await daily_plans.delete_one({
        "_id": ObjectId(plan_id),
        "user_id": str(current_user["_id"])
    })

    return {"status": "deleted"}

# -------------------- ACCURACY ROUTE --------------------

@api_router.get("/accuracy")
async def get_accuracy(current_user=Depends(get_current_user)):
    accuracy = await get_user_accuracy(str(current_user["_id"]))
    return accuracy

# -------------------- PRODUCTIVITY SCORE ROUTE --------------------

@api_router.get("/productivity-score")
async def get_productivity_score(current_user=Depends(get_current_user)):
    user_id = str(current_user["_id"])

    plans = []
    async for p in daily_plans.find({"user_id": user_id}):
        plans.append(p)

    if not plans:
        return {
            "score": 0,
            "completion_rate": 0,
            "focus_hours": 0
        }

    total_tasks = 0
    total_ai_time = 0

    for plan in plans:
        tasks = plan.get("optimizedTasks", [])
        total_tasks += len(tasks)

        for t in tasks:
            total_ai_time += t.get("aiTime", 0)

    focus_hours = total_ai_time
    completion_rate = 1
    focus_ratio = min(focus_hours / 8, 1)

    score = int(
        completion_rate * 50 +
        focus_ratio * 50
    )

    return {
        "score": score,
        "completion_rate": completion_rate,
        "focus_hours": round(focus_hours, 1)
    }

# ⚠️ TEMPORARY TEST ENDPOINT
@api_router.post("/test-task")
async def create_test_task(task: Task):
    task_data = task.model_dump()
    task_data["_id"] = str(uuid.uuid4())
    task_data["created_at"] = datetime.now().isoformat()
    print(f"✅ Test task created: {task_data}")
    return task_data

# -------------------- AUTH ROUTES --------------------

@api_router.post("/signup")
async def signup(user: SignupRequest):
    logger.info(f"Signup attempt for email: {user.email}")
    
    if await users.find_one({"email": user.email}):
        logger.warning(f"Email already registered: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")

    token = generate_verification_token()

    new_user = {
        "email": user.email,
        "hashed_password": hash_password(user.password),
        "is_verified": False,
        "verification_token": token,
        "created_at": datetime.now(timezone.utc)
    }

    await users.insert_one(new_user)
    logger.info(f"User created: {user.email}")

    send_verification_email(user.email, token)

    return {"message": "Signup successful. Please verify your email."}

@api_router.post("/login")
async def login(user: LoginRequest):
    logger.info(f"Login attempt for email: {user.email}")
    
    db_user = await users.find_one({"email": user.email})

    if not db_user:
        logger.warning(f"User not found: {user.email}")
        raise HTTPException(status_code=400, detail="Invalid credentials")

    if not db_user["is_verified"]:
        logger.warning(f"Email not verified: {user.email}")
        raise HTTPException(status_code=403, detail="Email not verified")

    if not verify_password(user.password, db_user["hashed_password"]):
        logger.warning(f"Invalid password for: {user.email}")
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = create_access_token({
        "user_id": str(db_user["_id"]),
        "email": db_user["email"]
    })

    logger.info(f"Login successful: {user.email}")
    return {
        "access_token": token,
        "token_type": "bearer"
    }

@api_router.get("/verify")
async def verify_email(token: str):
    user = await users.find_one({"verification_token": token})

    if not user:
        raise HTTPException(status_code=400, detail="Token not found")

    await users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True, "verification_token": None}}
    )

    return RedirectResponse(url="http://localhost:3000/login")

# ==================== AI ASSISTANT ROUTES ====================

@api_router.post("/ai-assistant/chat")
async def chat_with_ai(
    request: ChatMessage,
    current_user=Depends(get_current_user)
):
    try:
        logger.info(f"Received message from user {current_user['_id']}: {request.message}")
        
        assistant = AIAssistant(str(current_user["_id"]), db)
        response = await assistant.process_message(request.message)
        
        logger.info(f"AI response: {response}")
        return response
        
    except Exception as e:
        logger.error(f"AI Assistant error: {str(e)}")
        traceback.print_exc()
        
        return {
            "type": "error",
            "message": "I'm having trouble right now. Please try again.",
            "error_details": str(e)
        }

@api_router.get("/ai-assistant/context")
async def get_ai_context_endpoint(
    current_user=Depends(get_current_user)
):
    try:
        context = await get_ai_context(str(current_user["_id"]), db)
        return context
    except Exception as e:
        logger.error(f"Context error: {e}")
        return {
            "suggestions": [
                "Plan my day: I need to study for 2 hours, go to the gym, and finish a project",
                "Give me productivity advice",
                "How can I improve my focus?",
                "Analyze my productivity habits"
            ],
            "has_history": False,
            "quick_actions": ["Create Schedule", "Get Advice", "Analyze Habits"]
        }

# ==================== WEBSOCKET ROUTES ====================

@api_router.websocket("/ws/{user_id}")
async def websocket_route(websocket: WebSocket, user_id: str):
    await websocket_endpoint(websocket, user_id)

@api_router.post("/notify/{user_id}")
async def send_notification(
    user_id: str, 
    notification: NotificationRequest,
    current_user=Depends(get_current_user)
):
    await manager.broadcast_notification(user_id, notification.dict())
    return {"status": "notification sent"}

@api_router.get("/online-users")
async def get_online_users(current_user=Depends(get_current_user)):
    return {"online_count": len(manager.active_connections)}

# ==================== ML ROUTES ====================

@api_router.get("/ml/patterns")
async def get_productivity_patterns(current_user=Depends(get_current_user)):
    learner = TimevoraLearner(str(current_user["_id"]), db)
    patterns = await learner.get_productivity_patterns()
    return patterns

@api_router.post("/ml/predict")
async def predict_task_duration(
    task: dict,
    current_user=Depends(get_current_user)
):
    learner = TimevoraLearner(str(current_user["_id"]), db)
    context = {
        'hour': datetime.now().hour,
        'day': datetime.now().weekday(),
        'month': datetime.now().month,
        'time_since_last': 8,
        'completed_yesterday': 1
    }
    accuracy = await learner.predict_accuracy(task, context)
    return {"predicted_accuracy": accuracy}

@api_router.get("/analytics")
async def get_analytics(
    days: int = 30,
    current_user=Depends(get_current_user)
):
    analytics_service = AnalyticsService(db)
    analytics = await analytics_service.get_user_analytics(str(current_user["_id"]), days)
    return analytics

@api_router.post("/ml/train")
async def train_model(current_user=Depends(get_current_user)):
    learner = TimevoraLearner(str(current_user["_id"]), db)
    success = await learner.train_model()
    return {"success": success}

# ==================== TIMEVORA AI BRAIN ====================

def timevora_ai(planning_data: dict) -> str:
    total = planning_data["totalLoad"]
    overloaded = planning_data["overloaded"]

    hard_tasks = [
        t["name"] for t in planning_data["tasks"]
        if t["difficulty"] == "hard"
    ]

    response = []

    if overloaded:
        response.append(
            "Your workload is too heavy for one day. I recommend moving some tasks to tomorrow to avoid burnout."
        )

    if hard_tasks:
        response.append(
            f"Focus on hard tasks like {', '.join(hard_tasks[:2])} in the morning when your energy is highest."
        )

    if total < 3:
        response.append("You can handle more today if you feel productive.")

    return " ".join(response) or "Your schedule looks balanced and realistic. Great job planning today!"

async def get_user_accuracy(user_id: str):
    records = []

    async for r in task_history.find({"user_id": user_id}):
        records.append(r)

    if not records:
        return {"easy": 1, "medium": 1, "hard": 1}

    stats = {"easy": [], "medium": [], "hard": []}

    for r in records:
        ratio = r["actualTime"] / r["aiTime"]
        stats[r["difficulty"]].append(ratio)

    return {
        k: round(sum(v) / len(v), 2) if v else 1
        for k, v in stats.items()
    }

# ==================== APP SETUP ====================

# Include router FIRST
app.include_router(api_router)

# ✅ CORS CONFIGURATION - UPDATED (only this, no manual middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://timevorai.netlify.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# -------------------- RUN --------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
