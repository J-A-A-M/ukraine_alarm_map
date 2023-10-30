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


struct Settings{
  char*   apssid                = "AlarmMap";
  char*   appassword            = "";
  char*   softwareversion       = "3.1";
  String  broadcastname         = "alarmmap";
  String  devicename            = "Alarm Map";
  String  devicedescription     = "Alarm Map Informer";
  char*   tcphost               = "alerts.net.ua";
  int     tcpport               = 12345;
  int     pixelcount            = 26;
  int     buttontime            = 100;

  // ------- web config start
  int     legacy                 = 1;
  int     pixelpin               = 13;
  int     buttonpin              = 35;
  int     ha_mqttport            = 1883;
  String  ha_mqttuser            = "";
  String  ha_mqttpassword        = "";
  String  ha_brokeraddress       = "";
  int     brightness             = 50;
  int     brightness_day         = 50;
  int     brightness_night       = 5;
  int     brightness_auto        = 0;
  int     color_alert            = 0;
  int     color_clear            = 120;
  int     color_new_alert        = 20;
  int     color_alert_over       = 100;
  int     brightness_alert       = 100;
  int     brightness_clear       = 100;
  int     brightness_new_alert   = 100;
  int     brightness_alert_over  = 100;
  int     weather_min_temp       = 5;
  int     weather_max_temp       = 30;
  int     alarms_auto_switch     = 1;
  int     home_district          = 7;
  int     kyiv_district_mode     = 1;
  int     map_mode               = 1;
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

Preferences       preferences;
WiFiManager       wm;
WiFiClient        client;
WiFiClient        client_tcp;
WiFiUDP           ntpUDP;
AsyncWebServer    webserver(80);
NTPClient         timeClient(ntpUDP, "ua.pool.ntp.org");
Async             asyncEngine = Async(20);
Adafruit_SSD1306  display(settings.display_width, settings.display_height, &Wire, -1);

NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod>* strip;

int     alarm_leds[26];
double  weather_leds[26];
int     flag_leds[26] = {
  60,60,60,180,180,60,60,60,60,60,60,
  60,180,180,180,180,180,180,
  180,180,180,60,60,60,60,180
};
int     legacy_flag_leds[26] = {
  60,60,60,180,180,180,180,180,180,
  180,180,180,60,60,60,60,60,60,60,
  180,180,60,60,60,60,180
};


int d0[]  = {0,1,3};
int d1[]  = {1,0,2,3,24};
int d2[]  = {2,1,3,4,5,23,24};
int d3[]  = {3,0,1,2,4};
int d4[]  = {4,2,3,5};
int d5[]  = {5,2,3,4,6,23};
int d6[]  = {6,5,7,22,23,25};
int d7[]  = {7,6,8,19,20,22,25};
int d8[]  = {8,7,9,19,20};
int d9[]  = {9,8,10,19};
int d10[] = {10,9,12,18,19};
int d11[] = {11,10,12};
int d12[] = {12,10,13,18};
int d13[] = {13,12,14,18};
int d14[] = {14,13,17,18};
int d15[] = {15,14};
int d16[] = {16,17,20,21,22};
int d17[] = {17,14,16,18,21};
int d18[] = {18,10,12,13,14,17,19,21};
int d19[] = {19,7,8,9,10,18,20,21,25};
int d20[] = {20,7,8,19,21,22,25};
int d21[] = {21,16,17,18,19,20,22};
int d22[] = {22,6,7,16,20,21,23,24,25};
int d23[] = {23,2,5,6,22,24};
int d24[] = {24,1,2,22,23};
int d25[] = {25,6,7,8,19,20,22};


int counters[] = {3,5,7,5,4,6,6,6,5,4,5,3,4,4,4,2,5,5,8,8,7,7,9,6,5,7};

int* neighboring_districts[] = {
  d0,d1,d2,d3,d4,d5,d6,d7,d8,d9,
  d10,d11,d12,d13,d14,d15,d16,d17,d18,d19,
  d20,d21,d22,d23,d24,d25
};


const unsigned char trident_small [] PROGMEM = {
	0x04, 0x00, 0x80, 0x10, 0x06, 0x01, 0xc0, 0x30, 0x07, 0x01, 0xc0, 0x70, 0x07, 0x81, 0xc0, 0xf0,
	0x07, 0xc1, 0xc1, 0xf0, 0x06, 0xc1, 0xc1, 0xb0, 0x06, 0xe1, 0xc3, 0xb0, 0x06, 0x61, 0xc3, 0x30,
	0x06, 0x71, 0xc7, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30,
	0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0xf1, 0xc7, 0xb0, 0x07, 0xe1, 0xc3, 0xf0,
	0x07, 0x83, 0xe0, 0xf0, 0x07, 0x03, 0x60, 0x70, 0x07, 0x87, 0x70, 0xf0, 0x07, 0xc6, 0x31, 0xf0,
	0x06, 0xee, 0x3b, 0xb0, 0x06, 0x7f, 0x7f, 0x30, 0x06, 0x3d, 0xde, 0x30, 0x06, 0x19, 0xcc, 0x30,
	0x07, 0xff, 0xff, 0xf0, 0x03, 0xff, 0xff, 0xe0, 0x01, 0xfc, 0x9f, 0xc0, 0x00, 0x0c, 0xd8, 0x00,
	0x00, 0x07, 0xf0, 0x00, 0x00, 0x03, 0xe0, 0x00, 0x00, 0x01, 0xc0, 0x00, 0x00, 0x00, 0x80, 0x00
};

//byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x38, 0x4A};
byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x00, 0x4A}; //big
//byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x10, 0x4A}; //small

bool    enableHA;
bool    wifiReconnect = false;
bool    tcpReconnect = false;
bool    blink = false;
bool    isDaylightSaving = false;
bool    isDay;
bool    isPressed = true;
int     mapMode;
int     displayMode;
long    buttonPressStart = 0;
time_t  displayOldTime = 0;
time_t  tcpLastPingTime = 0;
int     offset = 9;



String haUptimeString         = settings.broadcastname + "_uptime";
String haWifiSignalString     = settings.broadcastname + "_wifi_signal";
String haFreeMemoryString     = settings.broadcastname + "_free_memory";
String haUsedMemoryString     = settings.broadcastname + "_used_memory";
String haBrightnessString     = settings.broadcastname + "_brightness";
String haMapModeString        = settings.broadcastname + "_map_mode";
String haDisplayModeString    = settings.broadcastname + "_display_mode";
String haMapModeCurrentString = settings.broadcastname + "_map_mode_current";
String haMapApiConnectString  = settings.broadcastname + "_map_api_connect";
String haBrightnessAutoString = settings.broadcastname + "_brightness_auto";
String haAlarmsAutoString     = settings.broadcastname + "_alarms_auto";


const char* haUptimeChar          = haUptimeString.c_str();
const char* haWifiSignalChar      = haWifiSignalString.c_str();
const char* haFreeMemoryChar      = haFreeMemoryString.c_str();
const char* haUsedMemoryChar      = haUsedMemoryString.c_str();
const char* haBrightnessChar      = haBrightnessString.c_str();
const char* haMapModeChar         = haMapModeString.c_str();
const char* haDisplayModeChar     = haDisplayModeString.c_str();
const char* haMapModeCurrentChar  = haMapModeCurrentString.c_str();
const char* haMapApiConnectChar   = haMapApiConnectString.c_str();
const char* haBrightnessAutoChar  = haBrightnessAutoString.c_str();
const char* haAlarmsAutoChar      = haAlarmsAutoString.c_str();


HADevice        device(mac, sizeof(mac));
HAMqtt          mqtt(client, device, 12);
HASensorNumber  haUptime(haUptimeChar);
HASensorNumber  haWifiSignal(haWifiSignalChar);
HASensorNumber  haFreeMemory(haFreeMemoryChar);
HASensorNumber  haUsedMemory(haUsedMemoryChar);
HANumber        haBrightness(haBrightnessChar);
HASelect        haMapMode(haMapModeChar);
HASelect        haDisplayMode(haDisplayModeChar);
HASensor        haMapModeCurrent(haMapModeCurrentChar);
HABinarySensor  haMapApiConnect(haMapApiConnectChar);
HASwitch        haBrightnessAuto(haBrightnessAutoChar);
HASwitch        haAlarmsAuto(haAlarmsAutoChar);

char* mapModes [] = {
  "Вимкнено",
  "Tpивoгa",
  "Погода",
  "Прапор"
};

//--Init start
void initLegacy(){
  if (settings.legacy) {
    offset = 0;
    for (int i = 0; i < 26; i++) {
      flag_leds[i] = legacy_flag_leds[i];
    }
  }else{
    settings.kyiv_district_mode = 3;
  }
}

void initSettings(){
  Serial.println("Init settings");
  preferences.begin("storage", false);
  settings.legacy                 = preferences.getInt("legacy", settings.legacy);
  settings.brightness             = preferences.getInt("brightness", settings.brightness);
  settings.brightness_day         = preferences.getInt("brd", settings.brightness_day);
  settings.brightness_night       = preferences.getInt("brn", settings.brightness_night);
  settings.brightness_auto        = preferences.getInt("bra", settings.brightness_auto);
  settings.color_alert            = preferences.getInt("coloral", settings.color_alert);
  settings.color_clear            = preferences.getInt("colorcl", settings.color_clear);
  settings.color_new_alert        = preferences.getInt("colorna", settings.color_new_alert);
  settings.color_alert_over       = preferences.getInt("colorao", settings.color_alert_over);
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
  preferences.end();
  mapMode                         = settings.map_mode;
  displayMode                     = settings.display_mode;
}

void initStrip(){
  Serial.print("pixelpin: ");
  Serial.println(settings.pixelpin);
  strip = new NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod>(settings.pixelcount, settings.pixelpin);
  //NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod> strip();
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

void timezoneUpdate(){
  timeClient.update();

  time_t rawTime = timeClient.getEpochTime();
  struct tm *timeInfo;
  timeInfo = localtime(&rawTime);

  int year = 1900 + timeInfo->tm_year;
  int month = 1 + timeInfo->tm_mon;
  int day = timeInfo->tm_mday;
  int hour = timeInfo->tm_hour;
  int minite = timeInfo->tm_min;
  int second = timeInfo->tm_sec;

  Serial.print("Current date and time: ");
  Serial.print(1900 + timeInfo->tm_year);
  Serial.print("-");
  Serial.print(1 + timeInfo->tm_mon);
  Serial.print("-");
  Serial.print(timeInfo->tm_mday);
  Serial.print(" ");
  Serial.print(timeInfo->tm_hour);
  Serial.print(":");
  Serial.print(timeInfo->tm_min);
  Serial.print(":");
  Serial.println(timeInfo->tm_sec);
  Serial.print("isDay: ");
  Serial.println(isDay);

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
    timeClient.setTimeOffset(10800);
  }
  else {
    timeClient.setTimeOffset(7200);
  }
}

int getLastSunday(int year,int month) {
  for (int day = 31; day >= 25; day--) {
    int h = (day + (13 * (month + 1)) / 5 + year + year / 4 - year / 100 + year / 400) % 7;
    if (h == 1) {
      return day;
    }
  }
}

void initWifi() {
    Serial.println("Init Wifi");
    WiFi.mode(WIFI_STA); // explicitly set mode, esp defaults to STA+AP
    //reset settings - wipe credentials for testing
    //wm.resetSettings();

    wm.setHostname(settings.broadcastname);
    wm.setTitle(settings.devicename);
    wm.setConfigPortalBlocking(true);
    wm.setConfigPortalTimeout(120);
    wm.setConnectTimeout(3);
    wm.setConnectRetries(10);
    display.clearDisplay();
    DisplayCenter(utf8cyr("Пiдключення WIFI.."),0,1);
    if(wm.autoConnect(settings.apssid, settings.appassword)){
        Serial.println("connected...yeey :)");
        display.clearDisplay();
        DisplayCenter(utf8cyr("WIFI пiдключeнo!"),0,1);
        wm.setHttpPort(8080);
        wm.startWebPortal();
        delay(5000);
        setupRouting();
        initHA();
        ArduinoOTA.begin();
        initBroadcast();
        tcpConnect();
    }
    else {
        Serial.println("Reboot");
        display.clearDisplay();
        DisplayCenter(utf8cyr("Пepeзaвaнтaжeння"),0,1);
        delay(5000);
        ESP.restart();
    }
}

void initBroadcast() {
  Serial.println("Init network device broadcast");

  if (!MDNS.begin(settings.broadcastname)) {
    Serial.println("Error setting up mDNS responder");
    display.clearDisplay();
    DisplayCenter(utf8cyr("Помилка mDNS"),0,1);
    while (1) {
      delay(1000);
    }
  }
  Serial.println("Device broadcasted to network: " + settings.broadcastname + ".local");
}

void initHA() {
  if (!wifiReconnect){
    Serial.println("Init Home assistant API");
    // String  brokerAddress_s      = settings.ha_brokeraddress;
    // int     mqttPort             = settings.ha_mqttport;
    // String  mqttUser_s           = settings.ha_mqttuser;
    // String  mqttPassword_s       = settings.ha_mqttpassword;


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
      Serial.println("Invalid IP address format!");
      enableHA = false;
    } else{
      enableHA = true;
    }

    if (enableHA) {
      device.setName(deviceName);
      device.setSoftwareVersion(settings.softwareversion);
      device.setManufacturer("v00g100skr");
      device.setModel(deviceDescr);
      device.enableSharedAvailability();

      haUptime.setIcon("mdi:timer-outline");
      haUptime.setName(haUptimeChar);
      haUptime.setUnitOfMeasurement("s");
      haUptime.setDeviceClass("duration");

      haWifiSignal.setIcon("mdi:wifi");
      haWifiSignal.setName(haWifiSignalChar);
      haWifiSignal.setUnitOfMeasurement("dBm");
      haWifiSignal.setDeviceClass("signal_strength");

      haFreeMemory.setIcon("mdi:memory");
      haFreeMemory.setName(haFreeMemoryChar);
      haFreeMemory.setUnitOfMeasurement("kB");
      haFreeMemory.setDeviceClass("data_size");

      haUsedMemory.setIcon("mdi:memory");
      haUsedMemory.setName(haUsedMemoryChar);
      haUsedMemory.setUnitOfMeasurement("kB");
      haUsedMemory.setDeviceClass("data_size");

      haBrightness.onCommand(onHaBrightnessCommand);
      haBrightness.setIcon("mdi:percent-circle");
      haBrightness.setName(haBrightnessChar);
      haBrightness.setCurrentState(settings.brightness);

      haMapMode.setOptions("Вимкнено;Тривога;Погода;Прапор");
      haMapMode.onCommand(onHaMapModeCommand);
      haMapMode.setIcon("mdi:map");
      haMapMode.setName(haMapModeChar);
      haMapMode.setCurrentState(settings.map_mode);

      haDisplayMode.setOptions("Вимкнено;Час;Погода;---;---;---;---;---;---;Перемикання");
      haDisplayMode.onCommand(onHaDisplayModeCommand);
      haDisplayMode.setIcon("mdi:clock-digital");
      haDisplayMode.setName(haDisplayModeChar);
      haDisplayMode.setCurrentState(settings.display_mode);

      haMapModeCurrent.setIcon("mdi:map");
      haMapModeCurrent.setName(haMapModeCurrentChar);
      haMapModeCurrent.setValue(mapModes[mapMode]);

      haMapApiConnect.setName(haMapApiConnectChar);
      haMapApiConnect.setDeviceClass("connectivity");
      haMapApiConnect.setCurrentState(false);

      haBrightnessAuto.onCommand(onhaBrightnessAutoCommand);
      haBrightnessAuto.setIcon("mdi:percent-circle-outline");
      haBrightnessAuto.setName(haBrightnessAutoChar);
      haBrightnessAuto.setCurrentState(settings.brightness_auto);

      haAlarmsAuto.onCommand(onhaAlarmsAutoCommand);
      haAlarmsAuto.setIcon("mdi:alert-outline");
      haAlarmsAuto.setName(haAlarmsAutoChar);
      haAlarmsAuto.setCurrentState(settings.alarms_auto_switch);

      device.enableLastWill();
      mqtt.begin(brokerAddr,settings.ha_mqttport,mqttUser,mqttPassword);
      Serial.print("Home Assistant MQTT connected: ");
      Serial.println(mqtt.isConnected());
    }
  }
}

void onhaBrightnessAutoCommand(bool state, HASwitch* sender)
{
    settings.brightness_auto = state;
    preferences.begin("storage", false);
    preferences.putInt("bra", settings.brightness_auto);
    preferences.end();
    Serial.println("brightness_auto commited to preferences");
    Serial.print("brightness_auto: ");
    Serial.println(settings.brightness_auto);
    sender->setState(state); // report state back to the Home Assistant
}

void onHaBrightnessCommand(HANumeric haBrightness, HANumber* sender)
{
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

void onhaAlarmsAutoCommand(bool state, HASwitch* sender)
{
    settings.alarms_auto_switch = state;
    preferences.begin("storage", false);
    preferences.putInt("aas", settings.alarms_auto_switch);
    preferences.end();
    Serial.println("alarms_auto_switch commited to preferences");
    Serial.print("alarms_auto_switch: ");
    Serial.println(settings.alarms_auto_switch);
    sender->setState(state); // report state back to the Home Assistant
}

void onHaMapModeCommand(int8_t index, HASelect* sender)
{
    switch (index) {
    case 0:
        settings.map_mode = 0;
        break;
    case 1:
        settings.map_mode = 1;
        break;
    case 2:
        settings.map_mode = 2;
        break;
    case 3:
        settings.map_mode = 3;
        break;
    default:
        return;
    }
    preferences.begin("storage", false);
    preferences.putInt("mapmode", settings.map_mode);
    preferences.end();
    Serial.println("map_mode commited to preferences");
    sender->setState(index);
}

void onHaDisplayModeCommand(int8_t index, HASelect* sender)
{
    switch (index) {
    case 0:
        settings.display_mode = 0;
        break;
    case 1:
        settings.display_mode = 1;
        break;
    case 2:
        settings.display_mode = 2;
        break;
    case 9:
        settings.display_mode = 9;
        break;
    default:
        return;
    }
    preferences.begin("storage", false);
    preferences.putInt("dm", settings.display_mode);
    preferences.end();
    displayMode = settings.display_mode;
    Serial.println("display_mode commited to preferences");
    sender->setState(index);
}

void initDisplay() {

  display = Adafruit_SSD1306(settings.display_width, settings.display_height, &Wire, -1);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.display();
  display.clearDisplay();
  display.setTextColor(WHITE);
  int16_t centerX = (settings.display_width - 32) / 2;    // Calculate the X coordinate
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

//--Button start
void buttonUpdate() {
  if (digitalRead(settings.buttonpin) == HIGH) {
    buttonPressStart = millis();
    if (!isPressed){
      Serial.println("Pressed");
      Serial.print("button_mode: ");
      Serial.println(settings.button_mode);
      isPressed = true;
      if (settings.button_mode == 1){
        mapModeSwitch();
      }
      if (settings.button_mode == 2){
        displayModeSwitch();
      }
    }
  }
  if (millis() - buttonPressStart > settings.buttontime){
    isPressed = false;
  }
}

void mapModeSwitch() {
  if (mapMode == settings.map_mode){
    settings.map_mode += 1;
    if (settings.map_mode > 3) {
      settings.map_mode = 0;
    }
  }else{
    settings.map_mode = 2;
  }
  settings.alarms_auto_switch = 0;

  Serial.print("map_mode: ");
  Serial.println(settings.map_mode);
  preferences.begin("storage", false);
  preferences.putInt("mapmode", settings.map_mode);
  preferences.putInt("aas", settings.alarms_auto_switch);
  preferences.end();
  if (enableHA) {
    haMapMode.setState(settings.map_mode);
    haAlarmsAuto.setState(false);
  }
  //touchModeDisplay(utf8cyr("Режим мапи:"), utf8cyr(mapModes[mapModeInit-1]));
}

void displayModeSwitch() {
  settings.display_mode += 1;
  if (settings.display_mode > 2) {
    settings.display_mode = 0;
  }
  Serial.print("display_mode: ");
  Serial.println(settings.display_mode);
  preferences.begin("storage", false);
  preferences.putInt("dm", settings.display_mode);
  preferences.end();
  displayMode = settings.display_mode;
  if (enableHA) {
    haDisplayMode.setState(settings.display_mode);
  }
  //touchModeDisplay(utf8cyr("Режим дисплея:"), utf8cyr(displayModes[displayModeInit-1]));
}
//--Button start

//--Display start
void DisplayCenter(String text, int bound, int text_size) {
  int16_t x;
  int16_t y;
  uint16_t width;
  uint16_t height;
  display.setCursor(0, 0);
  display.setTextSize(text_size);
  display.getTextBounds(text, 0, 0, &x, &y, &width, &height);
  display.setCursor(((settings.display_width - width) / 2), ((settings.display_height - height) / 2) + bound);
  display.println(utf8cyr(text));
  display.display();
}

String utf8cyr(String source) {
  int i,k;
  String target;
  unsigned char n;
  char m[2] = { '0', '\0' };

  k = source.length(); i = 0;
  while (i < k) {
    n = source[i]; i++;
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

void displayCycle() {
  int hour = timeClient.getHours();
  int minute = timeClient.getMinutes();

  if (displayMode == 0 || settings.display_mode == 0) {
    //Serial.println("Display mode off");
    display.clearDisplay();
    display.display();
  }
  if (displayMode == 1 || settings.display_mode == 1) {
    //Serial.println("Display mode clock");
    int day = timeClient.getDay();
    String daysOfWeek[] = {"Heдiля", "Пoнeдiлoк", "Biвтopoк", "Середа", "Четвер", "П\'ятниця", "Субота"};
    display.setCursor(0, 0);
    display.clearDisplay();
    display.setTextSize(1);
    display.println(utf8cyr(daysOfWeek[day]));
    String time = "";
    if (hour < 10) time += "0";
    time += hour;
    time += ":";
    if (minute < 10) time += "0";
    time += minute;

    DisplayCenter(time,7,3);
  }
  if (displayMode == 2 || settings.display_mode == 2) {
    //Serial.println("Display mode weather");
    display.setCursor(0, 0);
    display.clearDisplay();
    String time = "";

    char roundedTemp[4];

    int position = calculateOffset(settings.home_district);

    dtostrf(weather_leds[position], 3, 1, roundedTemp);
    time += roundedTemp;
    time += " C";
    DisplayCenter(time,7,3);
  }
  if (displayMode == 9) {
    time_t displayCurrentTime = timeClient.getEpochTime();
    long displayDiffTime = difftime(displayCurrentTime, displayOldTime);
    if (displayDiffTime >= settings.display_mode_time){
      settings.display_mode += 1;
      if (settings.display_mode > 2) {
        settings.display_mode = 1;
      }
      displayOldTime = timeClient.getEpochTime();
    }
  }
}
//--Display end

//--Web server start
void setupRouting() {
  Serial.println("Init WebServer");
  webserver.on("/", HTTP_GET, handleRoot);
  webserver.on("/save", HTTP_POST, handleSave);
  webserver.begin();
  Serial.println("Webportal running");
}


void handleRoot(AsyncWebServerRequest* request){
  String html;
  html +="<!DOCTYPE html>";
  html +="<html lang='en'>";
  html +="<head>";
  html +="    <meta charset='UTF-8'>";
  html +="    <meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html +="    <title>" + settings.devicename + "</title>";
  html +="    <link rel='stylesheet' href='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'>";
  html +="    <style>";
  html +="        body { background-color: #4396ff; }";
  html +="        .container { background-color: #fff0d5; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,.1); }";
  html +="        label { font-weight: bold; }";
  html +="        #sliderValue1, #sliderValue2, #sliderValue3, #sliderValue4 { font-weight: bold; color: #070505; }";
  html +="        .color-box { width: 30px; height: 30px; display: inline-block; margin-left: 10px; border: 1px solid #ccc; vertical-align: middle; }";
  html +="        .full-screen-img {width: 100%;height: 100%;object-fit: cover;}";
  html +="    </style>";
  html +="</head>";
  html +="<body>";
  html +="    <div class='container mt-3'>";
  html +="        <h2 class='text-center'>" + settings.devicedescription + " ";
  html +=             settings.softwareversion;
  html +="        </h2>";
  html +="        <div class='row'>";
  html +="            <div class='col-md-6 offset-md-3'>";
  if (mapMode == 1){
    html +="                <img class='full-screen-img' src='http://alerts.net.ua/alerts_map.png'>";
  }
  if (mapMode == 2){
    html +="                <img class='full-screen-img' src='http://alerts.net.ua/weather_map.png'>";
  }
  html +="            </div>";
  html +="        </div>";
  html +="        <div class='row'>";
  html +="            <div class='col-md-6 offset-md-3'>";
  html +="            <h4 class='mt-4'>Локальна IP-адреса: ";
    html +=             WiFi.localIP().toString();
  html +="            </h4>";
  html +="                <form action='/save' method='POST'>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox8'>Режим прошивки</label>";
  html +="                        <select name='legacy' class='form-control' id='selectBox8'>";
  html +="<option value='0'";
  if (settings.legacy == 1) html += " selected";
  html +=">Плата JAAM</option>";
  html +="<option value='1'";
  if (settings.legacy == 1) html += " selected";
  html +=">Класична (початок на Закарпатті)</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='inputField1'> Адреса mqtt-сервера Home Assistant</label>";
  html +="                        <input type='text' name='ha_brokeraddress' class='form-control' id='inputField1' placeholder='' value='" + String(settings.ha_brokeraddress) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='inputField2'>Порт mqtt-сервера Home Assistant</label>";
  html +="                        <input type='text' name='ha_mqttport' class='form-control' id='inputField2' value='" + String(settings.ha_mqttport) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='inputField3'>Юзер mqtt-сервера Home Assistant</label>";
  html +="                        <input type='text' name='ha_mqttuser' class='form-control' id='inputField3' value='" + String(settings.ha_mqttuser) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='inputField4'>Пароль mqtt-сервера Home Assistant</label>";
  html +="                        <input type='text' name='ha_mqttpassword' class='form-control' id='inputField4' value='" + String(settings.ha_mqttpassword) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='inputField5'>Керуючій пін лед-стрічкі</label>";
  html +="                        <input type='text' name='pixelpin' class='form-control' id='inputField5' value='" + String(settings.pixelpin) + "'>";
  html +="                    </div>";
    html +="                   <div class='form-group'>";
  html +="                        <label for='inputField5'>Керуючій пін кнопки</label>";
  html +="                        <input type='text' name='buttonpin' class='form-control' id='inputField6' value='" + String(settings.buttonpin) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider1'>Загальна яскравість: <span id='sliderValue1'>" + String(settings.brightness) + "</span></label>";
  html +="                        <input type='range' name='brightness' class='form-control-range' id='slider1' min='0' max='100' value='" + String(settings.brightness) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider1'>Денна яскравість: <span id='sliderValue13'>" + String(settings.brightness_day) + "</span></label>";
  html +="                        <input type='range' name='brightness_day' class='form-control-range' id='slider13' min='0' max='100' value='" + String(settings.brightness_day) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider1'>Нічна яскравість: <span id='sliderValue14'>" + String(settings.brightness_night) + "</span></label>";
  html +="                        <input type='range' name='brightness_night' class='form-control-range' id='slider14' min='0' max='100' value='" + String(settings.brightness_night) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider1'>Початок дня: <span id='sliderValue15'>" + String(settings.day_start) + "</span></label>";
  html +="                        <input type='range' name='day_start' class='form-control-range' id='slider15' min='0' max='24' value='" + String(settings.day_start) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider1'>Початок ночі: <span id='sliderValue16'>" + String(settings.night_start) + "</span></label>";
  html +="                        <input type='range' name='night_start' class='form-control-range' id='slider16' min='0' max='24' value='" + String(settings.night_start) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group form-check'>";
  html +="                        <input name='brightness_auto' type='checkbox' class='form-check-input' id='checkbox2'";
  if (settings.brightness_auto == 1) html += " checked";
  html +=">";
  html +="                        <label class='form-check-label' for='checkbox'>";
  html +="                          Автояскравість";
  html +="                        </label>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider9'>Яскравість районів з тривогами: <span id='sliderValue9'>" + String(settings.brightness_alert) + "</span></label>";
  html +="                        <input type='range' name='brightness_alert' class='form-control-range' id='slider9' min='0' max='100' value='" + String(settings.brightness_alert) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider10'>Яскравість районів без тривог: <span id='sliderValue10'>" + String(settings.brightness_clear) + "</span></label>";
  html +="                        <input type='range' name='brightness_clear' class='form-control-range' id='slider10' min='0' max='100' value='" + String(settings.brightness_clear) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider11'>Яскравість нових тривог: <span id='sliderValue11'>" + String(settings.brightness_new_alert) + "</span></label>";
  html +="                        <input type='range' name='brightness_new_alert' class='form-control-range' id='slider11' min='0' max='100' value='" + String(settings.brightness_new_alert) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider12'>Яскравість відбою: <span id='sliderValue12'>" + String(settings.brightness_alert_over) + "</span></label>";
  html +="                        <input type='range' name='brightness_alert_over' class='form-control-range' id='slider12' min='0' max='100' value='" + String(settings.brightness_alert_over) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider3'>Тривога: <span id='sliderValue3'>" + String(settings.color_alert) + "</span></label>";
  html +="                        <input type='range' name='color_alert' class='form-control-range' id='slider3' min='0' max='360' value='" + String(settings.color_alert) + "'>";
  html +="                        <div class='color-box' id='colorBox1'></div>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider4'>Нема тривоги: <span id='sliderValue4'>" + String(settings.color_clear) + "</span></label>";
  html +="                        <input type='range' name='color_clear' class='form-control-range' id='slider4' min='0' max='360' value='" + String(settings.color_clear) + "'>";
  html +="                        <div class='color-box' id='colorBox2'></div>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider5'>Початок тривоги: <span id='sliderValue5'>" + String(settings.color_new_alert) + "</span></label>";
  html +="                        <input type='range' name='color_new_alert' class='form-control-range' id='slider5' min='0' max='360' value='" + String(settings.color_new_alert) + "'>";
  html +="                        <div class='color-box' id='colorBox3'></div>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider6'>Закінчення тривоги: <span id='sliderValue6'>" + String(settings.color_alert_over) + "</span></label>";
  html +="                        <input type='range' name='color_alert_over' class='form-control-range' id='slider6' min='0' max='360' value='" + String(settings.color_alert_over) + "'>";
  html +="                        <div class='color-box' id='colorBox4'></div>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider7'>Нижній рівень температури: <span id='sliderValue7'>" + String(settings.weather_min_temp) + "</span></label>";
  html +="                        <input type='range' name='weather_min_temp' class='form-control-range' id='slider7' min='-20' max='10' value='" + String(settings.weather_min_temp) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider8'>Верхній рівень температури: <span id='sliderValue8'>" + String(settings.weather_max_temp) + "</span></label>";
  html +="                        <input type='range' name='weather_max_temp' class='form-control-range' id='slider8' min='11' max='40' value='" + String(settings.weather_max_temp) + "'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider17'>Час перемикання дисплея: <span id='sliderValue17'>" + String(settings.display_mode_time) + "</span></label>";
  html +="                        <input type='range' name='display_mode_time' class='form-control-range' id='slider17' min='1' max='60' value='" + String(settings.display_mode_time) + "'>";
  html +="                    </div>";
  if(settings.legacy){
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox1'>Режим діода 'Київська область'</label>";
  html +="                        <select name='kyiv_district_mode' class='form-control' id='selectBox1'>";
  html +="<option value='1'";
  if (settings.kyiv_district_mode == 1) html += " selected";
  html +=">Київська область</option>";
  html +="<option value='2'";
  if (settings.kyiv_district_mode == 2) html += " selected";
  html +=">Київ</option>";
  html +="<option value='3'";
  if (settings.kyiv_district_mode == 3) html += " selected";
  html +=">Київська область + Київ (2 діода)</option>";
  html +="<option value='4'";
  if (settings.kyiv_district_mode == 4) html += " selected";
  html +=">Київська область + Київ (1 діод)</option>";
  html +="                        </select>";
  html +="                    </div>";
  }
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox2'>Режим мапи</label>";
  html +="                        <select name='map_mode' class='form-control' id='selectBox2'>";
  html +="<option value='0'";
  if (settings.map_mode == 0) html += " selected";
  html +=">Вимкнена</option>";
  html +="<option value='1'";
  if (settings.map_mode == 1) html += " selected";
  html +=">Тривоги</option>";
  html +="<option value='2'";
  if (settings.map_mode == 2) html += " selected";
  html +=">Погода</option>";
  html +="<option value='3'";
  if (settings.map_mode == 3) html += " selected";
  html +=">Прапор</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox5'>Режим дисплея</label>";
  html +="                        <select name='display_mode' class='form-control' id='selectBox5'>";
  html +="<option value='0'";
  if (displayMode == 0) html += " selected";
  html +=">Вимкнений</option>";
  html +="<option value='1'";
  if (displayMode == 1) html += " selected";
  html +=">Час</option>";
  html +="<option value='2'";
  if (displayMode == 2) html += " selected";
  html +=">Погода</option>";
  html +="<option value='9'";
  if (displayMode == 9) html += " selected";
  html +=">Перемикання за часом</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox6'>Режим кнопки</label>";
  html +="                        <select name='button_mode' class='form-control' id='selectBox6'>";
  html +="<option value='0'";
  if (settings.button_mode == 0) html += " selected";
  html +=">Вимкнений</option>";
  html +="<option value='1'";
  if (settings.button_mode == 1) html += " selected";
  html +=">Перемикання режимів мапи</option>";
  html +="<option value='2'";
  if (settings.button_mode == 2) html += " selected";
  html +=">Перемикання режимів дисплея</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox3'>Домашній регіон</label>";
  html +="                        <select name='home_district' class='form-control' id='selectBox3'>";
  html +="<option value='15'";
  if (settings.home_district == 15) html += " selected";
  html +=">АР Крим</option>";
  html +="<option value='22'";
  if (settings.home_district == 22) html += " selected";
  html +=">Вінницька область</option>";
  html +="<option value='4'";
  if (settings.home_district == 4) html += " selected";
  html +=">Волинська область</option>";
  html +="<option value='18'";
  if (settings.home_district == 18) html += " selected";
  html +=">Дніпропетровська область</option>";
  html +="<option value='12'";
  if (settings.home_district == 12) html += " selected";
  html +=">Донецька область</option>";
  html +="<option value='6'";
  if (settings.home_district == 6) html += " selected";
  html +=">Житомирська область</option>";
  html +="<option value='0'";
  if (settings.home_district == 0) html += " selected";
  html +=">Закарпатська область</option>";
  html +="<option value='13'";
  if (settings.home_district == 13) html += " selected";
  html +=">Запорізька область</option>";
  html +="<option value='1'";
  if (settings.home_district == 1) html += " selected";
  html +=">Івано-Франківська область</option>";
  html +="<option value='7'";
  if (settings.home_district == 7) html += " selected";
  html +=">Київська область</option>";
  html +="<option value='25'";
  if (settings.home_district == 25) html += " selected";
  html +=">Київ</option>";
  html +="<option value='21'";
  if (settings.home_district == 21) html += " selected";
  html +=">Кіровоградська область</option>";
  html +="<option value='11'";
  if (settings.home_district == 11) html += " selected";
  html +=">Луганська область</option>";
  html +="<option value='3'";
  if (settings.home_district == 3) html += " selected";
  html +=">Львівська область</option>";
  html +="<option value='17'";
  if (settings.home_district == 17) html += " selected";
  html +=">Миколаївська область</option>";
  html +="<option value='16'";
  if (settings.home_district == 16) html += " selected";
  html +=">Одеська область</option>";
  html +="<option value='19'";
  if (settings.home_district == 19) html += " selected";
  html +=">Полтавська область</option>";
  html +="<option value='5'";
  if (settings.home_district == 5) html += " selected";
  html +=">Рівненська область</option>";
  html +="<option value='9'";
  if (settings.home_district == 9) html += " selected";
  html +=">Сумська область</option>";
  html +="<option value='2'";
  if (settings.home_district == 2) html += " selected";
  html +=">Тернопільська область</option>";
  html +="<option value='10'";
  if (settings.home_district == 10) html += " selected";
  html +=">Харківська область</option>";
  html +="<option value='14'";
  if (settings.home_district == 14) html += " selected";
  html +=">Херсонська область</option>";
  html +="<option value='23'";
  if (settings.home_district == 23) html += " selected";
  html +=">Хмельницька область</option>";
  html +="<option value='20'";
  if (settings.home_district == 20) html += " selected";
  html +=">Черкаська область</option>";
  html +="<option value='24'";
  if (settings.home_district == 24) html += " selected";
  html +=">Чернівецька область</option>";
  html +="<option value='8'";
  if (settings.home_district == 8) html += " selected";
  html +=">Чернігівська область</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox4'>Відображення на мапі нових тривог та відбою</label>";
  html +="                        <select name='alarms_notify_mode' class='form-control' id='selectBox4'>";
   html +="<option value='0'";
  if (settings.alarms_notify_mode == 0) html += " selected";
  html +=">Вимкнено</option>";
  html +="<option value='1'";
  if (settings.alarms_notify_mode == 1) html += " selected";
  html +=">Колір</option>";
   html +="<option value='2'";
  if (settings.alarms_notify_mode == 2) html += " selected";
  html +=">Колір+зміна яскравості</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox7'>Розмір дисплея</label>";
  html +="                        <select name='display_height' class='form-control' id='selectBox7'>";
   html +="<option value='32'";
  if (settings.display_height == 32) html += " selected";
  html +=">128*32</option>";
  html +="<option value='64'";
  if (settings.display_height == 64) html += " selected";
  html +=">128*64</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group form-check'>";
  html +="                        <input name='alarms_auto_switch' type='checkbox' class='form-check-input' id='checkbox'";
  if (settings.alarms_auto_switch == 1) html += " checked";
  html +=">";
  html +="                        <label class='form-check-label' for='checkbox'>";
  html +="                          Перемикання мапи в режим тривоги у випадку тривоги у домашньому регіоні";
  html +="                        </label>";
  html +="                    </div>";
  html +="                    <button type='submit' class='btn btn-primary'>Зберегти налаштування</button>";
  html +="                </form>";
  html +="            </div>";
  html +="        </div>";
  html +="    </div>";
  html +="";
  html +="    <script src='https://code.jquery.com/jquery-3.5.1.slim.min.js'></script>";
  html +="    <script src='https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.3/dist/umd/popper.min.js'></script>";
  html +="    <script src='https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js'></script>";
  html +="    <script>";
  html +="        const sliders = ['slider1', 'slider3', 'slider4', 'slider5', 'slider6', 'slider7', 'slider8', 'slider9', 'slider10', 'slider11', 'slider12', 'slider13', 'slider14', 'slider15', 'slider16', 'slider17'];";
  html +="";
  html +="        sliders.forEach(slider => {";
  html +="            const sliderElem = document.getElementById(slider);";
  html +="            const sliderValueElem = document.getElementById(slider.replace('slider', 'sliderValue'));";
  html +="            sliderElem.addEventListener('input', () => sliderValueElem.textContent = sliderElem.value);";
  html +="        });";
  html +="";
  html +="        function updateColorBox(boxId, hue) {";
  html +="            const rgbColor = hsbToRgb(hue, 100, 100);";
  html +="            document.getElementById(boxId).style.backgroundColor = `rgb(${rgbColor.r}, ${rgbColor.g}, ${rgbColor.b})`;";
  html +="        }";
  html +="";
  html +="        const initialHue1 = parseInt(slider3.value);";
  html +="        const initialRgbColor1 = hsbToRgb(initialHue1, 100, 100);";
  html +="        document.getElementById('colorBox1').style.backgroundColor = `rgb(${initialRgbColor1.r}, ${initialRgbColor1.g}, ${initialRgbColor1.b})`;";
  html +="";
  html +="        const initialHue2 = parseInt(slider4.value);";
  html +="        const initialRgbColor2 = hsbToRgb(initialHue2, 100, 100);";
  html +="        document.getElementById('colorBox2').style.backgroundColor = `rgb(${initialRgbColor2.r}, ${initialRgbColor2.g}, ${initialRgbColor2.b})`;";
  html +="";
  html +="        const initialHue3 = parseInt(slider5.value);";
  html +="        const initialRgbColor3 = hsbToRgb(initialHue3, 100, 100);";
  html +="        document.getElementById('colorBox3').style.backgroundColor = `rgb(${initialRgbColor3.r}, ${initialRgbColor3.g}, ${initialRgbColor3.b})`;";
  html +="";
  html +="        const initialHue4 = parseInt(slider4.value);";
  html +="        const initialRgbColor4 = hsbToRgb(initialHue4, 100, 100);";
  html +="        document.getElementById('colorBox4').style.backgroundColor = `rgb(${initialRgbColor4.r}, ${initialRgbColor4.g}, ${initialRgbColor4.b})`;";
  html +="";
  html +="        function hsbToRgb(h, s, b) {";
  html +="            h /= 360;";
  html +="            s /= 100;";
  html +="            b /= 100;";
  html +="";
  html +="            let r, g, bl;";
  html +="";
  html +="            if (s === 0) {";
  html +="                r = g = bl = b;";
  html +="            } else {";
  html +="                const i = Math.floor(h * 6);";
  html +="                const f = h * 6 - i;";
  html +="                const p = b * (1 - s);";
  html +="                const q = b * (1 - f * s);";
  html +="                const t = b * (1 - (1 - f) * s);";
  html +="";
  html +="                switch (i % 6) {";
  html +="                    case 0: r = b, g = t, bl = p; break;";
  html +="                    case 1: r = q, g = b, bl = p; break;";
  html +="                    case 2: r = p, g = b, bl = t; break;";
  html +="                    case 3: r = p, g = q, bl = b; break;";
  html +="                    case 4: r = t, g = p, bl = b; break;";
  html +="                    case 5: r = b, g = p, bl = q; break;";
  html +="                }";
  html +="            }";
  html +="";
  html +="            return {";
  html +="                r: Math.round(r * 255),";
  html +="                g: Math.round(g * 255),";
  html +="                b: Math.round(bl * 255)";
  html +="            };";
  html +="        }";
  html +="";
  html +="        sliders.slice(1).forEach((slider, index) => {";
  html +="            const sliderElem = document.getElementById(slider);";
  html +="            const colorBoxElem = document.getElementById('colorBox' + (index + 1));";
  html +="            sliderElem.addEventListener('input', () => {";
  html +="                const hue = parseInt(sliderElem.value);";
  html +="                updateColorBox(colorBoxElem.id, hue);";
  html +="                document.getElementById(slider.replace('slider', 'sliderValue')).textContent = hue;";
  html +="            });";
  html +="        });";
  html +="    </script>";
  html +="</body>";
  html +="</html>";
  request->send(200, "text/html", html);
}

void handleSave(AsyncWebServerRequest* request){
  preferences.begin("storage", false);
  bool reboot = false;
  bool disableBrightnessAuto = false;
  if (request->hasParam("legacy", true)){
    if (request->getParam("legacy", true)->value().toInt() != settings.legacy){
      reboot = true;
    }
    settings.legacy = request->getParam("legacy", true)->value().toInt();
    preferences.putInt("legacy", settings.legacy);
    Serial.println("legacy commited to preferences");
  }
  if (request->hasParam("ha_brokeraddress", true)){
    if (request->getParam("ha_brokeraddress", true)->value() != settings.ha_brokeraddress){
      reboot = true;
    }
    settings.ha_brokeraddress = request->getParam("ha_brokeraddress", true)->value();
    preferences.putString("ha_brokeraddr", settings.ha_brokeraddress);
    Serial.println("ha_brokeraddress commited to preferences");
  }
  if (request->hasParam("ha_mqttport", true)){
    if (request->getParam("ha_mqttport", true)->value().toInt() != settings.ha_mqttport){
      reboot = true;
    }
    settings.ha_mqttport = request->getParam("ha_mqttport", true)->value().toInt();
    preferences.putInt("ha_mqttport", settings.ha_mqttport);
    Serial.println("ha_mqttport commited to preferences");
  }
  if (request->hasParam("pixelpin", true)){
    if (request->getParam("pixelpin", true)->value().toInt() != settings.pixelpin){
      reboot = true;
    }
    settings.pixelpin = request->getParam("pixelpin", true)->value().toInt();
    preferences.putInt("pp", settings.pixelpin);
    Serial.println("pixelpin commited: ");
    Serial.println(settings.pixelpin);
  }
  if (request->hasParam("buttonpin", true)){
    if (request->getParam("buttonpin", true)->value().toInt() != settings.buttonpin){
      reboot = true;
    }
    settings.buttonpin = request->getParam("buttonpin", true)->value().toInt();
    preferences.putInt("bp", settings.buttonpin);
    Serial.println("buttonpin commited: ");
    Serial.println(settings.buttonpin);
  }
  if (request->hasParam("ha_mqttuser", true)){
    if (request->getParam("ha_mqttuser", true)->value() != settings.ha_mqttuser){
      reboot = true;
    }
    settings.ha_mqttuser = request->getParam("ha_mqttuser", true)->value();
    preferences.putString("ha_mqttuser", settings.ha_mqttuser);
    Serial.println("ha_mqttuser commited to preferences");
  }
  if (request->hasParam("ha_mqttpassword", true)){
    if (request->getParam("ha_mqttpassword", true)->value() != settings.ha_mqttpassword){
      reboot = true;
    }
    settings.ha_mqttpassword = request->getParam("ha_mqttpassword", true)->value();
    preferences.putString("ha_mqttpass", settings.ha_mqttpassword);
    Serial.println("ha_mqttpassword commited to preferences");
  }
  if (request->hasParam("brightness", true)){
    int currentBrightness = request->getParam("brightness", true)->value().toInt();

    if(currentBrightness != settings.brightness){
      disableBrightnessAuto = true;
    }
    settings.brightness = request->getParam("brightness", true)->value().toInt();
    preferences.putInt("brightness", settings.brightness);
    haBrightness.setState(settings.brightness);
    Serial.println("brightness commited to preferences");
  }
  if (request->hasParam("brightness_auto", true) and !disableBrightnessAuto){
    settings.brightness_auto = 1;
    haBrightnessAuto.setState(true);
    preferences.putInt("bra", settings.brightness_auto);
    Serial.println("brightness_auto enabled to preferences");
  }else{
    settings.brightness_auto = 0;
    haBrightnessAuto.setState(false);
    preferences.putInt("bra", settings.brightness_auto);
    Serial.println("brightness_auto disabled to preferences");
  }
  if (request->hasParam("brightness_day", true)){
    settings.brightness_day = request->getParam("brightness_day", true)->value().toInt();
    preferences.putInt("brd", settings.brightness_day);
    Serial.println("brightness_day commited to preferences");
  }
  if (request->hasParam("brightness_night", true)){
    settings.brightness_night = request->getParam("brightness_night", true)->value().toInt();
    preferences.putInt("brn", settings.brightness_night);
    Serial.println("brightness_night commited to preferences");
  }
  if (request->hasParam("day_start", true)){
    settings.day_start = request->getParam("day_start", true)->value().toInt();
    preferences.putInt("ds", settings.day_start);
    Serial.println("day_start commited to preferences");
  }
  if (request->hasParam("night_start", true)){
    settings.night_start = request->getParam("night_start", true)->value().toInt();
    preferences.putInt("ns", settings.night_start);
    Serial.println("night_start commited to preferences");
  }
  if (request->hasParam("brightness_alert", true)){
    settings.brightness_alert = request->getParam("brightness_alert", true)->value().toInt();
    preferences.putInt("ba", settings.brightness_alert);
    Serial.println("brightness_alert commited to preferences");
  }
  if (request->hasParam("brightness_clear", true)){
    settings.brightness_clear = request->getParam("brightness_clear", true)->value().toInt();
    preferences.putInt("bc", settings.brightness_clear);
    Serial.println("brightness_clear commited to preferences");
  }
  if (request->hasParam("brightness_new_alert", true)){
    settings.brightness_new_alert = request->getParam("brightness_new_alert", true)->value().toInt();
    preferences.putInt("bna", settings.brightness_new_alert);
    Serial.println("brightness_new_alert commited to preferences");
  }
  if (request->hasParam("brightness_alert_over", true)){
    settings.brightness_alert_over = request->getParam("brightness_alert_over", true)->value().toInt();
    preferences.putInt("bao", settings.brightness_alert_over);
    Serial.println("brightness_alert_over commited to preferences");
  }
  if (request->hasParam("color_alert", true)){
    settings.color_alert = request->getParam("color_alert", true)->value().toInt();
    preferences.putInt("coloral", settings.color_alert);
    Serial.println("color_alert commited to preferences");
  }
  if (request->hasParam("color_clear", true)){
    settings.color_clear = request->getParam("color_clear", true)->value().toInt();
    preferences.putInt("colorcl", settings.color_clear);
    Serial.println("color_clear commited to preferences");
  }
  if (request->hasParam("color_new_alert", true)){
    settings.color_new_alert = request->getParam("color_new_alert", true)->value().toInt();
    preferences.putInt("colorna", settings.color_new_alert);
    Serial.println("color_new_alert commited to preferences");
  }
  if (request->hasParam("color_alert_over", true)){
    settings.color_alert_over = request->getParam("color_alert_over", true)->value().toInt();
    preferences.putInt("colorao", settings.color_alert_over);
    Serial.println("color_alert_over commited to preferences");
  }
  if (request->hasParam("home_district", true)){
    settings.home_district = request->getParam("home_district", true)->value().toInt();
    preferences.putInt("hd", settings.home_district);
    Serial.println("home_district commited to preferences");
  }
  if (request->hasParam("alarms_auto_switch", true)){
    settings.alarms_auto_switch = 1;
    haAlarmsAuto.setState(true);
    preferences.putInt("aas", settings.alarms_auto_switch);
    Serial.println("alarms_auto_switch commited to preferences");
  }else{
    settings.alarms_auto_switch = 0;
    haAlarmsAuto.setState(false);
    preferences.putInt("aas", settings.alarms_auto_switch);
    Serial.println("alarms_auto_switch commited to preferences");
  }
  if (request->hasParam("kyiv_district_mode", true)){
    settings.kyiv_district_mode = request->getParam("kyiv_district_mode", true)->value().toInt();
    preferences.putInt("kdm", settings.kyiv_district_mode);
    Serial.println("kyiv_district_mode commited to preferences");
  }
  if (request->hasParam("map_mode", true)){
    settings.map_mode = request->getParam("map_mode", true)->value().toInt();
    preferences.putInt("mapmode", settings.map_mode);
    haMapMode.setState(settings.map_mode);
    Serial.println("map_mode commited to preferences");
  }
  if (request->hasParam("display_mode", true)){
    settings.display_mode = request->getParam("display_mode", true)->value().toInt();
    preferences.putInt("dm", settings.display_mode);
    displayMode = settings.display_mode;
    haDisplayMode.setState(settings.display_mode);
    Serial.print("display_mode commited to preferences: ");
    Serial.println(displayMode);
  }
  if (request->hasParam("display_mode_time", true)){
    settings.display_mode_time = request->getParam("display_mode_time", true)->value().toInt();
    preferences.putInt("dmt", settings.display_mode_time);
    Serial.println("display_mode_time commited to preferences");
  }
  if (request->hasParam("button_mode", true)){
    settings.button_mode = request->getParam("button_mode", true)->value().toInt();
    preferences.putInt("bm", settings.button_mode);
    Serial.println("button_mode commited to preferences");
  }
  if (request->hasParam("alarms_notify_mode", true)){
    settings.alarms_notify_mode = request->getParam("alarms_notify_mode", true)->value().toInt();
    preferences.putInt("anm", settings.alarms_notify_mode);
    Serial.println("alarms_notify_mode commited to preferences");
  }
  if (request->hasParam("weather_min_temp", true)){
    settings.weather_min_temp = request->getParam("weather_min_temp", true)->value().toInt();
    preferences.putInt("mintemp", settings.weather_min_temp);
    Serial.println("color_alert_over commited to preferences");
  }
  if (request->hasParam("weather_max_temp", true)){
    settings.weather_max_temp = request->getParam("weather_max_temp", true)->value().toInt();
    preferences.putInt("maxtemp", settings.weather_max_temp);
    Serial.println("weather_max_temp commited to preferences");
  }
  if (request->hasParam("display_height", true)){
    if (request->getParam("display_height", true)->value().toInt() != settings.display_height){
      reboot = true;
    }
    preferences.putInt("dh", request->getParam("display_height", true)->value().toInt());
    Serial.print("display_height commited to preferences: ");
    Serial.println(request->getParam("display_height", true)->value().toInt());
  }
  preferences.end();
  delay(1000);
  request->redirect("/");
  if(reboot){
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

  if(enableHA){
    haUptime.setValue(uptimeValue);
    haWifiSignal.setValue(rssi);
    haFreeMemory.setValue(freeHeapSize);
    haUsedMemory.setValue(usedHeapSize);
  }
  Serial.println(uptimeValue);
}

void connectStatuses(){
  Serial.print("Map API connected: ");
  Serial.println(client_tcp.connected());
  if (enableHA){
    Serial.print("Home Assistant MQTT connected: ");
    Serial.println(mqtt.isConnected());
    haMapApiConnect.setState(client_tcp.connected(), true);
  }
}

void timeUpdate() {
  timeClient.update();
  int currentHour = timeClient.getHours();
  isDay = currentHour >= settings.day_start && currentHour < settings.night_start;
}

void autoBrightnessUpdate() {
  if (settings.brightness_auto == 1) {
    int currentBrightness = 0;
    currentBrightness = isDay ? settings.brightness_day : settings.brightness_night;
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
void tcpConnect(){
  if (millis() - tcpLastPingTime > 30000){
    tcpReconnect = true;
  }
  if (!client_tcp.connected() or tcpReconnect) {
    Serial.println("Connecting to map API...");
    display.clearDisplay();
    DisplayCenter(utf8cyr("Пiдключення map-API.."),0,1);
    while (!client_tcp.connect(settings.tcphost, settings.tcpport))
    {
        Serial.println("Failed");
        display.clearDisplay();
        DisplayCenter(utf8cyr("map-API нeдocтyпнe"),0,1);
        haMapApiConnect.setState(false);
        delay(1000);
    }
    display.clearDisplay();
    DisplayCenter(utf8cyr("map-API пiдключeнo"),0,1);
    Serial.println("Connected");
    haMapApiConnect.setState(true);
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
//     if (!client_tcp.connect(settings.tcphost, settings.tcpport))
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

void tcpProcess(){
  String data;
  while (client_tcp.available() > 0)
  {
      data += (char)client_tcp.read();
  }
  if (data.length()) {
    Serial.print("New data: ");
    Serial.print(data.length());
    Serial.print(" : ");
    Serial.println(data);
    parseString(data);
  }
}

void parseString(String str) {
  if (str == "p"){
    Serial.println("TCP PING SUCCESS");
    tcpLastPingTime = millis();
    tcpReconnect = false;
  }else{
    int colonIndex = str.indexOf(":");
    String firstPart = str.substring(0, colonIndex);
    String secondPart = str.substring(colonIndex + 1);

    int firstArraySize = countOccurrences(firstPart, ',') + 1;
    int firstArray[firstArraySize];
    extractAlarms(firstPart, firstArraySize);

    int secondArraySize = countOccurrences(secondPart, ',') + 1;
    int secondArray[secondArraySize];
    extractWeather(secondPart, secondArraySize);
  }
}

int countOccurrences(String str, char target) {
  int count = 0;
  for (int i = 0; i < str.length(); i++) {
    if (str.charAt(i) == target) {
      count++;
    }
  }
  return count;
}

void extractAlarms(String str, int size) {
  int index = 0;
  char *token = strtok(const_cast<char*>(str.c_str()), ",");
  while (token != NULL && index < size) {
    alarm_leds[calculateOffset(index)] = atoi(token);
    token = strtok(NULL, ",");
    index++;
  }
}

void extractWeather(String str, int size) {
  int index = 0;
  char *token = strtok(const_cast<char*>(str.c_str()), ",");
  //Serial.print("weather");
  while (token != NULL && index < size) {
    weather_leds[calculateOffset(index)] = atof(token);
    token = strtok(NULL, ",");
    index++;
    //Serial.print(weather_leds[position]);
    //Serial.print(" ");
  }
  //Serial.println(" ");
}


//--TCP process end

//--Map processing start
int calculateOffset(int initial_position){
  int position;
  if (initial_position == 25) {
    position = 25;
  }else{
    position = initial_position + offset;
    if (position >= 25) {
      position-= 25;
    }
  }
  return position;
}

HsbColor processAlarms(int led) {
  HsbColor hue;
  float local_brightness = settings.brightness/200.0f;
  int local_color;
  if (blink and settings.alarms_notify_mode == 2){
    local_brightness = settings.brightness/600.0f;
  }

  float local_brightness_alert = settings.brightness_alert/100.0f;
  float local_brightness_clear = settings.brightness_clear/100.0f;
  float local_bbrightness_new_alert = settings.brightness_new_alert/100.0f;
  float local_brightness_alert_over = settings.brightness_alert_over/100.0f;

  switch (led) {
  case 0:
      hue = HsbColor(settings.color_clear/360.0f,1.0,settings.brightness*local_brightness_clear/200.0f);
      break;
  case 1:
      hue = HsbColor(settings.color_alert/360.0f,1.0,settings.brightness*local_brightness_alert/200.0f);
      break;
  case 2:
      local_color = settings.color_alert_over;
      if (settings.alarms_notify_mode == 0){
        local_color = settings.color_clear;
      }
      hue = HsbColor(local_color/360.0f,1.0,local_brightness*local_brightness_alert_over);
      break;
  case 3:
      local_color = settings.color_new_alert;
      if (settings.alarms_notify_mode == 0){
        local_color = settings.color_alert;
      }
      hue = HsbColor(local_color/360.0f,1.0,local_brightness*local_bbrightness_new_alert);
      break;
  }
  return hue;
}

float processWeather(int led) {
  double minTemp = settings.weather_min_temp;
  double maxTemp = settings.weather_max_temp;
  double temp = led;
  float normalizedValue = float(temp - minTemp) / float(maxTemp - minTemp);
  if (normalizedValue > 1){
    normalizedValue = 1;
  }
  if (normalizedValue < 0){
    normalizedValue = 0;
  }
  int hue = 300 + normalizedValue * (0 - 300);
  hue = (int)hue % 360;
  return hue/360.0f;
}

void mapCycle(){
  //Serial.println("Map update");
  if (mapMode == 0){
    mapOff();
  }
  if (mapMode == 1){
    mapAlarms();
  }
  if (mapMode == 2){
    mapWeather();
  }
  if (mapMode == 3){
    mapFlag();
  }
}

void mapOff(){
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, HslColor(0.0,0.0,0.0));
  }
  strip->Show();
}

void mapAlarms(){
  int adapted_alarm_leds[26];
  int lastValue = alarm_leds[25];
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    adapted_alarm_leds[i] = alarm_leds[i];
  }
  if (settings.kyiv_district_mode == 2){
    adapted_alarm_leds[7] = alarm_leds[25];
  }
  if (settings.kyiv_district_mode == 3){
    for (int i = 24; i >= 8 + offset; i--) {
      adapted_alarm_leds[i + 1] = alarm_leds[i];
    }
    adapted_alarm_leds[8 + offset] = lastValue;
  }
  if (settings.kyiv_district_mode == 4){
    if (alarm_leds[25] == 0 and alarm_leds[7] == 0){
      adapted_alarm_leds[7] = 0;
    }
    if (alarm_leds[25] == 1 or alarm_leds[7] == 1){
      adapted_alarm_leds[7] = 1;
    }
    if (alarm_leds[25] == 2 or alarm_leds[7] == 2){
      adapted_alarm_leds[7] = 2;
    }
    if (alarm_leds[25] == 3 or alarm_leds[7] == 3){
      adapted_alarm_leds[7] = 3;
    }
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, processAlarms(adapted_alarm_leds[i]));
  }
  strip->Show();
  blink = !blink;
}

void mapWeather(){
  int adapted_weather_leds[26];
  int lastValue = weather_leds[25];
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    adapted_weather_leds[i] = weather_leds[i];
  }
  if (settings.kyiv_district_mode == 2){
    adapted_weather_leds[7] = weather_leds[25];
  }
  if (settings.kyiv_district_mode == 3){
    for (int i = 24; i >= 8 + offset; i--) {
      adapted_weather_leds[i + 1] = weather_leds[i];
    }
    adapted_weather_leds[8 + offset] = lastValue;
  }
  if (settings.kyiv_district_mode == 4){
    adapted_weather_leds[7] = (weather_leds[25]+weather_leds[7])/2.0f;
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
     //Serial.print(adapted_weather_leds[i]);
     //Serial.print(" ");
    strip->SetPixelColor(i, HslColor(processWeather(adapted_weather_leds[i]),1.0,settings.brightness/200.0f));
  }
  //Serial.println(" ");
  strip->Show();
}

void mapFlag(){
  int adapted_flag_leds[26];
  int lastValue = flag_leds[25];
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    adapted_flag_leds[i] = flag_leds[i];
  }
  if (settings.kyiv_district_mode == 2){
    adapted_flag_leds[7] = flag_leds[25];
  }
  if (settings.kyiv_district_mode == 3){
    for (int i = 24; i >= 8 + offset; i--) {
      adapted_flag_leds[i + 1] = flag_leds[i];
    }
    adapted_flag_leds[8 + offset] = lastValue;
  }
  for (uint16_t i = 0; i < strip->PixelCount(); i++) {
    strip->SetPixelColor(i, HsbColor(adapted_flag_leds[i]/360.0f,1.0,settings.brightness/200.0f));
  }
  strip->Show();
}

void alarmTrigger(){
  int currentMapMode = settings.map_mode;
  if(settings.alarms_auto_switch){
    int position = settings.home_district;
    for (int j = 0; j < counters[position]; j++) {
      int alarm_led_id = calculateOffset(neighboring_districts[position][j]);
      if (alarm_leds[alarm_led_id] != 0)   {
        currentMapMode = 1;
      }
    }
  }
  if (mapMode != currentMapMode){
    haMapModeCurrent.setValue(mapModes[currentMapMode]);
  }
  mapMode = currentMapMode;
}
//--Map processing end

void WifiReconnect(){
  if (WiFi.status() != WL_CONNECTED){
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

  pinMode(settings.buttonpin, INPUT);

  asyncEngine.setInterval(uptime, 60000);
  asyncEngine.setInterval(tcpProcess, 10);
  asyncEngine.setInterval(connectStatuses, 10000);
  asyncEngine.setInterval(tcpConnect, 5000);
  asyncEngine.setInterval(mapCycle, 1000);
  asyncEngine.setInterval(timeUpdate, 5000);
  asyncEngine.setInterval(displayCycle, 1000);
  asyncEngine.setInterval(alarmTrigger, 1000);
  asyncEngine.setInterval(WifiReconnect, 5000);
  asyncEngine.setInterval(autoBrightnessUpdate, 1000);
  asyncEngine.setInterval(buttonUpdate, 100);
  asyncEngine.setInterval(timezoneUpdate, 60000);
}

void loop() {
  wm.process();
  asyncEngine.run();
  ArduinoOTA.handle();
  if(enableHA){
    mqtt.loop();
  }
}