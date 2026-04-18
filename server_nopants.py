from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import requests
import serial
import time
import threading
import os 
import subprocess
import atexit
import re
import dateparser
from dateparser.search import search_dates
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json
from groq import Groq 
import yt_dlp
from ddgs import DDGS
import psutil

# ---> INITIALIZE THE CLOUD BRAIN <---
groq_client = Groq(api_key="YOUR_GROQ_API_KEY_HERE")

# Permission to create and edit calendar events
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# The "leash" to control the Pi's screen
kiosk_process = None
kiosk_toggle = True
is_alarming = False
alarm_process = None
music_process = None
current_screen = '/face'

# ---> SMART HOME TRACKERS <---
smart_home_status = None
smart_home_event = threading.Event()
do_not_disturb = False

# ---> MUSIC STATE MANAGER <---
music_queue = []
current_song_title = None
is_music_playing = False

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---> CONFIGURATION & PERSONA STORE <---
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    # Default settings in case the file doesn't exist yet
    default_config = {
        "api_key": "YOUR_GROQ_API_KEY_HERE",
        "persona_prompt": "You are a helpful, highly energetic robot named NoPants.",
        "tts_voice": "./piper/en_US-ryan-medium.onnx",
        "stt_language": "en-US",
        "face_theme": "theme-spongebob"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
                # Merge defaults with saved settings
                return {**default_config, **user_config}
        except Exception:
            pass
    return default_config

# --- 1. SETUP HARDWARE ---
try:
    esp32 = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    print("ESP32 Connected to Web Server!")
    time.sleep(2)
except Exception as e:
    print(f"Warning: Hardware not connected. {e}")
    esp32 = None

def send_to_hardware(cmd):
    if esp32:
        esp32.write(f"{cmd}\n".encode('utf-8'))
        socketio.sleep(0.1)
    
    socketio.emit('hardware_command', {'command': cmd})
        
def read_from_hardware():
    global is_alarming, alarm_process, smart_home_status
    while True:
        if esp32 and esp32.in_waiting > 0:
            try:
                while esp32.in_waiting > 0:
                    line = esp32.readline().decode('utf-8').strip()
                    if line:
                        if "SYSTEM: Sent ->" in line:
                            smart_home_status = "SUCCESS"
                            smart_home_event.set() 
                        elif "SYSTEM: CRITICAL ERROR" in line:
                            smart_home_status = "FAILED"
                            smart_home_event.set() 
                            
                        # --- ALARM KILL SWITCH (Any button stops a ringing alarm) ---
                        if is_alarming and ("BTN" in line or "KNOB:PRESS" in line):
                            print("ALARM KILLED BY USER!")
                            panic_stop() 
                            continue 
                        
                        # ---> FACE PAGE HARDWARE CONTROLS <---
                        if current_screen == '/face':
                            # -- THE VOLUME KNOB --
                            if line == "KNOB:RIGHT":
                                os.system("amixer sset Master 5%+ 2>/dev/null")
                                print("Volume Up!")
                            elif line == "KNOB:LEFT":
                                os.system("amixer sset Master 5%- 2>/dev/null")
                                print("Volume Down!")
                                
                            # -- BUTTON 1: THE WALKIE-TALKIE --
                            elif line == "BTN:1":
                                print("Walkie-Talkie Triggered!")
                                send_to_hardware("LED:CYAN")
                                socketio.emit('force_mic_listen') 
                                
                            # -- BUTTON 2: THE PANIC BUTTON --
                            elif line == "BTN:2":
                                panic_stop()
                                
                            # -- BUTTON 3: THE PARTY TRICK --
                            elif line == "BTN:3":
                                socketio.start_background_task(party_trick)
                        # ------------------------------------------
                        
                        # Only pass input to the Arcade Games if the game screen is active
                        if current_screen == '/game':
                            socketio.emit('game_input', {'command': line})
                            
            except Exception as e:
                print(f"Serial Error: {e}")
                socketio.sleep(2.0) 
                
        socketio.sleep(0.005)

socketio.start_background_task(read_from_hardware)

# --- 2. THE TTS ENGINE (OFFLINE PIPER) ---
def speak(text):
    print(f"NoPants is speaking: '{text}'")
    send_to_hardware("EARS:UP")
    send_to_hardware("LED:BLUE") 
    
    safe_text = text.replace('"', '').replace('\n', ' ')
    socketio.emit('llm_response', {'response': safe_text})
    
    # Load the local voice setting from the config!
    config = load_config()
    voice_model = config.get("tts_voice", "./piper/en_US-ryan-medium.onnx")
    config_file = f"{voice_model}.json"
    
    # ---> THE STRICT AUTO-HEALER <---
    needs_healing = False
    if not os.path.exists(voice_model) or os.path.getsize(voice_model) < 15000000:
        needs_healing = True
    if not os.path.exists(config_file) or os.path.getsize(config_file) < 100:
        needs_healing = True
        
    if needs_healing:
        print(f"\n[SYSTEM] Voice files for {voice_model} are missing or corrupted!")
        print("[SYSTEM] Auto-downloading from HuggingFace. This might take a minute...")
        
        # Clean up corrupted files before downloading so they don't clash
        os.system(f"rm -f {voice_model} {config_file}")
        
        # Break apart the filename to dynamically build the correct HuggingFace URL
        filename = os.path.basename(voice_model) 
        region = filename.split('-')[0]          
        voice_name = filename.split('-')[1]      
        language = region.split('_')[0]          
        
        base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{language}/{region}/{voice_name}/medium"
        
        # Safely download the raw binary and the config using wget
        os.system(f'wget -q --show-progress -O {voice_model} "{base_url}/{filename}?download=true"')
        os.system(f'wget -q --show-progress -O {config_file} "{base_url}/{filename}.json?download=true"')
        
        # THE FIX: Verify the download actually worked! (No 404 HTML files allowed)
        if not os.path.exists(voice_model) or os.path.getsize(voice_model) < 15000000:
            print(f"[SYSTEM] ERROR: HuggingFace doesn't have '{voice_name}'! Falling back to Ryan to prevent a crash.")
            os.system(f"rm -f {voice_model} {config_file}")
            voice_model = "./piper/en_US-ryan-medium.onnx"
        else:
            print("[SYSTEM] Voice successfully installed! Booting up...\n")

    try:
        # Inject the selected ONNX file into the local Piper command
        turbo_cmd = f'echo "{safe_text}" | ./piper/piper --model {voice_model} --output_raw 2>/dev/null | play -q -t raw -r 22050 -e signed -b 16 -c 1 - pitch +450 tempo 1.0 bass -15 treble +10 2>/dev/null'
        os.system(turbo_cmd)
        
    except Exception as e:
        print(f"Piper Error: {e}")
        
    socketio.emit('stop_talking', {})
    
    send_to_hardware("EARS:FLAT")
    send_to_hardware("LED:OFF")

# ---> BUTTON 2 (THE PANIC BUTTON) <---
def panic_stop():
    global is_alarming, alarm_process, music_process, do_not_disturb
    print("PANIC BUTTON PRESSED! Shutting everything down...")
    
    do_not_disturb = False
    
    # 1. Stop Alarms
    is_alarming = False
    if alarm_process:
        alarm_process.terminate()
        alarm_process = None
    socketio.emit('alarm_stop')
    
    # 2. Stop Music
    if music_process:
        music_process.terminate()
        music_process = None
    socketio.emit('music_stop')
        
    # 3. Stop TTS
    os.system("killall play piper 2>/dev/null")
    socketio.emit('stop_talking')
    
    # 4. Reset the face and ears
    send_to_hardware("LED:OFF")
    send_to_hardware("EARS:FLAT")

# ---> BUTTON 3 (THE PARTY TRICK) <---
def party_trick():
    print("PARTY TRICK TRIGGERED!")
    send_to_hardware("EARS:SHAKE")
    send_to_hardware("LED:RGB:255,0,255") # Pink!
    
    known_facts = get_memory_string()
    
    try:
        # 1. ATTEMPT CLOUD BRAIN (GROQ)
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are NoPants, a chaotic and fun robot. Tell a 1-sentence hilarious joke or a bizarre fun fact in 30 words. Try to be creative!"},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.9 
        )
        joke = chat_completion.choices[0].message.content
        speak(joke)
        
    except Exception as e:
        print(f"Cloud Party Trick Failed: {e}. USING LOCAL BRAIN!")
        
        try:
            # 2. LOCAL FALLBACK BRAIN (OLLAMA)
            local_payload = {
                "model": "llama3.2:1b",
                "messages": [{"role": "system", "content": f"You are NoPants. Tell a very short, funny joke about: {known_facts}"}],
                "stream": False
            }
            response = requests.post("http://localhost:11434/api/chat", json=local_payload, timeout=10)
            joke = response.json()['message']['content']
            speak(joke)
            
        except Exception as local_e:
            speak("I forgot how to party.")

# --- 3. KIOSK DISPLAY MANAGER ---
def switch_kiosk(route):
    global kiosk_process, kiosk_toggle, current_screen
    
    current_screen = route
    kiosk_toggle = not kiosk_toggle
    profile_dir = '/tmp/kiosk_A' if kiosk_toggle else '/tmp/kiosk_B'
    
    print(f"Launching Kiosk on Route: {route} (Profile: {profile_dir})")
    new_process = subprocess.Popen([
        'chromium-browser', 
        '--kiosk',               
        '--start-fullscreen',    
        '--start-maximized',     
        '--noerrdialogs', 
        '--disable-infobars', 
        '--disable-gpu',        
        '--disable-sync',       
        '--incognito',  
        '--autoplay-policy=no-user-gesture-required',
        f'--user-data-dir={profile_dir}',  
        f'--app=http://127.0.0.1:5000{route}' 
    ])
    
    if kiosk_process is not None:
        print(f"Scheduling previous Kiosk process for termination...")
        old_process = kiosk_process 
        threading.Timer(3.0, old_process.terminate).start()
        
    kiosk_process = new_process

@atexit.register
def cleanup_kiosk():
    global kiosk_process
    if kiosk_process is not None:
        print("Closing Kiosk display...")
        kiosk_process.terminate()

# --- 4. WEB ROUTES & SOCKETS ---
@app.route('/')
def index():
    return render_template('index.html', config=load_config())
    
@app.route('/game')
def game_screen():
    return render_template('game.html')
    
@app.route('/face')
def render_face():
    return render_template('face.html', config=load_config())
    
@app.route('/settings')
def settings_page():
    current_config = load_config()
    current_memories = load_memories()
    current_alarms = load_alarms()
    return render_template('settings.html', config=current_config, memories=current_memories, alarms=current_alarms)

@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    new_settings = request.json
    with open(CONFIG_FILE, 'w') as f:
        json.dump(new_settings, f)
    
    # Instantly update the Groq API Key if it was changed!
    global groq_client
    groq_client = Groq(api_key=new_settings.get('api_key', ''))
    
    socketio.emit('reload_face')
    
    return {"status": "success", "message": "NoPants's brain has been rewired!"}

@app.route('/api/update_memory', methods=['POST'])
def update_memory():
    global user_memories
    cleaned_memories = request.json.get('memories', [])
    user_memories = cleaned_memories
    with open(memory_file, 'w') as f:
        json.dump(user_memories, f)
    print(f"[SYSTEM] Memories manually overwritten! Total: {len(user_memories)}")
    return {"status": "success", "message": "Memories scrubbed!"}
    
@app.route('/api/delete_alarm', methods=['POST'])
def delete_alarm():
    global system_alarms
    alarm_id = request.json.get('id')
    
    # Keep every alarm EXCEPT the one with the matching ID
    system_alarms = [al for al in system_alarms if al.get('id') != alarm_id]
    
    # Save to disk and update the face UI instantly!
    save_alarms()
    print(f"[SYSTEM] Protocol {alarm_id} terminated by user.")
    return {"status": "success", "message": "Protocol terminated!"}

@socketio.on('hardware_command')
def handle_hardware(data):
    cmd = data['command']
    send_to_hardware(cmd)
    
@socketio.on('game_over_music')
def play_ending_music():
    print("Game Over! Playing Spongebob ending theme...")
    os.system('play /home/nopants/NoPants_all/spongebob_ending.mp3 2>/dev/null &')
    
# --- GOOGLE CALENDAR ENGINE ---
def add_to_google_calendar(event_title, start_datetime):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        end_datetime = start_datetime + datetime.timedelta(hours=1)
        local_timezone = 'Asia/Kuala_Lumpur'
        
        event = {
          'summary': event_title,
          'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': local_timezone,
          },
          'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': local_timezone,
          },
        }

        event_result = service.events().insert(calendarId='primary', body=event).execute()
        print(f"Event created: {event_result.get('htmlLink')}")
        return True

    except Exception as e:
        print(f"Calendar Error: {e}")
        return False
        
def check_upcoming_meetings(time_min=None, time_max=None):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            except Exception: return []
        else: return []

    try:
        service = build('calendar', 'v3', credentials=creds)
        
        # If no time is provided, default to 'Now'
        if not time_min:
            time_min = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')

        events_result = service.events().list(
            calendarId='primary', 
            timeMin=time_min,
            timeMax=time_max, # Added this!
            maxResults=10, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except Exception as e:
        print(f"Calendar Read Error: {e}")
        return []
        
def play_next_in_queue():
    # ADDED music_process so the global kill-switches can see it!
    global current_song_title, is_music_playing, music_queue, music_process 
    
    if len(music_queue) == 0:
        is_music_playing = False
        current_song_title = None
        socketio.emit('music_stop')  # Stops the head bobbing and hides the UI
        return

    query = music_queue.pop(0)
    is_music_playing = True
    
    try:
        import yt_dlp
        ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch', 'source_address': '0.0.0.0'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            video = info['entries'][0] if 'entries' in info else info
                
            current_song_title = video.get('title', 'Unknown Track')
            url = video['url']
            
            print(f"Now Playing: {current_song_title}")
            socketio.emit('now_playing', {'title': current_song_title})
            
            # Emit the correct socket so the Face starts head-bobbing!
            socketio.emit('music_start') 
            
            import subprocess
            # FIX: Use Popen so the "Stop Music" command can actually terminate it
            music_process = subprocess.Popen(['cvlc', '--ipv4', '--no-video', '--play-and-exit', url]) 
            music_process.wait() # Block safely until the song finishes
            
            play_next_in_queue()
            
    except Exception as e:
        print(f"Music Queue Error: {e}")
        play_next_in_queue()
        
# ---> PROACTIVE CALENDAR MONITOR <---
alerted_events = set()

def proactive_calendar_monitor():
    global alerted_events
    print("Starting Proactive Calendar Monitor...")
    
    while True:
        events = check_upcoming_meetings()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for event in events:
            event_id = event['id']
            
            # If we already yelled at you for this meeting, skip it!
            if event_id in alerted_events:
                continue
                
            start_str = event['start'].get('dateTime')
            if not start_str: 
                continue # Skip all-day events (like birthdays)
                
            # Convert Google's string into a mathematical Python time
            start_time = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            
            # Calculate exactly how many minutes are left until the meeting
            time_diff = (start_time - now).total_seconds() / 60.0
            
            # If the meeting is between 4.0 and 6.0 minutes away... ACTIVATE!
            if 4.0 <= time_diff <= 6.0:
                
                # ---> Check if we are in Study Mode! <---
                if do_not_disturb:
                    print(f"Skipping alert for {event['summary']} because Do Not Disturb is ON.")
                    alerted_events.add(event_id)
                    continue 

                title = event.get('summary', 'a meeting')
                print(f"PROACTIVE ALERT: {title} is in 5 minutes!")
                
                # Wake up the hardware!
                send_to_hardware("EARS:SHAKE")
                send_to_hardware("LED:CYAN")
                
                try:
                    # Let Groq generate a dynamic, panicky alert message
                    chat_completion = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "You are NoPants, a highly energetic robot."},
                            {"role": "user", "content": f"Tell the user they have a meeting called '{title}' in exactly 5 minutes! Warn them not to be late. Sound like a cartoon character. Keep it under 20 words."}
                        ],
                        model="llama-3.1-8b-instant",
                        temperature=0.8 
                    )
                    alert_msg = chat_completion.choices[0].message.content
                    speak(alert_msg)
                except Exception as e:
                    # Fallback if the internet drops
                    speak(f"Hey! Your meeting {title} starts in 5 minutes! Hurry up!")
                
                # Add it to the memory bank so he doesn't repeat himself
                alerted_events.add(event_id)
                
        # Sleep for exactly 60 seconds, then loop and check again!
        socketio.sleep(60)

# --- OLLAMA EXTRACTORS ---
def extract_event_details(prompt):
    now = datetime.datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")

    system_prompt = (
        f"You are a scheduling assistant. Today is {current_day}, {current_date}. "
        "Extract the meeting title and the exact date/time. "
        "Respond ONLY with a JSON object: {\"title\": \"string\", \"time\": \"YYYY-MM-DD HH:MM\"}. "
        "Convert all relative times (today, tomorrow, 3pm) into the numeric YYYY-MM-DD HH:MM format using 24-hour time."
        "CRITICAL RULE: If the user provides a small number like '5' or '7' without saying AM or PM, use logical deduction. "
        "(e.g., people usually schedule parties and meetings in the afternoon/evening, so output 17:00 or 19:00, NOT 05:00)."
    )
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User: {prompt}"}
            ],
            model="llama-3.1-8b-instant", 
            response_format={"type": "json_object"}, 
            temperature=0.0
        )
        ai_data = json.loads(chat_completion.choices[0].message.content)
        return ai_data.get("title", "Meeting"), ai_data.get("time", "")
    except Exception as e:
        print(f"Groq Calendar Error: {e}")
        return "Meeting", ""

# ---> TIME-AWARE MASTER TASK AGENT <---
def extract_master_queue(user_text, history):
    # Get the exact current date and time!
    current_time = datetime.datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
    
    known_facts = get_memory_string()
    
    # Format the last 4 messages so the Agent knows what you were just talking about
    history_text = "None"
    if history:
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]])
    
    system_prompt = f"""
    You are the Master Command Agent for a robot named NoPants. 
    CURRENT DATE & TIME: {current_time}
    USER FACTS TO REMEMBER: {known_facts}
    
    Convert the user's complex request into a sequential array of tasks.
    
    Valid Task Types:
    1. "SMART_LIGHT" - You MUST use one of these exact string formats:
       - Power: HOME:LIGHT:ON or HOME:LIGHT:OFF
       - Solid Color: HOME:LIGHT:COLOR:<color> (e.g., red, blue, green). NEVER use "rainbow" or "pulse" as a color.
       - Animations: HOME:LIGHT:ANIM:RAINBOW or HOME:LIGHT:ANIM:PULSE
    2. "HARDWARE" - commands: LED:RED, LED:BLUE, LED:CYAN, LED:OFF, EARS:UP, EARS:FLAT, EARS:SHAKE
    3. "TIMER" - Requires a "seconds" integer. 
    4. "SPEAK" - Requires a "text" string to say out loud. If the user asks for the time or date, you MUST use this task and read the CURRENT DATE & TIME provided above!
    5. "DELAY" - Requires a "seconds" number to wait.
    6. "PLAY_MUSIC" - Requires a "query" string. Use this to clear the current queue and immediately play a NEW song.
    7. "SEARCH_WEB" - Requires a "query" string. Use this for news or real-world questions. NEVER use this to find the current time or date!
    8. "UNSUPPORTED" - Use this if the user asks you to do a physical or digital action that is NOT listed in steps 1-7 (e.g., opening a specific app like YouTube, ordering food, moving a motor you don't have). 
       - Requires a "text" string. 
       - In the text string, you must state that you don't have the code for that yet, and then act like a Lead Developer and tell the user exactly what Python library or Linux command they need to install to give you that feature.
    9. "REMEMBER_FACT" - Requires a "fact" string. Use this ANY TIME the user tells you personal information, preferences, names, or things to remember long-term. Extract the core fact.
    10. "CHECK_CALENDAR" - Requires a "date" string in YYYY-MM-DD format. 
        Use the CURRENT DATE & TIME provided above to calculate relative dates (e.g., tomorrow, next Friday).
    11. "CREATE_CALENDAR_EVENT" - Requires "title" (string) and "time" (YYYY-MM-DD HH:MM). Use this anytime the user asks to schedule, record, or add a meeting/event to their calendar!
    12. "SET_ALARM" - For specific daily/weekly times (e.g., "7 AM every weekday"). Requires "time" (24-hour "HH:MM"), "days" (Array of full day names, e.g., ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]), and "label".
    13. "SET_INTERVAL" - For repeating intervals (e.g., "remind me to drink water every hour"). Requires "minutes" (integer) and "label".
    14. "QUEUE_MUSIC" - Requires a "query" string. Use this ONLY if the user says "add X to the queue" or "play X next". 
    15. "CHECK_MUSIC" - Use this if the user asks "what song is this?" or "what is playing right now?". Requires NO parameters.
    
    CRITICAL RULES: 
    - Look at the Recent Conversation context to understand what the user means.
    - GENERAL QUESTIONS: If the user asks a general question about your capabilities (e.g., "what can you do?"), summarize your skills in the "spoken_reply" and leave the "commands" array EMPTY. Do NOT use the SPEAK task if you are already using spoken_reply!
    - DO NOT invent extra steps. Only perform the specific action the user requested.
    - If the user asks to "record," "add," or "schedule," ONLY use CREATE_CALENDAR_EVENT. 
    - DO NOT use CHECK_CALENDAR unless the user explicitly asks to "check," "see," or "read" their schedule.
    - If scheduling a meeting, ALWAYS use "CREATE_CALENDAR_EVENT". Do NOT use "SET_ALARM" for meetings.

    Respond ONLY with a valid JSON object formatted exactly like this:
    {{
      "spoken_reply": "A quick confirmation of the sequence. (Leave this empty if using a SPEAK task!)",
      "commands": [
        {{"type": "SMART_LIGHT", "command": "HOME:LIGHT:COLOR:red"}},
        {{"type": "DELAY", "seconds": 2.0}},
        {{"type": "SMART_LIGHT", "command": "HOME:LIGHT:ANIM:RAINBOW"}},
        {{"type": "PLAY_MUSIC", "query": "Jennie Mantra"}},
        {{"type": "SEARCH_WEB", "query": "latest news April 2026"}},
        {{"type": "SPEAK", "text": "Today is {current_time}."}},
        {{"type": "UNSUPPORTED", "text": "I don't have a tool to open YouTube. You should add a Python subprocess command to launch chromium-browser to youtube.com!"}},
        {{"type": "REMEMBER_FACT", "fact": "User's dog is named Happy"}},
        {{"type": "CHECK_CALENDAR", "date": "2026-04-18"}}
        {{"type": "CREATE_CALENDAR_EVENT", "title": "Robotics Meeting", "time": "2026-04-19 11:00"}}
      ]
    }}
    """
    
    user_payload = f"RECENT CONVERSATION:\n{history_text}\n\nUSER REQUEST: {user_text}"
    
    try:
        # 1. ATTEMPT CLOUD BRAIN (GROQ)
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload}
            ],
            model="llama-3.1-8b-instant", 
            response_format={"type": "json_object"},
            temperature=0.0
        )
        ai_data = json.loads(chat_completion.choices[0].message.content)
        return ai_data.get("commands", []), ai_data.get("spoken_reply", "Done.")
        
    except Exception as e:
        print(f"Cloud Queue Failed: {e}. WAKING UP LOCAL BRAIN!")
        
        try:
            # 2. LOCAL FALLBACK BRAIN (OLLAMA)
            local_payload = {
                "model": "llama3.2:1b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload}
                ],
                "format": "json",
                "stream": False
            }
            # Hit the local Ollama server running on port 11434
            response = requests.post("http://localhost:11434/api/chat", json=local_payload, timeout=15)
            ai_data = json.loads(response.json()['message']['content'])
            return ai_data.get("commands", []), ai_data.get("spoken_reply", "Done.")
            
        except Exception as local_e:
            print(f"Local Brain Error: {local_e}")
            return [], "Barnacles. I have completely lost my mind."
            
# --- 5. THE AI BRAIN (BACKGROUND THREAD) ---
chat_history = []

def ask_ai_in_background(user_prompt):
    global chat_history
    send_to_hardware("EARS:UP")
    send_to_hardware("LED:CYAN") 
    
    # Load the persona from the config!
    config = load_config()
    base_persona = config.get("persona_prompt", "You are NoPants.")
    
    # Inject the user's personal facts into his subconscious!
    known_facts = get_memory_string()
    system_persona = f"You are a helpful, highly energetic robot named NoPants. You MUST answer in 20 words or less. Be brief, punchy, and sound like a cartoon. USER FACTS TO REMEMBER: {known_facts}"
    
    chat_history.append({"role": "user", "content": user_prompt})
    
    if len(chat_history) > 10:
        chat_history = chat_history[-10:]
        
    api_messages = [{"role": "system", "content": system_persona}] + chat_history
    
    try:
        # 1. ATTEMPT CLOUD BRAIN (GROQ)
        chat_completion = groq_client.chat.completions.create(
            messages=api_messages,
            model="llama-3.1-8b-instant",
            temperature=0.7 
        )
        bot_reply = chat_completion.choices[0].message.content
        chat_history.append({"role": "assistant", "content": bot_reply})
        
    except Exception as e:
        print(f"Cloud Chat Failed: {e}. WAKING UP LOCAL BRAIN!")
        
        try:
            # 2. LOCAL FALLBACK BRAIN (OLLAMA)
            local_payload = {
                "model": "llama3.2:1b",
                "messages": api_messages,
                "stream": False
            }
            response = requests.post("http://localhost:11434/api/chat", json=local_payload, timeout=10)
            bot_reply = response.json()['message']['content']
            chat_history.append({"role": "assistant", "content": bot_reply})
            
        except Exception as local_e:
            bot_reply = "My cloud connection is dead, and my local brain is asleep."

    speak(bot_reply)
    
@socketio.on('hotword_detected')
def handle_hotword():
    print("Hotword heard! Waking up face...")
    send_to_hardware("LED:BLUE") 
    
def alarm_loop():
    global is_alarming, alarm_process
    is_alarming = True
    socketio.emit('alarm_start') 

    while is_alarming:
        send_to_hardware("EARS:UP")
        alarm_process = subprocess.Popen(['play', '/home/nopants/NoPants_all/static/alarm.mp3'], stderr=subprocess.DEVNULL)
        
        while alarm_process.poll() is None and is_alarming:
            send_to_hardware("LED:RED")
            time.sleep(0.15)
            send_to_hardware("LED:OFF")
            time.sleep(0.15)
        
        if is_alarming:
            send_to_hardware("EARS:FLAT")
            time.sleep(0.5)

def alarm_finished():
    print("Timer is up! Triggering Alarm Sequence...")
    threading.Thread(target=alarm_loop).start()
    
def pomodoro_finished():
    global do_not_disturb, music_process
    print("Pomodoro Complete!")
    
    # 1. Turn off DND
    do_not_disturb = False
    
    # 2. Stop the Lo-Fi Music
    if music_process:
        music_process.terminate()
        music_process = None
    socketio.emit('music_stop')
    
    # 3. Visual & Audio Celebration
    send_to_hardware("LED:RGB:0,255,0") # Green!
    speak("Pomodoro complete! Great job. Time for a 5 minute break!")

# --- 6. VOICE COMMAND ROUTER (THE TRAFFIC COP) ---
@socketio.on('llm_request')
def handle_llm(data):
    global music_process, do_not_disturb, music_queue

    user_prompt = data['prompt'].lower()
    print(f"Web User: {user_prompt}")

    # ==========================================
    # TIER 1: INSTANT HARDWARE OVERRIDES
    # ==========================================
    if "stop music" in user_prompt or "shut up" in user_prompt:
        do_not_disturb = False 
        music_queue.clear() 
        if music_process:
            music_process.terminate()
            music_process = None
        socketio.emit('music_stop')
        socketio.start_background_task(speak, "Music stopped.")
        return
        
    if "sleep" in user_prompt or "relax" in user_prompt:
        socketio.start_background_task(speak, "Going back to sleep.")
        return
        
    if "play" in user_prompt and "game" in user_prompt:
        socketio.start_background_task(speak, "Booting up NoPants OS. Grab the knob.")
        switch_kiosk('/game')
        return
        
    if "exit" in user_prompt and "game" in user_prompt:
        socketio.start_background_task(speak, "Returning to base operation.")
        switch_kiosk('/face')
        return

    # ==========================================
    # TIER 2: HARDCODED APPS (Pomodoro & Weather)
    # ==========================================
    if "study mode" in user_prompt or "pomodoro" in user_prompt:
        do_not_disturb = True
        socketio.start_background_task(speak, "Study mode activated. 25 minutes on the clock. Focus up!")
        send_to_hardware("LED:RGB:150,50,0") 
        music_queue.clear()
        music_queue.append("lofi hip hop radio beats to relax study to")
        socketio.start_background_task(play_next_in_queue)
        socketio.emit('start_visual_timer', {'seconds': 1500})
        threading.Timer(1500.0, pomodoro_finished).start()
        return

    if "weather" in user_prompt:
        send_to_hardware("LED:CYAN")
        socketio.start_background_task(process_weather_logic, user_prompt)
        return

    # ==========================================
    # TIER 3: THE MASTER TASK AGENT
    # ==========================================
    # If the prompt contains any of these words, route it to the advanced JSON Task Agent
    queue_triggers = [
        "light", "timer", "wait", "then", "music", "song", "play", "queue", "next", 
        "what is playing", "what song", "search", "news", "today", "who is", "what is", 
        "open", "launch", "start", "can you", "remember", "my", "i like", "i love", 
        "my name", "calendar", "meeting", "events", "schedule", "wake me up", 
        "remind me", "alarm", "every", "add to"
    ]

    if any(word in user_prompt for word in queue_triggers):
        send_to_hardware("LED:CYAN")
        socketio.start_background_task(process_master_queue_logic, user_prompt)
        return

    # ==========================================
    # TIER 4: DEFAULT CONVERSATION
    # ==========================================
    # If it's just normal chatting, send it to the conversational brain
    socketio.start_background_task(ask_ai_in_background, user_prompt)


# --- DEDICATED LOGIC WORKERS ---

def process_weather_logic(user_prompt):
    global chat_history
    try:
        loc_prompt = f"Extract the city name from this request: '{user_prompt}'. If no city is mentioned, reply ONLY with 'Nibong Tebal'. Do not say anything else."
        loc_response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": loc_prompt}],
            model="llama-3.1-8b-instant", temperature=0.0 
        )
        location = loc_response.choices[0].message.content.strip()
        
        weather_data = requests.get(f"https://wttr.in/{location.replace(' ', '+')}?format=%C,+%t", timeout=5).text.strip()
        
        prompt = f"The user asked for the weather in {location}. The live data says: {weather_data}. Tell the user this in a fun, energetic cartoon robot voice. Keep it under 20 words!"
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": "You are NoPants."}, {"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", temperature=0.7 
        )
        answer = chat_completion.choices[0].message.content
        
        chat_history.append({"role": "user", "content": f"What is the weather in {location}?"})
        chat_history.append({"role": "assistant", "content": answer})
        speak(answer)
    except Exception as e:
        print(f"Weather Error: {e}")
        speak("Barnacles! My weather antenna got struck by lightning.")

def process_master_queue_logic(user_prompt):
    global smart_home_status, chat_history, system_alarms
    
    command_list, spoken_reply = extract_master_queue(user_prompt, chat_history)
    print(f"Master Agent Task List: {json.dumps(command_list, indent=2)}")
    
    if spoken_reply:
        # Check if the AI scheduled ANY 'SPEAK' tasks in the array.
        has_speak_task = any(step.get("type") == "SPEAK" for step in command_list)
        
        # Only say the general reply if there isn't a dedicated SPEAK task coming up
        if not has_speak_task:
            speak(spoken_reply)
            
    for step in command_list:
        task_type = step.get("type", "")
        
        if task_type == "SMART_LIGHT":
            system_command = step.get("command", "")
            if system_command.startswith("HOME:LIGHT:COLOR:"):
                color_word = system_command.split(":")[-1].strip().lower()
                color_map = { "red": "255,0,0", "green": "0,255,0", "blue": "0,0,255", "yellow": "255,255,0", "purple": "128,0,128", "cyan": "0,255,255", "white": "255,255,255", "orange": "255,165,0", "pink": "255,105,180" }
                system_command = f"HOME:LIGHT:COLOR:{color_map.get(color_word, '255,255,255')}" 
                    
            smart_home_status = None
            send_to_hardware(system_command)
            wait_time = 0
            while smart_home_status is None and wait_time < 3.0:
                socketio.sleep(0.1) 
                wait_time += 0.1
            if smart_home_status != "SUCCESS":
                send_to_hardware("LED:RED")
                speak("Uh oh, the smart light stopped responding.")
                break 

        elif task_type == "HARDWARE":
            send_to_hardware(step.get("command", ""))
            
        elif task_type == "TIMER":
            secs = step.get("seconds", 0)
            if secs > 0:
                socketio.emit('start_visual_timer', {'seconds': secs})
                threading.Timer(secs, alarm_finished).start()

        elif task_type == "SPEAK":
            speak(step.get("text", ""))

        elif task_type == "PLAY_MUSIC":
            music_queue.clear()
            music_queue.append(step.get("query", ""))
            socketio.start_background_task(play_next_in_queue)
            
        elif task_type == "QUEUE_MUSIC":
            music_queue.append(step.get("query", ""))
            speak("Added to the queue.")
            if not is_music_playing: socketio.start_background_task(play_next_in_queue)

        elif task_type == "CHECK_MUSIC":
            if current_song_title:
                clean_title = current_song_title.split('(')[0].split('[')[0].strip()
                speak(f"Currently playing: {clean_title}.")
            else:
                speak("I don't hear any music playing right now!")

        elif task_type == "DELAY":
            secs = step.get("seconds", 0)
            if secs > 0: socketio.sleep(secs) 

        elif task_type == "SEARCH_WEB":
            search_query = step.get("query", "")
            if search_query:
                try:
                    results = DDGS().text(search_query, max_results=3, timelimit='w')
                    if not results:
                        speak("I couldn't find anything about that online.")
                        continue
                    web_info = " ".join([r['body'] for r in results])
                    current_date = datetime.datetime.now().strftime("%B %d, %Y")
                    prompt = f"Today is {current_date}. User asked: '{search_query}'. Read this web data and answer them in 30 words or less. Be punchy and sound like a cartoon robot. Web Data: {web_info}"
                    
                    chat_completion = groq_client.chat.completions.create(
                        messages=[{"role": "system", "content": "You are NoPants."}, {"role": "user", "content": prompt}],
                        model="llama-3.1-8b-instant", temperature=0.7 
                    )
                    answer = chat_completion.choices[0].message.content
                    chat_history.append({"role": "user", "content": f"Search the web for {search_query}"})
                    chat_history.append({"role": "assistant", "content": answer})
                    speak(answer)
                except Exception as e:
                    speak("Barnacles! I couldn't connect to the internet.")

        elif task_type == "CHECK_CALENDAR":
            target_date_str = step.get("date") 
            try:
                import pytz
                local_tz = pytz.timezone('Asia/Kuala_Lumpur')
                if target_date_str:
                    base_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
                    target_day = local_tz.localize(base_date)
                else:
                    target_day = datetime.datetime.now(local_tz)

                start_of_range = target_day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                end_of_range = target_day.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
                events = check_upcoming_meetings(time_min=start_of_range, time_max=end_of_range)
                
                day_label = "today" if target_date_str == datetime.datetime.now().strftime("%Y-%m-%d") else "that day"
                if target_date_str == (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d"):
                    day_label = "tomorrow"

                if not events:
                    speak(f"Your calendar for {day_label} is completely clear!")
                else:
                    agenda = []
                    for e in events:
                        title = e.get('summary', 'An Event')
                        start_str = e['start'].get('dateTime', e['start'].get('date'))
                        if 'T' in start_str:
                            dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                            time_friendly = dt.astimezone(local_tz).strftime("%I:%M %p")
                        else:
                            time_friendly = "All Day"
                        agenda.append(f"{title} at {time_friendly}")
                        
                    event_text = ". ".join(agenda)
                    prompt = f"The user's schedule for {target_date_str} ({day_label}) is: {event_text}. Summarize this for them in 30 words or less. Be punchy and energetic!"
                    
                    chat_completion = groq_client.chat.completions.create(
                        messages=[{"role": "system", "content": "You are NoPants."}, {"role": "user", "content": prompt}],
                        model="llama-3.1-8b-instant", temperature=0.7 
                    )
                    speak(chat_completion.choices[0].message.content)
            except Exception as e:
                speak("Barnacles! I had a glitch reading your schedule.")

        elif task_type == "CREATE_CALENDAR_EVENT":
            event_title = step.get("title", "Meeting")
            time_str = step.get("time", "")
            if time_str:
                try:
                    parsed_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                    import pytz
                    local_tz = pytz.timezone('Asia/Kuala_Lumpur')
                    parsed_time = local_tz.localize(parsed_time)
                    success = add_to_google_calendar(event_title, parsed_time)
                    if success:
                        send_to_hardware("LED:BLUE")
                        friendly_time = parsed_time.strftime("%I:%M %p on %A")
                        speak(f"Done! I've added {event_title} to your calendar for {friendly_time}. Going back to sleep!")
                    else:
                        speak("Barnacles! I failed to sync with Google Calendar.")
                except Exception as e:
                    speak("I couldn't figure out the exact time for that meeting.")

        elif task_type == "REMEMBER_FACT":
            new_fact = step.get("fact", "")
            if new_fact:
                save_new_memory(new_fact)
                send_to_hardware("LED:CYAN")
                socketio.sleep(0.5)

        elif task_type == "SET_ALARM":
            alarm_label = step.get("label", "Alarm")
            system_alarms.append({
                "id": str(time.time()), "type": "daily", "time": step.get("time", "00:00"),
                "days": step.get("days", []), "label": alarm_label, "triggered_today": False
            })
            save_alarms()

        elif task_type == "SET_INTERVAL":
            mins = step.get("minutes", 60)
            reminder_label = step.get("label", "Reminder")
            system_alarms.append({
                "id": str(time.time()), "type": "interval", "minutes": mins,
                "next_run": time.time() + (mins * 60), "label": reminder_label
            })
            save_alarms()

        elif task_type == "UNSUPPORTED":
            send_to_hardware("EARS:FLAT")
            send_to_hardware("LED:RED")
            speak(step.get("text", "I don't have the code to do that yet."))
    
# ---> LONG-TERM PERSONAL MEMORY DATABASE <---
memory_file = os.path.join(os.path.dirname(__file__), 'user_memory.json')

def load_memories():
    if os.path.exists(memory_file):
        try:
            with open(memory_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return [] # Returns an empty list of facts if no file exists

user_memories = load_memories()

def save_new_memory(fact):
    global user_memories
    if fact not in user_memories:
        user_memories.append(fact)
        
        # ---> Prevent brain bloat! Keep only the newest 30 memories. <---
        if len(user_memories) > 30:
            user_memories = user_memories[-30:]
            
        with open(memory_file, 'w') as f:
            json.dump(user_memories, f)
        print(f"NEW MEMORY SAVED: {fact} (Total: {len(user_memories)}/30)")
        
def get_memory_string():
    if not user_memories:
        return "No personal facts known yet."
    return " | ".join(user_memories)
    
# ---> ARCADE LEADERBOARD DATABASE <---
leaderboard_file = os.path.join(os.path.dirname(__file__), 'leaderboard.json')

def load_leaderboard():
    if os.path.exists(leaderboard_file):
        try:
            with open(leaderboard_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {'TURRET': 0, 'TETRIS': 0, 'BURGER': 0}

arcade_leaderboard = load_leaderboard()

@socketio.on('request_leaderboard')
def send_leaderboard():
    socketio.emit('update_leaderboard', arcade_leaderboard)

@socketio.on('submit_score')
def save_new_score(data):
    game = data.get('game')
    score = data.get('score', 0)
    if game in arcade_leaderboard and score > arcade_leaderboard[game]:
        arcade_leaderboard[game] = score
        with open(leaderboard_file, 'w') as f:
            json.dump(arcade_leaderboard, f)
        socketio.emit('update_leaderboard', arcade_leaderboard)
        
# ---> RECURRING ALARM DATABASE <---
alarms_file = os.path.join(os.path.dirname(__file__), 'alarms.json')

def load_alarms():
    if os.path.exists(alarms_file):
        try:
            with open(alarms_file, 'r') as f: return json.load(f)
        except Exception: pass
    return []

system_alarms = load_alarms()

def save_alarms():
    with open(alarms_file, 'w') as f: json.dump(system_alarms, f)
    socketio.emit('update_alarms_ui', system_alarms)

@socketio.on('request_alarms')
def send_alarms_to_face():
    socketio.emit('update_alarms_ui', system_alarms)

# ---> BACKGROUND ALARM MONITOR <---
def background_alarm_monitor():
    global system_alarms
    print("Starting Background Alarm Monitor...")
    while True:
        import pytz
        local_tz = pytz.timezone('Asia/Kuala_Lumpur')
        now = datetime.datetime.now(local_tz)
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%A")
        current_ts = time.time()
        
        needs_save = False
        
        for al in system_alarms:
            # 1. Daily/Weekly Scheduled Alarms
            if al.get('type') == 'daily':
                if current_time == al['time'] and current_day in al['days']:
                    if not al.get('triggered_today'):
                        print(f"ALARM TRIGGERED: {al['label']}")
                        socketio.start_background_task(speak, f"Wake up! {al['label']}!")
                        socketio.start_background_task(alarm_loop)
                        al['triggered_today'] = True
                        needs_save = True
                        
            # 2. Hourly/Minute Interval Reminders
            elif al.get('type') == 'interval':
                if current_ts >= al.get('next_run', 0):
                    print(f"REMINDER TRIGGERED: {al['label']}")
                    socketio.start_background_task(speak, f"Reminder: {al['label']}")
                    socketio.start_background_task(party_trick) # A fun visual flash instead of a loud siren!
                    al['next_run'] = current_ts + (al['minutes'] * 60)
                    needs_save = True
                    
        # Reset daily triggers at midnight
        if current_time == "00:00":
            for al in system_alarms: 
                al['triggered_today'] = False
            needs_save = True
            
        if needs_save: save_alarms()
        socketio.sleep(10) # Check the clock every 10 seconds
        
# ---> SYSTEM HEALTH MONITOR <---
def system_health_monitor():
    print("Starting System Health Monitor...")
    while True:
        try:
            # 1. CPU & RAM
            cpu_usage = psutil.cpu_percent(interval=0.2)
            ram_usage = psutil.virtual_memory().percent
            
            # 2. Volume Level
            try:
                vol_out = subprocess.check_output("amixer sget Master | grep -o '[0-9]*%' | head -1", shell=True, text=True).strip()
                volume = int(vol_out.replace('%', '')) if vol_out else 0
            except:
                volume = 0
                
            # 3. WiFi Signal Strength (Reading direct from Linux core)
            wifi_signal = "0%"
            try:
                with open("/proc/net/wireless", "r") as f:
                    lines = f.readlines()
                    if len(lines) > 2:
                        data = lines[2].split()
                        if data[0].startswith("wlan0"):
                            # Linux wifi quality is usually out of 70
                            quality = float(data[2].replace('.', ''))
                            wifi_signal = f"{min(100, int((quality/70)*100))}%"
            except:
                wifi_signal = "N/A"
                    
            # 4. ESP32 Connection Status
            esp_connected = esp32 is not None and esp32.is_open

            # Send the vitals to the Web UI!
            socketio.emit('system_health', {
                'cpu': cpu_usage,
                'ram': ram_usage,
                'volume': volume,
                'wifi': wifi_signal,
                'esp32': esp_connected
            })
        except Exception as e:
            print(f"Health Monitor Error: {e}")
            
        socketio.sleep(1) # Update the dashboard every 3 seconds

# --- 7. STARTUP SEQUENCE ---
if __name__ == '__main__':
    print("Starting NoPants Web Server on http://0.0.0.0:5000")
    
    # Switch the display on
    threading.Timer(2.0, lambda: switch_kiosk('/face')).start()
    
    # LAUNCH THE AUTONOMOUS HEARTBEAT!
    socketio.start_background_task(proactive_calendar_monitor)
    socketio.start_background_task(background_alarm_monitor)
    socketio.start_background_task(system_health_monitor)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
