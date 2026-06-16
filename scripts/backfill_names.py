import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

from app.components.sheet_manager import SheetManager
from app.components.response_handler import ResponseHandler

async def main():
    print("Starting backfill process...")
    sheet_manager = SheetManager()
    await sheet_manager.initialize()
    
    handler = ResponseHandler()
    
    # We need to access the spreadsheet directly to update
    ws = sheet_manager._spreadsheet.worksheet("Manual_Review")
    values = ws.get_all_values()
    
    print(f"Found {len(values)} rows in Manual_Review sheet")
    
    cache = {}
    
    # Row 1 is header
    for i, row in enumerate(values[1:], start=2):
        if len(row) >= 3:
            sender_id = row[2]
            
            # Check if name is already populated in 8th column
            if len(row) >= 8 and row[7].strip() != "":
                continue
                
            if sender_id not in cache:
                name = await handler.get_user_profile_name(sender_id)
                cache[sender_id] = name
                await asyncio.sleep(0.2) # sleep to prevent rate limiting
            else:
                name = cache[sender_id]
                
            try:
                ws.update_cell(i, 8, name)
            except Exception:
                pass

    print("Backfill complete.")

if __name__ == "__main__":
    asyncio.run(main())
