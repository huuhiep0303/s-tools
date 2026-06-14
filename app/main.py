"""
FastAPI application entry point — equivalent of src/index.ts.
Initializes components, connects to DB, and sets up webhook endpoints.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from datetime import datetime
from pydantic import BaseModel
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load environment variables if not already set (for local dev)
load_dotenv()

from app.components.ai_classifier import AIClassifier
from app.components.facebook_receiver import FacebookReceiver
from app.components.response_handler import ResponseHandler
from app.components.sheet_manager import SheetManager
from app.database.connection import connect_db, disconnect_db
from app.database.models import ensure_indexes, get_session, save_session
from app.jobs.scheduler import JobScheduler
from app.utils.logger import logger

from app.db import get_db, AsyncSessionLocal
from app.crud import user as crud_user
from app.crud import bot as crud_bot
from app.crud import leave as crud_leave
from app.crud import financial as crud_financial
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.auth import verify_token

# Global component instances
classifier = AIClassifier()
receiver = FacebookReceiver()
handler = ResponseHandler()
sheet_manager = SheetManager()
scheduler = JobScheduler(sheet_manager, handler)


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
        
    scheduler.start()
    
    yield
    
    # Shutdown
    logger.log_info("Main", "shutdown", "Shutting down system")
    scheduler.stop()
    await disconnect_db()


# Initialize FastAPI app
app = FastAPI(title="Facebook AI Member Management", lifespan=lifespan)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ------------------------------------------------------------------
# Admin Dashboard API Endpoints
# ------------------------------------------------------------------

@app.get("/api/v1/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Get dashboard statistics."""
    # Compute stats from PostgreSQL
    active = await crud_user.count_users_by_status(db, "ACTIVE")
    paused = await crud_user.count_users_by_status(db, "PAUSED")
    quit_c = await crud_user.count_users_by_status(db, "QUIT")
    revenue = active * 200000
    
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
    training = await crud_leave.get_leaves_in_month(db, month_start, now.date(), "training_leave")
    meeting = await crud_leave.get_leaves_in_month(db, month_start, now.date(), "meeting_leave")
    
    return {
        "activeMembers": active,
        "pausedMembers": paused,
        "quitMembers": quit_c,
        "monthlyRevenue": revenue,
        "trainingLeaveCount": training,
        "meetingLeaveCount": meeting,
        "lastUpdated": now.isoformat() + "Z"
    }

@app.get("/api/v1/members")
async def get_members(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Get all members."""
    users = await crud_user.get_all_users(db)
    members = []
    for u in users:
        # Get leave counts roughly, or just omit if not strict
        members.append({
            "facebookId": u.facebook_id,
            "name": u.full_name,
            "activeStatus": u.status.value.lower(),
            "statusDate": u.updated_at.isoformat(),
            "feeEligibility": u.fee_eligibility.value.lower(),
            "feeAmount": 200000 if u.status.value == "ACTIVE" else 0,
            "trainingLeaveCount": 0, # Optimization: could aggregate
            "meetingLeaveCount": 0
        })
    return members

@app.get("/api/v1/manual-reviews")
async def get_manual_reviews(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Get manual review queue."""
    reviews = await crud_bot.get_manual_reviews(db)
    return [{
        "recordId": r.id,
        "messageContent": r.message_content,
        "senderId": r.sender_id,
        "senderName": r.sender_name,
        "timestamp": r.created_at.isoformat() + "Z",
        "confidence": r.confidence,
        "reviewed": r.reviewed,
        "manualClassification": r.manual_classification
    } for r in reviews]

@app.get("/api/v1/history")
async def get_history(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Get recent request history."""
    history = await crud_bot.get_bot_history(db)
    return [{
        "recordId": h.id,
        "timestamp": h.created_at.isoformat() + "Z",
        "facebookId": h.facebook_id,
        "requestType": h.request_type,
        "confidence": h.confidence,
        "status": h.status
    } for h in history]

class ResolveReviewRequest(BaseModel):
    finalCategory: str

@app.post("/api/v1/manual-reviews/{record_id}/resolve")
async def resolve_manual_review(record_id: str, req: ResolveReviewRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Resolve a manual review and send confirmation."""
    try:
        updated_review = await crud_bot.resolve_manual_review(db, record_id, req.finalCategory)
        if not updated_review:
            raise HTTPException(status_code=404, detail="Review not found")
            
        await crud_bot.create_bot_history(db, {
            "facebook_id": updated_review.sender_id,
            "request_type": req.finalCategory,
            "confidence": 1.0,
            "status": "success"
        })
        
        # Background sync to Sheet
        background_tasks.add_task(sheet_manager.resolve_manual_review, record_id, req.finalCategory)
        background_tasks.add_task(sheet_manager.record_history, {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "facebookId": updated_review.sender_id,
            "requestType": req.finalCategory,
            "confidence": 1.0,
            "status": "success"
        })
        
        msg = handler._format_confirmation(req.finalCategory, {})
        await handler.send_direct_message(updated_review.sender_id, msg)
        
        return {"status": "ok"}
    except Exception as exc:
        logger.log_error("Main", "resolve_manual_review", "Error", {"error": exc})
        raise HTTPException(status_code=500, detail=str(exc))



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
    
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
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
                
                # Record in DB and sheet
                await crud_bot.create_manual_review(db, {
                    "message_content": content,
                    "sender_id": sender_id,
                    "sender_name": profile_name,
                    "confidence": classification.confidence,
                    "reviewed": False,
                    "manual_classification": classification.category
                })
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
    
            if classification.category == "greeting":
                logger.log_info("Main", "process_message", "→ Step 3: Handling greeting", {"senderId": sender_id})
                assistant_reply = await handler.send_confirmation(sender_id, classification.category, {})
                history.append({"role": "assistant", "content": assistant_reply})
                await save_session(sender_id, history)
                return
                
            if classification.category == "thanks":
                logger.log_info("Main", "process_message", "→ Step 3: Handling thanks", {"senderId": sender_id})
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
                
            if classification.category in ["faq", "onboarding"]:
                logger.log_info("Main", "process_message", "→ Step 3: Handling FAQ/Onboarding (RAG)", {"senderId": sender_id})
                
                kb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base.md")
                kb_content = ""
                if os.path.exists(kb_path):
                    with open(kb_path, "r", encoding="utf-8") as f:
                        kb_content = f.read()
                else:
                    logger.log_warn("Main", "process_message", "knowledge_base.md not found, using empty context")
                        
                assistant_reply = await classifier.answer_faq(content, kb_content, recent_history)
                await handler.send_direct_message(sender_id, assistant_reply)
                
                history.append({"role": "assistant", "content": assistant_reply})
                await save_session(sender_id, history)
                
                await crud_bot.create_bot_history(db, {
                    "facebook_id": sender_id,
                    "request_type": classification.category,
                    "confidence": classification.confidence,
                    "status": "success"
                })
                await sheet_manager.record_history({
                    "timestamp": timestamp,
                    "facebookId": sender_id,
                    "requestType": classification.category,
                    "confidence": classification.confidence,
                    "status": "success"
                })
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
                    
                user = await crud_user.get_user_by_facebook_id(db, sender_id)
                if not user:
                    user = await crud_user.create_user(db, {"facebook_id": sender_id, "full_name": "Unknown"})
                from app.models.leave import LeaveTypeEnum
                from datetime import date
                l_type = LeaveTypeEnum.TRAINING if classification.category == "training_leave" else LeaveTypeEnum.MONTHLY_MEETING
                await crud_leave.create_leave_request(db, {
                    "user_id": user.id,
                    "type": l_type,
                    "date": date.today(),
                    "reason": classification.reason
                })
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
                    db_status = "PAUSED" if new_status == "paused" else "QUIT"
                    await crud_user.update_user(db, sender_id, {"status": db_status})
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
                    await crud_bot.create_bot_history(db, {
                        "facebook_id": sender_id,
                        "request_type": classification.category,
                        "confidence": classification.confidence,
                        "status": "failed"
                    })
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
            
            await crud_bot.create_bot_history(db, {
                "facebook_id": sender_id,
                "request_type": classification.category,
                "confidence": classification.confidence,
                "status": "success"
            })
            await sheet_manager.record_history({
                "timestamp": timestamp,
                "facebookId": sender_id,
                "requestType": classification.category,
                "confidence": classification.confidence,
                "status": "success"
            })
            
            # Save session history
            history.append({"role": "assistant", "content": assistant_reply})
            await save_session(sender_id, history)
            
            logger.log_info("Main", "process_message", "Message processing workflow completed successfully", {"senderId": sender_id})
            
        except Exception as exc:
            logger.log_error("Main", "process_message", "Workflow failed", {"error": exc, "senderId": sender_id})
            await crud_bot.create_bot_history(db, {
                "facebook_id": sender_id,
                "request_type": "unclassified",
                "confidence": 0.0,
                "status": "failed"
            })
            await sheet_manager.record_history({
                "timestamp": timestamp,
                "facebookId": sender_id,
                "requestType": "unclassified",
                "confidence": 0.0,
                "status": "failed"
            })

# ------------------------------------------------------------------
# Auth Endpoints
# ------------------------------------------------------------------
import random
from app.auth import create_access_token

# In-memory store for OTPs (For production, consider Redis or DB)
otp_store = {}

class OTPRequest(BaseModel):
    facebookId: str

class OTPVerifyRequest(BaseModel):
    facebookId: str
    otp: str

@app.post("/api/v1/auth/request-otp")
async def request_otp(req: OTPRequest, db: AsyncSession = Depends(get_db)):
    # Verify user exists
    user = await crud_user.get_user_by_facebook_id(db, req.facebookId)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    otp = str(random.randint(100000, 999999))
    otp_store[req.facebookId] = otp
    
    # In a real scenario, you send this OTP via messenger
    msg = f"Mã xác thực (OTP) để đăng nhập S-Group Platform của bạn là: {otp}\nVui lòng không chia sẻ mã này cho bất kỳ ai."
    await handler.send_direct_message(req.facebookId, msg)
    
    # Also log it for debugging
    logger.log_info("Auth", "request-otp", f"OTP generated for {req.facebookId}: {otp}")
    
    return {"status": "ok", "message": "OTP sent via Messenger"}

@app.post("/api/v1/auth/verify-otp")
async def verify_otp(req: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    saved_otp = otp_store.get(req.facebookId)
    if not saved_otp or saved_otp != req.otp:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
        
    # Get user to determine role
    user = await crud_user.get_user_by_facebook_id(db, req.facebookId)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # For now, admin if facebook_id in ADMIN_FACEBOOK_IDS env (or just assign user role)
    admin_ids = os.getenv("ADMIN_FACEBOOK_IDS", "").split(",")
    role = "admin" if req.facebookId in admin_ids else "user"
    
    token = create_access_token({
        "sub": req.facebookId,
        "name": user.full_name,
        "role": role
    })
    
    # Clear OTP
    del otp_store[req.facebookId]
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "facebookId": req.facebookId,
            "name": user.full_name,
            "role": role
        }
    }

# ------------------------------------------------------------------
# Static Files & React Router Catch-All
# ------------------------------------------------------------------

# Serve static assets (JS, CSS, images) from frontend/dist/assets
if os.path.exists("frontend/dist/assets"):
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

# Serve specific root files like vite.svg or favicon.ico if they exist
if os.path.exists("frontend/dist"):
    @app.get("/{filename:path}")
    async def serve_root_files(filename: str):
        file_path = os.path.join("frontend/dist", filename)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # If it's not a file (e.g. a React route like /dashboard), return index.html
        return FileResponse("frontend/dist/index.html")
    
    # Catch-all for React Router on root
    @app.get("/")
    async def serve_index():
        return FileResponse("frontend/dist/index.html")
