#include <esp_now.h>
#include <WiFi.h>
#include <FastLED.h>
#include <esp_wifi.h>

// --- HARDWARE SETUP ---
#define LED_PIN     19
#define NUM_LEDS    8 
#define MAX_BRIGHTNESS  150

CRGB leds[NUM_LEDS];
QueueHandle_t commandQueue;

// --- FreeRTOS Task Handle ---
TaskHandle_t TaskCore1; // For LED Animations and Commands

// --- STATE VARIABLES ---
enum LightMode { MODE_SOLID, MODE_RAINBOW, MODE_PULSE, MODE_OFF };
LightMode currentMode = MODE_OFF;
CRGB currentColor = CRGB::White;
uint8_t currentBrightness = MAX_BRIGHTNESS;

// Animation helpers
uint8_t gHue = 0; // Rotating color for rainbow

// --- RECEIVE CALLBACK FUNCTION ---
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
    char incomingString[32];
    memcpy(incomingString, incomingData, len);
    incomingString[len < 32 ? len : 31] = '\0';
    // Drop into the queue without waiting (ISR safe)
    xQueueSendFromISR(commandQueue, &incomingString, NULL); 
}

// ==========================================
// TASK: THE LIGHT CONTROLLER (Runs on Core 1)
// ==========================================
void LightTask(void * pvParameters) {
    char receivedCommand[32];

    for(;;) {
        // "0" means check the mailbox but DON'T wait if it's empty, 
        // allowing the animation engine below it to keep spinning!
        if (xQueueReceive(commandQueue, &receivedCommand, 0) == pdPASS) {
            String cmd = String(receivedCommand);
            Serial.println("Command Executed: " + cmd);

            if (cmd == "LIGHT:ON") {
                currentMode = MODE_SOLID;
                FastLED.setBrightness(currentBrightness);
                fill_solid(leds, NUM_LEDS, currentColor);
            } 
            else if (cmd == "LIGHT:OFF") {
                currentMode = MODE_OFF;
                FastLED.clear(true);
            }
            else if (cmd.startsWith("LIGHT:BRIGHTNESS:")) {
                currentBrightness = cmd.substring(17).toInt();
                FastLED.setBrightness(currentBrightness);
            }
            else if (cmd.startsWith("LIGHT:COLOR:")) {
                int firstComma = cmd.indexOf(',');
                int secondComma = cmd.lastIndexOf(',');
                if (firstComma > 0 && secondComma > firstComma) {
                    int r = cmd.substring(12, firstComma).toInt();
                    int g = cmd.substring(firstComma + 1, secondComma).toInt();
                    int b = cmd.substring(secondComma + 1).toInt();
                    currentColor = CRGB(r, g, b);
                    currentMode = MODE_SOLID;
                    FastLED.setBrightness(currentBrightness);
                    fill_solid(leds, NUM_LEDS, currentColor);
                }
            }
            else if (cmd == "LIGHT:ANIM:RAINBOW") {
                currentMode = MODE_RAINBOW;
            }
            else if (cmd == "LIGHT:ANIM:PULSE") {
                currentMode = MODE_PULSE;
            }
            
            FastLED.show(); 
        }

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
                float breath = (exp(sin(millis()/2000.0*PI)) - 0.36787944)*108.0;
                FastLED.setBrightness(breath);
                fill_solid(leds, NUM_LEDS, currentColor);
                FastLED.show();
            }
        }

        // FreeRTOS Yield: Gives the processor a tiny break to handle Wi-Fi
        vTaskDelay(5 / portTICK_PERIOD_MS); 
    }
}

// ==========================================
// SETUP
// ==========================================
void setup() {
    Serial.begin(115200);
    commandQueue = xQueueCreate(10, 32);

    FastLED.addLeds<WS2812, LED_PIN, GRB>(leds, NUM_LEDS).setCorrection(TypicalLEDStrip);
    FastLED.setBrightness(currentBrightness);
    FastLED.setMaxPowerInVoltsAndMilliamps(5, 500); 
    FastLED.clear(true);
    FastLED.show();

    WiFi.mode(WIFI_AP_STA); 
    WiFi.setTxPower(WIFI_POWER_19_5dBm);
    WiFi.disconnect(); 
    esp_wifi_set_channel(13, WIFI_SECOND_CHAN_NONE);

    if (esp_now_init() != ESP_OK) {
        Serial.println("Error initializing ESP-NOW");
        return;
    }
    esp_now_register_recv_cb(OnDataRecv);
    
    // START FREERTOS TASK
    // Pinned to Core 1 (same core that handles Wi-Fi by default)
    xTaskCreatePinnedToCore(LightTask, "TaskCore1", 10000, NULL, 1, &TaskCore1, 1);

    Serial.println("Smart Light Advanced FreeRTOS Engine Ready!");
}

void loop() {
    // The main loop is dead. FreeRTOS is the captain now.
    vTaskDelete(NULL); 
}
