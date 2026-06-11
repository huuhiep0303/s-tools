"""
FastAPI application entry point — equivalent of src/index.ts.
Initializes components, connects to DB, and sets up webhook endpoints.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

# Load environment variables if not already set (for local dev)
load_dotenv()

from app.components.ai_classifier import AIClassifier
from app.components.facebook_receiver import FacebookReceiver
from app.components.response_handler import ResponseHandler
from app.components.sheet_manager import SheetManager
from app.database.connection import connect_db, disconnect_db
from app.database.models import ensure_indexes, get_session, save_session
from app.utils.logger import logger

# Global component instances
classifier = AIClassifier()
receiver = FacebookReceiver()
handler = ResponseHandler()
sheet_manager = SheetManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: startup and shutdown."""
    logger.log_info("Main", "startup", "Starting Facebook AI Member Management System")
    
    # Initialize database
    await connect_db()
    await ensure_indexes()
    
    # Initialize SheetManager
    try:
        await sheet_manager.initialize()
        await sheet_manager.validate_and_create_sheets()
    except Exception as exc:
        logger.log_error("Main", "startup", "Failed to initialize SheetManager", {"error": exc})
        # We don't fail startup, but log it. Next request might fail or trigger re-init.
    
    yield
    
    # Shutdown
    logger.log_info("Main", "shutdown", "Shutting down system")
    await disconnect_db()


# Initialize FastAPI app
app = FastAPI(title="Facebook AI Member Management", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Webhook verification endpoint (Facebook sends GET request here to verify).
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    verify_token = os.getenv("FACEBOOK_VERIFY_TOKEN", "")
    
    if mode == "subscribe" and token == verify_token:
        logger.log_info("Main", "webhook-verify", "Webhook verified successfully")
        return Response(content=challenge, media_type="text/plain", status_code=200)
    
    logger.log_warn("Main", "webhook-verify", "Webhook verification failed", 
                    {"mode": mode, "token_provided": bool(token)})
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook handler for incoming messages from Facebook.
    Responds with 200 OK immediately and processes the message in the background.
    """
    # Verify signature
    signature = request.headers.get("x-hub-signature-256", "")
    body_bytes = await request.body()
    
    if not receiver.verify_signature(body_bytes, signature):
        logger.log_warn("Main", "webhook-handle", "Invalid signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse JSON
    import json
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    if body.get("object") != "page":
        return Response(status_code=404)
    
    # Extract message data
    message_data = receiver.extract_message_data(body)
    if message_data:
        # Enqueue background processing
        background_tasks.add_task(process_message, message_data)
        
    return Response(content="EVENT_RECEIVED", media_type="text/plain", status_code=200)


async def process_message(message_data: dict):
    """
    Main workflow for processing a message:
    1. Check session history.
    2. Classify with AI.
    3. Update session history.
    4. Handle business logic (leave, status update, etc.).
    5. Send response.
    """
    sender_id = message_data["senderId"]
    content = message_data["content"]
    timestamp = message_data["timestamp"]
    
    logger.log_info("Main", "process_message", "Starting message processing workflow", 
                    {"senderId": sender_id})
    
    try:
        # Load session history
        session = await get_session(sender_id)
        history = session.get("history", [])
        
        # We limit history to last 5 pairs (10 messages) to save tokens
        recent_history = history[-10:] if len(history) > 10 else history
        message_data["history"] = recent_history
        
        # Step 1: AI Classification
        logger.log_info("Main", "process_message", "→ Step 1: Starting AI classification", {"senderId": sender_id})
        classification = await classifier.classify(message_data)
        
        # Update history
        history.append({"role": "user", "content": content})
        # Assistant response will be added at the end depending on what is sent
        
        # Step 2: Manual Review check
        if classification.manual_review:
            logger.log_info("Main", "process_message", "→ Step 2: Routing to manual review", {"senderId": sender_id})
            # Send clarification
            assistant_reply = await handler.send_clarification_request(sender_id, {
                "category": classification.category,
                "date": classification.date,
                "date_range": classification.date_range,
                "reason": classification.reason
            })
            
            profile_name = await handler.get_user_profile_name(sender_id)
            # Notify admins
            await handler.send_admin_notification({
                "messageContent": content,
                "senderId": sender_id,
                "senderName": profile_name,
                "timestamp": timestamp
            })
            
            # Record in manual review sheet
            await sheet_manager.record_manual_review({
                "messageContent": content,
                "senderId": sender_id,
                "timestamp": timestamp,
                "confidence": classification.confidence,
                "reviewed": False,
                "manualClassification": classification.category
            })
            
            history.append({"role": "assistant", "content": assistant_reply})
            await save_session(sender_id, history)
            return

        # Step 3: Handle Greetings, FAQ & Ambiguous Stop
        if classification.category == "greeting":
            logger.log_info("Main", "process_message", "→ Step 3: Handling greeting", {"senderId": sender_id})
            assistant_reply = await handler.send_confirmation(sender_id, classification.category, {})
            history.append({"role": "assistant", "content": assistant_reply})
            await save_session(sender_id, history)
            return
            
        if classification.category == "bot_identity":
            logger.log_info("Main", "process_message", "→ Step 3: Handling FAQ (bot_identity)", {"senderId": sender_id})
            assistant_reply = await handler.send_confirmation(sender_id, classification.category, {})
            history.append({"role": "assistant", "content": assistant_reply})
            await save_session(sender_id, history)
            return
            
        if classification.category == "ambiguous_stop":
            logger.log_info("Main", "process_message", "→ Step 3: Handling ambiguous stop", {"senderId": sender_id})
            assistant_reply = await handler.send_clarification_request(sender_id, {"category": classification.category})
            history.append({"role": "assistant", "content": assistant_reply})
            await save_session(sender_id, history)
            return
            
        # Step 4: Handle Leave Requests
        if classification.category in ["training_leave", "meeting_leave"]:
            logger.log_info("Main", "process_message", "→ Step 4: Processing leave request", {"senderId": sender_id})
            
            # Check for missing info
            if not (classification.date or classification.date_range) or not classification.reason:
                assistant_reply = await handler.send_clarification_request(sender_id, {
                    "category": classification.category,
                    "date": classification.date,
                    "date_range": classification.date_range,
                    "reason": classification.reason
                })
                history.append({"role": "assistant", "content": assistant_reply})
                await save_session(sender_id, history)
                return
            
            # Format date for sheet
            date_str = ""
            if classification.date_range:
                date_str = f"{classification.date_range['start']} to {classification.date_range['end']}"
            elif classification.date:
                date_str = classification.date
                
            await sheet_manager.record_leave_request({
                "facebookId": sender_id,
                "requestType": classification.category,
                "date": date_str,
                "reason": classification.reason,
                "timestamp": timestamp
            })
            
            # Send confirmation
            assistant_reply = await handler.send_confirmation(sender_id, classification.category, {
                "date": date_str,
                "reason": classification.reason
            })
            
        # Step 5: Handle Status Updates
        elif classification.category in ["pause_membership", "quit_membership"]:
            logger.log_info("Main", "process_message", "→ Step 5: Processing status update", {"senderId": sender_id})
            
            # Check for missing info
            if classification.category == "pause_membership" and not classification.date and not classification.date_range:
                assistant_reply = await handler.send_clarification_request(sender_id, {"category": classification.category})
                history.append({"role": "assistant", "content": assistant_reply})
                await save_session(sender_id, history)
                return
                
            if not classification.reason:
                assistant_reply = await handler.send_clarification_request(sender_id, {"category": classification.category, "date": classification.date, "date_range": classification.date_range})
                history.append({"role": "assistant", "content": assistant_reply})
                await save_session(sender_id, history)
                return
            
            new_status = "paused" if classification.category == "pause_membership" else "inactive"
            
            try:
                await sheet_manager.update_member_status({
                    "facebookId": sender_id,
                    "newStatus": new_status
                })
                
                # Format date for reply
                date_str = ""
                if classification.date_range:
                    date_str = classification.date_range['start']
                elif classification.date:
                    date_str = classification.date
                    
                assistant_reply = await handler.send_confirmation(sender_id, classification.category, {
                    "date": date_str
                })
            except Exception as e:
                # E.g. member not found or invalid transition
                logger.log_error("Main", "process_message", "Failed to update status", {"error": e})
                assistant_reply = "Xin lỗi, đã có lỗi xảy ra khi cập nhật trạng thái của bạn. Ban nội bộ sẽ kiểm tra lại nhé."
                await handler.send_confirmation(sender_id, "error", {})
                # Record failure and save session, then return early
                await sheet_manager.record_history({
                    "timestamp": timestamp,
                    "facebookId": sender_id,
                    "requestType": classification.category,
                    "confidence": classification.confidence,
                    "status": "failed"
                })
                history.append({"role": "assistant", "content": assistant_reply})
                await save_session(sender_id, history)
                return
        
        else:
            assistant_reply = await handler.send_clarification_request(sender_id)
            
        # Step 6: Record history and update dashboard
        logger.log_info("Main", "process_message", "→ Step 6: Updating system records", {"senderId": sender_id})
        
        await sheet_manager.record_history({
            "timestamp": timestamp,
            "facebookId": sender_id,
            "requestType": classification.category,
            "confidence": classification.confidence,
            "status": "success"
        })
        
        await sheet_manager.update_dashboard()
        
        # Save session history
        history.append({"role": "assistant", "content": assistant_reply})
        await save_session(sender_id, history)
        
        logger.log_info("Main", "process_message", "Message processing workflow completed successfully", {"senderId": sender_id})
        
    except Exception as exc:
        logger.log_error("Main", "process_message", "Workflow failed", {"error": exc, "senderId": sender_id})
        await sheet_manager.record_history({
            "timestamp": timestamp,
            "facebookId": sender_id,
            "requestType": "unclassified",
            "confidence": 0.0,
            "status": "failed"
        })
