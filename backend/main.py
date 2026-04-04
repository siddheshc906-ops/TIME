# backend/main.py

import sys
import os
import uuid
import logging
import json
import traceback
import asyncio
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, Request
from fastapi.responses import RedirectResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId
import certifi

from auth import hash_password, verify_password, verify_google_token
from jwt_service import create_access_token
from otp_service import generate_otp, send_otp_msg91, otp_expiry
from core.dependencies import get_current_user, set_db

from ai_assistant import AIAssistant, get_ai_context, get_guidance_response
from ai.core import TimevoraAI
from ai.scheduler import IntelligentScheduler
from ai.analyzer import ProductivityAnalyzer
from ai.learner import AdaptiveLearner
from ai.recommender import TaskRecommender

from websocket import manager, websocket_endpoint
from ml_service import TimevoraLearner
from analytics_service import AnalyticsService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

try:
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        raise ValueError("MONGO_URL not set")

    logger.info("Connecting to MongoDB…")
    client = AsyncIOMotorClient(
        mongo_url,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
    )
    db = client[os.environ.get("DB_NAME", "timevora")]

    users             = db.users
    tasks_col         = db.tasks
    status_checks     = db.status_checks
    task_history      = db.task_history
    daily_plans       = db.daily_plans
    user_preferences  = db.user_preferences
    priority_feedback = db.priority_feedback
    dismissed_tasks   = db.dismissed_tasks

    logger.info("✅ MongoDB client created")
    set_db(db)  # give dependencies.py access to the DB

except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    logger.error(traceback.format_exc())

app = FastAPI(title="Timevora API", description="Timevora Backend API", version="2.0.0")

# ── Rate Limiter setup ──────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://timevorai.netlify.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

api_router = APIRouter(prefix="/api")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  PYDANTIC MODELS
# ╚══════════════════════════════════════════════════════════════════════════════

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
    difficulty: Optional[str] = "medium"
    estimated_time: Optional[float] = 1.0
    deadline: Optional[datetime] = None

class SignupRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    token: str

class OtpSendRequest(BaseModel):
    phone: str          # 10-digit Indian number e.g. "9876543210"

class OtpVerifyRequest(BaseModel):
    phone: str
    otp: str

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
    category: Optional[str] = "general"
    task_id: Optional[str] = None
    notes: Optional[str] = None

class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class AdvancedPlanRequest(BaseModel):
    tasks: List[dict]
    preferences: Optional[dict] = {}
    date: Optional[str] = None

class TaskPredictionRequest(BaseModel):
    task: dict
    context: Optional[dict] = {}

class NotificationRequest(BaseModel):
    type: str
    title: str
    message: str
    icon: Optional[str] = None
    data: Optional[dict] = None

class PriorityChangeRequest(BaseModel):
    task_name: str
    old_priority: str
    new_priority: str

class TaskCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    duration: int = 60
    priority: str = "medium"
    difficulty: str = "medium"
    category: str = "work"
    scheduled_time: Optional[datetime] = None

class TaskUpdateRequest(BaseModel):
    text: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    difficulty: Optional[str] = None
    estimated_time: Optional[float] = None
    scheduled_time: Optional[datetime] = None

class BulkTaskCreate(BaseModel):
    tasks: List[TaskCreateRequest]

class ProductivityInsightsResponse(BaseModel):
    has_sufficient_data: bool
    total_tasks: int
    accuracy_insights: dict
    chronotype: Optional[dict] = None
    message: Optional[str] = None

class ScheduleRequest(BaseModel):
    tasks: Optional[List[dict]] = None
    message: Optional[str] = None
    date: Optional[str] = None

class DismissTaskRequest(BaseModel):
    task_id: str
    reason: Optional[str] = "dismissed"

# ── NEW models for schedule update/delete ──
class UpdateScheduleRequest(BaseModel):
    date: Optional[str] = None
    schedule: List[dict] = []

class DeletePlanByDateRequest(BaseModel):
    date: Optional[str] = None


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ROOT / HEALTH
# ╚══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {"message": "Timevora API is running", "status": "healthy", "version": "2.0.0"}

@app.head("/")
async def root_head():
    return JSONResponse(content={}, status_code=200)

@app.get("/health")
async def health_check():
    mongo_status = "connected" if "client" in globals() and client else "disconnected"
    from ai.core import USE_GEMINI
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mongodb": mongo_status,
        "ai": {"gemini": USE_GEMINI, "any_available": USE_GEMINI},
    }

@app.head("/health")
async def health_head():
    return JSONResponse(content={}, status_code=200)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  STATUS
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/test-cors")
async def test_cors():
    return {"message": "CORS is working", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.get("/")
async def api_root():
    return {"message": "Timevora API v2 — all systems operational"}

@api_router.get("/status")
async def get_status():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    obj = StatusCheck(**input.model_dump())
    doc = obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await status_checks.insert_one(doc)
    return obj

@api_router.get("/status/all", response_model=List[StatusCheck])
async def get_status_checks():
    results = await status_checks.find({}, {"_id": 0}).to_list(1000)
    for r in results:
        r["timestamp"] = datetime.fromisoformat(r["timestamp"])
    return results


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  AUTH
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/signup")
@limiter.limit("5/minute")  # max 5 signup attempts per minute per IP
async def signup(request: Request, user: SignupRequest):
    if await users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    await users.insert_one({
        "email": user.email,
        "hashed_password": hash_password(user.password),
        "is_verified": True,
        "created_at": datetime.now(timezone.utc),
    })
    return {"message": "Signup successful! You can now log in."}

@api_router.post("/login")
@limiter.limit("5/minute")  # max 5 login attempts per minute per IP — prevents brute force
async def login(request: Request, user: LoginRequest):
    db_user = await users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token({"sub": db_user["email"], "user_id": str(db_user["_id"]), "email": db_user["email"]})
    return {"access_token": token, "token_type": "bearer"}

@api_router.get("/verify")
async def verify_email(token: str):
    user = await users.find_one({"verification_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Token not found")
    await users.update_one({"_id": user["_id"]}, {"$set": {"is_verified": True, "verification_token": None}})
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/login")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  GOOGLE AUTH
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/auth/google")
@limiter.limit("10/minute")  # google auth is less risky but still limit it
async def google_auth(request: Request, req: GoogleAuthRequest):
    try:
        gdata = verify_google_token(req.token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email      = gdata["email"]
    google_sub = gdata["sub"]
    name       = gdata.get("name", "")
    picture    = gdata.get("picture", "")

    user = await users.find_one({"email": email})

    if not user:
        new_user = {
            "email":       email,
            "name":        name,
            "picture":     picture,
            "google_sub":  google_sub,
            "auth_method": "google",
            "verified":    True,
            "created_at":  datetime.now(timezone.utc),
        }
        await users.insert_one(new_user)
    else:
        if not user.get("google_sub"):
            await users.update_one(
                {"email": email},
                {"$set": {"google_sub": google_sub, "picture": picture}}
            )

    # Fetch user _id for consistent token
    db_google_user = await users.find_one({"email": email})
    google_user_id = str(db_google_user["_id"]) if db_google_user else email
    token = create_access_token({"sub": email, "user_id": google_user_id, "email": email})
    return {"access_token": token, "token_type": "bearer"}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  PHONE OTP AUTH
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/otp/send")
@limiter.limit("3/minute")  # OTP sends cost money (MSG91) — strictly limit to 3/min per IP
async def otp_send(request: Request, req: OtpSendRequest):
    phone = req.phone.strip()
    if len(phone) != 10 or not phone.isdigit():
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit phone number")

    otp        = generate_otp()
    expiry     = otp_expiry()
    intl_phone = "91" + phone

    await db.otp_store.update_one(
        {"phone": phone},
        {"$set": {"otp": otp, "expires_at": expiry}},
        upsert=True
    )

    sent = await send_otp_msg91(intl_phone, otp)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send OTP. Try again.")

    return {"message": f"OTP sent to +91 {phone}"}


@api_router.post("/otp/verify")
@limiter.limit("5/minute")  # max 5 OTP verify attempts per minute per IP
async def otp_verify(request: Request, req: OtpVerifyRequest):
    phone  = req.phone.strip()
    record = await db.otp_store.find_one({"phone": phone})

    if not record:
        raise HTTPException(status_code=400, detail="OTP not found. Please request a new one.")

    if datetime.now(timezone.utc) > record["expires_at"].replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

    if record["otp"] != req.otp:
        raise HTTPException(status_code=400, detail="Incorrect OTP")

    await db.otp_store.delete_one({"phone": phone})

    phone_email = f"{phone}@phone.timevora"
    user = await users.find_one({"phone": phone})

    if not user:
        await users.insert_one({
            "phone":       phone,
            "email":       phone_email,
            "auth_method": "phone",
            "verified":    True,
            "created_at":  datetime.now(timezone.utc),
        })

    phone_user = await users.find_one({"phone": phone})
    phone_user_id = str(phone_user["_id"]) if phone_user else phone_email
    token = create_access_token({"sub": phone_email, "user_id": phone_user_id, "email": phone_email})
    return {"access_token": token, "token_type": "bearer"}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TASKS
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/tasks")
async def create_task(task: Task, current_user=Depends(get_current_user)):
    data = task.model_dump()
    data["user_id"]    = str(current_user["_id"])
    data["created_at"] = datetime.now(timezone.utc)
    data["status"]     = "active"
    data["is_deleted"] = False
    result  = await tasks_col.insert_one(data)
    created = {"_id": str(result.inserted_id), **data}
    await manager.broadcast_to_user(str(current_user["_id"]), {"type": "task:created", "task": created, "timestamp": datetime.now(timezone.utc).isoformat()})
    return created

@api_router.post("/tasks/enhanced")
async def create_task_enhanced(task: TaskCreateRequest, current_user=Depends(get_current_user)):
    data = task.model_dump()
    data["user_id"]    = str(current_user["_id"])
    data["created_at"] = datetime.now(timezone.utc)
    data["completed"]  = False
    data["text"]       = data.pop("name")
    data["status"]     = "active"
    data["is_deleted"] = False
    result  = await tasks_col.insert_one(data)
    created = {"_id": str(result.inserted_id), **data}
    await manager.broadcast_to_user(str(current_user["_id"]), {"type": "task:created", "task": created, "timestamp": datetime.now(timezone.utc).isoformat()})
    return created

@api_router.get("/tasks")
async def get_tasks(current_user=Depends(get_current_user)):
    """Returns a plain array so frontend setTasks(data) works directly."""
    results = []
    async for t in tasks_col.find(
        {"user_id": str(current_user["_id"]), "is_deleted": {"$ne": True}}
    ).sort("created_at", -1):
        t["_id"] = str(t["_id"])
        results.append(t)
    return results  # plain array, NOT {"tasks": results}

@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, current_user=Depends(get_current_user)):
    user_id = str(current_user["_id"])
    try:
        obj_id = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    delete_result = await tasks_col.delete_one({"_id": obj_id, "user_id": user_id})
    await daily_plans.update_many({"user_id": user_id}, {"$pull": {"schedule": {"task_id": task_id}, "optimizedTasks": {"id": task_id}, "pending_tasks": {"task_id": task_id}}})
    await dismissed_tasks.update_one({"user_id": user_id, "task_id": task_id}, {"$set": {"user_id": user_id, "task_id": task_id, "dismissed_at": datetime.now(timezone.utc), "reason": "deleted"}}, upsert=True)
    await task_history.update_many({"user_id": user_id, "task_id": task_id}, {"$set": {"task_deleted": True}})
    await manager.broadcast_to_user(user_id, {"type": "task:deleted", "task_id": task_id, "timestamp": datetime.now(timezone.utc).isoformat()})
    logger.info(f"🗑️ Task {task_id} deleted for user {user_id} (found: {delete_result.deleted_count})")
    return {"status": "deleted", "task_id": task_id, "cleaned_plans": True}

@api_router.put("/tasks/{task_id}")
async def update_task(task_id: str, data: dict, current_user=Depends(get_current_user)):
    await tasks_col.update_one({"_id": ObjectId(task_id), "user_id": str(current_user["_id"])}, {"$set": data})
    updated = await tasks_col.find_one({"_id": ObjectId(task_id)})
    updated["_id"] = str(updated["_id"])
    await manager.broadcast_to_user(str(current_user["_id"]), {"type": "task:updated", "task": updated, "timestamp": datetime.now(timezone.utc).isoformat()})
    if data.get("completed"):
        streak = await _count_completed_tasks(str(current_user["_id"]))
        if streak and streak % 5 == 0:
            await manager.broadcast_notification(str(current_user["_id"]), {"type": "achievement", "title": "🎯 Achievement Unlocked!", "message": f"🔥 {streak} tasks completed! You're on fire!", "icon": "🏆"})
    return {"status": "updated"}

@api_router.patch("/tasks/{task_id}/complete")
async def mark_task_complete(task_id: str, current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        task = await tasks_col.find_one({"_id": ObjectId(task_id), "user_id": user_id})
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        result = await tasks_col.update_one({"_id": ObjectId(task_id), "user_id": user_id}, {"$set": {"completed": True, "status": "completed", "completed_at": datetime.now(timezone.utc)}})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        await daily_plans.update_many({"user_id": user_id}, {"$pull": {"pending_tasks": {"task_id": task_id}}})
        return {"success": True, "message": "Task marked as completed", "task": {"id": task_id, "name": task.get("text", ""), "priority": task.get("priority", "medium"), "difficulty": task.get("difficulty", "medium")}}
    except Exception as e:
        logger.error(f"Error marking task complete: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _count_completed_tasks(user_id: str) -> int:
    return await tasks_col.count_documents({"user_id": user_id, "completed": True})


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  PENDING TASKS
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/pending-tasks")
async def get_pending_tasks(current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        dismissed_ids = set()
        async for d in dismissed_tasks.find({"user_id": user_id}, {"task_id": 1}):
            dismissed_ids.add(d["task_id"])

        pending = []
        async for task in tasks_col.find({"user_id": user_id, "completed": {"$ne": True}, "is_deleted": {"$ne": True}, "status": {"$nin": ["completed", "deleted", "dismissed"]}}).sort("created_at", -1):
            task_id_str = str(task["_id"])
            if task_id_str in dismissed_ids:
                continue
            pending.append({"id": task_id_str, "name": task.get("text", ""), "priority": task.get("priority", "medium"), "difficulty": task.get("difficulty", "medium"), "estimated_time": task.get("estimated_time", 1.0), "category": task.get("category", "general"), "created_at": task.get("created_at", datetime.now(timezone.utc)).isoformat()})

        return {"success": True, "tasks": pending, "count": len(pending)}
    except Exception as e:
        logger.error(f"Error fetching pending tasks: {e}")
        return {"success": False, "error": str(e), "tasks": [], "count": 0}

@api_router.post("/pending-tasks/{task_id}/dismiss")
async def dismiss_pending_task(task_id: str, current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        await dismissed_tasks.update_one({"user_id": user_id, "task_id": task_id}, {"$set": {"user_id": user_id, "task_id": task_id, "dismissed_at": datetime.now(timezone.utc), "reason": "dismissed_from_pending"}}, upsert=True)
        await tasks_col.update_one({"_id": ObjectId(task_id), "user_id": user_id}, {"$set": {"status": "dismissed", "dismissed_at": datetime.now(timezone.utc)}})
        return {"success": True, "message": "Task dismissed", "task_id": task_id}
    except Exception as e:
        logger.error(f"Error dismissing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/pending-tasks/{task_id}")
async def delete_pending_task(task_id: str, current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        await tasks_col.delete_one({"_id": ObjectId(task_id), "user_id": user_id})
        await dismissed_tasks.update_one({"user_id": user_id, "task_id": task_id}, {"$set": {"user_id": user_id, "task_id": task_id, "dismissed_at": datetime.now(timezone.utc), "reason": "permanently_deleted"}}, upsert=True)
        await daily_plans.update_many({"user_id": user_id}, {"$pull": {"schedule": {"task_id": task_id}, "optimizedTasks": {"id": task_id}, "pending_tasks": {"task_id": task_id}}})
        await manager.broadcast_to_user(user_id, {"type": "task:deleted", "task_id": task_id, "timestamp": datetime.now(timezone.utc).isoformat()})
        return {"success": True, "message": "Task permanently deleted", "task_id": task_id}
    except Exception as e:
        logger.error(f"Error deleting pending task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/pending-tasks/dismiss-all")
async def dismiss_all_pending_tasks(current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        pending_ids = []
        async for task in tasks_col.find({"user_id": user_id, "completed": {"$ne": True}, "is_deleted": {"$ne": True}}, {"_id": 1}):
            pending_ids.append(str(task["_id"]))
        if pending_ids:
            for tid in pending_ids:
                await dismissed_tasks.update_one({"user_id": user_id, "task_id": tid}, {"$set": {"user_id": user_id, "task_id": tid, "dismissed_at": datetime.now(timezone.utc), "reason": "bulk_dismiss"}}, upsert=True)
            await tasks_col.update_many({"user_id": user_id, "completed": {"$ne": True}}, {"$set": {"status": "dismissed", "dismissed_at": datetime.now(timezone.utc)}})
        return {"success": True, "message": f"Dismissed {len(pending_ids)} pending tasks", "dismissed_count": len(pending_ids)}
    except Exception as e:
        logger.error(f"Error dismissing all tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/pending-tasks/restore/{task_id}")
async def restore_dismissed_task(task_id: str, current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        await dismissed_tasks.delete_one({"user_id": user_id, "task_id": task_id})
        await tasks_col.update_one({"_id": ObjectId(task_id), "user_id": user_id}, {"$set": {"status": "active"}, "$unset": {"dismissed_at": ""}})
        return {"success": True, "message": "Task restored", "task_id": task_id}
    except Exception as e:
        logger.error(f"Error restoring task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TASK FEEDBACK
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/task-feedback")
async def task_feedback_endpoint(feedback: TaskFeedback, current_user=Depends(get_current_user)):
    user_id = str(current_user["_id"])
    if feedback.aiTime <= 0 or feedback.actualTime <= 0:
        raise HTTPException(status_code=400, detail="aiTime and actualTime must be > 0")

    accuracy_ratio = round(feedback.aiTime / feedback.actualTime, 3)
    now = datetime.now(timezone.utc)

    feedback_doc = {"user_id": user_id, "name": feedback.name, "difficulty": feedback.difficulty, "priority": feedback.priority, "category": feedback.category or "general", "aiTime": feedback.aiTime, "actualTime": feedback.actualTime, "accuracy_ratio": accuracy_ratio, "hour_of_day": now.hour, "day_of_week": now.strftime("%A"), "created_at": now}
    if feedback.task_id:
        feedback_doc["task_id"] = feedback.task_id
    if feedback.notes:
        feedback_doc["notes"] = feedback.notes

    result = await task_history.insert_one(feedback_doc)

    if feedback.task_id:
        try:
            await tasks_col.update_one({"_id": ObjectId(feedback.task_id), "user_id": user_id}, {"$set": {"completed": True, "status": "completed", "actualTime": feedback.actualTime, "completed_at": now}})
            await dismissed_tasks.update_one({"user_id": user_id, "task_id": feedback.task_id}, {"$set": {"user_id": user_id, "task_id": feedback.task_id, "dismissed_at": now, "reason": "completed_with_feedback"}}, upsert=True)
        except Exception as e:
            logger.warning(f"Could not update original task: {e}")

    count = await task_history.count_documents({"user_id": user_id})
    retrain_triggered = False
    if count >= 10 and count % 10 == 0:
        asyncio.create_task(_background_train_model(user_id))
        retrain_triggered = True

    await _update_user_streak(user_id)
    insight = _generate_quick_insight(accuracy_ratio, feedback.name)

    return {"status": "saved", "feedback_id": str(result.inserted_id), "total_records": count, "accuracy_ratio": accuracy_ratio, "retrain_triggered": retrain_triggered, "insight": insight, "message": f"Feedback saved! {count} total tasks tracked."}


def _generate_quick_insight(accuracy_ratio: float, task_name: str) -> str:
    if accuracy_ratio > 1.3:
        return f"You finished '{task_name}' {round((accuracy_ratio - 1) * 100)}% faster than estimated! 🚀"
    elif accuracy_ratio < 0.7:
        return f"'{task_name}' took {round((1 - accuracy_ratio) * 100)}% longer than expected. I'll adjust future estimates. ⏰"
    elif accuracy_ratio < 0.85:
        return f"'{task_name}' took a bit longer than estimated. Noted for future scheduling. 📝"
    else:
        return f"Great estimate for '{task_name}'! Your predictions are getting accurate. ✨"

async def _background_train_model(user_id: str):
    try:
        learner = AdaptiveLearner(user_id, db)
        success = await learner.train_model()
        if success:
            await user_preferences.update_one({"user_id": user_id}, {"$set": {"last_trained": datetime.now(timezone.utc), "last_trained_count": await task_history.count_documents({"user_id": user_id})}}, upsert=True)
    except Exception as e:
        logger.error(f"❌ Background retrain error for {user_id}: {e}")

async def _update_user_streak(user_id: str):
    try:
        streak = await calculate_user_streak(user_id)
        await user_preferences.update_one({"user_id": user_id}, {"$set": {"streak": streak, "last_updated": datetime.now(timezone.utc)}}, upsert=True)
    except Exception as e:
        logger.error(f"Error updating streak: {e}")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TASK FEEDBACK HISTORY
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/task-feedback")
async def get_feedback_history(current_user=Depends(get_current_user)):
    user_id = str(current_user["_id"])
    history = []
    async for record in task_history.find({"user_id": user_id}).sort("created_at", -1).limit(100):
        record["_id"] = str(record["_id"])
        history.append(record)
    total = len(history)
    avg_accuracy   = sum(r.get("accuracy_ratio", 1.0) for r in history) / total if total else 0
    overestimates  = sum(1 for r in history if r.get("accuracy_ratio", 1.0) > 1.2)
    underestimates = sum(1 for r in history if r.get("accuracy_ratio", 1.0) < 0.8)
    return {"history": history, "summary": {"total_feedbacks": total, "avg_accuracy": round(avg_accuracy, 3), "overestimates": overestimates, "underestimates": underestimates, "model_ready": total >= 10}}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TASK PRIORITY
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/task-priority")
async def update_task_priority(request: PriorityChangeRequest, current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        await priority_feedback.insert_one({"user_id": user_id, "task_name": request.task_name, "old_priority": request.old_priority, "new_priority": request.new_priority, "created_at": datetime.now(timezone.utc)})
        return {"success": True, "message": f"Priority updated to {request.new_priority}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  AI PRODUCTIVITY PROFILE
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/ai/productivity-profile")
async def get_productivity_profile(current_user=Depends(get_current_user)):
    try:
        user_id      = str(current_user["_id"])
        ai           = TimevoraAI(user_id, db)
        full_profile = await ai.get_productivity_profile()
        accuracy     = await get_user_accuracy(user_id)

        accuracy_insights = {}
        for difficulty, ratio in accuracy.items():
            if ratio > 1.2:
                accuracy_insights[difficulty] = f"Takes {int((ratio - 1) * 100)}% longer than estimated"
            elif ratio < 0.8:
                accuracy_insights[difficulty] = f"Completes {int((1 - ratio) * 100)}% faster than estimated"

        legacy_chronotype   = await detect_chronotype(user_id)
        total_tasks         = await task_history.count_documents({"user_id": user_id})
        has_sufficient_data = total_tasks >= 5

        return {"success": True, "ready": full_profile.get("ready", has_sufficient_data), "feedbacks_given": full_profile.get("feedbacks_given", total_tasks), "feedbacks_needed": 5 if not has_sufficient_data else 0, "overall_accuracy": full_profile.get("overall_accuracy", 0), "accuracy_trend": full_profile.get("accuracy_trend", "insufficient_data"), "category_accuracy": full_profile.get("category_accuracy", {}), "difficulty_accuracy": full_profile.get("difficulty_accuracy", accuracy), "energy_patterns": full_profile.get("energy_patterns", {}), "insights": full_profile.get("insights", []), "streak": full_profile.get("streak", 0), "productivity_score": full_profile.get("productivity_score", 0), "message": full_profile.get("message", ""), "chronotype": full_profile.get("chronotype") or legacy_chronotype, "profile": full_profile, "has_sufficient_data": has_sufficient_data, "total_tasks": total_tasks, "accuracy_insights": accuracy_insights}

    except Exception as e:
        logger.error(f"Productivity profile error: {e}", exc_info=True)
        try:
            user_id     = str(current_user["_id"])
            total_tasks = await task_history.count_documents({"user_id": user_id})
            return {"success": False, "ready": total_tasks >= 5, "feedbacks_given": total_tasks, "feedbacks_needed": max(0, 5 - total_tasks), "total_tasks": total_tasks, "accuracy_insights": {}, "chronotype": await detect_chronotype(user_id), "insights": [], "message": f"Complete {max(0, 5 - total_tasks)} more tasks to unlock insights!" if total_tasks < 5 else "", "error": str(e)}
        except Exception:
            return {"success": False, "error": str(e)}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  AI CHRONOTYPE
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/ai/chronotype")
async def get_chronotype_endpoint(current_user=Depends(get_current_user)):
    try:
        user_id     = str(current_user["_id"])
        ai          = TimevoraAI(user_id, db)
        chrono_data = await ai.get_chronotype_data()
        if chrono_data and chrono_data.get("ready"):
            return {"success": True, **chrono_data}
        legacy_chrono = await detect_chronotype(user_id)
        total_tasks   = await task_history.count_documents({"user_id": user_id})
        if legacy_chrono:
            return {"success": True, "ready": True, **legacy_chrono, "total_tasks_analyzed": total_tasks}
        return {"success": True, "ready": False, "tasks_completed": total_tasks, "tasks_needed": max(0, 14 - total_tasks), "message": f"Complete {max(0, 14 - total_tasks)} more tasks to discover your chronotype!"}
    except Exception as e:
        logger.error(f"Chronotype endpoint error: {e}", exc_info=True)
        return {"success": False, "ready": False, "error": str(e)}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  AI LEARNING INSIGHTS
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/ai/insights")
async def get_ai_insights(current_user=Depends(get_current_user)):
    try:
        user_id = str(current_user["_id"])
        ai      = TimevoraAI(user_id, db)
        profile = await ai.get_productivity_profile()
        if not profile.get("ready"):
            return {"success": True, "ready": False, "insights": [], "feedbacks_given": profile.get("feedbacks_given", 0), "feedbacks_needed": profile.get("feedbacks_needed", 5), "message": profile.get("message", "Complete more tasks to unlock insights!")}
        return {"success": True, "ready": True, "insights": profile.get("insights", []), "chronotype": profile.get("chronotype"), "accuracy_trend": profile.get("accuracy_trend", "stable"), "overall_accuracy": profile.get("overall_accuracy", 0), "feedbacks_given": profile.get("feedbacks_given", 0)}
    except Exception as e:
        logger.error(f"AI insights error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "insights": []}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LEGACY CHRONOTYPE DETECTION
# ╚══════════════════════════════════════════════════════════════════════════════

async def detect_chronotype(user_id: str) -> dict:
    try:
        completed_hours = []
        async for task in tasks_col.find({"user_id": user_id, "completed": True}, {"created_at": 1, "scheduled_time": 1, "completed_at": 1}):
            dt = task.get("completed_at") or task.get("scheduled_time") or task.get("created_at")
            if dt:
                if isinstance(dt, str):
                    try:
                        dt = datetime.fromisoformat(dt)
                    except (ValueError, TypeError):
                        continue
                completed_hours.append(dt.hour)

        async for record in task_history.find({"user_id": user_id}, {"created_at": 1, "hour_of_day": 1}):
            hour = record.get("hour_of_day")
            if hour is not None:
                completed_hours.append(hour)
            elif record.get("created_at") and isinstance(record["created_at"], datetime):
                completed_hours.append(record["created_at"].hour)

        if len(completed_hours) < 5:
            return None

        morning_count   = sum(1 for h in completed_hours if 5  <= h < 12)
        afternoon_count = sum(1 for h in completed_hours if 12 <= h < 17)
        evening_count   = sum(1 for h in completed_hours if 17 <= h < 23)
        night_count     = sum(1 for h in completed_hours if h >= 23 or h < 5)
        max_count       = max(morning_count, afternoon_count, evening_count, night_count)

        if max_count == morning_count and morning_count > 0:
            return {"type": "Morning Lion",    "emoji": "🦁", "peak": "9–11 AM",      "peak_slot": "morning",   "description": "You're at your sharpest in the morning.", "color": "#F59E0B"}
        elif max_count == evening_count and evening_count > 0:
            return {"type": "Night Owl",       "emoji": "🦉", "peak": "8–10 PM",      "peak_slot": "evening",   "description": "Your creative energy peaks in the evening.", "color": "#3B82F6"}
        elif max_count == night_count and night_count > 0:
            return {"type": "Midnight Phoenix","emoji": "🔥", "peak": "10 PM – 1 AM", "peak_slot": "night",     "description": "You do your best work when the world is quiet.", "color": "#EF4444"}
        else:
            return {"type": "Afternoon Wolf",  "emoji": "🐺", "peak": "2–4 PM",       "peak_slot": "afternoon", "description": "You hit your stride after lunch.", "color": "#8B5CF6"}
    except Exception as e:
        logger.error(f"Chronotype detection error: {e}")
        return None


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  DAILY PLANS
# ║  NOTE: Specific routes (/generate, /update-schedule, /by-date) MUST come
# ║  BEFORE the catch-all /{plan_id} route or FastAPI will treat them as IDs.
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/daily-plans")
async def get_daily_plans(current_user=Depends(get_current_user)):
    plans = []
    async for p in daily_plans.find({"user_id": str(current_user["_id"])}).sort("created_at", -1):
        p["_id"] = str(p["_id"])
        plans.append(p)
    return plans

@api_router.post("/daily-plans/generate")
async def generate_daily_plan(request: ScheduleRequest, current_user=Depends(get_current_user)):
    try:
        user_id     = str(current_user["_id"])
        target_date = request.date or date.today().isoformat()
        tasks       = request.tasks or []

        if not tasks:
            dismissed_ids = set()
            async for d in dismissed_tasks.find({"user_id": user_id}, {"task_id": 1}):
                dismissed_ids.add(d["task_id"])
            db_tasks = []
            async for t in tasks_col.find({"user_id": user_id, "completed": {"$ne": True}, "is_deleted": {"$ne": True}, "status": {"$nin": ["completed", "deleted", "dismissed"]}}).limit(50):
                task_id_str = str(t["_id"])
                if task_id_str in dismissed_ids:
                    continue
                db_tasks.append({"name": t.get("text", ""), "estimatedTime": t.get("estimated_time", 1.0), "priority": t.get("priority", "medium"), "difficulty": t.get("difficulty", "medium"), "category": t.get("category", "general"), "task_id": task_id_str})
            tasks = db_tasks

        if not tasks:
            return {"success": True, "message": "No tasks to schedule. Add tasks first!", "schedule": []}

        ai = TimevoraAI(user_id, db)
        await ai._load_user_context()
        for t in tasks:
            t.setdefault("difficulty", "medium")
            t.setdefault("priority",   "medium")
            t.setdefault("category",   "general")
            t.setdefault("duration",   t.get("estimatedTime", 1.0))
            t.setdefault("name",       t.get("text", t.get("task", "Untitled")))

        schedule  = ai._create_schedule_manually(tasks, [])
        formatted = ai._format_schedule_items(schedule)

        await daily_plans.update_one({"user_id": user_id, "date": target_date}, {"$set": {"schedule": formatted, "task_count": len(tasks), "created_at": datetime.now(timezone.utc), "source": "ai_generated"}}, upsert=True)

        return {"success": True, "schedule": formatted, "date": target_date, "patterns_used": bool(ai.context.productivity_patterns), "message": f"Schedule created with {len(formatted)} time blocks"}

    except Exception as e:
        logger.error(f"Generate daily plan error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "schedule": []}


@api_router.post("/daily-plans/update-schedule")
async def update_schedule(request: UpdateScheduleRequest, current_user=Depends(get_current_user)):
    """
    ✅ THE KEY FIX: Save updated schedule after task deletion.
    Called by frontend whenever a task is deleted or the schedule changes.
    Empty schedule = delete the plan document so refresh shows empty state.
    """
    try:
        user_id     = str(current_user["_id"])
        target_date = request.date or date.today().isoformat()
        schedule    = request.schedule

        if not schedule:
            # No tasks left — delete plan so page refreshes to empty
            await daily_plans.delete_one({"user_id": user_id, "date": target_date})
            logger.info(f"🗑️ Plan cleared for user {user_id} on {target_date}")
            return {"success": True, "message": "Plan cleared", "date": target_date}

        await daily_plans.update_one(
            {"user_id": user_id, "date": target_date},
            {"$set": {"schedule": schedule, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

        logger.info(f"✅ Schedule updated for user {user_id} on {target_date}: {len(schedule)} items")
        return {"success": True, "message": f"Schedule saved with {len(schedule)} tasks", "date": target_date, "count": len(schedule)}

    except Exception as e:
        logger.error(f"update_schedule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/daily-plans/by-date")
async def delete_daily_plan_by_date(request: DeletePlanByDateRequest, current_user=Depends(get_current_user)):
    """Delete plan for a specific date (Clear button). Uses /by-date to avoid conflict with /{plan_id}."""
    try:
        user_id     = str(current_user["_id"])
        target_date = request.date or date.today().isoformat()
        result      = await daily_plans.delete_one({"user_id": user_id, "date": target_date})
        logger.info(f"🗑️ Plan cleared for user {user_id} on {target_date} (deleted: {result.deleted_count})")
        return {"success": True, "message": "Plan cleared", "date": target_date, "deleted_count": result.deleted_count}
    except Exception as e:
        logger.error(f"delete_daily_plan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/daily-plans/{plan_date}")
async def get_daily_plan_by_date(plan_date: str, current_user=Depends(get_current_user)):
    user_id = str(current_user["_id"])
    plan = await daily_plans.find_one({"user_id": user_id, "date": plan_date})
    if plan:
        plan["_id"] = str(plan["_id"])
        return plan
    return {"message": "No plan found for this date", "schedule": []}


@api_router.delete("/daily-plans/{plan_id}")
async def delete_plan(plan_id: str, current_user=Depends(get_current_user)):
    await daily_plans.delete_one({"_id": ObjectId(plan_id), "user_id": str(current_user["_id"])})
    return {"status": "deleted"}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ACCURACY + PRODUCTIVITY SCORE
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/accuracy")
async def get_accuracy_endpoint(current_user=Depends(get_current_user)):
    return await get_user_accuracy(str(current_user["_id"]))

@api_router.get("/productivity-score")
async def get_productivity_score(current_user=Depends(get_current_user)):
    user_id  = str(current_user["_id"])
    analyzer = ProductivityAnalyzer(user_id, db)
    patterns = await analyzer.analyze_patterns()
    score_data = patterns.get("productivity_score", {})
    focus_data = patterns.get("focus_patterns", {})
    completion = patterns.get("task_completion", {})
    return {"score": score_data.get("overall", 0), "completion_rate": completion.get("overall_rate", 0), "focus_hours": focus_data.get("average_focus_time", 0), "components": score_data.get("components", {})}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  DAY CONTEXT — User's daily structure (blocked slots, meals, wake/sleep)
# ╚══════════════════════════════════════════════════════════════════════════════

class DayContextRequest(BaseModel):
    """Direct save of day context from frontend settings panel."""
    wake_up:       Optional[float] = 7.0
    day_start:     Optional[float] = 9.0
    lunch_start:   Optional[float] = 13.0
    lunch_end:     Optional[float] = 14.0
    dinner_start:  Optional[float] = 19.0
    day_end:       Optional[float] = 22.0
    blocked_slots: Optional[list]  = []

@api_router.get("/day-context")
async def get_day_context(current_user=Depends(get_current_user)):
    user_id = str(current_user["_id"])
    doc = await db.user_day_context.find_one({"user_id": user_id})
    if doc:
        doc["_id"] = str(doc["_id"])
        return {"success": True, "context": doc, "has_custom": True}
    # Return defaults
    return {
        "success":    True,
        "has_custom": False,
        "context": {
            "wake_up": 7.0, "day_start": 9.0,
            "lunch_start": 13.0, "lunch_end": 14.0,
            "dinner_start": 19.0, "day_end": 22.0,
            "blocked_slots": [],
        },
    }

@api_router.post("/day-context")
async def save_day_context(request: DayContextRequest, current_user=Depends(get_current_user)):
    user_id = str(current_user["_id"])
    ctx = request.dict()
    ctx["user_id"]    = user_id
    ctx["has_custom"] = True
    ctx["updated_at"] = datetime.now(timezone.utc)
    await db.user_day_context.update_one(
        {"user_id": user_id}, {"$set": ctx}, upsert=True
    )
    return {"success": True, "message": "Day context saved!"}


class DailyCheckinRequest(BaseModel):
    """Save a date-specific schedule override (e.g. 'today I have no college')."""
    date:          str
    day_start:     Optional[float] = None
    day_end:       Optional[float] = None
    lunch_start:   Optional[float] = None
    lunch_end:     Optional[float] = None
    dinner_start:  Optional[float] = None
    blocked_slots: Optional[list]  = []
    note:          Optional[str]   = None

@api_router.post("/day-context/today")
async def save_today_context(request: DailyCheckinRequest, current_user=Depends(get_current_user)):
    """
    Save a date-specific override so today's schedule is different
    from the user's usual routine without changing their saved routine.
    """
    user_id = str(current_user["_id"])
    ctx = {k: v for k, v in request.dict().items() if v is not None}
    ctx["user_id"]      = user_id
    ctx["date_override"] = request.date
    ctx["has_custom"]   = True
    ctx["updated_at"]   = datetime.now(timezone.utc)
    await db.user_day_context.update_one(
        {"user_id": user_id, "date_override": request.date},
        {"$set": ctx},
        upsert=True,
    )
    return {"success": True, "message": f"Today's schedule saved for {request.date}"}

@api_router.get("/day-context/today")
async def get_today_context(current_user=Depends(get_current_user)):
    """Get the context specifically for today (date-specific override if set)."""
    user_id   = str(current_user["_id"])
    today_str = date.today().isoformat()
    doc = await db.user_day_context.find_one(
        {"user_id": user_id, "date_override": today_str}
    )
    if doc:
        doc["_id"] = str(doc["_id"])
        return {"success": True, "has_override": True, "context": doc}
    return {"success": True, "has_override": False, "date": today_str}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  AI ASSISTANT CHAT — Merges new tasks into existing schedule
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/ai-assistant/chat")
async def chat_with_ai(
    request: ChatMessage, current_user=Depends(get_current_user)
):
    try:
        user_id   = str(current_user["_id"])
        assistant = AIAssistant(user_id, db)
        response  = await assistant.process_message(request.message)

        # ── Save / MERGE schedule to MongoDB ──────────────────────────────────
        if (
            response.get("type") == "schedule"
            and response.get("schedule")
            and len(response["schedule"]) > 0
        ):
            today_str = date.today().isoformat()
            new_items = response["schedule"]

            try:
                # Fetch any existing plan for today
                existing_plan = await daily_plans.find_one(
                    {"user_id": user_id, "date": today_str}
                )
                existing_schedule = existing_plan.get("schedule", []) if existing_plan else []

                # Decide: add-task (merge) vs full re-plan (replace)
                # Priority 1: AI explicitly flagged add_intent
                # Priority 2: keyword heuristic on user message
                msg_lower = request.message.lower()
                is_add_intent = bool(response.get("add_intent"))  # set by _handle_add_task
                if not is_add_intent and existing_schedule:
                    _add_kws  = ["add ", "also add", "also schedule", "include ",
                                 "put ", "insert", "add task", "one more",
                                 "add another", "i also need", "i also have"]
                    _full_kws = ["plan my day", "plan my whole", "reschedule",
                                 "redo my schedule", "create schedule", "make a new",
                                 "start over", "start fresh", "optimize my schedule",
                                 "organise my day", "organize my day"]
                    has_add  = any(kw in msg_lower for kw in _add_kws)
                    has_full = any(kw in msg_lower for kw in _full_kws)
                    is_add_intent = has_add and not has_full

                if is_add_intent and existing_schedule:
                    # ── ADD TASK: _handle_add_task already placed the new tasks
                    # in free slots using _find_free_slots, which returns ONLY
                    # the new tasks.  We merge them here and send the FULL
                    # merged list back to the frontend so it can just replace
                    # its state (no second merge needed on the frontend).
                    def _decimal(time_str):
                        """'2:15 PM' → 14.25"""
                        if not time_str:
                            return None
                        m = re.match(r'(\d+):(\d+)\s*(AM|PM)', str(time_str), re.IGNORECASE)
                        if not m:
                            return None
                        h, mn, period = int(m[1]), int(m[2]), m[3].upper()
                        if period == "PM" and h != 12: h += 12
                        if period == "AM" and h == 12: h = 0
                        return h + mn / 60

                    def _fmt(decimal_h):
                        """14.25 → '2:15 PM'"""
                        h = int(decimal_h)
                        m = round((decimal_h - h) * 60)
                        period = "AM" if h < 12 else "PM"
                        dh = h % 12 or 12
                        return f"{dh}:{m:02d} {period}"

                    # Normalise existing schedule times to strings for consistent storage
                    normalised_existing = []
                    for item in existing_schedule:
                        st = item.get("start_time")
                        et = item.get("end_time")
                        if isinstance(st, (int, float)):
                            item = {**item, "start_time": _fmt(st), "end_time": _fmt(et or st + item.get("duration", 1))}
                        normalised_existing.append(item)

                    # Normalise new items too
                    normalised_new = []
                    for item in new_items:
                        st = item.get("start_time")
                        et = item.get("end_time")
                        if isinstance(st, (int, float)):
                            item = {**item, "start_time": _fmt(st), "end_time": _fmt(et or st + item.get("duration", 1))}
                        normalised_new.append(item)

                    merged_schedule = normalised_existing + normalised_new

                    # ── CRITICAL: tell frontend the response already has the
                    # full merged schedule — do NOT merge again on the frontend.
                    response["schedule"]                  = merged_schedule
                    response["full_schedule_in_response"] = True

                    logger.info(
                        f"➕ Merged {len(normalised_new)} new task(s) into existing "
                        f"{len(normalised_existing)}-item schedule for user {user_id}"
                    )
                else:
                    merged_schedule = new_items
                    response["full_schedule_in_response"] = False
                    logger.info(
                        f"🔄 Full schedule replacement ({len(new_items)} items) "
                        f"for user {user_id} on {today_str}"
                    )

                await daily_plans.update_one(
                    {"user_id": user_id, "date": today_str},
                    {
                        "$set": {
                            "schedule":    merged_schedule,
                            "insights":    response.get("insights", []),
                            "tasks_found": response.get("tasks_found", []),
                            "created_at":  datetime.now(timezone.utc),
                            "source":      "ai_chat",
                        }
                    },
                    upsert=True,
                )
                logger.info(
                    f"✅ Schedule saved to daily_plans for user {user_id} "
                    f"on {today_str} with {len(merged_schedule)} tasks"
                )
            except Exception as save_err:
                logger.error(f"Failed to save/merge schedule to daily_plans: {save_err}")

        return response

    except Exception as e:
        logger.error(f"AI Assistant error: {e}", exc_info=True)
        return {
            "type":    "error",
            "message": "I'm having trouble right now. Please try again.",
        }


@api_router.get("/ai-assistant/context")
async def get_ai_context_endpoint(current_user=Depends(get_current_user)):
    try:
        return await get_ai_context(str(current_user["_id"]), db)
    except Exception as e:
        logger.error(f"Context error: {e}")
        # ✅ UPDATED: Student-focused suggestions (Priority 3 fix)
        return {
            "suggestions": [
                "I have Physics, Maths and Chemistry to study today — plan it",
                "Exam in 3 days, help me plan my revision schedule",
                "I study best in the morning, plan 6 hours of study",
                "Analyze my study patterns this week"
            ],
            "has_history": False,
            "quick_actions": ["Create Schedule", "Get Advice", "Analyze Habits"]
        }


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  AI GUIDANCE (NEW: Performance page AI chat)
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/ai/guidance")
async def get_guidance(
    request: ChatMessage,
    current_user=Depends(get_current_user),
):
    """
    Performance page AI coaching chat.
    Uses real user data to give personalised answers.
    """
    try:
        result = await get_guidance_response(
            str(current_user["_id"]),
            db,
            request.message,
        )
        return result
    except Exception as e:
        logger.error(f"Guidance error: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Could not load guidance. Please try again.",
        }


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ADVANCED AI ROUTES
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/ai/advanced-plan")
async def advanced_planning(request: AdvancedPlanRequest, current_user=Depends(get_current_user)):
    try:
        scheduler = IntelligentScheduler(str(current_user["_id"]), db)
        result    = await scheduler.create_optimal_schedule(request.tasks, request.preferences or {})
        formatted = [{"task": item["task"], "start_time": _fmt_time(item["start_time"]), "end_time": _fmt_time(item["end_time"]), "duration": round(item["duration"], 1), "priority": item.get("priority", "medium"), "focus_score": item.get("focus_score", 5), "energy_score": item.get("energy_score", 0.5), "time": f"{_fmt_time(item['start_time'])} - {_fmt_time(item['end_time'])}"} for item in result["schedule"]]
        plan_date = request.date or date.today().isoformat()
        await daily_plans.update_one({"user_id": str(current_user["_id"]), "date": plan_date}, {"$set": {"schedule": formatted, "created_at": datetime.now(timezone.utc), "source": "advanced_ai"}}, upsert=True)
        return {"success": True, "schedule": formatted, "insights": result["insights"], "metrics": {"total_focus_time": round(result.get("total_focus_time", 0), 1), "energy_alignment": round(result.get("energy_aligned", 0), 3)}}
    except Exception as e:
        logger.error(f"Advanced planning error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@api_router.get("/ai/recommendations")
async def get_recommendations(current_user=Depends(get_current_user)):
    try:
        user_id      = str(current_user["_id"])
        pending      = await db.tasks.find({"user_id": user_id, "completed": False}).sort("created_at", -1).limit(20).to_list(20)
        history      = await db.task_history.find({"user_id": user_id}).sort("created_at", -1).limit(50).to_list(50)
        accuracy     = await get_user_accuracy(user_id)
        streak       = await calculate_user_streak(user_id)
        recommender  = TaskRecommender(user_id, db)
        recommendations = await recommender.get_recommendations({"pending_tasks": pending, "task_history": history, "stats": {**accuracy, "streak": streak}})
        return {"success": True, "recommendations": recommendations}
    except Exception as e:
        logger.error(f"Recommendations error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@api_router.post("/ai/train-model")
async def train_ai_model(current_user=Depends(get_current_user)):
    try:
        learner = AdaptiveLearner(str(current_user["_id"]), db)
        success = await learner.train_model()
        if success:
            return {"success": True, "message": "🎉 Model trained! AI predictions are now personalised to you."}
        return {"success": False, "message": "📊 Need at least 10 completed tasks to train. Keep tracking!"}
    except Exception as e:
        logger.error(f"Train model error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@api_router.get("/ai/patterns")
async def get_learning_patterns(current_user=Depends(get_current_user)):
    try:
        learner  = AdaptiveLearner(str(current_user["_id"]), db)
        patterns = await learner.get_productivity_patterns()
        return {"success": True, "patterns": patterns}
    except Exception as e:
        return {"success": False, "error": str(e)}

@api_router.post("/ai/predict-task")
async def predict_task(request: TaskPredictionRequest, current_user=Depends(get_current_user)):
    try:
        learner       = AdaptiveLearner(str(current_user["_id"]), db)
        ctx           = request.context or {"hour": datetime.now().hour, "day": datetime.now().weekday(), "month": datetime.now().month}
        accuracy      = await learner.predict_accuracy(request.task, ctx)
        adjusted_time = round(request.task.get("time", 1) * accuracy, 1)
        return {"success": True, "predicted_accuracy": accuracy, "adjusted_time": adjusted_time}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  WEBSOCKET + NOTIFICATIONS
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.websocket("/ws/{user_id}")
async def websocket_route(websocket: WebSocket, user_id: str):
    await websocket_endpoint(websocket, user_id)

@api_router.post("/notify/{user_id}")
async def send_notification(user_id: str, notification: NotificationRequest, current_user=Depends(get_current_user)):
    await manager.broadcast_notification(user_id, notification.dict())
    return {"status": "notification sent"}

@api_router.get("/online-users")
async def get_online_users(current_user=Depends(get_current_user)):
    return {"online_count": len(manager.active_connections)}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ML ROUTES
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.get("/ml/patterns")
async def get_ml_patterns(current_user=Depends(get_current_user)):
    learner  = TimevoraLearner(str(current_user["_id"]), db)
    patterns = await learner.get_productivity_patterns()
    return patterns

@api_router.post("/ml/predict")
async def ml_predict(task: dict, current_user=Depends(get_current_user)):
    learner  = TimevoraLearner(str(current_user["_id"]), db)
    ctx      = {"hour": datetime.now().hour, "day": datetime.now().weekday(), "month": datetime.now().month}
    accuracy = await learner.predict_accuracy(task, ctx)
    return {"predicted_accuracy": accuracy}

@api_router.get("/analytics")
async def get_analytics(days: int = 30, current_user=Depends(get_current_user)):
    service   = AnalyticsService(db)
    analytics = await service.get_user_analytics(str(current_user["_id"]), days)
    return analytics

@api_router.post("/ml/train")
async def ml_train(current_user=Depends(get_current_user)):
    learner = TimevoraLearner(str(current_user["_id"]), db)
    success = await learner.train_model()
    return {"success": success}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  SHARED HELPER FUNCTIONS
# ╚══════════════════════════════════════════════════════════════════════════════

async def get_user_accuracy(user_id: str) -> dict:
    records = []
    async for r in task_history.find({"user_id": user_id}):
        records.append(r)
    if not records:
        return {"easy": 1.0, "medium": 1.0, "hard": 1.0}
    buckets: dict = {"easy": [], "medium": [], "hard": []}
    for r in records:
        ai_time = r.get("aiTime", 0)
        actual  = r.get("actualTime", 0)
        diff    = r.get("difficulty", "medium")
        if ai_time > 0 and actual > 0 and diff in buckets:
            buckets[diff].append(actual / ai_time)
    return {k: round(sum(v) / len(v), 2) if v else 1.0 for k, v in buckets.items()}


async def get_category_accuracy(user_id: str) -> dict:
    records = []
    async for r in task_history.find({"user_id": user_id}):
        records.append(r)
    if not records:
        return {}
    buckets: dict = {}
    for r in records:
        ai_time  = r.get("aiTime", 0)
        actual   = r.get("actualTime", 0)
        category = r.get("category", "general")
        if ai_time > 0 and actual > 0:
            if category not in buckets:
                buckets[category] = []
            buckets[category].append(actual / ai_time)
    return {k: round(sum(v) / len(v), 3) if v else 1.0 for k, v in buckets.items() if len(v) >= 2}


async def calculate_user_streak(user_id: str) -> int:
    try:
        plans  = await daily_plans.find({"user_id": user_id}).sort("date", -1).limit(30).to_list(30)
        streak = 0
        today  = datetime.now().date()
        for plan in plans:
            try:
                plan_date = datetime.fromisoformat(plan["date"]).date()
            except (ValueError, KeyError):
                continue
            if plan_date == today - timedelta(days=streak):
                if len(plan.get("optimizedTasks", plan.get("schedule", []))) > 0:
                    streak += 1
                else:
                    break
            else:
                break
        return streak
    except Exception as e:
        logger.error(f"calculate_user_streak error: {e}")
        return 0


def _fmt_time(hour: Optional[float]) -> str:
    if hour is None:
        return ""
    h = int(hour)
    m = int((hour - h) * 60)
    period  = "AM" if h < 12 else "PM"
    display = h % 12 or 12
    return f"{display}:{m:02d} {period}"

format_time_decimal = _fmt_time


def _timevora_ai_simple(planning_data: dict) -> str:
    overloaded = planning_data.get("overloaded", False)
    hard_tasks = [t["name"] for t in planning_data.get("tasks", []) if t.get("difficulty") == "hard"]
    total      = planning_data.get("totalLoad", 0)
    parts = []
    if overloaded:
        parts.append("Your workload is too heavy for one day. Consider moving some tasks to tomorrow.")
    if hard_tasks:
        parts.append(f"Schedule hard tasks like {', '.join(hard_tasks[:2])} in the morning when your energy is highest.")
    if total < 3 and not overloaded:
        parts.append("You can take on more today if you feel productive.")
    return " ".join(parts) or "Your schedule looks balanced and realistic. Great job planning today!"


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LEGACY ENDPOINTS
# ╚══════════════════════════════════════════════════════════════════════════════

@api_router.post("/ai-insight")
async def ai_insight(planning: AIPlanningData, current_user=Depends(get_current_user)):
    accuracy   = await get_user_accuracy(str(current_user["_id"]))
    ai_message = _timevora_ai_simple(planning.model_dump())
    return {"message": ai_message}

@api_router.post("/analyze-day")
async def analyze_day(data: AnalyzeDayRequest, current_user=Depends(get_current_user)):
    difficulty_factor = {"easy": 1.1, "medium": 1.35, "hard": 1.9}
    priority_factor   = {"low": 1.0,  "medium": 1.3,  "high": 1.7}
    accuracy = await get_user_accuracy(str(current_user["_id"]))
    enriched = []
    for t in data.tasks:
        base_time  = t.time * difficulty_factor.get(t.difficulty, 1.35)
        adjustment = accuracy.get(t.difficulty, 1.0)
        ai_time    = round(base_time * adjustment, 1)
        score      = difficulty_factor.get(t.difficulty, 1.35) * priority_factor.get(t.priority, 1.3) * t.time
        enriched.append({"id": str(uuid.uuid4()), "name": t.name, "priority": t.priority, "difficulty": t.difficulty, "userTime": t.time, "aiTime": ai_time, "score": score})

    ordered  = sorted(enriched, key=lambda x: x["score"], reverse=True)
    hour     = 9
    schedule = []
    for task in ordered:
        remaining = max(1, int(round(task["aiTime"])))
        while remaining > 0:
            schedule.append({"time": f"{hour}:00 - {hour + 1}:00", "task": task["name"], "duration": 1, "priority": task["priority"]})
            hour += 1
            remaining -= 1

    today_str = date.today().isoformat()
    await daily_plans.update_one({"user_id": str(current_user["_id"]), "date": today_str}, {"$set": {"optimizedTasks": ordered, "schedule": schedule, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    await manager.broadcast_to_user(str(current_user["_id"]), {"type": "schedule:ready", "date": today_str, "task_count": len(ordered), "timestamp": datetime.now(timezone.utc).isoformat()})
    return {"optimizedTasks": ordered, "schedule": schedule}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  STARTUP
# ╚══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def _create_indexes():
    try:
        await task_history.create_index([("user_id", 1), ("created_at", -1)])
        await daily_plans.create_index( [("user_id", 1), ("date",       -1)])
        await tasks_col.create_index(   [("user_id", 1), ("completed",   1)])
        await priority_feedback.create_index([("user_id", 1), ("created_at", -1)])
        await task_history.create_index([("user_id", 1), ("category",   1)])
        await task_history.create_index([("user_id", 1), ("difficulty", 1)])
        await dismissed_tasks.create_index([("user_id", 1), ("task_id", 1)], unique=True)
        await tasks_col.create_index([("user_id", 1), ("status",     1)])
        await tasks_col.create_index([("user_id", 1), ("is_deleted", 1)])
        logger.info("✅ MongoDB indexes ensured")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ROUTER + ENTRY POINT
# ╚══════════════════════════════════════════════════════════════════════════════

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting Timevora API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)