# NoPants: AI-Powered Robotic Assistant

Welcome to the central repository for **NoPants**, a DIY, fully-functional, highly interactive robotic assistant. Featuring a dual-brain architecture (Cloud LLaMA + Local Ollama), robust hardware integration, and a suite of snarky, productivity-focused smart-assistant tools, NoPants is practically a tabletop JARVIS.

![NoPants Hero Shot](Pics_&_Videos/Main_hero_pic.jpeg)
> **Meet NoPants! The ultimate DIY tabletop assistant.**

---

## 📚 The Documentation Base

We've split the documentation up into distinct, detail-heavy pages so you can learn exactly how NoPants operates behind the scenes without scrolling endlessly.

| Documentation Page | Description |
| :--- | :--- |
| **[🧠 The Architecture](docs/ARCHITECTURE.md)** | Learn about the Dual-Brain LLM system, the Master Task Agent pipelines, and the Piper Auto-Healer logic. |
| **[✨ Complete Features Breakdown](docs/FEATURES.md)** | Discover everything NoPants can do, from Google Calendar Pomodoro alerts, to Arcade web games, to streaming YouTube queue engines. |
| **[🤖 Physical Hardware & IO Map](docs/HARDWARE.md)** | Explore the ESP32 integration, including NeoPixel RGB maps, Servo animatronics protocols, and physical wiring schematics. |
| **[🚀 Setup & Installation Guide](docs/SETUP_GUIDE.md)** | Download dependencies, configure OAuth keys, and spin up the Chromium Kiosk face matrix. |

---

## 🎬 Demo Reel

See NoPants in action!

<video src="Pics_&_Videos/self_introduction.mp4" controls width="100%"></video>

> **Demo:** NoPants introduces itself — voice, face animations and all.

---

## ⚡ Quick Start Cheat Sheet

**Web Server Address (Local Network):**
`http://<SERVER_IP>:5000`
*(Example: `http://192.168.1.131:5000`)*

**Check ESP32 Hardware Port:**
```bash
ls /dev/ttyUSB*
```

**Chrome Microphone Flag:**
To allow microphone accesses over HTTP on your local network, enable this Chrome flag on your viewing device:
`chrome://flags/#unsafely-treat-insecure-origin-as-secure`