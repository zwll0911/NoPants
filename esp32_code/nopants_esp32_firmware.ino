#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <FastLED.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

struct GameButton {
  uint8_t pin;
  bool currentState;
  bool lastReading;
  unsigned long lastDebounceTime;
  String name;
};

// --- 1. HARDWARE SETUP ---
const int LED_PIN = 12;       
const int NUM_LEDS = 16;       
const int BRIGHTNESS = 150;   

const int SDA_PIN = 21;
const int SCL_PIN = 22;
const int LEFT_EAR_CH = 0;    
const int RIGHT_EAR_CH = 1;   

// --- INPUT PINS ---
const int PIN_CLK = 4;
const int PIN_DT = 16;
const int PIN_SW = 17; 

const int PIN_BTN1 = 19;
const int PIN_BTN2 = 18;
const int PIN_BTN3 = 0;

// --- 2. SERVO ANGLE CONFIGURATION (MIRRORED) ---
const int LEFT_EAR_FLAT = 90; 
const int LEFT_EAR_UP = 0;    

const int RIGHT_EAR_FLAT = 0; 
const int RIGHT_EAR_UP = 90;  

// --- 3. INITIALIZE OBJECTS ---
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(); 
CRGB leds[NUM_LEDS];

// --- FreeRTOS Task Handles ---
TaskHandle_t TaskCore0; // For Inputs
TaskHandle_t TaskCore1; // For Serial/Outputs

// Give every button its own independent memory and timer
GameButton btn1 = {PIN_BTN1, HIGH, HIGH, 0, "BTN:1"};
GameButton btn2 = {PIN_BTN2, HIGH, HIGH, 0, "BTN:2"};
GameButton btn3 = {PIN_BTN3, HIGH, HIGH, 0, "BTN:3"};
GameButton knobBtn = {PIN_SW, HIGH, HIGH, 0, "KNOB:PRESS"};

int lastStateCLK;

// ==========================================
// --- ESP-NOW SMART HOME HUB CONFIG ---
// ==========================================
// 1. The Phonebook (Smart Light MAC Address)
uint8_t smartLightMac[] = {0x80, 0xF3, 0xDA, 0x54, 0xD3, 0x84};

// 2. The Message Structure (Must match receiver exactly)
typedef struct struct_message {
  char command[32]; 
} struct_message;

struct_message outgoingData;
esp_now_peer_info_t peerInfo;

volatile bool deliveryComplete = false;
volatile bool deliverySuccess = false;

// 3. The Wireless Transmission Function
void sendSmartHomeCommand(String cmd) {
  memset(outgoingData.command, 0, sizeof(outgoingData.command));
  cmd.toCharArray(outgoingData.command, 32);

  int retries = 0;
  int maxRetries = 20; // Try up to 10 times!

  while (retries < maxRetries) {
    deliveryComplete = false; // Reset the receipt
    
    // Shoot the message!
    esp_err_t result = esp_now_send(smartLightMac, (uint8_t *) &outgoingData, sizeof(outgoingData));
    
    if (result == ESP_OK) {
      // Wait up to 100ms for the delivery receipt to come back
      unsigned long startWait = millis();
      while (!deliveryComplete && millis() - startWait < 100) {
        delay(1);
      }

      // If the receipt arrived and says SUCCESS, we are done!
      if (deliverySuccess) {
        Serial.println("SYSTEM: Sent -> " + cmd + " [DELIVERED ON ATTEMPT " + String(retries + 1) + "]");
        return; // Exit the function completely
      }
    }

    // If we get down here, the message failed or timed out.
    retries++;
    if (retries < maxRetries) {
      Serial.println("SYSTEM: Delivery failed. Retrying... (" + String(retries) + "/" + String(maxRetries) + ")");
      vTaskDelay(25 / portTICK_PERIOD_MS);
    }
  }

  // If we looped 4 times and it STILL failed, then the light is truly unplugged.
  Serial.println("SYSTEM: CRITICAL ERROR -> Could not reach Smart Light after " + String(maxRetries) + " attempts.");
}

// 4. The Delivery Receipt
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  // Record if it was a success or failure
  deliverySuccess = (status == ESP_NOW_SEND_SUCCESS);
  // Tell the sending loop that the receipt has arrived!
  deliveryComplete = true; 
}
// ==========================================


void setServoAngle(uint8_t channel, uint8_t angle) {
  uint16_t microsec = map(angle, 0, 180, 500, 2500);
  pwm.writeMicroseconds(channel, microsec);
}

// --- INDEPENDENT DEBOUNCE ALGORITHM ---
void checkButton(GameButton &btn) {
  bool currentReading = digitalRead(btn.pin);

  if (currentReading != btn.lastReading) {
    btn.lastDebounceTime = millis(); 
  }

  if ((millis() - btn.lastDebounceTime) > 25) {
    if (currentReading != btn.currentState) {
      btn.currentState = currentReading;
      if (btn.currentState == LOW) {
        Serial.println(btn.name); 
      }
    }
  }
  btn.lastReading = currentReading;
}

// ==========================================
// TASK 1: THE INPUT READER (Runs on Core 0)
// ==========================================
void InputTask(void * pvParameters) {
  for(;;) { 
    int currentStateCLK = digitalRead(PIN_CLK);
    if (currentStateCLK != lastStateCLK && currentStateCLK == 1) {
      if (digitalRead(PIN_DT) != currentStateCLK) {
        Serial.println("KNOB:RIGHT");
      } else {
        Serial.println("KNOB:LEFT");
      }
    }
    lastStateCLK = currentStateCLK;

    checkButton(btn1);
    checkButton(btn2);
    checkButton(btn3);
    checkButton(knobBtn);

    vTaskDelay(1 / portTICK_PERIOD_MS); 
  }
}

// ==========================================
// TASK 2: THE COMMAND ROUTER (Runs on Core 1)
// ==========================================
void CommandTask(void * pvParameters) {
  for(;;) {
    if (Serial.available() > 0) {
      String command = Serial.readStringUntil('\n');
      command.trim(); 

      // --- NEW: SMART HOME ROUTER ---
      // If Python sends "HOME:LIGHT:ON", we strip off "HOME:" and send "LIGHT:ON" wirelessly!
      if (command.startsWith("HOME:")) {
        String wirelessCmd = command.substring(5); 
        sendSmartHomeCommand(wirelessCmd);
      }
      // ------------------------------
      
      else if (command == "EARS:UP") {
        setServoAngle(LEFT_EAR_CH, LEFT_EAR_UP);
        setServoAngle(RIGHT_EAR_CH, RIGHT_EAR_UP); 
      } 
      else if (command == "EARS:FLAT") {
        setServoAngle(LEFT_EAR_CH, LEFT_EAR_FLAT);
        setServoAngle(RIGHT_EAR_CH, RIGHT_EAR_FLAT);
      }
      else if (command == "LED:RED") {
        fill_solid(leds, NUM_LEDS, CRGB::Red); 
        FastLED.show();
      }
      else if (command == "LED:BLUE") {
        fill_solid(leds, NUM_LEDS, CRGB::Blue);
        FastLED.show();
      }
      else if (command == "LED:CYAN") {
        fill_solid(leds, NUM_LEDS, CRGB::Cyan);
        FastLED.show();
      }
      else if (command == "LED:OFF") {
        FastLED.clear(true); 
      }
      else if (command.startsWith("LED:RGB:")) {
        int firstComma = command.indexOf(',');
        int secondComma = command.lastIndexOf(',');
        if (firstComma > 0 && secondComma > firstComma) {
            int r = command.substring(8, firstComma).toInt();
            int g = command.substring(firstComma + 1, secondComma).toInt();
            int b = command.substring(secondComma + 1).toInt();
            fill_solid(leds, NUM_LEDS, CRGB(r, g, b));
            FastLED.show();
        }
      }
      else if (command == "EARS:SHAKE") {
        for(int i = 0; i < 4; i++) {
            setServoAngle(LEFT_EAR_CH, 45); 
            setServoAngle(RIGHT_EAR_CH, 45);
            vTaskDelay(60 / portTICK_PERIOD_MS);
            setServoAngle(LEFT_EAR_CH, LEFT_EAR_UP); 
            setServoAngle(RIGHT_EAR_CH, RIGHT_EAR_UP);
            vTaskDelay(60 / portTICK_PERIOD_MS);
        }
      }
    }
    
    vTaskDelay(10 / portTICK_PERIOD_MS); 
  }
}

// ==========================================
// SETUP
// ==========================================
void setup() {
  Serial.begin(115200);

  Wire.begin(SDA_PIN, SCL_PIN);
  pwm.begin();
  pwm.setOscillatorFrequency(27000000);
  pwm.setPWMFreq(50); 

  FastLED.addLeds<WS2812, LED_PIN, GRB>(leds, NUM_LEDS).setCorrection(TypicalLEDStrip);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.clear(true); 

  setServoAngle(LEFT_EAR_CH, LEFT_EAR_FLAT);
  setServoAngle(RIGHT_EAR_CH, RIGHT_EAR_FLAT);

  pinMode(PIN_CLK, INPUT_PULLUP);
  pinMode(PIN_DT, INPUT_PULLUP);
  pinMode(PIN_SW, INPUT_PULLUP);
  pinMode(PIN_BTN1, INPUT_PULLUP);
  pinMode(PIN_BTN2, INPUT_PULLUP);
  pinMode(PIN_BTN3, INPUT_PULLUP);
  lastStateCLK = digitalRead(PIN_CLK);

  // --- INITIALIZE WIFI & ESP-NOW ---
  WiFi.mode(WIFI_AP_STA);
  WiFi.setTxPower(WIFI_POWER_19_5dBm); // Force the antenna amplifier to maximum power!
  WiFi.disconnect();
  esp_wifi_set_channel(13, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    Serial.println("SYSTEM: Error initializing ESP-NOW");
  } else {
    // Register the Delivery Receipt function!
    esp_now_register_send_cb(OnDataSent);

    // NEW: Clear the struct memory so no garbage data breaks the antenna!
    esp_now_peer_info_t peerInfo = {}; 
    
    // Register the Smart Light in the phonebook
    memcpy(peerInfo.peer_addr, smartLightMac, 6);
    peerInfo.channel = 13;  
    peerInfo.encrypt = false;
    peerInfo.ifidx = WIFI_IF_STA;
    
    if (esp_now_add_peer(&peerInfo) != ESP_OK){
      Serial.println("SYSTEM: Failed to add Smart Light peer");
    } else {
      Serial.println("SYSTEM: Smart Light registered successfully!");
    }
  }
  // ---------------------------------

  xTaskCreatePinnedToCore(InputTask, "TaskCore0", 10000, NULL, 1, &TaskCore0, 0);
  xTaskCreatePinnedToCore(CommandTask, "TaskCore1", 10000, NULL, 1, &TaskCore1, 1);

  Serial.println("ESP32 FreeRTOS Initialized.");
}

void loop() {
  vTaskDelete(NULL); 
}
