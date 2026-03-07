from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Any
import asyncio
import json
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        # Store active connections: user_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store user info
        self.user_info: Dict[str, dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Broadcast user online status
        await self.broadcast_user_status(user_id, "online")
        
        print(f"🔌 User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                # Broadcast user offline status
                asyncio.create_task(self.broadcast_user_status(user_id, "offline"))
        
        print(f"🔌 User {user_id} disconnected")
    
    async def broadcast_user_status(self, user_id: str, status: str):
        """Broadcast user online/offline status"""
        await self.broadcast_to_all({
            "type": "user_status",
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_personal_message(self, user_id: str, message: dict):
        """Send message to specific user"""
        if user_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.add(connection)
            
            # Clean up disconnected
            self.active_connections[user_id] -= disconnected
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected users"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(user_id, message)
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast to all connections of a specific user"""
        await self.send_personal_message(user_id, message)
    
    async def broadcast_task_update(self, task: dict, action: str):
        """Broadcast task updates to relevant users"""
        # If task has assigned users, notify them
        if 'assigned_to' in task:
            for user_id in task['assigned_to']:
                await self.send_personal_message(user_id, {
                    "type": f"task:{action}",
                    "task": task,
                    "timestamp": datetime.now().isoformat()
                })
    
    async def broadcast_notification(self, user_id: str, notification: dict):
        """Send notification to user"""
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
            message = json.loads(data)
            
            # Handle different message types
            message_type = message.get('type')
            
            if message_type == 'ping':
                await websocket.send_json({'type': 'pong'})
            
            elif message_type == 'task:completed':
                # Broadcast to all connections that task is completed
                await manager.broadcast_task_update(message['task'], 'completed')
                
                # Send achievement notification if applicable
                if message.get('streak'):
                    await manager.broadcast_notification(message['user_id'], {
                        'type': 'achievement',
                        'title': '🔥 Streak Achieved!',
                        'message': f"You've completed {message['streak']} tasks in a row!",
                        'icon': '🏆'
                    })
            
            elif message_type == 'schedule:ready':
                await manager.broadcast_to_user(message['user_id'], {
                    'type': 'schedule:ready',
                    'date': message['date'],
                    'tasks': message['tasks']
                })
            
            elif message_type == 'chat:message':
                # Handle real-time chat
                await manager.broadcast_to_user(message['to_user_id'], {
                    'type': 'chat:message',
                    'from': message['from_user_id'],
                    'message': message['message'],
                    'timestamp': datetime.now().isoformat()
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)