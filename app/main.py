# app/main.py - V2 Bidirectional Translation
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv
from typing import Dict
import asyncio

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Real-Time Translation Server - V2",
    description="Live bidirectional conversation translator - Any language to any language",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import services
from app.services.room_manager import RoomManager
from app.services.translation_pipeline import TranslationPipeline

# Initialize services
room_manager = RoomManager()
translation_pipeline = TranslationPipeline()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Translation server V2 starting...")
    print("✅ Room manager initialized (bidirectional support)")
    print("✅ Translation pipeline ready")

@app.get("/")
def read_root():
    return {
        "status": "running",
        "service": "Real-Time Translation Server V2",
        "version": "2.0.0",
        "features": {
            "bidirectional": True,
            "languages": "any-to-any",
            "mode": "real-time"
        },
        "endpoints": {
            "health": "/health",
            "create_room": "/api/room/create",
            "join_room": "/api/room/join/{room_code}",
            "websocket": "/ws/{room_code}/{user_id}",
            "languages": "/api/languages"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "active_rooms": len(room_manager.rooms),
        "groq_api": os.getenv("GROQ_API_KEY") is not None,
        "google_translate": os.getenv("GOOGLE_APPLICATION_CREDENTIALS") is not None
    }

@app.get("/api/languages")
def get_supported_languages():
    """Get all supported languages - Now supports any-to-any"""
    return {
        "mode": "bidirectional",
        "note": "Each user selects their native language. System translates between all pairs.",
        "supported_languages": [
            {"code": "en", "name": "English", "flag": "🇺🇸"},
            {"code": "zh", "name": "Chinese (Simplified)", "flag": "🇨🇳"},
            {"code": "es", "name": "Spanish", "flag": "🇪🇸"},
            {"code": "fr", "name": "French", "flag": "🇫🇷"},
            {"code": "fa", "name": "Persian (Farsi)", "flag": "🇮🇷"},
            {"code": "ru", "name": "Russian", "flag": "🇷🇺"},
            {"code": "de", "name": "German", "flag": "🇩🇪"},
            {"code": "ja", "name": "Japanese", "flag": "🇯🇵"},
            {"code": "ko", "name": "Korean", "flag": "🇰🇷"},
            {"code": "pt", "name": "Portuguese", "flag": "🇵🇹"},
            {"code": "it", "name": "Italian", "flag": "🇮🇹"},
            {"code": "ar", "name": "Arabic", "flag": "🇸🇦"},
            {"code": "hi", "name": "Hindi", "flag": "🇮🇳"},
            {"code": "tr", "name": "Turkish", "flag": "🇹🇷"},
            {"code": "nl", "name": "Dutch", "flag": "🇳🇱"},
            {"code": "pl", "name": "Polish", "flag": "🇵🇱"},
            {"code": "vi", "name": "Vietnamese", "flag": "🇻🇳"},
            {"code": "th", "name": "Thai", "flag": "🇹🇭"}
        ]
    }

@app.post("/api/room/create")
async def create_room():
    """
    Create a new conversation room (V2 - no language specified)
    Each participant selects their language when joining
    """
    
    room = room_manager.create_room()
    
    return {
        "room_code": room.room_code,
        "created_at": room.created_at.isoformat(),
        "websocket_url": f"ws://localhost:8000/ws/{room.room_code}/{{user_id}}",
        "status": "Room created - share code with conversation partner",
        "note": "Each user will select their language when joining"
    }

@app.get("/api/room/{room_code}")
async def get_room_info(room_code: str):
    """Get information about a room"""
    
    room = room_manager.get_room(room_code)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return {
        "room_code": room.room_code,
        "participants": [
            {
                "user_id": p.user_id,
                "user_name": p.user_name,
                "language": p.language,
                "joined_at": p.joined_at.isoformat()
            }
            for p in room.participants.values()
        ],
        "created_at": room.created_at.isoformat(),
        "is_active": room.is_active
    }

@app.post("/api/room/join/{room_code}")
async def join_room(
    room_code: str, 
    user_name: str = "Guest",
    language: str = "en"
):
    """
    Join an existing conversation room (V2 - with language selection)
    
    - **room_code**: 6-character room code
    - **user_name**: Your display name
    - **language**: Your native language code (en, zh, es, fr, etc.)
    """
    
    room = room_manager.get_room(room_code)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.is_active:
        raise HTTPException(status_code=400, detail="Room is no longer active")
    
    # Validate language code
    valid_languages = ["en", "zh", "es", "fr", "fa", "ru", "de", "ja", "ko", "pt", "it", "ar", "hi", "tr", "nl", "pl", "vi", "th"]
    if language not in valid_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language code. Must be one of: {', '.join(valid_languages)}"
        )
    
    # Generate user ID
    import uuid
    user_id = str(uuid.uuid4())[:8]
    
    return {
        "room_code": room_code,
        "user_id": user_id,
        "user_name": user_name,
        "language": language,
        "websocket_url": f"ws://localhost:8000/ws/{room_code}/{user_id}",
        "status": "Ready to connect"
    }

@app.websocket("/ws/{room_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, user_id: str):
    """
    WebSocket endpoint for real-time bidirectional translation
    
    Expected message format on connect:
    {
        "type": "join",
        "user_name": "Alice",
        "language": "en"
    }
    
    For sending messages:
    {
        "type": "text",
        "text": "Hello, how are you?"
    }
    
    Or audio:
    {
        "type": "audio_chunk",
        "audio_data": "base64_encoded_audio"
    }
    """
    
    # Get room
    room = room_manager.get_room(room_code)
    
    if not room:
        await websocket.close(code=4004, reason="Room not found")
        return
    
    # Accept connection
    await websocket.accept()
    
    # Wait for join message with user info
    try:
        join_data = await websocket.receive_json()
        
        if join_data.get("type") != "join":
            await websocket.close(code=4001, reason="First message must be 'join' type")
            return
        
        user_name = join_data.get("user_name", "Guest")
        language = join_data.get("language", "en")
        
        # Add participant to room with their language
        success = room_manager.add_participant(
            room_code=room_code,
            user_id=user_id,
            user_name=user_name,
            language=language,
            websocket=websocket
        )
        
        if not success:
            await websocket.close(code=4004, reason="Failed to join room")
            return
        
        print(f"✅ {user_name} ({language}) joined room {room_code}")
        
        # Send welcome message
        await websocket.send_json({
            "type": "system",
            "message": f"Connected to room {room_code} as {user_name}",
            "your_language": language,
            "participants": len(room.participants)
        })
        
        # Notify others that someone joined
        await room_manager.broadcast_to_room(
            room_code=room_code,
            message={
                "type": "system",
                "message": f"{user_name} ({language}) joined the conversation",
                "participants": len(room.participants),
                "new_user": {
                    "user_id": user_id,
                    "user_name": user_name,
                    "language": language
                }
            },
            exclude_user=user_id
        )
        
    except Exception as e:
        print(f"❌ Error during join: {e}")
        await websocket.close(code=4002, reason="Join failed")
        return
    
    # Main message loop
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "audio_chunk":
                # Handle audio chunk
                audio_data = data.get("audio_data")  # Base64 encoded
                
                # Get sender info
                sender = room.get_participant(user_id)
                if not sender:
                    continue
                
                # Process through translation pipeline for EACH receiver
                targets = room.get_translation_targets(user_id)
                
                for target_participant, source_lang, target_lang in targets:
                    # Translate from sender's language to target's language
                    result = await translation_pipeline.process_audio_chunk(
                        audio_data=audio_data,
                        source_lang=source_lang,
                        target_lang=target_lang
                    )
                    
                    if result["status"] == "success":
                        # Send translation to specific user
                        await room_manager.send_to_user(
                            room_code=room_code,
                            user_id=target_participant.user_id,
                            message={
                                "type": "translation",
                                "sender": sender.user_name,
                                "sender_language": source_lang,
                                "original_text": result["original_text"],
                                "translated_text": result["translated_text"],
                                "translated_audio": result["translated_audio"],
                                "your_language": target_lang
                            }
                        )
                
                # Send confirmation to sender
                await websocket.send_json({
                    "type": "processed",
                    "status": "sent",
                    "recipients": len(targets)
                })
            
            elif message_type == "text":
                # Handle text-only translation (for testing)
                text = data.get("text")
                
                # Get sender info
                sender = room.get_participant(user_id)
                if not sender:
                    continue
                
                print(f"📤 {sender.user_name} ({sender.language}): {text}")
                
                # Get translation targets
                targets = room.get_translation_targets(user_id)
                
                # Translate and send to each target
                for target_participant, source_lang, target_lang in targets:
                    result = await translation_pipeline.process_text(
                        text=text,
                        source_lang=source_lang,
                        target_lang=target_lang
                    )
                    
                    if result["status"] == "success":
                        print(f"📥 → {target_participant.user_name} ({target_lang}): {result['translated_text']}")
                        
                        # Send translation to specific user
                        await room_manager.send_to_user(
                            room_code=room_code,
                            user_id=target_participant.user_id,
                            message={
                                "type": "translation",
                                "sender": sender.user_name,
                                "sender_language": source_lang,
                                "original_text": text,
                                "translated_text": result["translated_text"],
                                "translated_audio": result["translated_audio"],
                                "your_language": target_lang
                            }
                        )
                
                # Send confirmation to sender
                await websocket.send_json({
                    "type": "sent",
                    "original_text": text,
                    "recipients": len(targets)
                })
            
            elif message_type == "ping":
                # Keep-alive ping
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        print(f"❌ User {user_id} disconnected from room {room_code}")
        
        # Get user info before removing
        participant = room.get_participant(user_id)
        user_name = participant.user_name if participant else "Unknown"
        
        # Remove participant
        room_manager.remove_participant(room_code, user_id)
        
        # Notify others
        if room_manager.get_room(room_code):  # Check if room still exists
            await room_manager.broadcast_to_room(
                room_code=room_code,
                message={
                    "type": "system",
                    "message": f"{user_name} left the conversation",
                    "participants": len(room.participants) if room else 0
                }
            )
    
    except Exception as e:
        print(f"❌ Error in WebSocket: {e}")
        await websocket.close(code=1011, reason=str(e))

@app.delete("/api/room/{room_code}")
async def close_room(room_code: str):
    """Close a conversation room"""
    
    room = room_manager.get_room(room_code)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Notify all participants
    await room_manager.broadcast_to_room(
        room_code=room_code,
        message={
            "type": "system",
            "message": "Room has been closed",
            "action": "disconnect"
        }
    )
    
    # Close room
    room_manager.close_room(room_code)
    
    return {"status": "Room closed", "room_code": room_code}

@app.get("/api/stats")
async def get_stats():
    """Get server statistics"""
    return room_manager.get_stats()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        ws_ping_interval=20,
        ws_ping_timeout=20
    )