#include "Arduino.h"
#include "WiFi.h"
#include "Audio.h"

#define I2S_DOUT      14
#define I2S_BCLK      13
#define I2S_LRC       12

Audio audio;
String receivedText = "";
bool newTextAvailable = false;

// WiFi credentials
const char* ssid = "Emads iPhone";
const char* password = "Sept2020";

void setup()
{
  Serial.begin(115200);
  Serial.println("TTS Intercom System Starting...");

  // Connect to WiFi
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Initialize audio output
  audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
  audio.setVolume(100);
  
  // Send initial message
  audio.connecttospeech("TTS Intercom ready. Send text to speak.", "en");
  Serial.println("Ready! Send text to be spoken through the serial monitor.");
}

void loop()
{
  // Process audio playback
  audio.loop();
  
  // Check for incoming serial data
  while (Serial.available()) {
    char c = Serial.read();
    
    // If newline or carriage return, process the message
    if (c == '\n' || c == '\r') {
      if (receivedText.length() > 0) {
        newTextAvailable = true;
      }
    } else {
      // Add character to the received text
      receivedText += c;
    }
  }
  
  // Process new text if available
  if (newTextAvailable) {
    Serial.print("Speaking: ");
    Serial.println(receivedText);
    
    // Convert text to speech
    audio.connecttospeech(receivedText.c_str(), "en");
    
    // Reset for next message
    receivedText = "";
    newTextAvailable = false;
  }
}

void audio_info(const char *info) {
  Serial.print("audio_info: ");
  Serial.println(info);
}