import sys
import asyncio
import uvicorn

if __name__ == "__main__":
    if sys.platform == "win32":
        # Force ProactorEventLoop on Windows for Playwright subprocess support
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    # Start the server
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
