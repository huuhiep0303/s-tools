import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logger import logger
from app.components.sheet_manager import SheetManager
from app.components.response_handler import ResponseHandler

class JobScheduler:
    def __init__(self, sheet_manager: SheetManager, response_handler: ResponseHandler):
        self.scheduler = AsyncIOScheduler()
        self.sheet_manager = sheet_manager
        self.response_handler = response_handler
        
    def start(self):
        """Start the scheduler and add jobs."""
        # Run every hour to check for events or fees
        self.scheduler.add_job(
            self.check_and_send_reminders,
            trigger=IntervalTrigger(hours=1),
            id="check_reminders_job",
            replace_existing=True,
            next_run_time=datetime.now() # Run immediately on startup
        )
        self.scheduler.start()
        logger.log_info("Job_Scheduler", "start", "Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.log_info("Job_Scheduler", "stop", "Scheduler stopped")

    async def check_and_send_reminders(self):
        """Check for upcoming events and unpaid fees, and send reminders."""
        logger.log_info("Job_Scheduler", "check_reminders", "Checking for reminders to send")
        try:
            members = await self.sheet_manager.get_members()
            events = await self.sheet_manager.get_events()
            
            active_members = [m for m in members if m.get("activeStatus") == "active"]
            
            now = datetime.now()
            
            # 1. Event Reminders (24 hours before)
            for event in events:
                if event.get("notified"):
                    continue
                    
                # Parse event date (assume YYYY-MM-DD HH:MM format for simplicity)
                try:
                    event_date_str = event.get("date", "")
                    # handle just date or date+time
                    if len(event_date_str) == 10:
                        event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
                    else:
                        event_date = datetime.strptime(event_date_str, "%Y-%m-%d %H:%M")
                        
                    # If event is within next 24 hours
                    time_diff = event_date - now
                    if timedelta(0) < time_diff <= timedelta(hours=24):
                        message = f"📢 THÔNG BÁO SỰ KIỆN: Sắp tới sẽ có sự kiện '{event.get('eventName')}' vào lúc {event_date_str}.\n\n{event.get('description')}\n\nMọi người chú ý tham gia đầy đủ nhé!"
                        
                        # Send to all active members
                        for member in active_members:
                            fb_id = member.get("facebookId")
                            if fb_id:
                                await self.response_handler.send_direct_message(fb_id, message)
                                await asyncio.sleep(0.5) # Avoid rate limits
                                
                        await self.sheet_manager.mark_event_notified(event.get("eventId"))
                        logger.log_info("Job_Scheduler", "send_event_reminder", f"Reminders sent for event {event.get('eventName')}")
                except Exception as e:
                    logger.log_error("Job_Scheduler", "check_reminders", f"Failed to parse event date for {event.get('eventName')}", {"error": e})
                    
            # 2. Fee Reminders (on the 5th of every month)
            if now.day == 5:
                for member in active_members:
                    fee_amount = member.get("feeAmount", 0)
                    # If they owe money
                    if fee_amount > 0:
                        fb_id = member.get("facebookId")
                        if fb_id:
                            message = f"💰 NHẮC NHỞ ĐÓNG QUỸ: Chào {member.get('name')}, hôm nay là ngày mùng 5, bạn nhớ đóng quỹ tháng này nhé. Số tiền cần đóng là {fee_amount} VNĐ.\nCảm ơn bạn!"
                            await self.response_handler.send_direct_message(fb_id, message)
                            await asyncio.sleep(0.5)
                            
        except Exception as exc:
            logger.log_error("Job_Scheduler", "check_reminders", "Error running reminder job", {"error": exc})
