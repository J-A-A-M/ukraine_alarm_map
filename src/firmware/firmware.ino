#include <Preferences.h>
#include <WiFiManager.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ESPmDNS.h>
#include <async.h>
#include <ArduinoOTA.h>
#include <ArduinoHA.h>
#include <NTPClient.h>
#include <NeoPixelBus.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
#include <HTTPClient.h>
#include <Update.h>
#include <vector>
#include <ArduinoJson.h>
#include <esp_system.h>

String VERSION = "3.4";

struct Settings {
  char*         apssid                 = "JAAM";
  const char*   softwareversion        = VERSION.c_str();
  int           pixelcount             = 26;
  int           buttontime             = 100;
  int           powerpin               = 12;
  int           wifipin                = 14;
  int           datapin                = 25;
  int           hapin                  = 26;
  int           reservedpin            = 27;

  // ------- web config start
  String  devicename             = "Alarm Map";
  String  devicedescription      = "Alarm Map Informer";
  String  broadcastname          = "alarmmap";
  String  serverhost             = "alerts.net.ua";
  int     tcpport                = 12345;
  int     updateport             = 8090;
  String  bin_name               = VERSION + ".bin";
  String  identifier             = "github";
  int     legacy                 = 1;
  int     pixelpin               = 13;
  int     buttonpin              = 15;
  int     ha_mqttport            = 1883;
  String  ha_mqttuser            = "";
  String  ha_mqttpassword        = "";
  String  ha_brokeraddress       = "";
  int     brightness             = 50;
  int     brightness_day         = 50;
  int     brightness_night       = 5;
  int     brightness_auto        = 0;
  int     home_alert_time        = 0;
  int     color_alert            = 0;
  int     color_clear            = 120;
  int     color_home_district    = 120;
  int     color_new_alert        = 30;
  int     color_alert_over       = 100;
  int     brightness_alert       = 100;
  int     brightness_clear       = 100;
  int     brightness_new_alert   = 100;
  int     brightness_alert_over  = 100;
  int     weather_min_temp       = -10;
  int     weather_max_temp       = 30;
  int     alarms_auto_switch     = 1;
  int     home_district          = 7;
  int     kyiv_district_mode     = 1;
  int     service_diodes_mode    = 0;
  int     sdm_auto               = 0;
  int     new_fw_notification    = 1;

  // ------- Map Modes:
  // -------  0 - Off
  // -------  1 - Alarms
  // -------  2 - Weather
  // -------  3 - UA Flag
  // -------  4 - Random colors
  int     map_mode               = 1;

  // ------- Display Modes:
  // -------  0 - Off
  // -------  1 - Clock
  // -------  2 - Home District Temperature
  // -------  9 - Toggle modes
  int     display_mode           = 2;
  int     display_mode_time      = 5;
  int     button_mode            = 0;
  int     alarms_notify_mode     = 2;
  int     display_width          = 128;
  int     display_height         = 32;
  int     day_start              = 8;
  int     night_start            = 22;
  // ------- web config end
};

Settings settings;

struct Firmware {
  int major = 0;
  int minor = 0;
  int patch = 0;
};

Firmware currentFirmware;
Firmware latestFirmware;

Preferences       preferences;
WiFiManager       wm;
WiFiClient        client;
WiFiClient        client_tcp;
WiFiClient        client_update;
WiFiUDP           ntpUDP;
HTTPClient        http;
AsyncWebServer    webserver(80);
NTPClient         timeClient(ntpUDP, "ua.pool.ntp.org");
Async             asyncEngine = Async(20);
Adafruit_SSD1306  display(settings.display_width, settings.display_height, &Wire, -1);

struct ServiceMessage {
  String title;
  String message;
  int textSize;
  long endTime;
  bool expired;
};

ServiceMessage serviceMessage;

NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod>* strip;

int     alarm_leds[26];
double  weather_leds[26];
int     flag_leds[26];
// int     flag_leds[26] = {
//   60,60,60,180,180,60,60,60,60,60,60,
//   60,180,180,180,180,180,180,
//   180,180,180,60,60,60,60,180
// };
int legacy_flag_leds[26] = {
  60, 60, 60, 180, 180, 180, 180, 180, 180,
  180, 180, 180, 60, 60, 60, 60, 60, 60, 60,
  180, 180, 60, 60, 60, 60, 180
};


int d0[] = { 0, 1, 3 };
int d1[] = { 1, 0, 2, 3, 24 };
int d2[] = { 2, 1, 3, 4, 5, 23, 24 };
int d3[] = { 3, 0, 1, 2, 4 };
int d4[] = { 4, 2, 3, 5 };
int d5[] = { 5, 2, 3, 4, 6, 23 };
int d6[] = { 6, 5, 7, 22, 23, 25 };
int d7[] = { 7, 6, 8, 19, 20, 22, 25 };
int d8[] = { 8, 7, 9, 19, 20 };
int d9[] = { 9, 8, 10, 19 };
int d10[] = { 10, 9, 12, 18, 19 };
int d11[] = { 11, 10, 12 };
int d12[] = { 12, 10, 13, 18 };
int d13[] = { 13, 12, 14, 18 };
int d14[] = { 14, 13, 17, 18 };
int d15[] = { 15, 14 };
int d16[] = { 16, 17, 20, 21, 22 };
int d17[] = { 17, 14, 16, 18, 21 };
int d18[] = { 18, 10, 12, 13, 14, 17, 19, 21 };
int d19[] = { 19, 7, 8, 9, 10, 18, 20, 21, 25 };
int d20[] = { 20, 7, 8, 19, 21, 22, 25 };
int d21[] = { 21, 16, 17, 18, 19, 20, 22 };
int d22[] = { 22, 6, 7, 16, 20, 21, 23, 24, 25 };
int d23[] = { 23, 2, 5, 6, 22, 24 };
int d24[] = { 24, 1, 2, 22, 23 };
int d25[] = { 25, 6, 7, 8, 19, 20, 22 };


int counters[] = { 3, 5, 7, 5, 4, 6, 6, 6, 5, 4, 5, 3, 4, 4, 4, 2, 5, 5, 8, 8, 7, 7, 9, 6, 5, 7 };

std::vector<String> districts = {
  "Закарпатська обл.",
  "Ів.-Франківська обл.",
  "Тернопільська обл.",
  "Львівська обл.",
  "Волинська обл.",
  "Рівненська обл.",
  "Житомирська обл.",
  "Київська обл.",
  "Чернігівська обл.",
  "Сумська обл.",
  "Харківська обл.",
  "Луганська обл.",
  "Донецька обл.",
  "Запорізька обл.",
  "Херсонська обл.",
  "АР Крим",
  "Одеська обл.",
  "Миколаївська обл.",
  "Дніпропетровська обл.",
  "Полтавська обл.",
  "Черкаська обл.",
  "Кіровоградська обл.",
  "Вінницька обл.",
  "Хмельницька обл.",
  "Чернівецька обл.",
  "Київ"
};

std::vector<String> districtsAlphabetical = {
  "АР Крим",
  "Вінницька область",
  "Волинська область",
  "Дніпропетровська область",
  "Донецька область",
  "Житомирська область",
  "Закарпатська область",
  "Запорізька область",
  "Івано-Франківська область",
  "Київська область",
  "Київ",
  "Кіровоградська область",
  "Луганська область",
  "Львівська область",
  "Миколаївська область",
  "Одеська область",
  "Полтавська область",
  "Рівненська область",
  "Сумська область",
  "Тернопільська область",
  "Харківська область",
  "Херсонська область",
  "Хмельницька область",
  "Черкаська область",
  "Чернівецька область",
  "Чернігівська область"
};

int alphabetDistrictToNum(int alphabet) {
  switch (alphabet) {
    case 0:
      return 15;
    case 1:
      return 22;
    case 2:
      return 4;
    case 3:
      return 18;
    case 4:
      return 12;
    case 5:
      return 6;
    case 6:
      return 0;
    case 7:
      return 13;
    case 8:
      return 1;
    case 9:
      return 7;
    case 10:
      return 25;
    case 11:
      return 21;
    case 12:
      return 11;
    case 13:
      return 3;
    case 14:
      return 17;
    case 15:
      return 16;
    case 16:
      return 19;
    case 17:
      return 5;
    case 18:
      return 9;
    case 19:
      return 2;
    case 20:
      return 10;
    case 21:
      return 14;
    case 22:
      return 23;
    case 23:
      return 20;
    case 24:
      return 24;
    case 25:
      return 8;
    default:
      // return Київ by default
      return 25;
  }
}

int numDistrictToAlphabet(int num) {
  switch (num) {
    case 0:
      return 6;
    case 1:
      return 8;
    case 2:
      return 19;
    case 3:
      return 13;
    case 4:
      return 2;
    case 5:
      return 17;
    case 6:
      return 5;
    case 7:
      return 9;
    case 8:
      return 25;
    case 9:
      return 18;
    case 10:
      return 20;
    case 11:
      return 12;
    case 12:
      return 4;
    case 13:
      return 7;
    case 14:
      return 21;
    case 15:
      return 0;
    case 16:
      return 15;
    case 17:
      return 14;
    case 18:
      return 3;
    case 19:
      return 16;
    case 20:
      return 23;
    case 21:
      return 11;
    case 22:
      return 1;
    case 23:
      return 22;
    case 24:
      return 24;
    case 25:
      return 10;
    default:
      // return Київ by default
      return 10;
  }
}

int* neighboring_districts[] = {
  d0, d1, d2, d3, d4, d5, d6, d7, d8, d9,
  d10, d11, d12, d13, d14, d15, d16, d17, d18, d19,
  d20, d21, d22, d23, d24, d25
};

const unsigned char trident_small[] PROGMEM = {
  0x04, 0x00, 0x80, 0x10, 0x06, 0x01, 0xc0, 0x30, 0x07, 0x01, 0xc0, 0x70, 0x07, 0x81, 0xc0, 0xf0,
  0x07, 0xc1, 0xc1, 0xf0, 0x06, 0xc1, 0xc1, 0xb0, 0x06, 0xe1, 0xc3, 0xb0, 0x06, 0x61, 0xc3, 0x30,
  0x06, 0x71, 0xc7, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30,
  0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0xf1, 0xc7, 0xb0, 0x07, 0xe1, 0xc3, 0xf0,
  0x07, 0x83, 0xe0, 0xf0, 0x07, 0x03, 0x60, 0x70, 0x07, 0x87, 0x70, 0xf0, 0x07, 0xc6, 0x31, 0xf0,
  0x06, 0xee, 0x3b, 0xb0, 0x06, 0x7f, 0x7f, 0x30, 0x06, 0x3d, 0xde, 0x30, 0x06, 0x19, 0xcc, 0x30,
  0x07, 0xff, 0xff, 0xf0, 0x03, 0xff, 0xff, 0xe0, 0x01, 0xfc, 0x9f, 0xc0, 0x00, 0x0c, 0xd8, 0x00,
  0x00, 0x07, 0xf0, 0x00, 0x00, 0x03, 0xe0, 0x00, 0x00, 0x01, 0xc0, 0x00, 0x00, 0x00, 0x80, 0x00
};

bool    enableHA;
bool    wifiReconnect = false;
bool    tcpReconnect = false;
bool    blink = false;
bool    isDaylightSaving = false;
bool    isPressed = true;
long    buttonPressStart = 0;
time_t  tcpLastPingTime = 0;
int     offset = 9;
bool    initUpdate = false;
long    homeAlertStart = 0;
int     timeOffset = 0;
time_t  lastHomeDistrictSync = 0;
bool    fwUpdateAvailable = false;

std::vector<String> bin_list;

HADevice        device;
HAMqtt          mqtt(client, device, 16);

uint64_t chipid = ESP.getEfuseMac();
String chipID1 = String((uint32_t)(chipid >> 32), HEX);
String chipID2 = String((uint32_t)chipid, HEX);

String haUptimeString             = chipID1 + chipID2 + "_uptime";
String haWifiSignalString         = chipID1 + chipID2 + "_wifi_signal";
String haFreeMemoryString         = chipID1 + chipID2 + "_free_memory";
String haUsedMemoryString         = chipID1 + chipID2 + "_used_memory";
String haBrightnessString         = chipID1 + chipID2 + "_brightness";
String haMapModeString            = chipID1 + chipID2 + "_map_mode";
String haDisplayModeString        = chipID1 + chipID2 + "_display_mode";
String haMapModeCurrentString     = chipID1 + chipID2 + "_map_mode_current";
String haMapApiConnectString      = chipID1 + chipID2 + "_map_api_connect";
String haBrightnessAutoString     = chipID1 + chipID2 + "_brightness_auto";
String haAlarmsAutoString         = chipID1 + chipID2 + "_alarms_auto";
String haShowHomeAlarmTimeString  = chipID1 + chipID2 + "_show_home_alarm_time";
String haRebootString             = chipID1 + chipID2 + "_reboot";
String haCpuTempString            = chipID1 + chipID2 + "_cpu_temp";
String haHomeDistrictString       = chipID1 + chipID2 + "_home_district";
String haToggleMapModeString      = chipID1 + chipID2 + "_toggle_map_mode";
String haToggleDisplayModeString  = chipID1 + chipID2 + "_toggle_display_mode";

HASensorNumber  haUptime(haUptimeString.c_str());
HASensorNumber  haWifiSignal(haWifiSignalString.c_str());
HASensorNumber  haFreeMemory(haFreeMemoryString.c_str());
HASensorNumber  haUsedMemory(haUsedMemoryString.c_str());
HANumber        haBrightness(haBrightnessString.c_str());
HASelect        haMapMode(haMapModeString.c_str());
HASelect        haDisplayMode(haDisplayModeString.c_str());
HASelect        haAlarmsAuto(haAlarmsAutoString.c_str());
HASensor        haMapModeCurrent(haMapModeCurrentString.c_str());
HABinarySensor  haMapApiConnect(haMapApiConnectString.c_str());
HASwitch        haBrightnessAuto(haBrightnessAutoString.c_str());
HASwitch        haShowHomeAlarmTime(haShowHomeAlarmTimeString.c_str());
HAButton        haReboot(haRebootString.c_str());
HAButton        haToggleMapMode(haToggleMapModeString.c_str());
HAButton        haToggleDisplayMode(haToggleDisplayModeString.c_str());
HASensorNumber  haCpuTemp(haCpuTempString.c_str(), HASensorNumber::PrecisionP1);
HASensor        haHomeDistrict(haHomeDistrictString.c_str());

std::vector<String> mapModes = {
  "Вимкнено",
  "Tpивoгa",
  "Погода",
  "Прапор",
  "Випадкові кольори"
};

std::vector<String> displayModes = {
  "Вимкнено",
  "Годинник",
  "Погода",
  "Перемикання"
};

std::vector<String> autoAlarms = {
  "Вимкнено",
  "Домашній та суміжні",
  "Лише домашній"
};

//--Init start
void initLegacy() {
  if (settings.legacy) {
    offset = 0;
    for (int i = 0; i < 26; i++) {
      flag_leds[i] = legacy_flag_leds[i];
    }
    settings.service_diodes_mode = 0;
  } else {
    for (int i = 0; i < 26; i++) {
      flag_leds[calculateOffset(i)] = legacy_flag_leds[i];
    }

    pinMode(settings.powerpin, OUTPUT);
    pinMode(settings.wifipin, OUTPUT);
    pinMode(settings.datapin, OUTPUT);
    pinMode(settings.hapin, OUTPUT);
    pinMode(settings.reservedpin, OUTPUT);

    servicePin(settings.powerpin, HIGH, false);

    settings.kyiv_district_mode = 3;
    settings.pixelpin = 13;
    settings.buttonpin = 35;
    settings.display_height = 64;
  }
  pinMode(settings.buttonpin, INPUT);
}

void servicePin(int pin, uint8_t status, bool force) {
  if (!settings.legacy && settings.service_diodes_mode) {
    digitalWrite(pin, status);
  }
  if (force) {
    digitalWrite(pin, status);
  }
}

void initSettings() {
  Serial.println("Init settings");
  preferences.begin("storage", false);

  settings.devicename             = preferences.getString("dn", settings.devicename);
  settings.devicedescription      = preferences.getString("dd", settings.devicedescription);
  settings.broadcastname          = preferences.getString("bn", settings.broadcastname);
  settings.serverhost             = preferences.getString("host", settings.serverhost);
  settings.identifier             = preferences.getString("id", settings.identifier);
  settings.tcpport                = preferences.getInt("tcpport", settings.tcpport);
  settings.updateport             = preferences.getInt("upport", settings.updateport);
  settings.legacy                 = preferences.getInt("legacy", settings.legacy);
  settings.brightness             = preferences.getInt("brightness", settings.brightness);
  settings.brightness_day         = preferences.getInt("brd", settings.brightness_day);
  settings.brightness_night       = preferences.getInt("brn", settings.brightness_night);
  settings.brightness_auto        = preferences.getInt("bra", settings.brightness_auto);
  settings.home_alert_time        = preferences.getInt("hat", settings.home_alert_time);
  settings.color_alert            = preferences.getInt("coloral", settings.color_alert);
  settings.color_clear            = preferences.getInt("colorcl", settings.color_clear);
  settings.color_new_alert        = preferences.getInt("colorna", settings.color_new_alert);
  settings.color_alert_over       = preferences.getInt("colorao", settings.color_alert_over);
  settings.color_home_district    = preferences.getInt("colorhd", settings.color_home_district);
  settings.brightness_alert       = preferences.getInt("ba", settings.brightness_alert);
  settings.brightness_clear       = preferences.getInt("bc", settings.brightness_clear);
  settings.brightness_new_alert   = preferences.getInt("bna", settings.brightness_new_alert);
  settings.brightness_alert_over  = preferences.getInt("bao", settings.brightness_alert_over);
  settings.alarms_auto_switch     = preferences.getInt("aas", settings.alarms_auto_switch);
  settings.home_district          = preferences.getInt("hd", settings.home_district);
  settings.kyiv_district_mode     = preferences.getInt("kdm", settings.kyiv_district_mode);
  settings.map_mode               = preferences.getInt("mapmode", settings.map_mode);
  settings.display_mode           = preferences.getInt("dm", settings.display_mode);
  settings.display_mode_time      = preferences.getInt("dmt", settings.display_mode_time);
  settings.button_mode            = preferences.getInt("bm", settings.button_mode);
  settings.alarms_notify_mode     = preferences.getInt("anm", settings.alarms_notify_mode);
  settings.weather_min_temp       = preferences.getInt("mintemp", settings.weather_min_temp);
  settings.weather_max_temp       = preferences.getInt("maxtemp", settings.weather_max_temp);
  settings.ha_brokeraddress       = preferences.getString("ha_brokeraddr", settings.ha_brokeraddress);
  settings.ha_mqttport            = preferences.getInt("ha_mqttport", settings.ha_mqttport);
  settings.ha_mqttuser            = preferences.getString("ha_mqttuser", settings.ha_mqttuser);
  settings.ha_mqttpassword        = preferences.getString("ha_mqttpass", settings.ha_mqttpassword);
  settings.display_width          = preferences.getInt("dw", settings.display_width);
  settings.display_height         = preferences.getInt("dh", settings.display_height);
  settings.day_start              = preferences.getInt("ds", settings.day_start);
  settings.night_start            = preferences.getInt("ns", settings.night_start);
  settings.pixelpin               = preferences.getInt("pp", settings.pixelpin);
  settings.buttonpin              = preferences.getInt("bp", settings.buttonpin);
  settings.service_diodes_mode    = preferences.getInt("sdm", settings.service_diodes_mode);
  settings.sdm_auto               = preferences.getInt("sdma", settings.sdm_auto);
  settings.new_fw_notification    = preferences.getInt("nfwn", settings.new_fw_notification);
  preferences.end();

  currentFirmware = parseFirmwareVersion(VERSION);
  Serial.print("Current firmware version: ");
  Serial.print(currentFirmware.major);
  Serial.print(".");
  Serial.print(currentFirmware.minor);
  Serial.print(".");
  Serial.println(currentFirmware.patch);
}

void initStrip() {
  Serial.print("pixelpin: ");
  Serial.println(settings.pixelpin);
  strip = new NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod>(settings.pixelcount, settings.pixelpin);
  Serial.println("Init leds");
  strip->Begin();
  mapFlag();
}

void initTime() {
  Serial.println("Init time");
  timeClient.begin();
  timezoneUpdate();
  tcpLastPingTime = millis();
}

void timezoneUpdate() {
  timeClient.update();

  time_t rawTime = timeClient.getEpochTime();
  struct tm* timeInfo;
  timeInfo = localtime(&rawTime);

  int year = 1900 + timeInfo->tm_year;
  int month = 1 + timeInfo->tm_mon;
  int day = timeInfo->tm_mday;
  int hour = timeInfo->tm_hour;
  int minutes = timeInfo->tm_min;
  int seconds = timeInfo->tm_sec;

  Serial.print("Current date and time: ");
  Serial.print(year);
  Serial.print("-");
  Serial.print(month);
  Serial.print("-");
  Serial.print(day);
  Serial.print(" ");
  Serial.print(hour);
  Serial.print(":");
  Serial.print(minutes);
  Serial.print(":");
  Serial.println(seconds);

  if ((month > 3 && month < 10) ||
      (month == 3 && day > getLastSunday(year,3)) ||
      (month == 3 && day == getLastSunday(year,3) and hour >=3) ||
      (month == 10 && day < getLastSunday(year,10))||
      (month == 10 && day == getLastSunday(year,10) and hour <3)) {
    isDaylightSaving = true;
  }
  Serial.print("isDaylightSaving: ");
  Serial.println(isDaylightSaving);
  if (isDaylightSaving) {
    timeOffset = 10800;
  } else {
    timeOffset = 7200;
  }
  timeClient.setTimeOffset(timeOffset);
}

int getLastSunday(int year, int month) {
  for (int day = 31; day >= 25; day--) {
    int h = (day + (13 * (month + 1)) / 5 + year + year / 4 - year / 100 + year / 400) % 7;
    if (h == 1) {
      return day;
    }
  }
  return 0;
}

void initWifi() {
  Serial.println("Init Wifi");
  WiFi.mode(WIFI_STA);  // explicitly set mode, esp defaults to STA+AP
  //reset settings - wipe credentials for testing
  //wm.resetSettings();

  wm.setHostname(settings.broadcastname);
  wm.setTitle(settings.devicename);
  wm.setConfigPortalBlocking(true);
  wm.setConnectTimeout(3);
  wm.setConnectRetries(10);
  wm.setAPCallback(apCallback);
  servicePin(settings.wifipin, LOW, false);
  showServiceMessage(wm.getWiFiSSID(true), "Підключення до:", 5000);
  String apssid = "";
  apssid += settings.apssid;
  apssid += "_";
  apssid += chipID1;
  apssid += chipID2;
  if (wm.autoConnect(apssid.c_str())) {
    Serial.println("connected...yeey :)");
    servicePin(settings.wifipin, HIGH, false);
    showServiceMessage("Підключено до WiFi!", 1000);
    wm.setHttpPort(8080);
    wm.startWebPortal();
    delay(1000);
    setupRouting();
    initHA();
    ArduinoOTA.begin();
    initBroadcast();
    tcpConnect();
    doFetchBinList();
    showServiceMessage(WiFi.localIP().toString(), "IP-адреса мапи:", 5000);
  } else {
    Serial.println("Reboot");
    showServiceMessage("Пepeзaвaнтaжeння...", 5000);
    delay(5000);
    ESP.restart();
  }
}

void apCallback(WiFiManager* wifiManager) {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println(utf8cyr("Підключіться до WiFi:"));
  DisplayCenter(wifiManager->getConfigPortalSSID(), 7, 1);
  WiFi.onEvent(wifiEvents);
}

static void wifiEvents(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
      display.clearDisplay();
      display.setCursor(0, 0);
      display.setTextSize(1);
      display.println(utf8cyr("Введіть у браузері:"));
      DisplayCenter(WiFi.softAPIP().toString(), 7, 1);
      WiFi.removeEvent(wifiEvents);
    default:
      break;
  }
}

void initBroadcast() {
  Serial.println("Init network device broadcast");

  if (!MDNS.begin(settings.broadcastname)) {
    Serial.println("Error setting up mDNS responder");
    showServiceMessage("Помилка mDNS");
    while (1) {
      delay(1000);
    }
  }
  Serial.println("Device broadcasted to network: " + settings.broadcastname + ".local");
}

void initHA() {
  if (!wifiReconnect) {
    Serial.println("Init Home assistant API");

    char* deviceName             = new char[settings.devicename.length() + 1];
    char* deviceDescr            = new char[settings.devicedescription.length() + 1];
    char* brokerAddress          = new char[settings.ha_brokeraddress.length() + 1];
    char* mqttUser               = new char[settings.ha_mqttuser.length() + 1];
    char* mqttPassword           = new char[settings.ha_mqttpassword.length() + 1];

    strcpy(deviceName, settings.devicename.c_str());
    strcpy(deviceDescr, settings.devicedescription.c_str());
    strcpy(brokerAddress, settings.ha_brokeraddress.c_str());
    strcpy(mqttUser, settings.ha_mqttuser.c_str());
    strcpy(mqttPassword, settings.ha_mqttpassword.c_str());

    IPAddress brokerAddr;

    if (!brokerAddr.fromString(brokerAddress)) {
      Serial.println("Invalid IP-address format!");
      enableHA = false;
    } else {
      enableHA = true;
    }

    if (enableHA) {
      byte mac[6];
      WiFi.macAddress(mac);
      device.setUniqueId(mac, sizeof(mac));
      device.setName(deviceName);
      device.setSoftwareVersion(settings.softwareversion);
      device.setManufacturer("v00g100skr");
      device.setModel(deviceDescr);
      device.enableSharedAvailability();

      haUptime.setIcon("mdi:timer-outline");
      haUptime.setName("Uptime");
      haUptime.setUnitOfMeasurement("s");
      haUptime.setDeviceClass("duration");

      haWifiSignal.setIcon("mdi:wifi");
      haWifiSignal.setName("WIFI Signal");
      haWifiSignal.setUnitOfMeasurement("dBm");
      haWifiSignal.setDeviceClass("signal_strength");

      haFreeMemory.setIcon("mdi:memory");
      haFreeMemory.setName("Free Memory");
      haFreeMemory.setUnitOfMeasurement("kB");
      haFreeMemory.setDeviceClass("data_size");

      haUsedMemory.setIcon("mdi:memory");
      haUsedMemory.setName("Used Memory");
      haUsedMemory.setUnitOfMeasurement("kB");
      haUsedMemory.setDeviceClass("data_size");

      haBrightness.onCommand(onHaBrightnessCommand);
      haBrightness.setIcon("mdi:brightness-percent");
      haBrightness.setName("Brightness");
      haBrightness.setCurrentState(settings.brightness);

      haMapMode.setOptions(getHaOptions(mapModes).c_str());
      haMapMode.onCommand(onHaMapModeCommand);
      haMapMode.setIcon("mdi:map");
      haMapMode.setName("Map Mode");
      haMapMode.setCurrentState(settings.map_mode);

      haDisplayMode.setOptions(getHaOptions(displayModes).c_str());
      haDisplayMode.onCommand(onHaDisplayModeCommand);
      haDisplayMode.setIcon("mdi:clock-digital");
      haDisplayMode.setName("Display Mode");
      haDisplayMode.setCurrentState(getHaDisplayMode(settings.display_mode));

      haAlarmsAuto.setOptions(getHaOptions(autoAlarms).c_str());
      haAlarmsAuto.onCommand(onhaAlarmsAutoCommand);
      haAlarmsAuto.setIcon("mdi:alert-outline");
      haAlarmsAuto.setName("Auto Alarm");
      haAlarmsAuto.setCurrentState(settings.alarms_auto_switch);

      haMapModeCurrent.setIcon("mdi:map");
      haMapModeCurrent.setName("Current Map Mode");

      haMapApiConnect.setName("Connectivity");
      haMapApiConnect.setDeviceClass("connectivity");
      haMapApiConnect.setCurrentState(false);

      haBrightnessAuto.onCommand(onhaBrightnessAutoCommand);
      haBrightnessAuto.setIcon("mdi:brightness-auto");
      haBrightnessAuto.setName("Auto Brightness");
      haBrightnessAuto.setCurrentState(settings.brightness_auto);

      haShowHomeAlarmTime.onCommand(onHaShowHomeAlarmTimeCommand);
      haShowHomeAlarmTime.setIcon("mdi:timer-alert");
      haShowHomeAlarmTime.setName("Show Home Alert Time");
      haShowHomeAlarmTime.setCurrentState(settings.home_alert_time);

      haReboot.onCommand(onHaButtonClicked);
      haReboot.setName("Reboot");
      haReboot.setDeviceClass("restart");

      haToggleMapMode.onCommand(onHaButtonClicked);
      haToggleMapMode.setName("Toggle Map Mode");
      haToggleMapMode.setIcon("mdi:map-plus");

      haToggleDisplayMode.onCommand(onHaButtonClicked);
      haToggleDisplayMode.setName("Toggle Display Mode");
      haToggleDisplayMode.setIcon("mdi:card-plus");

      haCpuTemp.setIcon("mdi:chip");
      haCpuTemp.setName("CPU Temperature");
      haCpuTemp.setDeviceClass("temperature");
      haCpuTemp.setUnitOfMeasurement("°C");
      haCpuTemp.setCurrentValue(temperatureRead());

      haHomeDistrict.setIcon("mdi:home-map-marker");
      haHomeDistrict.setName("Home District");

      device.enableLastWill();
      mqtt.onConnected(mqttConnected);
      mqtt.begin(brokerAddr, settings.ha_mqttport, mqttUser, mqttPassword);
    }
  }
}

void mqttConnected() {
  Serial.println("Home Assistant MQTT connected!");
  if (enableHA) {
    // Update HASensors values (Unlike the other device types, the HASensor doesn't store the previous value that was set. It means that the MQTT message is produced each time the setValue method is called.)
    haMapModeCurrent.setValue(mapModes[getCurrentMapMode()].c_str());
    haHomeDistrict.setValue(districtsAlphabetical[numDistrictToAlphabet(settings.home_district)].c_str());
  }
}

String getHaOptions(std::vector<String> list) {
  String result;
  for (String option : list) {
    if (list[0] != option) {
      result += ";";
    }
    result += option;
  }
  return result;
}

void onHaButtonClicked(HAButton* sender) {
  if (sender == &haReboot){
    ESP.restart();
  } else if (sender == &haToggleMapMode) {
    mapModeSwitch();
  } else if (sender == &haToggleDisplayMode) {
    displayModeSwitch();
  }
}

void onHaShowHomeAlarmTimeCommand(bool state, HASwitch* sender) {
  settings.home_alert_time = state;
  preferences.begin("storage", false);
  preferences.putInt("hat", settings.home_alert_time);
  preferences.end();
  Serial.println("home_alert_time commited to preferences");
  Serial.print("home_alert_time: ");
  Serial.println(settings.home_alert_time);
  sender->setState(state);  // report state back to the Home Assistant
}

void onhaBrightnessAutoCommand(bool state, HASwitch* sender) {
  settings.brightness_auto = state;
  preferences.begin("storage", false);
  if (state == false) {
    settings.brightness = settings.brightness_day;
    preferences.putInt("brightness", settings.brightness);
    haBrightness.setState(settings.brightness);
  }
  preferences.putInt("bra", settings.brightness_auto);
  preferences.end();
  Serial.println("brightness_auto commited to preferences");
  Serial.print("brightness_auto: ");
  Serial.println(settings.brightness_auto);
  sender->setState(state);  // report state back to the Home Assistant
}

void onHaBrightnessCommand(HANumeric haBrightness, HANumber* sender) {
  int8_t numberInt8 = haBrightness.toInt8();
  settings.brightness = numberInt8;
  settings.brightness_auto = 0;
  preferences.begin("storage", false);
  preferences.putInt("brightness", settings.brightness);
  preferences.putInt("bra", 0);
  preferences.end();
  Serial.println("brightness commited to preferences");
  haBrightnessAuto.setState(false);
  sender->setState(haBrightness);
}

void onhaAlarmsAutoCommand(int8_t index, HASelect* sender) {
  settings.alarms_auto_switch = index;
  preferences.begin("storage", false);
  preferences.putInt("aas", settings.alarms_auto_switch);
  preferences.end();
  Serial.print("alarms_auto_switch commited to preferences: ");
  Serial.println(settings.alarms_auto_switch);
  sender->setState(index);
}

void onHaMapModeCommand(int8_t index, HASelect* sender) {
  settings.map_mode = index;
  saveMapMode();
}

void onHaDisplayModeCommand(int8_t index, HASelect* sender) {
  settings.display_mode = getRealDisplayMode(index);
  saveDisplayMode();
  // update to selected displayMode
  displayCycle();
}

int getHaDisplayMode(int displayMode) {
  switch (displayMode) {
    case 0:
      // passthrough
    case 1:
      // passthrough
    case 2:
      return displayMode;
    case 9:
      return 3;
    default:
      return 0;
  }
}

int getRealDisplayMode(int displayMode) {
  switch (displayMode) {
    case 0:
      // passthrough
    case 1:
      // passthrough
    case 2:
      return displayMode;
    case 3:
      return 9;
    default:
      return 0;
  }
}

void initDisplay() {

  display = Adafruit_SSD1306(settings.display_width, settings.display_height, &Wire, -1);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.display();
  display.clearDisplay();
  display.setTextColor(WHITE);
  // int16_t centerX = (settings.display_width - 32) / 2;    // Calculate the X coordinate
  int16_t centerY = (settings.display_height - 32) / 2;
  display.drawBitmap(0, centerY, trident_small, 32, 32, 1);
  display.setTextSize(1);
  String text1 = utf8cyr("Just Another");
  String text2 = utf8cyr("Alert Map ");
  int16_t x;
  int16_t y;
  uint16_t width;
  uint16_t height;
  display.getTextBounds(text1, 0, 0, &x, &y, &width, &height);
  display.setCursor(35, ((settings.display_height - height) / 2) - 9);
  display.print(text1);
  display.setCursor(35, ((settings.display_height - height) / 2));
  display.print(text2);
  display.setCursor(35, ((settings.display_height - height) / 2) + 9);
  display.print(settings.softwareversion);
  display.display();
  delay(3000);
}
//--Init end

//--Update

std::vector<String> fetchAndParseJSON() {
  Serial.println("Start fetching bin list");
  String jsonURLString = "http://" + settings.serverhost + ":" + settings.updateport + "/list";
  Serial.println(jsonURLString);
  const char* jsonURL = jsonURLString.c_str();
  http.begin(jsonURL);
  int httpCode = http.GET();
  std::vector<String> tempFilenames;

  if (httpCode > 0) {
    String payload = http.getString();
    JsonDocument doc;
    deserializeJson(doc, payload);

    JsonArray arr = doc.as<JsonArray>();
    for (String filename : arr) {
      tempFilenames.push_back(filename);
    }
    Serial.println("Bin list fetched");
  } else {
    Serial.println("Error on HTTP request");
  }

  http.end();
  for (String& filename : tempFilenames) {
    Serial.println(filename);
  }
  return tempFilenames;
}

void doFetchBinList() {
  Serial.println("DoFetchBinList");
  bin_list = fetchAndParseJSON();
  saveLatestFirmware();
  fwUpdateAvailable = firstIsNewer(latestFirmware, currentFirmware);
}

void saveLatestFirmware() {
  Firmware firmware;
  for (String& filename : bin_list) {
    if (filename.startsWith("latest")) continue;
    Firmware parsedFirmware = parseFirmwareVersion(filename);
    if (firstIsNewer(parsedFirmware, firmware)) {
      firmware = parsedFirmware;
    }
  }
  latestFirmware = firmware;
  Serial.print("Latest firmware version: ");
  Serial.print(latestFirmware.major);
  Serial.print(".");
  Serial.print(latestFirmware.minor);
  Serial.print(".");
  Serial.println(latestFirmware.patch);
}

bool firstIsNewer(Firmware first, Firmware second) {
  if (first.major > second.major) return true;
  if (first.major == second.major) {
    if (first.minor > second.minor) return true;
    if (first.minor == second.minor) {
      if (first.patch > second.patch) return true;
    }
  }
  return false;
}

// Home District Json Parsing
void parseHomeDistrictJson() {
  // Skip parsing if home alert time is disabled or less then 5 sec from last sync
  if ((timeClient.getEpochTime() - lastHomeDistrictSync <= 5) || settings.home_alert_time == 0) return;
  // Save sync time
  lastHomeDistrictSync = timeClient.getEpochTime();

  String jsonURLString = "http://" + settings.serverhost + "/map/region/v1/" + settings.home_district;
  Serial.println("Http request to: " + jsonURLString);
  const char* jsonURL = jsonURLString.c_str();
  http.begin(jsonURL);
  int httpCode = http.GET();

  if (httpCode == 200) {
    String payload = http.getString();
    Serial.println("Http Success, payload: " + payload);

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);
    if (error) {
      Serial.println("Deserialization error: ");
      Serial.println(error.f_str());
      return;
    }
    Serial.println("Json parsed!");
    bool alertNow = doc["data"]["alertnow"];
    Serial.println(alertNow);
    if (alertNow) {
      homeAlertStart = doc["data"]["changed"];
      Serial.println(homeAlertStart);
    } else {
      homeAlertStart = 0;
    }
  } else {
    Serial.println("Error on HTTP request:" + httpCode);
  }
}

void doUpdate() {
  if (initUpdate) {
    initUpdate = false;
    downloadAndUpdateFw(settings.bin_name);
  }
}

void downloadAndUpdateFw(String binFileName) {
  String firmwareUrlString = "http://" + settings.serverhost + ":" + settings.updateport + "/" + binFileName + "";
  const char* firmwareUrl = firmwareUrlString.c_str();
  http.begin(firmwareUrl);
  Serial.println(firmwareUrl);
  int httpCode = http.GET();
  if (httpCode == 200) {
    int contentLength = http.getSize();
    bool canBegin = Update.begin(contentLength);
    if (canBegin) {
      showServiceMessage("Оновлення..");
      size_t written = Update.writeStream(http.getStream());
      if (written == contentLength) {
        Serial.println("Written : " + String(written) + " successfully");
      } else {
        Serial.println("Written only : " + String(written) + "/" + String(contentLength) + "");
      }
      if (Update.end()) {
        Serial.println("OTA done!");
        if (Update.isFinished()) {
          Serial.println("Update successfully completed. Rebooting.");
          ESP.restart();
        } else {
          Serial.println("Update not finished? Something went wrong!");
        }
      } else {
        Serial.println("Error Occurred. Error #: " + String(Update.getError()));
      }
    } else {
      Serial.println("Not enough space to begin OTA");
    }
  } else {
    Serial.print("Error on HTTP request: ");
    Serial.println(httpCode);
  }
  http.end();
}
//--Update end

//--Service
void checkServicePins() {
  if (!settings.legacy) {
    if (settings.service_diodes_mode) {
      Serial.println("Dioded enabled");
      servicePin(settings.powerpin, HIGH, true);
      if (WiFi.status() != WL_CONNECTED) {
        servicePin(settings.wifipin, LOW, true);
      } else {
        servicePin(settings.wifipin, HIGH, true);
      }
      if (!mqtt.isConnected()) {
        servicePin(settings.hapin, LOW, true);
      } else {
        servicePin(settings.hapin, HIGH, true);
      }
      if (!client_tcp.connected() or tcpReconnect) {
        servicePin(settings.datapin, LOW, true);
      } else {
        servicePin(settings.datapin, HIGH, true);
      }
    } else {
      Serial.println("Dioded disables");
      servicePin(settings.powerpin, LOW, true);
      servicePin(settings.wifipin, LOW, true);
      servicePin(settings.hapin, LOW, true);
      servicePin(settings.datapin, LOW, true);
    }
  }
}


//--Service end

// for display chars testing purposes
// int startSymbol = 0;
//--Button start
void buttonUpdate() {
  if (digitalRead(settings.buttonpin) == HIGH) {
    buttonPressStart = millis();
    if (!isPressed) {
      Serial.println("Pressed");
      Serial.print("button_mode: ");
      Serial.println(settings.button_mode);
      isPressed = true;
      // for display chars testing purposes
      // startSymbol ++;
      if (settings.new_fw_notification == 1 && fwUpdateAvailable && settings.button_mode != 0) {
        downloadAndUpdateFw("latest.bin");
      } else if (settings.button_mode == 1) {
        mapModeSwitch();
      } else if (settings.button_mode == 2) {
        displayModeSwitch();
      }
    }
  }
  if (millis() - buttonPressStart > settings.buttontime) {
    isPressed = false;
  }
}

void mapModeSwitch() {
  settings.map_mode += 1;
  if (settings.map_mode > 4) {
    settings.map_mode = 0;
  }
  saveMapMode();
}

void saveMapMode() {
  Serial.print("map_mode changed to: ");
  Serial.println(settings.map_mode);
  preferences.begin("storage", false);
  preferences.putInt("mapmode", settings.map_mode);
  preferences.end();
  Serial.println("map_mode commited to preferences");
  if (enableHA) {
    haMapMode.setState(settings.map_mode);
    haMapModeCurrent.setValue(mapModes[getCurrentMapMode()].c_str());
  }
  showServiceMessage(mapModes[settings.map_mode], "Режим мапи:");
  // update to selected mapMode
  mapCycle();
}

void displayModeSwitch() {
  switch (settings.display_mode) {
    case 0:
      // passthrough
    case 1:
      settings.display_mode += 1;
      break;
    case 2:
      settings.display_mode = 9;
      break;
    case 9:
      // passthrough
    default:
      settings.display_mode = 0;
      break;
  }
  saveDisplayMode();
}

void saveDisplayMode() {
  Serial.print("display_mode changed to: ");
  Serial.println(settings.display_mode);
  preferences.begin("storage", false);
  preferences.putInt("dm", settings.display_mode);
  preferences.end();
  Serial.println("display_mode commited to preferences");
  if (enableHA) {
    haDisplayMode.setState(getHaDisplayMode(settings.display_mode));
  }
  showServiceMessage(displayModes[getHaDisplayMode(settings.display_mode)], "Режим дисплея:", 1000);
  // update to selected displayMode
  displayCycle();
}
//--Button end

void saveHomeDistrict() {
  Serial.print("home_district changed to: ");
  Serial.println(settings.home_district);
  preferences.begin("storage", false);
  preferences.putInt("hd", settings.home_district);
  preferences.end();
  Serial.print("home_district commited to preferences");
  if (enableHA) {
    haHomeDistrict.setValue(districtsAlphabetical[numDistrictToAlphabet(settings.home_district)].c_str());
    haMapModeCurrent.setValue(mapModes[getCurrentMapMode()].c_str());
  }
  homeAlertStart = 0;
  parseHomeDistrictJson();
  showServiceMessage(districts[settings.home_district], "Домашній регіон:", 2000);
}

//--Display start
void DisplayCenter(String text, int bound, int text_size) {
  int16_t x;
  int16_t y;
  uint16_t width;
  uint16_t height;
  String utf8Text = utf8cyr(text);
  display.setCursor(0, 0);
  display.setTextSize(text_size);
  display.getTextBounds(utf8Text, 0, 0, &x, &y, &width, &height);
  display.setCursor(((settings.display_width - width) / 2), ((settings.display_height - height) / 2) + bound);
  display.println(utf8Text);
  display.display();
}

int getTextSizeToFitDisplay(String text) {
  int16_t x;
  int16_t y;
  uint16_t textWidth;
  uint16_t height;

  display.setTextWrap(false);
  String utf8Text = utf8cyr(text);
  display.setCursor(0, 0);
  display.setTextSize(3);
  display.getTextBounds(utf8Text, 0, 0, &x, &y, &textWidth, &height);

  if (display.width() >= textWidth) {
    display.setTextWrap(true);
    return 3;
  }

  display.setTextSize(2);
  display.getTextBounds(utf8Text, 0, 0, &x, &y, &textWidth, &height);

  display.setTextWrap(true);
  if (display.width() >= textWidth) {
    return 2;
  } else {
    return 1;
  }
}

String utf8cyr(String source) {
  int i, k;
  String target;
  unsigned char n;
  char m[2] = { '0', '\0' };

  k = source.length();
  i = 0;
  while (i < k) {
    n = source[i];
    i++;
    if (n >= 0xC0) {
      switch (n) {
        case 0xD0: {
          n = source[i]; i++;
          if (n == 0x81) { n = 0xA8; break; }       //  Ё
          if (n == 0x84) { n = 0xAA; break; }       //  Є
          if (n == 0x86) { n = 0xB1; break; }       //  І
          if (n == 0x87) { n = 0xAF; break; }       //  Ї
          if (n >= 0x90 && n <= 0xBF) n = n + 0x2F; break;
        }
        case 0xD1: {
          n = source[i]; i++;
          if (n == 0x91) { n = 0xB7; break; }       //  ё
          if (n == 0x94) { n = 0xB9; break; }       //  є
          if (n == 0x96) { n = 0xB2; break; }       //  і
          if (n == 0x97) { n = 0xBE; break; }       //  ї
          if (n >= 0x80 && n <= 0x8F) n = n + 0x6F; break;
        }
        case 0xD2: {
          n = source[i]; i++;
          if (n == 0x90) { n = 0xA5; break; }       //  Ґ
          if (n == 0x91) { n = 0xB3; break; }       //  ґ
        }
      }
    }
    m[0] = n;
    target = target + String(m);
  }
  return target;
}

void showServiceMessage(String message) {
  showServiceMessage(message, "");
}

void showServiceMessage(String message, int duration) {
  showServiceMessage(message, "", duration);
}

void showServiceMessage(String message, String title) {
  showServiceMessage(message, title, 2000);
}

void showServiceMessage(String message, String title, int duration) {
  serviceMessage.title = title;
  serviceMessage.message = message;
  serviceMessage.textSize = getTextSizeToFitDisplay(message);
  serviceMessage.endTime = millis() + duration;
  serviceMessage.expired = false;
  displayCycle();
}

void serviceMessageUpdate() {
  if (!serviceMessage.expired && millis() > serviceMessage.endTime) {
    serviceMessage.expired = true;
  }
}

void displayCycle() {
  // for display chars testing purposes
  // display.clearDisplay();
  // String str = "";
  // str += startSymbol;
  // str += "-";
  // str += (char) startSymbol;
  // DisplayCenter(str, 7, 2);
  // return;

  // update service message expiration
  serviceMessageUpdate();

  // Show service message if not expired
  if (!serviceMessage.expired) {
    displayServiceMessage(serviceMessage);
    return;
  }

  // Show Home Alert Time Info if enabled in settings and we have alert start time
  if (homeAlertStart > 0 && settings.home_alert_time == 1) {
    showHomeAlertInfo();
    return;
  }
  // Show New Firmware Notification if enabled in settings and New firmware available
  if (settings.new_fw_notification == 1 && fwUpdateAvailable) {
    showNewFirmwareNotification();
    return;
  }

  displayByMode(settings.display_mode);
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
    // Display Mode Switching
    case 9:
      displayByMode(calculateCurrentDisplayMode());
      break;
    // Unknown Display Mode, clearing display...
    default:
      clearDisplay();
      break;
  }
}

void clearDisplay() {
  display.clearDisplay();
  display.display();
}

void displayServiceMessage(ServiceMessage message) {
  display.clearDisplay();
  int bound = 0;
  if (message.title.length() > 0) {
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.println(utf8cyr(message.title));
    bound = 7;
  }

  DisplayCenter(message.message, bound, message.textSize);
}

void showHomeAlertInfo() {
  int toggleTime = 5;  // seconds
  int remainder = timeClient.getSeconds() % (toggleTime * 2);
  display.setCursor(0, 0);
  display.clearDisplay();
  display.setTextSize(1);
  if (remainder < toggleTime) {
    display.println(utf8cyr("Тривога триває:"));
  } else {
    display.println(utf8cyr(districts[settings.home_district]));
  }
  unsigned long timerSeconds = timeClient.getEpochTime() - homeAlertStart - timeOffset;
  unsigned long seconds = timerSeconds;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  if (hours >= 99) {
    DisplayCenter("99+ год.", 7, 2);
    return;
  }
  seconds %= 60;
  minutes %= 60;
  String divider = getDivider();
  String alertTime = "";
  if (hours > 0) {
    if (hours < 10) alertTime += "0";
    alertTime += hours;
    alertTime += divider;
  }
  if (minutes < 10) alertTime += "0";
  alertTime += minutes;
  if (hours == 0) {
    alertTime += divider;
    if (seconds < 10) alertTime += "0";
    alertTime += seconds;
  }
  DisplayCenter(alertTime, 7, 3);
}

void showNewFirmwareNotification() {
  int toggleTime = 5;  // seconds
  int remainder = timeClient.getSeconds() % (toggleTime * 2);
  display.setCursor(0, 0);
  display.clearDisplay();
  display.setTextSize(1);
  if (remainder < toggleTime) {
    display.println(utf8cyr("Доступне оновлення:"));
    String version = "v";
    version += latestFirmware.major;
    version += ".";
    version += latestFirmware.minor;
    if (latestFirmware.patch > 0) {
      version += ".";
      version += latestFirmware.patch;
    }
    DisplayCenter(version, 7, 3);
  } else if (settings.button_mode == 0) {
    display.println(utf8cyr("Введіть у браузері:"));
    DisplayCenter(WiFi.localIP().toString(), 7, 1);
  } else {
    display.println(utf8cyr("Для оновлення"));
    String text = "натисніть кнопку ";
    text += (char)24;
    DisplayCenter(text, 7, 1);
  }
}

void showClock() {
  int hour = timeClient.getHours();
  int minute = timeClient.getMinutes();
  int day = timeClient.getDay();
  String daysOfWeek[] = { "Heдiля", "Пoнeдiлoк", "Biвтopoк", "Середа", "Четвер", "П\'ятниця", "Субота" };
  display.setCursor(0, 0);
  display.clearDisplay();
  display.setTextSize(1);
  display.println(utf8cyr(daysOfWeek[day]));
  String time = "";
  if (hour < 10) time += "0";
  time += hour;
  time += getDivider();
  if (minute < 10) time += "0";
  time += minute;
  DisplayCenter(time, 7, 3);
}

void showTemp() {
  display.setCursor(0, 0);
  display.clearDisplay();
  display.setTextSize(1);
  display.println(utf8cyr(districts[settings.home_district]));
  String temp = "";
  char roundedTemp[4];
  int position = calculateOffset(settings.home_district);
  dtostrf(weather_leds[position], 3, 1, roundedTemp);
  temp += roundedTemp;
  temp += (char)128;
  temp += "C";
  DisplayCenter(temp, 7, 3);
}

int calculateCurrentDisplayMode() {
  int toggleTime = settings.display_mode_time;
  int remainder = timeClient.getEpochTime() % (toggleTime * 2);
  if (remainder < toggleTime) {
    // Display Mode Clock
    return 1;
  } else {
    // Display Mode Temperature
    return 2;
  }
}

String getDivider() {
  // Change every second
  if (timeClient.getSeconds() % 2 == 0) {
    return ":";
  } else {
    return " ";
  }
}
//--Display end

Firmware parseFirmwareVersion(String version) {

  String parts[4];
  int count = 0;

  while (version.length() > 0) {
    int index = version.indexOf('.');
    if (index == -1) {
      // No dot found
      parts[count++] = version;
      break;
    } else {
      parts[count++] = version.substring(0, index);
      version = version.substring(index + 1);
    }
  }

  Firmware firmware;

  firmware.major = atoi(parts[0].c_str());
  firmware.minor = atoi(parts[1].c_str());
  if (parts[2] == "bin" || parts[2] == NULL) {
    firmware.patch = 0;
  } else {
    firmware.patch = atoi(parts[2].c_str());
  }
  return firmware;
}

//--Web server start
void setupRouting() {
  Serial.println("Init WebServer");
  webserver.on("/", HTTP_GET, handleRoot);
  webserver.on("/save", HTTP_POST, handleSave);
  webserver.on("/update", HTTP_POST, handleUpdate);
  webserver.begin();
  Serial.println("Webportal running");
}


void handleRoot(AsyncWebServerRequest* request) {
  String html;
  html += "<!DOCTYPE html>";
  html += "<html lang='en'>";
  html += "<head>";
  html += "    <meta charset='UTF-8'>";
  html += "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "    <title>" + settings.devicename + "</title>";
  html += "    <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'>";
  html += "    <style>";
  html += "        body { background-color: #4396ff; }";
  html += "        .btn {margin-bottom: 0.25rem;}";
  html += "        .container { padding: 20px; }";
  html += "        label { font-weight: bold; }";
  html += "        #sliderValue1, #sliderValue2, #sliderValue3, #sliderValue4 { font-weight: bold; color: #070505; }";
  html += "        .color-box { width: 30px; height: 30px; display: inline-block; margin-left: 10px; border: 1px solid #ccc; vertical-align: middle; }";
  html += "        .full-screen-img {width: 100%;height: 100%;object-fit: cover;}";
  html += "        .box_yellow { background-color: #fff0d5; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,.1); }";
  html += "    </style>";
  html += "</head>";
  html += "<body>";
  html += "    <div class='container mt-3'  id='accordion'>";
  html += "        <h2 class='text-center'>" + settings.devicedescription + " ";
  html += settings.softwareversion;
  html += "        </h2>";
  html += "        <div class='row'>";
  html += "            <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                <div class='box_yellow col-md-12 mt-2'>";
  switch (getCurrentMapMode()) {
    case 2:
      html += "                <img class='full-screen-img' src='http://alerts.net.ua/weather_map.png'>";
      break;
    case 3:
      html += "                <img class='full-screen-img' src='http://alerts.net.ua/flag_map.png'>";
      break;
    case 4:
      html += "                <img class='full-screen-img' src='http://alerts.net.ua/random_map.png'>";
      break;
    case 0:
      html += "                <img class='full-screen-img' src='http://alerts.net.ua/off_map.png'>";
      break;
    default:
      html += "                <img class='full-screen-img' src='http://alerts.net.ua/alerts_map.png'>";
  }
  html += "                </div>";
  html += "              </div>";
  html += "            </div>";
  html += "        </div>";
  html += "        <div class='row'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <h5>Локальна IP-адреса: ";
  html += WiFi.localIP().toString();
  html += "                    </h5>";
  html += "                </div>";
  html += "              </div>";
  html += "            </div>";
  html += "        </div>";
  html += "        <div class='row'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#collapseBrightness' aria-expanded='false' aria-controls='collapseBrightness'>";
  html += "                         Яскравість";
  html += "                    </button>";
  html += "                    <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#collapseColors' aria-expanded='false' aria-controls='collapseColors'>";
  html += "                         Кольори";
  html += "                    </button>";
  html += "                    <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#collapseWeather' aria-expanded='false' aria-controls='collapseWeather'>";
  html += "                         Погода";
  html += "                    </button>";
  html += "                    <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#collapseModes' aria-expanded='false' aria-controls='collapseModes'>";
  html += "                         Режими";
  html += "                    </button>";
  html += "                    <button class='btn btn-warning' type='button' data-toggle='collapse' data-target='#collapseTech' aria-expanded='false' aria-controls='collapseTech'>";
  html += "                         DEV";
  html += "                    </button>";
  html += "                    <button class='btn btn-danger' type='button' data-toggle='collapse' data-target='#collapseFirmware' aria-expanded='false' aria-controls='collapseFirmware'>";
  html += "                         Прошивка";
  html += "                    </button>";
  html += "                </div>";
  html += "              </div>";
  html += "            </div>";
  html += "        </div>";
  html += "        <form action='/save' method='POST'>";
  html += "        <div class='row collapse' id='collapseBrightness' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Загальна: <span id='sliderValue1'>" + String(settings.brightness) + "</span>%</label>";
  html += "                        <input type='range' name='brightness' class='form-control-range' id='slider1' min='0' max='100' value='" + String(settings.brightness) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Денна: <span id='sliderValue13'>" + String(settings.brightness_day) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_day' class='form-control-range' id='slider13' min='0' max='100' value='" + String(settings.brightness_day) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Нічна: <span id='sliderValue14'>" + String(settings.brightness_night) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_night' class='form-control-range' id='slider14' min='0' max='100' value='" + String(settings.brightness_night) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Початок дня: <span id='sliderValue15'>" + String(settings.day_start) + "</span> годин</label>";
  html += "                        <input type='range' name='day_start' class='form-control-range' id='slider15' min='0' max='24' value='" + String(settings.day_start) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Початок ночі: <span id='sliderValue16'>" + String(settings.night_start) + "</span> годин</label>";
  html += "                        <input type='range' name='night_start' class='form-control-range' id='slider16' min='0' max='24' value='" + String(settings.night_start) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group form-check'>";
  html += "                        <input name='brightness_auto' type='checkbox' class='form-check-input' id='checkbox1'";
  if (settings.brightness_auto == 1) html += " checked";
  html += ">";
  html += "                        <label class='form-check-label' for='checkbox1'>";
  html += "                          Змінювати яскравість (день-ніч по годинам)";
  html += "                        </label>";
  html += "                    </div>";
  if (!settings.legacy) {
    html += "                  <div class='form-group form-check'>";
    html += "                      <input name='sdm_auto' type='checkbox' class='form-check-input' id='checkbox2'";
    if (settings.sdm_auto == 1) html += " checked";
    html += ">";
    html += "                      <label class='form-check-label' for='checkbox2'>";
    html += "                        Вимикати сервісні діоди в нічний час";
    html += "                      </label>";
    html += "                  </div>";
  }
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider9'>Області з тривогами: <span id='sliderValue9'>" + String(settings.brightness_alert) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_alert' class='form-control-range' id='slider9' min='0' max='100' value='" + String(settings.brightness_alert) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider10'>Області без тривог: <span id='sliderValue10'>" + String(settings.brightness_clear) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_clear' class='form-control-range' id='slider10' min='0' max='100' value='" + String(settings.brightness_clear) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider11'>Нові тривоги: <span id='sliderValue11'>" + String(settings.brightness_new_alert) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_new_alert' class='form-control-range' id='slider11' min='0' max='100' value='" + String(settings.brightness_new_alert) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider12'>Відбій тривог: <span id='sliderValue12'>" + String(settings.brightness_alert_over) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_alert_over' class='form-control-range' id='slider12' min='0' max='100' value='" + String(settings.brightness_alert_over) + "'>";
  html += "                    </div>";
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/save' method='POST'>";
  html += "        <div class='row collapse' id='collapseColors' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider3'>Області з тривогами: <span id='sliderValue3'>" + String(settings.color_alert) + "</span></label>";
  html += "                        <input type='range' name='color_alert' class='form-control-range' id='slider3' min='0' max='360' value='" + String(settings.color_alert) + "'>";
  html += "                        <div class='color-box' id='colorBox1'></div>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider4'>Області без тривог: <span id='sliderValue4'>" + String(settings.color_clear) + "</span></label>";
  html += "                        <input type='range' name='color_clear' class='form-control-range' id='slider4' min='0' max='360' value='" + String(settings.color_clear) + "'>";
  html += "                        <div class='color-box' id='colorBox2'></div>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider5'>Нові тривоги: <span id='sliderValue5'>" + String(settings.color_new_alert) + "</span></label>";
  html += "                        <input type='range' name='color_new_alert' class='form-control-range' id='slider5' min='0' max='360' value='" + String(settings.color_new_alert) + "'>";
  html += "                        <div class='color-box' id='colorBox3'></div>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider6'>Відбій тривог: <span id='sliderValue6'>" + String(settings.color_alert_over) + "</span></label>";
  html += "                        <input type='range' name='color_alert_over' class='form-control-range' id='slider6' min='0' max='360' value='" + String(settings.color_alert_over) + "'>";
  html += "                        <div class='color-box' id='colorBox4'></div>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider7'>Домашній регіон: <span id='sliderValue7'>" + String(settings.color_home_district) + "</span></label>";
  html += "                        <input type='range' name='color_home_district' class='form-control-range' id='slider7' min='0' max='360' value='" + String(settings.color_home_district) + "'>";
  html += "                        <div class='color-box' id='colorBox5'></div>";
  html += "                    </div>";
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/save' method='POST'>";
  html += "        <div class='row collapse' id='collapseWeather' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider18'>Нижній рівень температури: <span id='sliderValue18'>" + String(settings.weather_min_temp) + "</span>°C</label>";
  html += "                        <input type='range' name='weather_min_temp' class='form-control-range' id='slider18' min='-20' max='10' value='" + String(settings.weather_min_temp) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider8'>Верхній рівень температури: <span id='sliderValue8'>" + String(settings.weather_max_temp) + "</span>°C</label>";
  html += "                        <input type='range' name='weather_max_temp' class='form-control-range' id='slider8' min='11' max='40' value='" + String(settings.weather_max_temp) + "'>";
  html += "                    </div>";
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/save' method='POST'>";
  html += "        <div class='row collapse' id='collapseModes' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  if (settings.legacy) {
    html += "                    <div class='form-group'>";
    html += "                        <label for='selectBox1'>Режим діода 'Київська область'</label>";
    html += "                        <select name='kyiv_district_mode' class='form-control' id='selectBox1'>";
    html += "<option value='1'";
    if (settings.kyiv_district_mode == 1) html += " selected";
    html += ">Київська область</option>";
    html += "<option value='2'";
    if (settings.kyiv_district_mode == 2) html += " selected";
    html += ">Київ</option>";
    html += "<option value='3'";
    if (settings.kyiv_district_mode == 3) html += " selected";
    html += ">Київська область + Київ (2 діода)</option>";
    html += "<option value='4'";
    if (settings.kyiv_district_mode == 4) html += " selected";
    html += ">Київська область + Київ (1 діод)</option>";
    html += "                        </select>";
    html += "                    </div>";
  }
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox2'>Режим мапи</label>";
  html += "                        <select name='map_mode' class='form-control' id='selectBox2'>";
  for (int i = 0; i < mapModes.size(); i++) {
    html += "<option value='";
    html += i;
    html += "'";
    if (settings.map_mode == i) html += " selected";
    html += ">";
    html += mapModes[i];
    html += "</option>";
  }
  html += "                        </select>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox5'>Режим дисплея</label>";
  html += "                        <select name='display_mode' class='form-control' id='selectBox5'>";
  for (int i = 0; i < displayModes.size(); i++) {
    int num = getRealDisplayMode(i);
    html += "<option value='";
    html += num;
    html += "'";
    if (settings.display_mode == num) html += " selected";
    html += ">";
    html += displayModes[i];
    html += "</option>";
  }
  html += "                        </select>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider17'>Час перемикання дисплея: <span id='sliderValue17'>" + String(settings.display_mode_time) + "</span> секунд</label>";
  html += "                        <input type='range' name='display_mode_time' class='form-control-range' id='slider17' min='1' max='60' value='" + String(settings.display_mode_time) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox6'>Режим кнопки</label>";
  html += "                        <select name='button_mode' class='form-control' id='selectBox6'>";
  html += "<option value='0'";
  if (settings.button_mode == 0) html += " selected";
  html += ">Вимкнений</option>";
  html += "<option value='1'";
  if (settings.button_mode == 1) html += " selected";
  html += ">Перемикання режимів мапи</option>";
  html += "<option value='2'";
  if (settings.button_mode == 2) html += " selected";
  html += ">Перемикання режимів дисплея</option>";
  html += "                        </select>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox3'>Домашній регіон</label>";
  html += "                        <select name='home_district' class='form-control' id='selectBox3'>";
  for (int alphabet = 0; alphabet < districtsAlphabetical.size(); alphabet++) {
    int num = alphabetDistrictToNum(alphabet);
    html += "<option value='";
    html += num;
    html += "'";
    if (settings.home_district == num) html += " selected";
    html += ">";
    html += districtsAlphabetical[alphabet];
    html += "</option>";
  }
  html += "                        </select>";
  html += "                    </div>";
  html += "                    <div class='form-group form-check'>";
  html += "                        <input name='home_alert_time' type='checkbox' class='form-check-input' id='checkbox3'";
  if (settings.home_alert_time == 1) html += " checked";
  html += ">";
  html += "                        <label class='form-check-label' for='checkbox3'>";
  html += "                          Показувати тривалість тривоги у дом. регіоні";
  html += "                        </label>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox4'>Відображення на мапі нових тривог та відбою</label>";
  html += "                        <select name='alarms_notify_mode' class='form-control' id='selectBox4'>";
  html += "<option value='0'";
  if (settings.alarms_notify_mode == 0) html += " selected";
  html += ">Вимкнено</option>";
  html += "<option value='1'";
  if (settings.alarms_notify_mode == 1) html += " selected";
  html += ">Колір</option>";
  html += "<option value='2'";
  if (settings.alarms_notify_mode == 2) html += " selected";
  html += ">Колір + зміна яскравості</option>";
  html += "                        </select>";
  html += "                    </div>";
  if (settings.legacy) {
    html += "                    <div class='form-group'>";
    html += "                        <label for='selectBox7'>Розмір дисплея</label>";
    html += "                        <select name='display_height' class='form-control' id='selectBox7'>";
    html += "<option value='32'";
    if (settings.display_height == 32) html += " selected";
    html += ">128*32</option>";
    html += "<option value='64'";
    if (settings.display_height == 64) html += " selected";
    html += ">128*64</option>";
    html += "                        </select>";
    html += "                    </div>";
  }
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox9'>Перемикання мапи в режим тривоги у випадку тривоги у домашньому регіоні</label>";
  html += "                        <select name='alarms_auto_switch' class='form-control' id='selectBox9'>";
  for (int i = 0; i < autoAlarms.size(); i++) {
    html += "<option value='";
    html += i;
    html += "'";
    if (settings.alarms_auto_switch == i) html += " selected";
    html += ">";
    html += autoAlarms[i];
    html += "</option>";
  }
  html += "                        </select>";
  html += "                    </div>";
  if (!settings.legacy) {
    html += "                    <div class='form-group form-check'>";
    html += "                        <input name='service_diodes_mode' type='checkbox' class='form-check-input' id='checkbox4'";
    if (settings.service_diodes_mode == 1) html += " checked";
    html += ">";
    html += "                        <label class='form-check-label' for='checkbox4'>";
    html += "                          Ввімкнути сервісні діоди на задній частині плати";
    html += "                        </label>";
    html += "                    </div>";
  }
  html += "                      <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/save' method='POST'>";
  html += "        <div class='row collapse' id='collapseTech' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox8'>Режим прошивки</label>";
  html += "                        <select name='legacy' class='form-control' id='selectBox8'>";
  html += "<option value='0'";
  if (settings.legacy == 1) html += " selected";
  html += ">Плата JAAM</option>";
  html += "<option value='1'";
  if (settings.legacy == 1) html += " selected";
  html += ">Класична (початок на Закарпатті)</option>";
  html += "                        </select>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField1'> Адреса mqtt-сервера Home Assistant</label>";
  html += "                        <input type='text' name='ha_brokeraddress' class='form-control' id='inputField1' placeholder='' value='" + String(settings.ha_brokeraddress) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField2'>Порт mqtt-сервера Home Assistant</label>";
  html += "                        <input type='text' name='ha_mqttport' class='form-control' id='inputField2' value='" + String(settings.ha_mqttport) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField3'>Юзер mqtt-сервера Home Assistant</label>";
  html += "                        <input type='text' name='ha_mqttuser' class='form-control' id='inputField3' value='" + String(settings.ha_mqttuser) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField4'>Пароль mqtt-сервера Home Assistant</label>";
  html += "                        <input type='text' name='ha_mqttpassword' class='form-control' id='inputField4' value='" + String(settings.ha_mqttpassword) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField7'>Адреса сервера даних</label>";
  html += "                        <input type='text' name='serverhost' class='form-control' id='inputField7' value='" + String(settings.serverhost) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField8'>Порт TCP сервера даних</label>";
  html += "                        <input type='text' name='tcpport' class='form-control' id='inputField8' value='" + String(settings.tcpport) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField8'>Порт сервера прошивок</label>";
  html += "                        <input type='text' name='updateport' class='form-control' id='inputField8' value='" + String(settings.updateport) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField9'>Назва пристрою</label>";
  html += "                        <input type='text' name='devicename' class='form-control' id='inputField9' value='" + String(settings.devicename) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField10'>Опис пристрою</label>";
  html += "                        <input type='text' name='devicedescription' class='form-control' id='inputField10' value='" + String(settings.devicedescription) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='inputField11'>Локальна адреса в мережі (" + String(settings.broadcastname) + ".local) </label>";
  html += "                        <input type='text' name='broadcastname' class='form-control' id='inputField11' value='" + String(settings.broadcastname) + "'>";
  html += "                    </div>";
  if (settings.legacy) {
    html += "                    <div class='form-group'>";
    html += "                        <label for='inputField5'>Керуючий пін лед-стрічки</label>";
    html += "                        <input type='text' name='pixelpin' class='form-control' id='inputField5' value='" + String(settings.pixelpin) + "'>";
    html += "                    </div>";
    html += "                    <div class='form-group'>";
    html += "                        <label for='inputField5'>Керуючий пін кнопки</label>";
    html += "                        <input type='text' name='buttonpin' class='form-control' id='inputField6' value='" + String(settings.buttonpin) + "'>";
    html += "                    </div>";
  }
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <div class='row collapse' id='collapseFirmware' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                       <form action='/save' method='POST'>";
  html += "                          <div class='form-group form-check'>";
  html += "                              <input name='new_fw_notification' type='checkbox' class='form-check-input' id='checkbox5'";
  if (settings.new_fw_notification == 1) html += " checked";
  html += ">";
  html += "                              <label class='form-check-label' for='checkbox5'>";
  html += "                                  Сповіщення про нові прошивки на екрані";
  html += "                              </label>";
  html += "                          </div>";
  html += "                          <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                       </form>";
  html += "                       <form action='/update' method='POST'>";
  html += "                          <div class='form-group'>";
  html += "                              <label for='selectBox9'>Файл прошивки</label>";
  html += "                              <select name='bin_name' class='form-control' id='selectBox9'>";
  for (String& filename : bin_list) {
    html += "<option value='" + filename + "'";
    if (settings.bin_name == filename) html += " selected";
    html += ">" + filename + "</option>";
  }
  html += "                              </select>";
  html += "                          </div>";
  html += "                          <button type='submit' class='btn btn-danger'>ОНОВИТИ ПРОШИВКУ</button>";
  html += "                       </form>";
  html += "                    </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "    </div>";
  html += "    </form>";
  html += "    <script src='https://code.jquery.com/jquery-3.5.1.slim.min.js'></script>";
  html += "    <script src='https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.3/dist/umd/popper.min.js'></script>";
  html += "    <script src='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js'></script>";
  html += "    <script>";
  html += "        const sliders = ['slider1', 'slider3', 'slider4', 'slider5', 'slider6', 'slider7', 'slider8', 'slider9', 'slider10', 'slider11', 'slider12', 'slider13', 'slider14', 'slider15', 'slider16', 'slider17', 'slider18'];";
  html += "";
  html += "        sliders.forEach(slider => {";
  html += "            const sliderElem = document.getElementById(slider);";
  html += "            const sliderValueElem = document.getElementById(slider.replace('slider', 'sliderValue'));";
  html += "            sliderElem.addEventListener('input', () => sliderValueElem.textContent = sliderElem.value);";
  html += "        });";
  html += "";
  html += "        function updateColorBox(boxId, hue) {";
  html += "            const rgbColor = hsbToRgb(hue, 100, 100);";
  html += "            document.getElementById(boxId).style.backgroundColor = `rgb(${rgbColor.r}, ${rgbColor.g}, ${rgbColor.b})`;";
  html += "        }";
  html += "";
  html += "        const initialHue1 = parseInt(slider3.value);";
  html += "        const initialRgbColor1 = hsbToRgb(initialHue1, 100, 100);";
  html += "        document.getElementById('colorBox1').style.backgroundColor = `rgb(${initialRgbColor1.r}, ${initialRgbColor1.g}, ${initialRgbColor1.b})`;";
  html += "";
  html += "        const initialHue2 = parseInt(slider4.value);";
  html += "        const initialRgbColor2 = hsbToRgb(initialHue2, 100, 100);";
  html += "        document.getElementById('colorBox2').style.backgroundColor = `rgb(${initialRgbColor2.r}, ${initialRgbColor2.g}, ${initialRgbColor2.b})`;";
  html += "";
  html += "        const initialHue3 = parseInt(slider5.value);";
  html += "        const initialRgbColor3 = hsbToRgb(initialHue3, 100, 100);";
  html += "        document.getElementById('colorBox3').style.backgroundColor = `rgb(${initialRgbColor3.r}, ${initialRgbColor3.g}, ${initialRgbColor3.b})`;";
  html += "";
  html += "        const initialHue4 = parseInt(slider6.value);";
  html += "        const initialRgbColor4 = hsbToRgb(initialHue4, 100, 100);";
  html += "        document.getElementById('colorBox4').style.backgroundColor = `rgb(${initialRgbColor4.r}, ${initialRgbColor4.g}, ${initialRgbColor4.b})`;";
  html += "";
  html += "        const initialHue5 = parseInt(slider7.value);";
  html += "        const initialRgbColor5 = hsbToRgb(initialHue5, 100, 100);";
  html += "        document.getElementById('colorBox5').style.backgroundColor = `rgb(${initialRgbColor5.r}, ${initialRgbColor5.g}, ${initialRgbColor5.b})`;";
  html += "";
  html += "        function hsbToRgb(h, s, b) {";
  html += "            h /= 360;";
  html += "            s /= 100;";
  html += "            b /= 100;";
  html += "";
  html += "            let r, g, bl;";
  html += "";
  html += "            if (s === 0) {";
  html += "                r = g = bl = b;";
  html += "            } else {";
  html += "                const i = Math.floor(h * 6);";
  html += "                const f = h * 6 - i;";
  html += "                const p = b * (1 - s);";
  html += "                const q = b * (1 - f * s);";
  html += "                const t = b * (1 - (1 - f) * s);";
  html += "";
  html += "                switch (i % 6) {";
  html += "                    case 0: r = b, g = t, bl = p; break;";
  html += "                    case 1: r = q, g = b, bl = p; break;";
  html += "                    case 2: r = p, g = b, bl = t; break;";
  html += "                    case 3: r = p, g = q, bl = b; break;";
  html += "                    case 4: r = t, g = p, bl = b; break;";
  html += "                    case 5: r = b, g = p, bl = q; break;";
  html += "                }";
  html += "            }";
  html += "";
  html += "            return {";
  html += "                r: Math.round(r * 255),";
  html += "                g: Math.round(g * 255),";
  html += "                b: Math.round(bl * 255)";
  html += "            };";
  html += "        }";
  html += "";
  html += "        sliders.slice(1).forEach((slider, index) => {";
  html += "            const sliderElem = document.getElementById(slider);";
  html += "            const colorBoxElem = document.getElementById('colorBox' + (index + 1));";
  html += "            sliderElem.addEventListener('input', () => {";
  html += "                const hue = parseInt(sliderElem.value);";
  html += "                updateColorBox(colorBoxElem.id, hue);";
  html += "                document.getElementById(slider.replace('slider', 'sliderValue')).textContent = hue;";
  html += "            });";
  html += "        });";
  html += "    </script>";
  html += "</body>";
  html += "</html>";
  request->send(200, "text/html", html);
}

void handleUpdate(AsyncWebServerRequest* request) {
  Serial.println("do_update triggered");
  initUpdate = true;
  if (request->hasParam("bin_name", true)) {
    settings.bin_name = strdup(request->getParam("bin_name", true)->value().c_str());
  }
}

void handleSave(AsyncWebServerRequest* request) {
  preferences.begin("storage", false);
  bool reboot = false;
  bool disableBrightnessAuto = false;
  if (request->hasParam("legacy", true)) {
    if (request->getParam("legacy", true)->value().toInt() != settings.legacy) {
      reboot = true;
      settings.legacy = request->getParam("legacy", true)->value().toInt();
      preferences.putInt("legacy", settings.legacy);
      Serial.println("legacy commited to preferences");
    }
  }
  if (request->hasParam("ha_brokeraddress", true)) {
    if (request->getParam("ha_brokeraddress", true)->value() != settings.ha_brokeraddress) {
      reboot = true;
      settings.ha_brokeraddress = request->getParam("ha_brokeraddress", true)->value();
      preferences.putString("ha_brokeraddr", settings.ha_brokeraddress);
      Serial.println("ha_brokeraddress commited to preferences");
    }
  }
  if (request->hasParam("devicename", true)) {
    if (request->getParam("devicename", true)->value() != settings.devicename) {
      reboot = true;
      settings.devicename = request->getParam("devicename", true)->value();
      preferences.putString("dn", settings.devicename);
      Serial.println("devicename commited to preferences");
    }
  }
  if (request->hasParam("devicedescription", true)) {
    if (request->getParam("devicedescription", true)->value() != settings.devicedescription) {
      reboot = true;
      settings.devicedescription = request->getParam("devicedescription", true)->value();
      preferences.putString("dd", settings.devicedescription);
      Serial.println("devicedescription commited to preferences");
    }
  }
  if (request->hasParam("broadcastname", true)) {
    if (request->getParam("broadcastname", true)->value() != settings.broadcastname) {
      reboot = true;
      settings.broadcastname = request->getParam("broadcastname", true)->value();
      preferences.putString("bn", settings.broadcastname);
      Serial.println("broadcastname commited to preferences");
    }
  }
  if (request->hasParam("ha_mqttport", true)) {
    if (request->getParam("ha_mqttport", true)->value().toInt() != settings.ha_mqttport) {
      reboot = true;
      settings.ha_mqttport = request->getParam("ha_mqttport", true)->value().toInt();
      preferences.putInt("ha_mqttport", settings.ha_mqttport);
      Serial.println("ha_mqttport commited to preferences");
    }
  }
  if (request->hasParam("serverhost", true)) {
    String local_host = String(settings.serverhost);
    if (request->getParam("serverhost", true)->value() != local_host) {
      reboot = true;
      settings.serverhost = strdup(request->getParam("serverhost", true)->value().c_str());
      preferences.putString("host", request->getParam("serverhost", true)->value());
      Serial.println("serverhost commited to preferences");
    }
  }
  if (request->hasParam("tcpport", true)) {
    if (request->getParam("tcpport", true)->value().toInt() != settings.tcpport) {
      reboot = true;
      settings.tcpport = request->getParam("tcpport", true)->value().toInt();
      preferences.putInt("tcpport", settings.tcpport);
      Serial.println("tcpport commited to preferences");
    }
  }
  if (request->hasParam("updateport", true)) {
    if (request->getParam("updateport", true)->value().toInt() != settings.updateport) {
      reboot = true;
      settings.updateport = request->getParam("updateport", true)->value().toInt();
      preferences.putInt("upport", settings.updateport);
      Serial.println("updateport commited to preferences");
    }
  }
  if (request->hasParam("pixelpin", true)) {
    if (request->getParam("pixelpin", true)->value().toInt() != settings.pixelpin) {
      reboot = true;
      settings.pixelpin = request->getParam("pixelpin", true)->value().toInt();
      preferences.putInt("pp", settings.pixelpin);
      Serial.println("pixelpin commited: ");
      Serial.println(settings.pixelpin);
    }
  }
  if (request->hasParam("buttonpin", true)) {
    if (request->getParam("buttonpin", true)->value().toInt() != settings.buttonpin) {
      reboot = true;
      settings.buttonpin = request->getParam("buttonpin", true)->value().toInt();
      preferences.putInt("bp", settings.buttonpin);
      Serial.println("buttonpin commited: ");
      Serial.println(settings.buttonpin);
    }
  }
  if (request->hasParam("ha_mqttuser", true)) {
    if (request->getParam("ha_mqttuser", true)->value() != settings.ha_mqttuser) {
      reboot = true;
      settings.ha_mqttuser = request->getParam("ha_mqttuser", true)->value();
      preferences.putString("ha_mqttuser", settings.ha_mqttuser);
      Serial.println("ha_mqttuser commited to preferences");
    }
  }
  if (request->hasParam("ha_mqttpassword", true)) {
    if (request->getParam("ha_mqttpassword", true)->value() != settings.ha_mqttpassword) {
      reboot = true;
      settings.ha_mqttpassword = request->getParam("ha_mqttpassword", true)->value();
      preferences.putString("ha_mqttpass", settings.ha_mqttpassword);
      Serial.println("ha_mqttpassword commited to preferences");
    }
  }
  if (request->hasParam("brightness", true)) {
    int currentBrightness = request->getParam("brightness", true)->value().toInt();
    if (currentBrightness != settings.brightness) {
      disableBrightnessAuto = true;
      settings.brightness = request->getParam("brightness", true)->value().toInt();
      preferences.putInt("brightness", settings.brightness);
      if (enableHA) {
        haBrightness.setState(settings.brightness);
      }
      Serial.println("brightness commited to preferences");
    }
  }
  if (request->hasParam("brightness_auto", true) and !disableBrightnessAuto) {
    if (settings.brightness_auto == 0) {
      settings.brightness_auto = 1;
      if (enableHA) {
        haBrightnessAuto.setState(true);
      }
      preferences.putInt("bra", settings.brightness_auto);
      Serial.println("brightness_auto enabled to preferences");
    }
  } else {
    if (settings.brightness_auto == 1) {
      settings.brightness_auto = 0;
      settings.brightness = settings.brightness_day;
      if (enableHA) {
        haBrightnessAuto.setState(false);
        haBrightness.setState(settings.brightness);
      }
      preferences.putInt("bra", settings.brightness_auto);
      preferences.putInt("brightness", settings.brightness);
      Serial.println("brightness_auto disabled to preferences");
    }
  }
  if (request->hasParam("service_diodes_mode", true)) {
    if (settings.service_diodes_mode == 0) {
      settings.service_diodes_mode = 1;
      preferences.putInt("sdm", settings.service_diodes_mode);
      checkServicePins();
      Serial.println("service_diodes_mode enabled to preferences");
    }
  } else {
    if (settings.service_diodes_mode == 1) {
      settings.service_diodes_mode = 0;
      preferences.putInt("sdm", settings.service_diodes_mode);
      checkServicePins();
      Serial.println("service_diodes_mode disabled to preferences");
    }
  }
  if (request->hasParam("sdm_auto", true) and !disableBrightnessAuto) {
    if (settings.sdm_auto == 0) {
      settings.sdm_auto = 1;
      settings.service_diodes_mode = 0;
      // if (enableHA) {
      //   haBrightnessAuto.setState(true);
      // }
      preferences.putInt("sdm", settings.service_diodes_mode);
      preferences.putInt("sdma", settings.sdm_auto);
      checkServicePins();
      Serial.println("sdm_auto enabled to preferences");
    }
  } else {
    if (settings.sdm_auto == 1) {
      settings.sdm_auto = 0;
      settings.service_diodes_mode = 1;
      // if (enableHA) {
      //   haBrightnessAuto.setState(false);
      // }
      preferences.putInt("sdm", settings.service_diodes_mode);
      preferences.putInt("sdma", settings.sdm_auto);
      checkServicePins();
      Serial.println("sdm_auto disabled to preferences");
    }
  }
  if (request->hasParam("home_alert_time", true)) {
    if (settings.home_alert_time == 0) {
      settings.home_alert_time = 1;
      if (enableHA) {
        haShowHomeAlarmTime.setState(true);
      }
      preferences.putInt("hat", settings.home_alert_time);
      Serial.println("home_alert_time enabled to preferences");
      parseHomeDistrictJson();
    }
  } else {
    if (settings.home_alert_time == 1) {
      settings.home_alert_time = 0;
      if (enableHA) {
        haShowHomeAlarmTime.setState(false);
      }
      preferences.putInt("hat", settings.home_alert_time);
      Serial.println("home_alert_time disabled to preferences");
    }
  }
  if (request->hasParam("new_fw_notification", true)) {
    if (settings.new_fw_notification == 0) {
      settings.new_fw_notification = 1;
      preferences.putInt("nfwn", settings.new_fw_notification);
      Serial.println("new_fw_notification enabled to preferences");
    }
  } else {
    if (settings.new_fw_notification == 1) {
      settings.new_fw_notification = 0;
      preferences.putInt("nfwn", settings.new_fw_notification);
      Serial.println("new_fw_notification disabled to preferences");
    }
  }
  if (request->hasParam("brightness_day", true)) {
    if (request->getParam("brightness_day", true)->value().toInt() != settings.brightness_day) {
      settings.brightness_day = request->getParam("brightness_day", true)->value().toInt();
      preferences.putInt("brd", settings.brightness_day);
      Serial.println("brightness_day commited to preferences");
    }
  }
  if (request->hasParam("brightness_night", true)) {
    if (request->getParam("brightness_night", true)->value().toInt() != settings.brightness_night) {
      settings.brightness_night = request->getParam("brightness_night", true)->value().toInt();
      preferences.putInt("brn", settings.brightness_night);
      Serial.println("brightness_night commited to preferences");
    }
  }
  if (request->hasParam("day_start", true)) {
    if (request->getParam("day_start", true)->value().toInt() != settings.day_start) {
      settings.day_start = request->getParam("day_start", true)->value().toInt();
      preferences.putInt("ds", settings.day_start);
      Serial.println("day_start commited to preferences");
    }
  }
  if (request->hasParam("night_start", true)) {
    if (request->getParam("night_start", true)->value().toInt() != settings.night_start) {
      settings.night_start = request->getParam("night_start", true)->value().toInt();
      preferences.putInt("ns", settings.night_start);
      Serial.println("night_start commited to preferences");
    }
  }
  if (request->hasParam("brightness_alert", true)) {
    if (request->getParam("brightness_alert", true)->value().toInt() != settings.brightness_alert) {
      settings.brightness_alert = request->getParam("brightness_alert", true)->value().toInt();
      preferences.putInt("ba", settings.brightness_alert);
      Serial.println("brightness_alert commited to preferences");
    }
  }
  if (request->hasParam("brightness_clear", true)) {
    if (request->getParam("brightness_clear", true)->value().toInt() != settings.brightness_clear) {
      settings.brightness_clear = request->getParam("brightness_clear", true)->value().toInt();
      preferences.putInt("bc", settings.brightness_clear);
      Serial.println("brightness_clear commited to preferences");
    }
  }
  if (request->hasParam("brightness_new_alert", true)) {
    if (request->getParam("brightness_new_alert", true)->value().toInt() != settings.brightness_new_alert) {
      settings.brightness_new_alert = request->getParam("brightness_new_alert", true)->value().toInt();
      preferences.putInt("bna", settings.brightness_new_alert);
      Serial.println("brightness_new_alert commited to preferences");
    }
  }
  if (request->hasParam("brightness_alert_over", true)) {
    if (request->getParam("brightness_alert_over", true)->value().toInt() != settings.brightness_alert_over) {
      settings.brightness_alert_over = request->getParam("brightness_alert_over", true)->value().toInt();
      preferences.putInt("bao", settings.brightness_alert_over);
      Serial.println("brightness_alert_over commited to preferences");
    }
  }
  if (request->hasParam("color_alert", true)) {
    if (request->getParam("color_alert", true)->value().toInt() != settings.color_alert) {
      settings.color_alert = request->getParam("color_alert", true)->value().toInt();
      preferences.putInt("coloral", settings.color_alert);
      Serial.println("color_alert commited to preferences");
    }
  }
  if (request->hasParam("color_clear", true)) {
    if (request->getParam("color_clear", true)->value().toInt() != settings.color_clear) {
      settings.color_clear = request->getParam("color_clear", true)->value().toInt();
      preferences.putInt("colorcl", settings.color_clear);
      Serial.println("color_clear commited to preferences");
    }
  }
  if (request->hasParam("color_new_alert", true)) {
    if (request->getParam("color_new_alert", true)->value().toInt() != settings.color_new_alert) {
      settings.color_new_alert = request->getParam("color_new_alert", true)->value().toInt();
      preferences.putInt("colorna", settings.color_new_alert);
      Serial.println("color_new_alert commited to preferences");
    }
  }
  if (request->hasParam("color_alert_over", true)) {
    if (request->getParam("color_alert_over", true)->value().toInt() != settings.color_alert_over) {
      settings.color_alert_over = request->getParam("color_alert_over", true)->value().toInt();
      preferences.putInt("colorao", settings.color_alert_over);
      Serial.println("color_alert_over commited to preferences");
    }
  }
  if (request->hasParam("color_home_district", true)) {
    if (request->getParam("color_home_district", true)->value().toInt() != settings.color_home_district) {
      settings.color_home_district = request->getParam("color_home_district", true)->value().toInt();
      preferences.putInt("colorhd", settings.color_home_district);
      Serial.println("color_home_district commited to preferences");
    }
  }
  if (request->hasParam("home_district", true)) {
    if (request->getParam("home_district", true)->value().toInt() != settings.home_district) {
      settings.home_district = request->getParam("home_district", true)->value().toInt();
      saveHomeDistrict();
    }
  }
  if (request->hasParam("alarms_auto_switch", true)) {
    if (request->getParam("alarms_auto_switch", true)->value().toInt() != settings.alarms_auto_switch) {
      settings.alarms_auto_switch = request->getParam("alarms_auto_switch", true)->value().toInt();
      if (enableHA) {
        haAlarmsAuto.setState(settings.alarms_auto_switch);
      }
      preferences.putInt("aas", settings.alarms_auto_switch);
      Serial.println("alarms_auto_switch commited to preferences");
    }
  }
  if (request->hasParam("kyiv_district_mode", true)) {
    if (request->getParam("kyiv_district_mode", true)->value().toInt() != settings.kyiv_district_mode) {
      settings.kyiv_district_mode = request->getParam("kyiv_district_mode", true)->value().toInt();
      preferences.putInt("kdm", settings.kyiv_district_mode);
      Serial.println("kyiv_district_mode commited to preferences");
    }
  }
  if (request->hasParam("map_mode", true)) {
    if (request->getParam("map_mode", true)->value().toInt() != settings.map_mode) {
      settings.map_mode = request->getParam("map_mode", true)->value().toInt();
      saveMapMode();
    }
  }
  if (request->hasParam("display_mode", true)) {
    if (request->getParam("display_mode", true)->value().toInt() != settings.display_mode) {
      settings.display_mode = request->getParam("display_mode", true)->value().toInt();
      saveDisplayMode();
      // update to selected displayMode
      displayCycle();
    }
  }
  if (request->hasParam("display_mode_time", true)) {
    if (request->getParam("display_mode_time", true)->value().toInt() != settings.display_mode_time) {
      settings.display_mode_time = request->getParam("display_mode_time", true)->value().toInt();
      preferences.putInt("dmt", settings.display_mode_time);
      Serial.println("display_mode_time commited to preferences");
    }
  }
  if (request->hasParam("button_mode", true)) {
    if (request->getParam("button_mode", true)->value().toInt() != settings.button_mode) {
      settings.button_mode = request->getParam("button_mode", true)->value().toInt();
      preferences.putInt("bm", settings.button_mode);
      Serial.println("button_mode commited to preferences");
    }
  }
  if (request->hasParam("alarms_notify_mode", true)) {
    if (request->getParam("alarms_notify_mode", true)->value().toInt() != settings.alarms_notify_mode) {
      settings.alarms_notify_mode = request->getParam("alarms_notify_mode", true)->value().toInt();
      preferences.putInt("anm", settings.alarms_notify_mode);
      Serial.println("alarms_notify_mode commited to preferences");
    }
  }
  if (request->hasParam("weather_min_temp", true)) {
    if (request->getParam("weather_min_temp", true)->value().toInt() != settings.weather_min_temp) {
      settings.weather_min_temp = request->getParam("weather_min_temp", true)->value().toInt();
      preferences.putInt("mintemp", settings.weather_min_temp);
      Serial.println("color_alert_over commited to preferences");
    }
  }
  if (request->hasParam("weather_max_temp", true)) {
    if (request->getParam("weather_max_temp", true)->value().toInt() != settings.weather_max_temp) {
      settings.weather_max_temp = request->getParam("weather_max_temp", true)->value().toInt();
      preferences.putInt("maxtemp", settings.weather_max_temp);
      Serial.println("weather_max_temp commited to preferences");
    }
  }
  if (request->hasParam("display_height", true)) {
    if (request->getParam("display_height", true)->value().toInt() != settings.display_height) {
      reboot = true;
      preferences.putInt("dh", request->getParam("display_height", true)->value().toInt());
      Serial.print("display_height commited to preferences: ");
      Serial.println(request->getParam("display_height", true)->value().toInt());
    }
  }
  preferences.end();
  delay(1000);
  request->redirect("/");
  if (reboot) {
    ESP.restart();
  }
}
//--Web server end

//--Service messages start
void uptime() {
  int     uptimeValue = millis() / 1000;
  int32_t number      = WiFi.RSSI();
  int     rssi        = 0 - number;

  float totalHeapSize = ESP.getHeapSize() / 1024.0;
  float freeHeapSize  = ESP.getFreeHeap() / 1024.0;
  float usedHeapSize  = totalHeapSize - freeHeapSize;
  float cpuTemp       = temperatureRead();

  if (enableHA) {
    haUptime.setValue(uptimeValue);
    haWifiSignal.setValue(rssi);
    haFreeMemory.setValue(freeHeapSize);
    haUsedMemory.setValue(usedHeapSize);
    haCpuTemp.setValue(cpuTemp);
  }
  Serial.println(uptimeValue);
}

void connectStatuses() {
  Serial.print("Map API connected: ");
  Serial.println(client_tcp.connected());
  if (enableHA) {
    Serial.print("Home Assistant MQTT connected: ");
    Serial.println(mqtt.isConnected());
    if (mqtt.isConnected()) {
      servicePin(settings.hapin, HIGH, false);
    } else {
      servicePin(settings.hapin, LOW, false);
    }
    haMapApiConnect.setState(client_tcp.connected(), true);
  }
}

void timeUpdate() {
  timeClient.update();
}

void autoBrightnessUpdate() {
  if (settings.brightness_auto == 1) {
    int currentHour = timeClient.getHours();
    bool isDay = currentHour >= settings.day_start && currentHour < settings.night_start;
    int currentBrightness = isDay ? settings.brightness_day : settings.brightness_night;
    if (!isDay && settings.sdm_auto && settings.service_diodes_mode != 0) {
      settings.service_diodes_mode = 0;
      checkServicePins();
    }
    if (isDay && settings.sdm_auto && settings.service_diodes_mode != 1) {
      settings.service_diodes_mode = 1;
      checkServicePins();
    }
    if (currentBrightness != settings.brightness) {
      settings.brightness = currentBrightness;
      if (enableHA) {
        haBrightness.setState(settings.brightness);
      }
      preferences.begin("storage", false);
      preferences.putInt("brightness", settings.brightness);
      preferences.end();
      Serial.print(" set auto brightness: ");
      Serial.println(settings.brightness);
    }
  }
}
//--Service messages end

//--TCP process start
void tcpConnect() {
  if (millis() - tcpLastPingTime > 60000) {
    tcpReconnect = true;
  }
  if (!client_tcp.connected() or tcpReconnect) {
    int cycle = 0;
    servicePin(settings.datapin, LOW, false);
    Serial.println("Connecting to map API...");
    Serial.print("id: ");
    Serial.println(settings.identifier);
    showServiceMessage("Пiдключення map-API..", 5000);
    const char* local_serverhost = settings.serverhost.c_str();
    while (!client_tcp.connect(local_serverhost, settings.tcpport)) {
      Serial.println("Failed");
      showServiceMessage("map-API нeдocтyпнe", 5000);
      if (enableHA) {
        haMapApiConnect.setState(false);
      }
      tcpReconnect = true;
      if (cycle > 30) {
        mapReconnect();
      }
      delay(2000);
      cycle += 1;
    }
    String combinedString = String(settings.softwareversion) + "_" + settings.identifier;
    char charArray[combinedString.length() + 1];
    combinedString.toCharArray(charArray, sizeof(charArray));
    Serial.println(charArray);
    client_tcp.print(charArray);
    showServiceMessage("map-API пiдключeнo", 5000);
    servicePin(settings.datapin, HIGH, false);
    Serial.println("TCP connected");
    if (enableHA) {
      haMapApiConnect.setState(true);
    }
    tcpLastPingTime = millis();
    tcpReconnect = false;
  }
}

// void tcpReconnect(){
//   if (millis() - tcpLastPingTime > 30000){
//     tcpReconnect = true;
//   }
//   if (!client_tcp.connected() or tcpReconnect) {
//     Serial.print("Reconnecting to map API: ");
//     display.clearDisplay();
//     DisplayCenter(utf8cyr("Підключення map-API.."),0,1);
//     if (!client_tcp.connect(settings.serverhost, settings.tcpport))
//     {
//       Serial.println("Failed");
//       display.clearDisplay();
//       DisplayCenter(utf8cyr("map-API нeдocтyпнe"),0,1);
//       haMapApiConnect.setState(false);
//     }else{
//       display.clearDisplay();
//       DisplayCenter(utf8cyr("map-API пiдключeнo"),0,1);
//       Serial.println("Connected");
//       haMapApiConnect.setState(true);
//     }
//   }
// }

void tcpProcess() {
  String data;
  while (client_tcp.available() > 0) {
    data += (char)client_tcp.read();
  }
  if (data.length()) {
    Serial.print("New data: ");
    Serial.print(data.length());
    Serial.print(" : ");
    Serial.println(data);
    TestParcer(data, data.length());
  }
}

void TestParcer(String sensorBuffer, int data_lenght) {
  if (sensorBuffer == "p") {
    Serial.println("TCP PING SUCCESS!");
    tcpLastPingTime = millis();
    tcpReconnect = false;
  } else {
    long values[26];
    float sensorValues[26];

    char buffer[data_lenght];

    sensorBuffer.toCharArray(buffer, sizeof(buffer));

    int n = sscanf(buffer, "%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld:%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f,%f",
                   &values[0], &values[1], &values[2], &values[3], &values[4], &values[5], &values[6], &values[7], &values[8], &values[9],
                   &values[10], &values[11], &values[12], &values[13], &values[14], &values[15], &values[16], &values[17], &values[18], &values[19],
                   &values[20], &values[21], &values[22], &values[23], &values[24], &values[25],
                   &sensorValues[0], &sensorValues[1], &sensorValues[2], &sensorValues[3], &sensorValues[4], &sensorValues[5], &sensorValues[6], &sensorValues[7],
                   &sensorValues[8], &sensorValues[9], &sensorValues[10], &sensorValues[11], &sensorValues[12], &sensorValues[13], &sensorValues[14],
                   &sensorValues[15], &sensorValues[16], &sensorValues[17], &sensorValues[18], &sensorValues[19], &sensorValues[20], &sensorValues[21],
                   &sensorValues[22], &sensorValues[23], &sensorValues[24], &sensorValues[25]);

    if (n == 52) {
      Serial.println("Successfully parsed sensor data!");
      for (int i = 0; i < 26; ++i) {
        alarm_leds[calculateOffset(i)] = values[i];
        Serial.print("Value ");
        Serial.print(i);
        Serial.print(": ");
        Serial.println(values[i]);
      }
      for (int i = 0; i < 26; ++i) {
        weather_leds[calculateOffset(i)] = sensorValues[i];
        Serial.print("Sensor Value ");
        Serial.print(i);
        Serial.print(": ");
        Serial.println(sensorValues[i], 1);
      }
    } else {
      Serial.print("Error parsing sensor buffer, could only decode ");
      Serial.print(n);
      Serial.println(" parameter(s).");
    }
  }
}

// void parseString(String str, int data_lenght) {
//   if (str == "p"){
//     Serial.println("TCP PING SUCCESS");
//     tcpLastPingTime = millis();
//     tcpReconnect = false;
//   }else{
//     int colonIndex = str.indexOf(":");
//     String firstPart = str.substring(0, colonIndex);
//     String secondPart = str.substring(colonIndex + 1);

//     int firstArraySize = countOccurrences(firstPart, ',') + 1;
//     int firstArray[firstArraySize];
//     extractAlarms(firstPart, firstArraySize);

//     int secondArraySize = countOccurrences(secondPart, ',') + 1;
//     int secondArray[secondArraySize];
//     extractWeather(secondPart, secondArraySize);
//   }
// }

// int countOccurrences(String str, char target) {
//   int count = 0;
//   for (int i = 0; i < str.length(); i++) {
//     if (str.charAt(i) == target) {
//       count++;
//     }
//   }
//   return count;
// }

// void extractAlarms(String str, int size) {
//   int index = 0;
//   char *token = strtok(const_cast<char*>(str.c_str()), ",");
//   while (token != NULL && index < size) {
//     alarm_leds[calculateOffset(index)] = atoi(token);
//     token = strtok(NULL, ",");
//     index++;
//   }
// }

// void extractWeather(String str, int size) {
//   int index = 0;
//   char *token = strtok(const_cast<char*>(str.c_str()), ",");
//   //Serial.print("weather");
//   while (token != NULL && index < size) {
//     weather_leds[calculateOffset(index)] = atof(token);
//     token = strtok(NULL, ",");
//     index++;
//     //Serial.print(weather_leds[position]);
//     //Serial.print(" ");
//   }
//   //Serial.println(" ");
// }


//--TCP process end

//--Map processing start
int calculateOffset(int initial_position) {
  int position;
  if (initial_position == 25) {
    position = 25;
  } else {
    position = initial_position + offset;
    if (position >= 25) {
      position -= 25;
    }
  }
  return position;
}

int calculateOffsetDistrict(int initial_position) {
  //Serial.print("initial_position");Serial.println(initial_position);
  int position;
  if (initial_position == 25) {
    position = 25;
  } else {
    position = initial_position + offset;
    if (position >= 25) {
      position -= 25;
    }
  }
  //Serial.print("position");Serial.println(position);
  if (settings.kyiv_district_mode == 2) {
    if (position == 25) {
      return 7 + offset;
    }
  }
  if (settings.kyiv_district_mode == 3) {

    if (position == 25) {
      //Serial.print("position8+");Serial.println(8+offset);
      return 8 + offset;
    }
    if (position > 7 + offset) {
      //Serial.print("position+");Serial.println(position + 1);
      return position + 1;
    }
  }
  if (settings.kyiv_district_mode == 4) {
    if (position == 25) {
      return 7 + offset;
    }
  }
  return position;
}


HsbColor processAlarms(int led, int position) {
  HsbColor hue;
  float local_brightness = settings.brightness / 200.0f;
  int local_color;
  if (blink and settings.alarms_notify_mode == 2) {
    local_brightness = settings.brightness / 600.0f;
  }

  float local_brightness_alert = settings.brightness_alert / 100.0f;
  float local_brightness_clear = settings.brightness_clear / 100.0f;
  float local_brightness_new_alert = settings.brightness_new_alert / 100.0f;
  float local_brightness_alert_over = settings.brightness_alert_over / 100.0f;

  int local_district = calculateOffsetDistrict(settings.home_district);

  switch (led) {
    case 0:
      int color_switch;
      if (position == local_district) {
        homeAlertStart = 0;
        color_switch = settings.color_home_district;
      } else {
        color_switch = settings.color_clear;
      }
      hue = HsbColor(color_switch / 360.0f, 1.0, settings.brightness * local_brightness_clear / 200.0f);
      break;
    case 1:
      if (position == local_district && homeAlertStart < 1) {
        parseHomeDistrictJson();
      }
      hue = HsbColor(settings.color_alert / 360.0f, 1.0, settings.brightness * local_brightness_alert / 200.0f);
      break;
    case 2:
      if (position == local_district) {
        homeAlertStart = 0;
      }
      local_color = settings.color_alert_over;
      if (settings.alarms_notify_mode == 0) {
        local_color = settings.color_clear;
      }
      hue = HsbColor(local_color / 360.0f, 1.0, local_brightness * local_brightness_alert_over);
      break;
    case 3:
      if (position == local_district && homeAlertStart < 1) {
        parseHomeDistrictJson();
      }
      local_color = settings.color_new_alert;
      if (settings.alarms_notify_mode == 0) {
        local_color = settings.color_alert;
      }
      hue = HsbColor(local_color / 360.0f, 1.0, local_brightness * local_brightness_new_alert);
      break;
  }
  return hue;
}

float processWeather(int led) {
  double minTemp = settings.weather_min_temp;
  double maxTemp = settings.weather_max_temp;
  double temp = led;
  float normalizedValue = float(temp - minTemp) / float(maxTemp - minTemp);
  if (normalizedValue > 1) {
    normalizedValue = 1;
  }
  if (normalizedValue < 0) {
    normalizedValue = 0;
  }
  int hue = 275 + normalizedValue * (0 - 275);
  hue = (int)hue % 360;
  return hue / 360.0f;
}

void mapReconnect() {
  float local_brightness = settings.brightness / 200.0f;
  if (blink) {
    local_brightness = settings.brightness / 600.0f;
  }
  HsbColor hue = HsbColor(64 / 360.0f, 1.0, local_brightness);
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, hue);
  }
  strip->Show();
  blink = !blink;
}

void mapCycle() {
  int currentMapMode = getCurrentMapMode();
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
  }
  blink = !blink;
}

void mapOff() {
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, HslColor(0.0, 0.0, 0.0));
  }
  strip->Show();
}

void mapAlarms() {
  int adapted_alarm_leds[26];
  int lastValue = alarm_leds[25];
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    adapted_alarm_leds[i] = alarm_leds[i];
  }
  if (settings.kyiv_district_mode == 2) {
    adapted_alarm_leds[7] = alarm_leds[25];
  }
  if (settings.kyiv_district_mode == 3) {
    for (int i = 24; i >= 8 + offset; i--) {
      adapted_alarm_leds[i + 1] = alarm_leds[i];
    }
    adapted_alarm_leds[8 + offset] = lastValue;
  }
  if (settings.kyiv_district_mode == 4) {
    if (alarm_leds[25] == 0 and alarm_leds[7] == 0) {
      adapted_alarm_leds[7] = 0;
    }
    if (alarm_leds[25] == 1 or alarm_leds[7] == 1) {
      adapted_alarm_leds[7] = 1;
    }
    if (alarm_leds[25] == 2 or alarm_leds[7] == 2) {
      adapted_alarm_leds[7] = 2;
    }
    if (alarm_leds[25] == 3 or alarm_leds[7] == 3) {
      adapted_alarm_leds[7] = 3;
    }
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, processAlarms(adapted_alarm_leds[i], i));
  }
  strip->Show();
  //blink = !blink;
}

void mapWeather() {
  int adapted_weather_leds[26];
  int lastValue = weather_leds[25];
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    adapted_weather_leds[i] = weather_leds[i];
  }
  if (settings.kyiv_district_mode == 2) {
    adapted_weather_leds[7] = weather_leds[25];
  }
  if (settings.kyiv_district_mode == 3) {
    for (int i = 24; i >= 8 + offset; i--) {
      adapted_weather_leds[i + 1] = weather_leds[i];
    }
    adapted_weather_leds[8 + offset] = lastValue;
  }
  if (settings.kyiv_district_mode == 4) {
    adapted_weather_leds[7] = (weather_leds[25] + weather_leds[7]) / 2.0f;
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    //Serial.print(adapted_weather_leds[i]);
    //Serial.print(" ");
    strip->SetPixelColor(i, HslColor(processWeather(adapted_weather_leds[i]), 1.0, settings.brightness / 200.0f));
  }
  //Serial.println(" ");
  strip->Show();
}

void mapFlag() {
  int adapted_flag_leds[26];
  int lastValue = flag_leds[25];
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    adapted_flag_leds[i] = flag_leds[i];
  }
  if (settings.kyiv_district_mode == 2) {
    adapted_flag_leds[7] = flag_leds[25];
  }
  if (settings.kyiv_district_mode == 3) {
    for (int i = 24; i >= 8 + offset; i--) {
      adapted_flag_leds[i + 1] = flag_leds[i];
    }
    adapted_flag_leds[8 + offset] = lastValue;
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, HsbColor(adapted_flag_leds[i] / 360.0f, 1.0, settings.brightness / 200.0f));
  }
  strip->Show();
}

void mapRandom() {
  int randomLed = random(26);
  int randomColor = random(360);
  strip->SetPixelColor(randomLed, HsbColor(randomColor / 360.0f, 1.0, settings.brightness / 200.0f));
  strip->Show();
}

int getCurrentMapMode() {
  int currentMapMode = settings.map_mode;
  int position = settings.home_district;
  //Serial.print("position ");Serial.println(settings.home_district);
  switch (settings.alarms_auto_switch) {
    case 1:
      for (int j = 0; j < counters[position]; j++) {
        int alarm_led_id = calculateOffset(neighboring_districts[position][j]);
        if (alarm_leds[alarm_led_id] != 0) {
          currentMapMode = 1;
        }
      }
      break;
    case 2:
      if (alarm_leds[calculateOffset(position)] != 0) {
        currentMapMode = 1;
      }
  }
  if (settings.map_mode != currentMapMode && enableHA) {
    haMapModeCurrent.setValue(mapModes[currentMapMode].c_str());
  }
  return currentMapMode;
}
//--Map processing end

void WifiReconnect() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFI Reconnect");
    wifiReconnect = true;
    initWifi();
  }
}

void setup() {
  Serial.begin(115200);

  initSettings();
  initLegacy();
  initStrip();
  initDisplay();
  initWifi();
  initTime();

  Serial.print("ESP32 Chip ID: ");
  Serial.print(chipID1);
  Serial.println(chipID2);

  asyncEngine.setInterval(uptime, 5000);
  asyncEngine.setInterval(tcpProcess, 10);
  asyncEngine.setInterval(connectStatuses, 10000);
  asyncEngine.setInterval(tcpConnect, 1000);
  asyncEngine.setInterval(mapCycle, 1000);
  asyncEngine.setInterval(timeUpdate, 5000);
  asyncEngine.setInterval(displayCycle, 100);
  asyncEngine.setInterval(WifiReconnect, 5000);
  asyncEngine.setInterval(autoBrightnessUpdate, 1000);
  asyncEngine.setInterval(timezoneUpdate, 60000);
  asyncEngine.setInterval(doUpdate, 5000);
  asyncEngine.setInterval(doFetchBinList, 600000);
}

void loop() {
  wm.process();
  asyncEngine.run();
  ArduinoOTA.handle();
  buttonUpdate();
  if (enableHA) {
    mqtt.loop();
  }
}
