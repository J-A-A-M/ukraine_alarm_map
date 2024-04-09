#include "Definitions.h"
#include "JaamUtils.h"
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
#include "JaamDisplay.h"
#if FW_UPDATE_ENABLED
#include <HTTPUpdate.h>
#endif
#include <ArduinoWebsockets.h>
#include "JaamLightSensor.h"
#include "JaamClimateSensor.h"
#if BUZZER_ENABLED
#include <melody_player.h>
#include <melody_factory.h>
#endif

const PROGMEM char* VERSION = "3.9";

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
  int     color_new_alert        = 30;
  int     color_alert_over       = 100;
  int     color_explosion        = 180;
  int     color_home_district    = 120;
  int     brightness_alert       = 100;
  int     brightness_clear       = 100;
  int     brightness_new_alert   = 100;
  int     brightness_alert_over  = 100;
  int     brightness_explosion   = 100;
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
  int     melody_on_alert        = 4;
  int     sound_on_alert_end     = 0;
  int     melody_on_alert_end    = 5;
  int     sound_on_explosion     = 0;
  int     melody_on_explosion    = 18;
  int     sound_on_every_hour    = 0;
  int     sound_on_button_click  = 0;
  int     mute_sound_on_night    = 0;
  int     invert_display         = 0;
  int     dim_display_on_night   = 1;
  int     ignore_mute_on_alert   = 0;


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
  int     display_model          = 1;
  int     display_width          = 128;
  int     display_height         = 32;
  int     day_start              = 8;
  int     night_start            = 22;
  int     ws_alert_time          = 150000;
  int     ws_reboot_time         = 300000;
  int     min_of_silence         = 1;
  int     enable_pin_on_alert    = 0;
  int     fw_update_channel      = 0;
  float   temp_correction        = 0;
  float   hum_correction         = 0;
  float   pressure_correction    = 0;
  float   light_sensor_factor    = 1;
  int     time_zone              = 2;
  int     alert_on_time          = 5;
  int     alert_off_time         = 5;
  int     explosion_time         = 3;
  int     alert_blink_time       = 2;
  // ------- web config end
};

Settings settings;

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
JaamDisplay       display;
JaamLightSensor   lightSensor;
JaamClimateSensor climate;
#if BUZZER_ENABLED
MelodyPlayer* player;
#endif

enum SoundType {
  START_UP,
  MIN_OF_SILINCE,
  MIN_OF_SILINCE_END,
  REGULAR,
  ALERT_ON,
  ALERT_OFF,
  EXPLOSIONS,
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

NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod>* strip;

uint8_t   alarm_leds[26];
long      alarm_time[26];
float     weather_leds[26];
long      explosions_time[26];
uint8_t   flag_leds[26];

#if HA_ENABLED
bool    enableHA;
#endif
bool    shouldWifiReconnect = false;
bool    websocketReconnect = false;
bool    isDaylightSaving = false;
time_t  websocketLastPingTime = 0;
int     offset = 9;
bool    initUpdate = false;
#if FW_UPDATE_ENABLED
bool    fwUpdateAvailable = false;
char    newFwVersion[25];
#endif
char    currentFwVersion[25];
bool    apiConnected;
bool    haConnected;
int     prevMapMode = 1;
bool    alarmNow = false;
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

int     ledsBrightnessLevels[BR_LEVELS_COUNT]; // Array containing LEDs brightness values
int     currentDimDisplay = 0;

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

int binsCount = 0;
char* bin_list[MAX_BINS_LIST_SIZE];

int testBinsCount = 0;
char*  test_bin_list[MAX_BINS_LIST_SIZE];

char chipID[13];
char localIP[16];
#if HA_ENABLED
HADevice        device;
HAMqtt          mqtt(client, device, 26);
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
char haAlarmAtHomeID[27];
char haLocalTempID[24];
char haLocalHumID[23];
char haLocalPressureID[28];
char haLightLevelID[25];
char haHomeTempID[23];
char haNightModeID[24];

HASensorNumber*  haUptime;
HASensorNumber*  haWifiSignal;
HASensorNumber*  haFreeMemory;
HASensorNumber*  haUsedMemory;
HASensorNumber*  haCpuTemp;
HANumber*        haBrightness;
HASelect*        haMapMode;
HASelect*        haDisplayMode;
HASwitch*        haShowHomeAlarmTime;
HAButton*        haToggleDisplayMode;
HASelect*        haAlarmsAuto;
HASelect*        haBrightnessAuto;
HASensor*        haMapModeCurrent;
HASensor*        haHomeDistrict;
HABinarySensor*  haMapApiConnect;
HAButton*        haReboot;
HAButton*        haToggleMapMode;
HALight*         haLight;
HABinarySensor*  haAlarmAtHome;
HASensorNumber*  haLocalTemp;
HASensorNumber*  haLocalHum;
HASensorNumber*  haLocalPressure;
HASensorNumber*  haLightLevel;
HASensorNumber*  haHomeTemp;
HASwitch*        haNightMode;
#endif

std::map<int, int> displayModeHAMap;
int ignoreDisplayModeOptions[DISPLAY_MODE_OPTIONS_MAX] = {-1, -1, -1, -1, -1, -1};
int ignoreSingleClickOptions[SINGLE_CLICK_OPTIONS_MAX] = {-1, -1, -1, -1, -1, -1, -1};
int ignoreLongClickOptions[LONG_CLICK_OPTIONS_MAX] = {-1, -1, -1, -1, -1, -1, -1, -1};

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

void initChipID() {
  uint64_t chipid = ESP.getEfuseMac();
  sprintf(chipID, "%04x%04x", (uint32_t)(chipid >> 32), (uint32_t)chipid);
  Serial.printf("ChipID Inited: '%s'\n", chipID);
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
  settings.color_explosion        = preferences.getInt("colorex", settings.color_explosion);
  settings.color_home_district    = preferences.getInt("colorhd", settings.color_home_district);
  settings.brightness_alert       = preferences.getInt("ba", settings.brightness_alert);
  settings.brightness_clear       = preferences.getInt("bc", settings.brightness_clear);
  settings.brightness_new_alert   = preferences.getInt("bna", settings.brightness_new_alert);
  settings.brightness_alert_over  = preferences.getInt("bao", settings.brightness_alert_over);
  settings.brightness_explosion   = preferences.getInt("bex", settings.brightness_explosion);
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
  settings.display_model          = preferences.getInt("dsmd", settings.display_model);
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
  settings.sound_on_button_click  = preferences.getInt("sobc", settings.sound_on_button_click);
  settings.sound_on_explosion     = preferences.getInt("soex", settings.sound_on_explosion);
  settings.melody_on_startup      = preferences.getInt("most", settings.melody_on_startup);
  settings.melody_on_alert        = preferences.getInt("moa", settings.melody_on_alert);
  settings.melody_on_alert_end    = preferences.getInt("moae", settings.melody_on_alert_end);
  settings.melody_on_explosion    = preferences.getInt("moex", settings.melody_on_explosion);
  settings.mute_sound_on_night    = preferences.getInt("mson", settings.mute_sound_on_night);
  settings.invert_display         = preferences.getInt("invd", settings.invert_display);
  settings.dim_display_on_night   = preferences.getInt("ddon", settings.dim_display_on_night);
  settings.time_zone              = preferences.getInt("tz", settings.time_zone);
  settings.ignore_mute_on_alert   = preferences.getInt("imoa", settings.ignore_mute_on_alert);
  settings.alert_on_time          = preferences.getInt("aont", settings.alert_on_time);
  settings.alert_off_time         = preferences.getInt("aoft", settings.alert_off_time);
  settings.explosion_time         = preferences.getInt("ext", settings.explosion_time);
  settings.alert_blink_time       = preferences.getInt("abt", settings.alert_blink_time);
  
  preferences.end();

  currentFirmware = parseFirmwareVersion(VERSION);
  fillFwVersion(currentFwVersion, currentFirmware);
  Serial.printf("Current firmware version: %s\n", currentFwVersion);
  distributeBrightnessLevels();
}

void initLegacy() {
  switch (settings.legacy) {
  case 0:
    Serial.println("Mode: jaam");
    for (int i = 0; i < 26; i++) {
      flag_leds[calculateOffset(i, offset)] = legacy_flag_leds[i];
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
    settings.display_model = 1;
    settings.display_height = 64;
    break;
  case 1:
    Serial.println("Mode: transcarpathia");
    offset = 0;
    for (int i = 0; i < 26; i++) {
      flag_leds[i] = legacy_flag_leds[i];
    }
    settings.service_diodes_mode = 0;
    break;
  case 2:
    Serial.println("Mode: odesa");
    for (int i = 0; i < 26; i++) {
      flag_leds[calculateOffset(i, offset)] = legacy_flag_leds[i];
    }
    break;
  }
  pinMode(settings.buttonpin, INPUT_PULLUP);
  Serial.printf("Offset: %d\n", offset);
}

void initBuzzer() {
#if BUZZER_ENABLED
  player = new MelodyPlayer(settings.buzzerpin, 0, HIGH);
  if (needToPlaySound(START_UP)) {
    playMelody(START_UP);
  }
#endif
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

void initDisplay() {
  display.begin(static_cast<JaamDisplay::DisplayModel>(settings.display_model), settings.display_width, settings.display_height);

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

void initSensors() {
  lightSensor.begin();
  if (lightSensor.isLightSensorAvailable()) {
    lightSensorCycle();
  }
  lightSensor.setPhotoresistorPin(settings.lightpin);

  // init climate sensor
  climate.begin();
  // try to get climate sensor data
  climateSensorCycle();

  initDisplayModes();
}

void initWifi() {
  Serial.println("Init Wifi");
  WiFi.mode(WIFI_STA); // explicitly set mode, esp defaults to STA+AP
  // reset settings - wipe credentials for testing
  // wm.resetSettings();

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
  initHA();
  socketConnect();
  showServiceMessage(getLocalIP(), "IP-адреса мапи:", 5000);
}

void initTime() {
  Serial.println("Init time");
  timeClient.setTimeZone(settings.time_zone);
  timeClient.setDSTauto(&dst); // auto update on summer/winter time.
  timeClient.setTimeout(5000); // 5 seconds waiting for reply
  timeClient.begin();
  syncTime(7);
}

void initHaVars() {
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
  haCpuTemp = new HASensorNumber(haCpuTempID, HASensorNumber::PrecisionP2);

  sprintf(haBrightnessID, "%s_brightness", chipID);
  haBrightness = new HANumber(haBrightnessID);

  sprintf(haMapModeID, "%s_map_mode", chipID);
  haMapMode = new HASelect(haMapModeID);
  if (display.isDisplayAvailable()) {
    sprintf(haDisplayModeID, "%s_display_mode", chipID);
    haDisplayMode = new HASelect(haDisplayModeID);

    sprintf(haToggleDisplayModeID, "%s_toggle_display_mode", chipID);
    haToggleDisplayMode = new HAButton(haToggleDisplayModeID);

    sprintf(haShowHomeAlarmTimeID, "%s_show_home_alarm_time", chipID);
    haShowHomeAlarmTime = new HASwitch(haShowHomeAlarmTimeID);
  }
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

  sprintf(haRebootID, "%s_reboot", chipID);
  haReboot = new HAButton(haRebootID);

  sprintf(haToggleMapModeID, "%s_toggle_map_mode", chipID);
  haToggleMapMode = new HAButton(haToggleMapModeID);

  sprintf(haLightID, "%s_light", chipID);
  haLight = new HALight(haLightID, HALight::BrightnessFeature | HALight::RGBFeature);

  sprintf(haAlarmAtHomeID, "%s_alarm_at_home", chipID);
  haAlarmAtHome = new HABinarySensor(haAlarmAtHomeID);

  if (climate.isTemperatureAvailable()) {
    sprintf(haLocalTempID, "%s_local_temp", chipID);
    haLocalTemp = new HASensorNumber(haLocalTempID, HASensorNumber::PrecisionP2);
  }
  if (climate.isHumidityAvailable()) {
    sprintf(haLocalHumID, "%s_local_hum", chipID);
    haLocalHum = new HASensorNumber(haLocalHumID, HASensorNumber::PrecisionP2);
  }
  if (climate.isPressureAvailable()) {
    sprintf(haLocalPressureID, "%s_local_pressure", chipID);
    haLocalPressure = new HASensorNumber(haLocalPressureID, HASensorNumber::PrecisionP2);
  }
  if (lightSensor.isLightSensorAvailable()) {
    sprintf(haLightLevelID, "%s_light_level", chipID);
    haLightLevel = new HASensorNumber(haLightLevelID, HASensorNumber::PrecisionP2);
  }
  sprintf(haHomeTempID, "%s_home_temp", chipID);
  haHomeTemp = new HASensorNumber(haHomeTempID, HASensorNumber::PrecisionP2);

  sprintf(haNightModeID, "%s_night_mode", chipID);
  haNightMode = new HASwitch(haNightModeID);

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
    playMelody(mosBeep);
    break;
  case MIN_OF_SILINCE_END:
    playMelody(uaAnthem);
    break;
  case ALERT_ON:
    playMelody(melodies[settings.melody_on_alert]);
    break;
  case ALERT_OFF:
    playMelody(melodies[settings.melody_on_alert_end]);
    break;
  case EXPLOSIONS:
    playMelody(melodies[settings.melody_on_explosion]);
    break;
  case REGULAR:
    playMelody(clockBeep);
    break;
  case SINGLE_CLICK:
    playMelody(singleClickSound);
    break;
  case LONG_CLICK:
    playMelody(longClickSound);
    break;
  }
#endif
}

bool needToPlaySound(SoundType type) {
#if BUZZER_ENABLED
  // ignore mute on alert
  if (SoundType::ALERT_ON == type && settings.sound_on_alert && settings.ignore_mute_on_alert) return true;

  // disable sounds on night mode
  if (settings.mute_sound_on_night && getNightModeType() > 0) return false;

  switch (type) {
  case START_UP:
    return settings.sound_on_startup;
  case MIN_OF_SILINCE:
    return settings.sound_on_min_of_sl;
  case MIN_OF_SILINCE_END:
    return settings.sound_on_min_of_sl;
  case ALERT_ON:
    return settings.sound_on_alert;
  case ALERT_OFF:
    return settings.sound_on_alert_end;
  case EXPLOSIONS:
    return settings.sound_on_explosion;
  case REGULAR:
    return settings.sound_on_every_hour;
  case SINGLE_CLICK:
  case LONG_CLICK:
    return settings.sound_on_button_click;
  }
#endif
  return false;
}

int getNightModeType() {
  // Night Mode activated by button
  if (nightMode) return 1;
  // Night mode activated by time
  if (settings.brightness_mode == 1 && isItNightNow()) return 2;
  // Night mode activated by sensor
  if (settings.brightness_mode == 2 && getCurrentBrightnessLevel() <= NIGHT_BRIGHTNESS_LEVEL) return 3;
  // Night mode is off
  return 0;
}

void servicePin(int pin, uint8_t status, bool force) {
  if (force || (!settings.legacy && settings.service_diodes_mode)) {
    digitalWrite(pin, status);
  }
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

void reportSettingsChange(const char* settingKey, const char* settingValue) {
  char settingsInfo[100];
  JsonDocument settings;
  settings[settingKey] = settingValue;
  sprintf(settingsInfo, "settings:%s", settings.as<String>().c_str());
  client_websocket.send(settingsInfo);
  Serial.printf("Sent settings analytics: %s\n", settingsInfo);
}

void syncTime(int8_t attempts) {
  timeClient.tick();
  if (timeClient.status() == UNIX_OK) return;
  Serial.println("Time not synced yet!");
  printNtpStatus(&timeClient);
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
  if (!shouldWifiReconnect) {
    Serial.println("Init Home assistant API");

    IPAddress brokerAddr;

    if (!brokerAddr.fromString(settings.ha_brokeraddress)) {
      Serial.println("Invalid IP-address format!");
      enableHA = false;
    } else {
      enableHA = true;
    }

    if (enableHA) {
      initHaVars();
      byte mac[6];
      WiFi.macAddress(mac);
      device.setUniqueId(mac, sizeof(mac));
      device.setName(settings.devicename);
      device.setSoftwareVersion(currentFwVersion);
      device.setManufacturer("v00g100skr");
      device.setModel(settings.devicedescription);
      sprintf(haConfigUrl, "http://%s:80", getLocalIP());
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

      if (display.isDisplayAvailable()) {
        char displayModeOptions[sizeOfCharsArray(displayModes, DISPLAY_MODE_OPTIONS_MAX) + DISPLAY_MODE_OPTIONS_MAX];
        displayModeHAMap = getHaOptions(displayModeOptions, displayModes, DISPLAY_MODE_OPTIONS_MAX, ignoreDisplayModeOptions);
        haDisplayMode->setOptions(displayModeOptions);
        haDisplayMode->onCommand(onHaDisplayModeCommand);
        haDisplayMode->setIcon("mdi:clock-digital");
        haDisplayMode->setName("Display Mode");
        haDisplayMode->setCurrentState(getLocalDisplayMode(settings.display_mode, ignoreDisplayModeOptions));

        haToggleDisplayMode->onCommand(onHaButtonClicked);
        haToggleDisplayMode->setName("Toggle Display Mode");
        haToggleDisplayMode->setIcon("mdi:card-plus");

        haShowHomeAlarmTime->onCommand(onHaShowHomeAlarmTimeCommand);
        haShowHomeAlarmTime->setIcon("mdi:timer-alert");
        haShowHomeAlarmTime->setName("Show Home Alert Time");
        haShowHomeAlarmTime->setCurrentState(settings.home_alert_time);
      }

      char autoAlarmsModeOptions[sizeOfCharsArray(autoAlarms, AUTO_ALARM_MODES_COUNT) + AUTO_ALARM_MODES_COUNT];
      getHaOptions(autoAlarmsModeOptions, autoAlarms, AUTO_ALARM_MODES_COUNT);
      haAlarmsAuto->setOptions(autoAlarmsModeOptions);
      haAlarmsAuto->onCommand(onhaAlarmsAutoCommand);
      haAlarmsAuto->setIcon("mdi:alert-outline");
      haAlarmsAuto->setName("Auto Alarm");
      haAlarmsAuto->setCurrentState(settings.alarms_auto_switch);

      haMapModeCurrent->setIcon("mdi:map");
      haMapModeCurrent->setName("Current Map Mode");

      haMapApiConnect->setIcon("mdi:server-network");
      haMapApiConnect->setName("Map API Connect");
      haMapApiConnect->setDeviceClass("connectivity");
      haMapApiConnect->setCurrentState(client_websocket.available());

      char autoBrightnessOptionsString[sizeOfCharsArray(autoBrightnessOptions, AUTO_BRIGHTNESS_OPTIONS_COUNT) + AUTO_BRIGHTNESS_OPTIONS_COUNT];
      getHaOptions(autoBrightnessOptionsString, autoBrightnessOptions, AUTO_BRIGHTNESS_OPTIONS_COUNT);
      haBrightnessAuto->setOptions(autoBrightnessOptionsString);
      haBrightnessAuto->onCommand(onHaBrightnessAutoCommand);
      haBrightnessAuto->setIcon("mdi:brightness-auto");
      haBrightnessAuto->setName("Auto Brightness");
      haBrightnessAuto->setCurrentState(settings.brightness_mode);

      haReboot->onCommand(onHaButtonClicked);
      haReboot->setName("Reboot");
      haReboot->setDeviceClass("restart");

      haToggleMapMode->onCommand(onHaButtonClicked);
      haToggleMapMode->setName("Toggle Map Mode");
      haToggleMapMode->setIcon("mdi:map-plus");

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

      haAlarmAtHome->setIcon("mdi:rocket-launch");
      haAlarmAtHome->setName("Alarm At Home");
      haAlarmAtHome->setDeviceClass("safety");
      haAlarmAtHome->setCurrentState(alarmNow);

      if (climate.isTemperatureAvailable()) {
        haLocalTemp->setIcon("mdi:thermometer");
        haLocalTemp->setName("Local Temperature");
        haLocalTemp->setUnitOfMeasurement("°C");
        haLocalTemp->setDeviceClass("temperature");
        haLocalTemp->setStateClass("measurement");
        haLocalTemp->setCurrentValue(climate.getTemperature(settings.temp_correction));
      }
      if (climate.isHumidityAvailable()) {
        haLocalHum->setIcon("mdi:water-percent");
        haLocalHum->setName("Local Humidity");
        haLocalHum->setUnitOfMeasurement("%");
        haLocalHum->setDeviceClass("humidity");
        haLocalHum->setStateClass("measurement");
        haLocalHum->setCurrentValue(climate.getHumidity(settings.hum_correction));
      }
      if (climate.isPressureAvailable()) {
        haLocalPressure->setIcon("mdi:gauge");
        haLocalPressure->setName("Local Pressure");
        haLocalPressure->setUnitOfMeasurement("mmHg");
        haLocalPressure->setDeviceClass("pressure");
        haLocalPressure->setStateClass("measurement");
        haLocalPressure->setCurrentValue(climate.getPressure(settings.pressure_correction));
      }
      if (lightSensor.isLightSensorAvailable()) {
        haLightLevel->setIcon("mdi:brightness-5");
        haLightLevel->setName("Light Level");
        haLightLevel->setUnitOfMeasurement("lx");
        haLightLevel->setDeviceClass("illuminance");
        haLightLevel->setStateClass("measurement");
        haLightLevel->setCurrentValue(lightSensor.getLightLevel(settings.light_sensor_factor));
      }

      haHomeTemp->setIcon("mdi:home-thermometer");
      haHomeTemp->setName("Home District Temperature");
      haHomeTemp->setUnitOfMeasurement("°C");
      haHomeTemp->setDeviceClass("temperature");
      haHomeTemp->setStateClass("measurement");

      haNightMode->onCommand(onHaNightModeCommand);
      haNightMode->setIcon("mdi:shield-moon-outline");
      haNightMode->setName("Night Mode");
      haNightMode->setCurrentState(nightMode);

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
  } else if (display.isDisplayAvailable() && sender == haToggleDisplayMode) {
    nextDisplayMode();
  }
}

void onHaNightModeCommand(bool state, HASwitch* sender) {
  saveHaNightMode(state);
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
  int newDisplayMode = getSettingsDisplayMode(index, ignoreDisplayModeOptions);
  saveDisplayMode(newDisplayMode);
}
#endif

int getHaDisplayMode(int localDisplayMode) {
  return displayModeHAMap[localDisplayMode];
}

void initDisplayOptions() {
  if (!display.isDisplayAvailable()) {
    // remove display related options from singl click optins list
    ignoreSingleClickOptions[0] = 2;
    ignoreSingleClickOptions[1] = 4;
    ignoreSingleClickOptions[2] = 5;
    // change single click option to default if it's not available
    if (isInArray(settings.button_mode, ignoreSingleClickOptions, SINGLE_CLICK_OPTIONS_MAX)) {
      saveInt(&settings.button_mode, "bm", 0, "button_mode");
    }

    // remove display related options from long click optins list
    ignoreLongClickOptions[0] = 2;
    ignoreLongClickOptions[1] = 4;
    ignoreLongClickOptions[2] = 5;
    // change long click option to default if it's not available
    if (isInArray(settings.button_mode_long, ignoreLongClickOptions, LONG_CLICK_OPTIONS_MAX)) {
      saveInt(&settings.button_mode_long, "bml", 0, "button_mode_long");
    }
  }
}

void updateInvertDisplayMode() {
  display.invertDisplay(settings.invert_display);
}

void updateDisplayBrightness() {
  if (!display.isDisplayAvailable()) return;
  int localDimDisplay = shouldDisplayBeOff() ? 0 : getCurrentBrightnes(0, 0, settings.dim_display_on_night ? 1 : 0, NULL);
  if (localDimDisplay == currentDimDisplay) return;
  currentDimDisplay = localDimDisplay;
  Serial.printf("Set display dim: %s\n", currentDimDisplay ? "ON" : "OFF");
  display.dim(currentDimDisplay);
}

void initDisplayModes() {
  if (!climate.isAnySensorAvailable()) {
    // remove climate sensor options from display optins list
    ignoreDisplayModeOptions[0] = 4;
    // change display mode to "changing" if it's not available
    if (isInArray(settings.display_mode, ignoreDisplayModeOptions, DISPLAY_MODE_OPTIONS_MAX)) {
      saveDisplayMode(9);
    }
  }
}
//--Init end

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
#endif

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
      // Serial.println("Dioded enabled");
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
      // Serial.println("Dioded disables");
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

  if (lastState == HIGH && currentState == LOW) { // button is pressed
    pressedTime = millis();
    isPressing = true;
    isLongDetected = false;
  } else if (lastState == LOW && currentState == HIGH) { // button is released
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
  handleClick(settings.button_mode, SINGLE_CLICK);
}

void longClick() {
#if FW_UPDATE_ENABLED
  if (settings.new_fw_notification == 1 && fwUpdateAvailable && isButtonActivated() && !isDisplayOff) {
    handleClick(100, LONG_CLICK);
    return;
  }
#endif

  handleClick(settings.button_mode_long, LONG_CLICK);
}

void handleClick(int event, SoundType soundType) {
  if (event != 0 && needToPlaySound(soundType)) playMelody(soundType);
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
      saveHaNightMode(!nightMode);
      break;
    case 7:
      rebootDevice();
      break;
    case 100:
      downloadAndUpdateFw(settings.fw_update_channel == 1 ? "latest_beta.bin" : "latest.bin", settings.fw_update_channel == 1);
      break;
    default:
      // do nothing
      break;
  }
}

bool isButtonActivated() {
  return settings.button_mode != 0 || settings.button_mode_long != 0;
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
  reportSettingsChange("map_mode", settings.map_mode);
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
  reportSettingsChange("brightness", settings.brightness);
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
  if (settings.brightness_mode == autoBrightnessMode) return false;
  settings.brightness_mode = autoBrightnessMode;
  preferences.begin("storage", false);
  preferences.putInt("bra", settings.brightness_mode);
  preferences.end();
  reportSettingsChange("brightness_mode", settings.brightness_mode);
  Serial.print("brightness_mode commited to preferences: ");
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
  reportSettingsChange("alarms_auto_switch", settings.alarms_auto_switch);
  Serial.print("alarms_auto_switch commited to preferences: ");
  Serial.println(settings.alarms_auto_switch);
#if HA_ENABLED
  if (enableHA) {
    haAlarmsAuto->setState(newMode);
  }
#endif
  return true;
}

bool saveHaNightMode(bool newState) {
  nightMode = newState;
  if (nightMode) {
    prevBrightness = settings.brightness;
  }
  showServiceMessage(nightMode ? "Увімкнено" : "Вимкнено", "Нічний режим:");
  autoBrightnessUpdate();
  mapCycle();
  reportSettingsChange("nightMode", nightMode ? "true" : "false");
  Serial.print("nightMode: ");
  Serial.println(nightMode ? "true" : "false");
#if HA_ENABLED
  if (enableHA) {
    haNightMode->setState(newState);
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
  reportSettingsChange("home_alert_time", settings.home_alert_time ? "true" : "false");
  Serial.print("home_alert_time commited to preferences: ");
  Serial.println(settings.home_alert_time ? "true" : "false");
#if HA_ENABLED
  if (enableHA && display.isDisplayAvailable()) {
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
  reportSettingsChange("ha_light_brightness", settings.ha_light_brightness);
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

bool saveHaLightRgb(RGBColor newRgb) {
  if (settings.ha_light_r == newRgb.r && settings.ha_light_g == newRgb.g && settings.ha_light_b == newRgb.b) return false;

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
  char rgbHex[8];
  sprintf(rgbHex, "#%02x%02x%02x", settings.ha_light_r, settings.ha_light_g, settings.ha_light_b);
  reportSettingsChange("ha_light_rgb", rgbHex);
#if HA_ENABLED
  if (enableHA) {
    haLight->setRGBColor(HALight::RGBColor(settings.ha_light_r, settings.ha_light_g, settings.ha_light_b));
  }
#endif
  mapCycle();
  return true;
}

void nextDisplayMode() {
  int newDisplayMode = settings.display_mode + 1;
  while (isInArray(newDisplayMode, ignoreDisplayModeOptions, DISPLAY_MODE_OPTIONS_MAX) || newDisplayMode > DISPLAY_MODE_OPTIONS_MAX - 1) {
    if (newDisplayMode > DISPLAY_MODE_OPTIONS_MAX - 1) {
      newDisplayMode = 0;
    } else {
      newDisplayMode++;
    }
  }
  if (newDisplayMode == DISPLAY_MODE_OPTIONS_MAX - 1) {
    newDisplayMode = 9;
  }

  saveDisplayMode(newDisplayMode);
}

bool saveDisplayMode(int newDisplayMode) {
  if (newDisplayMode == settings.display_mode) return false;
  settings.display_mode = newDisplayMode;
  preferences.begin("storage", false);
  preferences.putInt("dm", settings.display_mode);
  preferences.end();
  reportSettingsChange("display_mode", settings.display_mode);
  Serial.print("display_mode commited to preferences: ");
  Serial.println(settings.display_mode);
  int localDisplayMode = getLocalDisplayMode(settings.display_mode, ignoreDisplayModeOptions);
#if HA_ENABLED
  if (enableHA && display.isDisplayAvailable()) {
    haDisplayMode->setState(getHaDisplayMode(localDisplayMode));
  }
#endif
  showServiceMessage(displayModes[localDisplayMode], "Режим дисплея:", 1000);
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
  reportSettingsChange("home_district", districts[settings.home_district]);
  Serial.print("home_district commited to preferences: ");
  Serial.println(districts[settings.home_district]);
#if HA_ENABLED
  if (enableHA) {
    haHomeDistrict->setValue(districtsAlphabetical[numDistrictToAlphabet(settings.home_district)]);
    haMapModeCurrent->setValue(mapModes[getCurrentMapMode()]);
  }
#endif
  showServiceMessage(districts[settings.home_district], "Домашній регіон:", 2000);
  return true;
}

//--Display start
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
  if (alarmNow && settings.home_alert_time == 1) {
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
  // every 3 sec.
  int periodIndex = getCurrentPeriodIndex(3, 3, timeClient.second());
  showMinOfSilanceScreen(periodIndex);
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

void displayServiceMessage(ServiceMessage message) {
  displayMessage(message.message, message.title, message.textSize);
}

void showHomeAlertInfo() {
  int periodIndex = getCurrentPeriodIndex(settings.display_mode_time, 2, timeClient.second());
  char title[50];
  if (periodIndex) {
    strcpy(title, districts[settings.home_district]);
  } else {
    strcpy(title, "Тривога триває:");
  }
  char message[15];
  int position = calculateOffset(settings.home_district, offset);
  fillFromTimer(message, timeClient.unixGMT() - alarm_time[position]);

  displayMessage(message, title);
}

#if FW_UPDATE_ENABLED
void showNewFirmwareNotification() {
  int periodIndex = getCurrentPeriodIndex(settings.display_mode_time, 2, timeClient.second());
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

void showClock() {
  char time[7];
  sprintf(time, "%02d%c%02d", timeClient.hour(), getDivider(timeClient.second()), timeClient.minute());
  const char* date = timeClient.unixToString("DSTRUA DD.MM.YYYY").c_str();
  displayMessage(time, date);
}

void showTemp() {
  int position = calculateOffset(settings.home_district, offset);
  char message[10];
  sprintf(message, "%.1f%cC", weather_leds[position], (char)128);
  displayMessage(message, districts[settings.home_district]);
}

void showTechInfo() {
  int periodIndex = getCurrentPeriodIndex(settings.display_mode_time, 6, timeClient.second());
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

void showClimate() {
  int periodIndex = getCurrentPeriodIndex(settings.display_mode_time, getClimateInfoSize(), timeClient.second());
  showLocalClimateInfo(periodIndex);
}

void showLocalTemp() {
  char message[10];
  sprintf(message, "%.1f%cC", climate.getTemperature(settings.temp_correction), (char)128);
  displayMessage(message, "Температура");
}

void showLocalHum() {
  char message[10];
  sprintf(message, "%.1f%%", climate.getHumidity(settings.hum_correction));
  displayMessage(message, "Вологість");
}

void showLocalPresure() {
  char message[12];
  sprintf(message, "%.1fmmHg", climate.getPressure(settings.pressure_correction));
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
    showLocalPresure();
    return;
  }
}

int getClimateInfoSize() {
  int size = 0;
  if (climate.isTemperatureAvailable()) size++;
  if (climate.isHumidityAvailable()) size++;
  if (climate.isPressureAvailable()) size++;
  return size;
}

void showSwitchingModes() {
  int periodIndex = getCurrentPeriodIndex(settings.display_mode_time, 2 + getClimateInfoSize(), timeClient.second());
  switch (periodIndex) {
  case 0:
    // Display Mode Clock
    showClock();
    break;
  case 1:
    // Display Mode Temperature
    showTemp();
    break;
  case 2:
  case 3:
  case 4:
    showLocalClimateInfo(periodIndex - 2);
    break;
  default:
    break;
  }
}
//--Display end

//--Web server start
void setupRouting() {
  Serial.println("Init WebServer");
  webserver.on("/", HTTP_GET, handleRoot);
  webserver.on("/saveBrightness", HTTP_POST, handleSaveBrightness);
  webserver.on("/saveColors", HTTP_POST, handleSaveColors);
  webserver.on("/saveModes", HTTP_POST, handleSaveModes);
#if BUZZER_ENABLED
  webserver.on("/saveSounds", HTTP_POST, handleSaveSounds);
#endif
  webserver.on("/refreshTelemetry", HTTP_POST, handleRefreshTelemetry);
  webserver.on("/saveDev", HTTP_POST, handleSaveDev);
#if FW_UPDATE_ENABLED
  webserver.on("/saveFirmware", HTTP_POST, handleSaveFirmware);
  webserver.on("/update", HTTP_POST, handleUpdate);
#endif
#if BUZZER_ENABLED
  webserver.on("/playTestSound", HTTP_GET, handlePlayTestSound);
#endif
  webserver.begin();
  Serial.println("Webportal running");
}

int getSettingsDisplayMode(int localDisplayMode) {
  return getSettingsDisplayMode(localDisplayMode, ignoreDisplayModeOptions);
}

int checkboxIndex = 1;
int sliderIndex = 1;
int selectIndex = 1;
int inputFieldIndex = 1;

String addCheckbox(const char* name, bool isChecked, const char* label, const char* onChanges = NULL, bool disabled = false) {
  String html;
  html += "<div class='form-group form-check'>";
  html += "<input name='";
  html += name;
  html += "' type='checkbox' class='form-check-input' id='chb";
  html += checkboxIndex;
  html += "'";
  if (onChanges) {
    html += " onchange='";
    html += onChanges;
    html += "'";
  }
  if (isChecked) html += " checked";
  if (disabled) html += " disabled";
  html += "/>";
  html += label;
  html += "</div>";
  checkboxIndex++;
  return html;
}

String addSliderInt(const char* name, const char* label, int value, int min, int max, int step = 1, const char* unitOfMeasurement = "", bool disabled = false, bool needColorBox = false) {
  String html;
  html += label;
  html += ": <span id='sv";
  html += sliderIndex;
  html += "'>";
  html += value;
  html += "</span>";
  html += unitOfMeasurement;
  if (needColorBox) {
    html += "</br><div class='color-box' id='cb";
    html += sliderIndex;
    RGBColor valueColor = hue2rgb(value);
    html += "' style='background-color: rgb(";
    html += valueColor.r;
    html += ", ";
    html += valueColor.g;
    html += ", ";
    html += valueColor.b;
    html += ");'></div>";
  }
  html += "<input type='range' name='";
  html += name;
  html += "' class='form-control-range' id='s";
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
  if (needColorBox) {
    html += " oninput='window.updateColAndVal(\"cb";
    html += sliderIndex;
    html += "\", \"sv";
  } else {
    html += " oninput='window.updateVal(\"sv";
  }
  html += sliderIndex;
  html += "\", this.value);'";
  if (disabled) html += " disabled";
  html += "/>";
  html += "</br>";
  sliderIndex++;
  return html;
}

String addSliderFloat(const char* name, const char* label, float value, float min, float max, float step = 0.1, const char* unitOfMeasurement = "", bool disabled = false) {
  String html;
  html += label;
  html += ": <span id='sv";
  html += sliderIndex;
  html += "'>";
  char stringValue[10];
  sprintf(stringValue, "%.1f", value);
  html += stringValue;
  html += "</span>";
  html += unitOfMeasurement;
  html += "<input type='range' name='";
  html += name;
  html += "' class='form-control-range' id='s";
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
  html += " oninput='window.updateVal(\"sv";
  html += sliderIndex;
  html += "\", this.value);'";
  if (disabled) html += " disabled";
  html += "/>";
  html += "</br>";
  sliderIndex++;
  return html;
}

String addSelectBox(const char* name, const char* label, int setting, char* options[], int optionsCount, int (*valueTransform)(int) = NULL, bool disabled = false, int ignoreOptions[] = NULL, const char* onChanges = NULL) {
  String html;
  html += label;
  html += "<select name='";
  html += name;
  html += "' class='form-control' id='sb";
  html += selectIndex;
  html += "'";
  if (onChanges) {
    html += " onchange='";
    html += onChanges;
    html += "'";
  }
  if (disabled) html += " disabled";
  html += ">";
  for (int i = 0; i < optionsCount; i++) {
    if (ignoreOptions && isInArray(i, ignoreOptions, optionsCount)) continue;
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
  html += "</br>";
  selectIndex++;
  return html;
}

String addInputText(const char* name, const char* label, const char* type, const char* value, int maxLength = -1) {
  String html;
  html += label;
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
  html += " id='if";
  html += inputFieldIndex;
  html += "' value='";
  html += value;
  html += "'>";
  html += "</br>";
  inputFieldIndex++;
  return html;
}

template <typename V>

String addCard(const char* title, V value, const char* unitOfMeasurement = "", int size = 1, int precision = 1) {
  String html;
  html += "<div class='col-auto mb-2'>";
  html += "<div class='card' style='width: 15rem; height: 9rem;'>";
  html += "<div class='card-header d-flex'>";
  html += title;
  html += "</div>";
  html += "<div class='card-body d-flex'>";
  html += "<h";
  html += size;
  html += " class='card-title  m-auto'>";
  if (std::is_same<V, float>::value) {
    char valueStr[10];
    sprintf(valueStr, "%.*f", precision, value);
    html += valueStr;
  } else if (std::is_same<V, int>::value) {
    char valueStr[10];
    sprintf(valueStr, "%d", value);
    html += valueStr;
  } else {
    html += value;
  }
  html += unitOfMeasurement;
  html += "</h";
  html += size;
  html += ">";
  html += "</div>";
  html += "</div>";
  html += "</div>";
  return html;
}

const char JS_SCRIPT[] PROGMEM = R"=====(
<script>
const urlParams = new URLSearchParams(window.location.search);
const activePage = urlParams.get('p');
var target = '';
switch (activePage) {
    case 'brgh':
        target = 'clB';
        break;
    case 'clrs':
        target = 'clC';
        break;
    case 'mds':
        target = 'clM';
        break;
    case 'snd':
        target = 'clS';
        break;
    case 'tlmtr':
        target = 'clT';
        break;
    case 'tch':
        target = 'cTc';
        break;
    case 'fw':
        target = 'clF';
        break;
}

if (target.length > 0) {
    document.getElementById(target).classList.add('show');
    window.scrollTo(0, document.body.scrollHeight);
}

if (urlParams.get('svd') === '1') {
    const toast = document.getElementById('liveToast');
    toast.classList.remove('hide');
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
    }, 2000);
}

function playTestSound(soundId = 4) {
    var xhttp = new XMLHttpRequest();
    xhttp.open('GET', '/playTestSound/?id='.concat(soundId), true);
    xhttp.send();
}

function disableElement(targetName, disable) {
    document.getElementsByName(targetName).forEach((elem) => {
        elem.disabled = disable;
    });
}

function updateColAndVal(colorId, valueId, value) {
    updateColorBox(colorId, value);
    updateVal(valueId, value);
}

function updateVal(valueId, value) {
    document.getElementById(valueId).textContent = value;
}

function updateColorBox(boxId, hue) {
    const rgbColor = hsbToRgb(hue, 100, 100);
    document.getElementById(boxId).style.backgroundColor = `rgb(${rgbColor.r}, ${rgbColor.g}, ${rgbColor.b})`;
}

function hsbToRgb(h, s, b) {
    h /= 360;
    s /= 100;
    b /= 100;

    let r, g, bl;

    if (s === 0) {
        r = g = bl = b;
    } else {
        const i = Math.floor(h * 6);
        const f = h * 6 - i;
        const p = b * (1 - s);
        const q = b * (1 - f * s);
        const t = b * (1 - (1 - f) * s);

        switch (i % 6) {
            case 0: r = b, g = t, bl = p; break;
            case 1: r = q, g = b, bl = p; break;
            case 2: r = p, g = b, bl = t; break;
            case 3: r = p, g = q, bl = b; break;
            case 4: r = t, g = p, bl = b; break;
            case 5: r = b, g = p, bl = q; break;
        }
    }

    return {
        r: Math.round(r * 255),
        g: Math.round(g * 255),
        b: Math.round(bl * 255)
    };
}

$('select[name=brightness_auto]').change(function () {
    const selectedOption = $(this).val();
    $('input[name=brightness]').prop('disabled', selectedOption == 1 || selectedOption == 2);
    $('input[name=brightness_day]').prop('disabled', selectedOption == 0);
    $('input[name=day_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);
    $('input[name=night_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);
});

$('select[name=alarms_notify_mode]').change(function () {
    const selectedOption = $(this).val();
    $('input[name=alert_on_time]').prop('disabled', selectedOption == 0);
    $('input[name=alert_off_time]').prop('disabled', selectedOption == 0);
    $('input[name=explosion_time]').prop('disabled', selectedOption == 0);
    $('input[name=alert_blink_time]').prop('disabled', selectedOption != 2);
});
</script>
)=====";

void handleRoot(AsyncWebServerRequest* request) {
  // reset indexes
  checkboxIndex = 1;
  sliderIndex = 1;
  selectIndex = 1;
  inputFieldIndex = 1;

  String html;
  html += "<!DOCTYPE html>";
  html += "<html lang='en'>";
  html += "<head>";
  html += "<meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>";
  html += settings.devicename;
  html += "</title>";
  html += "<link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'>";
  html += "<style>";
  html += "body { background-color: #4396ff; }";
  html += ".btn {margin-bottom: 0.25rem;}";
  html += ".container { padding: 20px; }";
  html += ".color-box { width: 30px; height: 30px; display: inline-block; margin-left: 10px; border: 1px solid #ccc; vertical-align: middle; }";
  html += ".full-screen-img {width: 100%;height: 100%;object-fit: cover;}";
  html += "input, select, .color-box {margin-top: 0.5rem;}";
  html += "span {font-weight: bold;}";
  html += ".by { background-color: #fff0d5; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,.1); }";
  html += "</style>";
  html += "</head>";
  html += "<body>";
  html += "<div class='container mt-3'  id='accordion'>";
  html += "<h2 class='text-center'>";
  html += settings.devicedescription;
  html += " ";
  html += currentFwVersion;
  html += "</h2>";
  html += "<div class='row justify-content-center'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += "<img class='full-screen-img' src='http://alerts.net.ua/";
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
  html += "</div>";
  html += "</div>";
  html += "<div class='row justify-content-center'>";
  html += "<div class='by col-md-9 mt-2'>";
#if FW_UPDATE_ENABLED
  if (fwUpdateAvailable) {
    html += "<div class='alert alert-success text-center'>";
    html += "Доступна нова версія прошивки - <b>";
    html += newFwVersion;
    html += "</b></br>Для оновлення перейдіть в розділ <b><a href='/?p=fw'>Прошивка</a></b></h8>";
    html += "</div>";
  }
#endif
  html += "Локальна IP-адреса: <b>";
  html += getLocalIP();
  html += "</b>";
  if (display.isDisplayEnabled()) {
    html += "</br>Дисплей: <b>";
    if (display.isDisplayAvailable()) {
      html += display.getDisplayModel();
      html += " (128x";
      html += display.height();
      html += ")";
    } else {
      html += "Немає";
    }
    html += "</b>";
  }
  if (lightSensor.isLightSensorEnabled()) {
    html += "</br>Сенсор освітлення: <b>";
    html += lightSensor.getSensorModel();
    html += "</b>";
  }
  if (climate.isAnySensorEnabled()) {
    html += "</br>Сенсор клімату: <b>";
    html += climate.getSensorModel();
    html += "</b>";
  }
  html += "</div>";
  html += "</div>";
  html += "<div class='row justify-content-center'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += "<button class='btn btn-success' type='button' data-toggle='collapse' data-target='#clB' aria-expanded='false' aria-controls='clB'>";
  html += "Яскравість";
  html += "</button>";
  html += " <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#clC' aria-expanded='false' aria-controls='clC'>";
  html += "Кольори";
  html += "</button>";
  html += " <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#clM' aria-expanded='false' aria-controls='clM'>";
  html += "Режими";
  html += "</button>";
#if BUZZER_ENABLED
  html += " <button class='btn btn-success' type='button' data-toggle='collapse' data-target='#clS' aria-expanded='false' aria-controls='clS'>";
  html += "Звуки";
  html += "</button>";
#endif
  html += " <button class='btn btn-primary' type='button' data-toggle='collapse' data-target='#clT' aria-expanded='false' aria-controls='clT'>";
  html += "Телеметрія";
  html += "</button>";
  html += " <button class='btn btn-warning' type='button' data-toggle='collapse' data-target='#cTc' aria-expanded='false' aria-controls='cTc'>";
  html += "DEV";
  html += "</button>";
#if FW_UPDATE_ENABLED
  html += " <button class='btn btn-danger' type='button' data-toggle='collapse' data-target='#clF' aria-expanded='false' aria-controls='clF'>";
  html += "Прошивка";
  html += "</button>";
#endif
  html += "</div>";
  html += "</div>";
  html += "<form action='/saveBrightness' method='POST'>";
  html += "<div class='row collapse justify-content-center' id='clB' data-parent='#accordion'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += "<div class='alert alert-success' role='alert'>Поточний рівень яскравості: <b>";
  html += settings.map_mode == 5 ? settings.ha_light_brightness : settings.current_brightness;
  html += "%</b><br>\"Нічний режим\": <b>";
  int nightModeType = getNightModeType();
  html += nightModeType == 0 ? "Вимкнено" : nightModeType == 1 ? "Активовано кнопкою" : nightModeType == 2 ? "Активовано за часом доби" : "Активовано за даними сенсора освітлення";
  html += "</b></div>";
  html += addSliderInt("brightness", "Загальна", settings.brightness, 0, 100, 1, "%", settings.brightness_mode == 1 || settings.brightness_mode == 2);
  html += addSliderInt("brightness_day", "Денна", settings.brightness_day, 0, 100, 1, "%", settings.brightness_mode == 0);
  html += addSliderInt("brightness_night", "Нічна", settings.brightness_night, 0, 100, 1, "%");
  html += addSliderInt("day_start", "Початок дня", settings.day_start, 0, 24, 1, " година", settings.brightness_mode == 0 || settings.brightness_mode == 2);
  html += addSliderInt("night_start", "Початок ночі", settings.night_start, 0, 24, 1, " година", settings.brightness_mode == 0 || settings.brightness_mode == 2);
  if (display.isDisplayAvailable()) {
    html += addCheckbox("dim_display_on_night", settings.dim_display_on_night, "Знижувати яскравість дисплею у нічний час");
  }
  html += addSelectBox("brightness_auto", "Автоматична яскравість", settings.brightness_mode, autoBrightnessOptions, AUTO_BRIGHTNESS_OPTIONS_COUNT);
  html += addSliderInt("brightness_alert", "Області з тривогами", settings.brightness_alert, 0, 100, 1, "%");
  html += addSliderInt("brightness_clear", "Області без тривог", settings.brightness_clear, 0, 100, 1, "%");
  html += addSliderInt("brightness_new_alert", "Нові тривоги", settings.brightness_new_alert, 0, 100, 1, "%");
  html += addSliderInt("brightness_alert_over", "Відбій тривог", settings.brightness_alert_over, 0, 100, 1, "%");
  html += addSliderInt("brightness_explosion", "Вибухи", settings.brightness_explosion, 0, 100, 1, "%");
  html += addSliderFloat("light_sensor_factor", "Коефіцієнт чутливості сенсора освітлення", settings.light_sensor_factor, 0.1, 10, 0.1);
  html += "<p class='text-info'>Детальніше на <a href='https://github.com/v00g100skr/ukraine_alarm_map/wiki/%D0%A1%D0%B5%D0%BD%D1%81%D0%BE%D1%80-%D0%BE%D1%81%D0%B2%D1%96%D1%82%D0%BB%D0%B5%D0%BD%D0%BD%D1%8F'>Wiki</a>.</p>";
  html += "<button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "</div>";
  html += "</div>";
  html += "</form>";
  html += "<form action='/saveColors' method='POST'>";
  html += "<div class='row collapse justify-content-center' id='clC' data-parent='#accordion'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += addSliderInt("color_alert", "Області з тривогами", settings.color_alert, 0, 360, 1, "", false, true);
  html += addSliderInt("color_clear", "Області без тривог", settings.color_clear, 0, 360, 1, "", false, true);
  html += addSliderInt("color_new_alert", "Нові тривоги", settings.color_new_alert, 0, 360, 1, "", false, true);
  html += addSliderInt("color_alert_over", "Відбій тривог", settings.color_alert_over, 0, 360, 1, "", false, true);
  html += addSliderInt("color_explosion", "Вибухи", settings.color_explosion, 0, 360, 1, "", false, true);
  html += addSliderInt("color_home_district", "Домашній регіон", settings.color_home_district, 0, 360, 1, "", false, true);
  html += "<button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "</div>";
  html += "</div>";
  html += "</form>";
  html += "<form action='/saveModes' method='POST'>";
  html += "<div class='row collapse justify-content-center' id='clM' data-parent='#accordion'>";
  html += "<div class='by col-md-9 mt-2'>";
  if (settings.legacy) {
  html += addSelectBox("kyiv_district_mode", "Режим діода \"Київська область\"", settings.kyiv_district_mode, kyivLedModeOptions, KYIV_LED_MODE_COUNT, [](int i) -> int {return i + 1;});
  }
  html += addSelectBox("map_mode", "Режим мапи", settings.map_mode, mapModes, MAP_MODES_COUNT);
  html += addSliderInt("color_lamp", "Колір режиму \"Лампа\"", rgb2hue(settings.ha_light_r, settings.ha_light_g, settings.ha_light_b), 0, 360, 1, "", false, true);
  html += addSliderInt("brightness_lamp", "Яскравість режиму \"Лампа\"", settings.ha_light_brightness, 0, 100, 1, "%");
  if (display.isDisplayAvailable()) {
    html += addSelectBox("display_mode", "Режим дисплея", settings.display_mode, displayModes, DISPLAY_MODE_OPTIONS_MAX, getSettingsDisplayMode, false, ignoreDisplayModeOptions);
    html += addCheckbox("invert_display", settings.invert_display, "Інвертувати дисплей (темний шрифт на світлому фоні)");
    html += addSliderInt("display_mode_time", "Час перемикання дисплея", settings.display_mode_time, 1, 60, 1, " секунд");
  }
  if (climate.isTemperatureAvailable()) {
    html += addSliderFloat("temp_correction", "Корегування температури", settings.temp_correction, -10, 10, 0.1, "°C");
  }
  if (climate.isHumidityAvailable()) {
    html += addSliderFloat("hum_correction", "Корегування вологості", settings.hum_correction, -20, 20, 0.5, "%");
  }
  if (climate.isPressureAvailable()) {
    html += addSliderFloat("pressure_correction", "Корегування атмосферного тиску", settings.pressure_correction, -50, 50, 0.5, " мм.рт.ст.");
  }
  html += addSliderInt("weather_min_temp", "Нижній рівень температури (режим 'Погода')", settings.weather_min_temp, -20, 10, 1, "°C");
  html += addSliderInt("weather_max_temp", "Верхній рівень температури (режим 'Погода')", settings.weather_max_temp, 11, 40, 1, "°C");
  html += addSelectBox("button_mode", "Режим кнопки (Single Click)", settings.button_mode, singleClickOptions, SINGLE_CLICK_OPTIONS_MAX, NULL, false, ignoreSingleClickOptions);
  html += addSelectBox("button_mode_long", "Режим кнопки (Long Click)", settings.button_mode_long, longClickOptions, LONG_CLICK_OPTIONS_MAX, NULL, false, ignoreLongClickOptions);
  html += addSelectBox("home_district", "Домашній регіон", settings.home_district, districtsAlphabetical, DISTRICTS_COUNT, alphabetDistrictToNum);

  if (display.isDisplayAvailable()) {
    html += addCheckbox("home_alert_time", settings.home_alert_time, "Показувати тривалість тривоги у дом. регіоні");
  }
  html += addSelectBox("alarms_notify_mode", "Відображення на мапі нових тривог, відбою та вибухів", settings.alarms_notify_mode, alertNotifyOptions, ALERT_NOTIFY_OPTIONS_COUNT);
  html += addSliderInt("alert_on_time", "Тривалість відображення початку тривоги", settings.alert_on_time, 1, 10, 1, " хвилин", settings.alarms_notify_mode == 0);
  html += addSliderInt("alert_off_time", "Тривалість відображення відбою", settings.alert_off_time, 1, 10, 1, " хвилин", settings.alarms_notify_mode == 0);
  html += addSliderInt("explosion_time", "Тривалість відображення інформації про вибухи", settings.explosion_time, 1, 10, 1, " хвилин", settings.alarms_notify_mode == 0);
  html += addSliderInt("alert_blink_time", "Тривалість анімації зміни яскравості", settings.alert_blink_time, 1, 5, 1, " секунд", settings.alarms_notify_mode != 2);
  html += addSelectBox("alarms_auto_switch", "Перемикання мапи в режим тривоги у випадку тривоги у домашньому регіоні", settings.alarms_auto_switch, autoAlarms, AUTO_ALARM_MODES_COUNT);
  if (!settings.legacy) {
    html += addCheckbox("service_diodes_mode", settings.service_diodes_mode, "Ввімкнути сервісні діоди");
  }
  html += addCheckbox("min_of_silence", settings.min_of_silence, "Активувати режим \"Хвилина мовчання\" (щоранку о 09:00)");
  html += addSliderInt("time_zone", "Часовий пояс (зсув відносно Ґрінвіча)", settings.time_zone, -12, 12, 1, " год.");
  html += "<button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "</div>";
  html += "</div>";
  html += "</form>";
#if BUZZER_ENABLED
  html += "<form action='/saveSounds' method='POST'>";
  html += "<div class='row collapse justify-content-center' id='clS' data-parent='#accordion'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += addCheckbox("sound_on_startup", settings.sound_on_startup, "Відтворювати мелодію при старті мапи", "window.disableElement(\"melody_on_startup\", !this.checked);");
  html += addSelectBox("melody_on_startup", "Мелодія при старті мапи", settings.melody_on_startup, melodyNames, MELODIES_COUNT, NULL, settings.sound_on_startup == 0, NULL, "window.playTestSound(this.value);");
  html += addCheckbox("sound_on_min_of_sl", settings.sound_on_min_of_sl, "Відтворювати звуки під час \"Xвилини мовчання\"");
  html += addCheckbox("sound_on_alert", settings.sound_on_alert, "Звукове сповіщення при тривозі у домашньому регіоні", "window.disableElement(\"melody_on_alert\", !this.checked);");
  html += addSelectBox("melody_on_alert", "Мелодія при тривозі у домашньому регіоні", settings.melody_on_alert, melodyNames, MELODIES_COUNT, NULL, settings.sound_on_alert == 0, NULL, "window.playTestSound(this.value);");
  html += addCheckbox("sound_on_alert_end", settings.sound_on_alert_end, "Звукове сповіщення при скасуванні тривоги у домашньому регіоні", "window.disableElement(\"melody_on_alert_end\", !this.checked);");
  html += addSelectBox("melody_on_alert_end", "Мелодія при скасуванні тривоги у домашньому регіоні", settings.melody_on_alert_end, melodyNames, MELODIES_COUNT, NULL, settings.sound_on_alert_end == 0, NULL, "window.playTestSound(this.value);");
  html += addCheckbox("sound_on_explosion", settings.sound_on_explosion, "Звукове сповіщення при вибухах у домашньому регіоні", "window.disableElement(\"melody_on_explosion\", !this.checked);");
  html += addSelectBox("melody_on_explosion", "Мелодія при вибухах у домашньому регіоні", settings.melody_on_explosion, melodyNames, MELODIES_COUNT, NULL, settings.sound_on_explosion == 0, NULL, "window.playTestSound(this.value);");
  html += addCheckbox("sound_on_every_hour", settings.sound_on_every_hour, "Звукове сповіщення щогодини");
  html += addCheckbox("sound_on_button_click", settings.sound_on_button_click, "Сигнали при натисканні кнопки");
  html += addCheckbox("mute_sound_on_night", settings.mute_sound_on_night, "Вимикати всі звуки у \"Нічному режимі\"", "window.disableElement(\"ignore_mute_on_alert\", !this.checked);");
  html += addCheckbox("ignore_mute_on_alert", settings.ignore_mute_on_alert, "Сигнали тривоги навіть у \"Нічному режимі\"", NULL, settings.mute_sound_on_night == 0);
  html += "<button type='submit' class='btn btn-info' aria-expanded='false'>Зберегти налаштування</button>";
  html += "<button type='button' class='btn btn-primary float-right' onclick='playTestSound();' aria-expanded='false'>Тест динаміка</button>";
  html += "</div>";
  html += "</div>";
  html += "</form>";
#endif
  html += "<form action='/refreshTelemetry' method='POST'>";
  html += "<div class='row collapse justify-content-center' id='clT' data-parent='#accordion'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += "<div class='row justify-content-center'>";

  html += addCard("Час роботи", uptimeChar, "", 4);
  html += addCard("Температура ESP32", cpuTemp, "°C");
  html += addCard("Вільна памʼять", freeHeapSize, "кБ");
  html += addCard("Використана памʼять", usedHeapSize, "кБ");
  html += addCard("WiFi сигнал", wifiSignal, "dBm");
  html += addCard(districts[settings.home_district], weather_leds[calculateOffset(settings.home_district, offset)], "°C");
#if HA_ENABLED
  html += addCard("Home Assistant", mqtt.isConnected() ? "Підключено" : "Відключено", "", 2);
#endif
  html += addCard("Сервер тривог", client_websocket.available() ? "Підключено" : "Відключено", "", 2);
  if (climate.isTemperatureAvailable()) {
    html += addCard("Температура", climate.getTemperature(settings.temp_correction), "°C");
  }
  if (climate.isHumidityAvailable()) {
    html += addCard("Вологість", climate.getHumidity(settings.hum_correction), "%");
  }
  if (climate.isPressureAvailable()) {
    html += addCard("Тиск", climate.getPressure(settings.pressure_correction), "mmHg", 2);
  }
  if (lightSensor.isLightSensorAvailable()) {
    html += addCard("Освітленість", lightSensor.getLightLevel(settings.light_sensor_factor), "lx");
  }
  html += "</div>";
  html += "<button type='submit' class='btn btn-info mt-3'>Оновити значення</button>";
  html += "</div>";
  html += "</div>";
  html += "</form>";
  html += "<form action='/saveDev' method='POST'>";
  html += "<div class='row collapse justify-content-center' id='cTc' data-parent='#accordion'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += addSelectBox("legacy", "Режим прошивки", settings.legacy, legacyOptions, LEGACY_OPTIONS_COUNT);
  if ((settings.legacy == 1 || settings.legacy == 2) && display.isDisplayEnabled()) {
    html += addSelectBox("display_model", "Тип дисплею", settings.display_model, displayModelOptions, DISPLAY_MODEL_OPTIONS_COUNT);
    html += addSelectBox("display_height", "Розмір дисплею", settings.display_height, displayHeightOptions, DISPLAY_HEIGHT_OPTIONS_COUNT, [](int i) -> int {return i == 0 ? 32 : 64;});
  }
#if HA_ENABLED
  html += addInputText("ha_brokeraddress", "Адреса mqtt Home Assistant", "text", settings.ha_brokeraddress, 30);
  html += addInputText("ha_mqttport", "Порт mqtt Home Assistant", "number", String(settings.ha_mqttport).c_str());
  html += addInputText("ha_mqttuser", "Користувач mqtt Home Assistant", "text", settings.ha_mqttuser, 30);
  html += addInputText("ha_mqttpassword", "Пароль mqtt Home Assistant", "text", settings.ha_mqttpassword, 50);
#endif

  html += addInputText("serverhost", "Адреса сервера даних", "text", settings.serverhost, 30);
  html += addInputText("websocket_port", "Порт Websockets", "number", String(settings.websocket_port).c_str());
  html += addInputText("updateport", "Порт сервера прошивок", "number", String(settings.updateport).c_str());
  html += addInputText("devicename", "Назва пристрою", "text", settings.devicename, 30);
  html += addInputText("devicedescription", "Опис пристрою", "text", settings.devicedescription, 50);
  html += addInputText("broadcastname", ("Локальна адреса (" + String(settings.broadcastname) + ".local)").c_str(), "text", settings.broadcastname, 30);
  if (settings.legacy) {
    html += addInputText("pixelpin", "Керуючий пін лед-стрічки", "number", String(settings.pixelpin).c_str());
    html += addInputText("buttonpin", "Керуючий пін кнопки", "number", String(settings.buttonpin).c_str());
  }
  html += addInputText("alertpin", "Пін, який замкнеться при тривозі у дом. регіоні (має бути digital)", "number", String(settings.alertpin).c_str());
  html += addCheckbox("enable_pin_on_alert", settings.enable_pin_on_alert, ("Замикати пін " + String(settings.alertpin) + " при тривозі у дом. регіоні").c_str());
  html += addInputText("lightpin", "Пін фоторезистора (має бути analog)", "number", String(settings.lightpin).c_str());
#if BUZZER_ENABLED
  html += addInputText("buzzerpin", "Керуючий пін динаміка (buzzer)", "number", String(settings.buzzerpin).c_str());
#endif
  html += "<b>";
  html += "<p class='text-danger'>УВАГА: будь-яка зміна налаштування в цьому розділі призводить до примусувого перезаватаження мапи.</p>";
  html += "<p class='text-danger'>УВАГА: деякі зміни налаштувань можуть привести до відмови прoшивки, якщо налаштування будуть несумісні. Будьте впевнені, що Ви точно знаєте, що міняється і для чого.</p>";
  html += "<p class='text-danger'>У випадку, коли мапа втратить працездатність після змін, перезавантаження i втрати доступу до сторінки керування - необхідно перепрошити мапу з нуля за допомогою скетча updater.ino (або firmware.ino, якщо Ви збирали прошивку самі) з репозіторія JAAM за допомогою Arduino IDE, виставивши примусове стирання памʼяті в меню Tools -> Erase all memory before sketch upload</p>";
  html += "</b>";
  html += "<button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "</div>";
  html += "</div>";
  html += "</form>";
#if FW_UPDATE_ENABLED
  html += "<div class='row collapse justify-content-center' id='clF' data-parent='#accordion'>";
  html += "<div class='by col-md-9 mt-2'>";
  html += "<form action='/saveFirmware' method='POST'>";
  if (display.isDisplayAvailable()) html += addCheckbox("new_fw_notification", settings.new_fw_notification, "Сповіщення про нові прошивки на екрані");
  html += addSelectBox("fw_update_channel", "Канал оновлення прошивок", settings.fw_update_channel, fwUpdateChannels, FW_UPDATE_CHANNELS_COUNT);
  html += "<b><p class='text-danger'>УВАГА: BETA-прошивки можуть вивести мапу з ладу i містити помилки. Якщо у Вас немає можливості прошити мапу через кабель, будь ласка, залишайтесь на каналі PRODUCTION!</p></b>";
  html += "<button type='submit' class='btn btn-info'>Зберегти налаштування</button>";
  html += "</form>";
  html += "<form action='/update' method='POST'>";
  html += "Файл прошивки";
  html += "<select name='bin_name' class='form-control' id='sb16'>";
  const int count = settings.fw_update_channel ? testBinsCount : binsCount;
  for (int i = 0; i < count; i++) {
    String filename = String(settings.fw_update_channel ? test_bin_list[i] : bin_list[i]);
    html += "<option value='" + filename + "'";
    if (filename == "latest.bin" || filename == "latest_beta.bin") html += " selected";
    html += ">" + filename + "</option>";
  }
  html += "</select>";
  html += "</br>";
  html += "<button type='submit' class='btn btn-danger'>ОНОВИТИ ПРОШИВКУ</button>";
  html += "</form>";
  html += "</div>";
  html += "</div>";
#endif
  html += "<div class='position-fixed bottom-0 right-0 p-3' style='z-index: 5; right: 0; bottom: 0;'>";
  html += "<div id='liveToast' class='toast hide' role='alert' aria-live='assertive' aria-atomic='true' data-delay='2000'>";
  html += "<div class='toast-body'>";
  html += "💾 Налаштування збережено!";
  html += "</div>";
  html += "</div>";
  html += "</div>";
  html += "</div>";
  html += "</form>";
  html += "<script src='https://code.jquery.com/jquery-3.5.1.slim.min.js'></script>";
  html += "<script src='https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.3/dist/umd/popper.min.js'></script>";
  html += "<script src='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js'></script>";
  html += JS_SCRIPT;
  html += "</body>";
  html += "</html>";
  Serial.printf("Html size: %d\n", html.length());
  request->send(200, "text/html", html);
}

bool saveInt(AsyncWebParameter* param, int *setting, const char* settingsKey, bool (*saveFun)(int) = NULL, void (*additionalFun)(void) = NULL) {
  if (!param) return false;
  int newValue = param->value().toInt();
  if (saveFun) {
    return saveFun(newValue);
  }
  if (newValue != *setting) {
    const char* paramName = param->name().c_str();
    saveInt(setting, settingsKey, newValue, paramName);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
};

void saveInt(int *setting, const char* settingsKey, int newValue, const char* paramName) {
  preferences.begin("storage", false);
  *setting = newValue;
  preferences.putInt(settingsKey, *setting);
  preferences.end();
  reportSettingsChange(paramName, *setting);
  Serial.printf("%s commited to preferences: %d\n", paramName, *setting);
}

bool saveFloat(AsyncWebParameter* param, float *setting, const char* settingsKey, bool (*saveFun)(float) = NULL, void (*additionalFun)(void) = NULL) {
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
    reportSettingsChange(paramName, *setting);
    Serial.printf("%s commited to preferences: %.1f\n", paramName, *setting);
    if (additionalFun) {
      additionalFun();
    }
    return true;
  }
  return false;
};

bool saveBool(AsyncWebParameter* param, const char* paramName, int *setting, const char* settingsKey, bool (*saveFun)(bool) = NULL, void (*additionalFun)(void) = NULL) {
  int paramValue = param ? 1 : 0;
  if (saveFun) {
    return saveFun(paramValue);
  }
  if (paramValue != *setting) {
    preferences.begin("storage", false);
    *setting = paramValue;
    preferences.putInt(settingsKey, *setting);
    preferences.end();
    reportSettingsChange(paramName, *setting ? "true" : "false");
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
    reportSettingsChange(paramName, setting);
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
  bool saved = false;
  saved = saveInt(request->getParam("brightness", true), &settings.brightness, "brightness", saveHaBrightness) || saved;
  saved = saveInt(request->getParam("brightness_day", true), &settings.brightness_day, "brd", NULL, distributeBrightnessLevels) || saved;
  saved = saveInt(request->getParam("brightness_night", true), &settings.brightness_night, "brn", NULL, distributeBrightnessLevels) || saved;
  saved = saveInt(request->getParam("day_start", true), &settings.day_start, "ds") || saved;
  saved = saveInt(request->getParam("night_start", true), &settings.night_start, "ns") || saved;
  saved = saveInt(request->getParam("brightness_auto", true), &settings.brightness_mode, "bra", saveHaBrightnessAuto) || saved;
  saved = saveInt(request->getParam("brightness_alert", true), &settings.brightness_alert, "ba") || saved;
  saved = saveInt(request->getParam("brightness_clear", true), &settings.brightness_clear, "bc") || saved;
  saved = saveInt(request->getParam("brightness_new_alert", true), &settings.brightness_new_alert, "bna") || saved;
  saved = saveInt(request->getParam("brightness_alert_over", true), &settings.brightness_alert_over, "bao") || saved;
  saved = saveInt(request->getParam("brightness_explosion", true), &settings.brightness_explosion, "bex") || saved;
  saved = saveFloat(request->getParam("light_sensor_factor", true), &settings.light_sensor_factor, "lsf") || saved;
  saved = saveBool(request->getParam("dim_display_on_night", true), "dim_display_on_night", &settings.dim_display_on_night, "ddon", NULL, updateDisplayBrightness) || saved;
  
  if (saved) autoBrightnessUpdate();
  
  char url[15];
  sprintf(url, "/?p=brgh&svd=%d", saved);
  request->redirect(url);
}

void handleSaveColors(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveInt(request->getParam("color_alert", true), &settings.color_alert, "coloral") || saved;
  saved = saveInt(request->getParam("color_clear", true), &settings.color_clear, "colorcl") || saved;
  saved = saveInt(request->getParam("color_new_alert", true), &settings.color_new_alert, "colorna") || saved;
  saved = saveInt(request->getParam("color_alert_over", true), &settings.color_alert_over, "colorao") || saved;
  saved = saveInt(request->getParam("color_explosion", true), &settings.color_explosion, "colorex") || saved;
  saved = saveInt(request->getParam("color_home_district", true), &settings.color_home_district, "colorhd") || saved;
  
  char url[15];
  sprintf(url, "/?p=clrs&svd=%d", saved);
  request->redirect(url);
}

void handleSaveModes(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveInt(request->getParam("map_mode", true), &settings.map_mode, "mapmode", saveMapMode) || saved;
  saved = saveInt(request->getParam("brightness_lamp", true), &settings.ha_light_brightness, "ha_lbri", saveHaLightBrightness) || saved;
  saved = saveInt(request->getParam("display_mode", true), &settings.display_mode, "dm", saveDisplayMode) || saved;
  saved = saveInt(request->getParam("home_district", true), &settings.home_district, "hd", saveHomeDistrict) || saved;
  saved = saveInt(request->getParam("display_mode_time", true), &settings.display_mode_time, "dmt") || saved;
  saved = saveFloat(request->getParam("temp_correction", true), &settings.temp_correction, "ltc", NULL, climateSensorCycle) || saved;
  saved = saveFloat(request->getParam("hum_correction", true), &settings.hum_correction, "lhc", NULL, climateSensorCycle) || saved;
  saved = saveFloat(request->getParam("pressure_correction", true), &settings.pressure_correction, "lpc", NULL, climateSensorCycle) || saved;
  saved = saveInt(request->getParam("weather_min_temp", true), &settings.weather_min_temp, "mintemp") || saved;
  saved = saveInt(request->getParam("weather_max_temp", true), &settings.weather_max_temp, "maxtemp") || saved;
  saved = saveInt(request->getParam("button_mode", true), &settings.button_mode, "bm") || saved;
  saved = saveInt(request->getParam("button_mode_long", true), &settings.button_mode_long, "bml") || saved;
  saved = saveInt(request->getParam("kyiv_district_mode", true), &settings.kyiv_district_mode, "kdm") || saved;
  saved = saveBool(request->getParam("home_alert_time", true), "home_alert_time", &settings.home_alert_time, "hat", saveHaShowHomeAlarmTime) || saved;
  saved = saveInt(request->getParam("alarms_notify_mode", true), &settings.alarms_notify_mode, "anm") || saved;
  saved = saveInt(request->getParam("alert_on_time", true), &settings.alert_on_time, "aont") || saved;
  saved = saveInt(request->getParam("alert_off_time", true), &settings.alert_off_time, "aoft") || saved;
  saved = saveInt(request->getParam("explosion_time", true), &settings.explosion_time, "ext") || saved;
  saved = saveInt(request->getParam("alert_blink_time", true), &settings.alert_blink_time, "abt") || saved;
  saved = saveInt(request->getParam("alarms_auto_switch", true), &settings.alarms_auto_switch, "aas", saveHaAlarmAuto) || saved;
  saved = saveBool(request->getParam("service_diodes_mode", true), "service_diodes_mode", &settings.service_diodes_mode, "sdm", NULL, checkServicePins) || saved;
  saved = saveBool(request->getParam("min_of_silence", true), "min_of_silence", &settings.min_of_silence, "mos") || saved;
  saved = saveBool(request->getParam("invert_display", true), "invert_display", &settings.invert_display, "invd", NULL, updateInvertDisplayMode) || saved;
  saved = saveInt(request->getParam("time_zone", true), &settings.time_zone, "tz", NULL, []() {
    timeClient.setTimeZone(settings.time_zone);
  }) || saved;

  if (request->hasParam("color_lamp", true)) {
    int selectedHue = request->getParam("color_lamp", true)->value().toInt();
    RGBColor rgb = hue2rgb(selectedHue);
    saved = saveHaLightRgb(rgb) || saved;
  }

  char url[15];
  sprintf(url, "/?p=mds&svd=%d", saved);
  request->redirect(url);
}

void handleSaveSounds(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveBool(request->getParam("sound_on_startup", true), "sound_on_startup", &settings.sound_on_startup, "sos") || saved;
  saved = saveInt(request->getParam("melody_on_startup", true), &settings.melody_on_startup, "most") || saved;
  saved = saveBool(request->getParam("sound_on_min_of_sl", true), "sound_on_min_of_sl", &settings.sound_on_min_of_sl, "somos") || saved;
  saved = saveBool(request->getParam("sound_on_alert", true), "sound_on_alert", &settings.sound_on_alert, "soa") || saved;
  saved = saveInt(request->getParam("melody_on_alert", true), &settings.melody_on_alert, "moa") || saved;
  saved = saveBool(request->getParam("sound_on_alert_end", true), "sound_on_alert_end", &settings.sound_on_alert_end, "soae") || saved;
  saved = saveInt(request->getParam("melody_on_alert_end", true), &settings.melody_on_alert_end, "moae") || saved;
  saved = saveBool(request->getParam("sound_on_explosion", true), "sound_on_explosion", &settings.sound_on_explosion, "soex") || saved;
  saved = saveInt(request->getParam("melody_on_explosion", true), &settings.melody_on_explosion, "moex") || saved;
  saved = saveBool(request->getParam("sound_on_every_hour", true), "sound_on_every_hour", &settings.sound_on_every_hour, "soeh") || saved;
  saved = saveBool(request->getParam("sound_on_button_click", true), "sound_on_button_click", &settings.sound_on_button_click, "sobc") || saved;
  saved = saveBool(request->getParam("mute_sound_on_night", true), "mute_sound_on_night", &settings.mute_sound_on_night, "mson") || saved;
  saved = saveBool(request->getParam("ignore_mute_on_alert", true), "ignore_mute_on_alert", &settings.ignore_mute_on_alert, "imoa") || saved;

  char url[15];
  sprintf(url, "/?p=snd&svd=%d", saved);
  request->redirect(url);
}

void handleRefreshTelemetry(AsyncWebServerRequest* request) {
  request->redirect("/?p=tlmtr");
}

void handleSaveDev(AsyncWebServerRequest* request) {
  bool reboot = false;
  reboot = saveInt(request->getParam("legacy", true), &settings.legacy, "legacy") || reboot;
  reboot = saveInt(request->getParam("display_height", true), &settings.display_height, "dh") || reboot;
  reboot = saveInt(request->getParam("display_model", true), &settings.display_model, "dsmd") || reboot;
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
  reboot = saveBool(request->getParam("enable_pin_on_alert", true), "enable_pin_on_alert", &settings.enable_pin_on_alert, "epoa") || reboot;

  if (reboot) {
    request->redirect("/");
    rebootDevice(3000, true);
    return;
  }
  request->redirect("/?p=tch");
}
#if FW_UPDATE_ENABLED
void handleSaveFirmware(AsyncWebServerRequest* request) {
  bool saved = false;
  saved = saveBool(request->getParam("new_fw_notification", true), "new_fw_notification", &settings.new_fw_notification, "nfwn") || saved;
  saved = saveInt(request->getParam("fw_update_channel", true), &settings.fw_update_channel, "fwuc", NULL, saveLatestFirmware) || saved;

  char url[15];
  sprintf(url, "/?p=fw&svd=%d", saved);
  request->redirect(url);
}
#endif

#if BUZZER_ENABLED
void handlePlayTestSound(AsyncWebServerRequest* request) {
  int soundId = request->getParam("id", false)->value().toInt();
  playMelody(melodies[soundId]);
  showServiceMessage(melodyNames[soundId], "Мелодія");
  request->send(200, "text/plain", "Test sound played!");
}
#endif
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

#if HA_ENABLED
  if (enableHA) {
    haUptime->setValue(uptimeValue);
    haWifiSignal->setValue(wifiSignal);
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
  if (lightSensor.isLightSensorAvailable()) {
    // Digital light sensor has higher priority. BH1750 measurmant range is 0..27306 lx. 500 lx - very bright indoor environment.
    currentValue = round(lightSensor.getLightLevel(settings.light_sensor_factor));
    maxValue = 500;
  } else {
    // reads the input on analog pin (value between 0 and 4095)
    currentValue = lightSensor.getPhotoresistorValue(settings.light_sensor_factor);
    // 2600 - very bright indoor environment.
    maxValue = 2600;
  }
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
  if (settings.brightness_mode == 2) return brightnessLevels ? getBrightnessFromSensor(brightnessLevels) : getCurrentBrightnessLevel() <= NIGHT_BRIGHTNESS_LEVEL ? nightBrightness : dayBrightness;

  // if auto brightnes deactivated, return regular brightnes
  // default
  return defaultBrightness;
}

bool isItNightNow() {
  // if day and night start time is equels it means it's always day, return day
  if (settings.night_start == settings.day_start) return false;

  int currentHour = timeClient.hour();

  // handle case, when night start hour is bigger than day start hour, ex. night start at 22 and day start at 9
  if (settings.night_start > settings.day_start) return currentHour >= settings.night_start || currentHour < settings.day_start ? true : false;

  // handle case, when day start hour is bigger than night start hour, ex. night start at 1 and day start at 8
  return currentHour < settings.day_start && currentHour >= settings.night_start ? true : false;
}
//--Service messages end

//--Websocket process start
void websocketProcess() {
  if (millis() - websocketLastPingTime > settings.ws_alert_time) {
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
      for (int i = 0; i < 26; ++i) {
        alarm_leds[calculateOffset(i, offset)] = data["alerts"][i][0];
        alarm_time[calculateOffset(i, offset)] = data["alerts"][i][1];
      }
      Serial.println("Successfully parsed alerts data");
    } else if (payload == "weather") {
      for (int i = 0; i < 26; ++i) {
        weather_leds[calculateOffset(i, offset)] = data["weather"][i];
      }
      Serial.println("Successfully parsed weather data");
#if HA_ENABLED
      if (enableHA) {
        haHomeTemp->setValue(weather_leds[calculateOffset(settings.home_district, offset)]);
      }
#endif
    } else if (payload == "explosions") {
      for (int i = 0; i < 26; ++i) {
        explosions_time[calculateOffset(i, offset)] = data["explosions"][i];
      }
      Serial.println("Successfully parsed explosions data");
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
}

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
    client_websocket.send("pong");
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
  sprintf(webSocketUrl, "ws://%s:%d/data_v2", settings.serverhost, settings.websocket_port);
  Serial.println(webSocketUrl);
  client_websocket.connect(webSocketUrl);
  if (client_websocket.available()) {
    Serial.print("connection time - ");
    Serial.print(millis() - startTime);
    Serial.println("ms");
    char firmwareInfo[100];
    sprintf(firmwareInfo, "firmware:%s_%s", currentFwVersion, settings.identifier);
    Serial.println(firmwareInfo);
    client_websocket.send(firmwareInfo);

    char userInfo[250];
    JsonDocument userInfoJson;
    userInfoJson["legacy"] = settings.legacy;
    userInfoJson["kyiv_mode"] = settings.kyiv_district_mode;
    userInfoJson["display_model"] = display.getDisplayModel();
    if (display.isDisplayAvailable()) userInfoJson["display_height"] = settings.display_height;
    userInfoJson["bh1750"] = lightSensor.isLightSensorAvailable();
    userInfoJson["bme280"] = climate.isBME280Available();
    userInfoJson["bmp280"] = climate.isBMP280Available();
    userInfoJson["sht2x"] = climate.isSHT2XAvailable();
    userInfoJson["sht3x"] = climate.isSHT3XAvailable();
#if HA_ENABLED
    userInfoJson["ha"] = enableHA;
#else
    userInfoJson["ha"] = false;
#endif
    sprintf(userInfo, "user_info:%s", userInfoJson.as<String>().c_str());
    Serial.println(userInfo);
    client_websocket.send(userInfo);
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

HsbColor processAlarms(int led, long time, int expTime, int position, float alertBrightness, float explosionBrightness) {
  HsbColor hue;
  int local_color;
  float local_brightness_alert = settings.brightness_alert / 100.0f;
  float local_brightness_clear = settings.brightness_clear / 100.0f;
  float local_brightness_new_alert = settings.brightness_new_alert / 100.0f;
  float local_brightness_alert_over = settings.brightness_alert_over / 100.0f;
  float local_brightness_explosion = settings.brightness_explosion / 100.0f;

  int local_district = calculateOffsetDistrict(settings.kyiv_district_mode, settings.home_district, offset);
  int color_switch;

  // explosions has highest priority
  if (expTime > 0 && timeClient.unixGMT() - expTime < settings.explosion_time * 60 && settings.alarms_notify_mode > 0) {
    color_switch = settings.color_explosion;
    hue = HsbColor(color_switch / 360.0f, 1.0, explosionBrightness * local_brightness_explosion);
    return hue;
  }

  switch (led) {
    case 0:
      if (timeClient.unixGMT() - time < settings.alert_off_time * 60 && settings.alarms_notify_mode > 0) {
        color_switch = settings.color_alert_over;
        hue = HsbColor(color_switch / 360.0f, 1.0, alertBrightness * local_brightness_alert_over);
      } else {
        if (position == local_district) {
          color_switch = settings.color_home_district;
        } else {
          color_switch = settings.color_clear;
        }
        hue = HsbColor(color_switch / 360.0f, 1.0, settings.current_brightness * local_brightness_clear / 200.0f);
      }
      break;
    case 1:
      if (timeClient.unixGMT() - time < settings.alert_on_time * 60 && settings.alarms_notify_mode > 0) {
        color_switch = settings.color_new_alert;
        hue = HsbColor(color_switch / 360.0f, 1.0, alertBrightness * local_brightness_new_alert);
      } else {
        color_switch = settings.color_alert;
        hue = HsbColor(color_switch / 360.0f, 1.0, settings.current_brightness * local_brightness_alert / 200.0f);
      }
      break;
  }
  return hue;
}

float getFadeInFadeOutBrightness(float maxBrightness, long fadeTime) {
  float minBrightness = maxBrightness * 0.01f;
  int progress = micros() % (fadeTime * 1000);
  int halfBlinkTime = fadeTime * 500;
  float blinkBrightness;
  if (progress < halfBlinkTime) {
    blinkBrightness = mapf(progress, 0, halfBlinkTime, minBrightness, maxBrightness);
  } else {
    blinkBrightness = mapf(progress, halfBlinkTime + 1, halfBlinkTime * 2, maxBrightness, minBrightness);
  }
  return blinkBrightness;
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
    // play mos beep every 2 sec during min of silence
    if (minuteOfSilence && needToPlaySound(MIN_OF_SILINCE)) {
      clockBeepInterval = asyncEngine.setInterval(playMinOfSilenceSound, 2000); // every 2 sec
    }
    // turn off mos beep
    if (!minuteOfSilence && clockBeepInterval >= 0) {
      asyncEngine.clearInterval(clockBeepInterval);
    }
#if BUZZER_ENABLED
    // play UA Anthem when min of silence ends
    if (!minuteOfSilence && needToPlaySound(MIN_OF_SILINCE_END)) {
      playMelody(MIN_OF_SILINCE_END);
      uaAnthemPlaying = true;
    }
#endif
  }
}

void playMinOfSilenceSound() {
  playMelody(MIN_OF_SILINCE);
}

int processWeather(float temp) {
  float minTemp = settings.weather_min_temp;
  float maxTemp = settings.weather_max_temp;
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

void mapReconnect() {
  float localBrightness = getFadeInFadeOutBrightness(settings.current_brightness / 200.0f, settings.alert_blink_time * 1000);
  HsbColor hue = HsbColor(64 / 360.0f, 1.0, localBrightness);
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, hue);
  }
  strip->Show();
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
    case 1000:
      mapReconnect();
      break;
  }
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
  uint8_t adapted_alarm_leds[26];
  long adapted_alarm_timers[26];
  long adapted_explosion_timers[26];
  adaptLeds(settings.kyiv_district_mode, alarm_leds, adapted_alarm_leds, strip->PixelCount(), offset);
  adaptLeds(settings.kyiv_district_mode, alarm_time, adapted_alarm_timers, strip->PixelCount(), offset);
  adaptLeds(settings.kyiv_district_mode, explosions_time, adapted_explosion_timers, strip->PixelCount(), offset);
  if (settings.kyiv_district_mode == 4) {
    if (alarm_leds[25] == 0 and alarm_leds[7] == 0) {
      adapted_alarm_leds[7] = 0;
      adapted_alarm_timers[7] = max(alarm_time[25], alarm_time[7]);
    }
    if (alarm_leds[25] == 1 or alarm_leds[7] == 1) {
      adapted_alarm_leds[7] = 1;
      adapted_alarm_timers[7] = max(alarm_time[25], alarm_time[7]);
    }
    adapted_explosion_timers[7] = max(explosions_time[25], explosions_time[7]);
  }
  float blinkBrightness = settings.current_brightness / 200.0f;
  float explosionBrightness = settings.current_brightness / 200.0f;
  if (settings.alarms_notify_mode == 2) {
    blinkBrightness = getFadeInFadeOutBrightness(blinkBrightness, settings.alert_blink_time * 1000);
    explosionBrightness = getFadeInFadeOutBrightness(explosionBrightness, settings.alert_blink_time * 500);
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, processAlarms(adapted_alarm_leds[i], adapted_alarm_timers[i], adapted_explosion_timers[i], i, blinkBrightness, explosionBrightness));
  }
  strip->Show();
}

void mapWeather() {
  float adapted_weather_leds[26];
  adaptLeds(settings.kyiv_district_mode, weather_leds, adapted_weather_leds, strip->PixelCount(), offset);
  if (settings.kyiv_district_mode == 4) {
    adapted_weather_leds[7] = (weather_leds[25] + weather_leds[7]) / 2.0f;
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, HslColor(processWeather(adapted_weather_leds[i]) / 360.0f, 1.0, settings.current_brightness / 400.0f));
  }
  strip->Show();
}

void mapFlag() {
  uint8_t adapted_flag_leds[26];
  adaptLeds(settings.kyiv_district_mode, flag_leds, adapted_flag_leds, strip->PixelCount(), offset);
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
  if (minuteOfSilence || uaAnthemPlaying) return 3; // ua flag

  int currentMapMode = isMapOff ? 0 : settings.map_mode;
  int position = settings.home_district;
  switch (settings.alarms_auto_switch) {
    case 1:
      for (int j = 0; j < counters[position]; j++) {
        int alarm_led_id = calculateOffset(neighboring_districts[position][j], offset);
        if (alarm_leds[alarm_led_id] != 0) {
          currentMapMode = 1;
        }
      }
      break;
    case 2:
      if (alarm_leds[calculateOffset(position, offset)] != 0) {
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

void wifiReconnect() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFI Reconnect");
    shouldWifiReconnect = true;
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
  // update service message expiration
  if (display.isDisplayAvailable()) serviceMessageUpdate();
}

void checkHomeDistrictAlerts() {
  int ledStatus = alarm_leds[calculateOffset(settings.home_district, offset)];
  int localHomeExplosions = explosions_time[calculateOffset(settings.home_district, offset)];
  bool localAlarmNow = ledStatus == 1;
  if (localAlarmNow != alarmNow) {
    alarmNow = localAlarmNow;
    if (alarmNow && needToPlaySound(ALERT_ON)) playMelody(ALERT_ON); 
    if (!alarmNow && needToPlaySound(ALERT_OFF)) playMelody(ALERT_OFF);

    alertPinCycle();

    if (alarmNow) {
      showServiceMessage("Тривога!", districts[settings.home_district], 5000);
    } else {
      showServiceMessage("Відбій!", districts[settings.home_district], 5000);
    }
#if HA_ENABLED
    if (enableHA) {
      haAlarmAtHome->setState(alarmNow);
    }
#endif
  }
  if (localHomeExplosions != homeExplosionTime) {
    homeExplosionTime = localHomeExplosions;
    if (homeExplosionTime > 0 && timeClient.unixGMT() - homeExplosionTime < settings.explosion_time * 60 && settings.alarms_notify_mode > 0) {
      showServiceMessage("Вибухи!", districts[settings.home_district], 5000);
      if (needToPlaySound(EXPLOSIONS)) playMelody(EXPLOSIONS);
    }
  }
}

void checkCurrentTimeAndPlaySound() {
  if (needToPlaySound(REGULAR) && beepHour != timeClient.hour() && timeClient.minute() == 0 && timeClient.second() == 0) {
    beepHour = timeClient.hour();
    playMelody(REGULAR);
  }
}

void lightSensorCycle() {
  lightSensor.read();
  updateHaLightSensors();
}

void updateHaTempSensors() {
#if HA_ENABLED
  if (enableHA && climate.isTemperatureAvailable()) {
    haLocalTemp->setValue(climate.getTemperature(settings.temp_correction));
  }
#endif
}

void updateHaHumSensors() {
#if HA_ENABLED
  if (enableHA && climate.isHumidityAvailable()) {
    haLocalHum->setValue(climate.getHumidity(settings.hum_correction));
  }
#endif
}

void updateHaPressureSensors() {
#if HA_ENABLED
  if (enableHA && climate.isPressureAvailable()) {
      haLocalPressure->setValue(climate.getPressure(settings.pressure_correction));
  }
#endif
}

void updateHaLightSensors() {
#if HA_ENABLED
  if (enableHA && lightSensor.isLightSensorAvailable()) {
    haLightLevel->setValue(lightSensor.getLightLevel(settings.light_sensor_factor));
  }
#endif
}

void climateSensorCycle() {
  if (!climate.isAnySensorAvailable()) return;
  climate.read();
  updateHaTempSensors();
  updateHaHumSensors();
  updateHaPressureSensors();
}

void setup() {
  Serial.begin(115200);

  initChipID();
  initSettings();
  initLegacy();
  initBuzzer();
  InitAlertPin();
  initStrip();
  initDisplay();
  initSensors();
  initWifi();
  initTime();

  asyncEngine.setInterval(uptime, 5000);
  asyncEngine.setInterval(connectStatuses, 60000);
  asyncEngine.setInterval(mapCycle, 1000);
  asyncEngine.setInterval(displayCycle, 100);
  asyncEngine.setInterval(wifiReconnect, 1000);
  asyncEngine.setInterval(autoBrightnessUpdate, 1000);
  asyncEngine.setInterval(doUpdate, 1000);
  asyncEngine.setInterval(websocketProcess, 3000);
  asyncEngine.setInterval(alertPinCycle, 1000);
  asyncEngine.setInterval(rebootCycle, 500);
  asyncEngine.setInterval(lightSensorCycle, 2000);
  asyncEngine.setInterval(climateSensorCycle, 5000);
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
  if (getCurrentMapMode() == 1 && settings.alarms_notify_mode == 2) {
    mapCycle();
  }
}
