"""
AIClassifier — Python equivalent of AIClassifier.ts.
Uses a single combined Gemini call to classify + extract info in one request.
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

# Vietnam timezone (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

import google.generativeai as genai
from app.utils.logger import logger

VALID_CATEGORIES = {
    "training_leave", "meeting_leave", "pause_membership",
    "quit_membership", "bot_identity", "unclassified",
    "greeting", "thanks", "ambiguous_stop"
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
    # Static system prompt — separated from user message for better Gemini understanding
    SYSTEM_PROMPT = """Bạn đóng vai trò là một thành viên của Ban Nội Bộ tổ chức sinh viên "S-Group".
Nhiệm vụ của bạn là giao tiếp tự nhiên, thân thiện và chuyên nghiệp với các thành viên khác, đồng thời phân loại và trích xuất thông tin từ tin nhắn của họ.

Hãy thực hiện ĐỒNG THỜI 2 việc:

1. PHÂN LOẠI tin nhắn vào đúng 1 category:
   - greeting         → lời chào hỏi thông thường (xin chào, hello, hi, chào buổi sáng...)
   - thanks           → lời cảm ơn, dạ vâng, ok ạ, đã rõ (khi user xác nhận hoặc cảm ơn sau khi được hỗ trợ)
   - training_leave   → xin nghỉ đào tạo (bao gồm viết tắt: "đt", "ĐT", "buổi đào tạo", "buổi dt")
   - meeting_leave    → xin nghỉ họp (họp tháng, họp ban, buổi họp...)
   - pause_membership → xin "tạm dừng hoạt động", "tạm off", "tạm nghỉ" (có tính tạm thời)
   - quit_membership  → xin "rời tổ chức", "nghỉ hẳn", "dừng hoạt động hẳn", "out" (vĩnh viễn)
   - ambiguous_stop   → "xin dừng hoạt động" chung chung, không rõ là tạm thời hay vĩnh viễn
   - bot_identity     → hỏi bạn là ai / vai trò của bạn / bot dùng để làm gì
   - unclassified     → không rõ / không khớp category nào ở trên

   LƯU Ý QUAN TRỌNG VỀ NGỮ CẢNH HỘI THOẠI:
   Nếu người dùng đang trả lời một câu hỏi của bạn từ tin nhắn trước (ví dụ: bổ sung ngày tháng, bổ sung lý do cho việc xin nghỉ hoặc xin rời tổ chức), hãy tiếp tục phân loại tin nhắn mới này vào category đang được thảo luận trong lịch sử hội thoại và trích xuất thông tin mới.
   Ví dụ: Nếu lịch sử cho thấy user xin nghỉ đào tạo nhưng thiếu ngày, và tin nhắn mới chỉ là "ngày 5/6" → category vẫn là training_leave.

2. TRÍCH XUẤT thông tin (dựa trên cả lịch sử và tin nhắn hiện tại):
   - reason: lý do cụ thể của yêu cầu (ví dụ: bị ốm, bận thi, về quê...). NẾU USER CHƯA NÊU LÝ DO CỤ THỂ, BẮT BUỘC PHẢI TRẢ VỀ CHUỖI RỖNG (""). KHÔNG lấy hành động "xin nghỉ" làm lý do.
   - date: ngày đơn lẻ dạng YYYY-MM-DD, hoặc null
   - dateRange: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} nếu có khoảng thời gian, hoặc null

Nhận dạng ngày: DD/MM/YYYY, DD-MM-YYYY, "ngày 15 tháng 3", "tuần sau", "hôm nay", "ngày mai",...
QUAN TRỌNG: Khi user nói "hôm nay", "ngày mai", "tuần sau"... hãy quy đổi dựa trên ngày hiện tại được cung cấp trong tin nhắn của user.
Dùng "date" cho ngày đơn lẻ; dùng "dateRange" cho khoảng thời gian; đặt cả hai thành null nếu không có ngày.

TỪ VIẾT TẮT / SLANG SINH VIÊN VIỆT NAM:
- "đt", "ĐT" = đào tạo
- "off", "xin off" = xin nghỉ
- "ae", "a/e" = anh em (cách gọi thân mật)
- "e" = em, "a" = anh/chị
- "nha", "nhen", "nè" = nhé
- "r" = rồi, "ko", "k" = không
- "dc", "đc" = được
- "bt" = bình thường / bận tí
- Emoji (🙏😢😅...) → bỏ qua emoji, tập trung vào nội dung text

Trả về CHỈ JSON hợp lệ (KHÔNG có markdown code fence, KHÔNG có text thêm, KHÔNG có ```json```):
{"category": "...", "confidence": 0.95, "reason": "...", "date": "YYYY-MM-DD hoặc null", "dateRange": null}

Hướng dẫn confidence:
- 0.90-1.00: từ khoá rõ ràng, ý định minh bạch, hoặc là câu trả lời trực tiếp cho ngữ cảnh đang có
- 0.70-0.89: ý định rõ nhưng diễn đạt gián tiếp
- 0.00-0.69: mơ hồ hoặc không rõ"""

    def __init__(self):
        api_key = os.getenv("AI_SERVICE_API_KEY", "")
        if not api_key:
            raise ValueError("AI_SERVICE_API_KEY is required")

        model_name = os.getenv("AI_SERVICE_MODEL", "gemini-2.0-flash")
        self.timeout = 30  # seconds (increased to accommodate retries)
        self.max_retries = 3
        self.retry_base_delay = 16  # seconds (Gemini suggests ~15s for rate limits)

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name,
            system_instruction=self.SYSTEM_PROMPT,
        )

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
        """Single Gemini call with automatic retry for rate limit (429) errors."""
        prompt = self._build_combined_prompt(content, history)
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response_text = await asyncio.wait_for(
                    asyncio.to_thread(self._gemini_generate, prompt),
                    timeout=self.timeout,
                )
                return self._parse_combined(response_text)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Gemini timeout after {self.timeout}s")
            except Exception as exc:
                last_error = exc
                error_str = str(exc)
                # Retry on rate limit (429) errors
                if "429" in error_str or "quota" in error_str.lower():
                    delay = self.retry_base_delay * (2 ** (attempt - 1))
                    logger.log_warn("AI_Classifier", "_call_combined",
                                    f"Rate limited (attempt {attempt}/{self.max_retries}), retrying in {delay}s",
                                    {"error": error_str[:200]})
                    if attempt < self.max_retries:
                        await asyncio.sleep(delay)
                        continue
                raise RuntimeError(f"Gemini error: {exc}") from exc

        raise RuntimeError(f"Gemini failed after {self.max_retries} retries: {last_error}") from last_error

    def _gemini_generate(self, prompt: str) -> str:
        result = self.model.generate_content(prompt)
        return result.text

    def _build_combined_prompt(self, content: str, history: list) -> str:
        """Build the USER message only (system role is handled by system_instruction)."""
        now = datetime.now(VN_TZ)
        current_date = now.strftime("%Y-%m-%d")
        weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        current_weekday = weekday_names[now.weekday()]

        user_parts = []
        user_parts.append(f"Thời điểm hiện tại: {current_weekday}, ngày {current_date}.")
        user_parts.append("")

        if history:
            user_parts.append("Lịch sử hội thoại:")
            for msg in history:
                role_label = "User" if msg.get("role") == "user" else "Assistant"
                user_parts.append(f"{role_label}: {msg.get('content', '')}")
            user_parts.append("")

        user_parts.append(f"Phân loại và trích xuất thông tin từ tin nhắn MỚI này:\n\n{content}")
        return "\n".join(user_parts)

    def _parse_combined(self, response: str) -> dict:
        try:
            clean = response.strip()

            # Strategy 1: Strip markdown code fences if present
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, re.IGNORECASE)
            if m:
                clean = m.group(1).strip()

            # Strategy 2: If still not valid JSON, try to find {...} block
            if not clean.startswith("{"):
                m2 = re.search(r"(\{[\s\S]*\})", clean)
                if m2:
                    clean = m2.group(1).strip()

            # Try parsing
            try:
                parsed = json.loads(clean)
            except json.JSONDecodeError:
                # Strategy 3: JSON might have trailing text after }, extract first valid block
                m3 = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", clean)
                if m3:
                    parsed = json.loads(m3.group(1).strip())
                else:
                    raise

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
                            {"error": exc, "raw_response": response[:500] if response else "(empty)"})
            return {"category": "unclassified", "confidence": 0.0,
                    "reason": "", "date": None, "dateRange": None}
