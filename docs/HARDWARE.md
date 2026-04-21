# 🤖 Physical Hardware & ESP32 Integration

NoPants interfaces with the real world via a distributed ESP32 microcontroller network. The system consists of a **Main Hub** (inside the robot chassis) connected to the Raspberry Pi over a USB serial connection (`/dev/ttyUSB0` at `115200` baud), and remote **Smart Light Nodes** communicating wirelessly via ESP-NOW.

!(../Pics_&_Videos/Main_hero_pic.jpeg)
> **Note:** A high-quality photo of the NoPants robot enclosure and wiring goes here.

---

## 🔌 1. The Serial Protocol

Because NoPants is a "Dual-Brain" system, the ESP32 is strictly treated as a peripheral node. It contains no heavy logic; it simply reads sensor data and actuates motors based on strict, newline-terminated (`\n`) string commands sent from the Python server.

### 📥 Inputs: ESP32 -> Raspberry Pi
The ESP32 continuously polls its GPIO pins for physical button presses or rotary encoder turns. When an event occurs, it shoots a string back to the Python server.

| Command String | Python Server Action |
| :--- | :--- |
| `KNOB:RIGHT` / `LEFT` | Executes Linux ALSA `amixer` commands to adjust master terminal volume by 5% increments. |
| `BTN:1` | **Walkie-Talkie Mode:** Flashes the LED cyan and forcefully opens the web UI microphone via SocketIO to record a hotword. |
| `BTN:2` | **Panic Button:** Safely triggers `panic_stop()`, killing all alarms, dumping YouTube music arrays (`cvlc`), silencing TTS, and flattening all ears. |
| `BTN:3` | **Party Trick:** Forces a pink LED display and triggers a joke via the AI brain. |
| `BTN:*` / `KNOB:PRESS` | If an alarm is currently ringing, any physical button press acts as a global killswitch to silence the alarm. |
| `SYSTEM: Sent ->` | Confirmation that a Smart Home relay command succeeded. |
| `SYSTEM: CRITICAL ERROR` | Confirmation that a Smart Home relay command failed. |

### 📤 Outputs: Raspberry Pi -> ESP32
The Python server emits direct string protocols to the ESP32 to define the robot's emotion, hardware state, and smart home relay requests.

**1. RGB Color Mapping Protocol (LEDs)**
* `LED:CYAN` — The robot is actively listening to you or processing a Master Task Queue.
* `LED:BLUE` — The robot is actively generating Piper TTS speech.
* `LED:RED` — A critical error occurred, an API failed, or an alarm is actively ringing.
* `LED:RGB:x,y,z` — Custom mapped colors (e.g., `LED:RGB:150,50,0` for the cozy Pomodoro Study Mode glow).

**2. Animatronic Servo "Ears"**
* `EARS:UP` — Stand at attention, executed automatically when speaking.
* `EARS:FLAT` — Rest state, executed when the system goes back to sleep.
* `EARS:SHAKE` — Panic/Excitement mode, triggered during proactive calendar alerts or Party Mode.

**3. Smart Home Expansion**
* `HOME:LIGHT:COLOR:r,g,b` — Routes smart home light controls through the ESP32 network.

---

## 🖥️ 2. Server-Side Integration (Python)

The Raspberry Pi manages the ESP32 via a dedicated background thread that constantly listens to the serial buffer without blocking the web server or the AI brain.

```python
# Hardware initialization and failure fallback
try:
    esp32 = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    print("ESP32 Connected to Web Server!")
except Exception as e:
    print(f"Warning: Hardware not connected. {e}")
    esp32 = None

# Background polling thread for instant hardware interrupts
def read_from_hardware():
    while True:
        if esp32 and esp32.in_waiting > 0:
            try:
                while esp32.in_waiting > 0:
                    line = esp32.readline().decode('utf-8').strip()
                    if line:
                        # Catch hardware overrides instantly
                        if current_screen == '/face':
                            if line == "KNOB:RIGHT":
                                os.system("amixer sset Master 5%+ 2>/dev/null")
                            elif line == "BTN:2":
                                panic_stop()
            except Exception as e:
                socketio.sleep(2.0) 
        socketio.sleep(0.005)
```

---

## ⚡ 3. The Main Hub Firmware (Robot Chassis)

To ensure that parsing serial commands never blocks the physical inputs (and vice versa), the Main Hub ESP32 firmware utilizes **FreeRTOS** to split operations across both physical CPU cores.

* **Core 0 (`InputTask`):** Dedicated entirely to reading rotary encoder pulses and debouncing buttons in real-time.
* **Core 1 (`CommandTask`):** Dedicated to parsing Python Serial strings, driving the I2C Servo Driver, updating FastLEDs, and transmitting ESP-NOW wireless packets.

```cpp
void setup() {
  // ... hardware init ...
  
  // FreeRTOS: Split the workload across both physical cores!
  xTaskCreatePinnedToCore(InputTask, "TaskCore0", 10000, NULL, 1, &TaskCore0, 0);
  xTaskCreatePinnedToCore(CommandTask, "TaskCore1", 10000, NULL, 1, &TaskCore1, 1);
}
```

### GPIO Pinout Map

| Component | ESP32 Pin | Protocol / Function |
| :--- | :--- | :--- |
| **Rotary Encoder (CLK)** | `GPIO 4` | Digital Input (Interrupt/Polling) |
| **Rotary Encoder (DT)** | `GPIO 16` | Digital Input |
| **Rotary Encoder (SW)** | `GPIO 17` | Digital Input (`KNOB:PRESS` / Alarm Killswitch) |
| **Button 1 (Walkie-Talkie)** | `GPIO 19` | Digital Input (`BTN:1`) |
| **Button 2 (Panic Stop)** | `GPIO 18` | Digital Input (`BTN:2`) |
| **Button 3 (Party Trick)** | `GPIO 0` | Digital Input (`BTN:3`) |
| **PCA9685 Servo Driver** | `GPIO 21 (SDA), 22 (SCL)` | I2C (Controls Left/Right Ear Servos) |
| **Robot Face LEDs** | `GPIO 12` | WS2812B NeoPixel Data (16 LEDs) |

---

## 📡 4. The ESP-NOW Smart Home Protocol

Instead of relying on slow, local Wi-Fi routers that can cause lag, NoPants operates its own localized 2.4GHz smart home network using **ESP-NOW**. 

When the Python server sends a command like `HOME:LIGHT:COLOR:red`, the main ESP32 strips the `HOME:` prefix and wirelessly blasts the command to the target node's MAC Address.

### The Reliable Delivery System
Wireless packets can drop. To ensure the Smart Light actually turns on, the Main Hub features a strict retry mechanism that waits for a Delivery Receipt from the remote node, attempting up to 20 times before reporting a critical failure back to Python.

```cpp
void sendSmartHomeCommand(String cmd) {
  // ... format struct ...
  int retries = 0;
  int maxRetries = 20; 

  while (retries < maxRetries) {
    deliveryComplete = false; 
    esp_err_t result = esp_now_send(smartLightMac, (uint8_t *) &outgoingData, sizeof(outgoingData));
    
    if (result == ESP_OK) {
      // Wait up to 100ms for the delivery receipt to come back
      unsigned long startWait = millis();
      while (!deliveryComplete && millis() - startWait < 100) { delay(1); }

      if (deliverySuccess) {
        Serial.println("SYSTEM: Sent -> " + cmd + " [DELIVERED]");
        return; // Exit on success!
      }
    }
    retries++;
    vTaskDelay(25 / portTICK_PERIOD_MS); // Wait before retrying
  }
  Serial.println("SYSTEM: CRITICAL ERROR -> Could not reach Smart Light");
}
```

---

## 💡 5. The Smart Light Node (Remote Firmware)

The remote Smart Light is built on another ESP32 (or ESP8266) equipped with 8 WS2812B LEDs on `GPIO 19`.

### ISR-Safe FreeRTOS Queue
Because incoming ESP-NOW messages trigger an Interrupt Service Routine (ISR), doing heavy processing directly inside the callback will crash the ESP32. 

To solve this, the Smart Light uses an `xQueue`. The ISR instantly drops the message into the mailbox and exits. The main FreeRTOS `LightTask` then opens the mail and smoothly processes the animations.

```cpp
// --- RECEIVE CALLBACK FUNCTION (ISR) ---
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
    char incomingString[32];
    memcpy(incomingString, incomingData, len);
    incomingString[len < 32 ? len : 31] = '\0';
    
    // Drop into the queue without waiting (ISR safe!)
    xQueueSendFromISR(commandQueue, &incomingString, NULL); 
}
```

### Non-Blocking Animation Engine
The Smart Light supports smooth, continuous animations like `MODE_RAINBOW` and `MODE_PULSE`. Instead of using `delay()` (which would freeze the chip and prevent it from receiving new commands), it uses FastLED's non-blocking `EVERY_N_MILLISECONDS` timers alongside mathematical sine waves for breathing effects.

```cpp
// --- ANIMATION ENGINE ---
if (currentMode == MODE_RAINBOW) {
    EVERY_N_MILLISECONDS(20) { 
        fill_rainbow(leds, NUM_LEDS, gHue, 7);
        gHue++; 
        FastLED.show();
    }
} 
else if (currentMode == MODE_PULSE) {
    EVERY_N_MILLISECONDS(10) {
        // Mathematical sine wave for smooth breathing
        float breath = (exp(sin(millis()/2000.0*PI)) - 0.36787944)*108.0;
        FastLED.setBrightness(breath);
        fill_solid(leds, NUM_LEDS, currentColor);
        FastLED.show();
    }
}
```

---

## 📐 6. Schematics

![Physical Wiring Schematic](docs/media/placeholder_schematic.jpg)
> **Note:** A detailed CAD or wiring schematic detailing the specific ESP32 GPIO pins utilized for the servos, buttons, and NeoPixel/LEDs goes here.
