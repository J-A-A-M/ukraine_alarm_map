#define JAAM_VERSION 2

#include <WiFi.h>
#include <HTTPUpdate.h>
#include <Preferences.h>

WiFiClient client;

Preferences preferences;

const char* ssid = ""; // Ваша WIFI-мережа
const char* password = ""; // Пароль до WIFI мережі
const char* userSsid = ""; // WIFI-мережа замовника
const char* userPassword = ""; // Пароль до WIFI мережі замовника


const char* firmwareUrl = "http://jaam.net.ua:2095/jaam.bin";

String identifier = "github";

void updateUserWifiCreds() {
  Serial.println("Disconnecting from WiFi...");
  bool disconnect = WiFi.disconnect(false, true);
  Serial.println(disconnect ? "Disconnected from WiFi" : "Disconnect from WiFi failed");
  if (userSsid != "" && userPassword != "") {
    WiFi.begin(userSsid, userPassword);
    WiFi.waitForConnectResult(10000);
    Serial.printf("Saved User WiFi creds. SSID: %s\n", userSsid);
  } else {
    Serial.println("No User WiFi creds, erased..."); }
}

void updateFirmware() {
  preferences.begin("storage", false);
  preferences.putString("id", identifier);

#if JAAM_VERSION == 1
  // Default value for JAAM 1
  preferences.putString("id", "JAAM");
  preferences.putInt("legacy", 0); // JAAM 1

  Serial.println("Default JAAM 1 settings applied...");

#elif JAAM_VERSION == 2

  // Default value for JAAM 2
  preferences.putString("id", "JAAM2");
  preferences.putInt("legacy", 3); // JAAM 2
  preferences.putInt("brightness", 50); // global brightness in %
  preferences.putInt("brd", 50); // day brightness in %
  preferences.putInt("brn", 7); // night brightness in %
  preferences.putInt("ddon", 1); // day/night mode for display (0 - off, 1 - on)
  preferences.putInt("bra", 1); // brightness mode (0 - off, 1 - day/night, 2 - light sensor)
  preferences.putInt("bs", 15); // service led brightness in %
  preferences.putInt("mapmode", 1); // map mode (0 - off, 1 - alarms, 2 - weather, 3 - flag, 4 - random colors, 5 - lamp)
  preferences.putInt("dm", 1); // display mode (0 - off, 1 - clock, 2 - weather, 3 - tech info, 4 - climate, 5 - combine)
  preferences.putInt("dmt", 3); // display mode switch time in seconds
  preferences.putInt("bm", 1); // button 1 click action (map mode switching)
  preferences.putInt("b2m", 2); // button 2 click action (display mode switching)
  preferences.putInt("hd", 25); // Kyiv
  preferences.putInt("anm", 2); // alarm notify mode (0 - off, 1 - color, 2 - color + animation)
  preferences.putInt("abt", 1); // alarm blink time in seconds
  preferences.putInt("aas", 1); // auto alarm mode (0 - off, 1 - home + neighbors, 2 - home only)
  preferences.putInt("sdm", 1); // service leds display mode (0 - off, 1 - on)
  preferences.putInt("mos", 1); // minute of silence (0 - off, 1 - on)
  preferences.putInt("somos", 1); // sounds on minute of silence (0 - off, 1 - on)
  preferences.putInt("soa", 1); // sounds on alert (0 - off, 1 - on)
  preferences.putInt("mson", 1); // mute sounds on night mode (0 - off, 1 - on)
  preferences.putInt("mv", 60); // melody volume %
  preferences.putInt("nfwn", 1); // notify on new firmware (0 - off, 1 - on)
  preferences.putInt("fwuc", 0); // firmware update channel (0 - stable, 1 - beta)

  Serial.println("Default JAAM 2 settings applied...");

#endif

  preferences.end();

  if (firmwareUrl == "") {
    Serial.println("No firmware URL provided, skipping firmware update...");
    updateUserWifiCreds();
    Serial.println("Now you can flash the firmware manually!");
    return;
  }

  t_httpUpdate_return fwRet = httpUpdate.update(client, firmwareUrl);
}

void setup() {
  Serial.begin(115200);
  uint64_t chipid = ESP.getEfuseMac();
  Serial.printf("Chip ID: %04x%04x\n", (uint32_t)(chipid >> 32), (uint32_t)chipid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.printf("Connecting to %s...\n", ssid);
    httpUpdate.rebootOnUpdate(false);
    httpUpdate.onStart([]() {
      Serial.println("Firmware update started!");
    });
    httpUpdate.onProgress([](int progress, int total) {
      if (total == 0) return;
      char progressText[5];
      Serial.printf("Progress: %d%%\n", progress / (total / 100));
    });
    httpUpdate.onEnd([]() {
      Serial.println("Firmware update successfully completed!");
      updateUserWifiCreds();
      delay(1000);
      ESP.restart();
    });
    httpUpdate.onError([](int error) {
      Serial.printf("Firmware update error occurred. Error (%d): %s\n", error, httpUpdate.getLastErrorString().c_str());
    });
  }
  Serial.println("Connected to WiFi");

  updateFirmware();
}

void loop() {
  // Your code here
}
