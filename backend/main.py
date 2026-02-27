import logging
from dotenv import load_dotenv

from vision_agents.core import Agent, AgentLauncher, User, Runner
from vision_agents.plugins import getstream, nvidia, deepgram, elevenlabs

load_dotenv()
logging.basicConfig(level=logging.INFO)


async def create_agent(**kwargs) -> Agent:
    """
    Factory function to create SightNotes agent.
    """

    agent = Agent(
        edge=getstream.Edge(),

        agent_user=User(
            name="SightNotes",
            id="agent"
        ),

        instructions="""
        You are SightNotes, an AI lecture assistant.

        You analyze:
        - Live video frames (slides, code, diagrams)
        - Live spoken speech

        Your job:
        1. Extract key concepts
        2. Extract important visible slide text
        3. Extract visible code snippets
        4. Generate structured lecture notes

        Always respond in this format:

        ### Key Concepts
        - ...

        ### Important Slide Text
        - ...

        ### Code Snippets
        - ...

        ### Summary
        Short academic summary.

        Be concise. Avoid repetition.
        """,

        # 🔥 NVIDIA Cosmos Vision-Language Model
        llm=nvidia.VLM(
            model="nvidia/cosmos-reason2-8b",
            fps=1,
            frame_buffer_seconds=8,
        ),

        # 🎤 Speech-to-Text
        stt=deepgram.STT(
            eager_turn_detection=True
        ),

        # 🔊 Text-to-Speech
        tts=elevenlabs.TTS(),

    )

    return agent


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs):
    """
    Called when the agent joins a call.
    """

    call = await agent.create_call(call_type, call_id)

    async with agent.join(call):

        await agent.simple_response(
            "Hello. I am SightNotes. I am ready to analyze your lecture."
        )

        await agent.finish()


if __name__ == "__main__":

    runner = Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
            max_sessions_per_call=1,
            agent_idle_timeout=120.0
        )
    )

    runner.cli()