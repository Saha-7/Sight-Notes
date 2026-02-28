import os
import asyncio
import logging
import datetime
from dotenv import load_dotenv

from vision_agents.core import Agent, AgentLauncher, User, Runner
from vision_agents.plugins import getstream, huggingface, deepgram, elevenlabs, smart_turn

load_dotenv()
logging.basicConfig(level=logging.INFO)

# ─── Global notes collector ───────────────────────────────────────────────────
session_notes = []


async def create_agent(**kwargs) -> Agent:

    agent = Agent(
        edge=getstream.Edge(),

        agent_user=User(
            name="SightNotes",
            id="agent"
        ),

        instructions="""
You are SightNotes, an AI lecture extraction assistant.

You analyze shared screen frames from lectures, PDFs, slides, and coding sessions.

Your task:
1. Extract only meaningful academic content.
2. Ignore UI elements, browser bars, watermarks, timestamps, or irrelevant overlays.
3. Focus only on lecture material.

Always respond in this EXACT format:

### Key Concepts
- Bullet points of major concepts

### Important Definitions
- Clearly visible definitions

### Important Visible Text
- Important bullet text or slide titles

### Code Snippets (if visible)
- Short extracted code fragments

### Summary
2-4 sentence concise academic summary.

### Study Questions
- Generate 2 short exam-style questions from visible content.

Rules:
- Be structured and concise.
- Avoid repetition.
- Do NOT hallucinate unseen content.
- If the screen does not show lecture content, respond ONLY with: "No lecture content detected."
""",

        # ✅ HuggingFace VLM - Llava is the most supported model for HF inference
        llm=huggingface.VLM(
            model="llava-hf/llava-1.5-7b-hf",
            fps=1,
            frame_buffer_seconds=5,
        ),

        # ✅ Audio pipeline satisfies SDK requirement
        stt=deepgram.STT(),
        tts=elevenlabs.TTS(),
        turn_detection=smart_turn.TurnDetection(),
    )

    return agent


def save_notes(notes: list) -> str:
    """Save collected notes to a markdown file. Returns filename or None."""
    if not notes:
        return None

    os.makedirs("notes", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"notes/SightNotes_{timestamp}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# SightNotes — Lecture Session\n\n")
        f.write(f"*Generated: {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")
        f.write("---\n\n")
        for i, note in enumerate(notes, 1):
            f.write(f"## Snapshot {i}\n\n")
            f.write(note.strip())
            f.write("\n\n---\n\n")

    logging.info(f"✅ Notes saved → {filename}")
    return filename


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs):
    global session_notes
    session_notes = []

    call = await agent.create_call(call_type, call_id)

    async with agent.join(call):

        # ── Welcome message ────────────────────────────────────────────────────
        await agent.simple_response(
            "Hello! I am SightNotes. Please share your screen with a lecture, "
            "PDF, or slides. I will automatically extract structured notes every "
            "30 seconds. Just share your screen and I will get started."
        )

        # ── Wait for participant to join and share screen ──────────────────────
        logging.info("⏳ Waiting 10 seconds for screen share to start...")
        await asyncio.sleep(10)

        # ── Auto-capture loop: fires every 30 seconds ──────────────────────────
        capture_count = 0
        MAX_CAPTURES = 20  # Safety limit: 20 captures = ~10 minutes

        while capture_count < MAX_CAPTURES:
            try:
                logging.info(f"📸 Capturing screen snapshot #{capture_count + 1}...")

                # Ask VLM to analyze the current screen frame
                response_text = await agent.llm.simple_response(
                    text="Analyze the current screen frame and extract structured lecture notes."
                )

                if response_text and "no lecture content detected" not in response_text.lower():
                    session_notes.append(response_text)
                    capture_count += 1
                    logging.info(f"✅ Note #{len(session_notes)} captured successfully.")
                else:
                    logging.info("⏭️ No lecture content detected in this frame, skipping.")

            except Exception as e:
                logging.warning(f"⚠️ Capture #{capture_count + 1} failed: {e}")

            # ── Wait 30 seconds before next capture ───────────────────────────
            await asyncio.sleep(30)

        # ── Session end: save notes ────────────────────────────────────────────
        filename = save_notes(session_notes)
        if filename:
            await agent.simple_response(
                f"Session complete. I have captured {len(session_notes)} note "
                f"snapshots and saved them to {filename}. Goodbye!"
            )
        else:
            await agent.simple_response(
                "Session complete. No lecture content was detected. "
                "Make sure to share your screen next time. Goodbye!"
            )

        await agent.finish()

    # ── Safety net: auto-save if session ends unexpectedly ────────────────────
    if session_notes:
        save_notes(session_notes)


if __name__ == "__main__":

    runner = Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
            max_sessions_per_call=1,
            agent_idle_timeout=300.0   # 5 min idle timeout
        )
    )

    runner.cli()