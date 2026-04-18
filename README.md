# NoPants: AI-Powered Robotic Desktop Assistant

**NoPants** is a DIY fully-functional, highly interactive robotic assistant. Featuring dual-brain architecture (Cloud & Local LLMs), complex hardware integration, real-time web UI, and a suite of smart-assistant tools, NoPants is practically a tabletop JARVIS.

## 🌟 Comprehensive Feature List

### 🧠 The AI Brain
* **Dual-Brain Architecture**: Uses Groq API (LLaMA-3.1-8b-instant) for lightning-fast cloud inference, and instantly falls back to a locally hosted Ollama instance (`llama3.2:1b`) if the internet drops.
* **Master Task Agent**: Employs an LLM strictly to parse complex user requests into a queue of actionable JSON tasks (e.g., executing multiple tasks sequentially like searching the web, then changing smart lights, then setting a timer).
* **Persistent Long-Term Memory**: The AI automatically extracts personal facts, preferences, and names from conversation, storing up to 30 facts in `user_memory.json` to retain long-term continuity without prompt bloat.

### 🔌 Hardware Integration (via ESP32)
* **Serial Communication**: Interfaces with an ESP32 microcontroller over `/dev/ttyUSB1`.
* **Animatronic Ears**: Hardware control for "UP", "FLAT", and "SHAKE" animations based on emotion and state.
* **RGB LED Visual Responses**: Color-coded feedback (Cyan for listening, Red for alarms/errors, Pink for party tricks, Green for success).
* **Physical Controls**:
  * **Rotary Knob**: Live volume control using Linux `amixer`.
  * **Walkie-Talkie Button**: Instantly triggers the microphone to listen for commands.
  * **Panic Button**: Immediately kills all talking, alarms, timers, and music across standard Linux systems.
  * **Party Trick Button**: Automatically generates a tiny 1-sentence joke/fact and performs an animatronic sequence with pink LEDs.

### 🎭 Voice & Personality Display
* **Offline Text-to-Speech (Piper)**: Generates highly responsive, offline voice lines. Automatically shapes the audio using `vlc`, `play`, and `sox` to shift pitch/tempo to achieve a "cartoon" voice.
* **Auto-Healing TTS Models**: If the `onnx` voice models go missing or corrupt, the script dynamically redownloads them from HuggingFace to prevent crashes.
* **Kiosk Interface (`/face`)**: Automatically launches Chromium in Kiosk mode. Connects over WebSockets for live UI updates, syncing mouth movements/head-bobbing to the audio output and music.

### 📅 Smart Integrations & Assistants
* **Proactive Google Calendar Monitor**: Uses Google OAuth to quietly check for upcoming meetings. At exactly 5 minutes before a meeting, the robot wakes up and dynamically yells a warning at the user using the LLM.
* **Calendar Management**: The LLM can parse and convert conversational sentences (e.g., "Schedule a party for tomorrow at 5") into relative dates, creating real events on the user's primary Google Calendar.
* **Pomodoro / Study Mode**: Enables "Do Not Disturb" (blocking calendar alerts), starts a 25-minute visual timer, turns LEDs to a calm color, and automatically streams Lo-Fi Hip Hop until the timer is complete.
* **Live Web Search**: Uses DuckDuckGo search strings (`DDGS`) to scrape the top 3 results from the past week, feeding the raw HTML text to the LLM to get a 30-word summarized answer.
* **Instant Weather**: Uses `wttr.in` combined with LLM city-extraction to fetch and announce the live local forecast.

### 🎵 Media & Time Management
* **YouTube Music Engine (`yt-dlp`)**: Streams music entirely ad-free natively using `cvlc`. Supports queueing multiple tracks ("add this to queue"), clearing queues, and asking the robot "what song is playing right now?".
* **Background Alarm Monitor**: Allows users to set repeating daily/weekly alarms, or recurring interval reminders (e.g., "remind me to drink water every hour").
* **Dashboard & Settings**: A local `/settings` interface allows dynamic modification of Groq API keys, robot persona configurations, deletion of alarms, and scrubbing the user memory bank.
* **Arcade Mode**: A dedicated `/game` dashboard for playing web games with a persistent leaderboard matrix. Includes real-time hardware pass-through mode so games can potentially be played with the hardware controls.

---

## 🛠️ Quick Start & Dev Notes

**Web Server Address (Local Network):**  
`http://<SERVER_IP>:5000`  
*(Example: `http://192.168.1.131:5000`)*

**Check ESP32 Hardware Port:**  
If the hardware isn't responding, check your Linux USB ports. Ensure your `server_nopants.py` matches the correct port.
```bash
ls /dev/ttyUSB*
```

**Testing on external devices (Chrome Warning):**  
To allow microphone accesses over HTTP within your local network, enable this Chrome flag on your viewing device and add your IP.
`chrome://flags/#unsafely-treat-insecure-origin-as-secure`