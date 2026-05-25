"""
ResponseHandler — Python equivalent of ResponseHandler.ts.
Sends messages via Facebook Messenger Graph API.
"""

import asyncio
import os
from typing import Optional

import httpx

from app.utils.logger import logger
from app.utils.retry import retry_fixed

FB_API_BASE = "https://graph.facebook.com/v18.0"


class ResponseHandler:
    def __init__(self):
        self.page_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
        if not self.page_token:
            raise ValueError("FACEBOOK_PAGE_ACCESS_TOKEN is required")

        admin_raw = os.getenv("ADMIN_FACEBOOK_IDS", "")
        self.admin_ids = [i.strip() for i in admin_raw.split(",") if i.strip()]

        logger.log_info("Response_Handler", "initialize", "ResponseHandler initialized",
                        {"adminCount": len(self.admin_ids)})

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def get_user_profile_name(self, sender_id: str) -> str:
        """Fetch display name from Facebook Graph API. Falls back to sender_id."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{FB_API_BASE}/{sender_id}",
                    params={"fields": "name", "access_token": self.page_token},
                )
                data = resp.json()
                if "name" in data:
                    return data["name"]
        except Exception as exc:
            logger.log_warn("Response_Handler", "get_user_profile_name",
                            f"Failed to fetch name for {sender_id}, falling back to ID",
                            {"error": exc})
        return sender_id

    async def send_confirmation(self, recipient_id: str, category: str,
                                data: dict) -> str:
        """Send confirmation message. Returns the sent text."""
        message = self._format_confirmation(category, data)
        logger.log_info("Response_Handler", "send_confirmation",
                        "Sending confirmation", {"recipientId": recipient_id, "category": category})
        try:
            await self._send_message(recipient_id, message, timeout=10)
            logger.log_info("Response_Handler", "send_confirmation",
                            "Confirmation sent successfully", {"recipientId": recipient_id})
        except Exception as exc:
            logger.log_error("Response_Handler", "send_confirmation",
                             "Failed to send confirmation", {"error": exc, "recipientId": recipient_id})
        return message

    async def send_clarification_request(self, recipient_id: str,
                                          classification: Optional[dict] = None) -> str:
        """Send clarification request with retry (3 attempts, 5 s apart)."""
        message = self._format_clarification(classification)
        logger.log_info("Response_Handler", "sendClarificationRequest",
                        "Sending clarification request", {"recipientId": recipient_id})
        try:
            await retry_fixed(
                lambda: self._send_message(recipient_id, message, timeout=10),
                max_attempts=3, delay_ms=5000,
                on_retry=lambda attempt, exc: logger.log_warn(
                    "Response_Handler", "sendClarificationRequest",
                    f"Send attempt {attempt} failed, retrying...",
                    {"error": exc, "recipientId": recipient_id},
                ),
            )
            logger.log_info("Response_Handler", "sendClarificationRequest",
                            "Clarification request sent successfully", {"recipientId": recipient_id})
        except Exception as exc:
            logger.log_error("Response_Handler", "sendClarificationRequest",
                             "Failed to send clarification request",
                             {"error": exc, "recipientId": recipient_id})
        return message

    async def send_admin_notification(self, data: dict):
        """Send notification to all configured admins."""
        if not self.admin_ids:
            logger.log_warn("Response_Handler", "sendAdminNotification",
                            "No admin IDs configured, skipping")
            return

        message = self._format_admin_notification(data)
        logger.log_info("Response_Handler", "sendAdminNotification",
                        "Sending admin notification", {"adminCount": len(self.admin_ids)})

        tasks = [self._notify_admin(aid, message) for aid in self.admin_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _notify_admin(self, admin_id: str, message: str):
        try:
            await retry_fixed(
                lambda: self._send_message(admin_id, message, timeout=30),
                max_attempts=3, delay_ms=60000,
                on_retry=lambda attempt, exc: logger.log_warn(
                    "Response_Handler", "sendAdminNotification",
                    f"Send attempt {attempt} to admin {admin_id} failed, retrying...",
                    {"error": exc, "adminId": admin_id},
                ),
            )
            logger.log_info("Response_Handler", "sendAdminNotification",
                            "Admin notification sent successfully", {"adminId": admin_id})
        except Exception as exc:
            logger.log_error("Response_Handler", "sendAdminNotification",
                             "Failed to send admin notification after all retries",
                             {"error": exc, "adminId": admin_id})

    async def _send_message(self, recipient_id: str, message: str, timeout: int = 10):
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{FB_API_BASE}/me/messages",
                params={"access_token": self.page_token},
                json={"recipient": {"id": recipient_id}, "message": {"text": message}},
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Facebook API error {resp.status_code}: {resp.text}"
                )

    def _format_confirmation(self, category: str, data: dict) -> str:
        date = data.get("date", "")
        switch = {
            "training_leave":
                f"Ban nội bộ đã ghi nhận thông tin bạn xin nghỉ đào tạo ngày {date}. Cảm ơn bạn đã thông báo nhé!",
            "meeting_leave":
                f"Ban nội bộ đã ghi nhận thông tin bạn xin nghỉ họp ngày {date}. Cảm ơn bạn đã thông báo nhé!",
            "pause_membership":
                f"Ban nội bộ đã ghi nhận yêu cầu tạm dừng hoạt động từ ngày {date} của bạn. Chúc bạn hoàn thành tốt các dự định cá nhân nhé!",
            "quit_membership":
                "Ban nội bộ đã ghi nhận thông tin xin rời tổ chức của bạn. Cảm ơn bạn vì khoảng thời gian đồng hành cùng SGroup!",
            "bot_identity":
                "Chào bạn, mình là thành viên Ban Nội Bộ SGroup. Mình ở đây để giúp bạn giải quyết các vấn đề liên quan đến nhân sự như xin nghỉ (đào tạo/họp), tạm dừng hoạt động hoặc rời tổ chức. Bạn cần mình hỗ trợ gì nào?",
            "greeting":
                "Chào bạn, mình là thành viên Ban Nội Bộ SGroup. Mình có thể giúp gì cho bạn hôm nay?",
        }
        return switch.get(
            category,
            f"Ban nội bộ đã ghi nhận yêu cầu của bạn. Cảm ơn bạn nhé!"
        )

    def _format_clarification(self, classification: Optional[dict]) -> str:
        if classification:
            cat = classification.get("category")
            has_date = classification.get("date") or classification.get("date_range")
            reason = classification.get("reason")
            
            if cat == "ambiguous_stop":
                return "Bạn muốn xin tạm dừng hoạt động trong một thời gian hay xin rời tổ chức (nghỉ hẳn) vậy ạ?"
                
            if cat == "pause_membership":
                if not has_date:
                    return "Ban nội bộ đã nhận yêu cầu tạm dừng hoạt động của bạn. Bạn vui lòng bổ sung khoảng thời gian cụ thể nhé!"
                if not reason:
                    return "Ban nội bộ đã nhận yêu cầu tạm dừng hoạt động. Bạn vui lòng bổ sung thêm lý do giúp ban nhé!"
            elif cat == "quit_membership":
                if not reason:
                    return "Ban nội bộ đã nhận yêu cầu rời tổ chức của bạn. Bạn có thể chia sẻ thêm lý do để ban nắm được không?"
            elif cat in ("training_leave", "meeting_leave"):
                if not has_date:
                    return "Ban nội bộ đã nhận yêu cầu xin nghỉ của bạn. Bạn vui lòng bổ sung thêm ngày tháng cụ thể nhé!"
        return (
            "Xin lỗi, ban nội bộ chưa hiểu rõ yêu cầu của bạn. "
            "Bạn có thể cho biết mình muốn: nghỉ đào tạo, nghỉ họp, tạm dừng, hay rời tổ chức? "
            "Đồng thời bổ sung thêm thời gian giúp ban nhé!"
        )

    def _format_admin_notification(self, data: dict) -> str:
        sender = data.get("senderId", "")
        ts = data.get("timestamp", "")
        content = data.get("messageContent", "")
        return f"⚠️ Tin nhắn cần xem xét thủ công từ {sender} lúc {ts}: {content}"
