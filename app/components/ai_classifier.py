"""
AIClassifier — Python equivalent of AIClassifier.ts.
Uses a single combined Gemini call to classify + extract info in one request.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai
from app.utils.logger import logger

VALID_CATEGORIES = {
    "training_leave", "meeting_leave", "pause_membership",
    "quit_membership", "bot_identity", "unclassified",
    "greeting", "ambiguous_stop"
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    reason: str
    date: Optional[str]
    date_range: Optional[dict]   # {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    manual_review: bool = False


class AIClassifier:
    def __init__(self):
        api_key = os.getenv("AI_SERVICE_API_KEY", "")
        if not api_key:
            raise ValueError("AI_SERVICE_API_KEY is required")

        model_name = os.getenv("AI_SERVICE_MODEL", "gemini-2.0-flash")
        self.timeout = 10  # seconds

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

        logger.log_info("AI_Classifier", "initialize", "AI Classifier initialized",
                        {"model": model_name, "timeout": self.timeout})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def classify(self, message: dict) -> ClassificationResult:
        """
        Classify a message using a single combined Gemini call.
        message = {"senderId": str, "content": str, "timestamp": str, "history": [...]}
        """
        content = message.get("content", "")
        history = message.get("history", [])
        sender_id = message.get("senderId", "")

        logger.log_debug("AI_Classifier", "classify",
                         "Starting classification (single combined AI call)",
                         {"facebookId": sender_id, "messageLength": len(content)})
        try:
            combined = await self._call_combined(content, history)

            # Truncate reason
            if combined.get("reason") and len(combined["reason"]) > 500:
                combined["reason"] = combined["reason"][:500]

            result = ClassificationResult(
                category=combined["category"],
                confidence=combined["confidence"],
                reason=combined.get("reason", ""),
                date=combined.get("date"),
                date_range=combined.get("dateRange"),
                manual_review=False,
            )

            # Business rules -----------------------------------------------
            # Low confidence → unclassified + manual review
            if result.confidence < 0.70:
                result.category = "unclassified"
                result.manual_review = True
                logger.log_warn("AI_Classifier", "classify",
                                "Low confidence, marking for manual review",
                                {"facebookId": sender_id, "confidence": result.confidence})

            logger.log_info("AI_Classifier", "classify",
                            "Message classified successfully",
                            {"facebookId": sender_id, "category": result.category,
                             "confidence": result.confidence, "manualReview": result.manual_review})
            return result

        except Exception as exc:
            logger.log_error("AI_Classifier", "classify", "Classification failed",
                             {"facebookId": sender_id, "error": exc})
            return ClassificationResult(
                category="unclassified", confidence=0.0,
                reason="", date=None, date_range=None, manual_review=True,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_combined(self, content: str, history: list) -> dict:
        """Single Gemini call that returns category + extraction in one JSON."""
        prompt = self._build_combined_prompt(content, history)
        try:
            response_text = await asyncio.wait_for(
                asyncio.to_thread(self._gemini_generate, prompt),
                timeout=self.timeout,
            )
            return self._parse_combined(response_text)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Gemini timeout after {self.timeout}s")
        except Exception as exc:
            raise RuntimeError(f"Gemini error: {exc}") from exc

    def _gemini_generate(self, prompt: str) -> str:
        result = self.model.generate_content(prompt)
        return result.text

    def _build_combined_prompt(self, content: str, history: list) -> str:
        current_year = datetime.now().year
        system = f"""Bạn đóng vai trò là một thành viên của Ban Nội Bộ tổ chức sinh viên "SGroup".
Nhiệm vụ của bạn là giao tiếp tự nhiên, thân thiện và chuyên nghiệp với các thành viên khác, đồng thời phân loại và trích xuất thông tin từ tin nhắn của họ.
Năm hiện tại là {current_year}. Hãy mặc định năm này nếu tin nhắn không nêu rõ.

Hãy thực hiện ĐỒNG THỜI 2 việc:

1. PHÂN LOẠI tin nhắn vào đúng 1 category:
   - greeting         → lời chào hỏi thông thường (xin chào, hello, chào buổi sáng...)
   - training_leave   → xin nghỉ đào tạo
   - meeting_leave    → xin nghỉ họp (họp tháng, họp ban...)
   - pause_membership → xin "tạm dừng hoạt động", "tạm off" (có tính tạm thời)
   - quit_membership  → xin "rời tổ chức", "nghỉ hẳn", "dừng hoạt động hẳn" (vĩnh viễn)
   - ambiguous_stop   → "xin dừng hoạt động" chung chung, không rõ là tạm thời hay vĩnh viễn
   - bot_identity     → hỏi bạn là ai / vai trò của bạn
   - unclassified     → không rõ / không khớp

   LƯU Ý QUAN TRỌNG VỀ NGỮ CẢNH: Nếu người dùng đang trả lời một câu hỏi của bạn từ tin nhắn trước (ví dụ: bổ sung ngày tháng, bổ sung lý do cho việc xin nghỉ hoặc xin rời tổ chức), hãy tiếp tục phân loại tin nhắn mới này vào category đang được thảo luận trong lịch sử hội thoại và trích xuất thông tin mới.

2. TRÍCH XUẤT thông tin (dựa trên cả lịch sử và tin nhắn hiện tại):
   - reason: lý do của yêu cầu (tối đa 500 ký tự, chuỗi rỗng nếu không có)
   - date: ngày đơn lẻ dạng YYYY-MM-DD, hoặc null
   - dateRange: {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}} nếu có khoảng thời gian, hoặc null

Nhận dạng ngày: DD/MM/YYYY, DD-MM-YYYY, "ngày 15 tháng 3", "tuần sau", "hôm nay", "ngày mai",...
Dùng "date" cho ngày đơn lẻ; dùng "dateRange" cho khoảng thời gian; đặt cả hai thành null nếu không có ngày.

Trả về CHỈ JSON (không có markdown, không có text thêm):
{{
  "category": "training_leave|meeting_leave|pause_membership|quit_membership|bot_identity|greeting|ambiguous_stop|unclassified",
  "confidence": 0.95,
  "reason": "lý do trích xuất hoặc chuỗi rỗng",
  "date": "YYYY-MM-DD" hoặc null,
  "dateRange": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}} hoặc null
}}

Hướng dẫn confidence:
- 0.90-1.00: từ khoá rõ ràng, ý định minh bạch, hoặc là câu trả lời trực tiếp cho ngữ cảnh đang có
- 0.70-0.89: ý định rõ nhưng diễn đạt gián tiếp
- 0.00-0.69: mơ hồ hoặc không rõ"""

        user_parts = []
        if history:
            user_parts.append("Lịch sử hội thoại:")
            for msg in history:
                role_label = "User" if msg.get("role") == "user" else "Assistant"
                user_parts.append(f"{role_label}: {msg.get('content', '')}")
            user_parts.append("")

        user_parts.append(f"Phân loại và trích xuất thông tin từ tin nhắn MỚI này:\n\n{content}")
        user = "\n".join(user_parts)

        return f"{system}\n\n{user}"

    def _parse_combined(self, response: str) -> dict:
        try:
            # Strip markdown code fences if present
            clean = response.strip()
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, re.IGNORECASE)
            if m:
                clean = m.group(1).strip()

            parsed = json.loads(clean)

            category = parsed.get("category", "unclassified")
            if category not in VALID_CATEGORIES:
                category = "unclassified"

            confidence = float(parsed.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))

            reason = str(parsed.get("reason", ""))[:500]

            raw_date = parsed.get("date")
            date = raw_date if isinstance(raw_date, str) and DATE_RE.match(raw_date) else None

            raw_range = parsed.get("dateRange")
            date_range = None
            if isinstance(raw_range, dict):
                s, e = raw_range.get("start"), raw_range.get("end")
                if s and e and DATE_RE.match(str(s)) and DATE_RE.match(str(e)):
                    date_range = {"start": s, "end": e}

            return {"category": category, "confidence": confidence,
                    "reason": reason, "date": date, "dateRange": date_range}
        except Exception as exc:
            logger.log_warn("AI_Classifier", "_parse_combined",
                            "Failed to parse combined AI response, returning unclassified",
                            {"error": exc})
            return {"category": "unclassified", "confidence": 0.0,
                    "reason": "", "date": None, "dateRange": None}
