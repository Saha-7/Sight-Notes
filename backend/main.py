import os
import asyncio
import logging
import datetime
import re
from dotenv import load_dotenv

from vision_agents.core import Agent, AgentLauncher, User, Runner
from vision_agents.plugins import getstream, gemini, deepgram, elevenlabs, smart_turn

load_dotenv()
logging.basicConfig(level=logging.INFO)

session_notes = []
NOTES_FILE = None
TOPIC_NAME = None


def slugify(text: str) -> str:
    words = re.sub(r'[^a-zA-Z\s]', '', text).split()
    return ''.join(w.capitalize() for w in words[:4])


def init_notes_file(topic: str = "SightNotes") -> str:
    os.makedirs("notes", exist_ok=True)
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    slug = slugify(topic)
    filename = f"notes/{slug}_{date}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {topic}\n\n")
        f.write(f"*Started: {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")
        f.write("---\n\n")
    logging.info(f"📁 Notes file → {filename}")
    return filename


def extract_topic_from_note(note_text: str) -> str:
    title_match = re.search(r'\*\*Slide Title[:\*]+\*?\*?\s*(.+)', note_text)
    if title_match:
        return title_match.group(1).strip().strip('*')
    bold_match = re.search(r'\*\*(.+?)\*\*', note_text)
    if bold_match:
        return bold_match.group(1).strip()
    concepts_match = re.search(r'### Key Concepts\n- (.+)', note_text)
    if concepts_match:
        return concepts_match.group(1).strip()
    return "SightNotes"


def rename_notes_file(old_path: str, topic: str) -> str:
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    slug = slugify(topic)
    new_path = f"notes/{slug}_{date}.md"
    try:
        os.rename(old_path, new_path)
        logging.info(f"📝 Renamed notes file → {new_path}")
        return new_path
    except Exception as e:
        logging.warning(f"Could not rename: {e}")
        return old_path


def append_note(filename: str, note_text: str, snapshot_num: int):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"## Snapshot {snapshot_num}\n\n")
        f.write(note_text.strip())
        f.write("\n\n---\n\n")
    logging.info(f"💾 Snapshot #{snapshot_num} written.")


async def create_agent(**kwargs) -> Agent:
    agent = Agent(
        edge=getstream.Edge(),
        agent_user=User(name="SightNotes", id="agent"),
        instructions="""
You are SightNotes, an AI lecture note extraction assistant.

You analyze shared screen frames from lectures, PDFs, slides, and coding sessions.

IMPORTANT RULES:
- If you can see ANY text, content, slides, code, diagrams or educational material on screen — extract it.
- Only respond with "No lecture content detected." if the screen is completely blank, shows only a desktop with no windows, or shows only system UI with zero educational content.
- Even partial slides, partially visible text, or low quality frames should be extracted if any content is visible.
- Do NOT be strict about what counts as lecture content. If in doubt, extract it.

Always respond in this EXACT format when content is visible:

### Key Concepts
- Bullet points of major concepts visible on screen

### Important Definitions
- Any definitions or explanations visible

### Important Visible Text
- Important bullet text, slide titles, headings, labels

### Code Snippets (if visible)
```
paste any visible code here
```

### Summary
2-4 sentence concise academic summary of what is shown.

### Study Questions
- Generate 2 short exam-style questions based on visible content.
""",
        llm=gemini.LLM(model="gemini-2.5-flash-lite"),
        stt=deepgram.STT(),
        tts=elevenlabs.TTS(),
        turn_detection=smart_turn.TurnDetection(),
    )
    return agent


async def join_call(agent: Agent, call_type: str, call_id: str, **kwargs):
    global session_notes, NOTES_FILE, TOPIC_NAME
    session_notes = []
    TOPIC_NAME = None

    NOTES_FILE = init_notes_file("SightNotes")

    call = await agent.create_call(call_type, call_id)

    async with agent.join(call):

        await agent.simple_response(
            "Hello! I am SightNotes. Please share your screen now with a lecture, PDF, or slides. "
            "I will automatically extract structured notes every 30 seconds. "
            "Say stop anytime to end the session."
        )

        should_stop = {"value": False}

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
                            f"Got it! Saved {len(session_notes)} snapshots. Goodbye!"
                        )
                        break
            except Exception as e:
                logging.warning(f"Voice listener ended: {e}")

        async def auto_capture():
            global NOTES_FILE, TOPIC_NAME

            # ✅ FIX 1: Wait 20s so screen share has time to fully load
            logging.info("⏳ Waiting 20 seconds for screen share to stabilize...")
            await asyncio.sleep(20)

            capture_count = 0
            MAX_CAPTURES = 120  # 120 x 30s = 60 minutes max

            while not should_stop["value"] and capture_count < MAX_CAPTURES:
                try:
                    logging.info(f"📸 Capturing snapshot #{capture_count + 1}...")

                    # ✅ FIX 2: More aggressive prompt — don't skip partial content
                    response = await agent.llm.simple_response(
                        text=(
                            "Look at the current screen carefully. "
                            "Extract all visible lecture content, slide text, code, or educational material. "
                            "Follow the exact format in your instructions. "
                            "If you see ANY educational content at all, extract it — do not skip partial content."
                        )
                    )

                    note_text = ""
                    if isinstance(response, str):
                        note_text = response
                    elif hasattr(response, "text") and isinstance(response.text, str):
                        note_text = response.text
                    elif hasattr(response, "content"):
                        note_text = str(response.content)

                    note_text = note_text.strip()

                    if note_text and "no lecture content detected" not in note_text.lower():
                        session_notes.append(note_text)
                        capture_count += 1
                        logging.info(f"✅ Content captured! Snapshot #{capture_count}")

                        # On first snapshot, detect topic and rename file
                        if capture_count == 1 and TOPIC_NAME is None:
                            TOPIC_NAME = extract_topic_from_note(note_text)
                            logging.info(f"📌 Topic detected: {TOPIC_NAME}")
                            NOTES_FILE = rename_notes_file(NOTES_FILE, TOPIC_NAME)
                            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                                content = f.read()
                            content = content.replace("# SightNotes", f"# {TOPIC_NAME}", 1)
                            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                                f.write(content)

                        append_note(NOTES_FILE, note_text, len(session_notes))

                    else:
                        logging.info("⏭️ No lecture content — make sure your PDF or slide is visible on screen!")

                except Exception as e:
                    err = str(e)
                    # ✅ FIX 3: Handle rate limits gracefully
                    if "429" in err or "quota" in err.lower():
                        logging.warning("⏳ Rate limit hit — waiting 60 seconds before retrying...")
                        await asyncio.sleep(60)
                        continue
                    else:
                        logging.warning(f"⚠️ Capture error: {e}")

                # Wait 30 seconds between captures
                for _ in range(30):
                    if should_stop["value"]:
                        break
                    await asyncio.sleep(1)

            if not should_stop["value"]:
                should_stop["value"] = True
                await agent.simple_response(
                    f"Session complete! Saved {len(session_notes)} snapshots."
                )

        try:
            await asyncio.gather(listen_for_stop(), auto_capture())
        except Exception as e:
            logging.warning(f"Session ended: {e}")

        await agent.finish()

    logging.info(f"✅ Done. Notes at → {NOTES_FILE}")
    logging.info(f"📊 Total snapshots: {len(session_notes)}")


if __name__ == "__main__":
    runner = Runner(
        AgentLauncher(
            create_agent=create_agent,
            join_call=join_call,
            max_sessions_per_call=1,
            agent_idle_timeout=600.0  # ✅ FIX 4: 10 min idle timeout
        )
    )
    runner.cli()


