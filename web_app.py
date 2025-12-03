import asyncio
import os
from typing import Dict, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from claude_agent_sdk import (  # noqa: E402
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)
from agent_video import video_tools_server  # noqa: E402
from agent_video.prompts import SYSTEM_PROMPT  # noqa: E402


app = FastAPI(title="Agent Video to Data")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# --------------------------------------------------------------------------
# Session Management (Actor Pattern)
# --------------------------------------------------------------------------

class SessionActor:
    """
    A dedicated actor that runs the ClaudeSDKClient in its own asyncio task.
    This prevents 'cancel scope' errors by ensuring the client is always
    accessed from the same task context.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.response_queue: asyncio.Queue = asyncio.Queue()
        self.greeting_queue: asyncio.Queue = asyncio.Queue()
        self.active_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        """Starts the background worker task."""
        self.is_running = True
        self.active_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """Signals the worker to stop and waits for it to finish."""
        if not self.is_running:
            return
        
        self.is_running = False
        # Send a sentinel to unblock the queue waiter
        await self.input_queue.put(None)
        
        if self.active_task:
            try:
                await self.active_task
            except asyncio.CancelledError:
                pass
            self.active_task = None

    async def get_greeting(self) -> str:
        """Waits for and returns the initial greeting message."""
        if not self.is_running:
             raise RuntimeError("Session is closed")
        
        # Wait for greeting (populated on startup)
        # We peek/get it. Since we only need it once, get is fine.
        # But if we call it multiple times, we might want to store it?
        # For now, assuming called once per session init.
        # To be safe against race conditions or timeouts:
        try:
            greeting = await asyncio.wait_for(self.greeting_queue.get(), timeout=30.0)
            # Put it back in case other calls need it (optional, but good for idempotency)
            # await self.greeting_queue.put(greeting) 
            # Actually, let's just return it. The frontend calls init once.
            return greeting
        except asyncio.TimeoutError:
            return "Hello! I'm ready to help (Greeting timed out)."

    async def process_message(self, message: str) -> str:
        """Sends a message to the agent and awaits the full text response."""
        if not self.is_running or not self.active_task:
            raise RuntimeError("Session is closed")
            
        await self.input_queue.put(message)
        
        # Wait for the result from the response queue OR for the worker to crash
        # This prevents hanging indefinitely if the worker fails
        get_response = asyncio.create_task(self.response_queue.get())
        
        done, pending = await asyncio.wait(
            [get_response, self.active_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        if get_response in done:
            # We got a response (or an error passed through the queue)
            result = get_response.result()
            if isinstance(result, Exception):
                raise result
            return result
        else:
            # The worker task finished/crashed before sending a response
            get_response.cancel()
            try:
                # Retrieve the exception from the task if it failed
                await self.active_task
            except Exception as e:
                raise RuntimeError(f"Session worker crashed: {e}")
            
            raise RuntimeError("Session worker stopped unexpectedly")

    async def _worker_loop(self):
        """The main loop that holds the ClaudeSDKClient context."""
        print(f"Session {self.session_id}: Worker started")
        
        try:
            options = ClaudeAgentOptions(
                system_prompt=SYSTEM_PROMPT,
                mcp_servers={"video-tools": video_tools_server},
                allowed_tools=[
                    "mcp__video-tools__transcribe_video",
                    "mcp__video-tools__write_file",
                ],
                max_turns=50,
            )

            async with ClaudeSDKClient(options) as client:
                # 1. Handle Initial Greeting
                initial_prompt = (
                    "Start the conversation by greeting me and asking for a video "
                    "to transcribe. Follow your workflow."
                )
                await client.query(initial_prompt)
                
                greeting_text = []
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                greeting_text.append(block.text)
                
                # Make greeting available to get_greeting()
                await self.greeting_queue.put("\n".join(greeting_text))
                
                print(f"Session {self.session_id}: Ready for input")

                # 2. Main Event Loop
                while self.is_running:
                    # Wait for input (message or None for shutdown)
                    user_message = await self.input_queue.get()
                    
                    if user_message is None:
                        # Shutdown signal
                        break

                    # Process the user message
                    try:
                        await client.query(user_message)
                        
                        full_text = []
                        async for message in client.receive_response():
                            if isinstance(message, AssistantMessage):
                                for block in message.content:
                                    if isinstance(block, TextBlock):
                                        full_text.append(block.text)
                        
                        # Send result back to the waiting HTTP handler
                        await self.response_queue.put("\n".join(full_text))
                        
                    except Exception as e:
                        print(f"Session {self.session_id}: Error processing message: {e}")
                        await self.response_queue.put(e)

        except Exception as e:
            print(f"Session {self.session_id}: Worker crashed: {e}")
        finally:
            print(f"Session {self.session_id}: Worker shutdown")


# In-memory storage for active sessions
active_sessions: Dict[str, SessionActor] = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str
    session_id: str

class InitRequest(BaseModel):
    session_id: str


async def get_or_create_session(session_id: str) -> SessionActor:
    """Retrieves an existing session or spawns a new actor."""
    if session_id in active_sessions:
        actor = active_sessions[session_id]
        if actor.is_running:
            return actor
        else:
            # Clean up dead session
            del active_sessions[session_id]

    print(f"Initializing new session actor: {session_id}")
    
    # Check API keys before starting
    if not os.environ.get("ANTHROPIC_API_KEY"):
         raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set on server.")

    actor = SessionActor(session_id)
    await actor.start()
    active_sessions[session_id] = actor
    return actor

# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat/init", response_model=ChatResponse)
async def chat_init(request: InitRequest):
    """Initializes the session and returns the greeting message."""
    try:
        actor = await get_or_create_session(request.session_id)
        greeting = await actor.get_greeting()
        return ChatResponse(
            response=greeting,
            session_id=request.session_id
        )
    except Exception as e:
        print(f"Error in chat init: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        actor = await get_or_create_session(request.session_id)
        
        # Send message to actor and await response
        response_text = await actor.process_message(request.message)
        
        return ChatResponse(
            response=response_text,
            session_id=request.session_id
        )
        
    except Exception as e:
        print(f"Error in chat processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    if session_id in active_sessions:
        actor = active_sessions.pop(session_id)
        await actor.stop()
    return {"status": "success", "message": f"Session {session_id} closed"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)
