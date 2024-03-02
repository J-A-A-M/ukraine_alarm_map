#include <Preferences.h>
#include <WiFiManager.h>
#include <ESPAsyncWebServer.h>
#include <ESPmDNS.h>
#include <async.h>
#include <ArduinoOTA.h>
#include <ArduinoHA.h>
#include <NeoPixelBus.h>
#include <Adafruit_SSD1306.h>
#include <HTTPUpdate.h>
#include <vector>
#include <ArduinoJson.h>
#include <ArduinoWebsockets.h>
#include <BH1750.h>
#include <BME280I2C.h>
#include <SHT31.h>
#include <SHT2x.h>
#include <NTPtime.h>

const PROGMEM char* VERSION = "3.6";

struct Settings {
  const char*   apssid                 = "JAAM";
  const char*   softwareversion        = VERSION;
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
  int     websocket_port         = 38440;
  int     updateport             = 8090;
  String  bin_name               = String(VERSION) + ".bin";
  String  identifier             = "github";
  int     legacy                 = 1;
  int     pixelpin               = 13;
  int     buttonpin              = 15;
  int     alertpin               = 34;
  int     lightpin               = 32;
  int     ha_mqttport            = 1883;
  String  ha_mqttuser            = "";
  String  ha_mqttpassword        = "";
  String  ha_brokeraddress       = "";
  int     current_brightness     = 50;
  int     brightness             = 50;
  int     brightness_day         = 50;
  int     brightness_night       = 5;
  int     brightness_mode        = 0;
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
  int     new_fw_notification    = 1;
  int     ha_light_brightness    = 50;
  int     ha_light_r             = 215;
  int     ha_light_g             = 7;
  int     ha_light_b             = 255;


  // ------- Map Modes:
  // -------  0 - Off
  // -------  1 - Alarms
  // -------  2 - Weather
  // -------  3 - UA Flag
  // -------  4 - Random colors
  // -------  5 - Lamp
  int     map_mode               = 1;

  // ------- Display Modes:
  // -------  0 - Off
  // -------  1 - Clock
  // -------  2 - Home District Temperature
  // -------  3 - Tech info
  // -------  9 - Toggle modes
  int     display_mode           = 2;
  int     display_mode_time      = 5;
  int     button_mode            = 0;
  int     button_mode_long       = 0;
  int     alarms_notify_mode     = 2;
  int     display_width          = 128;
  int     display_height         = 32;
  int     day_start              = 8;
  int     night_start            = 22;
  int     ws_alert_time          = 120000;
  int     ws_reboot_time         = 180000;
  int     min_of_silence         = 1;
  int     enable_pin_on_alert    = 0;
  int     fw_update_channel      = 0;
  float   temp_correction        = 0;
  float   hum_correction         = 0;
  float   presure_correction     = 0;
  float   light_sensor_factor    = 1;
  // ------- web config end
};

Settings settings;

struct Firmware {
  int major = 0;
  int minor = 0;
  int patch = 0;
  int betaBuild = 0;
  bool isBeta = false;
};

Firmware currentFirmware;
Firmware latestFirmware;

using namespace websockets;

Preferences       preferences;
WiFiManager       wm;
WiFiClient        client;
WebsocketsClient  client_websocket;
AsyncWebServer    webserver(80);
NTPtime           timeClient(2);
DSTime            dst(3, 0, 7, 3, 10, 0, 7, 4); //https://en.wikipedia.org/wiki/Eastern_European_Summer_Time
Async             asyncEngine = Async(20);
Adafruit_SSD1306  display(settings.display_width, settings.display_height, &Wire, -1);
BH1750            bh1750;
BME280I2C         bme280;
SHT31             sht3x;
HTU20             htu2x;

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
int legacy_flag_leds[26] PROGMEM = {
  60, 60, 60, 180, 180, 180, 180, 180, 180,
  180, 180, 180, 60, 60, 60, 60, 60, 60, 60,
  180, 180, 60, 60, 60, 60, 180
};


int d0[] PROGMEM = { 0, 1, 3 };
int d1[] PROGMEM = { 1, 0, 2, 3, 24 };
int d2[] PROGMEM = { 2, 1, 3, 4, 5, 23, 24 };
int d3[] PROGMEM = { 3, 0, 1, 2, 4 };
int d4[] PROGMEM = { 4, 2, 3, 5 };
int d5[] PROGMEM = { 5, 2, 3, 4, 6, 23 };
int d6[] PROGMEM = { 6, 5, 7, 22, 23, 25 };
int d7[] PROGMEM = { 7, 6, 8, 19, 20, 22, 25 };
int d8[] PROGMEM = { 8, 7, 9, 19, 20 };
int d9[] PROGMEM = { 9, 8, 10, 19 };
int d10[] PROGMEM = { 10, 9, 12, 18, 19 };
int d11[] PROGMEM = { 11, 10, 12 };
int d12[] PROGMEM = { 12, 10, 13, 18 };
int d13[] PROGMEM = { 13, 12, 14, 18 };
int d14[] PROGMEM = { 14, 13, 17, 18 };
int d15[] PROGMEM = { 15, 14 };
int d16[] PROGMEM = { 16, 17, 20, 21, 22 };
int d17[] PROGMEM = { 17, 14, 16, 18, 21 };
int d18[] PROGMEM = { 18, 10, 12, 13, 14, 17, 19, 21 };
int d19[] PROGMEM = { 19, 7, 8, 9, 10, 18, 20, 21, 25 };
int d20[] PROGMEM = { 20, 7, 8, 19, 21, 22, 25 };
int d21[] PROGMEM = { 21, 16, 17, 18, 19, 20, 22 };
int d22[] PROGMEM = { 22, 6, 7, 16, 20, 21, 23, 24, 25 };
int d23[] PROGMEM = { 23, 2, 5, 6, 22, 24 };
int d24[] PROGMEM = { 24, 1, 2, 22, 23 };
int d25[] PROGMEM = { 25, 7 };


int counters[] PROGMEM = { 3, 5, 7, 5, 4, 6, 6, 6, 5, 4, 5, 3, 4, 4, 4, 2, 5, 5, 8, 8, 7, 7, 9, 6, 5, 2 };

std::vector<const PROGMEM char*> districts PROGMEM = {
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

std::vector<const PROGMEM char*> districtsAlphabetical PROGMEM = {
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

int* neighboring_districts[] PROGMEM = {
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
bool    websocketReconnect = false;
bool    blink = false;
bool    isDaylightSaving = false;
time_t  websocketLastPingTime = 0;
int     offset = 9;
bool    initUpdate = false;
long    homeAlertStart = 0;
int     timeOffset = 0;
time_t  lastHomeDistrictSync = 0;
bool    fwUpdateAvailable = false;
int     rssi;
bool    apiConnected;
bool    haConnected;
int     prevMapMode = 1;
bool    alarmNow = false;
bool    minuteOfSilence = false;
bool    isMapOff = false;
bool    isDisplayOff = false;
bool    nightMode = false;
int     prevBrightness = -1;
int     needRebootWithDelay = -1;
bool    bh1750Inited = false;
bool    bme280Inited = false;
bool    bmp280Inited = false;
bool    sht3xInited = false;
bool    htu2xInited = false;
float   lightInLuxes = -1;
float   localTemp = -273;
float   localHum = -1;
float   localPresure = -1;


#define BR_LEVELS_COUNT 20
int     brightnessLevels[BR_LEVELS_COUNT]; // Array containing brightness values

// Button variables
#define SHORT_PRESS_TIME 500 // 500 milliseconds
#define LONG_PRESS_TIME  500 // 500 milliseconds
int lastState = LOW;  // the previous state from the input pin
int currentState;     // the current reading from the input pin
unsigned long pressedTime  = 0;
unsigned long releasedTime = 0;
bool isPressing = false;
bool isLongDetected = false;

std::vector<String> bin_list;
std::vector<String> test_bin_list;

HADevice        device;
HAMqtt          mqtt(client, device, 19);

uint64_t chipid = ESP.getEfuseMac();
String chipID = String((uint32_t)(chipid >> 32), HEX) + String((uint32_t)chipid, HEX);

String haUptimeString             = chipID + "_uptime";
String haWifiSignalString         = chipID + "_wifi_signal";
String haFreeMemoryString         = chipID + "_free_memory";
String haUsedMemoryString         = chipID + "_used_memory";
String haBrightnessString         = chipID + "_brightness";
String haMapModeString            = chipID + "_map_mode";
String haDisplayModeString        = chipID + "_display_mode";
String haMapModeCurrentString     = chipID + "_map_mode_current";
String haMapApiConnectString      = chipID + "_map_api_connect";
String haBrightnessAutoString     = chipID + "_brightness_auto";
String haAlarmsAutoString         = chipID + "_alarms_auto";
String haShowHomeAlarmTimeString  = chipID + "_show_home_alarm_time";
String haRebootString             = chipID + "_reboot";
String haCpuTempString            = chipID + "_cpu_temp";
String haHomeDistrictString       = chipID + "_home_district";
String haToggleMapModeString      = chipID + "_toggle_map_mode";
String haToggleDisplayModeString  = chipID + "_toggle_display_mode";
String haLightString              = chipID + "_light";

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
HASelect        haBrightnessAuto(haBrightnessAutoString.c_str());
HASwitch        haShowHomeAlarmTime(haShowHomeAlarmTimeString.c_str());
HAButton        haReboot(haRebootString.c_str());
HAButton        haToggleMapMode(haToggleMapModeString.c_str());
HAButton        haToggleDisplayMode(haToggleDisplayModeString.c_str());
HASensorNumber  haCpuTemp(haCpuTempString.c_str(), HASensorNumber::PrecisionP1);
HASensor        haHomeDistrict(haHomeDistrictString.c_str());
HALight         haLight(haLightString.c_str(), HALight::BrightnessFeature | HALight::RGBFeature);

std::vector<const PROGMEM char*> mapModes PROGMEM = {
  "Вимкнено",
  "Тривога",
  "Погода",
  "Прапор",
  "Випадкові кольори",
  "Лампа"
};

std::vector<const PROGMEM char*> displayModes PROGMEM = {
  "Вимкнено",
  "Годинник",
  "Погода",
  "Технічна інформація",
  "Перемикання"
};

std::vector<const PROGMEM char*> autoAlarms PROGMEM = {
  "Вимкнено",
  "Домашній та суміжні",
  "Лише домашній"
};

std::vector<const PROGMEM char*> singleClickOptions PROGMEM = {
  "Вимкнено",
  "Перемикання режимів мапи",
  "Перемикання режимів дисплея",
  "Увімк./Вимк. мапу",
  "Увімк./Вимк. дисплей",
  "Увімк./Вимк. мапу та дисплей",
  "Увімк./Вимк. нічний режим"
};

std::vector<const PROGMEM char*> longClickOptions PROGMEM = {
  "Вимкнено",
  "Перемикання режимів мапи",
  "Перемикання режимів дисплея",
  "Увімк./Вимк. мапу",
  "Увімк./Вимк. дисплей",
  "Увімк./Вимк. мапу та дисплей",
  "Увімк./Вимк. нічний режим",
  "Перезавантаження пристрою"
};

std::vector<const PROGMEM char*> fwUpdateChannels PROGMEM = {
  "Production",
  "Beta"
};

std::vector<const PROGMEM char*> autoBrightnessOptions PROGMEM = {
  "Вимкнено",
  "День/Ніч",
  "Сенсор освітлення"
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
    //pinMode(settings.reservedpin, OUTPUT);

    servicePin(settings.powerpin, HIGH, false);

    settings.kyiv_district_mode = 3;
    settings.pixelpin = 13;
    settings.buttonpin = 35;
    settings.display_height = 64;
  }
  pinMode(settings.buttonpin, INPUT_PULLUP);
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
  settings.websocket_port         = preferences.getInt("wsp", settings.websocket_port);
  settings.updateport             = preferences.getInt("upport", settings.updateport);
  settings.legacy                 = preferences.getInt("legacy", settings.legacy);
  settings.current_brightness     = preferences.getInt("cbr", settings.current_brightness);
  settings.brightness             = preferences.getInt("brightness", settings.brightness);
  settings.brightness_day         = preferences.getInt("brd", settings.brightness_day);
  settings.brightness_night       = preferences.getInt("brn", settings.brightness_night);
  settings.brightness_mode        = preferences.getInt("bra", settings.brightness_mode);
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
  settings.button_mode_long       = preferences.getInt("bml", settings.button_mode_long);
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
  settings.alertpin               = preferences.getInt("ap", settings.alertpin);
  settings.lightpin               = preferences.getInt("lp", settings.lightpin);
  settings.service_diodes_mode    = preferences.getInt("sdm", settings.service_diodes_mode);
  settings.new_fw_notification    = preferences.getInt("nfwn", settings.new_fw_notification);
  settings.ws_alert_time          = preferences.getInt("wsat", settings.ws_alert_time);
  settings.ws_reboot_time         = preferences.getInt("wsrt", settings.ws_reboot_time);
  settings.ha_light_brightness    = preferences.getInt("ha_lbri", settings.ha_light_brightness);
  settings.ha_light_r             = preferences.getInt("ha_lr", settings.ha_light_r);
  settings.ha_light_g             = preferences.getInt("ha_lg", settings.ha_light_g);
  settings.ha_light_b             = preferences.getInt("ha_lb", settings.ha_light_b);
  settings.enable_pin_on_alert    = preferences.getInt("epoa", settings.enable_pin_on_alert);
  settings.min_of_silence         = preferences.getInt("mos", settings.min_of_silence);
  settings.fw_update_channel      = preferences.getInt("fwuc", settings.fw_update_channel);
  settings.temp_correction        = preferences.getFloat("ltc", settings.temp_correction);
  settings.hum_correction         = preferences.getFloat("lhc", settings.hum_correction);
  settings.presure_correction     = preferences.getFloat("lpc", settings.presure_correction);
  settings.light_sensor_factor    = preferences.getFloat("lsf", settings.light_sensor_factor);

  preferences.end();

  currentFirmware = parseFirmwareVersion(VERSION);
  Serial.print("Current firmware version: ");
  Serial.println(getFwVersion(currentFirmware));
}

void InitAlertPin() {
  if (settings.enable_pin_on_alert) {
    Serial.print("alertpin: ");
    Serial.println(settings.alertpin);
    pinMode(settings.alertpin, OUTPUT);
  }
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
  timeClient.setDSTauto(&dst); // auto update on summer/winter time.
  timeClient.setTimeout(5000); // 5 seconds waiting for reply
  timeClient.begin();
  syncTime(7);
}
  
void syncTime(int8_t attempts) {
  timeClient.tick();
  if (timeClient.status() == UNIX_OK) return;
  Serial.println("Time not synced yet!");
  printNtpStatus();
  int8_t count = 1;
  while (timeClient.NTPstatus() != NTP_OK && count <= attempts) {
    Serial.print("Attempt #");
    Serial.print(count);
    Serial.print(" of ");
    Serial.println(attempts);
    if (timeClient.NTPstatus() != NTP_WAITING_REPLY) {
      Serial.println("Force update!");
      timeClient.updateNow();
    }
    timeClient.tick();
    if (count < attempts) delay(1000);
    count++;
    printNtpStatus();
  }
}

void printNtpStatus() {
  Serial.print("NTP status: ");
    switch (timeClient.NTPstatus()) {
      case 0:
        Serial.println("OK");
        Serial.print("Current date and time: ");
        Serial.println(timeClient.unixToString("DD.MM.YYYY hh:mm:ss"));
        break;
      case 1:
        Serial.println("NOT_STARTED");
        break;
      case 2:
        Serial.println("NOT_CONNECTED_WIFI");
        break;
      case 3:
        Serial.println("NOT_CONNECTED_TO_SERVER");
        break;
      case 4:
        Serial.println("NOT_SENT_PACKET");
        break;
      case 5:
        Serial.println("WAITING_REPLY");
        break;
      case 6:
        Serial.println("TIMEOUT");
        break;
      case 7:
        Serial.println("REPLY_ERROR");
        break;
      case 8:
        Serial.println("NOT_CONNECTED_ETHERNET");
        break;
      default:
        Serial.println("UNKNOWN_STATUS");
        break;
    }
}

void displayMessage(String message, int messageTextSize, String title = "") {
  display.clearDisplay();
  int bound = 0;
  if (title.length() > 0) {
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.println(utf8cyr(title));
    bound = 4 + messageTextSize;
  }
  displayCenter(message, bound, messageTextSize);
}

void rebootDevice(int time = 2000, bool async = false) {
  if (async) {
    needRebootWithDelay = time;
    return;
  }
  showServiceMessage("Перезавантаження..", time);
  delay(time);
  ESP.restart();
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
  wm.setSaveConfigCallback(saveConfigCallback);
  wm.setConfigPortalTimeout(180);
  servicePin(settings.wifipin, LOW, false);
  showServiceMessage(wm.getWiFiSSID(true), "Підключення до:", 5000);
  String apssid = String(settings.apssid) + "_" + chipID;
  if (!wm.autoConnect(apssid.c_str())) {
    Serial.println("Reboot");
    rebootDevice(5000);
    return;
  }
  // Connected to WiFi
  Serial.println("connected...yeey :)");
  servicePin(settings.wifipin, HIGH, false);
  showServiceMessage("Підключено до WiFi!");
  wm.setHttpPort(8080);
  wm.startWebPortal();
  delay(5000);
  setupRouting();
  initUpdates();
  initBroadcast();
  socketConnect();
  initHA();
  showServiceMessage(WiFi.localIP().toString(), "IP-адреса мапи:", 5000);
}

void apCallback(WiFiManager* wifiManager) {
  String title = "Підключіться до WiFi:";
  String message = wifiManager->getConfigPortalSSID();
  displayMessage(message, getTextSizeToFitDisplay(message), title);
  WiFi.onEvent(wifiEvents);
}

void saveConfigCallback() {
  showServiceMessage(wm.getWiFiSSID(true), "Збережено AP:");
  delay(2000);
  rebootDevice();
}

static void wifiEvents(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
      displayMessage(WiFi.softAPIP().toString(), getTextSizeToFitDisplay(WiFi.softAPIP().toString()), "Введіть у браузері:");
      WiFi.removeEvent(wifiEvents);
      break;
    default:
      break;
  }
}

void initUpdates() {
  ArduinoOTA.onStart(showUpdateStart);
  ArduinoOTA.onEnd(showUpdateEnd);
  ArduinoOTA.onProgress(showUpdateProgress);
  ArduinoOTA.onError(showOtaUpdateErrorMessage);
  ArduinoOTA.begin();
  Update.onProgress(showUpdateProgress);
  httpUpdate.onStart(showUpdateStart);
  httpUpdate.onEnd(showUpdateEnd);
  httpUpdate.onProgress(showUpdateProgress);
  httpUpdate.onError(showHttpUpdateErrorMessage);
}

void showUpdateProgress(size_t progress, size_t total) {
  if (total == 0) return;
  String progressText = String(progress / (total / 100)) + "%";
  showServiceMessage(progressText, "Оновлення:");
}

void showUpdateStart() {
  showServiceMessage("Починаємо!", "Оновлення:");
  delay(1000);
}

void showUpdateEnd() {
  showServiceMessage("Перезавантаження..", "Оновлення:");
  delay(1000);
}

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

void initBroadcast() {
  Serial.println("Init network device broadcast");

  if (!MDNS.begin(settings.broadcastname)) {
    Serial.println("Error setting up mDNS responder");
    showServiceMessage("Помилка mDNS");
    while (1) {
      delay(1000);
    }
  }
  Serial.printf("Device broadcasted to network: %s.local", settings.broadcastname);
  Serial.println();
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
      // Doesn't work right now. Try on next arduino HA release.
      // const char* deviceUrl = ((String) "http://"+ WiFi.localIP().toString() + ":80/").c_str();
      // Serial.println(deviceUrl);
      // device.setConfigurationUrl(deviceUrl);
      device.enableExtendedUniqueIds();
      device.enableSharedAvailability();
      device.enableLastWill();

      haUptime.setIcon("mdi:timer-outline");
      haUptime.setName("Uptime");
      haUptime.setUnitOfMeasurement("s");
      haUptime.setDeviceClass("duration");

      haWifiSignal.setIcon("mdi:wifi");
      haWifiSignal.setName("WIFI Signal");
      haWifiSignal.setUnitOfMeasurement("dBm");
      haWifiSignal.setDeviceClass("signal_strength");
      haWifiSignal.setStateClass("measurement");

      haFreeMemory.setIcon("mdi:memory");
      haFreeMemory.setName("Free Memory");
      haFreeMemory.setUnitOfMeasurement("kB");
      haFreeMemory.setDeviceClass("data_size");
      haFreeMemory.setStateClass("measurement");

      haUsedMemory.setIcon("mdi:memory");
      haUsedMemory.setName("Used Memory");
      haUsedMemory.setUnitOfMeasurement("kB");
      haUsedMemory.setDeviceClass("data_size");
      haUsedMemory.setStateClass("measurement");

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
      haMapApiConnect.setCurrentState(client_websocket.available());

      haBrightnessAuto.setOptions(getHaOptions(autoBrightnessOptions).c_str());
      haBrightnessAuto.onCommand(onHaBrightnessAutoCommand);
      haBrightnessAuto.setIcon("mdi:brightness-auto");
      haBrightnessAuto.setName("Auto Brightness");
      haBrightnessAuto.setCurrentState(settings.brightness_mode);

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
      haCpuTemp.setStateClass("measurement");

      haHomeDistrict.setIcon("mdi:home-map-marker");
      haHomeDistrict.setName("Home District");

      haLight.setIcon("mdi:led-strip-variant");
      haLight.setName("Lamp");
      haLight.setBrightnessScale(100);
      haLight.setCurrentState(settings.map_mode == 5);
      haLight.setCurrentBrightness(settings.ha_light_brightness);
      haLight.setCurrentRGBColor(HALight::RGBColor(settings.ha_light_r, settings.ha_light_g, settings.ha_light_b));
      haLight.onStateCommand(onHaLightState);
      haLight.onBrightnessCommand(onHaLightBrightness);
      haLight.onRGBColorCommand(onHaLightRGBColor);

      device.enableLastWill();
      mqtt.onStateChanged(onMqttStateChanged);
      mqtt.begin(brokerAddr, settings.ha_mqttport, mqttUser, mqttPassword);
    }
  }
}

void onMqttStateChanged(HAMqtt::ConnectionState state) {
  Serial.print("Home Assistant MQTT state changed! State:");
  Serial.println(state);
  haConnected = state == HAMqtt::StateConnected;
  servicePin(settings.hapin, haConnected ? HIGH : LOW, false);
  if (enableHA && haConnected) {
    // Update HASensors values (Unlike the other device types, the HASensor doesn't store the previous value that was set. It means that the MQTT message is produced each time the setValue method is called.)
    haMapModeCurrent.setValue(mapModes[getCurrentMapMode()]);
    haHomeDistrict.setValue(districtsAlphabetical[numDistrictToAlphabet(settings.home_district)]);
  }
}

String getHaOptions(std::vector<const char*> list) {
  String result;
  for (const char* option : list) {
    if (list[0] != option) {
      result += ";";
    }
    result += option;
  }
  return result;
}

void onHaLightState(bool state, HALight* sender) {
  if (settings.map_mode == 5 && state) return;
  int newMapMode = state ? 5 : prevMapMode;
  saveMapMode(newMapMode);
}

void onHaLightBrightness(uint8_t brightness, HALight* sender) {
  saveHaLightBrightness(brightness);
}

void onHaLightRGBColor(HALight::RGBColor rgb, HALight* sender) {
  saveHaLightRgb(rgb);
}

void onHaButtonClicked(HAButton* sender) {
  if (sender == &haReboot) {
    device.setAvailability(false);
    rebootDevice();
  } else if (sender == &haToggleMapMode) {
    mapModeSwitch();
  } else if (sender == &haToggleDisplayMode) {
    nextDisplayMode();
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

void onHaBrightnessAutoCommand(int8_t index, HASelect* sender) {
  settings.brightness_mode = index;
  preferences.begin("storage", false);
  preferences.putInt("bra", settings.brightness_mode);
  preferences.end();
  Serial.print("brightness_auto commited to preferences: ");
  Serial.println(settings.brightness_mode);
  sender->setState(index);  // report state back to the Home Assistant
  autoBrightnessUpdate();
  showServiceMessage(autoBrightnessOptions[settings.brightness_mode], "Авто. яскравість:");
}

void onHaBrightnessCommand(HANumeric haBrightness, HANumber* sender) {
  int8_t numberInt8 = haBrightness.toInt8();
  settings.brightness = numberInt8;
  preferences.begin("storage", false);
  preferences.putInt("brightness", settings.brightness);
  preferences.end();
  Serial.println("brightness commited to preferences");
  sender->setState(haBrightness);
  autoBrightnessUpdate();
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
  saveMapMode(index);
}

void onHaDisplayModeCommand(int8_t index, HASelect* sender) {
  int newDisplayMode = getRealDisplayMode(index);
  saveDisplayMode(newDisplayMode);
}

int getHaDisplayMode(int displayMode) {
  int lastModeIndex = displayModes.size() - 1;
  if (displayMode < lastModeIndex) return displayMode;
  if (displayMode == 9) return lastModeIndex;
  // default
  return 0;
}

int getRealDisplayMode(int displayMode) {
  int lastModeIndex = displayModes.size() - 1;
  if (displayMode < lastModeIndex) return displayMode;
  if (displayMode == lastModeIndex) return 9;
  // default
  return 0;
}

void initDisplay() {

  display = Adafruit_SSD1306(settings.display_width, settings.display_height, &Wire, -1);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.display();
  display.clearDisplay();
  display.setTextColor(WHITE);
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

void initI2cTempSensors() {
  Wire.begin();
  initBh1750LightSensor();
  initSht3xTempSensor();
  initHtu2xTempSensor();
  initBme280TempSensor();
  initDisplayModes();
}

void initBh1750LightSensor() {
  bh1750Inited = bh1750.begin(BH1750::CONTINUOUS_HIGH_RES_MODE_2);
  if (bh1750Inited) {
    delay(500); //waiting to get first measurement
    bh1750LightSensorCycle();
    Serial.println("Found BH1750 light sensor! Success.");
  } else {
    Serial.println("Not found BH1750 light sensor!");
  }
  // Distribute brightness levels
  distributeBrightnessLevels();
}

void initSht3xTempSensor() {
  sht3xInited = sht3x.begin();
  if (sht3xInited) {
    Serial.println("Found SHT3x temp/hum sensor! Success.");
  } else {
    Serial.println("Not found SHT3x temp/hum sensor!");
  }
}

void initHtu2xTempSensor() {
  htu2xInited = htu2x.begin();
  if (sht3xInited) {
    Serial.println("Found HTU2x temp/hum sensor! Success.");
  } else {
    Serial.println("Not found HTU2x temp/hum sensor!");
  }
}

void initBme280TempSensor() {
  bme280.begin();
  switch (bme280.chipModel()) {
    case BME280::ChipModel_BME280:
      bme280Inited = true;
      Serial.println("Found BME280 temp/hum/presure sensor! Success.");
      break;
    case BME280::ChipModel_BMP280:
      bmp280Inited = true;
      Serial.println("Found BMP280 temp/presure sensor! No Humidity available.");
      break;
    default:
      bme280Inited = false;
      bmp280Inited = false;
      Serial.println("Not found BME280 or BMP280!");
  }
}

void initDisplayModes() {
  if (bme280Inited || bmp280Inited || sht3xInited || htu2xInited) {
    displayModes.insert(displayModes.end() - 1, "Мікроклімат");
    localTempHumSensorCycle();
  } else if (settings.display_mode == displayModes.size() - 1) {
    saveDisplayMode(9);
  }
}
//--Init end

//--Update
void saveLatestFirmware() {
  std::vector<String> tempBinList = settings.fw_update_channel == 1 ? test_bin_list : bin_list;
  Firmware firmware;
  for (String& filename : tempBinList) {
    if (filename.startsWith("latest")) continue;
    Firmware parsedFirmware = parseFirmwareVersion(filename);
    if (firstIsNewer(parsedFirmware, firmware)) {
      firmware = parsedFirmware;
    }
  }
  latestFirmware = firmware;
  fwUpdateAvailable = firstIsNewer(latestFirmware, currentFirmware);
  Serial.print("Latest firmware version: ");
  Serial.println(getFwVersion(latestFirmware));
  Serial.println(fwUpdateAvailable ? "New fw available!" : "No new firmware available");
}

bool firstIsNewer(Firmware first, Firmware second) {
  if (first.major > second.major) return true;
  if (first.major == second.major) {
    if (first.minor > second.minor) return true;
    if (first.minor == second.minor) {
      if (first.patch > second.patch) return true;
      if (first.patch == second.patch) {
        if (first.isBeta && second.isBeta) {
          if (first.betaBuild > second.betaBuild) return true;
        } else {
          return !first.isBeta && second.isBeta;
        }
      }
    }
  }
  return false;
}

JsonDocument parseJson(String payload) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload);
  if (error) {
    Serial.print("Deserialization error: ");
    Serial.println(error.f_str());
    return doc;
  } else {
    return doc;
  }
}

// Home District Json Parsing
void parseHomeDistrictJson() {
  // Skip parsing if home alert time is disabled or less then 5 sec from last sync
  if ((timeClient.unixGMT() - lastHomeDistrictSync <= 5) || settings.home_alert_time == 0) return;
  // Save sync time
  lastHomeDistrictSync = timeClient.unixGMT();
  String combinedString = "district:" + String(settings.home_district);
  Serial.println(combinedString.c_str());
  client_websocket.send(combinedString.c_str());
}

void doUpdate() {
  if (initUpdate) {
    initUpdate = false;
    downloadAndUpdateFw(settings.bin_name, settings.fw_update_channel == 1);
  }
}

void downloadAndUpdateFw(String binFileName, bool isBeta) {
  char spiffUrlChar[100];
  char firmwareUrlChar[100];
  Serial.println("Building spiffs url...");
  sprintf(spiffUrlChar, "http://%s:%d%s%s", settings.serverhost, settings.updateport, isBeta ? "/beta/spiffs/spiffs_" : "/spiffs/spiffs_", binFileName.c_str());
  Serial.println("Building firmware url...");
  sprintf(firmwareUrlChar, "http://%s:%d%s%s", settings.serverhost, settings.updateport, isBeta ? "/beta/" : "/", binFileName.c_str());

  Serial.printf("Spiffs url: %s\n", spiffUrlChar);
  t_httpUpdate_return spiffsRet = httpUpdate.updateSpiffs(client, spiffUrlChar, VERSION);
  handleUpdateStatus(spiffsRet, true);

  Serial.printf("Firmware url: %s\n", firmwareUrlChar);
  t_httpUpdate_return fwRet = httpUpdate.update(client, firmwareUrlChar, VERSION);
  handleUpdateStatus(fwRet, false);
}

void handleUpdateStatus(t_httpUpdate_return ret, bool isSpiffsUpdate) {
  Serial.printf("%s update status:\n", isSpiffsUpdate ? "Spiffs" : "Firmware");
  switch (ret) {
    case HTTP_UPDATE_FAILED:
      Serial.printf("Error Occurred. Error (%d): %s\n", httpUpdate.getLastError(), httpUpdate.getLastErrorString().c_str());
      break;
    case HTTP_UPDATE_NO_UPDATES:
      Serial.println("HTTP_UPDATE_NO_UPDATES");
      break;
    case HTTP_UPDATE_OK:
      if (isSpiffsUpdate) {
        Serial.println("Spiffs update successfully completed. Starting firmware update...");
      } else {
        Serial.println("Firmware update successfully completed. Rebooting...");
        rebootDevice();
      }
      break;
  }

}
//--Update end

//--Service
void checkServicePins() {
  if (!settings.legacy) {
    if (settings.service_diodes_mode) {
      //Serial.println("Dioded enabled");
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
      if (!client_websocket.available()) {
        servicePin(settings.datapin, LOW, true);
      } else {
        servicePin(settings.datapin, HIGH, true);
      }
    } else {
      //Serial.println("Dioded disables");
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
  // read the state of the switch/button:
  currentState = digitalRead(settings.buttonpin);

  if (lastState == HIGH && currentState == LOW) {  // button is pressed
    pressedTime = millis();
    isPressing = true;
    isLongDetected = false;
  } else if (lastState == LOW && currentState == HIGH) {  // button is released
    isPressing = false;
    releasedTime = millis();

    long pressDuration = releasedTime - pressedTime;

    if (pressDuration < SHORT_PRESS_TIME) singleClick();
  }

  if (isPressing == true && isLongDetected == false) {
    long pressDuration = millis() - pressedTime;

    if (pressDuration > LONG_PRESS_TIME) {
      longClick();
      isLongDetected = true;
    }
  }

  // save the the last state
  lastState = currentState;
}

void singleClick() {
  handleClick(settings.button_mode);
}

void longClick() {
  if (settings.new_fw_notification == 1 && fwUpdateAvailable && settings.button_mode != 0 && !isDisplayOff) {
    downloadAndUpdateFw(settings.fw_update_channel == 1 ? "latest_beta.bin" : "latest.bin", settings.fw_update_channel == 1);
    return;
  }

  handleClick(settings.button_mode_long);
}

void handleClick(int event) {
  switch (event) {
    case 1:
      mapModeSwitch();
      break;
    case 2:
      nextDisplayMode();
      break;
    case 3:
      isMapOff = !isMapOff;
      showServiceMessage(!isMapOff ? "Увімкнено" : "Вимкнено", "Мапу:");
      mapCycle();
      break;
    case 4:
      isDisplayOff = !isDisplayOff;
      showServiceMessage(!isDisplayOff ? "Увімкнено" : "Вимкнено", "Дисплей:");
      break;
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
    case 6:
      nightMode = !nightMode;
      if (nightMode) {
        prevBrightness = settings.brightness;
      }
      showServiceMessage(nightMode ? "Увімкнено" : "Вимкнено", "Нічний режим:");
      autoBrightnessUpdate();
      mapCycle();
      break;
    case 7:
      rebootDevice();
      break;
    default:
      // do nothing
      break;
  }
}

void mapModeSwitch() {
  int newMapMode = settings.map_mode + 1;
  if (newMapMode > 5) {
    newMapMode = 0;
  }
  saveMapMode(newMapMode);
}

void saveMapMode(int newMapMode) {
  if (newMapMode == settings.map_mode) return;

  if (newMapMode == 5) {
    prevMapMode = settings.map_mode;
  }
  settings.map_mode = newMapMode;
  Serial.print("map_mode changed to: ");
  Serial.println(settings.map_mode);
  preferences.begin("storage", false);
  preferences.putInt("mapmode", settings.map_mode);
  preferences.end();
  Serial.println("map_mode commited to preferences");
  if (enableHA) {
    haLight.setState(settings.map_mode == 5);
    haMapMode.setState(settings.map_mode);
    haMapModeCurrent.setValue(mapModes[getCurrentMapMode()]);
  }
  showServiceMessage(mapModes[settings.map_mode], "Режим мапи:");
  // update to selected mapMode
  mapCycle();
}

void saveHaLightBrightness(int newBrightness) {
  if (settings.ha_light_brightness == newBrightness) return;
  settings.ha_light_brightness = newBrightness;
  preferences.begin("storage", false);
  preferences.putInt("ha_lbri", settings.ha_light_brightness);
  preferences.end();
  Serial.println("ha_light_brightness commited to preferences");
  Serial.print("ha_light_brightness: ");
  Serial.println(settings.ha_light_brightness);
  if (enableHA) {
    haLight.setBrightness(newBrightness);
  }
  mapCycle();
}

void saveHaLightRgb(HALight::RGBColor newRgb) {
  if (settings.ha_light_r == newRgb.red && settings.ha_light_g == newRgb.green && settings.ha_light_b != newRgb.blue) return;
  
  preferences.begin("storage", false);
  if (settings.ha_light_r != newRgb.red) {
    settings.ha_light_r = newRgb.red;
    preferences.putInt("ha_lr", settings.ha_light_r);
    Serial.print("ha_light_red commited to preferences: ");
    Serial.println(settings.ha_light_r);
  }
  if (settings.ha_light_g != newRgb.green) {
    settings.ha_light_g = newRgb.green;
    preferences.putInt("ha_lg", settings.ha_light_g);
    Serial.print("ha_light_green commited to preferences: ");
    Serial.println(settings.ha_light_g);
  }
  if (settings.ha_light_b != newRgb.blue) {
    settings.ha_light_b = newRgb.blue;
    preferences.putInt("ha_lb", settings.ha_light_b);
    Serial.print("ha_light_blue commited to preferences: ");
    Serial.println(settings.ha_light_b);
  }
  preferences.end();

  if (enableHA) {
    haLight.setRGBColor(newRgb);
  }
  mapCycle();
}

void nextDisplayMode() {
  int newDisplayMode;
  // Get last mode index without mode "Switching"
  int lastModeIndex = displayModes.size() - 2;
  if (settings.display_mode < lastModeIndex) {
    newDisplayMode = settings.display_mode + 1;
  } else if (settings.display_mode == lastModeIndex) {
    newDisplayMode = 9;
  } else {
    newDisplayMode = 0;
  }
  saveDisplayMode(newDisplayMode);
}

void saveDisplayMode(int newDisplayMode) {
  if (newDisplayMode == settings.display_mode) return;
  settings.display_mode = newDisplayMode;
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

void saveHomeDistrict(int newHomeDistrict) {
  if (newHomeDistrict == settings.home_district) return;
  settings.home_district = newHomeDistrict;
  Serial.print("home_district changed to: ");
  Serial.println(settings.home_district);
  preferences.begin("storage", false);
  preferences.putInt("hd", settings.home_district);
  preferences.end();
  Serial.println("home_district commited to preferences");
  if (enableHA) {
    haHomeDistrict.setValue(districtsAlphabetical[numDistrictToAlphabet(settings.home_district)]);
    haMapModeCurrent.setValue(mapModes[getCurrentMapMode()]);
  }
  homeAlertStart = 0;
  parseHomeDistrictJson();
  showServiceMessage(districts[settings.home_district], "Домашній регіон:", 2000);
}

//--Display start
void displayCenter(String text, int bound, int text_size) {
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
  display.setTextSize(4);
  display.getTextBounds(utf8Text, 0, 0, &x, &y, &textWidth, &height);

  if (settings.display_height > 32 && display.width() >= textWidth) {
    display.setTextWrap(true);
    return 4;
  }

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

  // check if we need activate "minute of silence mode"
  checkMinuteOfSilence();

  // update service message expiration
  serviceMessageUpdate();

  // Show service message if not expired (Always show, it's short message)
  if (!serviceMessage.expired) {
    displayServiceMessage(serviceMessage);
    return;
  }

  // Show Minute of silence mode if activated. (Priority - 0)
  if (minuteOfSilence) {
    displayMinuteOfSilence();
    return;
  }

  // Show Home Alert Time Info if enabled in settings and we have alert start time (Priority - 1)
  if (homeAlertStart > 0 && settings.home_alert_time == 1) {
    showHomeAlertInfo();
    return;
  }

  // Turn off display, if activated (Priority - 2)
  if (isDisplayOff) {
    clearDisplay();
    return;
  }

  // Show New Firmware Notification if enabled in settings and New firmware available (Priority - 3)
  if (settings.new_fw_notification == 1 && fwUpdateAvailable) {
    showNewFirmwareNotification();
    return;
  }

  // Show selected display mode in other cases (Priority - last)
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
    case 3:
      showTechInfo();
      break;
    // Display Climate info from sensor
    case 4:
      showClimate();
      break;
    // Display Mode Switching
    case 9:
      showSwitchingModes();
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

void displayMinuteOfSilence() {
  int toggleTime = 3;  // seconds
  int remainder = timeClient.second() % (toggleTime * 3);
  display.clearDisplay();
  int16_t centerY = (settings.display_height - 32) / 2;
  display.drawBitmap(0, centerY, trident_small, 32, 32, 1);
  int textSize;
  String text1;
  String text2;
  String text3;
  int gap = 40;
  if (remainder < toggleTime) {
    textSize = 1;
    text1 = utf8cyr("Шана");
    text2 = utf8cyr("Полеглим");
    text3 = utf8cyr("Героям!");
  } else if (remainder < toggleTime * 2) {
    textSize = 2;
    text1 = utf8cyr("Слава");
    text3 = utf8cyr("Україні!");
    gap = 32;
  } else {
    textSize = 2;
    text1 = utf8cyr("Смерть");
    text3 = utf8cyr("ворогам!");
    gap = 32;
  }
  display.setTextSize(textSize);

  int16_t x;
  int16_t y;
  uint16_t width;
  uint16_t height;
  display.getTextBounds(text1, 0, 0, &x, &y, &width, &height);
  display.setCursor(gap, ((settings.display_height - height) / 2) - 9);
  display.print(text1);
  display.setCursor(gap, ((settings.display_height - height) / 2));
  display.print(text2);
  display.setCursor(gap, ((settings.display_height - height) / 2) + 9);
  display.print(text3);
  display.display();
}

void displayServiceMessage(ServiceMessage message) {
  displayMessage(message.message, message.textSize, message.title);
}

void showHomeAlertInfo() {
  int toggleTime = 5;  // seconds
  int remainder = timeClient.second() % (toggleTime * 2);
  String title;
  if (remainder < toggleTime) {
    title = "Тривога триває:";
  } else {
    title = districts[settings.home_district];
  }
  String message = getStringFromTimer(timeClient.unixGMT() - homeAlertStart - timeOffset);

  displayMessage(message, getTextSizeToFitDisplay(message), title);
}

String getFwVersion(Firmware firmware) {
  String version = String(firmware.major) + "." + firmware.minor;
  if (firmware.patch > 0) {
    version += ".";
    version += firmware.patch;
  }
  if (firmware.isBeta) {
    version += "-b";
    version += firmware.betaBuild;
  }
  return version;
}

void showNewFirmwareNotification() {
  int toggleTime = 5;  // seconds
  int remainder = timeClient.second() % (toggleTime * 2);
  String title;
  String message;
  if (remainder < toggleTime) {
    title = "Доступне оновлення:";
    message = getFwVersion(latestFirmware);
  } else if (settings.button_mode == 0) {
    title = "Введіть у браузері:";
    message = WiFi.localIP().toString();
  } else {
    title = "Для оновл. натисніть";
    message = (String) "та тримайте кнопку " + (char)24;
  }
  
  displayMessage(message, getTextSizeToFitDisplay(message), title);
}

void showClock() {
  String time = timeClient.unixToString(String("hh") + getDivider() + "mm");
  String date = timeClient.unixToString("DSTRUA DD.MM.YYYY");
  displayMessage(time, getTextSizeToFitDisplay(time), date);
}

void showTemp() {
  char roundedTemp[4];
  int position = calculateOffset(settings.home_district);
  dtostrf(weather_leds[position], 3, 1, roundedTemp);
  String temp = String(roundedTemp) + (char)128 + "C";
  displayMessage(temp, getTextSizeToFitDisplay(temp), districts[settings.home_district]);
}

void showTechInfo() {
  int toggleTime = settings.display_mode_time;  // seconds
  int remainder = timeClient.second() % (toggleTime * 6);
  String title;
  String message;
  // IP address
  if (remainder < toggleTime) {
    title = "IP-адреса мапи:";
    message = WiFi.localIP().toString();
    // Wifi Signal level
  } else if (remainder < toggleTime * 2) {
    title = "Сигнал WiFi:";
    message += rssi;
    message += " dBm";
    // Uptime
  } else if (remainder < toggleTime * 3) {
    title = "Час роботи:";
    message = getStringFromTimer(millis() / 1000);
    // map-API status
  } else if (remainder < toggleTime * 4) {
    title = "Статус map-API:";
    message = apiConnected ? "Підключено" : "Відключено";
    // HA Status
  } else if (remainder < toggleTime * 5) {
    title = "Home Assistant:";
    message = haConnected ? "Підключено" : "Відключено";
  } else {
    title = "Версія прошивки:";
    message = VERSION;
  }

  displayMessage(message, getTextSizeToFitDisplay(message), title);
}

void showClimate() {
  int toggleTime = settings.display_mode_time;  // seconds
  int remainder = timeClient.second() % (toggleTime * getClimateInfoSize());
  if (remainder < toggleTime) {
    showLocalClimateInfo(0);
  } else if (remainder < toggleTime * 2) {
    showLocalClimateInfo(1);
  } else if (remainder < toggleTime * 3) {
    showLocalClimateInfo(2);
  }
}

void showLocalTemp() {
  char roundedTemp[5];
  dtostrf(localTemp, 5, 1, roundedTemp);
  String message = String(roundedTemp) + (char)128 + "C";
  displayMessage(message, getTextSizeToFitDisplay(message), "Температура");
}

void showLocalHum() {
  char roundedHum[5];
  dtostrf(localHum, 5, 1, roundedHum);
  String message = String(roundedHum) + "%";

  displayMessage(message, getTextSizeToFitDisplay(message), "Вологість");
}

void showLocalPresure() {
  char roundedPres[6];
  dtostrf(localPresure, 6, 1, roundedPres);
  String message = String(roundedPres) + "mmHg";
  displayMessage(message, getTextSizeToFitDisplay(message), "Тиск");
}

void showLocalClimateInfo(int index) {
  if (index == 0 && localTemp > -273) {
    showLocalTemp();
    return;
  }
  if (index <= 1 && localHum > 0) {
    showLocalHum();
    return;
  }
  if (index <= 2 && localPresure > 0) {
    showLocalPresure();
    return;
  }
}

int getClimateInfoSize() {
  int size = 0;
  if (localTemp > -273) size++;
  if (localHum > 0) size++;
  if (localPresure > 0) size++;
  return size;
}

String getStringFromTimer(long timerSeconds) {
  String message;
  unsigned long seconds = timerSeconds;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  if (hours >= 99) {
    return "99+ год.";
  } else {
    String message;
    seconds %= 60;
    minutes %= 60;
    String divider = getDivider();
    if (hours > 0) {
      if (hours < 10) message += "0";
      message += hours;
      message += divider;
    }
    if (minutes < 10) message += "0";
    message += minutes;
    if (hours == 0) {
      message += divider;
      if (seconds < 10) message += "0";
      message += seconds;
    }
    return message;
  }
}

void showSwitchingModes() {
  int toggleTime = settings.display_mode_time;
  int remainder = timeClient.second() % (toggleTime * (2 + getClimateInfoSize()));
  if (remainder < toggleTime) {
    // Display Mode Clock
    showClock();
  } else if (remainder < toggleTime * 2) {
    // Display Mode Temperature
    showTemp();
  } else if (remainder < toggleTime * 3) {
    showLocalClimateInfo(0);
  } else if (remainder < toggleTime * 4) {
    showLocalClimateInfo(1);
  } else if (remainder < toggleTime * 5) {
    showLocalClimateInfo(2);
  }
}

String getDivider() {
  // Change every second
  if (timeClient.second() % 2 == 0) {
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
  if (parts[1].indexOf("-b") > 0) {
    int indexOfBeta = parts[1].indexOf("-b");
    firmware.minor = atoi(parts[1].substring(0, indexOfBeta).c_str());
    firmware.isBeta = true;
    firmware.betaBuild = atoi(parts[1].substring(indexOfBeta + 2, parts[1].length()).c_str());
  } else {
    firmware.minor = atoi(parts[1].c_str());
  }
  if (parts[2] == "bin" || parts[2] == NULL) {
    firmware.patch = 0;
  } else if (parts[2].indexOf("-b") > 0) {
    int indexOfBeta = parts[2].indexOf("-b");
    firmware.patch = atoi(parts[2].substring(0, indexOfBeta).c_str());
    firmware.isBeta = true;
    firmware.betaBuild = atoi(parts[2].substring(indexOfBeta + 2, parts[2].length()).c_str());
  } else {
    firmware.patch = atoi(parts[2].c_str());
  }
  return firmware;
}

//--Web server start
void setupRouting() {
  Serial.println("Init WebServer");
  webserver.on("/", HTTP_GET, handleRoot);
  webserver.on("/saveBrightness", HTTP_POST, handleSaveBrightness);
  webserver.on("/saveColors", HTTP_POST, handleSaveColors);
  webserver.on("/saveWeather", HTTP_POST, handleSaveWeather);
  webserver.on("/saveModes", HTTP_POST, handleSaveModes);
  webserver.on("/saveDev", HTTP_POST, handleSaveDev);
  webserver.on("/saveFirmware", HTTP_POST, handleSaveFirmware);
  webserver.on("/update", HTTP_POST, handleUpdate);
  webserver.begin();
  Serial.println("Webportal running");
}

String disableRange(bool isDisabled) {
  return isDisabled ? " disabled" : "";
}

String floatToString(float value, int prec) {
  char result[10];
  dtostrf(value, 2 + prec, prec, result);
  return String(result);
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
  html += "                <img class='full-screen-img' src='http://alerts.net.ua/";
  switch (getCurrentMapMode()) {
    case 0:
      html += "off_map.png";
      break;
    case 2:
      html += "weather_map.png";
      break;
    case 3:
      html += "flag_map.png";
      break;
    case 4:
      html += "random_map.png";
      break;
    case 5:
      html += "lamp_map.png";
      break;
    default:
      html += "alerts_map.png";
  }
  html += "'>";
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
  if (fwUpdateAvailable) {
    html += "        <div class='row'>";
    html += "           <div class='col-md-6 offset-md-3'>";
    html += "              <div class='row'>";
    html += "                 <div class='box_yellow col-md-12 mt-2' style='background-color: #ffc107; color: #212529'>";
    html += "                    <h8>Доступна нова версія прошивки <a href='https://github.com/v00g100skr/ukraine_alarm_map/releases/tag/" + getFwVersion(latestFirmware) + "'>" + getFwVersion(latestFirmware) + "</a></br>Для оновлення перейдіть в розділ \"Прошивка\"</h8>";
    html += "                </div>";
    html += "              </div>";
    html += "            </div>";
    html += "        </div>";
  }
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
  html += "        <form action='/saveBrightness' method='POST'>";
  html += "        <div class='row collapse' id='collapseBrightness' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Загальна: <span id='sliderValue1'>" + String(settings.brightness) + "</span>%</label>";
  html += "                        <input type='range' name='brightness' class='form-control-range' id='slider1' min='0' max='100' value='" + String(settings.brightness) + "'" + disableRange(settings.brightness_mode == 1 || settings.brightness_mode == 2) + ">";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Денна: <span id='sliderValue13'>" + String(settings.brightness_day) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_day' class='form-control-range' id='slider13' min='0' max='100' value='" + String(settings.brightness_day) + "'" + disableRange(settings.brightness_mode == 0) + ">";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Нічна: <span id='sliderValue14'>" + String(settings.brightness_night) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_night' class='form-control-range' id='slider14' min='0' max='100' value='" + String(settings.brightness_night) + "'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Початок дня: <span id='sliderValue15'>" + String(settings.day_start) + "</span> година</label>";
  html += "                        <input type='range' name='day_start' class='form-control-range' id='slider15' min='0' max='24' value='" + String(settings.day_start) + "'" + disableRange(settings.brightness_mode == 0 || settings.brightness_mode == 2) + ">";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider1'>Початок ночі: <span id='sliderValue16'>" + String(settings.night_start) + "</span> година</label>";
  html += "                        <input type='range' name='night_start' class='form-control-range' id='slider16' min='0' max='24' value='" + String(settings.night_start) + "'" + disableRange(settings.brightness_mode == 0 || settings.brightness_mode == 2) + ">";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox12'>Автоматична яскравість</label>";
  html += "                        <select name='brightness_auto' class='form-control' id='selectBox12'>";
  for (int i = 0; i < autoBrightnessOptions.size(); i++) {
    html += "<option value='";
    html += i;
    html += "'";
    if (settings.brightness_mode == i) html += " selected";
    html += ">";
    html += autoBrightnessOptions[i];
    html += "</option>";
  }
  html += "                        </select>";
  html += "                    </div>";
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
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider24'>Коефіцієнт чутливості сенсора освітлення: <span id='sliderValue24'>" + floatToString(settings.light_sensor_factor, 1) + "</span></label>";
  html += "                        <input type='range' name='light_sensor_factor' class='form-control-range' id='slider24' min='0.1' max='10' step='0.1' value='" + String(settings.light_sensor_factor) + "'>";
  html += "                    </div>";
  html += "                    <p class='text-info'>Коефіцієнт чутливості працює наступним чином: Значення менше 1 - знижує чутливість, більше 1 - підвищує. Формула для розрахунку - <b>L = Ls * K</b>, де <b>Ls</b> - дані з сенсора, <b>K</b> - коефіцієнт чутливості, <b>L</b> - рівень освітлення, що використовується для регулювання яскравості мапи.<br>Детальніше на <a href='https://github.com/v00g100skr/ukraine_alarm_map/wiki/%D0%A1%D0%B5%D0%BD%D1%81%D0%BE%D1%80-%D0%BE%D1%81%D0%B2%D1%96%D1%82%D0%BB%D0%B5%D0%BD%D0%BD%D1%8F'>Wiki</a>.</p>";
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/saveColors' method='POST'>";
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
  html += "        <form action='/saveWeather' method='POST'>";
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
  html += "        <form action='/saveModes' method='POST'>";
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
  html += "                       <label for='slider19'>Колір режиму \"Лампа\": <span id='sliderValue19'>0</span></label><br/>";
  html += "                       <div class='color-box' id='colorBox17'></div>";
  html += "                       <input type='range' name='color_lamp' class='form-control-range' id='slider19' min='0' max='360' value='0'>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='slider20'>Яскравість режиму \"Лампа\": <span id='sliderValue20'>" + String(settings.ha_light_brightness) + "</span>%</label>";
  html += "                        <input type='range' name='brightness_lamp' class='form-control-range' id='slider20' min='1' max='100' value='" + String(settings.ha_light_brightness) + "'>";
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
  if (sht3xInited || bme280Inited || bmp280Inited || htu2xInited) {
    html += "                    <div class='form-group'>";
    html += "                        <label for='slider21'>Корегування температури: <span id='sliderValue21'>" + floatToString(settings.temp_correction, 1) + "</span> °C</label>";
    html += "                        <input type='range' name='temp_correction' class='form-control-range' id='slider21' min='-10' max='10' step='0.1' value='" + String(settings.temp_correction) + "'>";
    html += "                    </div>";
  }
  if (sht3xInited || bme280Inited || htu2xInited) {
    html += "                    <div class='form-group'>";
    html += "                        <label for='slider22'>Корегування вологості: <span id='sliderValue22'>" + floatToString(settings.hum_correction, 1) + "</span> %</label>";
    html += "                        <input type='range' name='hum_correction' class='form-control-range' id='slider22' min='-20' max='20' step='0.5' value='" + String(settings.hum_correction) + "'>";
    html += "                    </div>";
  }
  if (bme280Inited || bmp280Inited) {
    html += "                    <div class='form-group'>";
    html += "                        <label for='slider23'>Корегування тиску: <span id='sliderValue23'>" + floatToString(settings.presure_correction, 1) + "</span> мм.рт.ст.</label>";
    html += "                        <input type='range' name='presure_correction' class='form-control-range' id='slider23' min='-50' max='50' step='0.5' value='" + String(settings.presure_correction) + "'>";
    html += "                    </div>";
  }
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox6'>Режим кнопки (Single Click)</label>";
  html += "                        <select name='button_mode' class='form-control' id='selectBox6'>";
  for (int i = 0; i < singleClickOptions.size(); i++) {
    html += "<option value='";
    html += i;
    html += "'";
    if (settings.button_mode == i) html += " selected";
    html += ">";
    html += singleClickOptions[i];
    html += "</option>";
  }
  html += "                        </select>";
  html += "                    </div>";
  html += "                    <div class='form-group'>";
  html += "                        <label for='selectBox10'>Режим кнопки (Long Click)</label>";
  html += "                        <select name='button_mode_long' class='form-control' id='selectBox10'>";
  for (int i = 0; i < longClickOptions.size(); i++) {
    html += "<option value='";
    html += i;
    html += "'";
    if (settings.button_mode_long == i) html += " selected";
    html += ">";
    html += longClickOptions[i];
    html += "</option>";
  }
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
  html += "                    <div class='form-group form-check'>";
  html += "                        <input name='min_of_silence' type='checkbox' class='form-check-input' id='checkbox6'";
  if (settings.min_of_silence == 1) html += " checked";
  html += ">";
  html += "                        <label class='form-check-label' for='checkbox6'>";
  html += "                          Активувати режим \"Хвилина мовчання\" (щоранку о 09:00)";
  html += "                        </label>";
  html += "                    </div>";
  html += "                      <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/saveDev' method='POST'>";
  html += "        <div class='row collapse' id='collapseTech' data-parent='#accordion'>";
  html += "           <div class='col-md-6 offset-md-3'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <b>";
  html += "                      <p class='text-danger'>УВАГА: будь-яка зміна налаштування в цьому розділі призводить до примусувого перезаватаження мапи.</p>";
  html += "                      <p class='text-danger'>УВАГА: деякі зміни налаштувань можуть привести до часткової або повної відмови прoшивки, якщо налаштування будуть несумісні з логікою роботи. Будьте впевнені, що Ви точно знаєте, що міняється і для чого.</p>";
  html += "                      <p class='text-danger'>У випадку, коли мапа втратить і не відновить працездатність після змін і перезавантаження (при умові втрати доступу до сторінки керування) - необхідно перепрошити мапу з нуля за допомогою скетча updater.ino (або firmware.ino, якщо Ви збирали прошивку самі Arduino IDE) з репозіторія JAAM за допомогою Arduino IDE, виставивши примусове стирання внутрішньої памʼяті в меню Tools -> Erase all memory before sketch upload</p>";
  html += "                    </b>";
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
  html += "                        <label for='inputField8'>Порт WebSockets</label>";
  html += "                        <input type='text' name='websocket_port' class='form-control' id='inputField8' value='" + String(settings.websocket_port) + "'>";
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
  html += "                      <div class='form-group'>";
  html += "                          <label for='inputField12'>Пін, який замкнеться при тривозі у дом. регіоні (має бути digital)</label>";
  html += "                          <input type='text' name='alertpin' class='form-control' id='inputField12' value='" + String(settings.alertpin) + "'>";
  html += "                      </div>";
  html += "                      <div class='form-group form-check'>";
  html += "                          <input name='enable_pin_on_alert' type='checkbox' class='form-check-input' id='checkbox6'";
  if (settings.enable_pin_on_alert == 1) html += " checked";
  html += ">";
  html += "                          <label class='form-check-label' for='checkbox6'>";
  html += "                            Замикати пін " + String(settings.alertpin) + " при тривозі у дом. регіоні";
  html += "                          </label>";
  html += "                      </div>";
  html += "                      <div class='form-group'>";
  html += "                          <label for='inputField13'>Пін сенсора освітлення (має бути analog)</label>";
  html += "                          <input type='text' name='lightpin' class='form-control' id='inputField12' value='" + String(settings.lightpin) + "'>";
  html += "                      </div>";
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
  html += "                       <form action='/saveFirmware' method='POST'>";
  html += "                          <div class='form-group form-check'>";
  html += "                              <input name='new_fw_notification' type='checkbox' class='form-check-input' id='checkbox5'";
  if (settings.new_fw_notification == 1) html += " checked";
  html += ">";
  html += "                              <label class='form-check-label' for='checkbox5'>";
  html += "                                  Сповіщення про нові прошивки на екрані";
  html += "                              </label>";
  html += "                          </div>";
  html += "                          <div class='form-group'>";
  html += "                              <label for='selectBox11'>Канал оновлення прошивок</label>";
  html += "                              <select name='fw_update_channel' class='form-control' id='selectBox11'>";
  for (int i = 0; i < fwUpdateChannels.size(); i++) {
    html += "<option value='";
    html += i;
    html += "'";
    if (settings.fw_update_channel == i) html += " selected";
    html += ">" + String(fwUpdateChannels[i]) + "</option>";
  }
  html += "                              </select>";
  html += "                              <b><p class='text-danger'>УВАГА: Прошивки, що розповсюджуються BETA каналом можуть містити помилки, або вивести мапу з ладу. Якщо у Вас немає можливості прошити мапу через кабель, або ви не знаєте як це зробити, будь ласка, залишайтесь на каналі PRODUCTION!</p></b>";
  html += "                          </div>";
  html += "                          <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                       </form>";
  html += "                       <form action='/update' method='POST'>";
  html += "                          <div class='form-group'>";
  html += "                              <label for='selectBox9'>Файл прошивки</label>";
  html += "                              <select name='bin_name' class='form-control' id='selectBox9'>";
  std::vector<String> tempBinList = settings.fw_update_channel == 1 ? test_bin_list : bin_list;
  for (String& filename : tempBinList) {
    html += "<option value='" + filename + "'";
    if (filename == "latest.bin" || filename == "latest_beta.bin") html += " selected";
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
  html += "        const sliders = ['slider1', 'slider3', 'slider4', 'slider5', 'slider6', 'slider7', 'slider8', 'slider9', 'slider10', 'slider11', 'slider12', 'slider13', 'slider14', 'slider15', 'slider16', 'slider17', 'slider18', 'slider19', 'slider20'";
   if (sht3xInited || bme280Inited || bmp280Inited || htu2xInited) {
    html += ", 'slider21'";
  }
  if (sht3xInited || bme280Inited || htu2xInited) {
    html += ", 'slider22'";
  }
  if (bme280Inited || bmp280Inited) {
    html += ", 'slider23'";
  }
  html += ", 'slider24'];";
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
  html += "        const initialRgbColor6 = { r: " + String(settings.ha_light_r) + ", g: " + String(settings.ha_light_g) + ", b: " + String(settings.ha_light_b) + " };";
  html += "        document.getElementById('colorBox17').style.backgroundColor = `rgb(${initialRgbColor6.r}, ${initialRgbColor6.g}, ${initialRgbColor6.b})`;";
  html += "        const initialHue6 = rgbToHue(initialRgbColor6.r, initialRgbColor6.g, initialRgbColor6.b);";
  html += "        document.getElementById('slider19').value = initialHue6;";
  html += "        document.getElementById('sliderValue19').textContent = initialHue6;";
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
  html += "        function rgbToHue(r, g, b) {";
  html += "            var h;";
  html += "            r /= 255, g /= 255, b /= 255;";
  html += "            var max = Math.max(r, g, b), min = Math.min(r, g, b);";
  html += "            if (max-min == 0) {";
  html += "                return 0;";
  html += "            }";
  html += "            if (max == r) {";
  html += "                h = (g-b)/(max-min);";
  html += "            }";
  html += "            else if (max == g) {";
  html += "                h = 2 +(b-r)/(max-min);";
  html += "            }";
  html += "            else if (max == b) {";
  html += "                h = 4 + (r-g)/(max-min);";
  html += "            }";
  html += "            h = h*60;";
  html += "            h %= 360;";
  html += "            if (h < 0) {";
  html += "                h += 360;";
  html += "            }";
  html += "            return Math.round(h);";
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
  html += "";
  html += "        $('select[name=brightness_auto]').change(function() {";
  html += "            const selectedOption =  $(this).val();";
  html += "            console.log('Selected auto_brightness option: '.concat(selectedOption));";
  html += "            $('input[name=brightness]').prop('disabled', selectedOption == 1 || selectedOption == 2);";
  html += "            $('input[name=brightness_day]').prop('disabled', selectedOption == 0);";
  html += "            $('input[name=day_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);";
  html += "            $('input[name=night_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);";
  html += "        });";


  html += "    </script>";
  html += "</body>";
  html += "</html>";
  request->send(200, "text/html", html);
}

HALight::RGBColor hue2rgb(int hue) {
  float r, g, b;

  float h = hue / 360.0;
  float s = 1.0;
  float v = 1.0;

  int i = floor(h * 6);
  float f = h * 6 - i;
  float p = v * (1 - s);
  float q = v * (1 - f * s);
  float t = v * (1 - (1 - f) * s);

  switch (i % 6) {
    case 0: r = v, g = t, b = p; break;
    case 1: r = q, g = v, b = p; break;
    case 2: r = p, g = v, b = t; break;
    case 3: r = p, g = q, b = v; break;
    case 4: r = t, g = p, b = v; break;
    case 5: r = v, g = p, b = q; break;
    default: r = 1.0, g = 1.0, b = 1.0; break;
  }

  return HALight::RGBColor(round(r * 255), round(g * 255), round(b * 255));
}

void handleUpdate(AsyncWebServerRequest* request) {
  Serial.println("do_update triggered");
  initUpdate = true;
  if (request->hasParam("bin_name", true)) {
    settings.bin_name = strdup(request->getParam("bin_name", true)->value().c_str());
  }
  request->redirect("/");
}

void handleSaveBrightness(AsyncWebServerRequest* request) {
  preferences.begin("storage", false);
  if (request->hasParam("brightness", true)) {
    if (request->getParam("brightness", true)->value().toInt() != settings.brightness) {
      settings.brightness = request->getParam("brightness", true)->value().toInt();
      preferences.putInt("brightness", settings.brightness);
      if (enableHA) {
        haBrightness.setState(settings.brightness);
      }
      Serial.println("brightness commited to preferences");
    }
  }
  if (request->hasParam("brightness_day", true)) {
    if (request->getParam("brightness_day", true)->value().toInt() != settings.brightness_day) {
      settings.brightness_day = request->getParam("brightness_day", true)->value().toInt();
      preferences.putInt("brd", settings.brightness_day);
      Serial.println("brightness_day commited to preferences");
      distributeBrightnessLevels();
    }
  }
  if (request->hasParam("brightness_night", true)) {
    if (request->getParam("brightness_night", true)->value().toInt() != settings.brightness_night) {
      settings.brightness_night = request->getParam("brightness_night", true)->value().toInt();
      preferences.putInt("brn", settings.brightness_night);
      Serial.println("brightness_night commited to preferences");
      distributeBrightnessLevels();
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
  if (request->hasParam("brightness_auto", true)) {
    if (request->getParam("brightness_auto", true)->value().toInt() != settings.brightness_mode) {
      settings.brightness_mode = request->getParam("brightness_auto", true)->value().toInt();
      if (enableHA) {
        haBrightnessAuto.setState(settings.brightness_mode);
      }
      preferences.putInt("bra", settings.brightness_mode);
      Serial.println("brightness_auto commited to preferences");
      showServiceMessage(autoBrightnessOptions[settings.brightness_mode], "Авто. яскравість:");
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
  if (request->hasParam("light_sensor_factor", true)) {
    if (request->getParam("light_sensor_factor", true)->value().toFloat() != settings.light_sensor_factor) {
      settings.light_sensor_factor = request->getParam("light_sensor_factor", true)->value().toFloat();
      preferences.putFloat("lsf", settings.light_sensor_factor);
      Serial.print("light_sensor_factor commited to preferences: ");
      Serial.println(settings.light_sensor_factor);
    }
  }
  preferences.end();
  autoBrightnessUpdate();
  request->redirect("/");
}

void handleSaveColors(AsyncWebServerRequest* request) {
  preferences.begin("storage", false);
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
  preferences.end();
  request->redirect("/");
}

void handleSaveWeather(AsyncWebServerRequest* request) {
  preferences.begin("storage", false);
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
  preferences.end();
  request->redirect("/");
}

void handleSaveModes(AsyncWebServerRequest* request) {
  bool reboot = false;
  // this part saves values to prefs individually, and begins and ends prefs sessions each time
  if (request->hasParam("map_mode", true)) {
    if (request->getParam("map_mode", true)->value().toInt() != settings.map_mode) {
      int newMapMode = request->getParam("map_mode", true)->value().toInt();
      saveMapMode(newMapMode);
    }
  }
  if (request->hasParam("color_lamp", true)) {
    int selectedHue = request->getParam("color_lamp", true)->value().toInt();
    HALight::RGBColor rgb = hue2rgb(selectedHue);
    saveHaLightRgb(rgb);
  }
  if (request->hasParam("brightness_lamp", true)) {
    int selectedBrightness = request->getParam("brightness_lamp", true)->value().toInt();
    if (selectedBrightness != settings.ha_light_brightness) {
      saveHaLightBrightness(selectedBrightness);
    }
  }
  if (request->hasParam("display_mode", true)) {
    if (request->getParam("display_mode", true)->value().toInt() != settings.display_mode) {
      int newDisplayMode = request->getParam("display_mode", true)->value().toInt();
      saveDisplayMode(newDisplayMode);
    }
  }
  if (request->hasParam("home_district", true)) {
    if (request->getParam("home_district", true)->value().toInt() != settings.home_district) {
      int newHomeDistrict = request->getParam("home_district", true)->value().toInt();
      saveHomeDistrict(newHomeDistrict);
    }
  }

  // this part saves values to prefs directlly here, so we have one prefs session for this
  preferences.begin("storage", false);
  if (request->hasParam("display_mode_time", true)) {
    if (request->getParam("display_mode_time", true)->value().toInt() != settings.display_mode_time) {
      settings.display_mode_time = request->getParam("display_mode_time", true)->value().toInt();
      preferences.putInt("dmt", settings.display_mode_time);
      Serial.println("display_mode_time commited to preferences");
    }
  }
  if (request->hasParam("temp_correction", true)) {
    if (request->getParam("temp_correction", true)->value().toFloat() != settings.temp_correction) {
      settings.temp_correction = request->getParam("temp_correction", true)->value().toFloat();
      preferences.putFloat("ltc", settings.temp_correction);
      Serial.print("temp_correction commited to preferences: ");
      Serial.println(settings.temp_correction);
      localTempHumSensorCycle();
    }
  }
  if (request->hasParam("hum_correction", true)) {
    if (request->getParam("hum_correction", true)->value().toFloat() != settings.hum_correction) {
      settings.hum_correction = request->getParam("hum_correction", true)->value().toFloat();
      preferences.putFloat("lhc", settings.hum_correction);
      Serial.print("hum_correction commited to preferences: ");
      Serial.println(settings.hum_correction);
      localTempHumSensorCycle();
    }
  }
  if (request->hasParam("presure_correction", true)) {
    if (request->getParam("presure_correction", true)->value().toFloat() != settings.presure_correction) {
      settings.presure_correction = request->getParam("presure_correction", true)->value().toFloat();
      preferences.putFloat("lpc", settings.presure_correction);
      Serial.print("presure_correction commited to preferences: ");
      Serial.println(settings.presure_correction);
      localTempHumSensorCycle();
    }
  }
  if (request->hasParam("button_mode", true)) {
    if (request->getParam("button_mode", true)->value().toInt() != settings.button_mode) {
      settings.button_mode = request->getParam("button_mode", true)->value().toInt();
      preferences.putInt("bm", settings.button_mode);
      Serial.println("button_mode commited to preferences");
    }
  }
  if (request->hasParam("button_mode_long", true)) {
    if (request->getParam("button_mode_long", true)->value().toInt() != settings.button_mode) {
      settings.button_mode_long = request->getParam("button_mode_long", true)->value().toInt();
      preferences.putInt("bml", settings.button_mode_long);
      Serial.println("button_mode_long commited to preferences");
    }
  }
  if (request->hasParam("kyiv_district_mode", true)) {
    if (request->getParam("kyiv_district_mode", true)->value().toInt() != settings.kyiv_district_mode) {
      settings.kyiv_district_mode = request->getParam("kyiv_district_mode", true)->value().toInt();
      preferences.putInt("kdm", settings.kyiv_district_mode);
      Serial.println("kyiv_district_mode commited to preferences");
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
  if (request->hasParam("alarms_notify_mode", true)) {
    if (request->getParam("alarms_notify_mode", true)->value().toInt() != settings.alarms_notify_mode) {
      settings.alarms_notify_mode = request->getParam("alarms_notify_mode", true)->value().toInt();
      preferences.putInt("anm", settings.alarms_notify_mode);
      Serial.println("alarms_notify_mode commited to preferences");
    }
  }
  if (request->hasParam("display_height", true)) {
    if (request->getParam("display_height", true)->value().toInt() != settings.display_height) {
      reboot = true;
      settings.display_height = request->getParam("display_height", true)->value().toInt();
      preferences.putInt("dh", settings.display_height);
      Serial.print("display_height commited to preferences: ");
      Serial.println(settings.display_height);
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
  if (request->hasParam("min_of_silence", true)) {
    if (settings.min_of_silence == 0) {
      settings.min_of_silence = 1;
      preferences.putInt("mos", settings.min_of_silence);
      Serial.println("min_of_silence enabled to preferences");
    }
  } else {
    if (settings.min_of_silence == 1) {
      settings.min_of_silence = 0;
      preferences.putInt("mos", settings.min_of_silence);
      Serial.println("min_of_silence disabled to preferences");
    }
  }
  preferences.end();
  request->redirect("/");
  if (reboot) {
    rebootDevice(3000, true);
  }
}

void handleSaveDev(AsyncWebServerRequest* request) {
  preferences.begin("storage", false);
  bool reboot = false;
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
  if (request->hasParam("ha_mqttport", true)) {
    if (request->getParam("ha_mqttport", true)->value().toInt() != settings.ha_mqttport) {
      reboot = true;
      settings.ha_mqttport = request->getParam("ha_mqttport", true)->value().toInt();
      preferences.putInt("ha_mqttport", settings.ha_mqttport);
      Serial.println("ha_mqttport commited to preferences");
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
  if (request->hasParam("serverhost", true)) {
    String local_host = String(settings.serverhost);
    if (request->getParam("serverhost", true)->value() != local_host) {
      reboot = true;
      settings.serverhost = strdup(request->getParam("serverhost", true)->value().c_str());
      preferences.putString("host", request->getParam("serverhost", true)->value());
      Serial.println("serverhost commited to preferences");
    }
  }
  if (request->hasParam("websocket_port", true)) {
    if (request->getParam("websocket_port", true)->value().toInt() != settings.websocket_port) {
      reboot = true;
      settings.websocket_port = request->getParam("websocket_port", true)->value().toInt();
      preferences.putInt("wsp", settings.websocket_port);
      Serial.println("websocket_port commited to preferences");
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
      Serial.print("pixelpin commited: ");
      Serial.println(settings.pixelpin);
    }
  }
  if (request->hasParam("buttonpin", true)) {
    if (request->getParam("buttonpin", true)->value().toInt() != settings.buttonpin) {
      reboot = true;
      settings.buttonpin = request->getParam("buttonpin", true)->value().toInt();
      preferences.putInt("bp", settings.buttonpin);
      Serial.print("buttonpin commited: ");
      Serial.println(settings.buttonpin);
    }
  }
  if (request->hasParam("alertpin", true)) {
    if (request->getParam("alertpin", true)->value().toInt() != settings.alertpin) {
      reboot = true;
      settings.alertpin = request->getParam("alertpin", true)->value().toInt();
      preferences.putInt("ap", settings.alertpin);
      Serial.print("alertpin commited: ");
      Serial.println(settings.alertpin);
    }
  }
  if (request->hasParam("lightpin", true)) {
    if (request->getParam("lightpin", true)->value().toInt() != settings.lightpin) {
      reboot = true;
      settings.lightpin = request->getParam("lightpin", true)->value().toInt();
      preferences.putInt("lp", settings.lightpin);
      Serial.print("lightpin commited: ");
      Serial.println(settings.lightpin);
    }
  }
  if (request->hasParam("enable_pin_on_alert", true)) {
    if (settings.enable_pin_on_alert == 0) {
      settings.enable_pin_on_alert = 1;
      reboot = true;
      preferences.putInt("epoa", settings.enable_pin_on_alert);
      Serial.println("enable_pin_on_alert enabled to preferences");
    }
  } else {
    if (settings.enable_pin_on_alert == 1) {
      settings.enable_pin_on_alert = 0;
      reboot = true;
      preferences.putInt("epoa", settings.enable_pin_on_alert);
      Serial.println("enable_pin_on_alert disabled to preferences");
    }
  }
  preferences.end();
  request->redirect("/");
  if (reboot) {
    rebootDevice(3000, true);
  }
}

void handleSaveFirmware(AsyncWebServerRequest* request) {
  preferences.begin("storage", false);
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
  if (request->hasParam("fw_update_channel", true)) {
    if (request->getParam("fw_update_channel", true)->value().toInt() != settings.fw_update_channel) {
      settings.fw_update_channel = request->getParam("fw_update_channel", true)->value().toInt();
      preferences.putInt("fwuc", settings.fw_update_channel);
      Serial.println("fw_update_channel commited to preferences");
      saveLatestFirmware();
    }
  }
  preferences.end();
  request->redirect("/");
}
//--Web server end

//--Service messages start
void uptime() {
  int   uptimeValue   = millis() / 1000;
  float totalHeapSize = ESP.getHeapSize() / 1024.0;
  float freeHeapSize  = ESP.getFreeHeap() / 1024.0;
  float usedHeapSize  = totalHeapSize - freeHeapSize;
  float cpuTemp       = temperatureRead();
            
  rssi = WiFi.RSSI();

  if (enableHA) {
    haUptime.setValue(uptimeValue);
    haWifiSignal.setValue(rssi);
    haFreeMemory.setValue(freeHeapSize);
    haUsedMemory.setValue(usedHeapSize);
    haCpuTemp.setValue(cpuTemp);
  }
}

void connectStatuses() {
  Serial.print("Map API connected: ");
  apiConnected = client_websocket.available();
  Serial.println(apiConnected);
  haConnected = false;
  if (enableHA) {
    Serial.print("Home Assistant MQTT connected: ");
    Serial.println(mqtt.isConnected());
    if (mqtt.isConnected()) {
      haConnected = true;
      servicePin(settings.hapin, HIGH, false);
    } else {
      servicePin(settings.hapin, LOW, false);
    }
    haMapApiConnect.setState(apiConnected, true);
  }
}

void distributeBrightnessLevels() {
  int minBrightness = min(settings.brightness_day, settings.brightness_night);
  int maxBrightness = max(settings.brightness_day, settings.brightness_night);
  int step = round(maxBrightness - minBrightness) / (BR_LEVELS_COUNT - 1);
  Serial.print("Brightness levels: [");
  for (int i = 0; i < BR_LEVELS_COUNT; i++) {
    brightnessLevels[i] = i == BR_LEVELS_COUNT - 1 ? maxBrightness : minBrightness + i * step;
    Serial.print(brightnessLevels[i]);
    if (i < BR_LEVELS_COUNT - 1) Serial.print(", ");
  }
  Serial.println("]");
}

void autoBrightnessUpdate() {
  int tempBrightness = getCurrentBrightnes();
  if (tempBrightness != settings.current_brightness) {
    settings.current_brightness = tempBrightness;
    preferences.begin("storage", false);
    preferences.putInt("cbr", settings.current_brightness);
    preferences.end();
    Serial.print("set current brightness: ");
    Serial.println(settings.current_brightness);
  }
}

int getBrightnessFromSensor() {

  // BH1750 have higher priority. BH1750 measurmant range is 0..27306 lx. 500 lx - very bright indoor environment.
  if (bh1750Inited) return brightnessLevels[getCurrentBrightnessLevel(round(lightInLuxes), 500)];

  // reads the input on analog pin (value between 0 and 4095)
  int analogValue = analogRead(settings.lightpin) * settings.light_sensor_factor;
  // Serial.print("Analog light value: ");
  // Serial.println(analogValue);

  // 2600 - very bright indoor environment.
  return brightnessLevels[getCurrentBrightnessLevel(analogValue, 2600)];
}

// Determine the current brightness level
int getCurrentBrightnessLevel(int currentValue, int maxValue) {
  int level = map(min(currentValue, maxValue), 0, maxValue, 0, BR_LEVELS_COUNT - 1);
  // Serial.print("Brightness level: ");
  // Serial.println(level);
  return level;
}

int getCurrentBrightnes() {
  // highest priority for night mode, return night brightness
  if (nightMode) return settings.brightness_night;

  // if nightMode deactivated return previous brightness
  if (prevBrightness >= 0) {
    int tempBrightnes = prevBrightness;
    prevBrightness = -1;
    return tempBrightnes;
  }

  // if auto brightnes deactivated, return regular brightnes
  if (settings.brightness_mode == 0) return settings.brightness;

  // if auto brightnes set to light sensor, read sensor value end return appropriate brightness.
  if (settings.brightness_mode == 2) return getBrightnessFromSensor();

  // if day and night start time is equels it means it's always day, return day brightness
  if (settings.night_start == settings.day_start) return settings.brightness_day;

  int currentHour = timeClient.hour();

  // handle case, when night start hour is bigger than day start hour, ex. night start at 22 and day start at 9
  if (settings.night_start > settings.day_start)
    return currentHour >= settings.night_start || currentHour < settings.day_start ? settings.brightness_night : settings.brightness_day;

  // handle case, when day start hour is bigger than night start hour, ex. night start at 1 and day start at 8
  return currentHour < settings.day_start && currentHour >= settings.night_start ? settings.brightness_night : settings.brightness_day;
}
//--Service messages end

//--Websocket process start
void websocketProcess() {
  if (millis() - websocketLastPingTime > settings.ws_alert_time) {
    mapReconnect();
    websocketReconnect = true;
  }
  if (millis() - websocketLastPingTime > settings.ws_reboot_time) {
    rebootDevice(3000, true);
  }
  if (!client_websocket.available() or websocketReconnect) {
    Serial.println("Reconnecting...");
    socketConnect();
  }
}

void onMessageCallback(WebsocketsMessage message) {
  Serial.print("Got Message: ");
  Serial.println(message.data());
  JsonDocument data = parseJson(message.data());
  String payload = data["payload"];
  if (!payload.isEmpty()) {
    if (payload == "ping") {
      Serial.println("Heartbeat from server");
      websocketLastPingTime = millis();
    } else if (payload == "alerts") {
      Serial.println("Successfully parsed alerts data");
      for (int i = 0; i < 26; ++i) {
        alarm_leds[calculateOffset(i)] = data["alerts"][i];
      }
    } else if (payload == "weather") {
      Serial.println("Successfully parsed weather data");
      for (int i = 0; i < 26; ++i) {
        weather_leds[calculateOffset(i)] = data["weather"][i];
      }
    } else if (payload == "bins") {
      Serial.println("Successfully parsed bins list");
      std::vector<String> tempFilenames;
      JsonArray arr = data["bins"].as<JsonArray>();
      for (String filename : arr) {
        tempFilenames.push_back(filename);
      }
      bin_list = tempFilenames;
      saveLatestFirmware();
    } else if (payload == "test_bins") {
      Serial.println("Successfully parsed test_bins list");
      std::vector<String> tempFilenames;
      JsonArray arr = data["test_bins"].as<JsonArray>();
      for (String filename : arr) {
        tempFilenames.push_back(filename);
      }
      test_bin_list = tempFilenames;
      saveLatestFirmware();
    } else if (payload == "district") {
      Serial.println("Successfully parsed district data");
      bool alertNow = data["district"]["alertnow"];
      Serial.println(alertNow);
      if (alertNow) {
        homeAlertStart = data["district"]["changed"];
        Serial.println(homeAlertStart);
      } else {
        homeAlertStart = 0;
      }
    }
  }
}

void onEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    apiConnected = true;
    Serial.println("connnection opened");
    servicePin(settings.datapin, HIGH, false);
    websocketLastPingTime = millis();
    if (enableHA) {
      haMapApiConnect.setState(apiConnected, true);
    }
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    apiConnected = false;
    Serial.println("connnection closed");
    servicePin(settings.datapin, LOW, false);
    if (enableHA) {
      haMapApiConnect.setState(apiConnected, true);
    }
  } else if (event == WebsocketsEvent::GotPing) {
    Serial.println("websocket ping");
    client_websocket.pong();
    Serial.println("answered pong");
    websocketLastPingTime = millis();
  } else if (event == WebsocketsEvent::GotPong) {
    Serial.println("websocket pong");
  }
}

void socketConnect() {
  Serial.println("connection start...");
  showServiceMessage("підключення..", "Сервер даних");
  client_websocket.onMessage(onMessageCallback);
  client_websocket.onEvent(onEventsCallback);
  long startTime = millis();
  String webSocketUrl = "ws://" + String(settings.serverhost) + ":" + String(settings.websocket_port) + "/data_v1";
  Serial.println(webSocketUrl);
  client_websocket.connect(webSocketUrl.c_str());
  if (client_websocket.available()) {
    Serial.print("connection time - ");
    Serial.print(millis() - startTime);
    Serial.println("ms");
    String combinedString = "firmware:" + String(settings.softwareversion) + "_" + settings.identifier;
    Serial.println(combinedString.c_str());
    client_websocket.send(combinedString.c_str());
    String chipId = "chip_id:" + chipID;
    Serial.println(chipId.c_str());
    client_websocket.send(chipId.c_str());
    client_websocket.ping();
    websocketReconnect = false;
    showServiceMessage("підключено!", "Сервер даних", 3000);
  } else {
    showServiceMessage("недоступний", "Сервер даних", 3000);
  }
}
//--Websocket process end

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
  int position;
  if (initial_position == 25) {
    position = 25;
  } else {
    position = initial_position + offset;
    if (position >= 25) {
      position -= 25;
    }
  }
  if (settings.kyiv_district_mode == 2) {
    if (position == 25) {
      return 7 + offset;
    }
  }
  if (settings.kyiv_district_mode == 3) {

    if (position == 25) {
      return 8 + offset;
    }
    if (position > 7 + offset) {
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
  float local_brightness = settings.current_brightness / 200.0f;
  int local_color;
  if (blink and settings.alarms_notify_mode == 2) {
    local_brightness = settings.current_brightness / 600.0f;
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
      hue = HsbColor(color_switch / 360.0f, 1.0, settings.current_brightness * local_brightness_clear / 200.0f);
      break;
    case 1:
      if (position == local_district && homeAlertStart < 1) {
        parseHomeDistrictJson();
      }
      hue = HsbColor(settings.color_alert / 360.0f, 1.0, settings.current_brightness * local_brightness_alert / 200.0f);
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

void checkMinuteOfSilence() {
  bool localMinOfSilence = (settings.min_of_silence == 1 && timeClient.hour() == 9 && timeClient.minute() == 0);
  if (localMinOfSilence != minuteOfSilence) {
    minuteOfSilence = localMinOfSilence;
    if (enableHA) {
      haMapModeCurrent.setValue(mapModes[getCurrentMapMode()]);
    }
  }
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
  float local_brightness = settings.current_brightness / 200.0f;
  if (blink) {
    local_brightness = settings.current_brightness / 600.0f;
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
    case 5:
      mapLamp();
  }
  blink = !blink;
}

void mapOff() {
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, HslColor(0.0, 0.0, 0.0));
  }
  strip->Show();
}

void mapLamp() {
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, RgbColor(settings.ha_light_r, settings.ha_light_g, settings.ha_light_b).Dim(round(settings.ha_light_brightness * 255 / 200.0f)));
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
    strip->SetPixelColor(i, HslColor(processWeather(adapted_weather_leds[i]), 1.0, settings.current_brightness / 200.0f));
  }
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
    strip->SetPixelColor(i, HsbColor(adapted_flag_leds[i] / 360.0f, 1.0, settings.current_brightness / 200.0f));
  }
  strip->Show();
}

void mapRandom() {
  int randomLed = random(26);
  int randomColor = random(360);
  strip->SetPixelColor(randomLed, HsbColor(randomColor / 360.0f, 1.0, settings.current_brightness / 200.0f));
  strip->Show();
}

int getCurrentMapMode() {
  if (minuteOfSilence) return 3;

  int currentMapMode = isMapOff ? 0 : settings.map_mode;
  int position = settings.home_district;
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
  if (settings.enable_pin_on_alert) {
    int ledStatus = alarm_leds[calculateOffset(position)];
    alarmNow = (ledStatus == 1 || ledStatus == 3);
  } else {
    alarmNow = false;
  }
  if (enableHA) {
    haMapModeCurrent.setValue(mapModes[currentMapMode]);
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

void alertPinCycle() {
  if (alarmNow && settings.enable_pin_on_alert && digitalRead(settings.alertpin) == LOW) {
    Serial.println("alert pin enabled");
    digitalWrite(settings.alertpin, HIGH);
  }
  if (!alarmNow && settings.enable_pin_on_alert && digitalRead(settings.alertpin) == HIGH) {
    Serial.println("alert pin disabled");
    digitalWrite(settings.alertpin, LOW);
  }
}

void rebootCycle() {
  if (needRebootWithDelay != -1) {
    int localDelay = needRebootWithDelay;
    needRebootWithDelay = -1;
    rebootDevice(localDelay);
  }
}

void bh1750LightSensorCycle() {
  if (!bh1750Inited || !bh1750.measurementReady(true)) return;
  lightInLuxes = bh1750.readLightLevel() * settings.light_sensor_factor;
  // Serial.print("BH1750!\tLight: ");
  // Serial.print(lightInLuxes);
  // Serial.println(" lx");
}

void localTempHumSensorCycle() {

  if (bme280Inited || bmp280Inited) {
    localTemp = bme280.temp(BME280::TempUnit_Celsius) + settings.temp_correction;
    localPresure = bme280.pres(BME280::PresUnit_inHg) * 25.4 + settings.presure_correction;  //mmHg

    if (bme280Inited) {
      localHum = bme280.hum() + settings.hum_correction;
    }

    // Serial.print("BME280! Temp: ");
    // Serial.print(localTemp);
    // Serial.print("°C");
    // Serial.print("\tHumidity: ");
    // Serial.print(localHum);
    // Serial.print("%");
    // Serial.print("\tPressure: ");
    // Serial.print(localPresure);
    // Serial.println("mmHg");
    return;
  }

  if (sht3xInited && sht3x.read()) {
    localTemp = sht3x.getTemperature() + settings.temp_correction;
    localHum = sht3x.getHumidity() + settings.hum_correction;

    // Serial.print("SHT3X! Temp: ");
    // Serial.print(localTemp);
    // Serial.print("°C");
    // Serial.print("\tHumidity: ");
    // Serial.print(localHum);
    // Serial.println("%");
    return;
  }

  if (htu2xInited && htu2x.read()) {
    localTemp = htu2x.getTemperature() + settings.temp_correction;
    localHum = htu2x.getHumidity() + settings.hum_correction;

    // Serial.print("HTU2X! Temp: ");
    // Serial.print(localTemp);
    // Serial.print("°C");
    // Serial.print("\tHumidity: ");
    // Serial.print(localHum);
    // Serial.println("%");
    return;
  }
}

void setup() {
  Serial.begin(115200);

  initSettings();
  initLegacy();
  InitAlertPin();
  initStrip();
  initDisplay();
  initI2cTempSensors();
  initWifi();
  initTime();

  asyncEngine.setInterval(uptime, 5000);
  asyncEngine.setInterval(connectStatuses, 60000);
  asyncEngine.setInterval(mapCycle, 1000);
  asyncEngine.setInterval(displayCycle, 100);
  asyncEngine.setInterval(WifiReconnect, 1000);
  asyncEngine.setInterval(autoBrightnessUpdate, 1000);
  asyncEngine.setInterval(doUpdate, 1000);
  asyncEngine.setInterval(websocketProcess, 3000);
  asyncEngine.setInterval(alertPinCycle, 1000);
  asyncEngine.setInterval(rebootCycle, 500);
  asyncEngine.setInterval(bh1750LightSensorCycle, 2000);
  asyncEngine.setInterval(localTempHumSensorCycle, 5000);
}

void loop() {
  wm.process();
  asyncEngine.run();
  ArduinoOTA.handle();
  buttonUpdate();
  if (enableHA) {
    mqtt.loop();
  }
  client_websocket.poll();
  syncTime(2);
}
