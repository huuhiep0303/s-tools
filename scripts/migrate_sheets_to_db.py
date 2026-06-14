import asyncio
import os
import sys
from datetime import datetime

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from app.db import AsyncSessionLocal
from app.components.sheet_manager import SheetManager
from app.models import User, FinancialRecord, LeaveRequest, BotHistory, ManualReview, RoleEnum, StatusEnum, FeeEligibilityEnum, PaymentStatusEnum, LeaveTypeEnum, LeaveStatusEnum

async def migrate_users(sheet_manager: SheetManager, db):
    members = await sheet_manager.get_members()
    print(f"Migrating {len(members)} users...")
    
    for m in members:
        fb_id = m.get("facebookId")
        if not fb_id:
            continue
            
        status_str = m.get("activeStatus", "").lower()
        if "active" in status_str:
            status = StatusEnum.ACTIVE
        elif "pause" in status_str:
            status = StatusEnum.PAUSED
        else:
            status = StatusEnum.QUIT
            
        fee_str = m.get("feeEligibility", "").lower()
        fee_eligibility = FeeEligibilityEnum.ELIGIBLE if "eligible" in fee_str else FeeEligibilityEnum.EXEMPT
        
        user = User(
            facebook_id=fb_id,
            full_name=m.get("name", "Unknown"),
            role=RoleEnum.USER, # Default to USER
            status=status,
            fee_eligibility=fee_eligibility
        )
        db.add(user)
    
    await db.commit()
    print("Users migrated successfully.")

async def migrate_history(sheet_manager: SheetManager, db):
    requests = await sheet_manager.get_recent_requests()
    print(f"Migrating {len(requests)} bot history records...")
    
    for r in requests:
        try:
            created_at = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None)
        except:
            created_at = datetime.utcnow()
            
        history = BotHistory(
            id=r.get("recordId") or None,
            facebook_id=r.get("facebookId", ""),
            request_type=r.get("requestType", ""),
            confidence=float(r.get("confidence", 0)),
            status=r.get("status", ""),
            created_at=created_at
        )
        db.add(history)
        
    await db.commit()
    print("Bot history migrated successfully.")

async def migrate_manual_reviews(sheet_manager: SheetManager, db):
    reviews = await sheet_manager.get_manual_reviews()
    print(f"Migrating {len(reviews)} manual reviews...")
    
    for r in reviews:
        try:
            created_at = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None)
        except:
            created_at = datetime.utcnow()
            
        review = ManualReview(
            id=r.get("recordId") or None,
            sender_id=r.get("senderId", ""),
            sender_name=r.get("senderName", ""),
            message_content=r.get("messageContent", ""),
            confidence=float(r.get("confidence", 0)),
            reviewed=r.get("reviewed", False),
            manual_classification=r.get("manualClassification", ""),
            created_at=created_at
        )
        db.add(review)
        
    await db.commit()
    print("Manual reviews migrated successfully.")

async def main():
    print("Starting migration from Google Sheets to PostgreSQL/SQLite...")
    
    # Init Sheet Manager
    sheet_manager = SheetManager()
    await sheet_manager.initialize()
    
    async with AsyncSessionLocal() as db:
        await migrate_users(sheet_manager, db)
        await migrate_history(sheet_manager, db)
        await migrate_manual_reviews(sheet_manager, db)
        # We can also migrate leaves here by reading the Leaves sheet, but currently get_members() aggregates them.
        # For a full migration, we would parse the raw Leaves sheet.
        
    print("Migration completed!")

if __name__ == "__main__":
    asyncio.run(main())
