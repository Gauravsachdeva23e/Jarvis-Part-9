from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext, ChatMessage
from livekit.plugins import google, noise_cancellation

# Import your custom modules
from Jarvis_prompts import instructions_prompt, Reply_prompts
from memory_loop import MemoryExtractor
# from jarvis_reasoning import thinking_capability
from mcp_client.server import MCPServerSse
from mcp_client.agent_tools import MCPToolsIntegration
import os
from mem0 import AsyncMemoryClient
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mem0_client = AsyncMemoryClient()
user_id = "Gaurav_22"


load_dotenv()


class Assistant(Agent):
    def __init__(self, chat_ctx) -> None:
        super().__init__(instructions=instructions_prompt,
                         chat_ctx= chat_ctx,
                         llm= google.beta.realtime.RealtimeModel(
                             model="gemini-2.5-flash-native-audio-preview-12-2025",
                             voice="Charon"
                         )
        )

async def entrypoint(ctx: agents.JobContext):

    # 4. STARTUP MEMORY: Fetch existing memories before the agent starts
    logger.info(f"Fetching initial memories for user: {user_id}")
    try:
        # Get all memories or perform a general search to prime the agent
        all_memories = await mem0_client.get_all(user_id=user_id)
        
        # Format them into a string
        memory_str = "\n".join([m.get('memory', '') or m.get('text', '') for m in all_memories])
        if memory_str:
            memory_str = f"\n\nKNOWN USER HISTORY:\n{memory_str}"
        else:
            memory_str = "\n(No previous history found.)"
            
    except Exception as e:
        logger.error(f"Error fetching initial memories: {e}")
        memory_str = "\n(Memory system unavailable)"

    # 5. Configure the Session
    session = AgentSession(
        preemptive_generation=True
    )
    #getting the current memory chat
    current_ctx = session.history.items

    # 6. Inject the startup memory into the context
    initial_ctx = ChatContext()
    initial_ctx.add_message(role="assistant", 
                            content=f'''The user's name is {user_id}.
                            {memory_str}''')
    
    await session.start(
        room=ctx.room,
        agent=Assistant(chat_ctx = initial_ctx), #sending currenet chat to llm in realtime
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )
    await session.generate_reply(
        instructions=Reply_prompts
    )
    conv_ctx = MemoryExtractor()
    await conv_ctx.run(current_ctx)
    


if __name__ == "__main__":
    import sys
    import asyncio
    
    # --- Windows Specific Fix ---
    if sys.platform == "win32":
        # Force the use of ProactorEventLoop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        # Create a loop manually to avoid the "no current event loop" error
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    # ----------------------------

    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))

    