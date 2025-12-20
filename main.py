# main.py - Real-Time Translation Backend for Railway
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from typing import Optional
import json

# Import your services (make sure these files are in the same directory)
from room_manager import RoomManager
from translation_pipeline import TranslationPipeline

# ========================================
# FastAPI App Initialization
# ========================================
app = FastAPI(
    title="Real-Time Translation API",
    description="Bidirectional real-time translation with WebSocket support",
    version="2.0"
)

# ========================================
# CORS Configuration (IMPORTANT for Railway + GitHub Pages)
# ========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://holysmokas.github.io/translation-server/",  # github pages
        "https://railway.app",
        "*"  # For development - remove in production if needed
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

# ========================================
# Pydantic Models
# ========================================
class RoomResponse(BaseModel):
    room_code: str
    message: str

class JoinRoomResponse(BaseModel):
    room_code: str
    user_id: str
    message: str

# ========================================
# HTTP Endpoints
# ========================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Real-Time Translation API",
        "version": "2.0",
        "mode": "bidirectional",
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
    return {"status": "healthy", "service": "translation-api"}

@app.post("/api/room/create", response_model=RoomResponse)
async def create_room():
    """
    Create a new conversation room
    Returns a unique 6-character room code
    """
    room = room_manager.create_room()
    
    return RoomResponse(
        room_code=room.room_code,
        message="Room created successfully"
    )

@app.post("/api/room/join/{room_code}", response_model=JoinRoomResponse)
async def join_room(
    room_code: str,
    user_name: str,
    language: str
):
    """
    Join an existing room
    
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
    
    return JoinRoomResponse(
        room_code=room_code.upper(),
        user_id=user_id,
        message=f"Ready to join room {room_code}"
    )

@app.get("/api/stats")
async def get_stats():
    """Get statistics about active rooms and translations"""
    stats = room_manager.get_stats()
    language_info = translation_pipeline.get_supported_languages()
    
    return {
        "rooms": stats,
        "translation": language_info
    }

@app.get("/api/languages")
async def get_languages():
    """Get list of supported languages"""
    return translation_pipeline.get_supported_languages()

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
            
            # Send welcome message to user
            await websocket.send_json({
                "type": "system",
                "message": f"Welcome {user_name}! You joined room {room_code}",
                "your_language": user_language
            })
            
            # Notify others
            await room_manager.broadcast_to_room(
                room_code=room_code,
                message={
                    "type": "system",
                    "message": f"{user_name} joined the conversation ({translation_pipeline.get_language_info(user_language)['code'].upper()})"
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
                    else:
                        print(f"❌ Translation failed: {result.get('error')}")
            
            elif message_type == "audio":
                # Audio message - transcribe, translate, and send
                audio_data = message_data.get("audio", "")
                
                if not audio_data:
                    continue
                
                # Get translation targets
                targets = room.get_translation_targets(user_id)
                
                # Process audio for each participant
                for participant, source_lang, target_lang in targets:
                    # Process audio through pipeline
                    result = await translation_pipeline.process_audio_chunk(
                        audio_data=audio_data,
                        source_lang=source_lang,
                        target_lang=target_lang
                    )
                    
                    if result["status"] == "success":
                        # Send to sender (confirmation)
                        if participant.user_id == user_id:
                            await websocket.send_json({
                                "type": "transcribed",
                                "original_text": result["original_text"]
                            })
                        
                        # Send translated message
                        await room_manager.send_to_user(
                            room_code=room_code,
                            user_id=participant.user_id,
                            message={
                                "type": "translation",
                                "sender": user_name,
                                "sender_language": source_lang,
                                "original_text": result["original_text"],
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