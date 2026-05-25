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
    "Leaves":          ["Record_ID", "Facebook_ID", "Request_Type", "Date", "Reason", "Created_At"],
    "Request_History": ["Record_ID", "Timestamp", "Facebook_ID", "Request_Type", "Confidence", "Status"],
    "Manual_Review":   ["Record_ID", "Message_Content", "Sender_ID", "Timestamp", "Confidence", "Reviewed", "Manual_Classification"],
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
        ]
        logger.log_info("Sheet_Manager", "recordManualReview",
                        "Recording to Manual_Review queue", {"senderId": review.get("senderId"), "recordId": record_id})
        await asyncio.to_thread(self._append_row, "Manual_Review", row)
        logger.log_info("Sheet_Manager", "recordManualReview",
                        "Manual review record created", {"recordId": record_id})

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
        active = sum(1 for r in member_rows if len(r) > 2 and r[2] == "active")
        paused = sum(1 for r in member_rows if len(r) > 2 and r[2] == "paused")
        quit_c = sum(1 for r in member_rows if len(r) > 2 and r[2] == "inactive")
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
    # Internal
    # ------------------------------------------------------------------

    def _append_row(self, sheet_name: str, row: list):
        ws = self._spreadsheet.worksheet(sheet_name)
        ws.append_row(row, value_input_option="RAW")
