import os
import asyncio
import logging
import datetime
from dotenv import load_dotenv

from vision_agents.core import Agent, AgentLauncher, User, Runner
from vision_agents.plugins import getstream, gemini, deepgram, elevenlabs, smart_turn

load_dotenv()
logging.basicConfig(level=logging.INFO)

# ─── Global notes collector ───────────────────────────────────────────────────
session_notes = []
NOTES_FILE = None  # Will be set at session start


def init_notes_file() -> str:
    """Create the notes folder and file at session START — not at the end."""
    os.makedirs("notes", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"notes/SightNotes_{timestamp}.md"
    # Write header immediately so file exists even if 0 notes captured
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# SightNotes — Lecture Session\n\n")
        f.write(f"*Started: {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")
        f.write("---\n\n")
    logging.info(f"📁 Notes file created → {filename}")
    return filename


def append_note(filename: str, note_text: str, snapshot_num: int):
    """Append a single note snapshot to the file immediately after capture."""
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"## Snapshot {snapshot_num}\n\n")
        f.write(note_text.strip())
        f.write("\n\n---\n\n")
    logging.info(f"💾 Snapshot #{snapshot_num} written to file.")


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

        # ✅ FREE: Gemini 2.5 Flash
        llm=gemini.LLM(
            model="gemini-2.5-flash",
        ),

        # ✅ Audio pipeline
        stt=deepgram.STT(),
        tts=elevenlabs.TTS(),
        turn_detection=smart_turn.TurnDetection(),
    )

    return agent


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs):
    global session_notes, NOTES_FILE
    session_notes = []

    # ✅ Create the notes file IMMEDIATELY at session start
    NOTES_FILE = init_notes_file()

    call = await agent.create_call(call_type, call_id)

    async with agent.join(call):

        await agent.simple_response(
            "Hello! I am SightNotes. Share your screen with a lecture, PDF, or slides "
            "and I will automatically extract structured notes every 30 seconds. "
            "Say stop anytime to end the session. Your notes are saved automatically."
        )

        should_stop = {"value": False}

        # ── Voice command listener ─────────────────────────────────────────────
        async def listen_for_stop():
            try:
                async for event in agent.on("user_speech_committed"):
                    transcript = getattr(event, "text", "") or ""
                    transcript = transcript.strip().lower()
                    logging.info(f"🎤 Heard: '{transcript}'")
                    if any(w in transcript for w in ["stop", "end", "quit", "finish", "bye", "save"]):
                        logging.info("🛑 Stop command received.")
                        should_stop["value"] = True
                        await agent.simple_response(
                            f"Got it! Saved {len(session_notes)} snapshots to {NOTES_FILE}. Goodbye!"
                        )
                        break
            except Exception as e:
                logging.warning(f"Voice listener ended: {e}")

        # ── Auto-capture every 30 seconds ─────────────────────────────────────
        async def auto_capture():
            await asyncio.sleep(10)  # Wait for screen share to start

            capture_count = 0
            MAX_CAPTURES = 40  # ~20 min max

            while not should_stop["value"] and capture_count < MAX_CAPTURES:
                try:
                    logging.info(f"📸 Capturing snapshot #{capture_count + 1}...")

                    response = await agent.llm.simple_response(
                        text="Analyze the current screen and extract structured lecture notes."
                    )

                    # Safely extract text
                    note_text = ""
                    if isinstance(response, str):
                        note_text = response
                    elif hasattr(response, "text") and isinstance(response.text, str):
                        note_text = response.text
                    elif hasattr(response, "content"):
                        note_text = str(response.content)

                    if note_text and "no lecture content detected" not in note_text.lower():
                        session_notes.append(note_text)
                        capture_count += 1
                        # ✅ Write to file IMMEDIATELY — never lose a note
                        append_note(NOTES_FILE, note_text, len(session_notes))
                    else:
                        logging.info("⏭️ No lecture content, skipping.")

                except Exception as e:
                    logging.warning(f"⚠️ Capture failed: {e}")

                # Wait 30 seconds, checking stop every second
                for _ in range(30):
                    if should_stop["value"]:
                        break
                    await asyncio.sleep(1)

            # Auto-finish after MAX_CAPTURES
            if not should_stop["value"]:
                should_stop["value"] = True
                await agent.simple_response(
                    f"Session complete! Saved {len(session_notes)} snapshots to {NOTES_FILE}."
                )

        # ── Run both together ──────────────────────────────────────────────────
        try:
            await asyncio.gather(
                listen_for_stop(),
                auto_capture(),
            )
        except Exception as e:
            logging.warning(f"Session ended: {e}")

        await agent.finish()

    logging.info(f"✅ Session complete. Notes at → {NOTES_FILE}")
    logging.info(f"📊 Total snapshots captured: {len(session_notes)}")


if __name__ == "__main__":

    runner = Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
            max_sessions_per_call=1,
            agent_idle_timeout=300.0
        )
    )

    runner.cli()