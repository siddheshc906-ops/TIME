# simple_server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# SIMPLE CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/tasks")
def get_tasks():
    return [{"_id": "1", "text": "Test", "priority": "medium", "completed": False}]

@app.post("/api/tasks")
def create_task(task: dict):
    print("✅ Task received:", task)
    return {"_id": "123", "text": task.get("text"), "priority": "medium", "completed": False}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)