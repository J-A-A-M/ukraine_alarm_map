#include <WiFi.h>
#include <HTTPClient.h>
#include <Update.h>

const char* ssid = ""; // Ваша WIFI-мережа
const char* password = ""; // Пароль до WIFI мережі
const char* firmwareUrl = "http://alerts.net.ua:8090/latest.bin";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
  
  updateFirmware();
}

void updateFirmware() {
  HTTPClient http;
  http.begin(firmwareUrl);
  Serial.println(firmwareUrl);
  int httpCode = http.GET();
  if (httpCode == 200) {
    int contentLength = http.getSize();
    bool canBegin = Update.begin(contentLength);
    if (canBegin) {
      size_t written = Update.writeStream(http.getStream());
      if (written == contentLength) {
        Serial.println("Written : " + String(written) + " successfully");
      } else {
        Serial.println("Written only : " + String(written) + "/" + String(contentLength) + " - Restarting");
        ESP.restart();
      }
      if (Update.end()) {
        Serial.println("OTA done!");
        if (Update.isFinished()) {
          Serial.println("Update successfully completed. Rebooting.");
          ESP.restart();
        } else {
          Serial.println("Update not finished? Something went wrong! - Restarting");
          ESP.restart();
        }
      } else {
        Serial.println("Error Occurred. Error #: " + String(Update.getError()) + " - Restarting");
        ESP.restart();
      }
    } else {
      Serial.println("Not enough space to begin OTA - Restarting");
      ESP.restart();
    }
  } else {
    Serial.print("Error on HTTP request: ");
    Serial.println(httpCode);
    Serial.println("Restarting...");
    ESP.restart();
  }
  http.end();
}

void loop() {
  // Your code here
}
