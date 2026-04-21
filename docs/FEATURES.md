# 🌟 Core Features & Code Deep-Dive

NoPants is bundled with a vast suite of smart assistant capabilities. From keeping you productive to managing background hardware states, here is a detailed breakdown of the exact Python logic powering the robot.

---

## 👔 1. Productivity & Planning

### Proactive Google Calendar (Read & Write)
NoPants doesn't just wait for you to ask about your schedule; it monitors it autonomously. A dedicated background thread continuously polls the Google Calendar API. If an event is exactly 5 minutes away, the robot initiates a panic sequence, bypassing standard conversational flow to warn you instantly.

Additionally, the LLM Master Task Queue can dynamically extract dates and times to create new events on the fly.

**The Proactive Monitor Logic:**
```python
def proactive_calendar_monitor():
    while True:
        events = check_upcoming_meetings()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for event in events:
            event_id = event['id']
            if event_id in alerted_events: continue
                
            start_time = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            time_diff = (start_time - now).total_seconds() / 60.0
            
            # If the meeting is between 4 and 6 minutes away... ACTIVATE!
            if 4.0 <= time_diff <= 6.0:
                if do_not_disturb: continue # Respect study mode
                
                send_to_hardware("EARS:SHAKE")
                send_to_hardware("LED:CYAN")
                
                # Generate a dynamic, frantic alert
                alert_msg = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are NoPants..."},
                        {"role": "user", "content": f"Warn the user {event['summary']} is in 5 mins!"}
                    ], model="llama-3.1-8b-instant"
                ).choices[0].message.content
                speak(alert_msg)
                alerted_events.add(event_id)
                
        socketio.sleep(60) # Poll every 60 seconds
```

### Pomodoro "Study Mode" & State Management
Triggered by saying *"Study mode"* or *"Pomodoro"*. This function alters the global state of the robot. It rejects pending alarms (setting `do_not_disturb = True`), shifts the hardware LEDs to a focus hue, automatically queues a Lo-Fi hip hop stream, and starts a 25-minute (1500 second) visual timer on the web UI.

**The State Override Logic:**
```python
elif "study mode" in user_prompt or "pomodoro" in user_prompt:
    do_not_disturb = True # Blocks background alarms & calendar alerts
    
    socketio.start_background_task(speak, "Study mode activated. 25 minutes on the clock.")
    send_to_hardware("LED:RGB:150,50,0") 
    
    # Inject Lo-Fi beats directly into the queue
    music_queue.clear()
    music_queue.append("lofi hip hop radio beats to relax study to")
    socketio.start_background_task(play_next_in_queue)
    
    # Trigger UI Timer and Background Thread
    socketio.emit('start_visual_timer', {'seconds': 1500})
    threading.Timer(1500.0, pomodoro_finished).start()
```

### The Subconscious Memory Bank
NoPants maintains persistent conversational memory across reboots. The Master Task Queue can trigger a `REMEMBER_FACT` action, which pushes specific preferences or names into a `user_memory.json` file. To prevent LLM context-window bloat, the system utilizes a sliding window, retaining only the 30 most recent facts.

**The Memory Injection Logic:**
```python
def save_new_memory(fact):
    global user_memories
    if fact not in user_memories:
        user_memories.append(fact)
        
        # Sliding Window: Prevent brain bloat! 
        if len(user_memories) > 30:
            user_memories = user_memories[-30:]
            
        with open(memory_file, 'w') as f:
            json.dump(user_memories, f)
```

---

## 🎵 2. Entertainment & Media

### Headless Music Streaming & Queuing
Using `yt-dlp` and a headless VLC subprocess (`cvlc`), NoPants can stream audio directly from YouTube without loading video assets. The Python server maintains process control, allowing users to physically interrupt playback via the ESP32 panic button.

**The Queue Processor:**
```python
def play_next_in_queue():
    global current_song_title, is_music_playing, music_process 
    
    if len(music_queue) == 0:
        is_music_playing = False
        socketio.emit('music_stop')
        return

    query = music_queue.pop(0)
    is_music_playing = True
    
    ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        video = info['entries'][0] if 'entries' in info else info
            
        current_song_title = video.get('title', 'Unknown Track')
        socketio.emit('now_playing', {'title': current_song_title})
        socketio.emit('music_start') 
        
        # Use Popen so the Panic Button can terminate the process
        music_process = subprocess.Popen(['cvlc', '--no-video', '--play-and-exit', video['url']]) 
        music_process.wait() # Block safely until the song finishes
        
        play_next_in_queue() # Recursive call for the next track
```

---

## 🛠️ 3. Utilities & Smart Integrations

### 3-Step Instant Weather (wttr.in)
Standard weather APIs require slow JSON parsing and expensive keys. NoPants uses a 3-step LLM extraction pipeline to parse the user's city, hit the lightning-fast `wttr.in` text endpoint, and re-format the raw data into natural speech.

**The Extraction Pipeline:**
```python
def process_weather():
    # 1. Extract location
    loc_prompt = f"Extract city from: '{user_prompt}'. Default: 'Nibong Tebal'. Reply city name only."
    location = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": loc_prompt}], model="llama-3.1-8b-instant"
    ).choices[0].message.content.strip()
    
    # 2. Fetch raw text data
    weather_data = requests.get(f"[https://wttr.in/](https://wttr.in/){location.replace(' ', '+')}?format=%C,+%t").text.strip()

    # 3. Format into character dialogue
    prompt = f"Weather for {location}: {weather_data}. Tell the user in a fun voice under 20 words."
    answer = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant"
    ).choices[0].message.content
    speak(answer)
```

### Dual-Interval Alarm Matrix
NoPants evaluates two different types of chronological events in a unified background thread:
* **Daily/Weekly Alarms:** Pinpoint chronological events (e.g., `07:00` on `Monday`). Triggers a loud audio siren and red LEDs.
* **Interval Reminders:** Epoch-based math (`current_timestamp + (minutes * 60)`). Designed for passive reminders like "drink water," triggering a visual hardware trick rather than a loud alarm.

**The Background Matrix:**
```python
def background_alarm_monitor():
    while True:
        now = datetime.datetime.now(local_tz)
        current_time = now.strftime("%H:%M")
        current_ts = time.time()
        
        for al in system_alarms:
            # 1. Exact Time Alarms (Siren)
            if al.get('type') == 'daily':
                if current_time == al['time'] and current_day in al['days'] and not al.get('triggered'):
                    socketio.start_background_task(alarm_loop)
                    al['triggered'] = True
                    
            # 2. Interval Reminders (Visual/Soft)
            elif al.get('type') == 'interval':
                if current_ts >= al.get('next_run', 0):
                    socketio.start_background_task(speak, f"Reminder: {al['label']}")
                    socketio.start_background_task(party_trick) 
                    al['next_run'] = current_ts + (al['minutes'] * 60)
                    
        socketio.sleep(10)
```
