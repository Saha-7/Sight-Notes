# SightNotes 👁️

An AI agent that watches your screen during lectures and automatically extracts structured notes every 30 seconds. No typing. No pausing. Just learn.

Built for the **Vision Possible: Agent Protocol** hackathon.

---

## What it does

You join a video call, share your screen with a lecture PDF or slides, and SightNotes silently captures a frame every 30 seconds. It sends that frame to Gemini, which reads the slide like a student would — pulling out key concepts, definitions, code snippets, a summary, and study questions. Everything gets saved to a markdown file and shown live in a React frontend.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     YOU                             │
│   (Browser tab — Stream demo UI)                    │
│   • Share screen → lecture PDF / slides             │
│   • Speak to control ("stop", "save")               │
└──────────────┬──────────────────────────────────────┘
               │ WebRTC (video + audio)
               ▼
┌─────────────────────────────────────────────────────┐
│           Stream Vision Agents SDK                  │
│   • Manages the call room                           │
│   • Receives screen share stream                    │
│   • Captures frames on demand                       │
│   • Routes audio to Deepgram / ElevenLabs           │
└────┬──────────────┬────────────────┬────────────────┘
     │              │                │
     ▼              ▼                ▼
 Gemini 2.5     Deepgram STT    ElevenLabs TTS
 Flash Lite      (your mic)      (agent voice)
 (reads slide)   transcribes     speaks back
     │
     ▼
┌─────────────────────┐
│  notes/*.md file    │  ← topic-named, timestamped
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐      ┌──────────────────────┐
│  Flask API Server   │ ←──  │  React Frontend      │
│  api_server.py      │ GET  │  localhost:5173      |
│  localhost:5001     │      │  Live + Sessions tabs│
└─────────────────────┘      └──────────────────────┘
```

---

## Tech Stack

| Part | What it does |
|---|---|
| Stream Vision Agents SDK | WebRTC call infrastructure + video pipeline |
| Google Gemini 2.5 Flash Lite | Reads screen frames, extracts notes (multimodal) |
| Deepgram | Speech-to-text — hears your voice commands |
| ElevenLabs | Text-to-speech — agent speaks back to you |
| Flask + CORS | Mini API server serving notes to frontend |
| React + Vite | Frontend showing live and past sessions |

---

## Getting API Keys

You need 5 things. Here's where to get each one.

### 1. Stream API Key + Secret
- Go to [getstream.io](https://getstream.io) → sign up free
- Create a new app → copy the **API Key** and **Secret**
- These let Stream create the video call room and WebRTC connection

### 2. Google Gemini API Key
- Go to [aistudio.google.com](https://aistudio.google.com) → sign in
- Click **Get API Key** → create one
- Free tier: **1000 requests/day** on `gemini-2.5-flash-lite` (what we use)
- ⚠️ Don't use `gemini-2.5-flash` — only 20 req/day free

### 3. Deepgram API Key
- Go to [console.deepgram.com](https://console.deepgram.com) → sign up
- Create a new API key from the dashboard
- Free tier is enough for testing

### 4. ElevenLabs API Key
- Go to [elevenlabs.io](https://elevenlabs.io) → sign up free
- Go to **Profile → API Key** → copy it
- Free tier gives 10,000 credits (enough for many sessions)
- If you hit the limit, create a new account with a different email

### 5. HuggingFace Token (required by vision-agents)
- Go to [huggingface.co](https://huggingface.co) → sign up → Settings → Access Tokens
- Create a **Read** token
- The vision-agents SDK needs this internally even if you don't call HF directly

---

## Setup

### Backend

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install vision-agents[getstream,huggingface,deepgram] python-dotenv flask flask-cors
```

Create `backend/.env`:

```env
STREAM_API_KEY=your_stream_api_key
STREAM_API_SECRET=your_stream_api_secret
GOOGLE_API_KEY=your_gemini_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
HUGGINGFACE_TOKEN=your_hf_token
```

### Frontend

```bash
cd frontend
npm install
```

---

## Running it

You need 3 terminals open at the same time.

**Terminal 1 — Vision Agent:**
```bash
cd backend
.\venv\Scripts\activate   # or source venv/bin/activate on Mac/Linux
python main.py run
```

**Terminal 2 — Flask API:**
```bash
cd backend
.\venv\Scripts\activate
python api_server.py
```

**Terminal 3 — React Frontend:**
```bash
cd frontend
npm run dev
```

Then open [localhost:5173](http://localhost:5173) in your browser.

---

## How to use it

1. Run all 3 terminals (agent, API, frontend)
2. The agent auto-opens a browser tab — join the Stream call
3. **Important:** Open your lecture PDF or slides *before* clicking share screen
4. Click **Share Screen** → choose the **Window** tab → pick your PDF window specifically (not entire screen — this matters for video quality)
5. Wait about 20-40 seconds for the first snapshot
6. Watch notes appear in the frontend automatically
7. Say "stop" to end the session (or press Ctrl+C in terminal)

Notes are saved to `backend/notes/` with the lecture topic as the filename.

---

## Problems I ran into

**Gemini kept saying "no lecture content detected"**  
The first capture was firing too fast — only 6 seconds after screen share started. The video frames weren't stable yet. Fixed it by waiting 20 seconds before the first capture instead of 10.

**H264 decode warnings in terminal**  
Windows + full screen share = video codec issues. Switched to sharing a specific window instead of the entire screen. Worked perfectly after that.

**ElevenLabs quota exhausted**  
Free tier gives 10,000 credits. A single "Hello" from the agent costs about 28. Used them up during testing. Solution: new account with different email, or just note it only affects the agent's voice — notes still save fine without it.

**Gemini 20 requests/day limit**  
Was using `gemini-2.5-flash` which only allows 20 free requests per day. Switched to `gemini-2.5-flash-lite` which allows 1000/day — way more than enough.

**Voice "stop" command not working**  
`agent.on("user_speech_committed")` event doesn't exist in the Vision Agents SDK version we're using. The voice listener fails silently. Workaround: press Ctrl+C in the terminal to stop. The notes still save correctly.

**Notes file staying named "SightNotes"**  
Topic detection only runs after the first successful snapshot. If Gemini quota was exhausted during early testing, no snapshots were captured, so the file never got renamed. Solved itself once the quota reset.

---

## Session limits

| Setting | Value |
|---|---|
| Captures every | 30 seconds |
| Max captures | 120 |
| Max session length | 60 minutes |
| Gemini free requests/day | 1000 (flash-lite) |

To change session length, edit `MAX_CAPTURES` in `backend/main.py`.

---

## Future scope

**Audio understanding** — Right now SightNotes only sees the screen. The most natural next step is capturing system audio too, so it can hear the lecturer's voice along with reading the slides. That would give truly complete lecture coverage.

**Flashcard export** — After a session, automatically convert the study questions into Anki flashcards or a quiz. Close the loop between passive watching and active studying.

**Notion / Google Docs integration** — One-click export instead of a local markdown file. Students already live in Notion.

**Multi-session linking** — If you attend 5 ML lectures across different days, detect they're related and merge them into one master knowledge base.

**Real-time Q&A** — Ask the agent mid-lecture: *"explain gradient descent from what was just shown"* — and it answers based on the current screen context.

---

## Project structure

```
SightNotes/
├── backend/
│   ├── main.py          # Vision agent — captures + extracts notes
│   ├── api_server.py    # Flask API serving notes to frontend
│   ├── requirements.txt
│   ├── .env             # your API keys (not committed)
│   └── notes/           # saved markdown files per session
└── frontend/
    ├── src/
    │   ├── App.jsx      # main UI — Live and Sessions views
    │   ├── App.css      # editorial cream/white theme
    │   └── index.css    # resets
    ├── package.json
    └── vite.config.js
```

---

## Made for

Vision Possible: Agent Protocol Hackathon — WeMakeDevs × Stream  
February 23 – March 1, 2026