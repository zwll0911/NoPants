# 🤖 Physical Hardware & ESP32 Integration

NoPants interfaces with the real world via an ESP32 microcontroller connected over serial communication (`/dev/ttyUSB1` at `115200` baud rate). 

![Image of Physical Robot Setup](docs/media/placeholder_robot_photo.jpg)
> **[Placeholder]**: Provide a high-quality photo of the NoPants robot enclosure and screen here.

---

## 🕹️ Controls & IO Map

The robot chassis provides physical controls for the user to override software states without using voice.

| Component | Action | Server Response |
| :--- | :--- | :--- |
| **Rotary Knob** | `KNOB:RIGHT` / `LEFT` | Executes ALSA `amixer` commands to adjust master terminal volume by 5% increments. |
| **Button 1 (Walkie-Talkie)** | `BTN:1` | Flashes the LED cyan and forcefully opens the web microphone to record a hotword trigger. |
| **Button 2 (Panic Button)** | `BTN:2` | Safely kills all alarms (`alarm_stop`), dumps YouTube music arrays (`killall cvlc`), and flattens all ears. |
| **Button 3 (Party Trick)** | `BTN:3` | Forces a pink LED display and triggers a joke via the AI brain. |

![Video of Buttons Being Pressed](docs/media/placeholder_buttons.mp4)
> **[Placeholder]**: Provide a short clip or image of the buttons and rotary knob.

---

## 🌈 Visual Feedback (LEDs & Servos)

The Python server emits direct string protocols to the ESP32 to define the robot's emotion and state. 

### RGB Color Mapping Protocol
The ESP32 firmware natively translates strings into visual states:
* `LED:CYAN` — The robot is actively listening to you.
* `LED:BLUE` — The robot is processing AI text or currently speaking.
* `LED:RED` — A critical error occurred, or an alarm is actively ringing.
* `LED:RGB:x,y,z` — Custom mapped colors (e.g. `150,50,0` for the cozy Pomodoro Study Mode glow).

### Animatronic Servo "Ears"
* `EARS:UP` — Stand at attention, executed when speaking.
* `EARS:FLAT` — Rest state.
* `EARS:SHAKE` — Panic/Excitement mode, triggered during proactive calendar alerts or jokes.

---

## ⚡ Schematics and Pinout

![Physical Wiring Schematic](docs/media/placeholder_schematic.jpg)
> **[Placeholder]**: Provide your CAD or wiring schematic here detailing the specific ESP32 GPIO pins utilized for the servos, buttons, and NeoPixel/LEDs.
