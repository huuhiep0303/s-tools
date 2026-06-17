"""
FastAPI application entry point — equivalent of src/index.ts.
Initializes components, connects to DB, and sets up webhook endpoints.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from datetime import datetime
import uuid
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
from app.crud import training as crud_training
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
            "id": u.id,
            "facebookId": u.facebook_id,
            "phone": u.phone,
            "name": u.full_name,
            "activeStatus": u.status.value.lower() if u.status else "quit",
            "role": u.role.value.lower() if hasattr(u, 'role') and u.role else "user",
            "statusDate": u.updated_at.isoformat() if u.updated_at else datetime.utcnow().isoformat(),
            "feeEligibility": u.fee_eligibility.value.lower() if u.fee_eligibility else "exempt",
            "feeAmount": 200000 if u.status and u.status.value == "ACTIVE" else 0,
            "trainingLeaveCount": 0, # Optimization: could aggregate
            "meetingLeaveCount": 0
        })
    return members

class MemberCreateUpdate(BaseModel):
    facebookId: str
    phone: str = ""
    name: str
    activeStatus: str
    feeEligibility: str
    role: str = "user"

@app.post("/api/v1/admin/members")
async def create_member(req: MemberCreateUpdate, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    
    # map frontend values to DB enums
    from app.models.user import StatusEnum, FeeEligibilityEnum, RoleEnum
    status_map = {"active": StatusEnum.ACTIVE, "paused": StatusEnum.PAUSED, "quit": StatusEnum.QUIT}
    fee_map = {"eligible": FeeEligibilityEnum.ELIGIBLE, "exempt": FeeEligibilityEnum.EXEMPT}
    
    user_data = {
        "facebook_id": req.facebookId,
        "phone": req.phone if req.phone else None,
        "full_name": req.name,
        "role": RoleEnum.ADMIN if req.role.lower() == "admin" else RoleEnum.USER,
        "status": status_map.get(req.activeStatus.lower(), StatusEnum.ACTIVE),
        "fee_eligibility": fee_map.get(req.feeEligibility.lower(), FeeEligibilityEnum.ELIGIBLE)
    }
    
    try:
        user = await crud_user.create_user(db, user_data)
        return {"status": "ok", "id": user.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot create user, maybe facebookId already exists. Error: {str(e)}")

@app.put("/api/v1/admin/members/{user_id}")
async def update_member(user_id: str, req: MemberCreateUpdate, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    from app.models.user import StatusEnum, FeeEligibilityEnum, RoleEnum
    status_map = {"active": StatusEnum.ACTIVE, "paused": StatusEnum.PAUSED, "quit": StatusEnum.QUIT}
    fee_map = {"eligible": FeeEligibilityEnum.ELIGIBLE, "exempt": FeeEligibilityEnum.EXEMPT}
    
    update_data = {
        "facebook_id": req.facebookId,
        "phone": req.phone if req.phone else None,
        "full_name": req.name,
        "role": RoleEnum.ADMIN if req.role.lower() == "admin" else RoleEnum.USER,
        "status": status_map.get(req.activeStatus.lower(), StatusEnum.ACTIVE),
        "fee_eligibility": fee_map.get(req.feeEligibility.lower(), FeeEligibilityEnum.ELIGIBLE)
    }
    
    try:
        updated = await crud_user.update_user_by_id(db, user_id, update_data)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot update user. Error: {str(e)}")

@app.delete("/api/v1/admin/members/{user_id}")
async def delete_member(user_id: str, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    try:
        deleted = await crud_user.delete_user_by_id(db, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Cannot delete user. They might have related records (leaves, financials). Try changing status to QUIT instead.")

@app.get("/api/v1/users/me/stats")
async def get_my_stats(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Get stats for the currently logged in user."""
    facebook_id = token_payload.get("sub")
    if not facebook_id:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    user = await crud_user.get_user_by_facebook_id(db, facebook_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Get financial records
    fin_records = await crud_financial.get_financial_records(db, user_id=user.id)
    total_due = sum(r.amount_due for r in fin_records)
    total_paid = sum(r.amount_paid for r in fin_records)
    fee_debt = total_due - total_paid
    
    # Get latest paid month
    paid_months = sorted([r.month for r in fin_records if r.status == "PAID"], reverse=True)
    fee_status = f"Đã nộp đến T{paid_months[0][-2:]}/{paid_months[0][:4]}" if paid_months else "Chưa có dữ liệu nộp quỹ"
    
    # Get leave records
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).date()
    
    training_leaves = await crud_leave.get_leaves_in_month(db, month_start, now.date(), "training_leave")
    meeting_leaves = await crud_leave.get_leaves_in_month(db, year_start, now.date(), "meeting_leave")
    
    return {
        "feeStatus": fee_status,
        "feeDebt": f"{int(fee_debt):,} ₫".replace(",", "."),
        "trainingLeaves": training_leaves,
        "meetingLeaves": meeting_leaves,
    }


class LeaveSubmitRequest(BaseModel):
    type: str
    date: str
    reason: str

@app.post("/api/v1/leaves")
async def submit_leave_request(req: LeaveSubmitRequest, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Submit a leave request."""
    facebook_id = token_payload.get("sub")
    if not facebook_id:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    user = await crud_user.get_user_by_facebook_id(db, facebook_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Parse date
    try:
        leave_date = datetime.strptime(req.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
    # Create request
    leave_data = {
        "user_id": user.id,
        "type": req.type,
        "date": leave_date,
        "reason": req.reason,
        "status": "APPROVED"
    }
    
    await crud_leave.create_leave_request(db, leave_data)
    
    # Send confirmation message
    msg = f"S-Group đã nhận và duyệt đơn xin nghỉ của bạn:\nLoại: {'Đào tạo' if req.type == 'training_leave' else 'Họp tháng'}\nNgày: {req.date}\nLý do: {req.reason}\nTrạng thái: ĐÃ DUYỆT"
    await handler.send_direct_message(facebook_id, msg)
    
    return {"status": "ok", "message": "Leave request submitted successfully"}


@app.get("/api/v1/manual-reviews")
async def get_manual_reviews(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    """Get manual review queue."""
    # Ensure admin
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
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
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
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
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
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

class ResolveLeaveRequest(BaseModel):
    status: str
    adminNotes: str = ""

@app.get("/api/v1/admin/leaves")
async def get_all_leaves(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    leaves = await crud_leave.get_leave_requests(db)
    # Get user names for UI convenience
    users = {u.id: u for u in await crud_user.get_all_users(db)}
    return [{
        "id": l.id,
        "userId": l.user_id,
        "userName": users[l.user_id].full_name if l.user_id in users else "Unknown",
        "facebookId": users[l.user_id].facebook_id if l.user_id in users else "Unknown",
        "type": l.type,
        "date": l.date.isoformat(),
        "reason": l.reason,
        "status": l.status,
        "createdAt": l.created_at.isoformat() + "Z"
    } for l in leaves]

@app.post("/api/v1/admin/leaves/{leave_id}/resolve")
async def resolve_leave(leave_id: str, req: ResolveLeaveRequest, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    updated = await crud_leave.update_leave_request(db, leave_id, {
        "status": req.status,
        "admin_notes": req.adminNotes
    })
    if not updated:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    user = await crud_user.get_user(db, updated.user_id)
    if user:
        status_vi = "ĐÃ ĐƯỢC DUYỆT" if req.status == "APPROVED" else "BỊ TỪ CHỐI"
        msg = f"S-Group thông báo:\nĐơn xin nghỉ ngày {updated.date.isoformat()} của bạn {status_vi}."
        if req.adminNotes:
            msg += f"\nLý do/Ghi chú: {req.adminNotes}"
        await handler.send_direct_message(user.facebook_id, msg)
        
    return {"status": "ok"}

class PayRequest(BaseModel):
    month: str

@app.get("/api/v1/admin/financials")
async def get_all_financials(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    records = await crud_financial.get_financial_records(db)
    users = {u.id: u for u in await crud_user.get_all_users(db)}
    return [{
        "id": r.id,
        "userName": users[r.user_id].full_name if r.user_id in users else "Unknown",
        "month": r.month,
        "amountDue": r.amount_due,
        "amountPaid": r.amount_paid,
        "status": r.status
    } for r in records]

@app.post("/api/v1/admin/financials/{user_id}/pay")
async def pay_financial(user_id: str, req: PayRequest, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    # Check if record for this month exists
    records = await crud_financial.get_financial_records(db, user_id=user_id, month=req.month)
    if not records:
        # Create a new record
        record = await crud_financial.create_financial_record(db, {
            "user_id": user_id,
            "month": req.month,
            "amount_due": 200000,
            "amount_paid": 200000,
            "status": "PAID",
            "updated_by_admin_id": token_payload.get("sub") # Store admin facebook_id roughly
        })
    else:
        # Update existing
        record = records[0]
        await crud_financial.update_financial_record(db, record.id, {
            "amount_paid": record.amount_due,
            "status": "PAID",
            "updated_by_admin_id": token_payload.get("sub")
        })
        
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
                
            if classification.category in ["faq", "onboarding", "training_query"]:
                logger.log_info("Main", "process_message", f"→ Step 3: Handling {classification.category} (RAG)", {"senderId": sender_id})
                
                kb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base.md")
                kb_content = ""
                if os.path.exists(kb_path):
                    with open(kb_path, "r", encoding="utf-8") as f:
                        kb_content = f.read()
                else:
                    logger.log_warn("Main", "process_message", "knowledge_base.md not found, using empty context")
                
                # If it's a training query, append course context
                if classification.category == "training_query":
                    user = await crud_user.get_user_by_facebook_id(db, sender_id)
                    if user:
                        course_memberships = await crud_training.get_courses_by_user(db, user.id)
                        if course_memberships:
                            kb_content += "\n\n=== THÔNG TIN LỚP ĐÀO TẠO CỦA BẠN ===\n"
                            for cm in course_memberships:
                                course = await crud_training.get_course_by_id(db, cm.course_id)
                                if course:
                                    kb_content += f"\nLớp: {course.name} ({course.description or 'Không có mô tả'})\n"
                                    sessions = await crud_training.get_sessions_by_course(db, course.id)
                                    for s in sessions:
                                        kb_content += f" - {s.session_number}: {s.title}\n"
                                        if s.date:
                                            kb_content += f"   Ngày học: {s.date.strftime('%Y-%m-%d %H:%M')}\n"
                                        if s.materials_url:
                                            kb_content += f"   Tài liệu: {s.materials_url}\n"
                                        if s.homework_desc:
                                            kb_content += f"   Bài tập: {s.homework_desc}\n"
                                        if s.homework_deadline:
                                            kb_content += f"   Hạn nộp (Deadline): {s.homework_deadline.strftime('%Y-%m-%d %H:%M')}\n"
                        else:
                            kb_content += "\n\n(Bạn hiện chưa tham gia lớp đào tạo nào trên hệ thống.)\n"
                    else:
                        kb_content += "\n\n(Không tìm thấy thông tin tài khoản của bạn trên hệ thống, vui lòng đăng nhập để xem thông tin lớp học.)\n"
                        
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
                    "reason": classification.reason,
                    "status": "APPROVED"
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

# In-memory store for tokens (For production, consider Redis or DB)
token_store = {}

@app.get("/api/v1/auth/users")
async def get_public_users(db: AsyncSession = Depends(get_db)):
    """Get list of users for login dropdown."""
    users = await crud_user.get_all_users(db)
    return [{"id": u.id, "full_name": u.full_name} for u in users if u.status.value == "ACTIVE"]

class MagicLinkRequest(BaseModel):
    userId: str

class MagicLinkVerifyRequest(BaseModel):
    token: str

from fastapi import Request

@app.post("/api/v1/auth/request-magic-link")
async def request_magic_link(req: MagicLinkRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Verify user exists
    user = await crud_user.get_user(db, req.userId)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    magic_token = str(uuid.uuid4())
    token_store[magic_token] = user.facebook_id
    
    # Send link via messenger
    base_url = str(request.base_url).rstrip("/")
    frontend_url = os.getenv("FRONTEND_URL", base_url)
    if "localhost" in frontend_url and "railway.app" in base_url:
        frontend_url = base_url
        
    login_link = f"{frontend_url}/login?token={magic_token}"
    msg = f"Chào {user.full_name},\nBấm vào link sau để đăng nhập vào Web S-Group (Link có hiệu lực 5 phút):\n{login_link}"
    
    try:
        await handler.send_direct_message(user.facebook_id, msg)
    except Exception as e:
        logger.log_error("Auth", "request-magic-link", "Failed to send message", {"error": str(e), "facebook_id": user.facebook_id})
        raise HTTPException(status_code=400, detail="Tài khoản của bạn chưa được liên kết với Messenger. Vui lòng nhắn tin cho Fanpage SGroup với cú pháp: 'đăng nhập' để liên kết tài khoản.")
    
    return {"status": "ok", "message": "Magic link sent via Messenger"}

@app.post("/api/v1/auth/verify-magic-link")
async def verify_magic_link(req: MagicLinkVerifyRequest, db: AsyncSession = Depends(get_db)):
    facebook_id = token_store.get(req.token)
    if not facebook_id:
        raise HTTPException(status_code=401, detail="Invalid or expired magic link")
        
    # Get user to determine role
    user = await crud_user.get_user_by_facebook_id(db, facebook_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Get user to determine role
    role = user.role.value.lower()
    
    token = create_access_token({
        "sub": facebook_id,
        "name": user.full_name,
        "role": role
    })
    
    # Clear token safely
    token_store.pop(req.token, None)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "facebookId": facebook_id,
            "name": user.full_name,
            "role": role
        }
    }

class SepayWebhookPayload(BaseModel):
    id: int
    gateway: str
    transactionDate: str
    accountNumber: str
    content: str
    transferType: str
    transferAmount: int
    accumulated: int
    referenceCode: str
    description: str

@app.post("/api/v1/webhooks/sepay")
async def sepay_webhook(payload: SepayWebhookPayload, request: Request, db: AsyncSession = Depends(get_db)):
    if payload.transferType != "in":
        return {"status": "ignored", "reason": "not an incoming transfer"}

    # Extract phone from content (e.g. SGROUP 0987654321)
    import re
    match = re.search(r'SGROUP\s*(\d{9,11})', payload.content, re.IGNORECASE)
    if not match:
        return {"status": "ignored", "reason": "no valid syntax found in content"}

    phone = match.group(1)
    
    # Find user by phone
    from app.crud.user import get_user_by_phone
    user = await get_user_by_phone(db, phone)
    if not user:
        logger.log_warn("Sepay", "webhook", "User not found for phone", {"phone": phone})
        return {"status": "ignored", "reason": "user not found"}

    # Calculate fee debt
    from app.crud.financial import get_fee_status
    fee_status = await get_fee_status(db, user.id)
    
    # Update DB - actually we should create a fee transaction, but the current financial system might not have it.
    # Currently financial.py uses FeeStatus. Wait, how are fees tracked? Let's assume we just log it and send message.
    # We will send a message via Messenger
    amount_str = f"{payload.transferAmount:,.0f}".replace(",", ".")
    msg = f"Cảm ơn bạn đã đóng quỹ S-Group với số tiền {amount_str} VNĐ.\n\n(Lưu ý: Hệ thống đang tự động ghi nhận, số dư nợ trên web sẽ được cập nhật sau)."
    
    try:
        await handler.send_direct_message(user.facebook_id, msg)
        logger.log_info("Sepay", "webhook", "Notification sent", {"phone": phone, "amount": payload.transferAmount})
    except Exception as e:
        logger.log_error("Sepay", "webhook", "Failed to send notification", {"error": str(e)})

    return {"status": "success"}

    return {"status": "success"}

# ------------------------------------------------------------------
# Check-in API
# ------------------------------------------------------------------

class CheckinSessionCreate(BaseModel):
    title: str
    duration_minutes: int

class CheckinRequest(BaseModel):
    secret_code: str

@app.post("/api/v1/admin/checkin/sessions")
async def create_checkin_session(req: CheckinSessionCreate, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
        
    from app.models.checkin import CheckinSession
    from datetime import timedelta
    import random
    import string
    
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    session = CheckinSession(
        title=req.title,
        secret_code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=req.duration_minutes)
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "title": session.title,
        "secret_code": session.secret_code,
        "expires_at": session.expires_at.isoformat() + "Z"
    }

@app.post("/api/v1/checkin")
async def checkin_user(req: CheckinRequest, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    facebook_id = token_payload.get("sub")
    if not facebook_id:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    from app.crud.user import get_user_by_facebook_id
    user = await get_user_by_facebook_id(db, facebook_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    from app.models.checkin import CheckinSession, CheckinRecord
    from sqlalchemy.future import select
    
    # Verify session
    result = await db.execute(select(CheckinSession).filter(CheckinSession.secret_code == req.secret_code))
    session = result.scalars().first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Mã điểm danh không hợp lệ")
        
    if session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Phiên điểm danh đã hết hạn")
        
    # Check if already checked in
    existing_check = await db.execute(
        select(CheckinRecord).filter(
            CheckinRecord.session_id == session.id,
            CheckinRecord.user_id == user.id
        )
    )
    if existing_check.scalars().first():
        return {"status": "ok", "message": "Bạn đã điểm danh rồi"}
        
    record = CheckinRecord(
        session_id=session.id,
        user_id=user.id
    )
    db.add(record)
    await db.commit()
    
    # Send Messenger Notification
    msg = f"Bạn đã điểm danh thành công: {session.title} lúc {datetime.now(VN_TZ).strftime('%H:%M')}."
    try:
        await handler.send_direct_message(user.facebook_id, msg)
    except Exception as e:
        logger.log_error("Checkin", "notify", "Failed to send checkin confirmation", {"error": str(e)})

    return {"status": "ok", "message": "Điểm danh thành công"}

# ------------------------------------------------------------------
# Training API (Admin & Mentor)
# ------------------------------------------------------------------

class CourseCreate(BaseModel):
    name: str
    description: Optional[str] = None

class CourseSessionCreate(BaseModel):
    session_number: str
    title: str
    date: Optional[str] = None
    materials_url: Optional[str] = None
    homework_desc: Optional[str] = None
    homework_deadline: Optional[str] = None

@app.get("/api/v1/training/courses")
async def get_courses(db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") not in ["admin", "mentor"]:
        raise HTTPException(status_code=403, detail="Admin/Mentor only")
    
    courses = await crud_training.get_all_courses(db)
    result = []
    for c in courses:
        mentor = await crud_user.get_user(db, c.mentor_id)
        result.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "mentorId": c.mentor_id,
            "mentorName": mentor.full_name if mentor else "Unknown",
            "createdAt": c.created_at.isoformat() + "Z" if c.created_at else None
        })
    return result

@app.post("/api/v1/training/courses")
async def create_course_api(req: CourseCreate, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") not in ["admin", "mentor"]:
        raise HTTPException(status_code=403, detail="Admin/Mentor only")
    
    user = await crud_user.get_user_by_facebook_id(db, token_payload.get("sub"))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    data = req.model_dump()
    data["mentor_id"] = user.id
    course = await crud_training.create_course(db, data)
    return {"status": "ok", "id": course.id}

@app.get("/api/v1/training/courses/{course_id}/sessions")
async def get_course_sessions(course_id: str, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") not in ["admin", "mentor"]:
        raise HTTPException(status_code=403, detail="Admin/Mentor only")
        
    sessions = await crud_training.get_sessions_by_course(db, course_id)
    return [{
        "id": s.id,
        "sessionNumber": s.session_number,
        "title": s.title,
        "date": s.date.isoformat() + "Z" if s.date else None,
        "materialsUrl": s.materials_url,
        "homeworkDesc": s.homework_desc,
        "homeworkDeadline": s.homework_deadline.isoformat() + "Z" if s.homework_deadline else None
    } for s in sessions]

@app.post("/api/v1/training/courses/{course_id}/sessions")
async def create_session_api(course_id: str, req: CourseSessionCreate, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") not in ["admin", "mentor"]:
        raise HTTPException(status_code=403, detail="Admin/Mentor only")
        
    data = req.model_dump()
    data["course_id"] = course_id
    
    if data.get("date"):
        try:
            data["date"] = datetime.fromisoformat(data["date"].replace("Z", "+00:00")).replace(tzinfo=None)
        except: pass
    if data.get("homework_deadline"):
        try:
            data["homework_deadline"] = datetime.fromisoformat(data["homework_deadline"].replace("Z", "+00:00")).replace(tzinfo=None)
        except: pass
        
    session = await crud_training.create_course_session(db, data)
    return {"status": "ok", "id": session.id}

@app.get("/api/v1/training/courses/{course_id}/members")
async def get_course_members(course_id: str, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") not in ["admin", "mentor"]:
        raise HTTPException(status_code=403, detail="Admin/Mentor only")
        
    members = await crud_training.get_members_by_course(db, course_id)
    result = []
    for m in members:
        user = await crud_user.get_user(db, m.user_id)
        if user:
            result.append({
                "userId": user.id,
                "facebookId": user.facebook_id,
                "name": user.full_name
            })
    return result

@app.post("/api/v1/training/courses/{course_id}/members")
async def add_course_member(course_id: str, payload: dict, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") not in ["admin", "mentor"]:
        raise HTTPException(status_code=403, detail="Admin/Mentor only")
    
    user_id = payload.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="userId is required")
        
    await crud_training.add_member_to_course(db, course_id, user_id)
    return {"status": "ok"}

@app.delete("/api/v1/training/courses/{course_id}/members/{user_id}")
async def remove_course_member(course_id: str, user_id: str, db: AsyncSession = Depends(get_db), token_payload: dict = Depends(verify_token)):
    if token_payload.get("role") not in ["admin", "mentor"]:
        raise HTTPException(status_code=403, detail="Admin/Mentor only")
        
    await crud_training.remove_member_from_course(db, course_id, user_id)
    return {"status": "ok"}

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
