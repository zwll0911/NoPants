# 🤖 NoPants OS: The AI-Powered Desktop Assistant

Welcome to the central repository for **NoPants**, a fully functional, highly interactive robotic desktop assistant. Built on a "Dual-Brain" AI architecture, NoPants bridges the gap between hardware and software, acting as a proactive tabletop companion.

![NoPants Hero Shot](Pics_&_Videos/Main_hero_pic.jpeg)

## 🌟 Overview

NoPants OS is not just a standard chatbot—it is a comprehensive **Task Execution Engine**. It features a custom Python/Flask WebSockets server that routes complex voice commands, controls physical hardware (via an ESP32), and renders a beautiful, real-time Glassmorphism holographic UI.

Whether you need to manipulate smart home lights, manage a Pomodoro study session, dynamically schedule Google Calendar events, or just want to hear a joke, NoPants processes the request instantly.

## 📚 Documentation Directory

To keep this repository clean, the detailed technical breakdowns of NoPants' subsystems have been divided into the following documents:

* **[Architecture & AI Logic](docs/ARCHITECTURE.md):** Deep dive into the Dual-Brain LLM routing (Groq + Ollama), the JSON Task Queue, and the Piper offline TTS engine.
* **[Features & Capabilities](docs/FEATURES.md):** Detailed explanations and code snippets of the Proactive Calendar Monitor, Live Weather extraction, and VLC Music Queue.
* **[Hardware & ESP32 Firmware](docs/HARDWARE.md):** Schematics, C++ serial parsing logic, and how the physical buttons/knobs act as system overrides.
* **[Setup & Installation Guide](docs/SETUP_GUIDE.md):** Step-by-step instructions on how to install dependencies, configure API keys, and boot NoPants OS on a Raspberry Pi.

## 📸 Interface Sneak Peek

The system features a dynamically animated face running in Chromium Kiosk Mode, paired with a web-based Command Center for system monitoring and "Subconscious" memory injection.

| Holographic AI Theme | Active Protocols Dashboard |
|:---:|:---:|
| ![Theme](Pics_&_Videos/Holographic_AI_theme_skin.jpeg) | ![Protocols](Pics_&_Videos/active_protocols_pic.jpeg) |

---
*If you like this project, feel free to drop a ⭐ on the repository!*
