# main.py - Real-Time Translation Backend with Daily.co Video
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from typing import Optional
import json
import requests

# Import your services
from room_manager import RoomManager
from translation_pipeline import TranslationPipeline

# ========================================
# FastAPI App Initialization
# ========================================
app = FastAPI(
    title="Real-Time Translation API with Video",
    description="Bidirectional real-time translation with video call support",
    version="2.1"
)

# ========================================
# CORS Configuration
# ========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://*.github.io",
        "https://railway.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# Initialize Services
# ========================================
room_manager = RoomManager()
translation_pipeline = TranslationPipeline()

# Daily.co Configuration
DAILY_API_KEY = os.getenv("DAILY_API_KEY")
DAILY_API_BASE = "https://api.daily.co/v1"

# ========================================
# Pydantic Models
# ========================================
class RoomResponse(BaseModel):
    room_code: str
    message: str
    video_url: Optional[str] = None

class JoinRoomResponse(BaseModel):
    room_code: str
    user_id: str
    message: str
    video_url: Optional[str] = None

# ========================================
# Daily.co Helper Functions
# ========================================

def create_daily_room(room_code: str) -> Optional[str]:
    """
    Create a Daily.co video room
    
    Args:
        room_code: Unique room identifier
        
    Returns:
        Daily.co room URL or None if failed
    """
    if not DAILY_API_KEY:
        print("⚠️  DAILY_API_KEY not set - video disabled")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {DAILY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Create room with custom name
        payload = {
            "name": f"translator-{room_code.lower()}",
            "privacy": "public",
            "properties": {
                "enable_chat": False,  # We have our own chat
                "enable_screenshare": False,
                "start_video_off": False,
                "start_audio_off": False,
                "enable_advanced_chat": False,
                "max_participants": 10
            }
        }
        
        response = requests.post(
            f"{DAILY_API_BASE}/rooms",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            video_url = data.get("url")
            print(f"✅ Created Daily.co room: {video_url}")
            return video_url
        else:
            print(f"❌ Daily.co room creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating Daily.co room: {e}")
        return None

def delete_daily_room(room_code: str):
    """Delete a Daily.co video room"""
    if not DAILY_API_KEY:
        return
    
    try:
        headers = {
            "Authorization": f"Bearer {DAILY_API_KEY}"
        }
        
        room_name = f"translator-{room_code.lower()}"
        
        requests.delete(
            f"{DAILY_API_BASE}/rooms/{room_name}",
            headers=headers,
            timeout=10
        )
        
        print(f"🗑️  Deleted Daily.co room: {room_name}")
        
    except Exception as e:
        print(f"❌ Error deleting Daily.co room: {e}")

# ========================================
# HTTP Endpoints
# ========================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Real-Time Translation API with Video",
        "version": "2.1",
        "mode": "bidirectional",
        "video_enabled": bool(DAILY_API_KEY),
        "endpoints": {
            "create_room": "POST /api/room/create",
            "join_room": "POST /api/room/join/{room_code}",
            "websocket": "WS /ws/{room_code}/{user_id}",
            "stats": "GET /api/stats"
        }
    }

@app.get("/health")
async def health():
    """Health check for Railway"""
    return {
        "status": "healthy",
        "service": "translation-api",
        "video_enabled": bool(DAILY_API_KEY)
    }

@app.post("/api/room/create", response_model=RoomResponse)
async def create_room():
    """
    Create a new conversation room with video support
    Returns a unique 6-character room code and Daily.co video URL
    """
    room = room_manager.create_room()
    
    # Create Daily.co video room
    video_url = create_daily_room(room.room_code)
    
    return RoomResponse(
        room_code=room.room_code,
        message="Room created successfully",
        video_url=video_url
    )

@app.post("/api/room/join/{room_code}", response_model=JoinRoomResponse)
async def join_room(
    room_code: str,
    user_name: str,
    language: str
):
    """
    Join an existing room with video support
    
    Args:
        room_code: 6-character room code
        user_name: User's display name
        language: User's native language code (e.g., "en", "zh")
    """
    # Validate room exists
    room = room_manager.get_room(room_code.upper())
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Validate language
    if not translation_pipeline.validate_language(language):
        raise HTTPException(
            status_code=400,
            detail=f"Language '{language}' is not supported"
        )
    
    # Generate user ID
    import random
    import string
    user_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    # Get video URL (reconstruct from room code)
    video_url = None
    if DAILY_API_KEY:
        video_url = f"https://translator-{room_code.lower()}.daily.co"
    
    return JoinRoomResponse(
        room_code=room_code.upper(),
        user_id=user_id,
        message=f"Ready to join room {room_code}",
        video_url=video_url
    )

@app.get("/api/stats")
async def get_stats():
    """Get statistics about active rooms and translations"""
    stats = room_manager.get_stats()
    language_info = translation_pipeline.get_supported_languages()
    
    return {
        "rooms": stats,
        "translation": language_info,
        "video_enabled": bool(DAILY_API_KEY)
    }

@app.get("/api/languages")
async def get_languages():
    """Get list of supported languages"""
    return translation_pipeline.get_supported_languages()

@app.delete("/api/room/{room_code}")
async def close_room(room_code: str):
    """Close a room and delete associated Daily.co room"""
    room_code = room_code.upper()
    
    # Delete Daily.co room
    delete_daily_room(room_code)
    
    # Close room in manager
    room_manager.close_room(room_code)
    
    return {"message": f"Room {room_code} closed"}

# ========================================
# WebSocket Endpoint
# ========================================

@app.websocket("/ws/{room_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, user_id: str):
    """
    WebSocket endpoint for real-time translation
    
    Args:
        room_code: Room code to join
        user_id: Unique user identifier
    """
    await websocket.accept()
    
    room_code = room_code.upper()
    room = room_manager.get_room(room_code)
    
    if not room:
        await websocket.send_json({
            "type": "error",
            "message": "Room not found"
        })
        await websocket.close()
        return
    
    # User info (will be set on join message)
    user_name = None
    user_language = None
    
    try:
        # Wait for join message
        data = await websocket.receive_text()
        join_data = json.loads(data)
        
        if join_data.get("type") == "join":
            user_name = join_data.get("user_name", "Guest")
            user_language = join_data.get("language", "en")
            
            # Add participant to room
            room_manager.add_participant(
                room_code=room_code,
                user_id=user_id,
                user_name=user_name,
                language=user_language,
                websocket=websocket
            )
            
            # Get video URL
            video_url = None
            if DAILY_API_KEY:
                video_url = f"https://translator-{room_code.lower()}.daily.co"
            
            # Send welcome message to user
            await websocket.send_json({
                "type": "system",
                "message": f"Welcome {user_name}! You joined room {room_code}",
                "your_language": user_language,
                "video_url": video_url
            })
            
            # Notify others
            await room_manager.broadcast_to_room(
                room_code=room_code,
                message={
                    "type": "system",
                    "message": f"{user_name} joined the conversation ({user_language.upper()})"
                },
                exclude_user=user_id
            )
        
        # Main message loop
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            
            if message_type == "text":
                # Text message - translate and send to all participants
                original_text = message_data.get("text", "")
                
                if not original_text.strip():
                    continue
                
                # Get translation targets
                targets = room.get_translation_targets(user_id)
                
                # Send confirmation to sender
                await websocket.send_json({
                    "type": "sent",
                    "original_text": original_text,
                    "recipients": len(targets)
                })
                
                # Translate and send to each participant
                for participant, source_lang, target_lang in targets:
                    # Translate text
                    result = await translation_pipeline.process_text(
                        text=original_text,
                        source_lang=source_lang,
                        target_lang=target_lang
                    )
                    
                    if result["status"] == "success":
                        # Send translated message
                        await room_manager.send_to_user(
                            room_code=room_code,
                            user_id=participant.user_id,
                            message={
                                "type": "translation",
                                "sender": user_name,
                                "sender_language": source_lang,
                                "original_text": original_text,
                                "translated_text": result["translated_text"],
                                "translated_audio": result.get("translated_audio", ""),
                                "your_language": target_lang
                            }
                        )
    
    except WebSocketDisconnect:
        print(f"❌ User {user_id} disconnected")
    
    except Exception as e:
        print(f"❌ WebSocket error for user {user_id}: {e}")
    
    finally:
        # Remove participant from room
        if user_name:
            room_manager.remove_participant(room_code, user_id)
            
            # Notify others
            await room_manager.broadcast_to_room(
                room_code=room_code,
                message={
                    "type": "system",
                    "message": f"{user_name} left the conversation"
                }
            )
            
            # If room is empty, delete Daily.co room
            if len(room.participants) == 0:
                delete_daily_room(room_code)

# ========================================
# Startup/Shutdown Events
# ========================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("=" * 50)
    print("🚀 Real-Time Translation API Starting...")
    print("=" * 50)
    print(f"✅ Translation Pipeline: Initialized")
    print(f"✅ Room Manager: Ready")
    print(f"✅ Supported Languages: {len(translation_pipeline.get_supported_languages()['languages'])}")
    print(f"{'✅' if DAILY_API_KEY else '⚠️ '} Daily.co Video: {'Enabled' if DAILY_API_KEY else 'Disabled (set DAILY_API_KEY to enable)'}")
    print("=" * 50)

@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("👋 Shutting down Real-Time Translation API...")

# ========================================
# For Railway: Port binding
# ========================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )