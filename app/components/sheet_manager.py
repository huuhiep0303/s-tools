"""
SheetManager — Python equivalent of SheetManager.ts.
Manages all Google Sheets operations using gspread.
"""

import json
import os
import random
import string
import time
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from app.utils.logger import logger
from app.utils.retry import retry_fixed, retry_exponential

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SHEET_STRUCTURES = {
    "Members":         ["Facebook_ID", "Name", "Active_Status", "Status_Date", "Fee_Eligibility", "Fee_Amount"],
    "Events":          ["Event_ID", "Event_Name", "Date", "Description", "Notified"],
    "Leaves":          ["Record_ID", "Facebook_ID", "Request_Type", "Date", "Reason", "Created_At"],
    "Request_History": ["Record_ID", "Timestamp", "Facebook_ID", "Request_Type", "Confidence", "Status"],
    "Manual_Review":   ["Record_ID", "Message_Content", "Sender_ID", "Timestamp", "Confidence", "Reviewed", "Manual_Classification", "Sender_Name"],
    "Dashboard":       ["Total_Active_Members", "Total_Paused_Members", "Total_Quit_Members",
                        "Monthly_Revenue", "Training_Leave_Count", "Meeting_Leave_Count", "Last_Updated"],
}


def _make_id(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
    return f"{prefix}_{int(time.time() * 1000)}_{suffix}"


class SheetManager:
    def __init__(self):
        self.spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "")
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self):
        if self._initialized:
            return
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS", "")
        if not creds_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_CREDENTIALS is required")

        import asyncio
        await asyncio.to_thread(self._sync_init, creds_json)
        self._initialized = True
        logger.log_info("Sheet_Manager", "initialize",
                        "SheetManager initialized", {"spreadsheetId": self.spreadsheet_id})

    def _sync_init(self, creds_json: str):
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)

    async def validate_and_create_sheets(self):
        """Create any missing sheets with their headers."""
        import asyncio
        await asyncio.to_thread(self._sync_validate_sheets)

    def _sync_validate_sheets(self):
        existing = {ws.title for ws in self._spreadsheet.worksheets()}
        for name, headers in SHEET_STRUCTURES.items():
            if name not in existing:
                logger.log_info("Sheet_Manager", "validate_and_create_sheets",
                                f"Creating missing sheet: {name}")
                ws = self._spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
                ws.append_row(headers)
                logger.log_info("Sheet_Manager", "validate_and_create_sheets",
                                f"Sheet created: {name}")

    # ------------------------------------------------------------------
    # Member helpers
    # ------------------------------------------------------------------

    async def member_exists(self, name_or_id: str) -> bool:
        """Check if a member exists in the Members sheet by name or Facebook ID."""
        import asyncio
        return await asyncio.to_thread(self._sync_member_exists, name_or_id)

    def _sync_member_exists(self, name_or_id: str) -> bool:
        try:
            ws = self._spreadsheet.worksheet("Members")
            values = ws.get_all_values()
            for row in values[1:]:   # skip header
                if len(row) >= 2 and (row[0] == name_or_id or row[1] == name_or_id):
                    return True
            return False
        except Exception as exc:
            logger.log_error("Sheet_Manager", "member_exists", "Error checking member", {"error": exc})
            return False

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def record_leave_request(self, request: dict):
        """Append a row to the Leaves sheet."""
        import asyncio
        record_id = _make_id("LEAVE")
        row = [
            record_id,
            request.get("facebookId", ""),
            request.get("requestType", ""),
            request.get("date", ""),
            request.get("reason", ""),
            request.get("timestamp", ""),
        ]
        logger.log_info("Sheet_Manager", "recordLeaveRequest",
                        "Recording leave request", {"facebookId": request.get("facebookId"), "recordId": record_id})
        await retry_exponential(
            lambda: asyncio.to_thread(self._append_row, "Leaves", row),
            max_attempts=3, base_delay_ms=2000,
            on_retry=lambda a, e: logger.log_warn("Sheet_Manager", "recordLeaveRequest",
                                                   f"Retry {a}", {"error": e}),
        )
        logger.log_info("Sheet_Manager", "recordLeaveRequest",
                        "Leave request recorded", {"recordId": record_id})

    async def update_member_status(self, update: dict):
        """Update Active_Status, Status_Date, Fee_Eligibility, Fee_Amount for a member."""
        import asyncio
        facebook_id = update.get("facebookId", "")
        new_status = update.get("newStatus", "")
        logger.log_info("Sheet_Manager", "updateMemberStatus",
                        f"Updating member status to {new_status}", {"facebookId": facebook_id})
        await retry_exponential(
            lambda: asyncio.to_thread(self._sync_update_status, facebook_id, new_status),
            max_attempts=3, base_delay_ms=2000,
            on_retry=lambda a, e: logger.log_warn("Sheet_Manager", "updateMemberStatus",
                                                   f"Retry {a}", {"error": e}),
        )

    def _sync_update_status(self, facebook_id: str, new_status: str):
        ws = self._spreadsheet.worksheet("Members")
        values = ws.get_all_values()
        row_index = None
        for i, row in enumerate(values[1:], start=2):   # 1-indexed, skip header
            if row[0] == facebook_id or (len(row) > 1 and row[1] == facebook_id):
                row_index = i
                break
        if row_index is None:
            raise ValueError(f"Member {facebook_id} not found in Members sheet")

        status_date = datetime.utcnow().strftime("%Y-%m-%d")
        fee_eligibility = "eligible" if new_status == "active" else "exempt"
        fee_amount = 200000 if new_status == "active" else 0

        ws.update(f"C{row_index}:F{row_index}",
                  [[new_status, status_date, fee_eligibility, fee_amount]])
        logger.log_info("Sheet_Manager", "updateMemberStatus",
                        "Member status updated", {"facebookId": facebook_id, "newStatus": new_status})

    async def record_history(self, history: dict):
        """Append a row to the Request_History sheet."""
        import asyncio
        record_id = _make_id("HIST")
        row = [
            record_id,
            history.get("timestamp", ""),
            history.get("facebookId", ""),
            history.get("requestType", ""),
            history.get("confidence", 0),
            history.get("status", ""),
        ]
        logger.log_info("Sheet_Manager", "recordHistory",
                        "Recording history", {"facebookId": history.get("facebookId"), "recordId": record_id})
        await retry_fixed(
            lambda: asyncio.to_thread(self._append_row, "Request_History", row),
            max_attempts=3, delay_ms=5000,
            on_retry=lambda a, e: logger.log_warn("Sheet_Manager", "recordHistory",
                                                   f"Retry {a}", {"error": e}),
        )

    async def record_manual_review(self, review: dict):
        """Append a row to the Manual_Review sheet."""
        import asyncio
        record_id = _make_id("REVIEW")
        row = [
            record_id,
            review.get("messageContent", ""),
            review.get("senderId", ""),
            review.get("timestamp", ""),
            review.get("confidence", 0),
            "true" if review.get("reviewed") else "false",
            review.get("manualClassification", ""),
            review.get("senderName", ""),
        ]
        logger.log_info("Sheet_Manager", "recordManualReview",
                        "Recording to Manual_Review queue", {"senderId": review.get("senderId"), "recordId": record_id})
        await asyncio.to_thread(self._append_row, "Manual_Review", row)
        logger.log_info("Sheet_Manager", "recordManualReview",
                        "Manual review record created", {"recordId": record_id})

    async def resolve_manual_review(self, record_id: str, final_category: str) -> dict:
        """Mark a manual review as resolved and update its category."""
        import asyncio
        return await asyncio.to_thread(self._sync_resolve_manual_review, record_id, final_category)

    def _sync_resolve_manual_review(self, record_id: str, final_category: str) -> dict:
        ws = self._spreadsheet.worksheet("Manual_Review")
        values = ws.get_all_values()
        row_index = None
        review_data = None
        for i, row in enumerate(values[1:], start=2):
            if row[0] == record_id:
                row_index = i
                review_data = {
                    "recordId": row[0],
                    "messageContent": row[1] if len(row) > 1 else "",
                    "senderId": row[2] if len(row) > 2 else "",
                    "timestamp": row[3] if len(row) > 3 else "",
                    "confidence": float(row[4]) if len(row) > 4 else 0.0,
                }
                break
        
        if not row_index:
            raise ValueError(f"Manual review {record_id} not found")
            
        ws.update(f"F{row_index}:G{row_index}", [["true", final_category]])
        logger.log_info("Sheet_Manager", "resolveManualReview", "Manual review resolved", {"recordId": record_id, "finalCategory": final_category})
        return review_data

    async def update_dashboard(self):
        """Recalculate and write dashboard stats."""
        import asyncio
        logger.log_info("Sheet_Manager", "updateDashboard", "Updating dashboard statistics")
        await retry_fixed(
            lambda: asyncio.to_thread(self._sync_update_dashboard),
            max_attempts=3, delay_ms=60000,
            on_retry=lambda a, e: logger.log_warn("Sheet_Manager", "updateDashboard",
                                                   f"Retry {a}", {"error": e}),
        )

    def _sync_update_dashboard(self):
        # Members stats
        ws_members = self._spreadsheet.worksheet("Members")
        member_rows = ws_members.get_all_values()[1:]
        active = sum(1 for r in member_rows if len(r) > 2 and r[2].strip().lower() == "active")
        paused = sum(1 for r in member_rows if len(r) > 2 and r[2].strip().lower() == "paused")
        quit_c = sum(1 for r in member_rows if len(r) > 2 and r[2].strip().lower() == "inactive")
        revenue = active * 200000

        # Leaves this month
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ws_leaves = self._spreadsheet.worksheet("Leaves")
        leave_rows = ws_leaves.get_all_values()[1:]
        training = meeting = 0
        for r in leave_rows:
            if len(r) < 6:
                continue
            try:
                created = datetime.fromisoformat(r[5].replace("Z", "+00:00"))
                if created >= month_start.replace(tzinfo=created.tzinfo):
                    if r[2] == "training_leave":
                        training += 1
                    elif r[2] == "meeting_leave":
                        meeting += 1
            except Exception:
                pass

        last_updated = now.isoformat() + "Z"
        data_row = [active, paused, quit_c, revenue, training, meeting, last_updated]

        ws_dash = self._spreadsheet.worksheet("Dashboard")
        all_vals = ws_dash.get_all_values()
        if len(all_vals) <= 1:
            ws_dash.append_row(data_row)
        else:
            ws_dash.update("A2:G2", [data_row])
        logger.log_info("Sheet_Manager", "updateDashboard",
                        "Dashboard updated", {"active": active, "revenue": revenue})

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_dashboard_stats(self) -> dict:
        import asyncio
        return await asyncio.to_thread(self._sync_get_dashboard_stats)

    def _sync_get_dashboard_stats(self) -> dict:
        try:
            # Members stats
            ws_members = self._spreadsheet.worksheet("Members")
            member_rows = ws_members.get_all_values()[1:]
            active = sum(1 for r in member_rows if len(r) > 2 and r[2].strip().lower() == "active")
            paused = sum(1 for r in member_rows if len(r) > 2 and r[2].strip().lower() == "paused")
            quit_c = sum(1 for r in member_rows if len(r) > 2 and r[2].strip().lower() == "inactive")
            revenue = active * 200000

            # Leaves this month
            now = datetime.utcnow()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            try:
                ws_leaves = self._spreadsheet.worksheet("Leaves")
                leave_rows = ws_leaves.get_all_values()[1:]
            except Exception:
                leave_rows = []
                
            training = meeting = 0
            for r in leave_rows:
                if len(r) < 6:
                    continue
                try:
                    created = datetime.fromisoformat(r[5].replace("Z", "+00:00"))
                    if created >= month_start.replace(tzinfo=created.tzinfo):
                        if r[2] == "training_leave":
                            training += 1
                        elif r[2] == "meeting_leave":
                            meeting += 1
                except Exception:
                    pass

            return {
                "activeMembers": active,
                "pausedMembers": paused,
                "quitMembers": quit_c,
                "monthlyRevenue": revenue,
                "trainingLeaveCount": training,
                "meetingLeaveCount": meeting,
                "lastUpdated": now.isoformat() + "Z"
            }
        except Exception as exc:
            logger.log_error("Sheet_Manager", "getDashboardStats", "Error", {"error": exc})
            return {}

    async def get_members(self) -> list:
        import asyncio
        return await asyncio.to_thread(self._sync_get_members)

    def _sync_get_members(self) -> list:
        try:
            ws_members = self._spreadsheet.worksheet("Members")
            member_values = ws_members.get_all_values()
            
            try:
                ws_leaves = self._spreadsheet.worksheet("Leaves")
                leave_values = ws_leaves.get_all_values()
            except Exception:
                leave_values = []
                
            leave_counts = {}
            for row in leave_values[1:]:
                if len(row) >= 3:
                    fb_id = row[1]
                    req_type = row[2]
                    if fb_id not in leave_counts:
                        leave_counts[fb_id] = {"training": 0, "meeting": 0}
                    if req_type == "training_leave":
                        leave_counts[fb_id]["training"] += 1
                    elif req_type == "meeting_leave":
                        leave_counts[fb_id]["meeting"] += 1

            members = []
            for row in member_values[1:]:
                if len(row) >= 2:
                    fb_id = row[0]
                    stats = leave_counts.get(fb_id, {"training": 0, "meeting": 0})
                    members.append({
                        "facebookId": fb_id,
                        "name": row[1],
                        "activeStatus": row[2] if len(row) > 2 else "",
                        "statusDate": row[3] if len(row) > 3 else "",
                        "feeEligibility": row[4] if len(row) > 4 else "",
                        "feeAmount": int(row[5]) if len(row) > 5 and row[5].isdigit() else 0,
                        "trainingLeaveCount": stats["training"],
                        "meetingLeaveCount": stats["meeting"]
                    })
            return members
        except Exception as exc:
            logger.log_error("Sheet_Manager", "getMembers", "Error", {"error": exc})
            return []

    async def get_events(self) -> list:
        import asyncio
        return await asyncio.to_thread(self._sync_get_events)

    def _sync_get_events(self) -> list:
        try:
            ws = self._spreadsheet.worksheet("Events")
            values = ws.get_all_values()
            events = []
            for row in values[1:]:
                if len(row) >= 3:
                    events.append({
                        "eventId": row[0],
                        "eventName": row[1],
                        "date": row[2],
                        "description": row[3] if len(row) > 3 else "",
                        "notified": row[4].lower() == 'true' if len(row) > 4 else False,
                    })
            return events
        except Exception as exc:
            logger.log_error("Sheet_Manager", "getEvents", "Error", {"error": exc})
            return []

    async def mark_event_notified(self, event_id: str):
        import asyncio
        await asyncio.to_thread(self._sync_mark_event_notified, event_id)

    def _sync_mark_event_notified(self, event_id: str):
        ws = self._spreadsheet.worksheet("Events")
        values = ws.get_all_values()
        for i, row in enumerate(values[1:], start=2):
            if row[0] == event_id:
                ws.update_cell(i, 5, "true")
                break

    async def get_manual_reviews(self) -> list:
        import asyncio
        return await asyncio.to_thread(self._sync_get_manual_reviews)

    def _sync_get_manual_reviews(self) -> list:
        try:
            ws = self._spreadsheet.worksheet("Manual_Review")
            values = ws.get_all_values()
            
            try:
                ws_members = self._spreadsheet.worksheet("Members")
                member_values = ws_members.get_all_values()
                member_map = {row[0]: row[1] for row in member_values[1:] if len(row) >= 2}
            except Exception:
                member_map = {}
                
            reviews = []
            for row in values[1:]:
                if len(row) >= 3:
                    sender_id = row[2]
                    sender_name = row[7] if len(row) > 7 and row[7] else member_map.get(sender_id, sender_id)
                    reviews.append({
                        "recordId": row[0],
                        "messageContent": row[1],
                        "senderId": sender_id,
                        "senderName": sender_name,
                        "timestamp": row[3] if len(row) > 3 else "",
                        "confidence": float(row[4]) if len(row) > 4 else 0,
                        "reviewed": row[5].lower() == "true" if len(row) > 5 else False,
                        "manualClassification": row[6] if len(row) > 6 else "",
                    })
            return reviews
        except Exception as exc:
            logger.log_error("Sheet_Manager", "getManualReviews", "Error", {"error": exc})
            return []

    async def get_recent_requests(self) -> list:
        import asyncio
        return await asyncio.to_thread(self._sync_get_recent_requests)

    def _sync_get_recent_requests(self) -> list:
        try:
            ws = self._spreadsheet.worksheet("Request_History")
            values = ws.get_all_values()
            requests = []
            # Get last 50 requests, reverse order
            for row in reversed(values[1:]):
                if len(row) >= 3:
                    requests.append({
                        "recordId": row[0],
                        "timestamp": row[1],
                        "facebookId": row[2],
                        "requestType": row[3] if len(row) > 3 else "",
                        "confidence": float(row[4]) if len(row) > 4 else 0,
                        "status": row[5] if len(row) > 5 else "",
                    })
                if len(requests) >= 50:
                    break
            return requests
        except Exception as exc:
            logger.log_error("Sheet_Manager", "getRecentRequests", "Error", {"error": exc})
            return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append_row(self, sheet_name: str, row: list):
        ws = self._spreadsheet.worksheet(sheet_name)
        ws.append_row(row, value_input_option="RAW")
