# backend/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Any
import asyncio
import json
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        print(f"🔌 User {user_id} connected. Connections: {len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"🔌 User {user_id} disconnected")
    
    async def send_personal_message(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.add(connection)
            self.active_connections[user_id] -= disconnected
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        await self.send_personal_message(user_id, message)
    
    async def broadcast_notification(self, user_id: str, notification: dict):
        await self.send_personal_message(user_id, {
            "type": "notification",
            **notification,
            "timestamp": datetime.now().isoformat()
        })

# Global instance
manager = ConnectionManager()

# WebSocket endpoint
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get('type')
                
                if message_type == 'ping':
                    await websocket.send_json({'type': 'pong'})
                
                elif message_type == 'task:completed':
                    # Broadcast to user
                    await manager.broadcast_to_user(message.get('user_id'), {
                        'type': 'task:completed',
                        'task': message.get('task'),
                        'timestamp': datetime.now().isoformat()
                    })
                
                elif message_type == 'schedule:ready':
                    await manager.broadcast_to_user(message.get('user_id'), {
                        'type': 'schedule:ready',
                        'date': message.get('date'),
                        'tasks': message.get('tasks')
                    })
                    
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)