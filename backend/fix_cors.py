# fix_cors.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# ✅ SIMPLE CORS - This WILL work
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/tasks")
def get_tasks():
    return [{"_id": "1", "text": "Test task from fix_cors", "priority": "medium", "completed": False}]

@app.post("/api/tasks")
def create_task(task: dict):
    print("✅ Task received:", task)
    return {
        "_id": "123",
        "text": task.get("text", ""),
        "priority": task.get("priority", "medium"),
        "completed": False
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)