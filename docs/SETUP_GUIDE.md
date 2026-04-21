# 🚀 Setup & Installation Guide

Setting up your very own NoPants robot involves configuring Python dependencies, a few Linux Audio commands, API authentication, and Google Workspace OAuth. 

Follow this guide step-by-step to bring your desktop assistant to life!

---

## 🐧 1. System Requirements & Core Packages

We highly recommend running the NoPants server on a Linux-based Single Board Computer (like a Raspberry Pi 4 or 5) because the system relies heavily on native Linux ALSA audio configurations and headless VLC processes.

Open your terminal and install the core media frameworks required for Piper TTS, YouTube audio streaming, and the Kiosk display:
```bash
sudo apt update
sudo apt install vlc sox libsox-fmt-all chromium-browser python3-virtualenv
```

---

## 🐍 2. Python Environment

We strongly recommend running NoPants inside a virtual environment to prevent package conflicts with your OS.

1. **Create and activate the environment:**
```bash
python3 -m venv nopants_env
source nopants_env/bin/activate
```

2. **Install the required libraries:**
Ensure your `requirements.txt` contains the following dependencies, then run `pip install`:
```text
Flask==3.0.0
Flask-SocketIO==5.3.6
pyserial==3.5
psutil==5.9.6
yt-dlp==2023.11.16
duckduckgo-search==3.9.3
groq==0.4.2
google-auth-oauthlib==1.1.0
google-api-python-client==2.108.0
dateparser==1.2.0
pytz==2023.3.post1
```
```bash
pip install -r requirements.txt
```

---

## 🧠 3. The Dual-Brain AI Setup

NoPants requires both a Cloud API key and a Local LLM for its fallback architecture.

### Primary Brain: Groq Cloud
1. Generate a free API Key from [console.groq.com](https://console.groq.com/).
2. You do not need to hardcode this! Once the server boots, access the web dashboard via `http://<YOUR_PI_IP>:5000/settings`.
3. Paste your Groq API key into the "Core Matrix" settings tab and click **Flash Core Matrix**.

### Secondary Brain: Local Ollama (Offline Fallback)
If your internet drops, NoPants will attempt to route prompts to a local LLM. You must have Ollama installed and running on the default port (`11434`).
```bash
# Install Ollama (if not already installed)
curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh

# Pull and run the lightweight Llama 3.2 model
ollama run llama3.2:1b
```

---

## 📅 4. Google Calendar OAuth

To enable proactive meeting alerts and conversational event scheduling, you must authorize Google Workspace APIs.

1. Head to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and enable the **Google Calendar API**.
3. Configure the OAuth Consent Screen (set it to "Desktop App").
4. Download your OAuth Client ID as `credentials.json` and place it in the root of your `nopants` directory.
5. **First Boot Authentication:** When you run `server_nopants.py` for the first time, the terminal will pause and output a Google authorization URL. Click the URL, log into your Google account, and approve the scopes. The server will generate a secure `token.json` file, and you will never have to do this again.

---

## 🗣️ 5. Piper Text-to-Speech Setup

**You do NOT need to manually download Piper voice models!**

The Python backend contains a strict Auto-Healing script. When the server boots, it will check for `en_US-ryan-medium.onnx` inside the `./piper/` directory. 

If the 60MB file is missing or corrupted, the server will automatically formulate the correct HuggingFace repository URL and securely download the `.onnx` and `.json` configuration files via `wget` before initializing the web server. 

*(Just ensure your Raspberry Pi is connected to the internet on the very first boot!)*

---

## ⚡ 6. Running the Application

Before booting, ensure the ESP32 Main Hub is plugged into the Raspberry Pi via USB. Verify the port identifier:
```bash
ls /dev/ttyUSB*
```
*(The `server_nopants.py` script defaults to `/dev/ttyUSB0`. If your system mounts it differently, update line 63 in the Python script).*

**Start the OS:**
```bash
python3 server_nopants.py
```

*Within 2 seconds, the server will automatically launch Chromium in full-screen Kiosk Mode, render the holographic face, and begin polling the hardware!*
