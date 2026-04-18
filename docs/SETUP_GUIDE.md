# 🚀 Setup & Installation Guide

Setting up your very own NoPants robot involves configuring Python dependencies, a few Linux Audio commands, and API authentication.

---

## 1. System Requirements & Dependencies

We highly recommend running NoPants on a Linux-based SBC (like a Raspberry Pi) since it relies on native Linux ALSA audio configurations.

### Install System Packages
Open your terminal and install the core media frameworks required for Piper TTS and Music playback:
```bash
sudo apt update
sudo apt install vlc sox libsox-fmt-all chromium-browser python3-virtualenv
```

### Setup Python Environment
We recommend running NoPants inside a virtual environment to prevent package conflicts.
```bash
python3 -m venv nopants_env
source nopants_env/bin/activate
pip install -r requirements.txt
```
*(Ensure `requirements.txt` contains `Flask`, `Flask-SocketIO`, `pyserial`, `psutil`, `yt-dlp`, `duckduckgo-search`, `groq`, etc.)*

---

## 2. API Keys & Configurations

NoPants requires some cloud authentication. All configurations are located in `config.json`.

1. Generate a **Groq API Key** from [console.groq.com](https://console.groq.com/).
2. Run NoPants once, and access the web dashboard via `http://<YOUR_IP>:5000/settings`.
3. Input your Groq API key into the Web UI.

### Ollama (Offline Fallback)
If you wish to use the offline fallback mode, ensure the Ollama server is running locally on port `11434`. 
```bash
ollama run llama3.2:1b
```

---

## 3. Google Calendar OAuth

To enable proactive meeting alerts and scheduling, you must authorize Google Workspace APIs.
1. Head to the Google Cloud Console and generate OAuth Desktop Credentials for the Google Calendar API.
2. Download your `credentials.json` and place it in the root of the NoPants directory.
3. Run the Python server normally. The system will prompt you in the terminal with a URL.
4. Click the URL, log into Google, and approve the requested scopes. This will formulate a secure `token.json` used on every subsequent boot.

---

## 4. Piper Text-to-Speech Setup

**You do NOT need to manually download Piper voices.**
The Python backend contains an auto-healing script. When the server starts up, it will check for `en_US-ryan-medium.onnx` inside the `./piper/` directory.

If it cannot find it, it will securely auto-download the ~60MB `onnx` and JSON configuration file directly from the HuggingFace repos before initializing the web server. Just ensure your device is connected to the internet on the first boot!

---

## 5. Running the Application

Ensure the ESP32 is plugged in via USB and verify the port identifier:
```bash
ls /dev/ttyUSB*
```
*(If yours is different from `ttyUSB1`, modify `server_nopants.py` accordingly).*

Start the bot!
```bash
python3 server_nopants.py
```
*(It will automatically spin up the Chromium Kiosk face after 2 seconds!)*
