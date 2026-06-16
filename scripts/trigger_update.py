import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.components.sheet_manager import SheetManager

async def main():
    sm = SheetManager()
    await sm.initialize()
    await sm.update_dashboard()
    print("Dashboard updated.")

if __name__ == "__main__":
    asyncio.run(main())
