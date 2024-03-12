#define LITE 0

#if LITE
#define ARDUINO_OTA_ENABLED 0
#define FW_UPDATE_ENABLED 0
#define HA_ENABLED 0
#define DISPLAY_ENABLED 0
#define BME280_ENABLED 0
#define SHT2X_ENABLED 0
#define SHT3X_ENABLED 0
#define BH1750_ENABLED 0
#define BUZZER_ENABLED 0
#else
#define ARDUINO_OTA_ENABLED 0
#define FW_UPDATE_ENABLED 1
#define HA_ENABLED 1
#define DISPLAY_ENABLED 1
#define BME280_ENABLED 1
#define SHT2X_ENABLED 1
#define SHT3X_ENABLED 1
#define BH1750_ENABLED 1
#define BUZZER_ENABLED 1
#endif

#include <Preferences.h>
#include <WiFiManager.h>
#include <ESPAsyncWebServer.h>
#include <ESPmDNS.h>
#include <async.h>
#if ARDUINO_OTA_ENABLED
#include <ArduinoOTA.h>
#endif
#if HA_ENABLED
#include <ArduinoHA.h>
#endif
#include <NeoPixelBus.h>
#if DISPLAY_ENABLED
#include <Adafruit_SSD1306.h>
#endif
#if FW_UPDATE_ENABLED
#include <HTTPUpdate.h>
#endif
#include <vector>
#include <ArduinoJson.h>
#include <ArduinoWebsockets.h>
#if BH1750_ENABLED
#include <BH1750_WE.h>
#endif
#if BME280_ENABLED
#include <forcedBMX280.h>
#endif
#if SHT2X_ENABLED || SHT3X_ENABLED
#include <SHTSensor.h>
#endif
#include <NTPtime.h>
#if BUZZER_ENABLED
#include <melody_player.h>
#include <melody_factory.h>
#endif

const PROGMEM char* VERSION = "3.7";

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
  char    devicename[31]         = "Alarm Map";
  char    devicedescription[51]  = "Alarm Map Informer";
  char    broadcastname[31]      = "alarmmap";
  char    serverhost[31]         = "alerts.net.ua";
  int     websocket_port         = 38440;
  int     updateport             = 8090;
  char    bin_name[51]           = "";
  char    identifier[51]         = "github";
  int     legacy                 = 1;
  int     pixelpin               = 13;
  int     buttonpin              = 15;
  int     alertpin               = 34;
  int     buzzerpin              = 33;
  int     lightpin               = 32;
  int     ha_mqttport            = 1883;
  char    ha_mqttuser[31]        = "";
  char    ha_mqttpassword[51]    = "";
  char    ha_brokeraddress[31]   = "";
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
  int     sound_on_startup       = 0;
  int     melody_on_startup      = 0;
  int     sound_on_min_of_sl     = 0;
  int     sound_on_alert         = 0;
  int     melody_on_alert        = 1;
  int     sound_on_alert_end     = 0;
  int     melody_on_alert_end    = 2;
  int     sound_on_every_hour    = 0;
  int     mute_sound_on_night    = 0;
  int     invert_display         = 0;
  int     disp_brightness        = 100;
  int     disp_brightness_night  = 50;


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
  // -------  4 - Climate (if sensor installed)
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
  float   pressure_correction    = 0;
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
#if FW_UPDATE_ENABLED
Firmware latestFirmware;
#endif

using namespace websockets;

Preferences       preferences;
WiFiManager       wm;
WiFiClient        client;
WebsocketsClient  client_websocket;
AsyncWebServer    webserver(80);
NTPtime           timeClient(2);
DSTime            dst(3, 0, 7, 3, 10, 0, 7, 4); //https://en.wikipedia.org/wiki/Eastern_European_Summer_Time
Async             asyncEngine = Async(20);
#if DISPLAY_ENABLED
Adafruit_SSD1306  display(settings.display_width, settings.display_height, &Wire, -1);
#define MAX_DISPLAY_BRIGHTNESS 0xCF
#endif
#if BH1750_ENABLED
BH1750_WE         bh1750;
#endif
#if BME280_ENABLED
ForcedBME280Float bme280;
#endif
#if SHT2X_ENABLED
SHTSensor         htu2x(SHTSensor::SHT2X);
#endif
#if SHT3X_ENABLED
SHTSensor         sht3x(SHTSensor::SHT3X);
#endif
#if BUZZER_ENABLED
MelodyPlayer* player;
const char uaAnthem[]       PROGMEM = "UkraineAnthem:d=4,o=5,b=200:2d5,4d5,32p,4d5,32p,4d5,32p,4c5,4d5,4d#5,2f5,4f5,4d#5,2d5,2c5,2a#4,2d5,2a4,2d5,1g4,32p,1g4";
const char imperialMarch[]  PROGMEM = "ImperialMarch:d=4,o=5,b=112:8d.,16p,8d.,16p,8d.,16p,8a#4,16p,16f,8d.,16p,8a#4,16p,16f,d.,8p,8a.,16p,8a.,16p,8a.,16p,8a#,16p,16f,8c#.,16p,8a#4,16p,16f,d.";
const char nokiaTun[]       PROGMEM = "NokiaTun:d=4,o=5,b=225:8e6,8d6,f#,g#,8c#6,8b,d,e,8b,8a,c#,e,2a";
const char clockBeep[]      PROGMEM = "Clock:d=4,o=4,b=250:g";

#define MELODIES_COUNT 3
const char* melodies[MELODIES_COUNT] PROGMEM = {
  uaAnthem,
  imperialMarch,
  nokiaTun
};

char* melodyNames[MELODIES_COUNT] PROGMEM = {
  "Гімн України",
  "Імперський марш",
  "Nokia tune"
};
#endif

enum SoundType {
  START_UP,
  MIN_OF_SILINCE,
  REGULAR,
  ALERT_ON,
  ALERT_OFF
};

struct ServiceMessage {
  const char* title;
  const char* message;
  int textSize;
  long endTime;
  int expired;
};

struct RGBColor {
  uint8_t r;
  uint8_t g;
  uint8_t b;
};

ServiceMessage serviceMessage;

NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod>* strip;

uint8_t   alarm_leds[26];
float     weather_leds[26];
uint8_t   flag_leds[26];
// int     flag_leds[26] = {
//   60,60,60,180,180,60,60,60,60,60,60,
//   60,180,180,180,180,180,180,
//   180,180,180,60,60,60,60,180
// };
const uint8_t legacy_flag_leds[26] PROGMEM = {
  60, 60, 60, 180, 180, 180, 180, 180, 180,
  180, 180, 180, 60, 60, 60, 60, 60, 60, 60,
  180, 180, 60, 60, 60, 60, 180
};

const uint8_t d0[] PROGMEM = { 0, 1, 3 };
const uint8_t d1[] PROGMEM = { 1, 0, 2, 3, 24 };
const uint8_t d2[] PROGMEM = { 2, 1, 3, 4, 5, 23, 24 };
const uint8_t d3[] PROGMEM = { 3, 0, 1, 2, 4 };
const uint8_t d4[] PROGMEM = { 4, 2, 3, 5 };
const uint8_t d5[] PROGMEM = { 5, 2, 3, 4, 6, 23 };
const uint8_t d6[] PROGMEM = { 6, 5, 7, 22, 23, 25 };
const uint8_t d7[] PROGMEM = { 7, 6, 8, 19, 20, 22, 25 };
const uint8_t d8[] PROGMEM = { 8, 7, 9, 19, 20 };
const uint8_t d9[] PROGMEM = { 9, 8, 10, 19 };
const uint8_t d10[] PROGMEM = { 10, 9, 12, 18, 19 };
const uint8_t d11[] PROGMEM = { 11, 10, 12 };
const uint8_t d12[] PROGMEM = { 12, 10, 13, 18 };
const uint8_t d13[] PROGMEM = { 13, 12, 14, 18 };
const uint8_t d14[] PROGMEM = { 14, 13, 17, 18 };
const uint8_t d15[] PROGMEM = { 15, 14 };
const uint8_t d16[] PROGMEM = { 16, 17, 20, 21, 22 };
const uint8_t d17[] PROGMEM = { 17, 14, 16, 18, 21 };
const uint8_t d18[] PROGMEM = { 18, 10, 12, 13, 14, 17, 19, 21 };
const uint8_t d19[] PROGMEM = { 19, 7, 8, 9, 10, 18, 20, 21, 25 };
const uint8_t d20[] PROGMEM = { 20, 7, 8, 19, 21, 22, 25 };
const uint8_t d21[] PROGMEM = { 21, 16, 17, 18, 19, 20, 22 };
const uint8_t d22[] PROGMEM = { 22, 6, 7, 16, 20, 21, 23, 24, 25 };
const uint8_t d23[] PROGMEM = { 23, 2, 5, 6, 22, 24 };
const uint8_t d24[] PROGMEM = { 24, 1, 2, 22, 23 };
const uint8_t d25[] PROGMEM = { 25, 7 };


const uint8_t counters[] PROGMEM = { 3, 5, 7, 5, 4, 6, 6, 6, 5, 4, 5, 3, 4, 4, 4, 2, 5, 5, 8, 8, 7, 7, 9, 6, 5, 2 };

#define DISTRICTS_COUNT 26

char* districts[DISTRICTS_COUNT] = {
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

char* districtsAlphabetical[DISTRICTS_COUNT] = {
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

const uint8_t* neighboring_districts[DISTRICTS_COUNT] PROGMEM = {
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

#if HA_ENABLED
bool    enableHA;
#endif
bool    wifiReconnect = false;
bool    websocketReconnect = false;
bool    blink = false;
bool    isDaylightSaving = false;
time_t  websocketLastPingTime = 0;
int     offset = 9;
bool    initUpdate = false;
long    homeAlertStart = 0;
time_t  lastHomeDistrictSync = 0;
#if FW_UPDATE_ENABLED
bool    fwUpdateAvailable = false;
char    newFwVersion[25];
#endif
char    currentVersion[25];
int     rssi;
bool    apiConnected;
bool    haConnected;
int     prevMapMode = 1;
bool    alarmNow = false;
bool    minuteOfSilence = false;
bool    uaAnthemPlaying = false;
short   clockBeepInterval = -1;
bool    isMapOff = false;
bool    isDisplayOff = false;
bool    nightMode = false;
int     prevBrightness = -1;
int     needRebootWithDelay = -1;
bool    bh1750Inited = false;
float   lightInLuxes = -1;
bool    bme280Inited = false;
bool    bmp280Inited = false;
bool    sht3xInited = false;
bool    htu2xInited = false;
float   localTemp = -273;
float   localHum = -1;
float   localPresure = -1;
int     beepHour = -1;

#define BR_LEVELS_COUNT 20
int     ledsBrightnessLevels[BR_LEVELS_COUNT]; // Array containing LEDs brightness values
#if DISPLAY_ENABLED
int     dispBrightnessLevels[BR_LEVELS_COUNT]; // Array containing display brightness values
int     currentDisplayBrightness = 100;
#endif

// Button variables
#define SHORT_PRESS_TIME 500 // 500 milliseconds
#define LONG_PRESS_TIME  500 // 500 milliseconds
int lastState = LOW;  // the previous state from the input pin
int currentState;     // the current reading from the input pin
unsigned long pressedTime  = 0;
unsigned long releasedTime = 0;
bool isPressing = false;
bool isLongDetected = false;
#define NIGHT_BRIGHTNESS_LEVEL 2

#define MAX_BINS_LIST_SIZE 10
int binsCount = 0;
char* bin_list[MAX_BINS_LIST_SIZE];

int testBinsCount = 0;
char*  test_bin_list[MAX_BINS_LIST_SIZE];

char chipID[13];
#if HA_ENABLED
HADevice        device;
HAMqtt          mqtt(client, device, 19);
char haConfigUrl[30];

char haUptimeID[20];
char haWifiSignalID[25];
char haFreeMemoryID[25];
char haUsedMemoryID[25];
char haCpuTempID[22];
char haBrightnessID[24];
char haMapModeID[22];
char haDisplayModeID[26];
char haAlarmsAutoID[25];
char haBrightnessAutoID[29];
char haMapModeCurrentID[30];
char haHomeDistrictID[27];
char haMapApiConnectID[29];
char haShowHomeAlarmTimeID[34];
char haRebootID[20];
char haToggleMapModeID[29];
char haToggleDisplayModeID[33];
char haLightID[19];

HASensorNumber*  haUptime;
HASensorNumber*  haWifiSignal;
HASensorNumber*  haFreeMemory;
HASensorNumber*  haUsedMemory;
HASensorNumber*  haCpuTemp;
HANumber*        haBrightness;
HASelect*        haMapMode;
HASelect*        haDisplayMode;
HASelect*        haAlarmsAuto;
HASelect*        haBrightnessAuto;
HASensor*        haMapModeCurrent;
HASensor*        haHomeDistrict;
HABinarySensor*  haMapApiConnect;
HASwitch*        haShowHomeAlarmTime;
HAButton*        haReboot;
HAButton*        haToggleMapMode;
HAButton*        haToggleDisplayMode;
HALight*         haLight;
#endif

void initHaVars() {
  uint64_t chipid = ESP.getEfuseMac();
  sprintf(chipID, "%04x%04x", (uint32_t)(chipid >> 32), (uint32_t)chipid);
  Serial.printf("ChipID Inited: '%s'\n", chipID);
#if HA_ENABLED
  sprintf(haUptimeID, "%s_uptime", chipID);
  haUptime = new HASensorNumber(haUptimeID);

  sprintf(haWifiSignalID, "%s_wifi_signal", chipID);
  haWifiSignal = new HASensorNumber(haWifiSignalID);

  sprintf(haFreeMemoryID, "%s_free_memory", chipID);
  haFreeMemory = new HASensorNumber(haFreeMemoryID);

  sprintf(haUsedMemoryID, "%s_used_memory", chipID);
  haUsedMemory = new HASensorNumber(haUsedMemoryID);

  sprintf(haCpuTempID, "%s_cpu_temp", chipID);
  haCpuTemp = new HASensorNumber(haCpuTempID, HASensorNumber::PrecisionP1);

  sprintf(haBrightnessID, "%s_brightness", chipID);
  haBrightness = new HANumber(haBrightnessID);

  sprintf(haMapModeID, "%s_map_mode", chipID);
  haMapMode = new HASelect(haMapModeID);

  sprintf(haDisplayModeID, "%s_display_mode", chipID);
  haDisplayMode = new HASelect(haDisplayModeID);

  sprintf(haBrightnessAutoID, "%s_brightness_auto", chipID);
  haAlarmsAuto = new HASelect(haBrightnessAutoID);

  sprintf(haAlarmsAutoID, "%s_alarms_auto", chipID);
  haBrightnessAuto = new HASelect(haAlarmsAutoID);

  sprintf(haMapModeCurrentID, "%s_map_mode_current", chipID);
  haMapModeCurrent = new HASensor(haMapModeCurrentID);

  sprintf(haHomeDistrictID, "%s_home_district", chipID);
  haHomeDistrict = new HASensor(haHomeDistrictID);

  sprintf(haMapApiConnectID, "%s_map_api_connect", chipID);
  haMapApiConnect = new HABinarySensor(haMapApiConnectID);

  sprintf(haShowHomeAlarmTimeID, "%s_show_home_alarm_time", chipID);
  haShowHomeAlarmTime = new HASwitch(haShowHomeAlarmTimeID);

  sprintf(haRebootID, "%s_reboot", chipID);
  haReboot = new HAButton(haRebootID);

  sprintf(haToggleMapModeID, "%s_toggle_map_mode", chipID);
  haToggleMapMode = new HAButton(haToggleMapModeID);

  sprintf(haToggleDisplayModeID, "%s_toggle_display_mode", chipID);
  haToggleDisplayMode = new HAButton(haToggleDisplayModeID);

  sprintf(haLightID, "%s_light", chipID);
  haLight = new HALight(haLightID, HALight::BrightnessFeature | HALight::RGBFeature);
#endif
}

#define MAP_MODES_COUNT 6
char* mapModes[MAP_MODES_COUNT] = {
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

#define AUTO_ALARM_MODES_COUNT 3
char* autoAlarms[AUTO_ALARM_MODES_COUNT] = {
  "Вимкнено",
  "Домашній та суміжні",
  "Лише домашній"
};

#define SINGLE_CLICK_OPTIONS_COUNT 7
char* singleClickOptions[SINGLE_CLICK_OPTIONS_COUNT] = {
  "Вимкнено",
  "Перемикання режимів мапи",
  "Перемикання режимів дисплея",
  "Увімк./Вимк. мапу",
  "Увімк./Вимк. дисплей",
  "Увімк./Вимк. мапу та дисплей",
  "Увімк./Вимк. нічний режим"
};

#define LONG_CLICK_OPTIONS_COUNT 8
char* longClickOptions[LONG_CLICK_OPTIONS_COUNT] = {
  "Вимкнено",
  "Перемикання режимів мапи",
  "Перемикання режимів дисплея",
  "Увімк./Вимк. мапу",
  "Увімк./Вимк. дисплей",
  "Увімк./Вимк. мапу та дисплей",
  "Увімк./Вимк. нічний режим",
  "Перезавантаження пристрою"
};

#if FW_UPDATE_ENABLED
#define FW_UPDATE_CHANNELS_COUNT 2
char* fwUpdateChannels[FW_UPDATE_CHANNELS_COUNT] = {
  "Production",
  "Beta"
};
#endif

#define AUTO_BRIGHTNESS_OPTIONS_COUNT 3
char* autoBrightnessOptions[AUTO_BRIGHTNESS_OPTIONS_COUNT] = {
  "Вимкнено",
  "День/Ніч",
  "Сенсор освітлення"
};

#define KYIV_LED_MODE_COUNT 4
char* kyivLedModeOptions[KYIV_LED_MODE_COUNT] = {
  "Київська область",
  "Київ",
  "Київська область + Київ (2 діода)",
  "Київська область + Київ (1 діод)"
};

#define ALERT_NOTIFY_OPTIONS_COUNT 3
char* alertNotifyOptions[ALERT_NOTIFY_OPTIONS_COUNT] = {
  "Вимкнено",
  "Колір",
  "Колір + зміна яскравості"
};

#define DISPLAY_HEIGHT_OPTIONS_COUNT 2
char* displayHeightOptions[DISPLAY_HEIGHT_OPTIONS_COUNT] = {
  "128x32",
  "128x64"
};

#define LEGACY_OPTIONS_COUNT 2
char* legacyOptions[LEGACY_OPTIONS_COUNT] = {
  "Плата JAAM",
  "Класична (початок на Закарпатті)"
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


void initBuzzer() {
#if BUZZER_ENABLED
  player = new MelodyPlayer(settings.buzzerpin, 0, HIGH);
  if (needToPlaySound(START_UP)) {
    playMelody(START_UP);
  }
#endif
}

void playMelody(const char* melodyRtttl) {
#if BUZZER_ENABLED
  Melody melody = MelodyFactory.loadRtttlString(melodyRtttl);
  player->playAsync(melody);
#endif
}

void playMelody(SoundType type) {
#if BUZZER_ENABLED
  switch (type) {
  case START_UP:
    playMelody(melodies[settings.melody_on_startup]);
    break;
  case MIN_OF_SILINCE:
    playMelody(clockBeep);
    break;
  case ALERT_ON:
    playMelody(melodies[settings.melody_on_alert]);
    break;
  case ALERT_OFF:
    playMelody(melodies[settings.melody_on_alert_end]);
    break;
  case REGULAR:
    playMelody(clockBeep);
    break;
  }
#endif
}

bool needToPlaySound(SoundType type) {
#if BUZZER_ENABLED
  if (settings.mute_sound_on_night) {
    // Night Mode activated by button
    if (nightMode) return false;
    // Night mode activated by time
    if (settings.brightness_mode == 1 && isItNightNow()) return false;
    // Night mode activated by sensor
    if (settings.brightness_mode == 2 && getCurrentBrightnessLevel() <= NIGHT_BRIGHTNESS_LEVEL) return false;
  }

  switch (type) {
  case START_UP:
    return settings.sound_on_startup;
  case MIN_OF_SILINCE:
    return settings.sound_on_min_of_sl;
  case ALERT_ON:
    return settings.sound_on_alert;
  case ALERT_OFF:
    return settings.sound_on_alert_end;
  case REGULAR:
    return settings.sound_on_every_hour;
  }
#endif
  return false;
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
  preferences.begin("storage", true);

  preferences.getString("dn", settings.devicename, sizeof(settings.devicename));
  preferences.getString("dd", settings.devicedescription, sizeof(settings.devicedescription));
  preferences.getString("bn", settings.broadcastname, sizeof(settings.broadcastname));
  preferences.getString("host", settings.serverhost, sizeof(settings.serverhost));
  preferences.getString("id", settings.identifier, sizeof(settings.identifier));
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
  preferences.getString("ha_brokeraddr", settings.ha_brokeraddress, sizeof(settings.ha_brokeraddress));
  settings.ha_mqttport            = preferences.getInt("ha_mqttport", settings.ha_mqttport);
  preferences.getString("ha_mqttuser", settings.ha_mqttuser, sizeof(settings.ha_mqttuser));
  preferences.getString("ha_mqttpass", settings.ha_mqttpassword, sizeof(settings.ha_mqttpassword));
  settings.display_width          = preferences.getInt("dw", settings.display_width);
  settings.display_height         = preferences.getInt("dh", settings.display_height);
  settings.day_start              = preferences.getInt("ds", settings.day_start);
  settings.night_start            = preferences.getInt("ns", settings.night_start);
  settings.pixelpin               = preferences.getInt("pp", settings.pixelpin);
  settings.buttonpin              = preferences.getInt("bp", settings.buttonpin);
  settings.alertpin               = preferences.getInt("ap", settings.alertpin);
  settings.buzzerpin              = preferences.getInt("bzp", settings.buzzerpin);
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
  settings.pressure_correction    = preferences.getFloat("lpc", settings.pressure_correction);
  settings.light_sensor_factor    = preferences.getFloat("lsf", settings.light_sensor_factor);
  settings.sound_on_startup       = preferences.getInt("sos", settings.sound_on_startup);
  settings.sound_on_min_of_sl     = preferences.getInt("somos", settings.sound_on_min_of_sl);
  settings.sound_on_alert         = preferences.getInt("soa", settings.sound_on_alert);
  settings.sound_on_alert_end     = preferences.getInt("soae", settings.sound_on_alert_end);
  settings.sound_on_every_hour    = preferences.getInt("soeh", settings.sound_on_every_hour);
  settings.melody_on_startup      = preferences.getInt("most", settings.melody_on_startup);
  settings.melody_on_alert        = preferences.getInt("moa", settings.melody_on_alert);
  settings.melody_on_alert_end    = preferences.getInt("moae", settings.melody_on_alert_end);
  settings.mute_sound_on_night    = preferences.getInt("mson", settings.mute_sound_on_night);
  settings.invert_display         = preferences.getInt("invd", settings.invert_display);
  settings.disp_brightness        = preferences.getInt("dbr", settings.disp_brightness);
  settings.disp_brightness_night  = preferences.getInt("dbrn", settings.disp_brightness_night);


  preferences.end();

  currentFirmware = parseFirmwareVersion(VERSION);
  fillFwVersion(currentVersion, currentFirmware);
  Serial.printf("Current firmware version: %s\n", currentVersion);
  distributeBrightnessLevels();
}

void InitAlertPin() {
  if (settings.enable_pin_on_alert) {
    Serial.printf("alertpin: %d\n");
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
    Serial.printf("Attempt #%d of %d\n", count, attempts);
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


void displayMessage(const char* message, const char* title = "", int messageTextSize = -1) {
#if DISPLAY_ENABLED
  if (messageTextSize == -1) {
    messageTextSize = getTextSizeToFitDisplay(message);
  }
  display.clearDisplay();
  bool withTitle = strlen(title) > 0;
  if (withTitle) {
    char cyrTitle[strlen(title)];
    display.setCursor(1, 1);
    display.setTextSize(1);
    utf8cyr(cyrTitle, title);
    display.println(cyrTitle);
  }
  displayCenter(message, withTitle, messageTextSize);
#endif
}

void showServiceMessage(const char* message, const char* title = "", int duration = 2000) {
#if DISPLAY_ENABLED
  serviceMessage.title = title;
  serviceMessage.message = message;
  serviceMessage.textSize = getTextSizeToFitDisplay(message);
  serviceMessage.endTime = millis() + duration;
  serviceMessage.expired = false;
  displayCycle();
#endif
}

void rebootDevice(int time = 2000, bool async = false) {
  if (async) {
    needRebootWithDelay = time;
    return;
  }
  showServiceMessage("Перезавантаження..", "", time);
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
  showServiceMessage(wm.getWiFiSSID(true).c_str(), "Підключення до:", 5000);
  char apssid[20];
  sprintf(apssid, "%s_%s", settings.apssid, chipID);
  if (!wm.autoConnect(apssid)) {
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
  showServiceMessage(WiFi.localIP().toString().c_str(), "IP-адреса мапи:", 3000);
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

static void wifiEvents(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
    {
      const char* ipAddress = WiFi.softAPIP().toString().c_str();
      displayMessage(ipAddress, "Введіть у браузері:");
      WiFi.removeEvent(wifiEvents);
      break;
    }
    default:
      break;
  }
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

#if FW_UPDATE_ENABLED || ARDUINO_OTA_ENABLED
void showUpdateProgress(size_t progress, size_t total) {
  if (total == 0) return;
  char progressText[5];
  sprintf(progressText, "%d%%", progress / (total / 100));
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
#if HA_ENABLED
  if (!wifiReconnect) {
    Serial.println("Init Home assistant API");

    IPAddress brokerAddr;

    if (!brokerAddr.fromString(settings.ha_brokeraddress)) {
      Serial.println("Invalid IP-address format!");
      enableHA = false;
    } else {
      enableHA = true;
    }

    if (enableHA) {
      byte mac[6];
      WiFi.macAddress(mac);
      device.setUniqueId(mac, sizeof(mac));
      device.setName(settings.devicename);
      device.setSoftwareVersion(currentVersion);
      device.setManufacturer("v00g100skr");
      device.setModel(settings.devicedescription);
      sprintf(haConfigUrl, "http://%s:80", WiFi.localIP().toString());
      Serial.printf("HA Device configurationUrl: '%s'\n", haConfigUrl);
      device.setConfigurationUrl(haConfigUrl);
      device.enableExtendedUniqueIds();
      device.enableSharedAvailability();
      device.enableLastWill();

      haUptime->setIcon("mdi:timer-outline");
      haUptime->setName("Uptime");
      haUptime->setUnitOfMeasurement("s");
      haUptime->setDeviceClass("duration");

      haWifiSignal->setIcon("mdi:wifi");
      haWifiSignal->setName("WIFI Signal");
      haWifiSignal->setUnitOfMeasurement("dBm");
      haWifiSignal->setDeviceClass("signal_strength");
      haWifiSignal->setStateClass("measurement");

      haFreeMemory->setIcon("mdi:memory");
      haFreeMemory->setName("Free Memory");
      haFreeMemory->setUnitOfMeasurement("kB");
      haFreeMemory->setDeviceClass("data_size");
      haFreeMemory->setStateClass("measurement");

      haUsedMemory->setIcon("mdi:memory");
      haUsedMemory->setName("Used Memory");
      haUsedMemory->setUnitOfMeasurement("kB");
      haUsedMemory->setDeviceClass("data_size");
      haUsedMemory->setStateClass("measurement");

      haBrightness->onCommand(onHaBrightnessCommand);
      haBrightness->setIcon("mdi:brightness-percent");
      haBrightness->setName("Brightness");
      haBrightness->setCurrentState(settings.brightness);

      char mapModeOptions[sizeOfCharsArray(mapModes, MAP_MODES_COUNT) + MAP_MODES_COUNT];
      getHaOptions(mapModeOptions, mapModes, MAP_MODES_COUNT);
      haMapMode->setOptions(mapModeOptions);
      haMapMode->onCommand(onHaMapModeCommand);
      haMapMode->setIcon("mdi:map");
      haMapMode->setName("Map Mode");
      haMapMode->setCurrentState(settings.map_mode);

      haDisplayMode->setOptions(getHaOptions(displayModes).c_str());
      haDisplayMode->onCommand(onHaDisplayModeCommand);
      haDisplayMode->setIcon("mdi:clock-digital");
      haDisplayMode->setName("Display Mode");
      haDisplayMode->setCurrentState(getHaDisplayMode(settings.display_mode));

      char autoAlarmsModeOptions[sizeOfCharsArray(autoAlarms, AUTO_ALARM_MODES_COUNT) + AUTO_ALARM_MODES_COUNT];
      getHaOptions(autoAlarmsModeOptions, autoAlarms, AUTO_ALARM_MODES_COUNT);
      haAlarmsAuto->setOptions(autoAlarmsModeOptions);
      haAlarmsAuto->onCommand(onhaAlarmsAutoCommand);
      haAlarmsAuto->setIcon("mdi:alert-outline");
      haAlarmsAuto->setName("Auto Alarm");
      haAlarmsAuto->setCurrentState(settings.alarms_auto_switch);

      haMapModeCurrent->setIcon("mdi:map");
      haMapModeCurrent->setName("Current Map Mode");

      haMapApiConnect->setName("Connectivity");
      haMapApiConnect->setDeviceClass("connectivity");
      haMapApiConnect->setCurrentState(client_websocket.available());

      char autoBrightnessOptionsString[sizeOfCharsArray(autoBrightnessOptions, AUTO_BRIGHTNESS_OPTIONS_COUNT) + AUTO_BRIGHTNESS_OPTIONS_COUNT];
      getHaOptions(autoBrightnessOptionsString, autoBrightnessOptions, AUTO_BRIGHTNESS_OPTIONS_COUNT);
      haBrightnessAuto->setOptions(autoBrightnessOptionsString);
      haBrightnessAuto->onCommand(onHaBrightnessAutoCommand);
      haBrightnessAuto->setIcon("mdi:brightness-auto");
      haBrightnessAuto->setName("Auto Brightness");
      haBrightnessAuto->setCurrentState(settings.brightness_mode);

      haShowHomeAlarmTime->onCommand(onHaShowHomeAlarmTimeCommand);
      haShowHomeAlarmTime->setIcon("mdi:timer-alert");
      haShowHomeAlarmTime->setName("Show Home Alert Time");
      haShowHomeAlarmTime->setCurrentState(settings.home_alert_time);

      haReboot->onCommand(onHaButtonClicked);
      haReboot->setName("Reboot");
      haReboot->setDeviceClass("restart");

      haToggleMapMode->onCommand(onHaButtonClicked);
      haToggleMapMode->setName("Toggle Map Mode");
      haToggleMapMode->setIcon("mdi:map-plus");

      haToggleDisplayMode->onCommand(onHaButtonClicked);
      haToggleDisplayMode->setName("Toggle Display Mode");
      haToggleDisplayMode->setIcon("mdi:card-plus");

      haCpuTemp->setIcon("mdi:chip");
      haCpuTemp->setName("CPU Temperature");
      haCpuTemp->setDeviceClass("temperature");
      haCpuTemp->setUnitOfMeasurement("°C");
      haCpuTemp->setCurrentValue(temperatureRead());
      haCpuTemp->setStateClass("measurement");

      haHomeDistrict->setIcon("mdi:home-map-marker");
      haHomeDistrict->setName("Home District");

      haLight->setIcon("mdi:led-strip-variant");
      haLight->setName("Lamp");
      haLight->setBrightnessScale(100);
      haLight->setCurrentState(settings.map_mode == 5);
      haLight->setCurrentBrightness(settings.ha_light_brightness);
      haLight->setCurrentRGBColor(HALight::RGBColor(settings.ha_light_r, settings.ha_light_g, settings.ha_light_b));
      haLight->onStateCommand(onHaLightState);
      haLight->onBrightnessCommand(onHaLightBrightness);
      haLight->onRGBColorCommand(onHaLightRGBColor);

      device.enableLastWill();
      mqtt.onStateChanged(onMqttStateChanged);
      mqtt.begin(brokerAddr, settings.ha_mqttport, settings.ha_mqttuser, settings.ha_mqttpassword);
    }
  }
#endif
}

#if HA_ENABLED
void onMqttStateChanged(HAMqtt::ConnectionState state) {
  Serial.print("Home Assistant MQTT state changed! State: ");
  Serial.println(state);
  haConnected = state == HAMqtt::StateConnected;
  servicePin(settings.hapin, haConnected ? HIGH : LOW, false);
  if (enableHA && haConnected) {
    // Update HASensors values (Unlike the other device types, the HASensor doesn't store the previous value that was set. It means that the MQTT message is produced each time the setValue method is called.)
    haMapModeCurrent->setValue(mapModes[getCurrentMapMode()]);
    haHomeDistrict->setValue(districtsAlphabetical[numDistrictToAlphabet(settings.home_district)]);
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

void getHaOptions(char* result, char* options[], int optionsSize) {
  strcpy(result, "");
  for (int i = 0; i < optionsSize; i++) {
    char* option = options[i];
    if (i > 0) {
      strcat(result, ";");
    }
    strcat(result, option);
  }
}

int sizeOfCharsArray(char* array[], int arraySize) {
  int result = 0;
  for (int i = 0; i < arraySize; i++) {
    result += strlen(array[i]);
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
  RGBColor color;
  color.r = rgb.red;
  color.g = rgb.green;
  color.b = rgb.blue;
  saveHaLightRgb(color);
}

void onHaButtonClicked(HAButton* sender) {
  if (sender == haReboot) {
    device.setAvailability(false);
    rebootDevice();
  } else if (sender == haToggleMapMode) {
    mapModeSwitch();
  } else if (sender == haToggleDisplayMode) {
    nextDisplayMode();
  }
}

void onHaShowHomeAlarmTimeCommand(bool state, HASwitch* sender) {
  saveHaShowHomeAlarmTime(state);
}

void onHaBrightnessAutoCommand(int8_t index, HASelect* sender) {
  saveHaBrightnessAuto(index);
}

void onHaBrightnessCommand(HANumeric haBrightness, HANumber* sender) {
  saveHaBrightness(haBrightness.toUInt8());
}

void onhaAlarmsAutoCommand(int8_t index, HASelect* sender) {
  saveHaAlarmAuto(index);
}

void onHaMapModeCommand(int8_t index, HASelect* sender) {
  saveMapMode(index);
}

void onHaDisplayModeCommand(int8_t index, HASelect* sender) {
  int newDisplayMode = getRealDisplayMode(index);
  saveDisplayMode(newDisplayMode);
}
#endif

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
#if DISPLAY_ENABLED
  display = Adafruit_SSD1306(settings.display_width, settings.display_height, &Wire, -1);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.display();
  display.clearDisplay();
  display.setTextColor(INVERSE);
  updateInvertDisplayMode();
  updateDisplayBrightness();
  int16_t centerY = (settings.display_height - 32) / 2;
  display.drawBitmap(0, centerY, trident_small, 32, 32, 1);
  display.setTextSize(1);
  char text1[15] = "";
  char text2[15] = "";
  utf8cyr(text1, "Just Another");
  utf8cyr(text2, "Alert Map");
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
  display.print(currentVersion);
  display.display();
  delay(3000);
#endif
}

void updateInvertDisplayMode() {
#if DISPLAY_ENABLED
  display.invertDisplay(settings.invert_display);
#endif
}

void updateDisplayBrightness() {
#if DISPLAY_ENABLED
  int localBrightness = shouldDisplayBeOff() ? 0 : getCurrentBrightnes(settings.disp_brightness, settings.disp_brightness, settings.disp_brightness_night, dispBrightnessLevels);
  if (localBrightness == currentDisplayBrightness) return;
  currentDisplayBrightness = localBrightness;
  Serial.printf("Set display brightness: %d\n", currentDisplayBrightness);
  uint8_t mappedBrightness = map(currentDisplayBrightness, 0, 100, 0, MAX_DISPLAY_BRIGHTNESS);
  display.ssd1306_command(SSD1306_SETCONTRAST);
  display.ssd1306_command(mappedBrightness);
#endif
}

void initI2cTempSensors() {
#if BH1750_ENABLED || BME280_ENABLED || SHT2X_ENABLED || SHT3X_ENABLED
  Wire.begin();
#endif
#if BH1750_ENABLED
  initBh1750LightSensor();
#endif
#if BME280_ENABLED
  initBme280TempSensor();
#endif
#if SHT3X_ENABLED
  initSht3xTempSensor();
#endif
#if SHT2X_ENABLED
  initHtu2xTempSensor();
#endif
#if BME280_ENABLED || SHT2X_ENABLED || SHT3X_ENABLED
  initDisplayModes();
#endif
}

#if BH1750_ENABLED
void initBh1750LightSensor() {
  bh1750Inited = bh1750.init();
  if (bh1750Inited) {
    bh1750.setMode(CHM_2);
    delay(500); //waiting to get first measurement
    bh1750LightSensorCycle();
    Serial.println("Found BH1750 light sensor! Success.");
  } else {
    Serial.println("Not found BH1750 light sensor!");
  }
}
#endif

#if SHT3X_ENABLED
void initSht3xTempSensor() {
  sht3xInited = sht3x.init();
  if (sht3xInited) {
    Serial.println("Found SHT3x temp/hum sensor! Success.");
  } else {
    Serial.println("Not found SHT3x temp/hum sensor!");
  }
}
#endif

#if SHT2X_ENABLED
void initHtu2xTempSensor() {
  htu2xInited = htu2x.init();
  if (sht3xInited) {
    Serial.println("Found HTU2x temp/hum sensor! Success.");
  } else {
    Serial.println("Not found HTU2x temp/hum sensor!");
  }
}
#endif

#if BME280_ENABLED
void initBme280TempSensor() {
  bme280.begin();
  switch (bme280.getChipID()) {
    case CHIP_ID_BME280:
      bme280Inited = true;
      Serial.println("Found BME280 temp/hum/presure sensor! Success.");
      break;
    case CHIP_ID_BMP280:
      bmp280Inited = true;
      Serial.println("Found BMP280 temp/presure sensor! No Humidity available.");
      break;
    default:
      bme280Inited = false;
      bmp280Inited = false;
      Serial.println("Not found BME280 or BMP280!");
  }
}
#endif
#if BME280_ENABLED || SHT2X_ENABLED || SHT3X_ENABLED
void initDisplayModes() {
  if (bme280Inited || bmp280Inited || sht3xInited || htu2xInited) {
    displayModes.insert(displayModes.end() - 1, "Мікроклімат");
    localTempHumSensorCycle();
  } else if (settings.display_mode == displayModes.size() - 1) {
    saveDisplayMode(9);
  }
}
#endif
//--Init end

void fillFwVersion(char* result, Firmware firmware) {
  char patch[5] = "";
  if (firmware.patch > 0) {
    sprintf(patch, ".%d", firmware.patch);
  }
  char beta[5] = "";
  if (firmware.isBeta) {
    sprintf(beta, "-b%d", firmware.betaBuild);
  }
#if LITE
  sprintf(result, "%d.%d%s%s-lite", firmware.major, firmware.minor, patch, beta);
#else
  sprintf(result, "%d.%d%s%s", firmware.major, firmware.minor, patch, beta);
#endif

}

//--Update
#if FW_UPDATE_ENABLED
void saveLatestFirmware() {
  const int *count = settings.fw_update_channel ? &testBinsCount : &binsCount;
  Firmware firmware = currentFirmware;
  for (int i = 0; i < *count; i++) {
    const char* filename = settings.fw_update_channel ? test_bin_list[i] : bin_list[i];
    if (prefix("latest", filename)) continue;
    Firmware parsedFirmware = parseFirmwareVersion(filename);
    if (firstIsNewer(parsedFirmware, firmware)) {
      firmware = parsedFirmware;
    }
  }
  latestFirmware = firmware;
  fwUpdateAvailable = firstIsNewer(latestFirmware, currentFirmware);
  fillFwVersion(newFwVersion, latestFirmware);
  Serial.printf("Latest firmware version: %s\n", newFwVersion);
  Serial.println(fwUpdateAvailable ? "New fw available!" : "No new firmware available");
}

bool prefix(const char *pre, const char *str) {
    return strncmp(pre, str, strlen(pre)) == 0;
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
#endif

JsonDocument parseJson(const char* payload) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload);
  if (error) {
    Serial.printf("Deserialization error: $s\n", error.f_str());
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
  char districtRequest[15];
  sprintf(districtRequest, "district:%d", settings.home_district);
  Serial.println(districtRequest);
  client_websocket.send(districtRequest);
}

void doUpdate() {
  if (initUpdate) {
    initUpdate = false;
    downloadAndUpdateFw(settings.bin_name, settings.fw_update_channel == 1);
  }
}

void downloadAndUpdateFw(const char* binFileName, bool isBeta) {
#if FW_UPDATE_ENABLED
  char spiffUrlChar[100];
  char firmwareUrlChar[100];
  Serial.println("Building spiffs url...");
  sprintf(spiffUrlChar, "http://%s:%d%s%s", settings.serverhost, settings.updateport, isBeta ? "/beta/spiffs/spiffs_" : "/spiffs/spiffs_", binFileName);
  Serial.println("Building firmware url...");
  sprintf(firmwareUrlChar, "http://%s:%d%s%s", settings.serverhost, settings.updateport, isBeta ? "/beta/" : "/", binFileName);

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
#endif
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
#if HA_ENABLED

      if (!mqtt.isConnected()) {
        servicePin(settings.hapin, LOW, true);
      } else {
        servicePin(settings.hapin, HIGH, true);
      }
#endif
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
#if FW_UPDATE_ENABLED
  if (settings.new_fw_notification == 1 && fwUpdateAvailable && settings.button_mode != 0 && !isDisplayOff) {
    downloadAndUpdateFw(settings.fw_update_channel == 1 ? "latest_beta.bin" : "latest.bin", settings.fw_update_channel == 1);
    return;
  }
#endif

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

bool saveMapMode(int newMapMode) {
  if (newMapMode == settings.map_mode) return false;

  if (newMapMode == 5) {
    prevMapMode = settings.map_mode;
  }
  settings.map_mode = newMapMode;
  preferences.begin("storage", false);
  preferences.putInt("mapmode", settings.map_mode);
  preferences.end();
  Serial.print("map_mode commited to preferences: ");
  Serial.println(settings.map_mode);
  #if HA_ENABLED
  if (enableHA) {
    haLight->setState(settings.map_mode == 5);
    haMapMode->setState(settings.map_mode);
    haMapModeCurrent->setValue(mapModes[getCurrentMapMode()]);
  }
  #endif
  showServiceMessage(mapModes[settings.map_mode], "Режим мапи:");
  // update to selected mapMode
  mapCycle();
  return true;
}

bool saveHaBrightness(int newBrightness) {
  if (settings.brightness == newBrightness) return false;
  settings.brightness = newBrightness;
  preferences.begin("storage", false);
  preferences.putInt("brightness", settings.brightness);
  preferences.end();
  Serial.print("brightness commited to preferences");
  Serial.println(settings.ha_light_brightness);
#if HA_ENABLED
  if (enableHA) {
    haBrightness->setState(newBrightness);
  }
#endif
  autoBrightnessUpdate();
  return true;
}

bool saveHaBrightnessAuto(int autoBrightnessMode) {
  if (settings.brightness_mode == autoBrightnessMode) return SPI_FLASH_YIELD_REQ_SUSPEND;
  settings.brightness_mode = autoBrightnessMode;
  preferences.begin("storage", false);
  preferences.putInt("bra", settings.brightness_mode);
  preferences.end();
  Serial.print("brightness_auto commited to preferences: ");
  Serial.println(settings.brightness_mode);
#if HA_ENABLED
  if (enableHA) {
    haBrightnessAuto->setState(autoBrightnessMode);
  }
#endif
  autoBrightnessUpdate();
  showServiceMessage(autoBrightnessOptions[settings.brightness_mode], "Авто. яскравість:");
  return true;
}

bool saveHaAlarmAuto(int newMode) {
  if (settings.alarms_auto_switch == newMode) return false;
  settings.alarms_auto_switch = newMode;
  preferences.begin("storage", false);
  preferences.putInt("aas", settings.alarms_auto_switch);
  preferences.end();
  Serial.print("alarms_auto_switch commited to preferences: ");
  Serial.println(settings.alarms_auto_switch);
#if HA_ENABLED
  if (enableHA) {
    haAlarmsAuto->setState(newMode);
  }
#endif
  return true;
}

bool saveHaShowHomeAlarmTime(bool newState) {
  if (settings.home_alert_time == newState) return false;
  settings.home_alert_time = newState;
  preferences.begin("storage", false);
  preferences.putInt("hat", settings.home_alert_time);
  preferences.end();
  Serial.print("home_alert_time commited to preferences: ");
  Serial.println(settings.home_alert_time ? "true" : "false");
#if HA_ENABLED
  if (enableHA) {
    haShowHomeAlarmTime->setState(newState);
  }
#endif
  return true;
}

bool saveHaLightBrightness(int newBrightness) {
  if (settings.ha_light_brightness == newBrightness) return false;
  settings.ha_light_brightness = newBrightness;
  preferences.begin("storage", false);
  preferences.putInt("ha_lbri", settings.ha_light_brightness);
  preferences.end();
  Serial.print("ha_light_brightness commited to preferences: ");
  Serial.println(settings.ha_light_brightness);
#if HA_ENABLED
  if (enableHA) {
    haLight->setBrightness(newBrightness);
  }
  mapCycle();
#endif
  return true;
}

void saveHaLightRgb(RGBColor newRgb) {
  if (settings.ha_light_r == newRgb.r && settings.ha_light_g == newRgb.g && settings.ha_light_b != newRgb.b) return;
  
  preferences.begin("storage", false);
  if (settings.ha_light_r != newRgb.r) {
    settings.ha_light_r = newRgb.r;
    preferences.putInt("ha_lr", settings.ha_light_r);
    Serial.print("ha_light_red commited to preferences: ");
    Serial.println(settings.ha_light_r);
  }
  if (settings.ha_light_g != newRgb.g) {
    settings.ha_light_g = newRgb.g;
    preferences.putInt("ha_lg", settings.ha_light_g);
    Serial.print("ha_light_green commited to preferences: ");
    Serial.println(settings.ha_light_g);
  }
  if (settings.ha_light_b != newRgb.b) {
    settings.ha_light_b = newRgb.b;
    preferences.putInt("ha_lb", settings.ha_light_b);
    Serial.print("ha_light_blue commited to preferences: ");
    Serial.println(settings.ha_light_b);
  }
  preferences.end();
#if HA_ENABLED
  if (enableHA) {
    haLight->setRGBColor(HALight::RGBColor(settings.ha_light_r, settings.ha_light_g, settings.ha_light_b));
  }
#endif
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

bool saveDisplayMode(int newDisplayMode) {
  if (newDisplayMode == settings.display_mode) return false;
  settings.display_mode = newDisplayMode;
  preferences.begin("storage", false);
  preferences.putInt("dm", settings.display_mode);
  preferences.end();
  Serial.print("display_mode commited to preferences: ");
  Serial.println(settings.display_mode);
#if HA_ENABLED
  if (enableHA) {
    haDisplayMode->setState(getHaDisplayMode(settings.display_mode));
  }
#endif
  showServiceMessage(displayModes[getHaDisplayMode(settings.display_mode)], "Режим дисплея:", 1000);
  // update to selected displayMode
  displayCycle();
  return true;
}
//--Button end

bool saveHomeDistrict(int newHomeDistrict) {
  if (newHomeDistrict == settings.home_district) return false;
  settings.home_district = newHomeDistrict;
  preferences.begin("storage", false);
  preferences.putInt("hd", settings.home_district);
  preferences.end();
  Serial.print("home_district commited to preferences: ");
  Serial.println(settings.home_district);
#if HA_ENABLED
  if (enableHA) {
    haHomeDistrict->setValue(districtsAlphabetical[numDistrictToAlphabet(settings.home_district)]);
    haMapModeCurrent->setValue(mapModes[getCurrentMapMode()]);
  }
#endif
  homeAlertStart = 0;
  parseHomeDistrictJson();
  showServiceMessage(districts[settings.home_district], "Домашній регіон:", 2000);
  return true;
}

//--Display start
void displayCycle() {
#if DISPLAY_ENABLED
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

#if FW_UPDATE_ENABLED
  // Show New Firmware Notification if enabled in settings and New firmware available (Priority - 3)
  if (settings.new_fw_notification == 1 && fwUpdateAvailable) {
    showNewFirmwareNotification();
    return;
  }
#endif

  // Show selected display mode in other cases (Priority - last)
  displayByMode(settings.display_mode);
#endif
}

#if DISPLAY_ENABLED
void displayCenter(const char* text, bool withTitle, int textSize) {
  int16_t x;
  int16_t y;
  uint16_t width;
  uint16_t height;
  char utf8Text[strlen(text)];
  utf8cyr(utf8Text, text);
  display.setTextSize(textSize);
  display.getTextBounds(utf8Text, 0, 0, &x, &y, &width, &height);
  int offsetY = (withTitle ? 10 : 0);
  int cursorX = (settings.display_width - width) / 2;
  int cursorY = max(((settings.display_height - height - offsetY) / 2), 0) + offsetY;
  display.setCursor(cursorX, cursorY);
  display.println(utf8Text);
  display.display();
}

int getTextSizeToFitDisplay(const char* text) {
  int16_t x;
  int16_t y;
  uint16_t textWidth;
  uint16_t height;

  display.setTextWrap(false);
  char utf8Text[strlen(text)]; 
  utf8cyr(utf8Text, text);
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

void utf8cyr(char* target, const char* source) {
  int i, k;
  unsigned char n;
  char m[2] = { '0', '\0' };
  strcpy(target, "");

  k = strlen(source);
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
    strcat(target, m);
  }
}

void serviceMessageUpdate() {
  if (!serviceMessage.expired && millis() > serviceMessage.endTime) {
    serviceMessage.expired = true;
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

bool shouldDisplayBeOff() {
  return serviceMessage.expired && (isDisplayOff || settings.display_mode == 0);
}

void displayMinuteOfSilence() {
  int toggleTime = 3;  // seconds
  int remainder = timeClient.second() % (toggleTime * 3);

  if (remainder < toggleTime) {
    showMinOfSilanceScreen(0);
  } else if (remainder < toggleTime * 2) {
    showMinOfSilanceScreen(1);
  } else {
    showMinOfSilanceScreen(2);
  }
}

void showMinOfSilanceScreen(int screen) {
  display.clearDisplay();
  int16_t centerY = (settings.display_height - 32) / 2;
  display.drawBitmap(0, centerY, trident_small, 32, 32, 1);
  int textSize;
  char text1[20] = "";
  char text2[20] = "";
  char text3[20] = "";
  int gap = 40;
  switch (screen)
  {
  case 0:
    textSize = 1;
    utf8cyr(text1, "Шана");
    utf8cyr(text2, "Полеглим");
    utf8cyr(text3, "Героям!");
    break;
  case 1:
    textSize = 2;
    utf8cyr(text1, "Слава");
    utf8cyr(text3, "Україні!");
    gap = 32;
    break;
  case 2:
   textSize = 2;
    utf8cyr(text1, "Смерть");
    utf8cyr(text3, "ворогам!");
    gap = 32;
    break;
  default:
    break;
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
  displayMessage(message.message, message.title, message.textSize);
}

void showHomeAlertInfo() {
  int toggleTime = settings.display_mode_time;  // seconds
  int remainder = timeClient.second() % (toggleTime * 2);
  char title[50];
  if (remainder < toggleTime) {
    strcpy(title, "Тривога триває:");
  } else {
    strcpy(title, districts[settings.home_district]);
  }
  char message[15];
  fillFromTimer(message, timeClient.unixGMT() - homeAlertStart);

  displayMessage(message, title);
}

#if FW_UPDATE_ENABLED
void showNewFirmwareNotification() {
  int toggleTime = settings.display_mode_time;  // seconds
  int remainder = timeClient.second() % (toggleTime * 2);
  char title[50];
  char message[50];
  if (remainder < toggleTime) {
    strcpy(title, "Доступне оновлення:");
    strcpy(message, newFwVersion);
  } else if (settings.button_mode == 0) {
    strcpy(title, "Введіть у браузері:");
    strcpy(message, WiFi.localIP().toString().c_str());
  } else {
    strcpy(title, "Для оновл. натисніть");
    sprintf(message, "та тримайте кнопку %c", (char)24);
  }
  
  displayMessage(message, title);
}
#endif


void showClock() {
  char time[7];
  sprintf(time, "%02d%c%02d", timeClient.hour(), getDivider(), timeClient.minute());
  const char* date = timeClient.unixToString("DSTRUA DD.MM.YYYY").c_str();
  displayMessage(time, date);
}

void showTemp() {
  int position = calculateOffset(settings.home_district);
  char message[10];
  sprintf(message, "%.1f%cC", weather_leds[position], (char)128);
  displayMessage(message, districts[settings.home_district]);
}

void showTechInfo() {
  int toggleTime = settings.display_mode_time;  // seconds
  int remainder = timeClient.second() % (toggleTime * 6);
  char title[35];
  char message[25];
  // IP address
  if (remainder < toggleTime) {
    strcpy(title, "IP-адреса мапи:");
    strcpy(message, WiFi.localIP().toString().c_str());
    // Wifi Signal level
  } else if (remainder < toggleTime * 2) {
    strcpy(title, "Сигнал WiFi:");
    sprintf(message, "%d dBm", rssi);
    // Uptime
  } else if (remainder < toggleTime * 3) {
    strcpy(title, "Час роботи:");
    fillFromTimer(message, millis() / 1000);
    // map-API status
  } else if (remainder < toggleTime * 4) {
    strcpy(title, "Статус map-API:");
    strcpy(message, apiConnected ? "Підключено" : "Відключено");
    // HA Status
  } else if (remainder < toggleTime * 5) {
    strcpy(title, "Home Assistant:");
    strcpy(message, haConnected ? "Підключено" : "Відключено");
    // Fw version
  } else {
    strcpy(title, "Версія прошивки:");
    strcpy(message, VERSION);
  }

  displayMessage(message, title);
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
  char message[10];
  sprintf(message, "%.1f%cC", localTemp, (char)128);
  displayMessage(message, "Температура");
}

void showLocalHum() {
  char message[10];
  sprintf(message, "%.1f%%", localHum);
  displayMessage(message, "Вологість");
}

void showLocalPresure() {
  char message[12];
  sprintf(message, "%.1fmmHg", localPresure);
  displayMessage(message, "Тиск");
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

void fillFromTimer(char* result, long timerSeconds) {
  unsigned long seconds = timerSeconds;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  if (hours >= 99) {
    strcpy(result, "99+ год.");
  } else {
    seconds %= 60;
    minutes %= 60;
    char divider = getDivider();
    if (hours > 0) {
      sprintf(result, "%02d%c%02d", hours, divider, minutes);
    } else {
      sprintf(result, "%02d%c%02d", minutes, divider, seconds);
    }
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

char getDivider() {
  // Change every second
  if (timeClient.second() % 2 == 0) {
    return ':';
  } else {
    return ' ';
  }
}
//--Display end
#endif

Firmware parseFirmwareVersion(const char *version) {

  Firmware firmware;

  char* versionCopy = strdup(version);
  char* token = strtok(versionCopy, ".-");

  while (token) {
    if (isdigit(token[0])) {
      if (firmware.major == 0)
        firmware.major = atoi(token);
      else if (firmware.minor == 0)
        firmware.minor = atoi(token);
      else if (firmware.patch == 0)
        firmware.patch = atoi(token);
    } else if (firmware.betaBuild == 0 && token[0] == 'b' && strcmp(token, "bin") != 0) {
      firmware.isBeta = true;
      firmware.betaBuild = atoi(token + 1); // Skip the 'b' character
    }
    token = strtok(NULL, ".-");
  }

  free(versionCopy);

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
  webserver.on("/saveSounds", HTTP_POST, handleSaveSounds);
  webserver.on("/saveDev", HTTP_POST, handleSaveDev);
#if FW_UPDATE_ENABLED
  webserver.on("/saveFirmware", HTTP_POST, handleSaveFirmware);
  webserver.on("/update", HTTP_POST, handleUpdate);
#endif
  webserver.begin();
  Serial.println("Webportal running");
}

const char* disableRange(bool isDisabled) {
  return isDisabled ? " disabled" : "";
}

String floatToString(float value) {
  char result[7];
  sprintf(result, "%.1f", value);
  return String(result);
}

String addCheckbox(const char* name, int checkboxIndex, bool isChecked, const char* label) {
  String html;
  html += "<div class='form-group form-check'>";
  html += "<input name='";
  html += name;
  html += "' type='checkbox' class='form-check-input' id=checkbox'";
  html += checkboxIndex;
  html += "'";
  if (isChecked) html += " checked";
  html += "/>";
  html += "<label class='form-check-label' for=checkbox'";
  html += checkboxIndex;
  html += "'>";
  html += label;
  html += "</label>";
  html += "</div>";
  return html;
}

String addSliderInt(const char* name, int sliderIndex, const char* label, int value, int min, int max, int step = 1, const char* unitOfMeasurement = "", bool disabled = false, int colorBoxIndex = -1) {
  String html;
  html += "<div class='form-group'>";
  html += "<label for='slider";
  html += sliderIndex;
  html += "'>";
  html += label;
  html += ": <span id='sliderValue";
  html += sliderIndex;
  html += "'>";
  html += value;
  html += "</span>";
  html += unitOfMeasurement;
  html += "</label>";
  if (colorBoxIndex > 0) {
    html += "</br><div class='color-box' id='colorBox";
    html += colorBoxIndex;
    html += "'></div>";
  }
  html += "<input type='range' name='";
  html += name;
  html += "' class='form-control-range' id='slider";
  html += sliderIndex;
  html += "' min='";
  html += min;
  html += "' max='";
  html += max;
  html += "' step='";
  html += step;
  html += "' value='";
  html += value;
  html += "'";
  html += disabled ? " disabled" : "";
  html += "/>";
  html += "</div>";
  return html;
}

String addSliderFloat(const char* name, int sliderIndex, const char* label, float value, float min, float max, float step = 0.1, const char* unitOfMeasurement = "", bool disabled = false) {
  String html;
  html += "<div class='form-group'>";
  html += "<label for='slider";
  html += sliderIndex;
  html += "'>";
  html += label;
  html += ": <span id='sliderValue";
  html += sliderIndex;
  html += "'>";
  html += floatToString(value);
  html += "</span>";
  html += unitOfMeasurement;
  html += "</label>";
  html += "<input type='range' name='";
  html += name;
  html += "' class='form-control-range' id='slider";
  html += sliderIndex;
  html += "' min='";
  html += min;
  html += "' max='";
  html += max;
  html += "' step='";
  html += step;
  html += "' value='";
  html += value;
  html += "'";
  html += disabled ? " disabled" : "";
  html += "/>";
  html += "</div>";
  return html;
}

String addSelectBox(const char* name, int selectIndex, const char* label, int setting, char* options[], int optionsCount, int (*valueTransform)(int) = NULL, bool disabled = false) {
  String html;
  html += "<div class='form-group'>";
  html += "<label for='selectBox";
  html += selectIndex;
  html += "'>";
  html += label;
  html += "</label>";
  html += "<select name='";
  html += name;
  html += "' class='form-control' id='selectBox";
  html += selectIndex;
  html += "'";
  html += disabled ? " disabled" : "";
  html += ">";
  for (int i = 0; i < optionsCount; i++) {
    int transformedIndex;
    if (valueTransform) {
      transformedIndex = valueTransform(i);
    } else {
      transformedIndex = i;
    }
    html += "<option value='";
    html += transformedIndex;
    html += "'";
    if (setting == transformedIndex) html += " selected";
    html += ">";
    html += options[i];
    html += "</option>";
  }
  html += "</select>";
  html += "</div>";
  return html;
}

String addInputText(const char* name, int inputFieldIndex, const char* label, const char* type, const char* value, int maxLength = -1) {
  String html;
  html += "<div class='form-group'>";
  html += "<label for='inputField";
  html += inputFieldIndex;
  html += "'>";
  html += label;
  html += "</label>";
  html += "<input type='";
  html += type;
  html += "' name='";
  html += name;
  html += "' class='form-control'";
  if (maxLength >= 0) {
    html += " maxlength='";
    html += maxLength;
    html += "'";
  }
  html += " id='inputField";
  html += inputFieldIndex;
  html += "' value='";
  html += value;
  html += "'>";
  html += "</div>";
  return html;
}

void handleRoot(AsyncWebServerRequest* request) {
  String html;
  html += "<!DOCTYPE html>";
  html += "<html lang='en'>";
  html += "<head>";
  html += "    <meta charset='UTF-8'>";
  html += "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "    <title>";
  html += settings.devicename;
  html += "</title>";
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
  html += "        <h2 class='text-center'>";
  html += settings.devicedescription;
  html += " ";
  html += currentVersion;
  html += "        </h2>";
  html += "        <div class='row'>";
  html += "            <div class='col-md-8 offset-md-2'>";
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
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <h5>Локальна IP-адреса: ";
  html += WiFi.localIP().toString();
  html += "                    </h5>";
  html += "                </div>";
  html += "              </div>";
  html += "            </div>";
  html += "        </div>";
#if FW_UPDATE_ENABLED
  if (fwUpdateAvailable) {
    html += "        <div class='row'>";
    html += "           <div class='col-md-8 offset-md-2'>";
    html += "              <div class='row'>";
    html += "                 <div class='box_yellow col-md-12 mt-2' style='background-color: #ffc107; color: #212529'>";
    html += "                    <h8>Доступна нова версія прошивки <a href='https://github.com/v00g100skr/ukraine_alarm_map/releases/tag/";
    html += newFwVersion;
    html += "'>";
    html += newFwVersion;
    html += "</a></br>Для оновлення перейдіть в розділ \"Прошивка\"</h8>";
    html += "                </div>";
    html += "              </div>";
    html += "            </div>";
    html += "        </div>";
  }
#endif
  html += "        <div class='row'>";
  html += "           <div class='col-md-8 offset-md-2'>";
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
#if BUZZER_ENABLED
  html += "                    <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#collapseSounds' aria-expanded='false' aria-controls='collapseSounds'>";
  html += "                         Звуки";
  html += "                    </button>";
#endif
  html += "                    <button class='btn btn-warning' type='button' data-toggle='collapse' data-target='#collapseTech' aria-expanded='false' aria-controls='collapseTech'>";
  html += "                         DEV";
  html += "                    </button>";
#if FW_UPDATE_ENABLED
  html += "                    <button class='btn btn-danger' type='button' data-toggle='collapse' data-target='#collapseFirmware' aria-expanded='false' aria-controls='collapseFirmware'>";
  html += "                         Прошивка";
  html += "                    </button>";
#endif
  html += "                </div>";
  html += "              </div>";
  html += "            </div>";
  html += "        </div>";
  html += "        <form action='/saveBrightness' method='POST'>";
  html += "        <div class='row collapse' id='collapseBrightness' data-parent='#accordion'>";
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += addSliderInt("brightness", 1, "Загальна", settings.brightness, 0, 100, 1, "%", settings.brightness_mode == 1 || settings.brightness_mode == 2);
  html += addSliderInt("brightness_day", 13, "Денна", settings.brightness_day, 0, 100, 1, "%", settings.brightness_mode == 0);
  html += addSliderInt("brightness_night", 14, "Нічна", settings.brightness_night, 0, 100, 1, "%");
  html += addSliderInt("day_start", 15, "Початок дня", settings.day_start, 0, 24, 1, " година", settings.brightness_mode == 0 || settings.brightness_mode == 2);
  html += addSliderInt("night_start", 16, "Початок ночі", settings.night_start, 0, 24, 1, " година", settings.brightness_mode == 0 || settings.brightness_mode == 2);
#if DISPLAY_ENABLED
  html += addSliderInt("disp_brightness", 25, "Дисплей", settings.disp_brightness, 1, 100, 1, "%");
  html += addSliderInt("disp_brightness_night", 26, "Дисплей (ніч)", settings.disp_brightness_night, 1, 100, 1, "%");
#endif
  html += addSelectBox("brightness_auto", 12, "Автоматична яскравість", settings.brightness_mode, autoBrightnessOptions, AUTO_BRIGHTNESS_OPTIONS_COUNT);
  html += addSliderInt("brightness_alert", 9, "Області з тривогами", settings.brightness_alert, 0, 100, 1, "%");
  html += addSliderInt("brightness_clear", 10, "Області без тривог", settings.brightness_clear, 0, 100, 1, "%");
  html += addSliderInt("brightness_new_alert", 11, "Нові тривоги", settings.brightness_new_alert, 0, 100, 1, "%");
  html += addSliderInt("brightness_alert_over", 12, "Відбій тривог", settings.brightness_alert_over, 0, 100, 1, "%");
  html += addSliderFloat("light_sensor_factor", 24, "Коефіцієнт чутливості сенсора освітлення", settings.light_sensor_factor, 0.1, 10, 0.1);
  html += "                    <p class='text-info'>Коефіцієнт чутливості працює наступним чином: Значення менше 1 - знижує чутливість, більше 1 - підвищує. Формула для розрахунку - <b>L = Ls * K</b>, де <b>Ls</b> - дані з сенсора, <b>K</b> - коефіцієнт чутливості, <b>L</b> - рівень освітлення, що використовується для регулювання яскравості мапи.<br>Детальніше на <a href='https://github.com/v00g100skr/ukraine_alarm_map/wiki/%D0%A1%D0%B5%D0%BD%D1%81%D0%BE%D1%80-%D0%BE%D1%81%D0%B2%D1%96%D1%82%D0%BB%D0%B5%D0%BD%D0%BD%D1%8F'>Wiki</a>.</p>";
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/saveColors' method='POST'>";
  html += "        <div class='row collapse' id='collapseColors' data-parent='#accordion'>";
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += addSliderInt("color_alert", 3, "Області з тривогами", settings.color_alert, 0, 360, 1, "", false, 1);
  html += addSliderInt("color_clear", 4, "Області без тривог", settings.color_clear, 0, 360, 1, "", false, 2);
  html += addSliderInt("color_new_alert", 5, "Нові тривоги", settings.color_new_alert, 0, 360, 1, "", false, 3);
  html += addSliderInt("color_alert_over", 6, "Відбій тривог", settings.color_alert_over, 0, 360, 1, "", false, 4);
  html += addSliderInt("color_home_district", 7, "Домашній регіон", settings.color_home_district, 0, 360, 1, "", false, 5);
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/saveWeather' method='POST'>";
  html += "        <div class='row collapse' id='collapseWeather' data-parent='#accordion'>";
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += addSliderInt("weather_min_temp", 18, "Нижній рівень температури", settings.weather_min_temp, -20, 10, 1, "°C");
  html += addSliderInt("weather_max_temp", 8, "Верхній рівень температури", settings.weather_max_temp, 11, 40, 1, "°C");
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
  html += "        <form action='/saveModes' method='POST'>";
  html += "        <div class='row collapse' id='collapseModes' data-parent='#accordion'>";
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  if (settings.legacy) {
  html += addSelectBox("kyiv_district_mode", 1, "Режим діода \"Київська область\"", settings.kyiv_district_mode, kyivLedModeOptions, KYIV_LED_MODE_COUNT, [](int i) -> int {return i + 1;});
  }
  html += addSelectBox("map_mode", 2, "Режим мапи", settings.map_mode, mapModes, MAP_MODES_COUNT);
  html += addSliderInt("color_lamp", 19, "Колір режиму \"Лампа\"", 0, 0, 360, 1, "", false, 17);
  html += addSliderInt("brightness_lamp", 20, "Яскравість режиму \"Лампа\"", settings.ha_light_brightness, 0, 360, 1, "%");
#if DISPLAY_ENABLED
  // html += addSelectBox("display_mode", 5, "Режим дисплея", settings.display_mode, displayModes, MAP_MODES_COUNT);

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
  html += addCheckbox("invert_display", 12, settings.invert_display, "Інвертувати дисплей (темний шрифт на світлому фоні)");
  html += addSliderInt("display_mode_time", 17, "Час перемикання дисплея", settings.display_mode_time, 1, 60, 1, " секунд");
#endif
  if (sht3xInited || bme280Inited || bmp280Inited || htu2xInited) {
    html += addSliderFloat("temp_correction", 21, "Корегування температури", settings.temp_correction, -10, 10, 0.1, "°C");
  }
  if (sht3xInited || bme280Inited || htu2xInited) {
    html += addSliderFloat("hum_correction", 22, "Корегування вологості", settings.hum_correction, -20, 20, 0.5, "%");
  }
  if (bme280Inited || bmp280Inited) {
    html += addSliderFloat("pressure_correction", 22, "Корегування вологості", settings.pressure_correction, -50, 50, 0.5, " мм.рт.ст.");
  }
  html += addSelectBox("button_mode", 6, "Режим кнопки (Single Click)", settings.button_mode, singleClickOptions, SINGLE_CLICK_OPTIONS_COUNT);
  html += addSelectBox("button_mode_long", 10, "Режим кнопки (Long Click)", settings.button_mode_long, longClickOptions, LONG_CLICK_OPTIONS_COUNT);
  html += addSelectBox("home_district", 3, "Домашній регіон", settings.home_district, districtsAlphabetical, DISTRICTS_COUNT, alphabetDistrictToNum);

#if DISPLAY_ENABLED
  html += addCheckbox("home_alert_time", 1, settings.home_alert_time, "Показувати тривалість тривоги у дом. регіоні");
#endif
  html += addSelectBox("alarms_notify_mode", 4, "Відображення на мапі нових тривог та відбою", settings.alarms_notify_mode, alertNotifyOptions, ALERT_NOTIFY_OPTIONS_COUNT);
#if DISPLAY_ENABLED
  if (settings.legacy) {
    html += addSelectBox("display_height", 7, "Розмір дисплею", settings.display_height, displayHeightOptions, DISPLAY_HEIGHT_OPTIONS_COUNT, [](int i) -> int {return i == 0 ? 32 : 64;});
  }
#endif
  html += addSelectBox("alarms_auto_switch", 9, "Перемикання мапи в режим тривоги у випадку тривоги у домашньому регіоні", settings.alarms_auto_switch, autoAlarms, AUTO_ALARM_MODES_COUNT);
  if (!settings.legacy) {
    html += addCheckbox("service_diodes_mode", 2, settings.service_diodes_mode, "Ввімкнути сервісні діоди на задній частині плати");
  }
  html += addCheckbox("min_of_silence", 3, settings.min_of_silence, "Активувати режим \"Хвилина мовчання\" (щоранку о 09:00)");
  html += "                      <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
#if BUZZER_ENABLED
  html += "        <form action='/saveSounds' method='POST'>";
  html += "        <div class='row collapse' id='collapseSounds' data-parent='#accordion'>";
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += addCheckbox("sound_on_startup", 4, settings.sound_on_startup, "Відтворювати мелодію при старті мапи");
  html += addSelectBox("melody_on_startup", 13, "Мелодія при старті мапи", settings.melody_on_startup, melodyNames, MELODIES_COUNT, NULL, settings.sound_on_startup == 0);
  html += addCheckbox("sound_on_min_of_sl", 5, settings.sound_on_min_of_sl, "Відтворювати звуки під час \"Xвилини мовчання\"");
  html += addCheckbox("sound_on_alert", 6, settings.sound_on_alert, "Звукове сповіщення при тривозі у домашньому регіоні");
  html += addSelectBox("melody_on_alert", 14, "Мелодія при тривозі у домашньому регіоні", settings.melody_on_alert, melodyNames, MELODIES_COUNT, NULL, settings.sound_on_alert == 0);
  html += addCheckbox("sound_on_alert_end", 7, settings.sound_on_alert_end, "Звукове сповіщення при скасуванні тривоги у домашньому регіоні");
  html += addSelectBox("melody_on_alert_end", 15, "Мелодія при скасуванні тривоги у домашньому регіоні", settings.melody_on_alert_end, melodyNames, MELODIES_COUNT, NULL, settings.sound_on_alert_end == 0);
  html += addCheckbox("sound_on_every_hour", 8, settings.sound_on_every_hour, "Звукове сповіщення щогодини");
  html += addCheckbox("mute_sound_on_night", 11, settings.mute_sound_on_night, "Вимикати всі звуки у \"Нічному режимі\"");
  html += "                       <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
#endif
  html += "        <form action='/saveDev' method='POST'>";
  html += "        <div class='row collapse' id='collapseTech' data-parent='#accordion'>";
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                    <b>";
  html += "                      <p class='text-danger'>УВАГА: будь-яка зміна налаштування в цьому розділі призводить до примусувого перезаватаження мапи.</p>";
  html += "                      <p class='text-danger'>УВАГА: деякі зміни налаштувань можуть привести до часткової або повної відмови прoшивки, якщо налаштування будуть несумісні з логікою роботи. Будьте впевнені, що Ви точно знаєте, що міняється і для чого.</p>";
  html += "                      <p class='text-danger'>У випадку, коли мапа втратить і не відновить працездатність після змін і перезавантаження (при умові втрати доступу до сторінки керування) - необхідно перепрошити мапу з нуля за допомогою скетча updater.ino (або firmware.ino, якщо Ви збирали прошивку самі Arduino IDE) з репозіторія JAAM за допомогою Arduino IDE, виставивши примусове стирання внутрішньої памʼяті в меню Tools -> Erase all memory before sketch upload</p>";
  html += "                    </b>";
  html += addSelectBox("legacy", 8, "Режим прошивки", settings.legacy, legacyOptions, LEGACY_OPTIONS_COUNT);
  #if HA_ENABLED
  html += addInputText("ha_brokeraddress", 1, "Адреса mqtt-сервера Home Assistant", "text", settings.ha_brokeraddress, 30);
  html += addInputText("ha_mqttport", 2, "Порт mqtt-сервера Home Assistant", "number", String(settings.ha_mqttport).c_str());
  html += addInputText("ha_mqttuser", 3, "Користувач mqtt-сервера Home Assistant", "text", settings.ha_mqttuser, 30);
  html += addInputText("ha_mqttpassword", 4, "Пароль mqtt-сервера Home Assistant", "text", settings.ha_mqttpassword, 50);
  #endif

  html += addInputText("serverhost", 7, "Адреса сервера даних", "text", settings.serverhost, 30);
  html += addInputText("websocket_port", 8, "Порт Websockets", "number", String(settings.websocket_port).c_str());
  html += addInputText("updateport", 9, "Порт сервера прошивок", "number", String(settings.updateport).c_str());
  html += addInputText("devicename", 10, "Назва пристрою", "text", settings.devicename, 30);
  html += addInputText("devicedescription", 11, "Опис пристрою", "text", settings.devicedescription, 50);
  html += addInputText("broadcastname", 12, ("Локальна адреса в мережі (" + String(settings.broadcastname) + ".local)").c_str(), "text", settings.broadcastname, 30);
  if (settings.legacy) {
    html += addInputText("pixelpin", 5, "Керуючий пін лед-стрічки", "number", String(settings.pixelpin).c_str());
    html += addInputText("buttonpin", 6, "Керуючий пін кнопки", "number", String(settings.buttonpin).c_str());
  }
  html += addInputText("alertpin", 13, "Пін, який замкнеться при тривозі у дом. регіоні (має бути digital)", "number", String(settings.alertpin).c_str());
  html += addCheckbox("enable_pin_on_alert", 9, settings.enable_pin_on_alert, ("Замикати пін " + String(settings.alertpin) + " при тривозі у дом. регіоні").c_str());
  html += addInputText("lightpin", 14, "Пін сенсора освітлення (фоторезистора, має бути analog)", "number", String(settings.lightpin).c_str());
#if BUZZER_ENABLED
  html += addInputText("lightpin", 15, "Керуючий пін динаміка (buzzer)", "number", String(settings.buzzerpin).c_str());
#endif
  html += "                    <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                 </div>";
  html += "              </div>";
  html += "           </div>";
  html += "        </div>";
  html += "        </form>";
#if FW_UPDATE_ENABLED
  html += "        <div class='row collapse' id='collapseFirmware' data-parent='#accordion'>";
  html += "           <div class='col-md-8 offset-md-2'>";
  html += "              <div class='row'>";
  html += "                 <div class='box_yellow col-md-12 mt-2'>";
  html += "                       <form action='/saveFirmware' method='POST'>";
  html += addCheckbox("new_fw_notification", 10, settings.new_fw_notification, "Сповіщення про нові прошивки на екрані");
  html += addSelectBox("fw_update_channel", 11, "Канал оновлення прошивок", settings.fw_update_channel, fwUpdateChannels, FW_UPDATE_CHANNELS_COUNT);
  html += "                          <b><p class='text-danger'>УВАГА: Прошивки, що розповсюджуються BETA каналом можуть містити помилки, або вивести мапу з ладу. Якщо у Вас немає можливості прошити мапу через кабель, або ви не знаєте як це зробити, будь ласка, залишайтесь на каналі PRODUCTION!</p></b>";
  html += "                          <button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "                       </form>";
  html += "                       <form action='/update' method='POST'>";
  html += "                          <div class='form-group'>";
  html += "                              <label for='selectBox16'>Файл прошивки</label>";
  html += "                              <select name='bin_name' class='form-control' id='selectBox16'>";
  const int count = settings.fw_update_channel ? testBinsCount : binsCount;
    for (int i = 0; i < count; i++) {
    String filename = String(settings.fw_update_channel ? test_bin_list[i] : bin_list[i]);
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
#endif
  html += "    </div>";
  html += "    </form>";
  html += "    <script src='https://code.jquery.com/jquery-3.5.1.slim.min.js'></script>";
  html += "    <script src='https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.3/dist/umd/popper.min.js'></script>";
  html += "    <script src='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js'></script>";
  html += "    <script>";
  html += "        const sliders = ['slider1', 'slider3', 'slider4', 'slider5', 'slider6', 'slider7', 'slider8', 'slider9', 'slider10', 'slider11', 'slider12', 'slider13', 'slider14', 'slider15', 'slider16'";
#if DISPLAY_ENABLED
  html += ", 'slider17'";
#endif
  html += ", 'slider18', 'slider19', 'slider20'";
  if (sht3xInited || bme280Inited || bmp280Inited || htu2xInited) {
    html += ", 'slider21'";
  }
  if (sht3xInited || bme280Inited || htu2xInited) {
    html += ", 'slider22'";
  }
  if (bme280Inited || bmp280Inited) {
    html += ", 'slider23'";
  }
  html += ", 'slider24'";
  #if DISPLAY_ENABLED
  html += ", 'slider25', 'slider26'";

  #endif
  html += "];";
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
  html += "            const selectedOption = $(this).val();";
  html += "            console.log('Selected auto_brightness option: '.concat(selectedOption));";
  html += "            $('input[name=brightness]').prop('disabled', selectedOption == 1 || selectedOption == 2);";
  html += "            $('input[name=brightness_day]').prop('disabled', selectedOption == 0);";
  html += "            $('input[name=day_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);";
  html += "            $('input[name=night_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);";
  html += "        });";
  html += "";
  html += "        $('input[name=sound_on_startup]').change(function() {";
  html += "            const value = $(this).is(':checked');";
  html += "            console.log('sound_on_startup value: '.concat(value));";
  html += "            $('select[name=melody_on_startup]').prop('disabled', !value);";
  html += "        });";
  html += "";
  html += "        $('input[name=sound_on_alert]').change(function() {";
  html += "            const value = $(this).is(':checked');";
  html += "            $('select[name=melody_on_alert]').prop('disabled', !value);";
  html += "        });";
  html += "";
  html += "        $('input[name=sound_on_alert_end]').change(function() {";
  html += "            const value = $(this).is(':checked');";
  html += "            $('select[name=melody_on_alert_end]').prop('disabled', !value);";
  html += "        });";
  html += "    </script>";
  html += "</body>";
  html += "</html>";
  request->send(200, "text/html", html);
}

RGBColor hue2rgb(int hue) {
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
  RGBColor rgb;
  rgb.r = round(r * 255);
  rgb.g = round(g * 255);
  rgb.b = round(b * 255);
  return rgb;
}

bool saveInt(AsyncWebParameter* param, int *setting, const char* settingsKey, bool (*saveFun)(int) = NULL, void (*additionalFun)(void) = NULL) {
  if (!param) return false;
  int paramValue = param->value().toInt();
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (paramValue != *setting) {
    preferences.begin("storage", false);
    const char* paramName = param->name().c_str();
    *setting = paramValue;
    preferences.putInt(settingsKey, *setting);
    preferences.end();
    Serial.printf("%s commited to preferences: %d\n", paramName, *setting);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
};

bool saveFloat(AsyncWebParameter* param, float *setting, const char* settingsKey, bool (*saveFun)(int) = NULL, void (*additionalFun)(void) = NULL) {
  if (!param) return false;
  float paramValue = param->value().toFloat();
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (paramValue != *setting) {
    preferences.begin("storage", false);
    const char* paramName = param->name().c_str();
    *setting = paramValue;
    preferences.putFloat(settingsKey, *setting);
    preferences.end();
    Serial.printf("%s commited to preferences: %.1f\n", paramName, *setting);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
};

bool saveBool(AsyncWebParameter* param, int *setting, const char* settingsKey, bool (*saveFun)(bool) = NULL, void (*additionalFun)(void) = NULL) {
  int paramValue = param ? 1 : 0;
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (paramValue != *setting) {
    preferences.begin("storage", false);
    const char* paramName = param ? param->name().c_str() : settingsKey;
    *setting = paramValue;
    preferences.putInt(settingsKey, *setting);
    preferences.end();
    Serial.printf("%s commited to preferences: %s\n", paramName, *setting ? "true" : "false");
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
};

bool saveString(AsyncWebParameter* param, char* setting, const char* settingsKey, bool (*saveFun)(const char*) = NULL, void (*additionalFun)(void) = NULL) {
  if (!param) return false;
  const char* paramValue = param->value().c_str();
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (strcmp(paramValue, setting) != 0) {
    preferences.begin("storage", false);
    const char* paramName = param->name().c_str();
    strcpy(setting, paramValue);
    preferences.putString(settingsKey, setting);
    preferences.end();
    Serial.printf("%s commited to preferences: %s\n", paramName, setting);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
};
#if FW_UPDATE_ENABLED
void handleUpdate(AsyncWebServerRequest* request) {
  Serial.println("do_update triggered");
  initUpdate = true;
  if (request->hasParam("bin_name", true)) {
    const char* bin_name = request->getParam("bin_name", true)->value().c_str();
    strcpy(settings.bin_name, bin_name);
  }
  request->redirect("/");
}
#endif

void handleSaveBrightness(AsyncWebServerRequest *request) {
  saveInt(request->getParam("brightness", true), &settings.brightness, "brightness", saveHaBrightness);
  saveInt(request->getParam("brightness_day", true), &settings.brightness_day, "brd", NULL, distributeBrightnessLevels);
  saveInt(request->getParam("brightness_night", true), &settings.brightness_night, "brn", NULL, distributeBrightnessLevels);
  saveInt(request->getParam("day_start", true), &settings.day_start, "ds");
  saveInt(request->getParam("night_start", true), &settings.night_start, "ns");
  saveInt(request->getParam("brightness_auto", true), &settings.brightness_mode, "bra", saveHaBrightnessAuto);
  saveInt(request->getParam("brightness_alert", true), &settings.brightness_alert, "ba");
  saveInt(request->getParam("brightness_clear", true), &settings.brightness_clear, "bc");
  saveInt(request->getParam("brightness_new_alert", true), &settings.brightness_new_alert, "bna");
  saveInt(request->getParam("brightness_alert_over", true), &settings.brightness_alert_over, "bao");
  saveFloat(request->getParam("light_sensor_factor", true), &settings.light_sensor_factor, "lsf");
  saveInt(request->getParam("disp_brightness", true), &settings.disp_brightness, "dbr", NULL, distributeBrightnessLevels);
  saveInt(request->getParam("disp_brightness_night", true), &settings.disp_brightness_night, "dbrn", NULL, distributeBrightnessLevels);
  autoBrightnessUpdate();
  request->redirect("/");
}

void handleSaveColors(AsyncWebServerRequest* request) {
  saveInt(request->getParam("color_alert", true), &settings.color_alert, "coloral");
  saveInt(request->getParam("color_clear", true), &settings.color_clear, "colorcl");
  saveInt(request->getParam("color_new_alert", true), &settings.color_new_alert, "colorna");
  saveInt(request->getParam("color_alert_over", true), &settings.color_alert_over, "colorao");
  saveInt(request->getParam("color_home_district", true), &settings.color_home_district, "colorhd");
  request->redirect("/");
}

void handleSaveWeather(AsyncWebServerRequest* request) {
  saveInt(request->getParam("weather_min_temp", true), &settings.weather_min_temp, "mintemp");
  saveInt(request->getParam("weather_max_temp", true), &settings.weather_max_temp, "maxtemp");
  request->redirect("/");
}

void handleSaveModes(AsyncWebServerRequest* request) {
  saveInt(request->getParam("map_mode", true), &settings.map_mode, "mapmode", saveMapMode);
  saveInt(request->getParam("brightness_lamp", true), &settings.ha_light_brightness, "ha_lbri", saveHaLightBrightness);
  saveInt(request->getParam("display_mode", true), &settings.display_mode, "dm", saveDisplayMode);
  saveInt(request->getParam("home_district", true), &settings.home_district, "hd", saveHomeDistrict);
  saveInt(request->getParam("display_mode_time", true), &settings.display_mode_time, "dmt");
  saveFloat(request->getParam("temp_correction", true), &settings.temp_correction, "ltc", NULL, localTempHumSensorCycle);
  saveFloat(request->getParam("hum_correction", true), &settings.hum_correction, "lhc", NULL, localTempHumSensorCycle);
  saveFloat(request->getParam("pressure_correction", true), &settings.pressure_correction, "lpc", NULL, localTempHumSensorCycle);
  saveInt(request->getParam("button_mode", true), &settings.button_mode, "bm");
  saveInt(request->getParam("button_mode_long", true), &settings.button_mode_long, "bml");
  saveInt(request->getParam("kyiv_district_mode", true), &settings.kyiv_district_mode, "kdm");
  saveBool(request->getParam("home_alert_time", true), &settings.home_alert_time, "hat", saveHaShowHomeAlarmTime, parseHomeDistrictJson);
  saveInt(request->getParam("alarms_notify_mode", true), &settings.alarms_notify_mode, "anm");
  bool reboot = saveInt(request->getParam("display_height", true), &settings.display_height, "dh");
  saveInt(request->getParam("alarms_auto_switch", true), &settings.alarms_auto_switch, "aas", saveHaAlarmAuto);
  saveBool(request->getParam("service_diodes_mode", true), &settings.service_diodes_mode, "sdm", NULL, checkServicePins);
  saveBool(request->getParam("min_of_silence", true), &settings.min_of_silence, "mos");
  saveBool(request->getParam("invert_display", true), &settings.invert_display, "invd", NULL, updateInvertDisplayMode);
  
  if (request->hasParam("color_lamp", true)) {
    int selectedHue = request->getParam("color_lamp", true)->value().toInt();
    RGBColor rgb = hue2rgb(selectedHue);
    saveHaLightRgb(rgb);
  }

  request->redirect("/");
  if (reboot) {
    rebootDevice(3000, true);
  }
}

void handleSaveSounds(AsyncWebServerRequest* request) {
  saveBool(request->getParam("sound_on_startup", true), &settings.sound_on_startup, "sos");
  saveInt(request->getParam("melody_on_startup", true), &settings.melody_on_startup, "most");
  saveBool(request->getParam("sound_on_min_of_sl", true), &settings.sound_on_min_of_sl, "somos");
  saveBool(request->getParam("sound_on_alert", true), &settings.sound_on_alert, "soa");
  saveInt(request->getParam("melody_on_alert", true), &settings.melody_on_alert, "moa");
  saveBool(request->getParam("sound_on_alert_end", true), &settings.sound_on_alert_end, "soae");
  saveInt(request->getParam("melody_on_alert_end", true), &settings.melody_on_alert_end, "moae");
  saveBool(request->getParam("sound_on_every_hour", true), &settings.sound_on_every_hour, "soeh");
  saveBool(request->getParam("mute_sound_on_night", true), &settings.mute_sound_on_night, "mson");
  request->redirect("/");
}

void handleSaveDev(AsyncWebServerRequest* request) {
  bool reboot = false;
  reboot = saveInt(request->getParam("legacy", true), &settings.legacy, "legacy") || reboot;
  reboot = saveString(request->getParam("ha_brokeraddress", true), settings.ha_brokeraddress, "ha_brokeraddr") || reboot;
  reboot = saveInt(request->getParam("ha_mqttport", true), &settings.ha_mqttport, "ha_mqttport") || reboot;
  reboot = saveString(request->getParam("ha_mqttuser", true), settings.ha_mqttuser, "ha_mqttuser") || reboot;
  reboot = saveString(request->getParam("ha_mqttpassword", true), settings.ha_mqttpassword, "ha_mqttpass") || reboot;
  reboot = saveString(request->getParam("devicename", true), settings.devicename, "dn") || reboot;
  reboot = saveString(request->getParam("devicedescription", true), settings.devicedescription, "dd") || reboot;
  reboot = saveString(request->getParam("broadcastname", true), settings.broadcastname, "bn") || reboot;
  reboot = saveString(request->getParam("serverhost", true), settings.serverhost, "host") || reboot;
  reboot = saveInt(request->getParam("websocket_port", true), &settings.websocket_port, "wsp") || reboot;
  reboot = saveInt(request->getParam("updateport", true), &settings.updateport, "upport") || reboot;
  reboot = saveInt(request->getParam("pixelpin", true), &settings.pixelpin, "pp") || reboot;
  reboot = saveInt(request->getParam("buttonpin", true), &settings.buttonpin, "bp") || reboot;
  reboot = saveInt(request->getParam("alertpin", true), &settings.alertpin, "ap") || reboot;
  reboot = saveInt(request->getParam("lightpin", true), &settings.lightpin, "lp") || reboot;
  reboot = saveInt(request->getParam("buzzerpin", true), &settings.buzzerpin, "bzp") || reboot;
  reboot = saveBool(request->getParam("enable_pin_on_alert", true), &settings.enable_pin_on_alert, "epoa") || reboot;

  request->redirect("/");
  if (reboot) {
    rebootDevice(3000, true);
  }
}
#if FW_UPDATE_ENABLED
void handleSaveFirmware(AsyncWebServerRequest* request) {
  saveBool(request->getParam("new_fw_notification", true), &settings.new_fw_notification, "nfwn");
  saveInt(request->getParam("fw_update_channel", true), &settings.fw_update_channel, "fwuc", NULL, saveLatestFirmware);
  request->redirect("/");
}
#endif
//--Web server end

//--Service messages start
void uptime() {
  int   uptimeValue   = millis() / 1000;
  float totalHeapSize = ESP.getHeapSize() / 1024.0;
  float freeHeapSize  = ESP.getFreeHeap() / 1024.0;
  float usedHeapSize  = totalHeapSize - freeHeapSize;
  float cpuTemp       = temperatureRead();
            
  rssi = WiFi.RSSI();
#if HA_ENABLED
  if (enableHA) {
    haUptime->setValue(uptimeValue);
    haWifiSignal->setValue(rssi);
    haFreeMemory->setValue(freeHeapSize);
    haUsedMemory->setValue(usedHeapSize);
    haCpuTemp->setValue(cpuTemp);
  }
#endif
}

void connectStatuses() {
  Serial.print("Map API connected: ");
  apiConnected = client_websocket.available();
  Serial.println(apiConnected);
  haConnected = false;
#if HA_ENABLED
  if (enableHA) {
    Serial.print("Home Assistant MQTT connected: ");
    Serial.println(mqtt.isConnected());
    if (mqtt.isConnected()) {
      haConnected = true;
      servicePin(settings.hapin, HIGH, false);
    } else {
      servicePin(settings.hapin, LOW, false);
    }
    haMapApiConnect->setState(apiConnected, true);
  }
#endif
}

void distributeBrightnessLevels() {
  distributeBrightnessLevelsFor(settings.brightness_day, settings.brightness_night, ledsBrightnessLevels, "Leds");
#if DISPLAY_ENABLED
  distributeBrightnessLevelsFor(settings.disp_brightness, settings.disp_brightness_night, dispBrightnessLevels, "Display");
#endif
}

void distributeBrightnessLevelsFor(int dayBrightness, int nightBrightness, int *brightnessLevels, const char* logTitle) {
  int minBrightness = min(dayBrightness, nightBrightness);
  int maxBrightness = max(dayBrightness, nightBrightness);
  float step = (maxBrightness - minBrightness) / (BR_LEVELS_COUNT - 1.0);
  Serial.printf("%s brightness levels: [", logTitle);
  for (int i = 0; i < BR_LEVELS_COUNT; i++) {
    brightnessLevels[i] = round(i == BR_LEVELS_COUNT - 1 ? maxBrightness : minBrightness + i * step), maxBrightness;
    Serial.print(brightnessLevels[i]);
    if (i < BR_LEVELS_COUNT - 1) Serial.print(", ");
  }
  Serial.println("]");
}

void autoBrightnessUpdate() {
  int tempBrightness = getCurrentBrightnes(settings.brightness, settings.brightness_day, settings.brightness_night, ledsBrightnessLevels);
  if (tempBrightness != settings.current_brightness) {
    settings.current_brightness = tempBrightness;
    preferences.begin("storage", false);
    preferences.putInt("cbr", settings.current_brightness);
    preferences.end();
    Serial.print("set current brightness: ");
    Serial.println(settings.current_brightness);
  }
}

int getBrightnessFromSensor(int brightnessLevels[]) {
  return brightnessLevels[getCurrentBrightnessLevel()];
}

// Determine the current brightness level
int getCurrentBrightnessLevel() {
  int currentValue;
  int maxValue;
#if BH1750_ENABLED
  if (bh1750Inited) {
    // BH1750 have higher priority. BH1750 measurmant range is 0..27306 lx. 500 lx - very bright indoor environment.
    currentValue = round(lightInLuxes);
    maxValue = 500;
  } else {
#endif
    // reads the input on analog pin (value between 0 and 4095)
    currentValue = round(analogRead(settings.lightpin) * settings.light_sensor_factor);
    // 2600 - very bright indoor environment.
    maxValue = 2600;
#if BH1750_ENABLED
  }
#endif
  int level = map(min(currentValue, maxValue), 0, maxValue, 0, BR_LEVELS_COUNT - 1);
  // Serial.print("Brightness level: ");
  // Serial.println(level);
  return level;
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

  // if auto brightness set to day/night mode, check current hour and choose brightness
  if (settings.brightness_mode == 1) return isItNightNow() ? nightBrightness : dayBrightness;

  // if auto brightnes set to light sensor, read sensor value end return appropriate brightness.
  if (settings.brightness_mode == 2) return getBrightnessFromSensor(brightnessLevels);

  // if auto brightnes deactivated, return regular brightnes
  //default
  return defaultBrightness;
}

bool isItNightNow() {
  // if day and night start time is equels it means it's always day, return day
  if (settings.night_start == settings.day_start) return false;

  int currentHour = timeClient.hour();

  // handle case, when night start hour is bigger than day start hour, ex. night start at 22 and day start at 9
  if (settings.night_start > settings.day_start)
    return currentHour >= settings.night_start || currentHour < settings.day_start ? true : false;

  // handle case, when day start hour is bigger than night start hour, ex. night start at 1 and day start at 8
  return currentHour < settings.day_start && currentHour >= settings.night_start ? true : false;
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
  JsonDocument data = parseJson(message.data().c_str());
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
#if FW_UPDATE_ENABLED
    } else if (payload == "bins") {
      fillBinList(data, "bins", bin_list, &binsCount);
      saveLatestFirmware();
    } else if (payload == "test_bins") {
      fillBinList(data, "test_bins", test_bin_list, &testBinsCount);
      saveLatestFirmware();
#endif
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

#if FW_UPDATE_ENABLED
void fillBinList(JsonDocument data, const char* payloadKey, char* binsList[], int *binsCount) {
  JsonArray arr = data[payloadKey].as<JsonArray>();
  *binsCount = min(static_cast<int>(arr.size()), MAX_BINS_LIST_SIZE);
  for (int i = 0; i < *binsCount; i++) {
    const char* filename = arr[i].as<const char*>();
    binsList[i] = new char[strlen(filename)];
    strcpy(binsList[i], filename);
  }
  Serial.printf("Successfully parsed %s list. List size: %d\n", payloadKey, *binsCount);
}
#endif

void onEventsCallback(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    apiConnected = true;
    Serial.println("connnection opened");
    servicePin(settings.datapin, HIGH, false);
    websocketLastPingTime = millis();
#if HA_ENABLED
    if (enableHA) {
      haMapApiConnect->setState(apiConnected, true);
    }
#endif
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    apiConnected = false;
    Serial.println("connnection closed");
    servicePin(settings.datapin, LOW, false);
#if HA_ENABLED
    if (enableHA) {
      haMapApiConnect->setState(apiConnected, true);
    }
#endif
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
  showServiceMessage("підключення...", "Сервер даних");
  client_websocket.onMessage(onMessageCallback);
  client_websocket.onEvent(onEventsCallback);
  long startTime = millis();
  char webSocketUrl[100];
  sprintf(webSocketUrl, "ws://%s:%d/data_v1", settings.serverhost, settings.websocket_port);
  Serial.println(webSocketUrl);
  client_websocket.connect(webSocketUrl);
  if (client_websocket.available()) {
    Serial.print("connection time - ");
    Serial.print(millis() - startTime);
    Serial.println("ms");
    char firmwareInfo[100];
    sprintf(firmwareInfo, "firmware:%s_%s", currentVersion, settings.identifier);
    Serial.println(firmwareInfo);
    client_websocket.send(firmwareInfo);
    char chipIdInfo[25];
    sprintf(chipIdInfo, "chip_id:%s", chipID);
    Serial.println(chipIdInfo);
    client_websocket.send(chipIdInfo);
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
#if HA_ENABLED
    if (enableHA) {
      haMapModeCurrent->setValue(mapModes[getCurrentMapMode()]);
    }
#endif
    // play clock beep every 2 sec during min of silence
    if (minuteOfSilence && needToPlaySound(MIN_OF_SILINCE)) {
      clockBeepInterval = asyncEngine.setInterval(playMinOfSilenceSound, 2000); // every 2 sec
      }
    // turn off clock beep
    if (!minuteOfSilence && clockBeepInterval >= 0) {
      asyncEngine.clearInterval(clockBeepInterval);
    }
#if BUZZER_ENABLED
    // play UA Anthem when min of silence ends
    if (!minuteOfSilence && needToPlaySound(MIN_OF_SILINCE)) {
      playMelody(uaAnthem);
      uaAnthemPlaying = true;
    }
#endif
  }
}

void playMinOfSilenceSound() {
  playMelody(MIN_OF_SILINCE);
}

float processWeather(int led) {
  float minTemp = settings.weather_min_temp;
  float maxTemp = settings.weather_max_temp;
  float temp = led;
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
  if (minuteOfSilence || uaAnthemPlaying) return 3; //ua flag

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
#if HA_ENABLED
  if (enableHA) {
    haMapModeCurrent->setValue(mapModes[currentMapMode]);
  }
#endif
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

void calculateStates() {
  // check if we need activate "minute of silence mode"
  checkMinuteOfSilence();

  // check alert in home district
  checkHomeDistrictAlerts();

#if BUZZER_ENABLED
  checkCurrentTimeAndPlaySound();

  if (uaAnthemPlaying && !player->isPlaying()) {
    uaAnthemPlaying = false;
  }
#endif
#if DISPLAY_ENABLED
  // update service message expiration
  serviceMessageUpdate();
#endif
}

void checkHomeDistrictAlerts() {
  int ledStatus = alarm_leds[calculateOffset(settings.home_district)];
  bool localAlarmNow = (ledStatus == 1 || ledStatus == 3);
  if (localAlarmNow != alarmNow) {
    alarmNow = localAlarmNow;
    if (alarmNow && needToPlaySound(ALERT_ON)) playMelody(ALERT_ON); 
    if (!alarmNow && needToPlaySound(ALERT_OFF)) playMelody(ALERT_OFF);

    alertPinCycle();

    if (alarmNow) {
      showServiceMessage("Тривога!", "У вашому регіоні", 5000);
    } else {
      showServiceMessage("Відбій!", "У вашому регіоні", 5000);
    }
  }
}

void checkCurrentTimeAndPlaySound() {
  if (needToPlaySound(REGULAR) && beepHour != timeClient.hour() && timeClient.minute() == 0 && timeClient.second() == 0) {
    beepHour = timeClient.hour();
    playMelody(REGULAR);
  }
}

void bh1750LightSensorCycle() {
#if BH1750_ENABLED
  if (!bh1750Inited) return;
  lightInLuxes = bh1750.getLux() * settings.light_sensor_factor;
  // Serial.print("BH1750!\tLight: ");
  // Serial.print(lightInLuxes);
  // Serial.println(" lx");
#endif
}

void localTempHumSensorCycle() {
#if BME280_ENABLED
  if (bme280Inited || bmp280Inited) {
    bme280.takeForcedMeasurement();

    localTemp = bme280.getTemperatureCelsiusAsFloat() + settings.temp_correction;
    localPresure = bme280.getPressureAsFloat() * 0.75006157584566 + settings.pressure_correction;  //mmHg

    if (bme280Inited) {
      localHum = bme280.getRelativeHumidityAsFloat() + settings.hum_correction;
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
#endif
#if SHT3X_ENABLED
  if (sht3xInited && sht3x.readSample()) {
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
#endif
#if SHT2X_ENABLED
  if (htu2xInited && htu2x.readSample()) {
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
#endif
}

void setup() {
  Serial.begin(115200);

  initHaVars();
  initSettings();
  initLegacy();
  initBuzzer();
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
  asyncEngine.setInterval(calculateStates, 500);
}

void loop() {
  wm.process();
  asyncEngine.run();
#if ARDUINO_OTA_ENABLED
  ArduinoOTA.handle();
#endif
  buttonUpdate();
#if HA_ENABLED
  if (enableHA) {
    mqtt.loop();
  }
#endif
  client_websocket.poll();
  syncTime(2);
}
