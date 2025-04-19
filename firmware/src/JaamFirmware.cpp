#include "JaamUtils.h"
#include <WiFiManager.h>
#include <ESPAsyncWebServer.h>
#include <StreamString.h>
#include <ESPmDNS.h>
#include <async.h>
#include <ArduinoJson.h>
#include <NTPtime.h>
#if ARDUINO_OTA_ENABLED
#include <ArduinoOTA.h>
#endif
#include "JaamHomeAssistant.h"
// to ignore the warning about the unused variable
#define FASTLED_INTERNAL
#include <FastLED.h>
#include "JaamDisplay.h"
#if FW_UPDATE_ENABLED
#include <HTTPUpdate.h>
#endif
#include <ArduinoWebsockets.h>
#include "JaamLightSensor.h"
#include "JaamClimateSensor.h"
#include "JaamButton.h"
#include "JaamSettings.h"
#if BUZZER_ENABLED
#include <melody_player.h>
#include <melody_factory.h>
#endif
#include <esp_task_wdt.h>
#if DFPLAYER_PRO_ENABLED
#include <DFRobot_DF1201S.h>
#include <HardwareSerial.h>
#endif

JaamSettings settings;
Firmware currentFirmware;
#if FW_UPDATE_ENABLED
Firmware latestFirmware;
char bin_name[51] = "";
#endif

using namespace websockets;

WiFiManager       wm;
WiFiClient        client;
WebsocketsClient  client_websocket;
AsyncWebServer    webserver(80);
NTPtime           timeClient(2);
DSTime            dst(3, 0, 7, 3, 10, 0, 7, 4); //https://en.wikipedia.org/wiki/Eastern_European_Summer_Time
Async             asyncEngine = Async(20);
JaamDisplay       display;
JaamLightSensor   lightSensor;
JaamClimateSensor climate;
JaamHomeAssistant ha;
std::pair<std::map<int, int>, std::map<int, int>> haDisplayModeMap;
std::pair<std::map<int, int>, std::map<int, int>> haMapModeMap;
#if BUZZER_ENABLED
MelodyPlayer* player;
#endif
#if DFPLAYER_PRO_ENABLED
HardwareSerial dfSerial(2);
DFRobot_DF1201S dfplayer;
String* dynamicTracks;
SettingListItem* dynamicTrackNames;
int totalFiles = 0;
#endif

enum ServiceLed {
  POWER,
  WIFI,
  DATA,
  HA,
  UPD_AVAILABLE
};

enum SoundType {
  MIN_OF_SILINCE,
  MIN_OF_SILINCE_END,
  REGULAR,
  ALERT_ON,
  ALERT_OFF,
  EXPLOSIONS,
  CRITICAL_MIG,
  CRITICAL_STRATEGIC,
  CRITICAL_MIG_MISSILES,
  CRITICAL_BALLISTIC_MISSILES,
  CRITICAL_STRATEGIC_MISSILES,
  SINGLE_CLICK,
  LONG_CLICK
};

struct ServiceMessage {
  const char* title;
  const char* message;
  int textSize;
  long endTime;
  int expired;
};

ServiceMessage serviceMessage;

CRGB strip[MAIN_LEDS_COUNT];
CRGB bg_strip[100];
CRGB service_strip[5];
int service_strip_update_index = 0;

std::map<int, std::pair<int, long>> id_to_alerts; //regionId to alert state and time
std::map<int, std::pair<int, long>> led_to_alerts; // ledPosition to alert state and time
std::map<int, float>                id_to_weather; //regionId to temperature
std::map<int, float>                led_to_weather; // ledPosition to temperature
std::map<int, long>                 id_to_explosions_notifications; //regionId to explosion time
std::map<int, long>                 led_to_explosions_notifications; // ledPosition to explosion time
std::map<int, long>                 id_to_missiles_notifications; //regionId to missiles time
std::map<int, long>                 led_to_missiles_notifications; // ledPosition to missils time
std::map<int, long>                 id_to_kabs_notifications; //regionId to kabs time
std::map<int, long>                 led_to_kabs_notifications; // ledPosition to kabs time
std::map<int, std::pair<int, long>> id_to_missiles; //regionId to missiles state and time
std::map<int, std::pair<int, long>> led_to_missiles; // ledPosition to missiles state and time
std::map<int, long>                 id_to_drones_notifications; //regionId to missiles time
std::map<int, long>                 led_to_drones_notifications; // ledPosition to missils time
std::map<int, std::pair<int, long>> id_to_drones; //regionId to drones state and time
std::map<int, std::pair<int, long>> led_to_drones; // ledPosition to drones state and time
std::map<int, std::pair<int, long>> id_to_kabs; //regionId to kabs state and time
std::map<int, std::pair<int, long>> led_to_kabs; // ledPosition to kabs state and time
std::map<int, std::pair<int, long>> id_to_energy; //regionId to energy state and time
std::map<int, std::pair<int, long>> led_to_energy; // ledPosition to energy state and time
std::map<int, int>                id_to_radiation; //regionId to radiation
std::map<int, int>                led_to_radiation; // ledPosition to radiation
std::map<int, int>                  led_to_flag_color; // ledPosition to flag color
std::pair<int, int*>                homeDistrictMapping; // id to ledPosition home district mapping


std::pair<int, int*> (*ledMapping)(int key);

bool      isFirstDataFetchCompleted = false;

float     brightnessFactor = 0.5f;
int       minBrightness = 1;
float     minBlinkBrightness = 0.05f;

bool    shouldWifiReconnect = false;
bool    websocketReconnect = false;
bool    isDaylightSaving = false;
time_t  websocketLastPingTime = 0;
bool    initUpdate = false;
#if FW_UPDATE_ENABLED
bool    fwUpdateAvailable = false;
char    newFwVersion[25];
#endif
char    currentFwVersion[25];
bool    apiConnected;
bool    haConnected;
bool    dfPlayerConnected;
int     prevMapMode = 1;
int     volumeCurrent = 0;
int     volumeDay = 0;
int     volumeNight = 0;
bool    alarmNow = false;
bool    alarmDronesNow = false;
bool    alarmMissilesNow = false;
bool    alarmKabsNow = false;
bool    pinAlarmNow = false;
long    homeExplosionTime = 0;
bool    minuteOfSilence = false;
bool    uaAnthemPlaying = false;
short   clockBeepInterval = -1;
bool    isMapOff = false;
bool    isDisplayOff = false;
bool    nightMode = false;
int     prevBrightness = -1;
int     needRebootWithDelay = -1;
int     beepHour = -1;
char    uptimeChar[25];
float   cpuTemp;
float   usedHeapSize;
float   freeHeapSize;
int     wifiSignal;

enum GlobalNotificationType {
  IS_MIG,
  IS_STRATEGIC,
  IS_MIG_MISSILES,
  IS_BALLISTIC_MISSILES,
  IS_STRATEGIC_MISSILES  
};

std::map<char, bool> GlobalNotifications = {
  {IS_MIG, false},
  {IS_STRATEGIC, false},
  {IS_MIG_MISSILES, false},
  {IS_BALLISTIC_MISSILES, false},
  {IS_STRATEGIC_MISSILES, false}
};

int     ledsBrightnessLevels[BR_LEVELS_COUNT]; // Array containing LEDs brightness values
int     currentDimDisplay = 0;

// 0 - Time
// 1 - Home District Temperature
// 2 - Climate Temperature
// 3 - Climate Humidity
// 4 - Climate Pressure
// 5 - Energy monitoring
int     currentDisplayToggleMode = 0;
int     currentDisplayToggleIndex = 0;

JaamButton buttons;

#define NIGHT_BRIGHTNESS_LEVEL 2

int binsCount = 0;
char* bin_list[MAX_BINS_LIST_SIZE];

int testBinsCount = 0;
char*  test_bin_list[MAX_BINS_LIST_SIZE];

char chipID[13];
char localIP[16];

bool isBgStripEnabled() {
  return settings.getInt(BG_LED_PIN) > -1 && settings.getInt(BG_LED_COUNT) > 0;
}

bool isServiceStripEnabled() {
  return settings.getInt(SERVICE_LED_PIN) > -1;
}

bool isAlertPinEnabled() {
  return settings.getInt(ALERT_PIN) > -1;
}

bool isClearPinEnabled() {
  return settings.getInt(CLEAR_PIN) > -1;
}

bool isBuzzerEnabled() {
  return settings.getInt(BUZZER_PIN) > -1;
}

bool isDFPlayerEnabled() {
  return settings.getInt(DF_RX_PIN) > -1 && settings.getInt(DF_TX_PIN) > -1;
}

bool isAnalogLightSensorEnabled() {
  return settings.getInt(LIGHT_SENSOR_PIN) > -1;
}


CRGB fromRgb(int r, int g, int b, float brightness) {
  // use brightnessFactor as a multiplier to get scaled brightness
  int scaledBrightness = (brightness == 0.0f) ? 0 : round(max(brightness, minBrightness * 1.0f) * 255.0f / 100.0f * brightnessFactor);
  return CRGB().setRGB(r, g, b).nscale8_video(scaledBrightness);
}

CRGB fromHue(int hue, float brightness) {
  RGBColor rgb = hue2rgb(hue);
  return fromRgb(rgb.r, rgb.g, rgb.b, brightness);
}

const char* getNameById(SettingListItem list[], int id, int size) {
  for (int i = 0; i < size; i++) {
    if (list[i].id == id) {
      return list[i].name;
    }
  }
  return "";
}

int getIndexById(SettingListItem list[], int id, int size) {
  for (int i = 0; i < size; i++) {
    if (list[i].id == id) {
      return i;
    }
  }
  return 0;
}

String getTrackById(int id) {
#if DFPLAYER_PRO_ENABLED
  if (dfPlayerConnected) {
    for (int i = 0; i < totalFiles; i++) {
      if (dynamicTrackNames[i].id == id) {
        return dynamicTracks[i];
      }
    }
  }
#endif
  return "";
}

std::pair<int, const char**> getNames(SettingListItem list[], int size, bool excludeIgnored = false) {
  int count = 0;
  for (int i = 0; i < size; i++) {
    if (excludeIgnored && !list[i].ignore) {
      count++;
    }
  }
  const char** names = new const char*[count];
  int index = 0;
  for (int i = 0; i < size; i++) {
    if (excludeIgnored && !list[i].ignore) {
      names[index] = list[i].name;
      index++;
    }
  }
  return std::make_pair(count, names);
}

// Forward declarations
void displayCycle();

void showServiceMessage(const char* message, const char* title = "", int duration = 2000) {
  if (!display.isDisplayAvailable()) return;
  serviceMessage.title = title;
  serviceMessage.message = message;
  serviceMessage.textSize = display.getTextSizeToFitDisplay(message);
  serviceMessage.endTime = millis() + duration;
  serviceMessage.expired = false;
  displayCycle();
}

void rebootDevice(int time = 2000, bool async = false) {
  if (async) {
    needRebootWithDelay = time;
    return;
  }
  showServiceMessage("Перезавантаження..", "", time);
  delay(time);
  display.clearDisplay();
  display.display();
  ESP.restart();
}

int expMap(int x, int in_min, int in_max, int out_min, int out_max) {
  // Apply exponential transformation to the original input value x
  float normalized = (float)(x - in_min) / (in_max - in_min);
  float scaled = pow(normalized, 2);

  // Map the scaled value to the output range
  return (int)(scaled * (out_max - out_min) + out_min);
}

int expMapLinear(int x, int in_min, int in_max, int out_min, int out_max) {
  float normalized = (float)(x - in_min) / (in_max - in_min);
  float scaled = pow(normalized, 2);
  return (int)(scaled * (out_max - out_min) + out_min);
}

void playMelody(const char* melodyRtttl) {
#if BUZZER_ENABLED
  if (isBuzzerEnabled()) {
    Melody melody = MelodyFactory.loadRtttlString(melodyRtttl);
    player->playAsync(melody);
  }
#endif
}

void playTrack(String track) {
#if DFPLAYER_PRO_ENABLED
  if (dfPlayerConnected && track != "") {
    dfplayer.playSpecFile(track);
    LOG.printf("Track played: %s (%s)\n", track.c_str(), dfplayer.getFileName());
  }
#endif
}

void playMelody(SoundType type) {
#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
  switch (type) {
  case MIN_OF_SILINCE:
    playMelody(MOS_BEEP);
    playTrack("/13.mp3");
    break;
  case MIN_OF_SILINCE_END:
    playMelody(UA_ANTHEM);
    break;
  case ALERT_ON:
    playMelody(MELODIES[settings.getInt(MELODY_ON_ALERT)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_ALERT)));
    break;
  case ALERT_OFF:
    playMelody(MELODIES[settings.getInt(MELODY_ON_ALERT_END)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_ALERT_END)));
    break;
  case EXPLOSIONS:
    playMelody(MELODIES[settings.getInt(MELODY_ON_EXPLOSION)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_EXPLOSION)));
    break;
  case CRITICAL_MIG:
    playMelody(MELODIES[settings.getInt(MELODY_ON_CRITICAL_MIG)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_CRITICAL_MIG)));
    break; 
  case CRITICAL_STRATEGIC:
    playMelody(MELODIES[settings.getInt(MELODY_ON_CRITICAL_STRATEGIC)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_CRITICAL_STRATEGIC)));
    break;
  case CRITICAL_MIG_MISSILES:
    playMelody(MELODIES[settings.getInt(MELODY_ON_CRITICAL_MIG_MISSILES)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_CRITICAL_MIG_MISSILES)));
    break;
  case CRITICAL_BALLISTIC_MISSILES:
    playMelody(MELODIES[settings.getInt(MELODY_ON_CRITICAL_BALLISTIC_MISSILES)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_CRITICAL_BALLISTIC_MISSILES)));
    break;
  case CRITICAL_STRATEGIC_MISSILES:
    playMelody(MELODIES[settings.getInt(MELODY_ON_CRITICAL_STRATEGIC_MISSILES)]);
    playTrack(getTrackById(settings.getInt(TRACK_ON_CRITICAL_STRATEGIC_MISSILES)));
    break;
  case REGULAR:
    playMelody(CLOCK_BEEP);
    playTrack("/12.mp3");
    break;
  case SINGLE_CLICK:
    playMelody(SINGLE_CLICK_SOUND);
    playTrack("/13.mp3");
    break;
  case LONG_CLICK:
    playMelody(LONG_CLICK_SOUND);
    playTrack("/12.mp3");
    break;
  }
#endif
}

bool isItNightNow() {
  int dayStart = settings.getInt(DAY_START);
  int nightStart = settings.getInt(NIGHT_START);
  // if day and night start time is equels it means it's always day, return day
  if (dayStart == nightStart) return false;

  int currentHour = timeClient.hour();

  // handle case, when night start hour is bigger than day start hour, ex. night start at 22 and day start at 9
  if (nightStart > dayStart) return currentHour >= nightStart || currentHour < dayStart ? true : false;

  // handle case, when day start hour is bigger than night start hour, ex. night start at 1 and day start at 8
  return currentHour < dayStart && currentHour >= nightStart ? true : false;
}

// Determine the current brightness level
int getCurrentBrightnessLevel() {
  int currentValue = 0;
  int maxValue;
  if (lightSensor.isLightSensorAvailable()) {
    // Digital light sensor has higher priority. BH1750 measurmant range is 0..27306 lx. 500 lx - very bright indoor environment.
    currentValue = round(lightSensor.getLightLevel(settings.getFloat(LIGHT_SENSOR_FACTOR)));
    maxValue = 500;
  } else if (isAnalogLightSensorEnabled()) {
    // reads the input on analog pin (value between 0 and 4095)
    currentValue = lightSensor.getPhotoresistorValue(settings.getFloat(LIGHT_SENSOR_FACTOR));
    // 2600 - very bright indoor environment.
    maxValue = 2600;
  }
  int level = map(min(currentValue, maxValue), 0, maxValue, 0, BR_LEVELS_COUNT - 1);
  // LOG.print("Brightness level: ");
  // LOG.println(level);
  return level;
}

int getNightModeType() {
  // Night Mode activated by button
  if (nightMode) return 1;
  // Night mode activated by time
  if (settings.getInt(BRIGHTNESS_MODE) == 1 && isItNightNow()) return 2;
  // Night mode activated by sensor
  if (settings.getInt(BRIGHTNESS_MODE) == 2 && getCurrentBrightnessLevel() <= NIGHT_BRIGHTNESS_LEVEL) return 3;
  // Night mode is off
  return 0;
}

bool needToPlaySound(SoundType type) {
#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
  // do not play any sound before websocket connection
  if (!isFirstDataFetchCompleted) return false;

  // ignore mute on alert
  if (SoundType::ALERT_ON == type && settings.getBool(SOUND_ON_ALERT) && settings.getBool(IGNORE_MUTE_ON_ALERT)) return true;

  // disable sounds on night mode by time only
  if (settings.getBool(MUTE_SOUND_ON_NIGHT) && isItNightNow()) return false;

  switch (type) {
  case MIN_OF_SILINCE:
    return settings.getBool(SOUND_ON_MIN_OF_SL);
  case MIN_OF_SILINCE_END:
    return settings.getBool(SOUND_ON_MIN_OF_SL);
  case ALERT_ON:
    return settings.getBool(SOUND_ON_ALERT);
  case ALERT_OFF:
    return settings.getBool(SOUND_ON_ALERT_END);
  case EXPLOSIONS:
    return settings.getBool(SOUND_ON_EXPLOSION);
  case CRITICAL_MIG:
    return settings.getBool(SOUND_ON_CRITICAL_MIG);
  case CRITICAL_STRATEGIC:
    return settings.getBool(SOUND_ON_CRITICAL_STRATEGIC);
  case CRITICAL_MIG_MISSILES:
    return settings.getBool(SOUND_ON_CRITICAL_MIG_MISSILES);
  case CRITICAL_BALLISTIC_MISSILES:
    return settings.getBool(SOUND_ON_CRITICAL_BALLISTIC_MISSILES);
  case CRITICAL_STRATEGIC_MISSILES:
    return settings.getBool(SOUND_ON_CRITICAL_STRATEGIC_MISSILES);
  case REGULAR:
    return settings.getBool(SOUND_ON_EVERY_HOUR);
  case SINGLE_CLICK:
  case LONG_CLICK:
    return settings.getBool(SOUND_ON_BUTTON_CLICK);
  }
#endif
  return false;
}

void servicePin(ServiceLed type, uint8_t status, bool force) {
  if (force || ((settings.getInt(LEGACY) == 0 || settings.getInt(LEGACY) == 3) && settings.getBool(SERVICE_DIODES_MODE))) {
    int pin = 0;
    int scaledBrightness = (settings.getInt(BRIGHTNESS_SERVICE) == 0) ? 0 : round(max(settings.getInt(BRIGHTNESS_SERVICE), minBrightness) * 255.0f / 100.0f * brightnessFactor);
    switch (type) {
      case POWER:
        pin = settings.getInt(POWER_PIN);
        service_strip[0] = status ? CRGB(CRGB::Red).nscale8_video(scaledBrightness) : CRGB::Black;
        break;
      case WIFI:
        pin = settings.getInt(WIFI_PIN);
        service_strip[1] = status ? CRGB(CRGB::Blue).nscale8_video(scaledBrightness) : CRGB::Black;
        break;
      case DATA:
        pin = settings.getInt(DATA_PIN);
        service_strip[2] = status ? CRGB(CRGB::Green).nscale8_video(scaledBrightness) : CRGB::Black;
        break;
      case HA:
        pin = settings.getInt(HA_PIN);
        service_strip[3] = status ? CRGB(CRGB::Yellow).nscale8_video(scaledBrightness) : CRGB::Black;
        break;
      case UPD_AVAILABLE:
        pin = settings.getInt(UPD_AVAILABLE_PIN);
        // this service led will be handled in the main loop for animation
#if TEST_MODE
        // show in test mode only
        service_strip[4] = status ? CRGB(CRGB::White).nscale8_video(scaledBrightness) : CRGB::Black;
#endif
        break;
    }
    if (pin > 0 && settings.getInt(LEGACY) == 0) {
      digitalWrite(pin, status);
    }
    if (isServiceStripEnabled() && settings.getInt(LEGACY) == 3) {
      FastLED.show();
    }
  }
}

void reportSettingsChange(const char* settingKey, const char* settingValue) {
  char settingsInfo[100];
  JsonDocument settings;
  settings[settingKey] = settingValue;
  sprintf(settingsInfo, "settings:%s", settings.as<String>().c_str());
  client_websocket.send(settingsInfo);
  LOG.printf("Sent settings analytics: %s\n", settingsInfo);
}

void reportSettingsChange(const char* settingKey, int newValue) {
  char settingsValue[10];
  sprintf(settingsValue, "%d", newValue);
  reportSettingsChange(settingKey, settingsValue);
}

void reportSettingsChange(const char* settingKey, float newValue) {
  char settingsValue[10];
  sprintf(settingsValue, "%.1f", newValue);
  reportSettingsChange(settingKey, settingsValue);
}

static void printNtpStatus(NTPtime* timeClient) {
  LOG.print("NTP status: ");
    switch (timeClient->NTPstatus()) {
      case 0:
        LOG.println("OK");
        LOG.print("Current date and time: ");
        LOG.println(timeClient->unixToString("DD.MM.YYYY hh:mm:ss"));
        break;
      case 1:
        LOG.println("NOT_STARTED");
        break;
      case 2:
        LOG.println("NOT_CONNECTED_WIFI");
        break;
      case 3:
        LOG.println("NOT_CONNECTED_TO_SERVER");
        break;
      case 4:
        LOG.println("NOT_SENT_PACKET");
        break;
      case 5:
        LOG.println("WAITING_REPLY");
        break;
      case 6:
        LOG.println("TIMEOUT");
        break;
      case 7:
        LOG.println("REPLY_ERROR");
        break;
      case 8:
        LOG.println("NOT_CONNECTED_ETHERNET");
        break;
      default:
        LOG.println("UNKNOWN_STATUS");
        break;
    }
}

void syncTime(int8_t attempts) {
  timeClient.tick();
  if (timeClient.status() == UNIX_OK) return;
  LOG.println("Time not synced yet!");
  printNtpStatus(&timeClient);
  int8_t count = 1;
  while (timeClient.NTPstatus() != NTP_OK && count <= attempts) {
    LOG.printf("Attempt #%d of %d\n", count, attempts);
    if (timeClient.NTPstatus() != NTP_WAITING_REPLY) {
      LOG.println("Force update!");
      timeClient.updateNow();
    }
    timeClient.tick();
    if (count < attempts) delay(1000);
    count++;
    printNtpStatus(&timeClient);
  }
}

void displayMessage(const char* message, const char* title = "", int messageTextSize = -1) {
  display.displayMessage(message, title, messageTextSize);
}

char* getLocalIP() {
  strcpy(localIP, WiFi.localIP().toString().c_str());
  return localIP;
}

static void wifiEvents(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED: {
      char softApIp[16];
      strcpy(softApIp, WiFi.softAPIP().toString().c_str());
      displayMessage(softApIp, "Введіть у браузері:");
      WiFi.removeEvent(wifiEvents);
      break;
    }
    default:
      break;
  }
}

void apCallback(WiFiManager* wifiManager) {
  const char* message = wifiManager->getConfigPortalSSID().c_str();
  displayMessage(message, "Підключіться до WiFi:");
  WiFi.onEvent(wifiEvents);
}

void saveConfigCallback() {
  showServiceMessage(wm.getWiFiSSID(true).c_str(), "Збережено AP:");
  delay(2000);
  rebootDevice();
}

#if ARDUINO_OTA_ENABLED
void showOtaUpdateErrorMessage(ota_error_t error) {
  switch (error) {
    case OTA_AUTH_ERROR:
      showServiceMessage("Авторизація", "Помилка оновлення:", 5000);
      break;
    case OTA_CONNECT_ERROR:
      showServiceMessage("Збій підключення", "Помилка оновлення:", 5000);
      break;
    case OTA_RECEIVE_ERROR:
      showServiceMessage("Збій отримання", "Помилка оновлення:", 5000);
      break;
    default:
      showServiceMessage("Щось пішло не так", "Помилка оновлення:", 5000);
      break;
  }
}
#endif

void mapUpdate(float percents) {
  int currentBrightness = settings.getInt(CURRENT_BRIGHTNESS);
  CRGB hue = fromHue(86, currentBrightness);
  int ledsCount = round(MAIN_LEDS_COUNT * percents);
  for (uint16_t i = 0; i < MAIN_LEDS_COUNT; i++) {
    if (i < ledsCount) {
      strip[i] = hue;
    } else {
      strip[i] = CRGB::Black;
    }
  }
  if (isBgStripEnabled()) {
    int bgPixelCount = settings.getInt(BG_LED_COUNT);
    int bgLedsCount = round(bgPixelCount * percents);
    float bgBrightnessFactor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    CRGB bgHue = fromHue(86, currentBrightness * bgBrightnessFactor);

    for (uint16_t i = 0; i < bgPixelCount; i++) {
      if (i < bgLedsCount) {
        bg_strip[i] = hue;
      } else {
        bg_strip[i] = CRGB::Black;
      }
    }
  }
  if (isServiceStripEnabled()) {
    fill_solid(service_strip, 5, CRGB::Black);
    service_strip[service_strip_update_index] = hue;
    if (service_strip_update_index == 4) {
      service_strip_update_index = 0;
    } else {
      service_strip_update_index++;
    }
  }
  FastLED.show();
}

#if FW_UPDATE_ENABLED || ARDUINO_OTA_ENABLED
void showUpdateProgress(size_t progress, size_t total) {
  if (total == 0) return;
  char progressText[5];
  sprintf(progressText, "%d%%", progress / (total / 100));
  showServiceMessage(progressText, "Оновлення:");
  mapUpdate(progress * 1.0f / total);
}

void showUpdateStart() {
  showServiceMessage("Починаємо!", "Оновлення:");
  delay(1000);
}

void showUpdateEnd() {
  showServiceMessage("Перезавантаження..", "Оновлення:");
  delay(1000);
}
#endif

#if FW_UPDATE_ENABLED
void showHttpUpdateErrorMessage(int error) {
  switch (error) {
    case HTTP_UE_TOO_LESS_SPACE:
      showServiceMessage("Замало місця", "Помилка оновлення:", 5000);
      break;
    case HTTP_UE_SERVER_NOT_REPORT_SIZE:
      showServiceMessage("Невідомий розмір файлу", "Помилка оновлення:", 5000);
      break;
    case HTTP_UE_BIN_FOR_WRONG_FLASH:
      showServiceMessage("Неправильний тип пам'яті", "Помилка оновлення:", 5000);
      break;
    default:
      showServiceMessage("Щось пішло не так", "Помилка оновлення:", 5000);
      break;
  }
}
#endif

void initBroadcast() {
  LOG.println("Init network device broadcast");
  const char* broadcastName = settings.getString(BROADCAST_NAME);
  if (!MDNS.begin(broadcastName)) {
    LOG.println("Error setting up mDNS responder");
    showServiceMessage("Помилка mDNS");
    while (1) {
      delay(1000);
    }
  }
  LOG.printf("Device broadcasted to network: %s.local", broadcastName);
  LOG.println();
}

bool isAlertInNeighboringDistricts() {
  int regionId = settings.getInt(HOME_DISTRICT);
  auto neighborsPair = NEIGHBORING_DISTRICS[regionId];
  int count = neighborsPair.first;
  int* neighbors = neighborsPair.second;
  for (int i = 0; i < count; i++) {
    if (id_to_alerts[neighbors[i]].first != 0) {
      return true;
    }
  }
  return false;
}

int getCurrentMapMode() {
  if (minuteOfSilence || uaAnthemPlaying) return 3; // ua flag

  int homeRegionId = settings.getInt(HOME_DISTRICT);
  int alarmMode = settings.getInt(ALARMS_AUTO_SWITCH);
  if (alarmMode == 1 && isAlertInNeighboringDistricts()) {
    return 1; // alerts mode
  }
  if (alarmMode >= 1 && id_to_alerts[homeRegionId].first != 0) {
    return 1; // alerts mode
  }
  return isMapOff ? 0 : settings.getInt(MAP_MODE);
}

void onMqttStateChanged(bool haStatus) {
  LOG.print("Home Assistant MQTT state changed! State: ");
  LOG.println(haStatus ? "Connected" : "Disconnected");
  haConnected = haStatus;
  servicePin(HA, haConnected ? HIGH : LOW, false);
  if (haConnected) {
    // Update HASensors values (Unlike the other device types, the HASensor doesn't store the previous value that was set. It means that the MQTT message is produced each time the setValue method is called.)
    ha.setMapModeCurrent(getNameById(MAP_MODES, getCurrentMapMode(), MAP_MODES_COUNT));
    ha.setHomeDistrict(getNameById(DISTRICTS, settings.getInt(HOME_DISTRICT), DISTRICTS_COUNT));
  }
}

// Forward declarations
void mapCycle();

bool saveMapMode(int newMapMode) {
  if (newMapMode == settings.getInt(MAP_MODE)) return false;

  if (newMapMode == 5) {
    prevMapMode = settings.getInt(MAP_MODE);
  }
  settings.saveInt(MAP_MODE, newMapMode);
  reportSettingsChange("map_mode", newMapMode);
  ha.setLampState(newMapMode == 5);
  ha.setMapMode(haMapModeMap.second[newMapMode]);
  const char* mapModeName = getNameById(MAP_MODES, newMapMode, MAP_MODES_COUNT);
  ha.setMapModeCurrent(mapModeName);
  showServiceMessage(mapModeName, "Режим мапи:");
  // update to selected mapMode
  mapCycle();
  return true;
}

int transformFromHaMapMode(int newIndex) {
  return haMapModeMap.first[newIndex];
}

int transformFromHaDisplayMode(int newIndex) {
  return haDisplayModeMap.first[newIndex];
}

int transformFromHaAutoAlarmMode(int newIndex) {
  return AUTO_ALARM_MODES[newIndex].id;
}

int transformFromHaAutoBrMode(int newIndex) {
  return AUTO_BRIGHTNESS_MODES[newIndex].id;
}

bool onNewLampStateFromHa(bool state) {
  if (settings.getInt(MAP_MODE) == 5 && state) return false;
  int newMapMode = state ? 5 : prevMapMode;
  return saveMapMode(newMapMode);
}

void updateInvertDisplayMode() {
  display.invertDisplay(settings.getBool(INVERT_DISPLAY));
}

bool shouldDisplayBeOff() {
  return serviceMessage.expired && (isDisplayOff || settings.getInt(DISPLAY_MODE) == 0);
}

int getBrightnessFromSensor(int brightnessLevels[]) {
  return brightnessLevels[getCurrentBrightnessLevel()];
}

int getCurrentBrightnes(int defaultBrightness, int dayBrightness, int nightBrightness, int brightnessLevels[]) {
  // highest priority for night mode, return night brightness
  if (nightMode) return nightBrightness;

  // // if nightMode deactivated return previous brightness
  // if (prevBrightness >= 0) {
  //   int tempBrightnes = prevBrightness;
  //   prevBrightness = -1;
  //   return tempBrightnes;
  // }

  int brightnessMode = settings.getInt(BRIGHTNESS_MODE);
  // if auto brightness set to day/night mode, check current hour and choose brightness
  if (brightnessMode == 1) return isItNightNow() ? nightBrightness : dayBrightness;

  // if auto brightnes set to light sensor, read sensor value end return appropriate brightness.
  if (brightnessMode == 2) return brightnessLevels ? getBrightnessFromSensor(brightnessLevels) : getCurrentBrightnessLevel() <= NIGHT_BRIGHTNESS_LEVEL ? nightBrightness : dayBrightness;

  // if auto brightnes deactivated, return regular brightnes
  // default
  return defaultBrightness;
}

void updateDisplayBrightness() {
  if (!display.isDisplayAvailable()) return;
  int localDimDisplay = shouldDisplayBeOff() ? 0 : getCurrentBrightnes(0, 0, settings.getInt(DIM_DISPLAY_ON_NIGHT) ? 1 : 0, NULL);
  if (localDimDisplay == currentDimDisplay) return;
  currentDimDisplay = localDimDisplay;
  LOG.printf("Set display dim: %s\n", currentDimDisplay ? "ON" : "OFF");
  display.dim(currentDimDisplay);
}

//--Update
#if FW_UPDATE_ENABLED
void saveLatestFirmware() {
  int fwUpdateChannel = settings.getInt(FW_UPDATE_CHANNEL);
  const int *count = fwUpdateChannel ? &testBinsCount : &binsCount;
  Firmware firmware = currentFirmware;
  for (int i = 0; i < *count; i++) {
    const char* filename = fwUpdateChannel ? test_bin_list[i] : bin_list[i];
    if (prefix("latest", filename)) continue;
    Firmware parsedFirmware = parseFirmwareVersion(filename);
    if (firstIsNewer(parsedFirmware, firmware)) {
      firmware = parsedFirmware;
    }
  }
  latestFirmware = firmware;
  fwUpdateAvailable = firstIsNewer(latestFirmware, currentFirmware);
  servicePin(UPD_AVAILABLE, fwUpdateAvailable ? HIGH : LOW, false);
  fillFwVersion(newFwVersion, latestFirmware);
  LOG.printf("Latest firmware version: %s\n", newFwVersion);
  LOG.println(fwUpdateAvailable ? "New fw available!" : "No new firmware available");
}

void handleUpdateStatus(t_httpUpdate_return ret, bool isSpiffsUpdate) {
  LOG.printf("%s update status:\n", isSpiffsUpdate ? "Spiffs" : "Firmware");
  switch (ret) {
    case HTTP_UPDATE_FAILED:
      LOG.printf("Error Occurred. Error (%d): %s\n", httpUpdate.getLastError(), httpUpdate.getLastErrorString().c_str());
      break;
    case HTTP_UPDATE_NO_UPDATES:
      LOG.println("HTTP_UPDATE_NO_UPDATES");
      break;
    case HTTP_UPDATE_OK:
      if (isSpiffsUpdate) {
        LOG.println("Spiffs update successfully completed. Starting firmware update...");
      } else {
        LOG.println("Firmware update successfully completed. Rebooting...");
        rebootDevice();
      }
      break;
  }
}

void downloadAndUpdateFw(const char* binFileName, bool isBeta) {
  // disable watchdog timer while update
  disableLoopWDT();

  LOG.println("Starting firmware update...");
  char spiffUrlChar[100];
  char firmwareUrlChar[100];

  LOG.println("Building firmware url...");
  sprintf(
    firmwareUrlChar,
    "http://%s:%d%s%s",
    settings.getString(WS_SERVER_HOST),
    settings.getInt(UPDATE_SERVER_PORT),
  #if ARDUINO_ESP32_DEV
    isBeta ? "/beta/" : "/",
  #elif ARDUINO_ESP32S3_DEV
    isBeta ? "/beta/s3/" : "/s3/",
  #elif ARDUINO_ESP32C3_DEV
    isBeta ? "/beta/c3/" : "/c3/",
  #endif
    binFileName
  );

  LOG.printf("Firmware url: %s\n", firmwareUrlChar);
  t_httpUpdate_return fwRet = httpUpdate.update(
    client,
    firmwareUrlChar,
    VERSION
    );
  handleUpdateStatus(fwRet, false);

  // enable watchdog timer after update
  enableLoopWDT();
}

void doUpdate() {
  if (initUpdate) {
    initUpdate = false;
    downloadAndUpdateFw(bin_name, settings.getInt(FW_UPDATE_CHANNEL) == 1);
  }
}
#endif
//--Update end

//--Service
void checkServicePins() {
  if (settings.getInt(LEGACY) == 0 || settings.getInt(LEGACY) == 3) {
    if (settings.getInt(SERVICE_DIODES_MODE)) {
      servicePin(POWER, HIGH, true);
      if (WiFi.status() != WL_CONNECTED) {
        servicePin(WIFI, LOW, true);
      } else {
        servicePin(WIFI, HIGH, true);
      }
      if (!haConnected) {
        servicePin(HA, LOW, true);
      } else {
        servicePin(HA, HIGH, true);
      }
      if (!client_websocket.available()) {
        servicePin(DATA, LOW, true);
      } else {
        servicePin(DATA, HIGH, true);
      }
#if FW_UPDATE_ENABLED
      if (fwUpdateAvailable) {
        servicePin(UPD_AVAILABLE, HIGH, true);
      } else {
        servicePin(UPD_AVAILABLE, LOW, true);
      }
#endif
    } else {
      servicePin(POWER, LOW, true);
      servicePin(WIFI, LOW, true);
      servicePin(HA, LOW, true);
      servicePin(DATA, LOW, true);
      servicePin(UPD_AVAILABLE, LOW, true);
    }
  }
}

//--Service end

void nextMapMode() {
  int newIndex = getIndexById(MAP_MODES, settings.getInt(MAP_MODE), MAP_MODES_COUNT);
  do {
    if (newIndex >= MAP_MODES_COUNT - 1) {
      newIndex = 0;
    } else {
      newIndex++;
    }
  } while (MAP_MODES[newIndex].ignore);

  saveMapMode(MAP_MODES[newIndex].id);
}

bool saveDisplayMode(int newDisplayMode) {
  if (newDisplayMode == settings.getInt(DISPLAY_MODE)) return false;
  settings.saveInt(DISPLAY_MODE, newDisplayMode);
  reportSettingsChange("display_mode", newDisplayMode);
  if (display.isDisplayAvailable()) {
    ha.setDisplayMode(haDisplayModeMap.second[newDisplayMode]);
  }
  showServiceMessage(getNameById(DISPLAY_MODES, newDisplayMode, DISPLAY_MODE_OPTIONS_MAX), "Режим дисплея:", 1000);
  // update to selected displayMode
  displayCycle();
  return true;
}

bool saveDisplayModeFromHa(int newIndex) {
  return saveDisplayMode(DISPLAY_MODES[newIndex].id);
}

void nextDisplayMode() {
  int newIndex = getIndexById(DISPLAY_MODES, settings.getInt(DISPLAY_MODE), DISPLAY_MODE_OPTIONS_MAX);
  do {
    if (newIndex >= DISPLAY_MODE_OPTIONS_MAX - 1) {
      newIndex = 0;
    } else {
      newIndex++;
    }
  } while (DISPLAY_MODES[newIndex].ignore);

  saveDisplayMode(DISPLAY_MODES[newIndex].id);
}

void autoBrightnessUpdate() {
  int tempBrightness = getCurrentBrightnes(settings.getInt(BRIGHTNESS), settings.getInt(BRIGHTNESS_DAY), settings.getInt(BRIGHTNESS_NIGHT), ledsBrightnessLevels);
  if (tempBrightness != settings.getInt(CURRENT_BRIGHTNESS)) {
    settings.saveInt(CURRENT_BRIGHTNESS, tempBrightness);
  }
}

bool saveNightMode(bool newState) {
  nightMode = newState;
  if (nightMode) {
    prevBrightness = settings.getInt(BRIGHTNESS);
  }
  showServiceMessage(nightMode ? "Увімкнено" : "Вимкнено", "Нічний режим:");
  autoBrightnessUpdate();
  mapCycle();
  reportSettingsChange("nightMode", nightMode ? "true" : "false");
  LOG.print("nightMode: ");
  LOG.println(nightMode ? "true" : "false");
  ha.setNightMode(nightMode);
  return true;
}

//--Button start
void handleClick(int event, JaamButton::Action action) {
  SoundType soundType = action == JaamButton::Action::SINGLE_CLICK ? SoundType::SINGLE_CLICK : SoundType::LONG_CLICK;
  if (event != 0 && needToPlaySound(soundType)) playMelody(soundType);
  switch (event) {
    // change map mode
    case 1:
      nextMapMode();
      break;
    // change display mode
    case 2:
      nextDisplayMode();
      break;
    // toggle map
    case 3:
      isMapOff = !isMapOff;
      showServiceMessage(!isMapOff ? "Увімкнено" : "Вимкнено", "Мапу:");
      mapCycle();
      break;
    // toggle display
    case 4:
      isDisplayOff = !isDisplayOff;
      showServiceMessage(!isDisplayOff ? "Увімкнено" : "Вимкнено", "Дисплей:");
      break;
    // toggle display and map
    case 5:
      if (isDisplayOff != isMapOff) {
        isDisplayOff = false;
        isMapOff = false;
      } else {
        isMapOff = !isMapOff;
        isDisplayOff = !isDisplayOff;
      }
      showServiceMessage(!isMapOff ? "Увімкнено" : "Вимкнено", "Дисплей та мапу:");
      mapCycle();
      break;
    // toggle night mode
    case 6:
      saveNightMode(!nightMode);
      break;
    // toggle lamp (singl click) or reboot device (long click)
    case 7:
      if (action == JaamButton::Action::SINGLE_CLICK) {
        int newMapMode = settings.getInt(MAP_MODE) == 5 ? prevMapMode : 5;
        saveMapMode(newMapMode);
      } else if (JaamButton::Action::LONG_CLICK) {
        rebootDevice();
      }
      break;
#if FW_UPDATE_ENABLED
    case 100:
      char updateFileName[30];
      sprintf(updateFileName, "%s.bin", newFwVersion);
      downloadAndUpdateFw(updateFileName, settings.getInt(FW_UPDATE_CHANNEL) == 1);
      break;
#endif
    default:
      // do nothing
      break;
  }
}

bool isButtonActivated() {
  return settings.getInt(BUTTON_1_MODE) != 0 || settings.getInt(BUTTON_1_MODE_LONG) != 0 || settings.getInt(BUTTON_2_MODE) != 0 || settings.getInt(BUTTON_2_MODE_LONG) != 0;
}

void singleClick(int mode) {
  handleClick(mode, JaamButton::SINGLE_CLICK);
}

void longClick(int modeLong) {
#if FW_UPDATE_ENABLED
  if (settings.getInt(NEW_FW_NOTIFICATION) == 1 && fwUpdateAvailable && isButtonActivated() && !isDisplayOff) {
    handleClick(100, JaamButton::LONG_CLICK);
    return;
  }
#endif
  handleClick(modeLong, JaamButton::LONG_CLICK);
}

void buttonClick(const char* buttonName, int mode) {
#if TEST_MODE
  displayMessage("Single click!", buttonName);
#else
  singleClick(mode);
#endif
}

void buttonLongClick(const char* buttonName, int modeLong) {
#if TEST_MODE
  displayMessage("Long click!", buttonName);
#else
  longClick(modeLong);
#endif
}

bool saveLampBrightness(int newBrightness, bool saveToSettings, bool checkPrevBrightness) {
  if (checkPrevBrightness && settings.getInt(HA_LIGHT_BRIGHTNESS) == newBrightness) return false;

  settings.saveInt(HA_LIGHT_BRIGHTNESS, newBrightness, saveToSettings);

  if (saveToSettings) {
    ha.setLampBrightness(newBrightness);
  }

  mapCycle();
  return true;
}

bool saveLampBrightness(int newBrightness) {
  return saveLampBrightness(newBrightness, true, true);
}

void saveCurrentLampBrightness() {
  LOG.println("Save current lamp brightness");
  saveLampBrightness(settings.getInt(HA_LIGHT_BRIGHTNESS), true, false);
}

char lampBrightnessMsg[4];

void buttonDuringLongClick(const char* buttonName, int modeLong, JaamButton::Action action) {
#if FW_UPDATE_ENABLED
  if (settings.getInt(NEW_FW_NOTIFICATION) == 1 && fwUpdateAvailable && isButtonActivated() && !isDisplayOff) {
    return;
  }
#endif
  if (action == JaamButton::Action::DURING_LONG_CLICK) {
    switch (modeLong) {
      case 8:
        // if lamp mode is active, increase lamp brightness
        if (getCurrentMapMode() == 5) {
          int newBrightness = settings.getInt(HA_LIGHT_BRIGHTNESS) + 1;
          if (newBrightness > 100) {
            newBrightness = 100;
          }
          saveLampBrightness(newBrightness, false, true);
          sprintf(lampBrightnessMsg, "%d%%", newBrightness);
          showServiceMessage(lampBrightnessMsg, "Яскравість лампи:");
        } else {
          showServiceMessage("Лише для режиму лампи");
        }
        break;
      case 9:
        // if lamp mode is active, decrease lamp brightness
        if (getCurrentMapMode() == 5) {
          int newBrightness = settings.getInt(HA_LIGHT_BRIGHTNESS) - 1;
          if (newBrightness < 0) {
            newBrightness = 0;
          }
          saveLampBrightness(newBrightness, false, true);
          sprintf(lampBrightnessMsg, "%d%%", newBrightness);
          showServiceMessage(lampBrightnessMsg, "Яскравість лампи:");
        } else {
          showServiceMessage("Лише для режиму лампи");
        }
        break;
      default:
        // do nothing
        break;
  }
  } else if (action == JaamButton::Action::LONG_CLICK_END) {
    switch (modeLong) {
      case 8:
      case 9:
        if (getCurrentMapMode() == 5) {
          saveCurrentLampBrightness();
        }
        break;
      default:
        // do nothing
        break;
    }
  }
}

void button1Click() {
  LOG.println("Button 1 click");
  buttonClick("Button 1", settings.getInt(BUTTON_1_MODE));
}

void button2Click() {
  LOG.println("Button 2 click");
  buttonClick("Button 2", settings.getInt(BUTTON_2_MODE));
}

void button1LongClick() {
  LOG.println("Button 1 long click");
  buttonLongClick("Button 1", settings.getInt(BUTTON_1_MODE_LONG));
}

void button2LongClick() {
  LOG.println("Button 2 long click");
  buttonLongClick("Button 2", settings.getInt(BUTTON_2_MODE_LONG));
}

void button1DuringLongClick(JaamButton::Action action) {
  LOG.println("Button 1 during long click");
  buttonDuringLongClick("Button 1", settings.getInt(BUTTON_1_MODE_LONG), action);
}

void button2DuringLongClick(JaamButton::Action action) {
  LOG.println("Button 2 during long click");
  buttonDuringLongClick("Button 2", settings.getInt(BUTTON_2_MODE_LONG), action);
}

void distributeBrightnessLevels() {
  distributeBrightnessLevelsFor(settings.getInt(BRIGHTNESS_DAY), settings.getInt(BRIGHTNESS_NIGHT), ledsBrightnessLevels, "Leds");
}

void remapFlag() {
  led_to_flag_color =  mapLeds(ledMapping, FLAG_COLORS);
}

std::pair<int, long> alertsCombiModeHandler(std::pair<int, long> kyiv, std::pair<int, long> kyivObl) {
  // if state of Kyiv and Kyiv Oblast are 'alert', return oldest by time
  if (kyiv.first == 1 && kyivObl.first == 1) return kyiv.second <= kyivObl.second ? kyiv : kyivObl;
  // if states of Kyiv and Kyiv Oblast are 'clear', return nearest by time
  if (kyiv.first == 0 && kyivObl.first == 0) return kyiv.second >= kyivObl.second ? kyiv : kyivObl;
  // if one of the states is 0, return another
  return kyiv.first == 0 ? kyivObl : kyiv;
}

void remapAlerts() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? alertsCombiModeHandler : NULL;
  led_to_alerts = mapLeds(ledMapping, id_to_alerts, combiHandler);
}

void remapMissiles() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? alertsCombiModeHandler : NULL;
  led_to_missiles = mapLeds(ledMapping, id_to_missiles, combiHandler);
}

void remapDrones() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? alertsCombiModeHandler : NULL;
  led_to_drones = mapLeds(ledMapping, id_to_drones, combiHandler);
}

void remapKabs() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? alertsCombiModeHandler : NULL;
  led_to_kabs = mapLeds(ledMapping, id_to_kabs, combiHandler);
}

float linearFloatCombiModeHandler(float value1, float value2) {
  // return average value of two values
  return (value1 + value2) / 2.0f;
}

int linearIntCombiModeHandler(int value1, int value2) {
  // return average value of two values
  return (value1 + value2) / 2;
}

void remapWeather() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? linearFloatCombiModeHandler : NULL;
  led_to_weather = mapLeds(ledMapping, id_to_weather, combiHandler);
}

void remapRadiation() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? linearIntCombiModeHandler : NULL;
  led_to_radiation = mapLeds(ledMapping, id_to_radiation, combiHandler);
}

void remapEnergy() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? alertsCombiModeHandler : NULL;
  led_to_energy = mapLeds(ledMapping, id_to_energy, combiHandler);
}

long maxCombiModeHandler(long value1, long value2) {
  // return nearest by time
  return max(value1, value2);
}

void remapExplosionsNotifications() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? maxCombiModeHandler : NULL;
  led_to_explosions_notifications = mapLeds(ledMapping, id_to_explosions_notifications, combiHandler);
}

void remapMissilesNotifications() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? maxCombiModeHandler : NULL;
  led_to_missiles_notifications = mapLeds(ledMapping, id_to_missiles_notifications, combiHandler);
}

void remapDronesNotifications() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? maxCombiModeHandler : NULL;
  led_to_drones_notifications = mapLeds(ledMapping, id_to_drones_notifications, combiHandler);
}

void remapKabsNotifications() {
  auto combiHandler = settings.getInt(KYIV_DISTRICT_MODE) == 4 ? maxCombiModeHandler : NULL;
  led_to_kabs_notifications = mapLeds(ledMapping, id_to_kabs_notifications, combiHandler);
}

void remapHomeDistrict() {
  homeDistrictMapping = ledMapping(settings.getInt(HOME_DISTRICT));
}

bool saveBrightness(int newBrightness) {
  if (settings.getInt(BRIGHTNESS) == newBrightness) return false;
  settings.saveInt(BRIGHTNESS, newBrightness);
  reportSettingsChange("brightness", newBrightness);
  ha.setBrightness(newBrightness);
  autoBrightnessUpdate();
  return true;
}

bool saveDayBrightness(int newBrightness) {
  if (settings.getInt(BRIGHTNESS_DAY) == newBrightness) return false;
  settings.saveInt(BRIGHTNESS_DAY, newBrightness);
  reportSettingsChange("brightness_day", newBrightness);
  ha.setDayBrightness(newBrightness);
  autoBrightnessUpdate();
  distributeBrightnessLevels();
  return true;
}

bool saveNightBrightness(int newBrightness) {
  if (settings.getInt(BRIGHTNESS_NIGHT) == newBrightness) return false;
  settings.saveInt(BRIGHTNESS_NIGHT, newBrightness);
  reportSettingsChange("brightness_night", newBrightness);
  ha.setNightBrightness(newBrightness);
  autoBrightnessUpdate();
  distributeBrightnessLevels();
  return true;
}

bool saveAutoBrightnessMode(int autoBrightnessMode) {
  if (settings.getInt(BRIGHTNESS_MODE) == autoBrightnessMode) return false;
  settings.saveInt(BRIGHTNESS_MODE, autoBrightnessMode);
  reportSettingsChange("brightness_mode", autoBrightnessMode);
  ha.setAutoBrightnessMode(autoBrightnessMode);
  autoBrightnessUpdate();
  showServiceMessage(getNameById(AUTO_BRIGHTNESS_MODES, autoBrightnessMode, AUTO_BRIGHTNESS_OPTIONS_COUNT), "Авто. яскравість:");
  return true;
}

bool saveAutoAlarmMode(int newMode) {
  if (settings.getInt(ALARMS_AUTO_SWITCH) == newMode) return false;
  settings.saveInt(ALARMS_AUTO_SWITCH, newMode);
  reportSettingsChange("alarms_auto_switch", newMode);
  ha.setAutoAlarmMode(newMode);
  return true;
}

bool saveShowHomeAlarmTime(bool newState) {
  if (settings.getBool(HOME_ALERT_TIME) == newState) return false;
  settings.saveBool(HOME_ALERT_TIME, newState);
  reportSettingsChange("home_alert_time", newState ? "true" : "false");
  if (display.isDisplayAvailable()) {
    ha.setShowHomeAlarmTime(newState);
  }
  return true;
}

bool saveLampRgb(int r, int g, int b) {
  if (settings.getInt(HA_LIGHT_R) == r && settings.getInt(HA_LIGHT_G) == g && settings.getInt(HA_LIGHT_B) == b) return false;

  if (settings.getInt(HA_LIGHT_R) != r) {
    settings.saveInt(HA_LIGHT_R, r);
  }
  if (settings.getInt(HA_LIGHT_G) != g) {
    settings.saveInt(HA_LIGHT_G, g);
  }
  if (settings.getInt(HA_LIGHT_B) != b) {
    settings.saveInt(HA_LIGHT_B, b);
  }
  char rgbHex[8];
  sprintf(rgbHex, "#%02x%02x%02x", settings.getInt(HA_LIGHT_R), settings.getInt(HA_LIGHT_G), settings.getInt(HA_LIGHT_B));
  reportSettingsChange("ha_light_rgb", rgbHex);
  ha.setLampColor(settings.getInt(HA_LIGHT_R), settings.getInt(HA_LIGHT_G), settings.getInt(HA_LIGHT_B));
  mapCycle();
  return true;
}

bool saveHomeDistrict(int newHomeDistrict) {
  if (newHomeDistrict == settings.getInt(HOME_DISTRICT)) return false;
  settings.saveInt(HOME_DISTRICT, newHomeDistrict);
  const char* homeDistrictName = getNameById(DISTRICTS, newHomeDistrict, DISTRICTS_COUNT);
  reportSettingsChange("home_district", getNameById(DISTRICTS, newHomeDistrict, DISTRICTS_COUNT));
  LOG.printf("home_district commited to preferences: %s\n", homeDistrictName);
  ha.setHomeDistrict(homeDistrictName);
  ha.setMapModeCurrent(getNameById(MAP_MODES, getCurrentMapMode(), MAP_MODES_COUNT));
  ha.setHomeTemperature(id_to_weather[newHomeDistrict]);
  ha.setHomeEnergy(id_to_energy[newHomeDistrict].first);
  ha.setHomeRadiation(id_to_radiation[newHomeDistrict]);
  showServiceMessage(homeDistrictName, "Домашній регіон:", 2000);
  remapHomeDistrict();
  return true;
}

//--Display start
void displayServiceMessage(ServiceMessage message) {
  displayMessage(message.message, message.title, message.textSize);
}

void showMinOfSilanceScreen(int screen) {
  switch (screen) {
  case 0:
    display.displayTextWithIcon(JaamDisplay::TRINDENT, "Шана", "Полеглим", "Героям!");
    break;
  case 1:
    display.displayTextWithIcon(JaamDisplay::TRINDENT, "Слава", "", "Україні!");
    break;
  case 2:
    display.displayTextWithIcon(JaamDisplay::TRINDENT, "Смерть", "", "ворогам!");
    break;
  default:
    break;
  }
}

void displayMinuteOfSilence() {
  // every 3 sec.
  int periodIndex = getCurrentPeriodIndex(3, 3, timeClient.second());
  showMinOfSilanceScreen(periodIndex);
}

void showHomeAlertInfo() {
  int periodIndex = getCurrentPeriodIndex(settings.getInt(DISPLAY_MODE_TIME), 2, timeClient.second());
  char title[50];
  if (periodIndex) {
    strcpy(title, getNameById(DISTRICTS, settings.getInt(HOME_DISTRICT), DISTRICTS_COUNT));
  } else {
    strcpy(title, "Тривога триває:");
  }
  char message[15];
  int regionId = settings.getInt(HOME_DISTRICT);
  fillFromTimer(message, timeClient.unixGMT() - id_to_alerts[regionId].second);

  displayMessage(message, title);
}

void clearDisplay() {
  display.clearDisplay();
  display.display();
}

void showClock() {
  char time[7];
  sprintf(time, "%02d%c%02d", timeClient.hour(), getDivider(timeClient.second()), timeClient.minute());
  const char* date = timeClient.unixToString("DSTRUA DD.MM.YYYY").c_str();
  displayMessage(time, date);
}

void showTemp() {
  int regionId = settings.getInt(HOME_DISTRICT);
  char message[10];
  sprintf(message, "%.1f%cC", id_to_weather[regionId], (char)128);
  displayMessage(message, getNameById(DISTRICTS, regionId, DISTRICTS_COUNT));
}

void showRadiation() {
  int regionId = settings.getInt(HOME_DISTRICT);
  char title[38];
  char message[35];
  sprintf(message, "%d", id_to_radiation[regionId]);
  displayMessage(message, "Радіація (нЗв/год)");
}

void showEnergy() {
  int regionId = settings.getInt(HOME_DISTRICT);
  int status = id_to_energy[regionId].first;
  char title[38];
  char message[35];
  strcpy(title, "Стан енергосистеми");

  switch (status) {
    case 0:
      strcpy(message, "Дані відсутні");
      break;
    case 3:
      strcpy(message, "Достатньо");
      break;
    case 4:
      strcpy(message, "Не вистачає");
      break;
    case 9:
      strcpy(message, "Відключення!");
      break;
    default:
      strcpy(message, "Невідомий статус");
      break;
    }
  displayMessage(message, title);
}

void showTechInfo() {
  int periodIndex = getCurrentPeriodIndex(settings.getInt(DISPLAY_MODE_TIME), 6, timeClient.second());
  char title[35];
  char message[25];
  switch (periodIndex) {
  case 0:
    // IP address
    strcpy(title, "IP-адреса мапи:");
    strcpy(message, getLocalIP());
    break;
  case 1:
    // Wifi Signal level
    strcpy(title, "Сигнал WiFi:");
    sprintf(message, "%d dBm", wifiSignal);
    break;
  case 2:
    // Uptime
    strcpy(title, "Час роботи:");
    fillFromTimer(message, millis() / 1000);
    break;
  case 3:
    // map-API status
    strcpy(title, "Статус map-API:");
    strcpy(message, apiConnected ? "Підключено" : "Відключено");
    break;
  case 4:
    // HA Status
    strcpy(title, "Home Assistant:");
    strcpy(message, haConnected ? "Підключено" : "Відключено");
    break;
  case 5:
    // Fw version
    strcpy(title, "Версія прошивки:");
    strcpy(message, currentFwVersion);
    break;
  default:
    break;
  }
  displayMessage(message, title);
}

int getClimateInfoSize() {
  int size = 0;
  if (climate.isTemperatureAvailable()) size++;
  if (climate.isHumidityAvailable()) size++;
  if (climate.isPressureAvailable()) size++;
  return size;
}

void showLocalTemp() {
  char message[10];
  sprintf(message, "%.1f%cC", climate.getTemperature(settings.getFloat(TEMP_CORRECTION)), (char)128);
  displayMessage(message, "Температура");
}

void showLocalHum() {
  char message[10];
  sprintf(message, "%.1f%%", climate.getHumidity(settings.getFloat(HUM_CORRECTION)));
  displayMessage(message, "Вологість");
}

void showLocalPressure() {
  char message[12];
  sprintf(message, "%.1fmmHg", climate.getPressure(settings.getFloat(PRESSURE_CORRECTION)));
  displayMessage(message, "Тиск");
}

void showLocalClimateInfo(int index) {
  if (index == 0 && climate.isTemperatureAvailable()) {
    showLocalTemp();
    return;
  }
  if (index <= 1 && climate.isHumidityAvailable()) {
    showLocalHum();
    return;
  }
  if (index <= 2 && climate.isPressureAvailable()) {
    showLocalPressure();
    return;
  }
}

void showClimate() {
  int periodIndex = getCurrentPeriodIndex(settings.getInt(DISPLAY_MODE_TIME), getClimateInfoSize(), timeClient.second());
  showLocalClimateInfo(periodIndex);
}

int getNextToggleMode(int periodIndex) {
  if (periodIndex == currentDisplayToggleIndex) return currentDisplayToggleMode;
  switch (currentDisplayToggleMode) {
  case 0:
    // if weather is enabled or no sensors available
    if (settings.getBool(TOGGLE_MODE_WEATHER) || !climate.isAnySensorAvailable()) {
      // show weather info
      return 1;
    }
  case 1:
    // if local temperature is enabled and available
    if (settings.getBool(TOGGLE_MODE_TEMP) && climate.isTemperatureAvailable()) {
      // show local temperature
      return 2;
    }
  case 2:
    // if local humidity is enabled and available
    if (settings.getBool(TOGGLE_MODE_HUM) && climate.isHumidityAvailable()) {
      // show local humidity
      return 3;
    }
  case 3:
    // if local pressure is enabled and available
    if (settings.getBool(TOGGLE_MODE_PRESS) && climate.isPressureAvailable()) {
      // show local pressure
      return 4;
    }
  case 4:
    // enegry status
    if (settings.getBool(TOGGLE_MODE_ENERGY)) {
      // show grid status
      return 5;
    }
    // else show time
  case 5:
    // radiation status
    if (settings.getBool(TOGGLE_MODE_RADIATION)) {
      // show radiation status
      return 6;
    }
    // else show time
  case 6:
  default:
    return 0;
  }
}

void showToggleModes() {
  int periodIndex = getCurrentPeriodIndex(settings.getInt(DISPLAY_MODE_TIME), 5, timeClient.second());
  int nextToggleMode = getNextToggleMode(periodIndex);
  currentDisplayToggleIndex = periodIndex;
  currentDisplayToggleMode = nextToggleMode;
  switch (currentDisplayToggleMode) {
  case 0:
    // Display Mode Clock
    showClock();
    break;
  case 1:
    // Display Mode Temperature
    showTemp();
    break;
  case 2:
    // Display Climate Temperature
    showLocalTemp();
    break;
  case 3:
    // Display Climate Humidity
    showLocalHum();
    break;
  case 4:
    // Display Climate Pressure
    showLocalPressure();
    break;
  case 5:
    // Display UkrEnergo Status
    showEnergy();
    break;
  case 6:
    // Display SaveEcoBot Radiation Status
    showRadiation();
    break;
  default:
    break;
  }
}

void displayByMode(int mode) {
  switch (mode) {
    // Display Mode Off
    case 0:
      clearDisplay();
      break;
    // Display Mode Clock
    case 1:
      showClock();
      break;
    // Display Mode Temperature
    case 2:
      showTemp();
      break;
    case 3:
      showTechInfo();
      break;
    // Display Climate info from sensor
    case 4:
      showClimate();
      break;
    // Display UkrEnergo Status
    case 5:
      showEnergy();
      break;
    // Display SaveEcoBot Radiation Status
    case 6:
      showRadiation();
      break;
    // Display Mode Switching
    case 9:
      showToggleModes();
      break;
    // Unknown Display Mode, clearing display...
    default:
      clearDisplay();
      break;
  }
}

#if FW_UPDATE_ENABLED
void showNewFirmwareNotification() {
  int periodIndex = getCurrentPeriodIndex(settings.getInt(DISPLAY_MODE_TIME), 2, timeClient.second());
  char title[50];
  char message[50];
  if (periodIndex) {
    strcpy(title, "Доступне оновлення:");
    strcpy(message, newFwVersion);
  } else if (!isButtonActivated()) {
    strcpy(title, "Введіть у браузері:");
    strcpy(message, getLocalIP());
  } else {
    strcpy(title, "Для оновл. натисніть");
    sprintf(message, "та тримайте кнопку %c", (char)24);
  }

  displayMessage(message, title);
}
#endif

void volumeCycle() {
#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
  int volumeLocal;
  if (getNightModeType() > 0) {
    volumeLocal = volumeNight;
  } else {
    volumeLocal = volumeDay;
  }
  if (volumeLocal != volumeCurrent) {
    volumeCurrent = volumeLocal;
    settings.saveInt(MELODY_VOLUME_CURRENT, volumeCurrent);
    if (isBuzzerEnabled()) {
      player->setVolume(expMap(volumeCurrent, 0, 100, 0, 255)); 
    }
    if (dfPlayerConnected) {
      dfplayer.setVol(expMapLinear(volumeCurrent, 0, 100, 0, 20));
    }
    LOG.printf("Set volume to: %d\n", volumeCurrent);
  }
#endif
}

void setCurrentVolume(int volume, Type settingType) {
  switch (settingType) {
    case MELODY_VOLUME_NIGHT:
      volumeNight  = volume;
      break;
    case MELODY_VOLUME_DAY:
      volumeDay  = volume;
      break;
  }
  volumeCycle();
}

void displayCycle() {
  if (!display.isDisplayAvailable()) return;

  updateDisplayBrightness();

  // Show service message if not expired (Always show, it's short message)
  if (!serviceMessage.expired) {
    displayServiceMessage(serviceMessage);
    return;
  }

  if (uaAnthemPlaying) {
    showMinOfSilanceScreen(1);
    return;
  }

  // Show Minute of silence mode if activated. (Priority - 0)
  if (minuteOfSilence) {
    displayMinuteOfSilence();
    return;
  }

  // Show Home Alert Time Info if enabled in settings and alarm in home district is enabled (Priority - 1)
  if (alarmNow && settings.getBool(HOME_ALERT_TIME)) {
    showHomeAlertInfo();
    return;
  }

  // Turn off display, if activated (Priority - 2)
  if (isDisplayOff) {
    clearDisplay();
    return;
  }

#if FW_UPDATE_ENABLED
  // Show New Firmware Notification if enabled in settings and New firmware available (Priority - 3)
  if (settings.getInt(NEW_FW_NOTIFICATION) == 1 && fwUpdateAvailable) {
    showNewFirmwareNotification();
    return;
  }
#endif

  // Show selected display mode in other cases (Priority - last)
  displayByMode(settings.getInt(DISPLAY_MODE));
}

void serviceMessageUpdate() {
  if (!serviceMessage.expired && millis() > serviceMessage.endTime) {
    serviceMessage.expired = true;
  }
}
//--Display end

void updateHaTempSensors() {
  if (climate.isTemperatureAvailable()) {
    ha.setLocalTemperature(climate.getTemperature(settings.getFloat(TEMP_CORRECTION)));
  }
}

void updateHaHumSensors() {
  if (climate.isHumidityAvailable()) {
    ha.setLocalHumidity(climate.getHumidity(settings.getFloat(HUM_CORRECTION)));
  }
}

void updateHaPressureSensors() {
  if (climate.isPressureAvailable()) {
    ha.setLocalPressure(climate.getPressure(settings.getFloat(PRESSURE_CORRECTION)));
  }
}

void climateSensorCycle() {
  if (!climate.isAnySensorAvailable()) return;
  climate.read();
  updateHaTempSensors();
  updateHaHumSensors();
  updateHaPressureSensors();
}

void setAlertPin() {
  if (isAlertPinEnabled()) {
    LOG.println("alert pin: HIGH");
    digitalWrite(settings.getInt(ALERT_PIN), HIGH);
  }
}

void setClearPin() {
  if (isClearPinEnabled()) {
    LOG.println("clear pin: HIGH");
    digitalWrite(settings.getInt(CLEAR_PIN), HIGH);
  }
}

void disableAlertPin() {
  if (isAlertPinEnabled()) {
    LOG.println("alert pin: LOW");
    digitalWrite(settings.getInt(ALERT_PIN), LOW);
  }
}

void disableClearPin() {
  if (isClearPinEnabled()) {
    LOG.println("clear pin: LOW");
    digitalWrite(settings.getInt(CLEAR_PIN), LOW);
  }
}

void disableAlertAndClearPins() {
  disableAlertPin();
  disableClearPin();
}

void initLedMapping() {
  if (settings.getInt(LEGACY) == 1) {
    switch (settings.getInt(KYIV_DISTRICT_MODE)) {
    case 1:
      ledMapping = mapTranscarpatiaStart1;
      LOG.println("Transcarpatia district mode 1");
      break;
    case 2:
      ledMapping = mapTranscarpatiaStart2;
      LOG.println("Transcarpatia district mode 2");
      break;
    case 3:
      ledMapping = mapTranscarpatiaStart3;
      LOG.println("Transcarpatia district mode 3");
      break;
    case 4:
      ledMapping = mapTranscarpatiaStart4;
      LOG.println("Transcarpatia district mode 4");
      break;
    default:
      LOG.printf("Unknown Kyiv district mode: %d\n", settings.getInt(KYIV_DISTRICT_MODE));
      throw std::runtime_error("Unknown Kyiv district mode");
    }
  } else {
    switch (settings.getInt(KYIV_DISTRICT_MODE)) {
    case 1:
      ledMapping = mapOdessaStart1;
      LOG.println("Odessa district mode 1");
      break;
    case 2:
      ledMapping = mapOdessaStart2;
      LOG.println("Odessa district mode 2");
      break;
    case 3:
      ledMapping = mapOdessaStart3;
      LOG.println("Odessa district mode 3");
      break;
    case 4:
      ledMapping = mapOdessaStart4;
      LOG.println("Odessa district mode 4");
      break;
    default:
      LOG.printf("Unknown Kyiv district mode: %d\n", settings.getInt(KYIV_DISTRICT_MODE));
      throw std::runtime_error("Unknown Kyiv district mode");
    }
  }
  remapFlag();
  remapAlerts();
  remapWeather();
  remapExplosionsNotifications();
  remapMissilesNotifications();
  remapMissiles();
  remapDronesNotifications();
  remapDrones();
  remapKabsNotifications();
  remapKabs();
  remapHomeDistrict();
  remapEnergy();
  remapRadiation();
}

//--Web server start

int checkboxIndex = 1;
int sliderIndex = 1;
int selectIndex = 1;
int inputFieldIndex = 1;

void addCheckbox(Print* response, const char* name, bool isChecked, const char* label, const char* onChanges = NULL, bool disabled = false) {
  response->print("<div class='form-group form-check'>");
  response->print("<input name='");
  response->print(name);
  response->print("' type='checkbox' class='form-check-input' id='chb");
  response->print(checkboxIndex);
  if (onChanges) {
    response->print("'");
    response->print(" onchange='");
    response->print(onChanges);
  }
  response->print("'");
  if (isChecked) response->print(" checked");
  if (disabled) response->print(" disabled");
  response->print("/>");
  response->print(label);
  response->println("</div>");
  checkboxIndex++;
}

template <typename V>

void addSlider(Print* response, const char* name, const char* label, V value, V min, V max, V step = 1, const char* unitOfMeasurement = "", bool disabled = false, bool needColorBox = false) {
  response->print(label);
  response->print(": <span id='sv");
  response->print(sliderIndex);
  response->print("'>");
  if (std::is_same<V, float>::value) {
    char stringValue[10];
    sprintf(stringValue, "%.1f", value);
    response->print(stringValue);
  } else {
    response->print(value);
  }
  response->print("</span>");
  response->print(unitOfMeasurement);
  if (needColorBox) {
    response->print("</br><div class='color-box' id='cb");
    response->print(sliderIndex);
    RGBColor valueColor = hue2rgb((int) value);
    response->print("' style='background-color: rgb(");
    response->print(valueColor.r);
    response->print(", ");
    response->print(valueColor.g);
    response->print(", ");
    response->print(valueColor.b);
    response->print(");'></div>");
  }
  response->print("<input type='range' name='");
  response->print(name);
  response->print("' class='form-control-range' id='s");
  response->print(sliderIndex);
  response->print("' min='");
  response->print(min);
  response->print("' max='");
  response->print(max);
  response->print("' step='");
  response->print(step);
  response->print("' value='");
  response->print(value);
  response->print("'");
  if (needColorBox) {
    response->print(" oninput='window.updateColAndVal(\"cb");
    response->print(sliderIndex);
    response->print("\", \"sv");
  } else {
    response->print(" oninput='window.updateVal(\"sv");
  }
  response->print(sliderIndex);
  response->print("\", this.value);'");
  if (disabled) response->print(" disabled");
  response->print("/>");
  response->println("</br>");
  sliderIndex++;
}

void addSelectBox(Print* response, const char* name, const char* label, int setting, SettingListItem options[], int optionsCount, bool disabled = false, const char* onChanges = NULL) {
  response->print(label);
  response->print(": <select name='");
  response->print(name);
  response->print("' class='form-control' id='sb");
  response->print(selectIndex);
  if (onChanges) {
    response->print("'");
    response->print(" onchange='");
    response->print(onChanges);
  }
  response->print("'");
  if (disabled) response->print(" disabled");
  response->print(">");
  for (int i = 0; i < optionsCount; i++) {
    if (options[i].ignore) continue;
    int index = options[i].id;
    response->print("<option value='");
    response->print(index);
    response->print("'");
    if (setting == index) response->print(" selected");
    response->print(">");
    response->print(options[i].name);
    response->print("</option>");
  }
  response->print("</select>");
  response->println("</br>");
  selectIndex++;
}

void addInputText(Print* response, const char* name, const char* label, const char* type, const char* value, int maxLength = -1) {
  response->print(label);
  response->print(": <input type='");
  response->print(type);
  response->print("' name='");
  response->print(name);
  response->print("' class='form-control'");
  if (maxLength >= 0) {
    response->print(" maxlength='");
    response->print(maxLength);
    response->print("'");
  }
  response->print(" id='if");
  response->print(inputFieldIndex);
  response->print("' value='");
  response->print(value);
  response->print("'>");
  response->println("</br>");
  inputFieldIndex++;
}

template <typename V>

void addCard(Print* response, const char* title, V value, const char* unitOfMeasurement = "", int size = 1, int precision = 1) {
  response->print("<div class='col-auto mb-2'>");
  response->print("<div class='card' style='width: 15rem; height: 9rem;'>");
  response->print("<div class='card-header d-flex'>");
  response->print(title);
  response->print("</div>");
  response->print("<div class='card-body d-flex'>");
  response->print("<h");
  response->print(size);
  response->print(" class='card-title m-auto'>");
  if (std::is_same<V, float>::value) {
    char valueStr[10];
    sprintf(valueStr, "%.*f", precision, value);
    response->print(valueStr);
  } else if (std::is_same<V, int>::value) {
    char valueStr[10];
    sprintf(valueStr, "%d", value);
    response->print(valueStr);
  } else {
    response->print(value);
  }
  response->print(unitOfMeasurement);
  response->print("</h");
  response->print(size);
  response->print(">");
  response->print("</div>");
  response->print("</div>");
  response->print("</div>");
}

void addHeader(Print* response) {
  response->println("<!DOCTYPE html>");
  response->println("<html lang='uk'>");
  response->println("<head>");
  response->println("<meta charset='UTF-8'>");
  response->println("<meta name='viewport' content='width=device-width, initial-scale=1.0'>");
  response->print("<title>");
  response->print(settings.getString(DEVICE_NAME));
  response->println("</title>");
  // To prevent favicon request
  response->println("<link rel='icon' href='data:image/png;base64,iVBORw0KGgo='>");
  response->println("<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css' integrity='sha384-xOolHFLEh07PJGoPkLv1IbcEPTNtaed2xpHsD9ESMhqIYd0nLMwNLD69Npy4HI+N' crossorigin='anonymous'>");
  response->print("<link rel='stylesheet' href='https://");
  response->print(settings.getString(WS_SERVER_HOST));
  response->println("/static/jaam_v1.css'>");
  response->println("</head>");
  response->println("<body>");
  response->println("<div class='container mt-3'  id='accordion'>");
  response->print("<h2 class='text-center'>");
  response->print(settings.getString(DEVICE_DESCRIPTION));
  response->print(" ");
  response->print(currentFwVersion);
  response->println("</h2>");
  response->println("<div class='row justify-content-center'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->print("<img class='full-screen-img' src='https://");
  response->print(settings.getString(WS_SERVER_HOST));
  response->print("/");
  switch (getCurrentMapMode()) {
    case 0:
      response->print("off_map.png");
      break;
    case 2:
      response->print("weather_map.png");
      break;
    case 3:
      response->print("flag_map.png");
      break;
    case 4:
      response->print("random_map.png");
      break;
    case 5:
      response->print("lamp_map.png");
      break;
    case 6:
      response->print("energy_map.png");
      break;
    case 7:
      response->print("radiation_map.png");
      break;
    default:
      response->print("alerts_map.png");
  }
  response->println("'>");
  response->println("</div>");
  response->println("</div>");
#if FW_UPDATE_ENABLED
  if (fwUpdateAvailable) {
    response->println("<div class='row justify-content-center'>");
    response->println("<div class='by col-md-9 mt-2'>");
    response->println("<div class='alert alert-success text-center'>");
    response->print("Доступна нова версія прошивки - <b>");
    response->print(newFwVersion);
    response->println("</b></br>Для оновлення перейдіть в розділ <b><a href='/firmware'>Прошивка</a></b></h8>");
    response->println("</div>");
    response->print("<div class='alert alert-info text-rigth' id='release-notes' data-version='");
    response->print(newFwVersion);
    response->println("'>Завантажити опис оновлення?</div>");
    response->print("<div class='text-center'><button class='btn btn-info' onclick='fetchReleaseNotes()'>Отримати опис оновлення</button></div><br>");
    response->println("</div>");
    response->println("</div>");
  }
#endif
  response->println("<div class='row justify-content-center'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->print("Локальна IP-адреса: <b>");
  response->print(getLocalIP());
  response->println("</b>");
  if (display.isDisplayEnabled()) {
    response->println("</br>Дисплей: <b>");
    if (display.isDisplayAvailable()) {
      response->print(display.getDisplayModel());
      response->print(" (128x");
      response->print(display.height());
      response->print(")");
    } else {
      response->print("Немає");
    }
    response->println("</b>");
  }
  if (lightSensor.isLightSensorEnabled()) {
    response->println("</br>Сенсор освітлення: <b>");
    response->print(lightSensor.getSensorModel());
    response->println("</b>");
  }
  if (climate.isAnySensorEnabled()) {
    response->println("</br>Сенсор клімату: <b>");
    response->print(climate.getSensorModel());
    response->println("</b>");
  }
  if (isBuzzerEnabled()) {
    response->println("</br>Буззер: <b>налаштовано</b>");;
  }
  if (dfPlayerConnected) {
    response->println("</br>DF Player Pro: <b>налаштовано</b>");;
  }
  response->println("</div>");
  response->println("</div>");
}

void addLinks(Print* response) {
  response->println("<div class='row justify-content-center'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->println("<a href='/brightness' class='btn btn-success'>Яскравість</a>");
  response->println("<a href='/colors' class='btn btn-success'>Кольори</a>");
  response->println("<a href='/modes' class='btn btn-success'>Режими</a>");
#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
  if (isBuzzerEnabled() || dfPlayerConnected) {
    response->println("<a href='/sounds' class='btn btn-success'>Звуки</a>");
  }
#endif
  response->println("<a href='/telemetry' class='btn btn-primary'>Телеметрія</a>");
  response->println("<a href='/dev' class='btn btn-warning'>DEV</a>");
#if FW_UPDATE_ENABLED
  response->println("<a href='/firmware' class='btn btn-danger'>Прошивка</a>");
#endif
  response->println("</div>");
  response->println("</div>");
}

void addFooter(Print* response) {
  response->println("<div class='position-fixed bottom-0 right-0 p-3' style='z-index: 5; right: 0; bottom: 0;'>");
  response->println("<div id='saved-toast' class='toast hide' role='alert' aria-live='assertive' aria-atomic='true' data-delay='2000'>");
  response->println("<div class='toast-body'>");
  response->println("💾 Налаштування збережено!");
  response->println("</div>");
  response->println("</div>");
  response->println("<div id='reboot-toast' class='toast hide' role='alert' aria-live='assertive' aria-atomic='true' data-delay='2000'>");
  response->println("<div class='toast-body'>");
  response->println("💾 Налаштування збережено! Перезавантаження...");
  response->println("</div>");
  response->println("</div>");
  response->println("<div id='restore-toast' class='toast hide' role='alert' aria-live='assertive' aria-atomic='true' data-delay='2000'>");
  response->println("<div class='toast-body'>");
  response->println("✅ Налаштування відновлено! Перезавантаження...");
  response->println("</div>");
  response->println("</div>");
  response->println("<div id='restore-error-toast' class='toast hide' role='alert' aria-live='assertive' aria-atomic='true' data-delay='2000'>");
  response->println("<div class='toast-body'>");
  response->println("🚫 Помилка відновлення налаштувань!");
  response->println("</div>");
  response->println("</div>");
  response->println("</div>");
  response->println("</div>");
  response->println("<script src='https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.slim.min.js' integrity='sha384-DfXdz2htPH0lsSSs5nCTpuj/zy4C+OGpamoFVy38MVBnE+IbbVYUew+OrCXaRkfj' crossorigin='anonymous'></script>");
  response->println("<script src='https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js' integrity='sha384-Fy6S3B9q64WdZWQUiU+q4/2Lc9npb8tCaSX9FK7E8HnRr0Jz8D6OP9dO5Vg3Q9ct' crossorigin='anonymous'></script>");
  response->println("<script src='https://cdn.jsdelivr.net/npm/js-cookie@3.0.5/dist/js.cookie.min.js'></script>");
#if FW_UPDATE_ENABLED
  if (fwUpdateAvailable) {
    response->println("<script src='https://cdn.jsdelivr.net/npm/marked/marked.min.js'></script>");
  }
#endif
  response->print("<script src='https://");
  response->print(settings.getString(WS_SERVER_HOST));
  response->println("/static/jaam_v1.js'></script>");
  response->print("<script src='https://");
  response->print(settings.getString(WS_SERVER_HOST));
  response->println("/static/jaam_v2.js'></script>");
  response->println("</body>");
  response->println("</html>");
}

void handleBrightness(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  AsyncResponseStream* response = request->beginResponseStream(asyncsrv::T_text_html);

  addHeader(response);
  addLinks(response);

  response->println("<form action='/saveBrightness' method='POST'>");
  response->println("<div class='row justify-content-center'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->print("<div class='alert alert-success' role='alert'>Поточний рівень яскравості: <b>");
  response->print(settings.getInt(MAP_MODE) == 5 ? settings.getInt(HA_LIGHT_BRIGHTNESS) : settings.getInt(CURRENT_BRIGHTNESS));
  response->println("%</b><br>\"Нічний режим\": <b>");
  int nightModeType = getNightModeType();
  response->print(nightModeType == 0 ? "Вимкнено" : nightModeType == 1 ? "Активовано кнопкою" : nightModeType == 2 ? "Активовано за часом доби" : "Активовано за даними сенсора освітлення");
  response->println("</b></div>");
  addSlider(response, "brightness", "Загальна", settings.getInt(BRIGHTNESS), 0, 100, 1, "%", settings.getInt(BRIGHTNESS_MODE) == 1 || settings.getInt(BRIGHTNESS_MODE) == 2);
  addSlider(response, "brightness_day", "Денна", settings.getInt(BRIGHTNESS_DAY), 0, 100, 1, "%", settings.getInt(BRIGHTNESS_MODE) == 0);
  addSlider(response, "brightness_night", "Нічна", settings.getInt(BRIGHTNESS_NIGHT), 0, 100, 1, "%");
  if (display.isDisplayAvailable()) {
    addCheckbox(response, "dim_display_on_night", settings.getBool(DIM_DISPLAY_ON_NIGHT), "Знижувати яскравість дисплею у нічний час");
  }
  addSelectBox(response, "brightness_auto", "Автоматична яскравість", settings.getInt(BRIGHTNESS_MODE), AUTO_BRIGHTNESS_MODES, AUTO_BRIGHTNESS_OPTIONS_COUNT);
  addSlider(response, "brightness_alert", "Області з тривогами", settings.getInt(BRIGHTNESS_ALERT), 0, 100, 1, "%");
  addSlider(response, "brightness_clear", "Області без тривог", settings.getInt(BRIGHTNESS_CLEAR), 0, 100, 1, "%");
  addSlider(response, "brightness_new_alert", "Нові тривоги", settings.getInt(BRIGHTNESS_NEW_ALERT), 0, 100, 1, "%");
  addSlider(response, "brightness_alert_over", "Відбій тривог", settings.getInt(BRIGHTNESS_ALERT_OVER), 0, 100, 1, "%");
  addSlider(response, "brightness_explosion", "Вибухи, БПЛА, ракетна небезпека, КАБ", settings.getInt(BRIGHTNESS_EXPLOSION), 0, 100, 1, "%");
  addSlider(response, "brightness_home_district", "Домашній регіон", settings.getInt(BRIGHTNESS_HOME_DISTRICT), 0, 100, 1, "%");
  if (isBgStripEnabled()) {
    addSlider(response, "brightness_bg", "Фонова LED-стрічка", settings.getInt(BRIGHTNESS_BG), 0, 100, 1, "%");
  }
  if (isServiceStripEnabled()) {
    addSlider(response, "brightness_service", "Сервісні LED", settings.getInt(BRIGHTNESS_SERVICE), 0, 100, 1, "%");
  }
  if (lightSensor.isAnySensorAvailable()) {
    addSlider(response, "light_sensor_factor", "Коефіцієнт чутливості сенсора освітлення", settings.getFloat(LIGHT_SENSOR_FACTOR), 0.1f, 30.0f, 0.1f);
  }
  response->println("<p class='text-info'>Детальніше про сенсор освітлення на <a href='https://github.com/J-A-A-M/ukraine_alarm_map/wiki/%D0%A1%D0%B5%D0%BD%D1%81%D0%BE%D1%80-%D0%BE%D1%81%D0%B2%D1%96%D1%82%D0%BB%D0%B5%D0%BD%D0%BD%D1%8F'>Wiki</a>.</p>");
  response->println("<button type='submit' class='btn btn-info'>Зберегти налаштування</button>");
  response->println("</div>");
  response->println("</div>");
  response->println("</form>");

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void handleColors(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  AsyncResponseStream* response = request->beginResponseStream(asyncsrv::T_text_html);

  addHeader(response);
  addLinks(response);

  response->println("<form action='/saveColors' method='POST'>");
  response->println("<div class='row justify-content-center' data-parent='#accordion'>");
  response->println("<div class='by col-md-9 mt-2'>");
  addSlider(response, "color_alert", "Області з тривогами", settings.getInt(COLOR_ALERT), 0, 360, 1, "", false, true);
  addSlider(response, "color_clear", "Області без тривог", settings.getInt(COLOR_CLEAR), 0, 360, 1, "", false, true);
  addSlider(response, "color_new_alert", "Нові тривоги", settings.getInt(COLOR_NEW_ALERT), 0, 360, 1, "", false, true);
  addSlider(response, "color_alert_over", "Відбій тривог", settings.getInt(COLOR_ALERT_OVER), 0, 360, 1, "", false, true);
  addSlider(response, "color_explosion", "Вибухи", settings.getInt(COLOR_EXPLOSION), 0, 360, 1, "", false, true);
  addSlider(response, "color_missiles", "Ракетна небезпека", settings.getInt(COLOR_MISSILES), 0, 360, 1, "", false, true);
  addSlider(response, "color_kabs", "Загроза КАБ", settings.getInt(COLOR_KABS), 0, 360, 1, "", false, true);
  addSlider(response, "color_drones", "Загроза БПЛА", settings.getInt(COLOR_DRONES), 0, 360, 1, "", false, true);
  addSlider(response, "color_home_district", "Домашній регіон", settings.getInt(COLOR_HOME_DISTRICT), 0, 360, 1, "", false, true);
  if (isBgStripEnabled()) {
    addSlider(response, "color_bg_neighbor_alert", "Колір фонової LED-стрічки при тривозі у сусідніх регіонах", settings.getInt(COLOR_BG_NEIGHBOR_ALERT), 0, 360, 1, "", false, true);
  }
  response->println("<button type='submit' class='btn btn-info'>Зберегти налаштування</button>");
  response->println("</div>");
  response->println("</div>");
  response->println("</form>");

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void handleModes(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  AsyncResponseStream* response = request->beginResponseStream(asyncsrv::T_text_html);

  addHeader(response);
  addLinks(response);

  response->println("<form action='/saveModes' method='POST'>");
  response->println("<div class='row justify-content-center' data-parent='#accordion'>");
  response->println("<div class='by col-md-9 mt-2'>");
  if (settings.getInt(LEGACY) == 1 || settings.getInt(LEGACY) == 2) {
  addSelectBox(response, "kyiv_district_mode", "Режим діода \"Київська область\"", settings.getInt(KYIV_DISTRICT_MODE), KYIV_LED_MODE_OPTIONS, KYIV_LED_MODE_COUNT);
  }
  addSelectBox(response, "home_district", "Домашній регіон", settings.getInt(HOME_DISTRICT), DISTRICTS, DISTRICTS_COUNT);
  addSelectBox(response, "map_mode", "Режим мапи", settings.getInt(MAP_MODE), MAP_MODES, MAP_MODES_COUNT);
  addSelectBox(response, "alarms_auto_switch", "Перемикання мапи в режим тривоги у випадку тривоги у домашньому регіоні", settings.getInt(ALARMS_AUTO_SWITCH), AUTO_ALARM_MODES, AUTO_ALARM_MODES_COUNT);
  addSelectBox(response, "alarms_notify_mode", "Відображення на мапі нових тривог, відбою та інших загроз", settings.getInt(ALARMS_NOTIFY_MODE), ALERT_NOTIFY_OPTIONS, ALERT_NOTIFY_OPTIONS_COUNT);
  addCheckbox(response, "enable_critical_notifications", settings.getBool(ENABLE_CRITICAL_NOTIFICATIONS), "Увімкнути критичні сповіщення (Міг, Кинджал, Стратегічна авіація, Крилаті ракети, Балістика)");
  addCheckbox(response, "enable_explosions", settings.getBool(ENABLE_EXPLOSIONS), "Показувати вибухи");
  addCheckbox(response, "enable_missiles", settings.getBool(ENABLE_MISSILES), "Показувати ракетну небезпеку");
  addCheckbox(response, "enable_drones", settings.getBool(ENABLE_DRONES), "Показувати загрозу БПЛА");
  addCheckbox(response, "enable_kabs", settings.getBool(ENABLE_KABS), "Показувати загрозу КАБ");
  addSlider(response, "alert_on_time", "Тривалість відображення початку тривоги", settings.getInt(ALERT_ON_TIME), 1, 10, 1, " хв.", settings.getInt(ALARMS_NOTIFY_MODE) == 0);
  addSlider(response, "alert_off_time", "Тривалість відображення відбою", settings.getInt(ALERT_OFF_TIME), 1, 10, 1, " хв.", settings.getInt(ALARMS_NOTIFY_MODE) == 0);
  addSlider(response, "explosion_time", "Тривалість відображення початку ракетної небезпеки, БПЛА, КАБ та інформації про вибухи", settings.getInt(EXPLOSION_TIME), 1, 10, 1, " хв.", settings.getInt(ALARMS_NOTIFY_MODE) == 0);
  addSlider(response, "alert_blink_time", "Тривалість анімації зміни яскравості", settings.getInt(ALERT_BLINK_TIME), 1, 5, 1, " с.", settings.getInt(ALARMS_NOTIFY_MODE) != 2);
  
  if (display.isDisplayAvailable()) {
    addSelectBox(response, "display_mode", "Режим дисплея", settings.getInt(DISPLAY_MODE), DISPLAY_MODES, DISPLAY_MODE_OPTIONS_MAX, false);
    addCheckbox(response, "home_alert_time", settings.getBool(HOME_ALERT_TIME), "Показувати на екрані тривалість тривоги у домашньому регіоні");
    addCheckbox(response, "invert_display", settings.getBool(INVERT_DISPLAY), "Інвертувати дисплей (темний шрифт на світлому фоні). УВАГА - ресурс роботи дисплея суттєво зменшиться");
    addSlider(response, "display_mode_time", "Час перемикання дисплея", settings.getInt(DISPLAY_MODE_TIME), 1, 60, 1, " с.");
    addSlider(response, "critical_notifications_display_time", "Тривалість відображення критичних і локальних сповіщень на дисплеї", settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME), 5, 120, 5, " с.");
    response->println("Відображати в режимі \"Перемикання\":<br><br>");
    addCheckbox(response, "toggle_mode_weather", settings.getBool(TOGGLE_MODE_WEATHER), "Погоду у домашньому регіоні");
    if (climate.isAnySensorAvailable()) {
      if (climate.isTemperatureAvailable()) addCheckbox(response, "toggle_mode_temp", settings.getBool(TOGGLE_MODE_TEMP), "Температуру в приміщенні");
      if (climate.isHumidityAvailable()) addCheckbox(response, "toggle_mode_hum", settings.getBool(TOGGLE_MODE_HUM), "Вологість в приміщенні");
      if (climate.isPressureAvailable()) addCheckbox(response, "toggle_mode_press", settings.getBool(TOGGLE_MODE_PRESS), "Тиск");
    }
    addCheckbox(response, "toggle_mode_energy", settings.getBool(TOGGLE_MODE_ENERGY), "Стан енергосистем у домашньому регіоні");
    addCheckbox(response, "toggle_mode_radiation", settings.getBool(TOGGLE_MODE_RADIATION), "Середній рівень радіації у домашньому регіоні");
  }
  addSlider(response, "day_start", "Початок дня", settings.getInt(DAY_START), 0, 24, 1, " година");
  addSlider(response, "night_start", "Початок ночі", settings.getInt(NIGHT_START), 0, 24, 1, " година");
  if (climate.isTemperatureAvailable()) {
    addSlider(response, "temp_correction", "Корегування температури", settings.getFloat(TEMP_CORRECTION), -10.0f, 10.0f, 0.1f, "°C");
  }
  if (climate.isHumidityAvailable()) {
    addSlider(response, "hum_correction", "Корегування вологості", settings.getFloat(HUM_CORRECTION), -20.0f, 20.0f, 0.5f, "%");
  }
  if (climate.isPressureAvailable()) {
    addSlider(response, "pressure_correction", "Корегування атмосферного тиску", settings.getFloat(PRESSURE_CORRECTION), -50.0f, 50.0f, 0.5f, " мм.рт.ст.");
  }
  addSlider(response, "weather_min_temp", "Нижній рівень температури (режим 'Погода')", settings.getInt(WEATHER_MIN_TEMP), -20, 10, 1, "°C");
  addSlider(response, "weather_max_temp", "Верхній рівень температури (режим 'Погода')", settings.getInt(WEATHER_MAX_TEMP), 11, 40, 1, "°C");
  addSlider(response, "radiation_max", "Верхній рівень радіації (режим 'Радіація')", settings.getInt(RADIATION_MAX), 110, 2000, 10, " нЗв/год");
  addSlider(response, "color_lamp", "Колір режиму \"Лампа\"", rgb2hue(settings.getInt(HA_LIGHT_R), settings.getInt(HA_LIGHT_G), settings.getInt(HA_LIGHT_B)), 0, 360, 1, "", false, true);
  addSlider(response, "brightness_lamp", "Яскравість режиму \"Лампа\"", settings.getInt(HA_LIGHT_BRIGHTNESS), 0, 100, 1, "%");
  if (buttons.isButton1Enabled()) {
    addSelectBox(response, "button_mode", "Режим кнопки (Single Click)", settings.getInt(BUTTON_1_MODE), SINGLE_CLICK_OPTIONS, SINGLE_CLICK_OPTIONS_MAX, NULL);
    addSelectBox(response, "button_mode_long", "Режим кнопки (Long Click)", settings.getInt(BUTTON_1_MODE_LONG), LONG_CLICK_OPTIONS, LONG_CLICK_OPTIONS_MAX, NULL);
  }
  if (buttons.isButton2Enabled()) {
    addSelectBox(response, "button2_mode", "Режим кнопки 2 (Single Click)", settings.getInt(BUTTON_2_MODE), SINGLE_CLICK_OPTIONS, SINGLE_CLICK_OPTIONS_MAX, NULL);
    addSelectBox(response, "button2_mode_long", "Режим кнопки 2 (Long Click)", settings.getInt(BUTTON_2_MODE_LONG), LONG_CLICK_OPTIONS, LONG_CLICK_OPTIONS_MAX, NULL);
  }
  
  if (settings.getInt(LEGACY) == 0 || settings.getInt(LEGACY) == 3) {
    addCheckbox(response, "service_diodes_mode", settings.getInt(SERVICE_DIODES_MODE), "Ввімкнути сервісні діоди");
  }
  addCheckbox(response, "min_of_silence", settings.getBool(MIN_OF_SILENCE), "Активувати режим \"Хвилина мовчання\" (щоранку о 09:00)");
  addSlider(response, "time_zone", "Часовий пояс (зсув відносно Ґрінвіча)", settings.getInt(TIME_ZONE), -12, 12, 1, " год.");
  response->println("<button type='submit' class='btn btn-info'>Зберегти налаштування</button>");
  response->println("</div>");
  response->println("</div>");
  response->println("</form>");

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void handleSounds(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  AsyncResponseStream* response = request->beginResponseStream(asyncsrv::T_text_html);

  addHeader(response);
  addLinks(response);
  response->println("<form action='/saveSounds' method='POST'>");
  response->println("<div class='row justify-content-center' data-parent='#accordion'>");
  response->println("<div class='by col-md-9 mt-2'>");
#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
  addCheckbox(response, "sound_on_min_of_sl", settings.getBool(SOUND_ON_MIN_OF_SL), "Відтворювати звуки під час \"Xвилини мовчання\"");
  addCheckbox(response, "sound_on_alert", settings.getBool(SOUND_ON_ALERT), "Звукове сповіщення при тривозі у домашньому регіоні", "window.disableElement(\"melody_on_alert\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_alert", "Мелодія при тривозі у домашньому регіоні (буззер)", settings.getInt(MELODY_ON_ALERT), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_ALERT), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_alert", "Трек при тривозі у домашньому регіоні", settings.getInt(TRACK_ON_ALERT), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_ALERT), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_alert_end", settings.getBool(SOUND_ON_ALERT_END), "Звукове сповіщення при скасуванні тривоги у домашньому регіоні", "window.disableElement(\"melody_on_alert_end\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_alert_end", "Мелодія при скасуванні тривоги у домашньому регіоні", settings.getInt(MELODY_ON_ALERT_END), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_ALERT_END), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_alert_end", "Трек при скасуванні тривоги у домашньому регіоні", settings.getInt(TRACK_ON_ALERT_END), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_ALERT_END), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_explosion", settings.getBool(SOUND_ON_EXPLOSION), "Звукове сповіщення при вибухах, БПЛА, КАБ, ракетах у домашньому регіоні", "window.disableElement(\"melody_on_explosion\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_explosion", "Мелодія при вибухах, БПЛА, КАБ, ракетах у домашньому регіоні", settings.getInt(MELODY_ON_EXPLOSION), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_EXPLOSION), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_explosion", "Трек при вибухах, БПЛА, КАБ, ракетах у домашньому регіоні", settings.getInt(TRACK_ON_EXPLOSION), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_EXPLOSION), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_critical_mig", settings.getBool(SOUND_ON_CRITICAL_MIG), "Звукове сповіщення при критичному сповіщенні 'Зліт МІГ-31к'", "window.disableElement(\"melody_on_critical_mig\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_critical_mig", "Мелодія при критичному сповіщенні 'Зліт МІГ-31к'", settings.getInt(MELODY_ON_CRITICAL_MIG), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_CRITICAL_MIG), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_critical_mig", "Трек при критичному сповіщенні 'Зліт МІГ-31к'", settings.getInt(TRACK_ON_CRITICAL_MIG), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_CRITICAL_MIG), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_critical_strategic", settings.getBool(SOUND_ON_CRITICAL_STRATEGIC), "Звукове сповіщення при критичному сповіщенні 'Зліт стратегічної авіації'", "window.disableElement(\"melody_on_critical_strategic\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_critical_strategic", "Мелодія при критичному сповіщенні 'Зліт стратегічної авіації'", settings.getInt(MELODY_ON_CRITICAL_STRATEGIC), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_CRITICAL_STRATEGIC), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_critical_strategic", "Трек при критичному сповіщенні 'Зліт стратегічної авіації'", settings.getInt(TRACK_ON_CRITICAL_STRATEGIC), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_CRITICAL_STRATEGIC), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_critical_mig_missiles", settings.getBool(SOUND_ON_CRITICAL_MIG_MISSILES), "Звукове сповіщення при критичному сповіщенні 'Запуск Х-47М2 «Кинджал»'", "window.disableElement(\"melody_on_critical_mig_missiles\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_critical_mig_missiles", "Мелодія при критичному сповіщенні 'Запуск Х-47М2 «Кинджал»'", settings.getInt(MELODY_ON_CRITICAL_MIG_MISSILES), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_CRITICAL_MIG_MISSILES), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_critical_mig_missiles", "Трек при критичному сповіщенні 'Запуск Х-47М2 «Кинджал»'", settings.getInt(TRACK_ON_CRITICAL_MIG_MISSILES), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_CRITICAL_MIG_MISSILES), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_critical_ballistic_missiles", settings.getBool(SOUND_ON_CRITICAL_BALLISTIC_MISSILES), "Звукове сповіщення при критичному сповіщенні 'Балістика'", "window.disableElement(\"melody_on_critical_ballistic_missiles\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_critical_ballistic_missiles", "Мелодія при критичному сповіщенні 'Балістика'", settings.getInt(MELODY_ON_CRITICAL_BALLISTIC_MISSILES), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_CRITICAL_BALLISTIC_MISSILES), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_critical_ballistic_missiles", "Трек при критичному сповіщенні 'Балістика'", settings.getInt(TRACK_ON_CRITICAL_BALLISTIC_MISSILES), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_CRITICAL_BALLISTIC_MISSILES), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_critical_strategic_missiles", settings.getBool(SOUND_ON_CRITICAL_STRATEGIC_MISSILES), "Звукове сповіщення при критичному сповіщенні 'Запуск крилатих ракет'", "window.disableElement(\"melody_on_critical_strategic_missiles\", !this.checked);");
  if (isBuzzerEnabled()) addSelectBox(response, "melody_on_critical_strategic_missiles", "Мелодія при критичному сповіщенні 'Запуск крилатих ракет'", settings.getInt(MELODY_ON_CRITICAL_STRATEGIC_MISSILES), MELODY_NAMES, MELODIES_COUNT, !settings.getBool(SOUND_ON_CRITICAL_STRATEGIC_MISSILES), "window.playTestSound(this.value);");
  if (dfPlayerConnected) addSelectBox(response, "track_on_critical_strategic_missiles", "Трек при критичному сповіщенні 'Запуск крилатих ракет'", settings.getInt(TRACK_ON_CRITICAL_STRATEGIC_MISSILES), dynamicTrackNames, totalFiles, !settings.getBool(SOUND_ON_CRITICAL_STRATEGIC_MISSILES), "window.playTestTrack(this.value);");
  addCheckbox(response, "sound_on_every_hour", settings.getBool(SOUND_ON_EVERY_HOUR), "Звукове сповіщення щогодини");
  addCheckbox(response, "sound_on_button_click", settings.getBool(SOUND_ON_BUTTON_CLICK), "Сигнали при натисканні кнопки");
  addCheckbox(response, "mute_sound_on_night", settings.getBool(MUTE_SOUND_ON_NIGHT), "Вимикати всі звуки у нічний час (налаштовується на вкладці \"Режими\")", "window.disableElement(\"ignore_mute_on_alert\", !this.checked);");
  addCheckbox(response, "ignore_mute_on_alert", settings.getBool(IGNORE_MUTE_ON_ALERT), "Сигнали тривоги навіть у нічний час", NULL, !settings.getBool(MUTE_SOUND_ON_NIGHT));
  addSlider(response, "melody_volume_day", "Гучність мелодії вдень", settings.getInt(MELODY_VOLUME_DAY), 0, 100, 1, "%");
  addSlider(response, "melody_volume_night", "Гучність мелодії вночі", settings.getInt(MELODY_VOLUME_NIGHT), 0, 100, 1, "%");

  response->println("<button type='submit' class='btn btn-info aria-expanded='false'>Зберегти налаштування</button>");
  if (isBuzzerEnabled()) response->println("<button type='button' class='btn btn-primary float-right' onclick='playTestSound();' aria-expanded='false'>Тест буззера</button>");
  if (dfPlayerConnected) response->println("<button type='button' class='btn btn-primary float-right' onclick='playTestTrack();' aria-expanded='false'>Тест DF Player Pro</button>");
#endif
  response->println("</div>");
  response->println("</div>");
  response->println("</form>");

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void handleTelemetry(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  int local_home_district = settings.getInt(HOME_DISTRICT);

  AsyncResponseStream* response = request->beginResponseStream(asyncsrv::T_text_html);

  addHeader(response);
  addLinks(response);

  response->println("<form action='/refreshTelemetry' method='POST'>");
  response->println("<div class='row justify-content-center' data-parent='#accordion'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->println("<div class='row justify-content-center'>");
  addCard(response, "Час роботи", uptimeChar, "", 4);
  addCard(response, "Температура ESP32", cpuTemp, "°C");
  addCard(response, "Вільна памʼять", freeHeapSize, "кБ");
  addCard(response, "Використана памʼять", usedHeapSize, "кБ");
  addCard(response, "WiFi сигнал", wifiSignal, "dBm");
  addCard(response, getNameById(DISTRICTS, local_home_district, DISTRICTS_COUNT), id_to_weather[local_home_district], "°C");
  addCard(response, getNameById(DISTRICTS, local_home_district, DISTRICTS_COUNT), id_to_radiation[local_home_district], " нЗв/год", 2, 0);
  if (ha.isHaEnabled()) {
    addCard(response, "Home Assistant", haConnected ? "Підключено" : "Відключено", "", 2);
  }
  addCard(response, "Сервер тривог", client_websocket.available() ? "Підключено" : "Відключено", "", 2);
  if (climate.isTemperatureAvailable()) {
    addCard(response, "Температура", climate.getTemperature(settings.getFloat(TEMP_CORRECTION)), "°C");
  }
  if (climate.isHumidityAvailable()) {
    addCard(response, "Вологість", climate.getHumidity(settings.getFloat(HUM_CORRECTION)), "%");
  }
  if (climate.isPressureAvailable()) {
    addCard(response, "Тиск", climate.getPressure(settings.getFloat(PRESSURE_CORRECTION)), "mmHg", 2);
  }
  if (lightSensor.isLightSensorAvailable()) {
    addCard(response, "Освітленість", lightSensor.getLightLevel(settings.getFloat(LIGHT_SENSOR_FACTOR)), "lx");
  }
  response->println("</div>");
  response->println("<button type='submit' class='btn btn-info mt-3'>Оновити значення</button>");
  response->println("</div>");
  response->println("</div>");
  response->println("</form>");

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void handleDev(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  AsyncResponseStream* response = request->beginResponseStream(asyncsrv::T_text_html);

  addHeader(response);
  addLinks(response);

  response->println("<div class='row justify-content-center' data-parent='#accordion'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->println("<form action='/saveDev' method='POST'>");
  addSelectBox(response, "legacy", "Режим прошивки", settings.getInt(LEGACY), LEGACY_OPTIONS, LEGACY_OPTIONS_COUNT);
  if ((settings.getInt(LEGACY) == 1 || settings.getInt(LEGACY) == 2) && display.isDisplayEnabled()) {
    addSelectBox(response, "display_model", "Тип дисплею", settings.getInt(DISPLAY_MODEL), DISPLAY_MODEL_OPTIONS, DISPLAY_MODEL_OPTIONS_COUNT);
    addSelectBox(response, "display_height", "Розмір дисплею", settings.getInt(DISPLAY_HEIGHT), DISPLAY_HEIGHT_OPTIONS, DISPLAY_HEIGHT_OPTIONS_COUNT);
  }
  if (ha.isHaEnabled()) {
    addInputText(response, "ha_brokeraddress", "Адреса mqtt Home Assistant", "text", settings.getString(HA_BROKER_ADDRESS), 30);
    addInputText(response, "ha_mqttport", "Порт mqtt Home Assistant", "number", String(settings.getInt(HA_MQTT_PORT)).c_str());
    addInputText(response, "ha_mqttuser", "Користувач mqtt Home Assistant", "text", settings.getString(HA_MQTT_USER), 30);
    addInputText(response, "ha_mqttpassword", "Пароль mqtt Home Assistant", "text", settings.getString(HA_MQTT_PASSWORD), 65);
  }
  addInputText(response, "ntphost", "Адреса сервера NTP", "text", settings.getString(NTP_HOST), 30);
  addInputText(response, "serverhost", "Адреса сервера даних", "text", settings.getString(WS_SERVER_HOST), 30);
  addInputText(response, "websocket_port", "Порт Websockets", "number", String(settings.getInt(WS_SERVER_PORT)).c_str());
  addInputText(response, "updateport", "Порт сервера прошивок", "number", String(settings.getInt(UPDATE_SERVER_PORT)).c_str());
  addInputText(response, "devicename", "Назва пристрою", "text", settings.getString(DEVICE_NAME), 30);
  addInputText(response, "devicedescription", "Опис пристрою", "text", settings.getString(DEVICE_DESCRIPTION), 50);
  addInputText(response, "broadcastname", ("Локальна адреса (" + String(settings.getString(BROADCAST_NAME)) + ".local)").c_str(), "text", settings.getString(BROADCAST_NAME), 30);
  if (settings.getInt(LEGACY) == 1 || settings.getInt(LEGACY) == 2) {
    addInputText(response, "pixelpin", "Керуючий пін лед-стрічки", "number", String(settings.getInt(MAIN_LED_PIN)).c_str());
    addInputText(response, "bg_pixelpin", "Керуючий пін фонової лед-стрічки (-1 - стрічки немає)", "number", String(settings.getInt(BG_LED_PIN)).c_str());
    addInputText(response, "bg_pixelcount", "Кількість пікселів фонової лед-стрічки", "number", String(settings.getInt(BG_LED_COUNT)).c_str());
    addInputText(response, "buttonpin", "Керуючий пін кнопки 1 (-1 - вимкнено)", "number", String(settings.getInt(BUTTON_1_PIN)).c_str());
    addCheckbox(response, "use_touch_button1", settings.getBool(USE_TOUCH_BUTTON_1), "Підтримка touch-кнопки TTP223 для кнопки 1");
    addInputText(response, "button2pin", "Керуючий пін кнопки 2 (-1 - вимкнено)", "number", String(settings.getInt(BUTTON_2_PIN)).c_str());
    addCheckbox(response, "use_touch_button2", settings.getBool(USE_TOUCH_BUTTON_2), "Підтримка touch-кнопки TTP223 для кнопки 2");
  }
  addSelectBox(response, "alert_clear_pin_mode", "Режим роботи пінів тривоги та відбою", settings.getInt(ALERT_CLEAR_PIN_MODE), ALERT_PIN_MODES_OPTIONS, ALERT_PIN_MODES_COUNT);
  addInputText(response, "alertpin", "Пін тривоги у домашньому регіоні (має бути output, -1 - вимкнено)", "number", String(settings.getInt(ALERT_PIN)).c_str());
  addInputText(response, "clearpin", "Пін відбою у домашньому регіоні (має бути output, лише для Імпульсного режиму, -1 - вимкнено)", "number", String(settings.getInt(CLEAR_PIN)).c_str());
  addSlider(response, "alert_clear_pin_time", "Тривалість замикання пінів тривоги та відбою в Імпульсному режимі", settings.getFloat(ALERT_CLEAR_PIN_TIME), 0.5f, 10.0f, 0.5f, " с.");

  if (settings.getInt(LEGACY) != 3) {
    addInputText(response, "lightpin", "Пін фоторезистора (має бути input, -1 - вимкнено)", "number", String(settings.getInt(LIGHT_SENSOR_PIN)).c_str());
#if BUZZER_ENABLED
    addInputText(response, "buzzerpin", "Керуючий пін динаміка (має бути output, -1 - вимкнено)", "number", String(settings.getInt(BUZZER_PIN)).c_str());
#endif
  }
#if DFPLAYER_PRO_ENABLED
    addInputText(response, "dfrxpin", "RX для DF Player (-1 - вимкнено)", "number", String(settings.getInt(DF_RX_PIN)).c_str());
    addInputText(response, "dftxpin", "TX для DF Player (-1 - вимкнено)", "number", String(settings.getInt(DF_TX_PIN)).c_str());
#endif
  response->println("<b>");
  response->println("<p class='text-danger'>УВАГА: будь-яка зміна налаштування в цьому розділі призводить до примусового перезаватаження мапи.</p>");
  response->println("<p class='text-danger'>УВАГА: деякі зміни налаштувань можуть привести до відмови прoшивки, якщо налаштування будуть несумісні. Будьте впевнені, що Ви точно знаєте, що міняється і для чого.</p>");
  response->println("<p class='text-danger'>Якщо мапа втратить працездатність після змін та перезавантаження, необхідно перепрошити мапу на сайті <a href='https://flasher.jaam.net.ua/'>flasher.jaam.net.ua</a>. Якщо звичайна прошивка не допомогла, перепрошити ще раз з видаленням всіх даних (під час прошивки треба поставити галочку 'Erase device')</p>");
  response->println("</b>");
  response->println("<button type='submit' class='btn btn-info' aria-expanded='false'>Зберегти налаштування</button>");
  response->print("<a href='http://");
  response->print(getLocalIP());
  response->println(":8080/0wifi' target='_blank' class='btn btn-primary float-right' aria-expanded='false'>Змінити налаштування WiFi</a>");
  response->println("</form>");
  response->println("</div>");
  response->println("</div>");
  response->println("<div class='row justify-content-center' data-parent='#accordion'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->println("<b><p class='text'>У цьому розділі можна зберегти та відновити налаштування мапи. Зберігаються всі налаштування, крім налаштувань WiFi.</p></b>");
  response->println("<form id='form_restore' action='/restore' method='POST' enctype='multipart/form-data'>");
  response->println("<a href='/backup' target='_blank' class='btn btn-info' aria-expanded='false'>Завантажити налаштування</a>");
  response->println("<label for='restore' class='btn btn-primary float-right' aria-expanded='false'>Відновити налаштування</label>");
  response->println("<input id='restore' name='restore' type='file' style='visibility:hidden;' onchange='javascript:document.getElementById(\"form_restore\").submit();' accept='application/json'/>");
  response->println("</form>");
  response->println("</div>");
  response->println("</div>");

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void handleFirmware(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  AsyncResponseStream* response = request->beginResponseStream(asyncsrv::T_text_html);

  addHeader(response);
  addLinks(response);

  #if FW_UPDATE_ENABLED
  response->println("<div class='row justify-content-center' data-parent='#accordion'>");
  response->println("<div class='by col-md-9 mt-2'>");
  response->println("<form action='/saveFirmware' method='POST'>");
  if (display.isDisplayAvailable()) addCheckbox(response, "new_fw_notification", settings.getInt(NEW_FW_NOTIFICATION), "Сповіщення про нові прошивки на екрані");
  addSelectBox(response, "fw_update_channel", "Канал оновлення прошивок", settings.getInt(FW_UPDATE_CHANNEL), FW_UPDATE_CHANNELS, FW_UPDATE_CHANNELS_COUNT);
  response->println("<b><p class='text-danger'>УВАГА: BETA-прошивки можуть вивести мапу з ладу i містити помилки. Якщо у Вас немає можливості прошити мапу через кабель, будь ласка, залишайтесь на каналі PRODUCTION!</p></b>");
  response->println("<button type='submit' class='btn btn-info'>Зберегти налаштування</button>");
  response->println("</form>");
  response->println("<form action='/update' method='POST'>");
  response->println("Файл прошивки");
  response->println("<select name='bin_name' class='form-control' id='sb16'>");
  const int count = settings.getInt(FW_UPDATE_CHANNEL) ? testBinsCount : binsCount;
  for (int i = 0; i < count; i++) {
    String filename = String(settings.getInt(FW_UPDATE_CHANNEL) ? test_bin_list[i] : bin_list[i]);
    response->print("<option value='");
    response->print(filename);
    response->print("'");
    if (i == 0) response->print(" selected");
    response->print(">");
    response->print(filename);
    response->println("</option>");
  }
  response->println("</select>");
  response->println("</br>");
  response->println("<button type='submit' class='btn btn-danger'>ОНОВИТИ ПРОШИВКУ</button>");
  response->println("</form>");
  response->println("</div>");
  response->println("</div>");
#endif

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void handleRoot(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  AsyncResponseStream* response = request->beginResponseStream("text/html");

  addHeader(response);
  addLinks(response);

  addFooter(response);

  response->setCode(200);
  request->send(response);
}

void saveInt(Type settingType, int newValue, const char* paramName) {
  settings.saveInt(settingType, newValue);
  reportSettingsChange(paramName, newValue);
}

bool saveInt(const AsyncWebParameter* param, Type settingType, bool (*saveFun)(int) = NULL, void (*additionalFun)(void) = NULL) {
  if (!param) return false;
  int newValue = param->value().toInt();
  if (saveFun) {
    return saveFun(newValue);
  }
  if (newValue != settings.getInt(settingType)) {
    const char* paramName = param->name().c_str();
    saveInt(settingType, newValue, paramName);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
}

bool saveFloat(const AsyncWebParameter* param, Type settingType, bool (*saveFun)(float) = NULL, void (*additionalFun)(void) = NULL) {
  if (!param) return false;
  float paramValue = param->value().toFloat();
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (paramValue != settings.getFloat(settingType)) {
    const char* paramName = param->name().c_str();
    settings.saveFloat(settingType, paramValue);
    reportSettingsChange(paramName, paramValue);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
}

bool saveBool(const AsyncWebParameter* param, const char* paramName, Type settingType, bool (*saveFun)(bool) = NULL, void (*additionalFun)(void) = NULL) {
  int paramValue = param ? 1 : 0;
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (paramValue != settings.getBool(settingType)) {
    settings.saveBool(settingType, paramValue);
    reportSettingsChange(paramName, paramValue ? "true" : "false");
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
}

bool saveString(const AsyncWebParameter* param, Type settingType, bool (*saveFun)(const char*) = NULL, void (*additionalFun)(void) = NULL) {
  if (!param) return false;
  const char* paramValue = param->value().c_str();
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (strcmp(paramValue, settings.getString(settingType)) != 0) {
    const char* paramName = param->name().c_str();
    settings.saveString(settingType, paramValue);
    reportSettingsChange(paramName, paramValue);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
}

#if FW_UPDATE_ENABLED
void handleUpdate(AsyncWebServerRequest* request) {
  LOG.println("do_update triggered");
  initUpdate = true;
  if (request->hasParam("bin_name", true)) {
    const char* binName = request->getParam("bin_name", true)->value().c_str();
    strcpy(bin_name, binName);
  }
  request->redirect("/");
}
#endif

AsyncWebServerResponse* redirectResponse(AsyncWebServerRequest* request, const char* location, bool saved, bool reboot = false, bool restore = false, bool restoreError = false) {
  AsyncWebServerResponse* response = request->beginResponse(302);
  response->addHeader(asyncsrv::T_LOCATION, location);
  response->addHeader("Set-Cookie", "scroll=true");
  if (saved) response->addHeader("Set-Cookie", "saved=true");
  if (restore) response->addHeader("Set-Cookie", "restore=true");
  if (restoreError) response->addHeader("Set-Cookie", "restore-error=true");
  return response;
}

void handleSaveBrightness(AsyncWebServerRequest *request) {
  bool saved = false;
  saved = saveInt(request->getParam("brightness", true), BRIGHTNESS, saveBrightness) || saved;
  saved = saveInt(request->getParam("brightness_day", true), BRIGHTNESS_DAY, saveDayBrightness) || saved;
  saved = saveInt(request->getParam("brightness_night", true), BRIGHTNESS_NIGHT, saveNightBrightness) || saved;
  saved = saveInt(request->getParam("brightness_auto", true), BRIGHTNESS_MODE, saveAutoBrightnessMode) || saved;
  saved = saveInt(request->getParam("brightness_alert", true), BRIGHTNESS_ALERT) || saved;
  saved = saveInt(request->getParam("brightness_clear", true), BRIGHTNESS_CLEAR) || saved;
  saved = saveInt(request->getParam("brightness_new_alert", true), BRIGHTNESS_NEW_ALERT) || saved;
  saved = saveInt(request->getParam("brightness_alert_over", true), BRIGHTNESS_ALERT_OVER) || saved;
  saved = saveInt(request->getParam("brightness_explosion", true), BRIGHTNESS_EXPLOSION) || saved;
  saved = saveInt(request->getParam("brightness_home_district", true), BRIGHTNESS_HOME_DISTRICT) || saved;
  saved = saveInt(request->getParam("brightness_bg", true), BRIGHTNESS_BG) || saved;
  saved = saveInt(request->getParam("brightness_service", true), BRIGHTNESS_SERVICE, NULL, checkServicePins) || saved;
  saved = saveFloat(request->getParam("light_sensor_factor", true), LIGHT_SENSOR_FACTOR) || saved;
  saved = saveBool(request->getParam("dim_display_on_night", true), "dim_display_on_night", DIM_DISPLAY_ON_NIGHT, NULL, updateDisplayBrightness) || saved;

  if (saved) autoBrightnessUpdate();

  request->send(redirectResponse(request, "/brightness", saved));
}

void handleSaveColors(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveInt(request->getParam("color_alert", true), COLOR_ALERT) || saved;
  saved = saveInt(request->getParam("color_clear", true), COLOR_CLEAR) || saved;
  saved = saveInt(request->getParam("color_new_alert", true), COLOR_NEW_ALERT) || saved;
  saved = saveInt(request->getParam("color_alert_over", true), COLOR_ALERT_OVER) || saved;
  saved = saveInt(request->getParam("color_explosion", true), COLOR_EXPLOSION) || saved;
  saved = saveInt(request->getParam("color_missiles", true), COLOR_MISSILES) || saved;
  saved = saveInt(request->getParam("color_kabs", true), COLOR_KABS) || saved;
  saved = saveInt(request->getParam("color_drones", true), COLOR_DRONES) || saved;
  saved = saveInt(request->getParam("color_home_district", true), COLOR_HOME_DISTRICT) || saved;
  saved = saveInt(request->getParam("color_bg_neighbor_alert", true), COLOR_BG_NEIGHBOR_ALERT) || saved;

  request->send(redirectResponse(request, "/colors", saved));
}

void handleSaveModes(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveInt(request->getParam("map_mode", true), MAP_MODE, saveMapMode) || saved;
  saved = saveInt(request->getParam("brightness_lamp", true), HA_LIGHT_BRIGHTNESS, saveLampBrightness) || saved;
  saved = saveInt(request->getParam("display_mode", true), DISPLAY_MODE, saveDisplayMode) || saved;
  saved = saveInt(request->getParam("home_district", true), HOME_DISTRICT, saveHomeDistrict) || saved;
  saved = saveInt(request->getParam("display_mode_time", true), DISPLAY_MODE_TIME) || saved;
  saved = saveBool(request->getParam("toggle_mode_weather", true), "toggle_mode_weather", TOGGLE_MODE_WEATHER) || saved;
  saved = saveBool(request->getParam("toggle_mode_energy", true), "toggle_mode_energy", TOGGLE_MODE_ENERGY) || saved;
  saved = saveBool(request->getParam("toggle_mode_radiation", true), "toggle_mode_radiation", TOGGLE_MODE_RADIATION) || saved;
  saved = saveBool(request->getParam("toggle_mode_temp", true), "toggle_mode_temp", TOGGLE_MODE_TEMP) || saved;
  saved = saveBool(request->getParam("toggle_mode_hum", true), "toggle_mode_hum", TOGGLE_MODE_HUM) || saved;
  saved = saveBool(request->getParam("toggle_mode_press", true), "toggle_mode_press", TOGGLE_MODE_PRESS) || saved;
  saved = saveFloat(request->getParam("temp_correction", true), TEMP_CORRECTION, NULL, climateSensorCycle) || saved;
  saved = saveFloat(request->getParam("hum_correction", true), HUM_CORRECTION, NULL, climateSensorCycle) || saved;
  saved = saveFloat(request->getParam("pressure_correction", true), PRESSURE_CORRECTION, NULL, climateSensorCycle) || saved;
  saved = saveInt(request->getParam("weather_min_temp", true), WEATHER_MIN_TEMP) || saved;
  saved = saveInt(request->getParam("weather_max_temp", true), WEATHER_MAX_TEMP) || saved;
  saved = saveInt(request->getParam("radiation_max", true), RADIATION_MAX) || saved;
  saved = saveInt(request->getParam("button_mode", true), BUTTON_1_MODE) || saved;
  saved = saveInt(request->getParam("button2_mode", true), BUTTON_2_MODE) || saved;
  saved = saveInt(request->getParam("button_mode_long", true), BUTTON_1_MODE_LONG) || saved;
  saved = saveInt(request->getParam("button2_mode_long", true), BUTTON_2_MODE_LONG) || saved;
  saved = saveInt(request->getParam("kyiv_district_mode", true), KYIV_DISTRICT_MODE, NULL, initLedMapping) || saved;
  saved = saveInt(request->getParam("day_start", true), DAY_START) || saved;
  saved = saveInt(request->getParam("night_start", true), NIGHT_START) || saved;
  saved = saveBool(request->getParam("home_alert_time", true), "home_alert_time", HOME_ALERT_TIME, saveShowHomeAlarmTime) || saved;
  saved = saveInt(request->getParam("alarms_notify_mode", true), ALARMS_NOTIFY_MODE) || saved;
  saved = saveBool(request->getParam("enable_explosions", true), "enable_explosions", ENABLE_EXPLOSIONS) || saved;
  saved = saveBool(request->getParam("enable_missiles", true), "enable_missiles", ENABLE_MISSILES) || saved;
  saved = saveBool(request->getParam("enable_drones", true), "enable_drones", ENABLE_DRONES) || saved;
  saved = saveBool(request->getParam("enable_kabs", true), "enable_kabs", ENABLE_KABS) || saved;
  saved = saveInt(request->getParam("alert_on_time", true), ALERT_ON_TIME) || saved;
  saved = saveInt(request->getParam("alert_off_time", true), ALERT_OFF_TIME) || saved;
  saved = saveInt(request->getParam("explosion_time", true), EXPLOSION_TIME) || saved;
  saved = saveInt(request->getParam("critical_notifications_display_time", true), CRITICAL_NOTIFICATIONS_DISPLAY_TIME) || saved;
  saved = saveBool(request->getParam("enable_critical_notifications", true), "enable_critical_notifications", ENABLE_CRITICAL_NOTIFICATIONS) || saved;
  saved = saveInt(request->getParam("alert_blink_time", true), ALERT_BLINK_TIME) || saved;
  saved = saveInt(request->getParam("alarms_auto_switch", true), ALARMS_AUTO_SWITCH, saveAutoAlarmMode) || saved;
  saved = saveBool(request->getParam("service_diodes_mode", true), "service_diodes_mode", SERVICE_DIODES_MODE, NULL, checkServicePins) || saved;
  saved = saveBool(request->getParam("min_of_silence", true), "min_of_silence", MIN_OF_SILENCE) || saved;
  saved = saveBool(request->getParam("invert_display", true), "invert_display", INVERT_DISPLAY, NULL, updateInvertDisplayMode) || saved;
  saved = saveInt(request->getParam("time_zone", true), TIME_ZONE, NULL, []() {
    timeClient.setTimeZone(settings.getInt(TIME_ZONE));
  }) || saved;

  if (request->hasParam("color_lamp", true)) {
    int selectedHue = request->getParam("color_lamp", true)->value().toInt();
    RGBColor rgb = hue2rgb(selectedHue);
    saved = saveLampRgb(rgb.r, rgb.g, rgb.b) || saved;
  }

  request->send(redirectResponse(request, "/modes", saved));
}

void handleSaveSounds(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveBool(request->getParam("sound_on_min_of_sl", true), "sound_on_min_of_sl", SOUND_ON_MIN_OF_SL) || saved;
  saved = saveBool(request->getParam("sound_on_alert", true), "sound_on_alert", SOUND_ON_ALERT) || saved;
  saved = saveInt(request->getParam("melody_on_alert", true), MELODY_ON_ALERT) || saved;
  saved = saveInt(request->getParam("track_on_alert", true), TRACK_ON_ALERT) || saved;
  saved = saveBool(request->getParam("sound_on_alert_end", true), "sound_on_alert_end", SOUND_ON_ALERT_END) || saved;
  saved = saveInt(request->getParam("melody_on_alert_end", true), MELODY_ON_ALERT_END) || saved;
  saved = saveInt(request->getParam("track_on_alert_end", true), TRACK_ON_ALERT_END) || saved;
  saved = saveBool(request->getParam("sound_on_explosion", true), "sound_on_explosion", SOUND_ON_EXPLOSION) || saved;
  saved = saveInt(request->getParam("melody_on_explosion", true), MELODY_ON_EXPLOSION) || saved;
  saved = saveInt(request->getParam("track_on_explosion", true), TRACK_ON_EXPLOSION) || saved;
  saved = saveBool(request->getParam("sound_on_critical_mig", true), "sound_on_critical_mig", SOUND_ON_CRITICAL_MIG) || saved;
  saved = saveInt(request->getParam("melody_on_critical_mig", true), MELODY_ON_CRITICAL_MIG) || saved;
  saved = saveInt(request->getParam("track_on_critical_mig", true), TRACK_ON_CRITICAL_MIG) || saved;
  saved = saveBool(request->getParam("sound_on_critical_strategic", true), "sound_on_critical_strategic", SOUND_ON_CRITICAL_STRATEGIC) || saved;
  saved = saveInt(request->getParam("melody_on_critical_strategic", true), MELODY_ON_CRITICAL_STRATEGIC) || saved;
  saved = saveInt(request->getParam("track_on_critical_strategic", true), TRACK_ON_CRITICAL_STRATEGIC) || saved;
  saved = saveBool(request->getParam("sound_on_critical_mig_missiles", true), "sound_on_critical_mig_missiles", SOUND_ON_CRITICAL_MIG_MISSILES) || saved;
  saved = saveInt(request->getParam("melody_on_critical_mig_missiles", true), MELODY_ON_CRITICAL_MIG_MISSILES) || saved;
  saved = saveInt(request->getParam("track_on_critical_mig_missiles", true), TRACK_ON_CRITICAL_MIG_MISSILES) || saved;
  saved = saveBool(request->getParam("sound_on_critical_ballistic_missiles", true), "sound_on_critical_ballistic_missiles", SOUND_ON_CRITICAL_BALLISTIC_MISSILES) || saved;
  saved = saveInt(request->getParam("melody_on_critical_ballistic_missiles", true), MELODY_ON_CRITICAL_BALLISTIC_MISSILES) || saved;
  saved = saveInt(request->getParam("track_on_critical_ballistic_missiles", true), TRACK_ON_CRITICAL_BALLISTIC_MISSILES) || saved;
  saved = saveBool(request->getParam("sound_on_critical_strategic_missiles", true), "sound_on_critical_strategic_missiles", SOUND_ON_CRITICAL_STRATEGIC_MISSILES) || saved;
  saved = saveInt(request->getParam("melody_on_critical_strategic_missiles", true), MELODY_ON_CRITICAL_STRATEGIC_MISSILES) || saved;
  saved = saveInt(request->getParam("track_on_critical_strategic_missiles", true), TRACK_ON_CRITICAL_STRATEGIC_MISSILES) || saved;
  saved = saveBool(request->getParam("sound_on_every_hour", true), "sound_on_every_hour", SOUND_ON_EVERY_HOUR) || saved;
  saved = saveBool(request->getParam("sound_on_button_click", true), "sound_on_button_click", SOUND_ON_BUTTON_CLICK) || saved;
  saved = saveBool(request->getParam("mute_sound_on_night", true), "mute_sound_on_night", MUTE_SOUND_ON_NIGHT) || saved;
  saved = saveBool(request->getParam("ignore_mute_on_alert", true), "ignore_mute_on_alert",IGNORE_MUTE_ON_ALERT) || saved;
  saved = saveInt(request->getParam("melody_volume_day", true), MELODY_VOLUME_DAY, NULL, []() {
        setCurrentVolume(settings.getInt(MELODY_VOLUME_DAY), MELODY_VOLUME_DAY);
      }) || saved;
  saved = saveInt(request->getParam("melody_volume_night", true), MELODY_VOLUME_NIGHT, NULL, []() {
        setCurrentVolume(settings.getInt(MELODY_VOLUME_NIGHT), MELODY_VOLUME_NIGHT);
      }) || saved;

  request->send(redirectResponse(request, "/sounds", saved));
}

void handleRefreshTelemetry(AsyncWebServerRequest* request) {
  request->send(redirectResponse(request, "/telemetry", false));
}

void handleSaveDev(AsyncWebServerRequest* request) {
  bool reboot = false;
  reboot = saveInt(request->getParam("legacy", true), LEGACY) || reboot;
  reboot = saveInt(request->getParam("display_height", true), DISPLAY_HEIGHT) || reboot;
  reboot = saveInt(request->getParam("display_model", true), DISPLAY_MODEL) || reboot;
  reboot = saveString(request->getParam("ha_brokeraddress", true), HA_BROKER_ADDRESS) || reboot;
  reboot = saveInt(request->getParam("ha_mqttport", true), HA_MQTT_PORT) || reboot;
  reboot = saveString(request->getParam("ha_mqttuser", true), HA_MQTT_USER) || reboot;
  reboot = saveString(request->getParam("ha_mqttpassword", true), HA_MQTT_PASSWORD) || reboot;
  reboot = saveString(request->getParam("devicename", true), DEVICE_NAME) || reboot;
  reboot = saveString(request->getParam("devicedescription", true), DEVICE_DESCRIPTION) || reboot;
  reboot = saveString(request->getParam("broadcastname", true), BROADCAST_NAME) || reboot;
  reboot = saveString(request->getParam("serverhost", true), WS_SERVER_HOST) || reboot;
  reboot = saveString(request->getParam("ntphost", true), NTP_HOST) || reboot;
  reboot = saveInt(request->getParam("websocket_port", true), WS_SERVER_PORT) || reboot;
  reboot = saveInt(request->getParam("updateport", true), UPDATE_SERVER_PORT) || reboot;
  reboot = saveInt(request->getParam("pixelpin", true), MAIN_LED_PIN) || reboot;
  reboot = saveInt(request->getParam("bg_pixelpin", true), BG_LED_PIN) || reboot;
  reboot = saveInt(request->getParam("bg_pixelcount", true), BG_LED_COUNT) || reboot;
  reboot = saveInt(request->getParam("buttonpin", true), BUTTON_1_PIN) || reboot;
  reboot = saveInt(request->getParam("button2pin", true), BUTTON_2_PIN) || reboot;
  reboot = saveBool(request->getParam("use_touch_button1", true), "use_touch_button1", USE_TOUCH_BUTTON_1) || reboot;
  reboot = saveBool(request->getParam("use_touch_button2", true), "use_touch_button2", USE_TOUCH_BUTTON_2) || reboot;
  reboot = saveInt(request->getParam("alert_clear_pin_mode", true), ALERT_CLEAR_PIN_MODE, NULL, disableAlertAndClearPins) || reboot;
  reboot = saveInt(request->getParam("alertpin", true), ALERT_PIN) || reboot;
  reboot = saveInt(request->getParam("clearpin", true), CLEAR_PIN) || reboot;
  reboot = saveFloat(request->getParam("alert_clear_pin_time", true), ALERT_CLEAR_PIN_TIME, NULL, disableAlertAndClearPins) || reboot;
  reboot = saveInt(request->getParam("lightpin", true), LIGHT_SENSOR_PIN) || reboot;
  reboot = saveInt(request->getParam("buzzerpin", true), BUZZER_PIN) || reboot;
  reboot = saveInt(request->getParam("dfrxpin", true), DF_RX_PIN) || reboot;
  reboot = saveInt(request->getParam("dftxpin", true), DF_TX_PIN) || reboot;

  if (reboot) {
    rebootDevice(3000, true);
  }
  request->send(redirectResponse(request, "/dev", false, reboot));
}

void handleBackup(AsyncWebServerRequest* request) {
  AsyncResponseStream* response = request->beginResponseStream("application/json");
  settings.getSettingsBackup(response, VERSION, chipID, timeClient.unixToString("DD.MM.YYYY hh:mm:ss").c_str());
  char filenameHeader[65];
  sprintf(filenameHeader, "attachment; filename=\"jaam_backup_%s.json\"", timeClient.unixToString("YYYY.MM.DD_hh-mm-ss").c_str());
  response->addHeader("Content-Disposition", filenameHeader);
  response->setCode(200);
  request->send(response);
}

StreamString jsonBody;

void handleRestoreBody(AsyncWebServerRequest *request, String filename, size_t index, uint8_t *data, size_t len, bool final) {
  LOG.println("Received restore json part...");
  LOG.printf("Filename: %s\n", filename.c_str());
  size_t totalSize = request->contentLength();
  LOG.printf("File size: %d\n", totalSize);
  LOG.printf("Part Size: %d\n", len);
  if (totalSize > MAX_JSON_SIZE) {
    LOG.println("File size is too big!");
    return;
  }
  jsonBody.write(data, len);
}

void handleRestore(AsyncWebServerRequest *request) {
  LOG.println("Restoring settings...");
  const char* jsonString = jsonBody.c_str();
  LOG.printf("JSON to restore: %s\n", jsonString);
  bool restored = settings.restoreSettingsBackup(jsonString);
  if (restored) {
    rebootDevice(3000, true);
  }
  jsonBody.clear();
  LOG.printf("Setting restored: %s\n", restored ? "true" : "false");
  request->send(redirectResponse(request, "/dev", false, false, restored, !restored));
}

#if FW_UPDATE_ENABLED
void handleSaveFirmware(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveBool(request->getParam("new_fw_notification", true), "new_fw_notification", NEW_FW_NOTIFICATION) || saved;
  saved = saveInt(request->getParam("fw_update_channel", true), FW_UPDATE_CHANNEL, NULL, saveLatestFirmware) || saved;

  request->send(redirectResponse(request, "/firmware", saved));
}
#endif

#if BUZZER_ENABLED
void handlePlayTestSound(AsyncWebServerRequest* request) {
  if (isBuzzerEnabled()) {
    int soundId = request->getParam("id", false)->value().toInt();
    if (soundId < 0 || soundId >= MELODIES_COUNT) {
      request->send(400, "text/plain", "Invalid sound ID");
      return;
    }
    playMelody(MELODIES[soundId]);
    showServiceMessage(getNameById(MELODY_NAMES, soundId, MELODIES_COUNT), "Мелодія");
    request->send(200, "text/plain", "Test sound played!");
  }
}
#endif

#if DFPLAYER_PRO_ENABLED
void handlePlayTestTrackById(AsyncWebServerRequest* request) {
  if (dfPlayerConnected) {
    if (request->hasParam("id")) {
      int trackId = request->getParam("id", false)->value().toInt();
      if (trackId < 0 || trackId >= totalFiles) {
        request->send(400, "text/plain", "Invalid track ID");
        return;
      }
      playTrack(getTrackById(trackId));
      showServiceMessage(getNameById(dynamicTrackNames, trackId, totalFiles), "Трек");
      request->send(200, "text/plain", "Test track played!");
    } else {
      request->send(400, "text/plain", "Missing 'id' parameter");
    }
  } else {
    request->send(503, "text/plain", "DFPlayer not available");
  }
}

void handlePlayTestTrackByFileName(AsyncWebServerRequest* request) {
  if (dfPlayerConnected) {
    if (request->hasParam("name")) {
      String trackName = request->getParam("name")->value();
      playTrack(trackName);
      showServiceMessage(trackName.c_str(), "Трек");
      delay(2000);
      request->send(200, "text/plain", "Test track played!");
    } else {
      request->send(400, "text/plain", "Missing 'name' parameter");
    }
  } else {
    request->send(503, "text/plain", "DFPlayer not available");
  }
}
#endif

LoggingMiddleware loggerMiddleware;

void setupRouting() {
  LOG.println("Init WebServer");
  loggerMiddleware.setOutput(LOG);
  webserver.addMiddleware(&loggerMiddleware);
  webserver.on("/", HTTP_GET, handleRoot);
  webserver.on("/brightness", HTTP_GET, handleBrightness);
  webserver.on("/saveBrightness", HTTP_POST, handleSaveBrightness);
  webserver.on("/colors", HTTP_GET, handleColors);
  webserver.on("/saveColors", HTTP_POST, handleSaveColors);
  webserver.on("/modes", HTTP_GET, handleModes);
  webserver.on("/saveModes", HTTP_POST, handleSaveModes);
#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
  if (isBuzzerEnabled() || dfPlayerConnected) {
    webserver.on("/sounds", HTTP_GET, handleSounds);
    webserver.on("/saveSounds", HTTP_POST, handleSaveSounds);
  }
#endif
  webserver.on("/telemetry", HTTP_GET, handleTelemetry);
  webserver.on("/refreshTelemetry", HTTP_POST, handleRefreshTelemetry);
  webserver.on("/dev", HTTP_GET, handleDev);
  webserver.on("/saveDev", HTTP_POST, handleSaveDev);
#if FW_UPDATE_ENABLED
  webserver.on("/firmware", HTTP_GET, handleFirmware);
  webserver.on("/saveFirmware", HTTP_POST, handleSaveFirmware);
  webserver.on("/update", HTTP_POST, handleUpdate);
#endif
#if BUZZER_ENABLED
  if (isBuzzerEnabled()) {
    webserver.on("/playTestSound", HTTP_GET, handlePlayTestSound);
  }
#endif
#if DFPLAYER_PRO_ENABLED
  if (dfPlayerConnected) {
    webserver.on("/playTestTrackById", HTTP_GET, handlePlayTestTrackById);
    webserver.on("/playTestTrackByFileName", HTTP_GET, handlePlayTestTrackByFileName);
  }
#endif
  webserver.on("/backup", HTTP_GET, handleBackup);
  webserver.on("/restore", HTTP_POST, handleRestore, handleRestoreBody, NULL);
  webserver.begin();
  LOG.println("Webportal running");
}
//--Web server end

//--Service messages start
void uptime() {
  int   uptimeValue   = millis() / 1000;
  fillUptime(uptimeValue, uptimeChar);

  float totalHeapSize = ESP.getHeapSize() / 1024.0;
  freeHeapSize  = ESP.getFreeHeap() / 1024.0;
  usedHeapSize  = totalHeapSize - freeHeapSize;
  cpuTemp       = temperatureRead();
  wifiSignal    = WiFi.RSSI();

  ha.setUptime(uptimeValue);
  ha.setWifiSignal(wifiSignal);
  ha.setFreeMemory(freeHeapSize);
  ha.setUsedMemory(usedHeapSize);
  ha.setCpuTemp(cpuTemp);
}

void connectStatuses() {
  LOG.print("Map API status: ");
  apiConnected = client_websocket.available();
  LOG.println(apiConnected ? "Connected" : "Disconnected");
  haConnected = false;
  if (ha.isHaAvailable()) {
    haConnected = ha.isMqttConnected();
    LOG.print("Home Assistant MQTT status: ");
    LOG.println(haConnected ? "Connected" : "Disconnected");
    if (haConnected) {
      servicePin(HA, HIGH, false);
    } else {
      servicePin(HA, LOW, false);
    }
    ha.setMapApiConnect(apiConnected);
  }
}

//--Service messages end

static JsonDocument parseJson(const char* payload) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload);
  if (error) {
    LOG.printf("Deserialization error: $s\n", error.f_str());
    return doc;
  } else {
    return doc;
  }
}

#if FW_UPDATE_ENABLED
static void fillBinList(JsonDocument data, const char* payloadKey, char* binsList[], int *binsCount) {
  JsonArray arr = data[payloadKey].as<JsonArray>();
  *binsCount = min(static_cast<int>(arr.size()), MAX_BINS_LIST_SIZE);
  for (int i = 0; i < *binsCount; i++) {
    const char* filename = arr[i].as<const char*>();
    binsList[i] = new char[strlen(filename)];
    strcpy(binsList[i], filename);
  }
  LOG.printf("Successfully parsed %s list. List size: %d\n", payloadKey, *binsCount);
}
#endif

void alertPinCycle() {
  if (isAlertPinEnabled() && settings.getInt(ALERT_CLEAR_PIN_MODE) == 0) {
    if (alarmNow && digitalRead(settings.getInt(ALERT_PIN)) == LOW) {
      setAlertPin();
    }
    if (!alarmNow && digitalRead(settings.getInt(ALERT_PIN)) == HIGH) {
      disableAlertPin();
    }
  }
  if (isAlertPinEnabled() && settings.getInt(ALERT_CLEAR_PIN_MODE) == 1 && alarmNow && !pinAlarmNow) {
    pinAlarmNow = true;
    if (!isFirstDataFetchCompleted) {
      LOG.println("Do not set alert pin on first data fetch");
      return;
    }
    setAlertPin();
    long timeoutMs = settings.getFloat(ALERT_CLEAR_PIN_TIME) * 1000;
    LOG.printf("Alert pin will be disabled in %d ms\n", timeoutMs);
    asyncEngine.setTimeout(disableAlertPin, timeoutMs);
  }
  if (isClearPinEnabled() && settings.getInt(ALERT_CLEAR_PIN_MODE) == 1 && !alarmNow && pinAlarmNow) {
    pinAlarmNow = false;
    if (!isFirstDataFetchCompleted) {
      LOG.println("Do not set clear pin on first data fetch");
      return;
    }
    setClearPin();
    long timeoutMs = settings.getFloat(ALERT_CLEAR_PIN_TIME) * 1000;
    LOG.printf("Clear pin will be disabled in %d ms\n", timeoutMs);
    asyncEngine.setTimeout(disableClearPin, timeoutMs);
  }
}

void checkHomeDistrictAlerts() {
  int ledStatus = id_to_alerts[settings.getInt(HOME_DISTRICT)].first;
  long localHomeExplosions = id_to_explosions_notifications[settings.getInt(HOME_DISTRICT)];
  bool localAlarmNow = ledStatus == 1;
  bool localAlarmDronesNow = isLocalAlarmNow(
    id_to_drones[settings.getInt(HOME_DISTRICT)],
    id_to_drones_notifications[settings.getInt(HOME_DISTRICT)],
    timeClient.unixGMT(),
    settings.getInt(EXPLOSION_TIME) * 60
  );
  bool localAlarmMissilesNow = isLocalAlarmNow(
    id_to_missiles[settings.getInt(HOME_DISTRICT)],
    id_to_missiles_notifications[settings.getInt(HOME_DISTRICT)],
    timeClient.unixGMT(),
    settings.getInt(EXPLOSION_TIME) * 60
  );
  bool localAlarmKabsNow = isLocalAlarmNow(
    id_to_kabs[settings.getInt(HOME_DISTRICT)],
    id_to_kabs_notifications[settings.getInt(HOME_DISTRICT)],
    timeClient.unixGMT(),
    settings.getInt(EXPLOSION_TIME) * 60
  );
  const char* districtName = getNameById(DISTRICTS, settings.getInt(HOME_DISTRICT), DISTRICTS_COUNT);
  if (localAlarmNow != alarmNow) {
    alarmNow = localAlarmNow;
    if (alarmNow && needToPlaySound(ALERT_ON)) playMelody(ALERT_ON);
    if (!alarmNow && needToPlaySound(ALERT_OFF)) playMelody(ALERT_OFF);

    alertPinCycle();

    if (alarmNow) {
      showServiceMessage("Тривога!", districtName, 5000);
    } else {
      showServiceMessage("Відбій!", districtName, 5000);
    }
    ha.setAlarmAtHome(alarmNow);
  }
  if (settings.getBool(ENABLE_EXPLOSIONS) && localHomeExplosions != homeExplosionTime) {
    homeExplosionTime = localHomeExplosions;
    if (homeExplosionTime > 0 && timeClient.unixGMT() - homeExplosionTime < settings.getInt(EXPLOSION_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
      showServiceMessage("Вибухи!", districtName, settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
      if (needToPlaySound(EXPLOSIONS)) playMelody(EXPLOSIONS);
    }
  }
  if (alarmKabsNow != localAlarmKabsNow) {
    alarmKabsNow = localAlarmKabsNow;
    if (alarmKabsNow && settings.getBool(ENABLE_KABS)) {
      showServiceMessage("КАБ!", districtName, settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
      if (needToPlaySound(EXPLOSIONS)) playMelody(EXPLOSIONS);
    }
  }
  if (alarmMissilesNow != localAlarmMissilesNow) {
    alarmMissilesNow = localAlarmMissilesNow;
    if (alarmMissilesNow && settings.getBool(ENABLE_MISSILES)) {
      showServiceMessage("Ракети!", districtName, settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
      if (needToPlaySound(EXPLOSIONS)) playMelody(EXPLOSIONS);
    }
  }
  if (alarmDronesNow != localAlarmDronesNow) {
    alarmDronesNow = localAlarmDronesNow;
    if (alarmDronesNow && settings.getBool(ENABLE_DRONES)) {
      showServiceMessage("БПЛА!", districtName, settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
      if (needToPlaySound(EXPLOSIONS)) playMelody(EXPLOSIONS);
    }
  }
}

void processGlobalNotifications(const JsonDocument& data) {
  if (settings.getBool(ENABLE_CRITICAL_NOTIFICATIONS)) {
    if (GlobalNotifications[IS_MIG] != data["mig"]) {
      GlobalNotifications[IS_MIG] = data["mig"].as<bool>();
      if (GlobalNotifications[IS_MIG] > 0) {
        showServiceMessage("МІГ-31к", "Критичне сповіщення!", settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
        if (needToPlaySound(CRITICAL_MIG)) playMelody(CRITICAL_MIG);
      }
    }
    if (GlobalNotifications[IS_STRATEGIC] != data["strategic"]) {
      GlobalNotifications[IS_STRATEGIC] = data["strategic"].as<bool>();
      if (GlobalNotifications[IS_STRATEGIC] > 0) {
        showServiceMessage("Стратегічна авіація", "Критичне сповіщення!", settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
        if (needToPlaySound(CRITICAL_STRATEGIC)) playMelody(CRITICAL_STRATEGIC);
      }
    }
    if (GlobalNotifications[IS_MIG_MISSILES] != data["mig_missiles"]) {
      GlobalNotifications[IS_MIG_MISSILES] = data["mig_missiles"].as<bool>();
      if (GlobalNotifications[IS_MIG_MISSILES] > 0) {
        showServiceMessage("Кинджал!", "Критичне сповіщення!", settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
        if (needToPlaySound(CRITICAL_MIG_MISSILES)) playMelody(CRITICAL_MIG_MISSILES);
      }
    }
    if (GlobalNotifications[IS_STRATEGIC_MISSILES] != data["strategic_missiles"]) {
      GlobalNotifications[IS_STRATEGIC_MISSILES] = data["strategic_missiles"].as<bool>();
      if (GlobalNotifications[IS_STRATEGIC_MISSILES] > 0) {
        showServiceMessage("Крилаті ракети!", "Критичне сповіщення!", settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
        if (needToPlaySound(CRITICAL_STRATEGIC_MISSILES)) playMelody(CRITICAL_STRATEGIC_MISSILES);
      }
    }
    if (GlobalNotifications[IS_BALLISTIC_MISSILES] != data["ballistic_missiles"]) {
      GlobalNotifications[IS_BALLISTIC_MISSILES] = data["ballistic_missiles"].as<bool>();
      if (GlobalNotifications[IS_BALLISTIC_MISSILES] > 0) {
        showServiceMessage("Балістика!", "Критичне сповіщення!", settings.getInt(CRITICAL_NOTIFICATIONS_DISPLAY_TIME) * 1000);
        if (needToPlaySound(CRITICAL_BALLISTIC_MISSILES)) playMelody(CRITICAL_BALLISTIC_MISSILES);
      }
    }
  }
}

//--Websocket process start

void onMessageCallback(WebsocketsMessage message) {
  LOG.print("Got Message: ");
  LOG.println(message.data());
  JsonDocument data = parseJson(message.data().c_str());
  String payload = data["payload"];
  if (!payload.isEmpty()) {
    if (payload == "ping") {
      LOG.println("Heartbeat from server");
      websocketLastPingTime = millis();
    } else if (payload == "alerts") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_alerts[mapIndexToRegionId(i)] = std::make_pair((uint8_t) data["alerts"][i][0], (long) data["alerts"][i][1]);
      }
      LOG.println("Successfully parsed alerts data");
      remapAlerts();
    } else if (payload == "weather") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_weather[mapIndexToRegionId(i)] = data["weather"][i];
      }
      LOG.println("Successfully parsed weather data");
      remapWeather();
      ha.setHomeTemperature(id_to_weather[settings.getInt(HOME_DISTRICT) ]);
    } else if (payload == "explosions") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_explosions_notifications[mapIndexToRegionId(i)] = data["explosions"][i];
      }
      LOG.println("Successfully parsed explosions notifications data");
      remapExplosionsNotifications();
    } else if (payload == "missiles") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_missiles_notifications[mapIndexToRegionId(i)] = data["missiles"][i];
      }
      LOG.println("Successfully parsed missiles notifications data");
      remapMissilesNotifications();
    } else if (payload == "missiles2") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_missiles[mapIndexToRegionId(i)] = std::make_pair((uint8_t) data["missiles"][i][0], (long) data["missiles"][i][1]);
      }
      LOG.println("Successfully parsed missiles data");
      remapMissiles();
    } else if (payload == "drones") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_drones_notifications[mapIndexToRegionId(i)] = data["drones"][i];
      }
      LOG.println("Successfully parsed drones notifications data");
      remapDronesNotifications();
    } else if (payload == "drones2") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_drones[mapIndexToRegionId(i)] = std::make_pair((uint8_t) data["drones"][i][0], (long) data["drones"][i][1]);
      }
      LOG.println("Successfully parsed drones data");
      remapDrones();
    } else if (payload == "kabs") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_kabs_notifications[mapIndexToRegionId(i)] = data["kabs"][i];
      }
      LOG.println("Successfully parsed kabs notifications data");
      remapKabsNotifications();
    } else if (payload == "kabs2") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_kabs[mapIndexToRegionId(i)] = std::make_pair((uint8_t) data["kabs"][i][0], (long) data["kabs"][i][1]);
      }
      LOG.println("Successfully parsed kabs data");
      remapKabs();
    } else if (payload == "energy") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_energy[mapIndexToRegionId(i)] = std::make_pair((uint8_t) data["energy"][i][0], (long) data["energy"][i][1]);
      }
      LOG.println("Successfully parsed energy data");
      remapEnergy();
      ha.setHomeEnergy(id_to_energy[settings.getInt(HOME_DISTRICT)].first);
    } else if (payload == "radiation") {
      for (int i = 0; i < MAIN_LEDS_COUNT; ++i) {
        id_to_radiation[mapIndexToRegionId(i)] = data["radiation"][i];
      }
      LOG.println("Successfully parsed radiation data");
      remapRadiation();
      ha.setHomeRadiation(id_to_radiation[settings.getInt(HOME_DISTRICT)]);
    } else if (payload == "global_notifications") {
      processGlobalNotifications(data["global_notifications"]);
      LOG.println("Successfully parsed global notifications");
#if FW_UPDATE_ENABLED
    } else if (payload == "bins") {
      fillBinList(data, "bins", bin_list, &binsCount);
      saveLatestFirmware();
    } else if (payload == "test_bins") {
      fillBinList(data, "test_bins", test_bin_list, &testBinsCount);
      saveLatestFirmware();
#endif
    }
  }
  checkHomeDistrictAlerts();
  alertPinCycle();
  isFirstDataFetchCompleted = true;
}

void onEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    apiConnected = true;
    LOG.println("connnection opened");
    servicePin(DATA, HIGH, false);
    websocketLastPingTime = millis();
    ha.setMapApiConnect(apiConnected);
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    apiConnected = false;
    LOG.println("connnection closed");
    servicePin(DATA, LOW, false);
    ha.setMapApiConnect(apiConnected);
  } else if (event == WebsocketsEvent::GotPing) {
    LOG.println("websocket ping");
    websocketLastPingTime = millis();
  } else if (event == WebsocketsEvent::GotPong) {
    LOG.println("websocket pong");
  }
}

void socketConnect() {
  LOG.println("connection start...");
  showServiceMessage("підключення...", "Сервер даних");
  client_websocket.onMessage(onMessageCallback);
  client_websocket.onEvent(onEventsCallback);
  long startTime = millis();
  char webSocketUrl[100];
  sprintf(
    webSocketUrl,
    "ws://%s:%d/data_v4",
    settings.getString(WS_SERVER_HOST),
    settings.getInt(WS_SERVER_PORT)
  );
  LOG.println(webSocketUrl);
  client_websocket.connect(webSocketUrl);
  if (client_websocket.available()) {
    LOG.print("connection time - ");
    LOG.print(millis() - startTime);
    LOG.println("ms");
    char chipIdInfo[25];
    sprintf(chipIdInfo, "chip_id:%s", chipID);
    LOG.println(chipIdInfo);
    client_websocket.send(chipIdInfo);
    char firmwareInfo[100];
    sprintf(firmwareInfo, "firmware:%s_%s", currentFwVersion, settings.getString(ID));
    LOG.println(firmwareInfo);
    client_websocket.send(firmwareInfo);

    char userInfo[250];
    JsonDocument userInfoJson;
    userInfoJson["legacy"] = settings.getInt(LEGACY);
    userInfoJson["kyiv_mode"] = settings.getInt(KYIV_DISTRICT_MODE);
    userInfoJson["display_model"] = display.getDisplayModel();
    if (display.isDisplayAvailable()) userInfoJson["display_height"] = settings.getInt(DISPLAY_HEIGHT);
    userInfoJson["bh1750"] = lightSensor.isLightSensorAvailable();
    userInfoJson["bme280"] = climate.isBME280Available();
    userInfoJson["bmp280"] = climate.isBMP280Available();
    userInfoJson["sht2x"] = climate.isSHT2XAvailable();
    userInfoJson["sht3x"] = climate.isSHT3XAvailable();
    userInfoJson["ha"] = ha.isHaAvailable();
    sprintf(userInfo, "user_info:%s", userInfoJson.as<String>().c_str());
    LOG.println(userInfo);
    client_websocket.send(userInfo);
    client_websocket.ping();
    websocketReconnect = false;
    showServiceMessage("підключено!", "Сервер даних", 3000);
  } else {
    showServiceMessage("недоступний", "Сервер даних", 3000);
  }
}

void websocketProcess() {
  if (millis() - websocketLastPingTime > settings.getInt(WS_ALERT_TIME)) {
    websocketReconnect = true;
  }
  if (millis() - websocketLastPingTime > settings.getInt(WS_REBOOT_TIME)) {
    rebootDevice(3000, true);
  }
  if (!client_websocket.available() or websocketReconnect) {
    LOG.println("Reconnecting...");
    socketConnect();
  }
}
//--Websocket process end

//--Map processing start

CRGB processAlarms(
  int alert_status, long alert_time, 
  int missile_status, long missile_time, 
  int drone_status, long drone_time, 
  int kab_status, long kab_time, 
  int explosion_notification_time, 
  int missiles_notification_time, 
  int drones_notification_time, 
  int kabs_notification_time, 
  int position, 
  float alertBrightness, 
  float notificationBrightness, 
  float extrafastBrightness, 
  bool isBgStrip
) {

  CRGB hue;
  float localBrightnessAlert = isBgStrip ? settings.getInt(BRIGHTNESS_BG) / 100.0f : settings.getInt(BRIGHTNESS_ALERT) / 100.0f;
  float localBrightnessClear = isBgStrip ? settings.getInt(BRIGHTNESS_BG) / 100.0f : settings.getInt(BRIGHTNESS_CLEAR) / 100.0f;
  float localBrightnessHomeDistrict = isBgStrip ? settings.getInt(BRIGHTNESS_BG) / 100.0f : settings.getInt(BRIGHTNESS_HOME_DISTRICT) / 100.0f;

  int localDistrictLedsCount = homeDistrictMapping.first;
  int* localDistrictLed = homeDistrictMapping.second;
  int colorSwitch;

  unix_t currentTime = timeClient.unixGMT();

  // explosions has highest priority
  if (settings.getBool(ENABLE_EXPLOSIONS) && explosion_notification_time > 0 && currentTime - explosion_notification_time < settings.getInt(EXPLOSION_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
    colorSwitch = settings.getInt(COLOR_EXPLOSION);
    hue = fromHue(colorSwitch, notificationBrightness * settings.getInt(BRIGHTNESS_EXPLOSION));
    return hue;
  }

  // kabs notifications has second priority
  if (settings.getBool(ENABLE_KABS) && kabs_notification_time > 0 && currentTime - kabs_notification_time < settings.getInt(EXPLOSION_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
    colorSwitch = settings.getInt(COLOR_KABS);
    hue = fromHue(colorSwitch, notificationBrightness * settings.getInt(BRIGHTNESS_EXPLOSION));
    return hue;
  }

  // kabs has third priority
  if (settings.getBool(ENABLE_KABS)) {
    switch (kab_status) {
      case ALERT:
        if (currentTime - kab_time < settings.getInt(ALERT_ON_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
          colorSwitch = settings.getInt(COLOR_KABS);
          hue = fromHue(colorSwitch, notificationBrightness * settings.getInt(BRIGHTNESS_EXPLOSION));
        } else {
          colorSwitch = settings.getInt(COLOR_KABS);
          hue = fromHue(colorSwitch, settings.getInt(CURRENT_BRIGHTNESS) * localBrightnessAlert);
        }
        return hue;
    }
  }

  // missiles notifications has fouth priority
  if (settings.getBool(ENABLE_MISSILES) && missiles_notification_time > 0 && currentTime - missiles_notification_time < settings.getInt(EXPLOSION_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
    colorSwitch = settings.getInt(COLOR_MISSILES);
    hue = fromHue(colorSwitch, notificationBrightness * settings.getInt(BRIGHTNESS_EXPLOSION));
    return hue;
  }

  // missiles  has fifth priority
  if (settings.getBool(ENABLE_MISSILES) && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
    switch (missile_status) {
      case ALERT:
        if (currentTime - missile_time < settings.getInt(EXPLOSION_TIME) * 60) {
          colorSwitch = settings.getInt(COLOR_MISSILES);
          hue = fromHue(colorSwitch, notificationBrightness * settings.getInt(BRIGHTNESS_EXPLOSION));
        } else {
          colorSwitch = settings.getInt(COLOR_MISSILES);
          hue = fromHue(colorSwitch, settings.getInt(CURRENT_BRIGHTNESS) * localBrightnessAlert);
        }
        return hue;
    }
  }

  // drones notifications has sixth priority
  if (settings.getBool(ENABLE_DRONES) && drones_notification_time > 0 && currentTime - drones_notification_time < settings.getInt(EXPLOSION_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
    colorSwitch = settings.getInt(COLOR_DRONES);
    hue = fromHue(colorSwitch, notificationBrightness * settings.getInt(BRIGHTNESS_EXPLOSION));
    return hue;
  }

  // drones has seventh priority
  if (settings.getBool(ENABLE_DRONES) && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
    switch (drone_status) {
      case ALERT:
        if (currentTime - drone_time < settings.getInt(EXPLOSION_TIME) * 60) {
          colorSwitch = settings.getInt(COLOR_DRONES);
          hue = fromHue(colorSwitch, notificationBrightness * settings.getInt(BRIGHTNESS_EXPLOSION));
        } else {
          colorSwitch = settings.getInt(COLOR_DRONES);
          hue = fromHue(colorSwitch, settings.getInt(CURRENT_BRIGHTNESS) * localBrightnessAlert);
        }
        return hue;
    }
  }

  switch (alert_status) {
    case ALERT:
      if (currentTime - alert_time < settings.getInt(ALERT_ON_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
        colorSwitch = settings.getInt(COLOR_NEW_ALERT);
        hue = fromHue(colorSwitch, alertBrightness * settings.getInt(BRIGHTNESS_NEW_ALERT));
      } else {
        colorSwitch = settings.getInt(COLOR_ALERT);
        hue = fromHue(colorSwitch, settings.getInt(CURRENT_BRIGHTNESS) * localBrightnessAlert);
      }
      break;
    case CLEAR:
      if (currentTime - alert_time < settings.getInt(ALERT_OFF_TIME) * 60 && settings.getInt(ALARMS_NOTIFY_MODE) > 0) {
        colorSwitch = settings.getInt(COLOR_ALERT_OVER);
        hue = fromHue(colorSwitch, alertBrightness * settings.getInt(BRIGHTNESS_ALERT_OVER));
      } else {
        float localBrightness;
        if (isBgStrip && isAlertInNeighboringDistricts()) {
          colorSwitch = settings.getInt(COLOR_BG_NEIGHBOR_ALERT);
          localBrightness = localBrightnessAlert;
        } else if (isInArray(position, localDistrictLed, localDistrictLedsCount)) {
          colorSwitch = settings.getInt(COLOR_HOME_DISTRICT);
          localBrightness = localBrightnessHomeDistrict;
        } else {
          colorSwitch = settings.getInt(COLOR_CLEAR);
          localBrightness = localBrightnessClear;
        }
        hue = fromHue(colorSwitch, settings.getInt(CURRENT_BRIGHTNESS) * localBrightness);
      }
      break;
  }
  return hue;
}

// float getFadeInFadeOutBrightness(float maxBrightness, long fadeTime) {
//   float fixedMaxBrightness = (maxBrightness > 0.0f && maxBrightness < minBlinkBrightness) ? minBlinkBrightness : maxBrightness;
//   float minBrightness = fixedMaxBrightness * 0.01f;
//   int progress = micros() % (fadeTime * 1000);
//   int halfBlinkTime = fadeTime * 500;
//   float blinkBrightness;
//   if (progress < halfBlinkTime) {
//     blinkBrightness = mapf(progress, 0, halfBlinkTime, minBrightness, fixedMaxBrightness);
//   } else {
//     blinkBrightness = mapf(progress, halfBlinkTime + 1, halfBlinkTime * 2, fixedMaxBrightness, minBrightness);
//   }
//   return blinkBrightness;
// }

float getFadeInFadeOutBrightness(float maxBrightness, long fadeTime) {
  // Ensure max brightness is not below minimum threshold
  float fixedMaxBrightness = (maxBrightness > 0.0f && maxBrightness < minBlinkBrightness)
                              ? minBlinkBrightness
                              : maxBrightness;

  float minBrightness = fixedMaxBrightness * 0.01f;
  float amplitude = fixedMaxBrightness - minBrightness;

  // Current position in the cycle (from 0 to fadeTime * 1000 microseconds)
  unsigned long progress = micros() % (fadeTime * 1000);

  // Normalized progress (0.0 to 1.0)
  float t = (float)progress / (fadeTime * 1000.0f);

  // Parabolic curve: -4(x - 0.5)^2 + 1 -> ranges from 0 to 1
  float curve = -4.0f * (t - 0.5f) * (t - 0.5f) + 1.0f;

  // Scale the curve to brightness range
  float blinkBrightness = minBrightness + amplitude * curve;

  return blinkBrightness;
}

void playMinOfSilenceSound() {
  playMelody(MIN_OF_SILINCE);
}

void checkMinuteOfSilence() {
  bool localMinOfSilence = (settings.getBool(MIN_OF_SILENCE) == 1 && timeClient.hour() == 9 && timeClient.minute() == 0);
  if (localMinOfSilence != minuteOfSilence) {
    minuteOfSilence = localMinOfSilence;
    ha.setMapModeCurrent(getNameById(MAP_MODES, getCurrentMapMode(), MAP_MODES_COUNT));
    // play mos beep every 2 sec during min of silence
    if (minuteOfSilence && needToPlaySound(MIN_OF_SILINCE)) {
      clockBeepInterval = asyncEngine.setInterval(playMinOfSilenceSound, 2000); // every 2 sec
    }
    // turn off mos beep
    if (!minuteOfSilence && clockBeepInterval >= 0) {
      asyncEngine.clearInterval(clockBeepInterval);
    }
#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
    // play UA Anthem when min of silence ends
    if ((isBuzzerEnabled() || dfPlayerConnected) && !minuteOfSilence && needToPlaySound(MIN_OF_SILINCE_END)) {
      playMelody(MIN_OF_SILINCE_END);
      uaAnthemPlaying = true;
    }
#endif
  }
}

int processWeather(float temp) {
  float minTemp = settings.getInt(WEATHER_MIN_TEMP);
  float maxTemp = settings.getInt(WEATHER_MAX_TEMP);
  float normalizedValue = float(temp - minTemp) / float(maxTemp - minTemp);
  if (normalizedValue > 1) {
    normalizedValue = 1;
  }
  if (normalizedValue < 0) {
    normalizedValue = 0;
  }
  int hue = round(275 + normalizedValue * (0 - 275));
  hue %= 360;
  return hue;
}

int processRadiation(int rad) {
  float maxRad = settings.getInt(RADIATION_MAX);

  float normalizedValue = float(rad - 100) / float(maxRad - 100);

  if (normalizedValue > 1) {
    normalizedValue = 1;
  }
  if (normalizedValue < 0) {
    normalizedValue = 0;
  }

  int hue = round(180 + normalizedValue * (320 - 180));  
  hue %= 360;

  return hue;
}

int processEnergy(int status) {
  int hue = 0;
  if (status == 3) {
    hue = 100;
  } else if (status == 4) {
    hue = 30;
  } else if (status == 9) {
    hue = 15;
  }
  return hue;
}

void mapReconnect() {
  float localBrightness = getFadeInFadeOutBrightness(settings.getInt(CURRENT_BRIGHTNESS) / 200.0f, settings.getInt(ALERT_BLINK_TIME) * 1000);
  CRGB hue = fromHue(64, localBrightness * settings.getInt(CURRENT_BRIGHTNESS));
  for (uint16_t i = 0; i < 26; i++) {
    strip[i] = hue;
  }
  if (isBgStripEnabled()) {
    float brightness_factor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), fromHue(64, localBrightness * settings.getInt(CURRENT_BRIGHTNESS) * brightness_factor));
  }
  FastLED.show();
}

void mapOff() {
  fill_solid(strip, MAIN_LEDS_COUNT, CRGB::Black);
  if (isBgStripEnabled()) {
    fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), CRGB::Black);
  }
  FastLED.show();
}

void mapLamp() {
  fill_solid(strip, MAIN_LEDS_COUNT, fromRgb(settings.getInt(HA_LIGHT_R), settings.getInt(HA_LIGHT_G), settings.getInt(HA_LIGHT_B), settings.getInt(HA_LIGHT_BRIGHTNESS)));
  if (isBgStripEnabled()) {
    float brightness_factor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), fromRgb(settings.getInt(HA_LIGHT_R), settings.getInt(HA_LIGHT_G), settings.getInt(HA_LIGHT_B), settings.getInt(HA_LIGHT_BRIGHTNESS) * brightness_factor));
  }
  FastLED.show();
}

void mapAlarms() {
  float blinkBrightness = settings.getInt(CURRENT_BRIGHTNESS) / 100.0f;
  float notificationBrightness = settings.getInt(CURRENT_BRIGHTNESS) / 100.0f;
  float extrafastBrightness = settings.getInt(CURRENT_BRIGHTNESS) / 100.0f;
  if (settings.getInt(ALARMS_NOTIFY_MODE) == 2) {
    blinkBrightness = getFadeInFadeOutBrightness(blinkBrightness, settings.getInt(ALERT_BLINK_TIME) * 1000);
    notificationBrightness = getFadeInFadeOutBrightness(notificationBrightness, settings.getInt(ALERT_BLINK_TIME) * 667);
    extrafastBrightness = getFadeInFadeOutBrightness(extrafastBrightness, settings.getInt(ALERT_BLINK_TIME) * 334);
  }
  for (uint16_t i = 0; i < MAIN_LEDS_COUNT; i++) {
    strip[i] = processAlarms(
      led_to_alerts[i].first,
      led_to_alerts[i].second,
      led_to_missiles[i].first,
      led_to_missiles[i].second,
      led_to_drones[i].first,
      led_to_drones[i].second,
      led_to_kabs[i].first,
      led_to_kabs[i].second,
      led_to_explosions_notifications[i],
      led_to_missiles_notifications[i],
      led_to_drones_notifications[i],
      led_to_kabs_notifications[i],
      i,
      blinkBrightness,
      notificationBrightness,
      extrafastBrightness,
      false
    );
  }
  if (isBgStripEnabled()) {
    // same as for local district
    int localDistrictLedCount = homeDistrictMapping.first; // get count of leds in local district
    if (localDistrictLedCount <= 0) {
      // if local district led is missing, fill bg strip with black color
      fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), CRGB::Black);
    } else {
      int localDistrictLed = homeDistrictMapping.second[0]; // get first led in local district
      fill_solid(
        bg_strip,
        settings.getInt(BG_LED_COUNT),
        processAlarms(
          led_to_alerts[localDistrictLed].first,
          led_to_alerts[localDistrictLed].second,
          led_to_missiles[localDistrictLed].first,
          led_to_missiles[localDistrictLed].second,
          led_to_drones[localDistrictLed].first,
          led_to_drones[localDistrictLed].second,
          led_to_kabs[localDistrictLed].first,
          led_to_kabs[localDistrictLed].second,
          led_to_explosions_notifications[localDistrictLed],
          led_to_missiles_notifications[localDistrictLed],
          led_to_drones_notifications[localDistrictLed],
          led_to_kabs_notifications[localDistrictLed],
          localDistrictLed,
          blinkBrightness,
          notificationBrightness,
          extrafastBrightness,
          true
        )
      );
    }
  }
  FastLED.show();
}

void mapWeather() {
  for (uint16_t i = 0; i < MAIN_LEDS_COUNT; i++) {
    strip[i] = fromHue(processWeather(led_to_weather[i]), settings.getInt(CURRENT_BRIGHTNESS));
  }
  if (isBgStripEnabled()) {
    // same as for local district
    float brightness_factor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), fromHue(processWeather(id_to_weather[settings.getInt(HOME_DISTRICT) ]), settings.getInt(CURRENT_BRIGHTNESS) * brightness_factor));
  }
  FastLED.show();
}

void mapRadiation() {
  int current_brightness = settings.getInt(CURRENT_BRIGHTNESS);
  int local_home_district = settings.getInt(HOME_DISTRICT);
  for (uint16_t i = 0; i < MAIN_LEDS_COUNT; i++) {
    int brightness = 0;
    int rad = led_to_radiation[i];
    if (rad > 0) {
      brightness = current_brightness;
    }
    strip[i] = fromHue(processRadiation(led_to_radiation[i]), brightness);
  }
  if (isBgStripEnabled()) {
    // same as for local district
    float brightness_factor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), fromHue(processRadiation(id_to_radiation[local_home_district]), current_brightness * brightness_factor));
  }
  FastLED.show();
}

void mapEnergy() {
  int current_brightness = settings.getInt(CURRENT_BRIGHTNESS);
  for (uint16_t i = 0; i < MAIN_LEDS_COUNT; i++) {
    int brightness = 0;
    int hue = led_to_energy[i].first;
    if (hue > 0) {
      brightness = current_brightness;
    }
    strip[i] = fromHue(processEnergy(hue), brightness);
  }
  if (isBgStripEnabled()) {
    // same as for local district
    float brightness_factor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), fromHue(processEnergy(id_to_energy[settings.getInt(HOME_DISTRICT)].first), settings.getInt(CURRENT_BRIGHTNESS) * brightness_factor));
  }
  FastLED.show();
}

void mapFlag() {
  for (uint16_t i = 0; i < MAIN_LEDS_COUNT; i++) {
    strip[i] = fromHue(led_to_flag_color[i], settings.getInt(CURRENT_BRIGHTNESS));
  }
  if (isBgStripEnabled()) {
      // 180 - blue color
    float brightness_factor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    fill_solid(bg_strip, settings.getInt(BG_LED_COUNT), fromHue(180, settings.getInt(CURRENT_BRIGHTNESS) * brightness_factor));
  }
  FastLED.show();
}

void mapRandom() {
  int randomLed = random(MAIN_LEDS_COUNT);
  int randomColor = random(360);
  strip[randomLed] = fromHue(randomColor, settings.getInt(CURRENT_BRIGHTNESS));
  if (isBgStripEnabled()) {
    int bgRandomLed = random(settings.getInt(BG_LED_COUNT));
    int bgRandomColor = random(360);
    float brightness_factor = settings.getInt(BRIGHTNESS_BG) / 100.0f;
    bg_strip[bgRandomLed] = fromHue(bgRandomColor, settings.getInt(CURRENT_BRIGHTNESS) * brightness_factor);
  }
  FastLED.show();
}

void mapCycle() {
  int currentMapMode = getCurrentMapMode();
  // show mapRecconect mode if websocket is not connected and map mode != 0
  if (websocketReconnect && currentMapMode) {
    currentMapMode = 1000;
  }
  switch (currentMapMode) {
    case 0:
      mapOff();
      break;
    case 1:
      mapAlarms();
      break;
    case 2:
      mapWeather();
      break;
    case 3:
      mapFlag();
      break;
    case 4:
      mapRandom();
      break;
    case 5:
      mapLamp();
      break;
    case 6:
      mapEnergy();
      break;
    case 7:
      mapRadiation();
      break;
    case 1000:
      mapReconnect();
      break;
  }
}

//--Map processing end

void rebootCycle() {
  if (needRebootWithDelay != -1) {
    int localDelay = needRebootWithDelay;
    needRebootWithDelay = -1;
    rebootDevice(localDelay);
  }
}

void checkCurrentTimeAndPlaySound() {
  if (needToPlaySound(REGULAR) && beepHour != timeClient.hour() && timeClient.minute() == 0 && timeClient.second() == 0) {
    beepHour = timeClient.hour();
    playMelody(REGULAR);
  }
}

void calculateStates() {
  // check if we need activate "minute of silence mode"
  checkMinuteOfSilence();

  // check alert in home district
  checkHomeDistrictAlerts();

#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
  if (isBuzzerEnabled() || dfPlayerConnected) {
    checkCurrentTimeAndPlaySound();

    if(isBuzzerEnabled()) {
      if (uaAnthemPlaying && !player->isPlaying()) {
        uaAnthemPlaying = false;
      }
    }
    if(dfPlayerConnected) {
      if (uaAnthemPlaying && !dfplayer.isPlaying()) {
        uaAnthemPlaying = false;
      }
    }
  }
#endif
  // update service message expiration
  if (display.isDisplayAvailable()) serviceMessageUpdate();
}

void updateHaLightSensors() {
  if (lightSensor.isLightSensorAvailable()) {
    ha.setLightLevel(lightSensor.getLightLevel(settings.getFloat(LIGHT_SENSOR_FACTOR)));
  }
}

void lightSensorCycle() {
  lightSensor.read();
  updateHaLightSensors();
}

void initChipID() {
  uint64_t chipid = ESP.getEfuseMac();
  sprintf(chipID, "%04x%04x", (uint32_t)(chipid >> 32), (uint32_t)chipid);
  LOG.printf("ChipID Inited: '%s'\n", chipID);
}

void initSettings() {
  LOG.println("Init settings");
  settings.init();
  currentFirmware = parseFirmwareVersion(VERSION);
  fillFwVersion(currentFwVersion, currentFirmware);
  LOG.printf("Current firmware version: %s\n", currentFwVersion);
  distributeBrightnessLevels();
}

void initLegacy() {
#if TEST_MODE
  settings.saveInt(LEGACY, 3, false);
#endif
  switch (settings.getInt(LEGACY)) {
  case 0:
    LOG.println("Mode: jaam 1");    

    settings.saveInt(POWER_PIN, 12, false);
    settings.saveInt(WIFI_PIN, 14, false);
    settings.saveInt(DATA_PIN, 25, false);
    settings.saveInt(HA_PIN, 26, false);
    settings.saveInt(UPD_AVAILABLE_PIN, 27, false);

    settings.saveInt(KYIV_DISTRICT_MODE, 3, false);
    settings.saveInt(MAIN_LED_PIN, 13, false);
    settings.saveInt(BG_LED_PIN, -1, false);
    settings.saveInt(BG_LED_COUNT, 0, false);
    settings.saveInt(SERVICE_LED_PIN, -1, false);
    settings.saveInt(BUTTON_1_PIN, 35, false);
    settings.saveInt(BUTTON_2_PIN, -1, false);
    settings.saveInt(DISPLAY_MODEL, 1, false);
    settings.saveInt(DISPLAY_HEIGHT, 64, false);
    settings.saveBool(USE_TOUCH_BUTTON_1, 0, false);

    pinMode(settings.getInt(POWER_PIN), OUTPUT);
    pinMode(settings.getInt(WIFI_PIN), OUTPUT);
    pinMode(settings.getInt(DATA_PIN), OUTPUT);
    pinMode(settings.getInt(HA_PIN), OUTPUT);
    pinMode(settings.getInt(UPD_AVAILABLE_PIN), OUTPUT);

    servicePin(POWER, HIGH, false);

    break;
  case 1:
    LOG.println("Mode: transcarpathia");

    settings.saveInt(SERVICE_DIODES_MODE, 0, false);
    break;
  case 2:
    LOG.println("Mode: odesa");

    settings.saveInt(SERVICE_DIODES_MODE, 0, false);
    break;
  case 3:
    LOG.println("Mode: jaam 2");

    settings.saveInt(KYIV_DISTRICT_MODE, 3, false);
    settings.saveInt(MAIN_LED_PIN, 13, false);
    settings.saveInt(BG_LED_PIN, 12, false);
    settings.saveInt(BG_LED_COUNT, 44, false);
    settings.saveInt(SERVICE_LED_PIN, 25, false);
    settings.saveInt(BUTTON_1_PIN, 4, false);
    settings.saveInt(BUTTON_2_PIN, 2, false);
    settings.saveInt(BUZZER_PIN, 33, false);
    settings.saveInt(DISPLAY_MODEL, 2, false);
    settings.saveInt(DISPLAY_HEIGHT, 64, false);
    brightnessFactor = 0.3f;
    minBrightness = 2;
    minBlinkBrightness = 0.07f;
    settings.saveBool(USE_TOUCH_BUTTON_1, 0, false);
    settings.saveBool(USE_TOUCH_BUTTON_2, 0, false);
    break;
  }
}

void initButtons() {
  LOG.println("Init buttons");

  LOG.printf("button1pin: %d\n", settings.getInt(BUTTON_1_PIN));
  LOG.printf("button1 touch: %d\n", settings.getBool(USE_TOUCH_BUTTON_1));
  buttons.setButton1Pin(settings.getInt(BUTTON_1_PIN), !settings.getBool(USE_TOUCH_BUTTON_1));
  buttons.setButton1ClickListener(button1Click);
  buttons.setButton1LongClickListener(button1LongClick);
  buttons.setButton1DuringLongClickListener(button1DuringLongClick);

  LOG.printf("button2pin: %d\n", settings.getInt(BUTTON_2_PIN));
  LOG.printf("button2 touch: %d\n", settings.getBool(USE_TOUCH_BUTTON_2));
  buttons.setButton2Pin(settings.getInt(BUTTON_2_PIN), !settings.getBool(USE_TOUCH_BUTTON_2));
  buttons.setButton2ClickListener(button2Click);
  buttons.setButton2LongClickListener(button2LongClick);
  buttons.setButton2DuringLongClickListener(button2DuringLongClick);
}

void initBuzzer() {
#if BUZZER_ENABLED
  if (isBuzzerEnabled()) {
    volumeCurrent = settings.getInt(MELODY_VOLUME_CURRENT);
    volumeDay = settings.getInt(MELODY_VOLUME_DAY);
    volumeNight = settings.getInt(MELODY_VOLUME_NIGHT);
    player = new MelodyPlayer(settings.getInt(BUZZER_PIN), 0, LOW);
    player->setVolume(expMap(volumeCurrent, 0, 100, 0, 255));
    LOG.printf("Set initial volume to: %d\n", volumeCurrent);
    
  }
#endif
}

void initAlertPin() {
  if (isAlertPinEnabled()) {
    LOG.printf("alertpin: %d\n", settings.getInt(ALERT_PIN));
    pinMode(settings.getInt(ALERT_PIN), OUTPUT);
  }
}

void initClearPin() {
  if (isClearPinEnabled() && settings.getInt(ALERT_CLEAR_PIN_MODE) == 1) {
    LOG.printf("clearpin: %d\n", settings.getInt(CLEAR_PIN));
    pinMode(settings.getInt(CLEAR_PIN), OUTPUT);
  }
}

void initFastledStrip(uint8_t pin, const CRGB *leds, int pixelcount) {
    bool isSupported = false;

    // Перевірка, чи пін входить до підтримуваних
    for (auto supportedPin : SUPPORTED_LEDS_PINS) {
        if (pin == supportedPin) {
            isSupported = true;
            break;
        }
    }

    if (!isSupported) {
        LOG.print("This PIN is not supported for LEDs: ");
        LOG.println(pin);
        return;
    }

    switch (pin) {
      #if ARDUINO_ESP32_DEV
        GENERATE_PIN_CASE(2)
        GENERATE_PIN_CASE(4)
        GENERATE_PIN_CASE(12)
        GENERATE_PIN_CASE(13)
        GENERATE_PIN_CASE(14)
        GENERATE_PIN_CASE(15)
        GENERATE_PIN_CASE(16)
        GENERATE_PIN_CASE(17)
        GENERATE_PIN_CASE(18)
        GENERATE_PIN_CASE(25)
        GENERATE_PIN_CASE(26)
        GENERATE_PIN_CASE(27)
        GENERATE_PIN_CASE(32)
        GENERATE_PIN_CASE(33)
      #elif ARDUINO_ESP32S3_DEV
        GENERATE_PIN_CASE(2)
        GENERATE_PIN_CASE(4)
        GENERATE_PIN_CASE(12)
        GENERATE_PIN_CASE(13)
        GENERATE_PIN_CASE(14)
        GENERATE_PIN_CASE(15)
        GENERATE_PIN_CASE(18)
        GENERATE_PIN_CASE(21)
        GENERATE_PIN_CASE(26)
        GENERATE_PIN_CASE(33)
        GENERATE_PIN_CASE(34)
        GENERATE_PIN_CASE(35)
        GENERATE_PIN_CASE(36)
        GENERATE_PIN_CASE(37)
        GENERATE_PIN_CASE(38)
        GENERATE_PIN_CASE(39)
        GENERATE_PIN_CASE(40)
        GENERATE_PIN_CASE(41)
        GENERATE_PIN_CASE(42)
      #elif ARDUINO_ESP32C3_DEV
        GENERATE_PIN_CASE(2)
        GENERATE_PIN_CASE(3)
        GENERATE_PIN_CASE(4)
        GENERATE_PIN_CASE(5)
        GENERATE_PIN_CASE(6)
        GENERATE_PIN_CASE(7)
        GENERATE_PIN_CASE(10)
        GENERATE_PIN_CASE(18)
        GENERATE_PIN_CASE(19)
        GENERATE_PIN_CASE(20)
        GENERATE_PIN_CASE(21)
      #endif
      default:
        LOG.print("Error: Unexpected pin configuration for this board: ");
        LOG.println(pin);
        break;
    }
}


void initStrip() {
  LOG.println("Init leds");
  LOG.print("pixelpin: ");
  LOG.println(settings.getInt(MAIN_LED_PIN));
  LOG.print("pixelcount: ");
  LOG.println(MAIN_LEDS_COUNT);
  initFastledStrip(settings.getInt(MAIN_LED_PIN), strip, MAIN_LEDS_COUNT);
  if (isBgStripEnabled()) {
    LOG.print("bg pixelpin: ");
    LOG.println(settings.getInt(BG_LED_PIN));
    LOG.print("bg pixelcount: ");
    LOG.println(settings.getInt(BG_LED_COUNT));
    initFastledStrip(settings.getInt(BG_LED_PIN), bg_strip, settings.getInt(BG_LED_COUNT));
  }
  if (isServiceStripEnabled()) {
    LOG.print("service ledpin: ");
    LOG.println(settings.getInt(SERVICE_LED_PIN));
    initFastledStrip(settings.getInt(SERVICE_LED_PIN), service_strip, 5);
    checkServicePins();
  }
  FastLED.setDither(DISABLE_DITHER);
  mapFlag();
}

void initDisplayOptions() {
  if (!display.isDisplayAvailable()) {
    // remove display related options from singl click optins list
    SINGLE_CLICK_OPTIONS[2].ignore = true;
    SINGLE_CLICK_OPTIONS[4].ignore = true;
    SINGLE_CLICK_OPTIONS[5].ignore = true;
    // change single click option to default if it's not available
    if (isInIgnoreList(settings.getInt(BUTTON_1_MODE), SINGLE_CLICK_OPTIONS, SINGLE_CLICK_OPTIONS_MAX)) {
      saveInt(BUTTON_1_MODE, 0, "button_mode");
    }
    if (isInIgnoreList(settings.getInt(BUTTON_2_MODE), SINGLE_CLICK_OPTIONS, SINGLE_CLICK_OPTIONS_MAX)) {
      saveInt(BUTTON_2_MODE, 0, "button2_mode");
    }

    // remove display related options from long click optins list
    LONG_CLICK_OPTIONS[2].ignore = true;
    LONG_CLICK_OPTIONS[4].ignore = true;
    LONG_CLICK_OPTIONS[5].ignore = true;
    // change long click option to default if it's not available
    if (isInIgnoreList(settings.getInt(BUTTON_1_MODE_LONG), LONG_CLICK_OPTIONS, LONG_CLICK_OPTIONS_MAX)) {
      saveInt(BUTTON_1_MODE_LONG, 0, "button_mode_long");
    }
    if (isInIgnoreList(settings.getInt(BUTTON_2_MODE_LONG), LONG_CLICK_OPTIONS, LONG_CLICK_OPTIONS_MAX)) {
      saveInt(BUTTON_2_MODE_LONG, 0, "button2_mode_long");
    }
  }
}

void initDisplayModes() {
  if (!climate.isAnySensorAvailable()) {
    LOG.println("No sensors available, disabling climate sensor options");
    // remove climate sensor options from display optins list
    for (int i = 0; i < DISPLAY_MODE_OPTIONS_MAX; i++) {
      if (DISPLAY_MODES[i].id == 4) {
        LOG.print("Display mode disabled: ");
        LOG.println(DISPLAY_MODES[i].name);
        DISPLAY_MODES[i].ignore = true;
        break;
      }
    }
    // change display mode to "changing" if it's not available
    if (isInIgnoreList(settings.getInt(DISPLAY_MODE), DISPLAY_MODES, DISPLAY_MODE_OPTIONS_MAX)) {
      saveDisplayMode(9);
    }
  } else {
    LOG.println("Climate sensor is available");
  }
}

void initDisplay() {
  display.begin(static_cast<JaamDisplay::DisplayModel>(settings.getInt(DISPLAY_MODEL)), settings.getInt(DISPLAY_WIDTH), settings.getInt(DISPLAY_HEIGHT));

  if (display.isDisplayAvailable()) {
    display.clearDisplay();
    display.setTextColor(2); // INVERSE
    updateInvertDisplayMode();
    updateDisplayBrightness();
    display.displayTextWithIcon(JaamDisplay::TRINDENT, "Just Another", "Alert Map", currentFwVersion);
    delay(3000);
  }
  initDisplayOptions();
}

int findTrackIndex(int fileNumber) {
#if DFPLAYER_PRO_ENABLED
  char trackName[10];
  sprintf(trackName, "/%02d.mp3", fileNumber);

  for (int i = 0; i < TRACKS_COUNT; i++) {
    char buffer[15];
    strcpy_P(buffer, (PGM_P)pgm_read_ptr(&TRACKS[i]));
    if (strcmp(buffer, trackName) == 0) {
      return i;
    }
  }
#endif
  return -1;
}

void initDfplayer() {
#if DFPLAYER_PRO_ENABLED
  if (isDFPlayerEnabled()) {
    volumeCurrent = settings.getInt(MELODY_VOLUME_CURRENT);
    volumeDay = settings.getInt(MELODY_VOLUME_DAY);
    volumeNight = settings.getInt(MELODY_VOLUME_NIGHT);
    int8_t attempts = 5;
    int8_t count = 1;
    dfSerial.begin(115200, SERIAL_8N1, settings.getInt(DF_RX_PIN), settings.getInt(DF_TX_PIN)); // RX, TX

    LOG.println("Init DFPlayer");
    LOG.printf("rx, tx: %d, %d\n", settings.getInt(DF_RX_PIN), settings.getInt(DF_TX_PIN));

    while (!dfplayer.begin(dfSerial)) {
      LOG.printf("Attempt #%d of %d\n", count, attempts);
      LOG.println("DFPlayer not found...");
      delay(1000);
      count++;
      if (count > attempts) return;
      
    }
    LOG.println("DFPlayer RX OK!");
    showServiceMessage("DFPlayer PRO", "Підключено:", 2000);
    dfplayer.setVol(2);
    delay(500); 
    if (dfplayer.getVol() != 2) {
      LOG.println("DFPlayer TX Fail!");
      return;
    }
    LOG.println("DFPlayer TX OK!");
    dfPlayerConnected = true;
    LOG.println("DFPlayer ready!");

    dfplayer.setVol(0); 
    dfplayer.switchFunction(dfplayer.MUSIC);
    dfplayer.setVol(expMapLinear(volumeCurrent, 0, 100, 0, 20));
    LOG.print("Volume: ");
    LOG.println(dfplayer.getVol());

    dfplayer.setPlayMode(dfplayer.ALLCYCLE);
    LOG.print("PlayMode: ");
    LOG.println(dfplayer.getPlayMode());
    delay(500);

    dfplayer.setLED(false);

    totalFiles = dfplayer.getTotalFile();
    LOG.print("The number of files available to play: ");
    LOG.println(totalFiles);
    if (totalFiles <= 0) {
      LOG.println("No files found!");
      return;
    }
    dynamicTracks = new String[totalFiles];
    dynamicTrackNames = new SettingListItem[totalFiles];

    for (int i = 0; i < totalFiles; i++) {
      int fileNumber = i + 1;

      int foundIndex = findTrackIndex(fileNumber);

      if (foundIndex >= 0) {
        dynamicTracks[i] = TRACKS[foundIndex];
        dynamicTrackNames[i] = TRACK_NAMES[foundIndex];
      } else {
        char trackPath[10];
        sprintf(trackPath, "/%02d.mp3", fileNumber);
        dynamicTracks[i] = String(trackPath);

        char* trackName = new char[20];
        sprintf(trackName, "Трек %d", fileNumber);

        dynamicTrackNames[i].id = i;
        dynamicTrackNames[i].name = trackName;
        dynamicTrackNames[i].ignore = false;
      }
    }

    for (int i = 0; i < totalFiles; i++) {
      LOG.print(dynamicTrackNames[i].id);
      LOG.print(": ");
      LOG.print(dynamicTracks[i]);
      LOG.print(" - ");
      LOG.println(dynamicTrackNames[i].name);
    }
  }
#endif
}

void initSensors() {
  lightSensor.begin(settings.getInt(LEGACY));
  if (lightSensor.isLightSensorAvailable()) {
    lightSensorCycle();
  }
  if (isAnalogLightSensorEnabled()) {
    lightSensor.setPhotoresistorPin(settings.getInt(LIGHT_SENSOR_PIN));
  }

  // init climate sensor
  climate.begin();
  // try to get climate sensor data
  climateSensorCycle();

  initDisplayModes();
}

void initUpdates() {
#if ARDUINO_OTA_ENABLED
  ArduinoOTA.onStart(showUpdateStart);
  ArduinoOTA.onEnd(showUpdateEnd);
  ArduinoOTA.onProgress(showUpdateProgress);
  ArduinoOTA.onError(showOtaUpdateErrorMessage);
  ArduinoOTA.begin();
#endif
#if FW_UPDATE_ENABLED
  Update.onProgress(showUpdateProgress);
  httpUpdate.onStart(showUpdateStart);
  httpUpdate.onEnd(showUpdateEnd);
  httpUpdate.onProgress(showUpdateProgress);
  httpUpdate.onError(showHttpUpdateErrorMessage);
#endif
}

void mapHaDisplayModes() {
  std::map<int, int> mapHaToId = {};
  std::map<int, int> mapIdToHa = {};
  int haIndex = 0;
  for (int i = 0; i < DISPLAY_MODE_OPTIONS_MAX; i++) {
    if (DISPLAY_MODES[i].ignore) continue;
    mapHaToId[haIndex] = DISPLAY_MODES[i].id;
    mapIdToHa[DISPLAY_MODES[i].id] = haIndex;
    haIndex++;
  }
  haDisplayModeMap = std::make_pair(mapHaToId, mapIdToHa);
}

void mapHaMapModes() {
  std::map<int, int> mapHaToId = {};
  std::map<int, int> mapIdToHa = {};
  int haIndex = 0;
  for (int i = 0; i < MAP_MODES_COUNT; i++) {
    if (MAP_MODES[i].ignore) continue;
    mapHaToId[haIndex] = MAP_MODES[i].id;
    mapIdToHa[MAP_MODES[i].id] = haIndex;
    haIndex++;
  }
  haMapModeMap = std::make_pair(mapHaToId, mapIdToHa);
}

void initHA() {
  if (shouldWifiReconnect) return;

  LOG.println("Init Home assistant API");

  if (!ha.initDevice(getLocalIP(), settings.getString(HA_BROKER_ADDRESS), settings.getString(DEVICE_NAME), currentFwVersion, settings.getString(DEVICE_DESCRIPTION), chipID)) {
    LOG.println("Home Assistant is not available!");
    return;
  }

  ha.initUptimeSensor();
  ha.initWifiSignalSensor();
  ha.initFreeMemorySensor();
  ha.initUsedMemorySensor();
  ha.initCpuTempSensor(temperatureRead());
  ha.initBrightnessSensor(settings.getInt(BRIGHTNESS), saveBrightness);
  ha.initDayBrightnessSensor(settings.getInt(BRIGHTNESS_DAY), saveDayBrightness);
  ha.initNightBrightnessSensor(settings.getInt(BRIGHTNESS_NIGHT), saveNightBrightness);
  auto mapModes = getNames(MAP_MODES, MAP_MODES_COUNT, true);
  mapHaMapModes();
  ha.initMapModeSensor(getIndexById(MAP_MODES, settings.getInt(MAP_MODE), MAP_MODES_COUNT), mapModes.second, mapModes.first, saveMapMode, transformFromHaMapMode);
  if (display.isDisplayAvailable()) {
    auto displayModes = getNames(DISPLAY_MODES, DISPLAY_MODE_OPTIONS_MAX, true);
    mapHaDisplayModes();
    ha.initDisplayModeSensor(haDisplayModeMap.second[settings.getInt(DISPLAY_MODE)], displayModes.second, displayModes.first, saveDisplayMode, transformFromHaDisplayMode);
    ha.initDisplayModeToggleSensor(nextDisplayMode);
    ha.initShowHomeAlarmTimeSensor(settings.getBool(HOME_ALERT_TIME), saveShowHomeAlarmTime);
  }
  auto alarmModes = getNames(AUTO_ALARM_MODES, AUTO_ALARM_MODES_COUNT, true);
  ha.initAutoAlarmModeSensor(getIndexById(AUTO_ALARM_MODES, settings.getInt(ALARMS_AUTO_SWITCH), AUTO_ALARM_MODES_COUNT), alarmModes.second, alarmModes.first, saveAutoAlarmMode, transformFromHaAutoAlarmMode);
  auto autoBrightnessModes = getNames(AUTO_BRIGHTNESS_MODES, AUTO_BRIGHTNESS_OPTIONS_COUNT, true);
  ha.initAutoBrightnessModeSensor(getIndexById(AUTO_BRIGHTNESS_MODES, settings.getInt(BRIGHTNESS_MODE), AUTO_BRIGHTNESS_OPTIONS_COUNT), autoBrightnessModes.second, autoBrightnessModes.first, saveAutoBrightnessMode, transformFromHaAutoBrMode);
  ha.initMapModeCurrentSensor();
  ha.initHomeDistrictSensor();
  ha.initMapApiConnectSensor(apiConnected);
  ha.initRebootSensor([] { rebootDevice(); });
  ha.initMapModeToggleSensor(nextMapMode);
  ha.initLampSensor(settings.getInt(MAP_MODE) == 5, settings.getInt(HA_LIGHT_BRIGHTNESS), settings.getInt(HA_LIGHT_R), settings.getInt(HA_LIGHT_G), settings.getInt(HA_LIGHT_B),
    onNewLampStateFromHa, saveLampBrightness, saveLampRgb);
  ha.initAlarmAtHomeSensor(alarmNow);
  if (climate.isTemperatureAvailable()) {
    ha.initLocalTemperatureSensor(climate.getTemperature(settings.getFloat(TEMP_CORRECTION)));
  }
  if (climate.isHumidityAvailable()) {
    ha.initLocalHumiditySensor(climate.getHumidity(settings.getFloat(HUM_CORRECTION)));
  }
  if (climate.isPressureAvailable()) {
    ha.initLocalPressureSensor(climate.getPressure(settings.getFloat(PRESSURE_CORRECTION)));
  }
  if (lightSensor.isLightSensorAvailable()) {
    ha.initLightLevelSensor(lightSensor.getLightLevel(settings.getFloat(LIGHT_SENSOR_FACTOR)));
  }
  ha.initHomeTemperatureSensor();
  ha.initNightModeSensor(nightMode, saveNightMode);
  ha.initHomeEnergySensor();
  ha.initHomeRadiationSensor();

  ha.connectToMqtt(settings.getInt(HA_MQTT_PORT), settings.getString(HA_MQTT_USER), settings.getString(HA_MQTT_PASSWORD), onMqttStateChanged);
}

void initWifi() {
  LOG.println("Init Wifi");
  WiFi.mode(WIFI_STA); // explicitly set mode, esp defaults to STA+AP
  // reset settings - wipe credentials for testing
  // wm.resetSettings();

  wm.setHostname(settings.getString(BROADCAST_NAME));
  wm.setTitle(settings.getString(DEVICE_NAME));
  wm.setConfigPortalBlocking(true);
  wm.setConnectTimeout(3);
  wm.setConnectRetries(10);
  wm.setAPCallback(apCallback);
  wm.setSaveConfigCallback(saveConfigCallback);
  wm.setConfigPortalTimeout(180);
  servicePin(WIFI, LOW, false);
  showServiceMessage(wm.getWiFiSSID(true).c_str(), "Підключення до:", 5000);
  char apssid[20];
  sprintf(apssid, "%s_%s", "JAAM", chipID);
  if (!wm.autoConnect(apssid)) {
    LOG.println("Reboot");
    rebootDevice(5000);
    return;
  }
  // Connected to WiFi
  LOG.println("connected...yeey :)");
  servicePin(WIFI, HIGH, false);
  showServiceMessage("Підключено до WiFi!");
  wm.setHttpPort(8080);
  wm.startWebPortal();
  delay(5000);
  setupRouting();
  initUpdates();
  initBroadcast();
  initHA();
  socketConnect();
  showServiceMessage(getLocalIP(), "IP-адреса мапи:", 5000);
}

void wifiReconnect() {
  if (WiFi.status() != WL_CONNECTED) {
    LOG.println("WiFI Reconnect");
    shouldWifiReconnect = true;
    initWifi();
  }
}

void initTime() {
  LOG.println("Init time");
  LOG.printf("NTP host: %s\n", settings.getString(NTP_HOST));
  timeClient.setHost(settings.getString(NTP_HOST));
  timeClient.setTimeZone(settings.getInt(TIME_ZONE));
  timeClient.setDSTauto(&dst); // auto update on summer/winter time.
  timeClient.setTimeout(5000); // 5 seconds waiting for reply
  timeClient.begin();
  syncTime(7);
}

void showLocalLightLevel() {
  char message[10];
  sprintf(message, "%.1f lx", lightSensor.getLightLevel(settings.getFloat(LIGHT_SENSOR_FACTOR)));
  displayMessage(message, "Освітлення");
}

#if TEST_MODE
void runSelfTests() {
  mapFlag();
  playMelody(UA_ANTHEM);
  servicePin(POWER, HIGH, true);
  servicePin(WIFI, HIGH, true);
  servicePin(DATA, HIGH, true);
  servicePin(HA, HIGH, true);
  servicePin(UPD_AVAILABLE, HIGH, true);
  showLocalTemp();
  sleep(2);
  showLocalHum();
  sleep(2);
  showLocalPressure();
  sleep(2);
  showLocalLightLevel();
  sleep(2);
  displayMessage("Please test buttons");
}
#endif

void serviceLedUpdAvailableHandler() {
  if (!isServiceStripEnabled()) return;
#if FW_UPDATE_ENABLED
  if (fwUpdateAvailable && settings.getBool(SERVICE_DIODES_MODE)) {
    int scaledBrightness = (settings.getInt(BRIGHTNESS_SERVICE) == 0) ? 0 : round(max(settings.getInt(BRIGHTNESS_SERVICE), minBrightness) * 255.0f / 100.0f * brightnessFactor);
    float updateBrightness = getFadeInFadeOutBrightness(scaledBrightness, 1500);
    service_strip[4] = CRGB(CRGB::White).nscale8_video(updateBrightness);
  } else {
    service_strip[4] = CRGB::Black;
  }
  FastLED.show();
#endif
}

void syncTimePeriodically() {
  syncTime(2);
}

void setup() {
  LOG.begin(115200);

  initChipID();
  initSettings();
  initLegacy();
  initLedMapping();
  initButtons();
  initBuzzer();
  initAlertPin();
  initClearPin();
  initStrip();
  initDisplay();
  initSensors();
  initDfplayer();
#if TEST_MODE
  runSelfTests();
#else
  initWifi();
  initTime();

  asyncEngine.setInterval(uptime, 5000);
  asyncEngine.setInterval(connectStatuses, 60000);
  asyncEngine.setInterval(mapCycle, 1000);
  asyncEngine.setInterval(displayCycle, 100);
  asyncEngine.setInterval(volumeCycle, 1000);
  asyncEngine.setInterval(wifiReconnect, 1000);
  asyncEngine.setInterval(autoBrightnessUpdate, 1000);
  #if FW_UPDATE_ENABLED
  asyncEngine.setInterval(doUpdate, 1000);
  #endif
  asyncEngine.setInterval(websocketProcess, 3000);
  asyncEngine.setInterval(alertPinCycle, 1000);
  asyncEngine.setInterval(rebootCycle, 500);
  asyncEngine.setInterval(lightSensorCycle, 2000);
  asyncEngine.setInterval(climateSensorCycle, 5000);
  asyncEngine.setInterval(calculateStates, 500);
  asyncEngine.setInterval(syncTimePeriodically, 60000);
#endif
  esp_err_t result  = esp_task_wdt_init(WDT_TIMEOUT, true);
  if (result == ESP_OK) {
    LOG.println("Watchdog timer enabled");
    enableLoopWDT();
  } else {
    LOG.println("Watchdog timer NOT enabled");
  }
}

void loop() {
#if TELNET_ENABLED
  LOG.handle();
#endif
#if TEST_MODE==0
  wm.process();
  asyncEngine.run();
#if ARDUINO_OTA_ENABLED
  ArduinoOTA.handle();
#endif
  ha.loop();
  client_websocket.poll();
  if (getCurrentMapMode() == 1 && settings.getInt(ALARMS_NOTIFY_MODE) == 2) {
    mapCycle();
  }
#endif
  buttons.tick();
  serviceLedUpdAvailableHandler();
}
