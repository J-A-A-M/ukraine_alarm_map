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
#include <NeoPixelAnimator.h>

Preferences     preferences;
WiFiManager     wm;
WiFiClient      client;
WiFiClient      client_tcp;
WiFiUDP         ntpUDP;
AsyncWebServer  webserver(80);
NTPClient       timeClient(ntpUDP, "ua.pool.ntp.org", 7200);
Async           asyncEngine = Async();

struct Settings{
  char*   apssid             = "AlarmMap";
  char*   appassword         = "";
  char*   softwareversion    = "3.0d-4";
  String  broadcastname      = "alarmmap";
  String  devicename         = "Alarm Map";
  String  devicedescription  = "Alarm Map Informer";
  char*   tcphost            = "";
  int     tcpport            = 12345;
  int     pixelcount         = 26;
  int     pixelpin           = 17;

  // ------- web config start
  int   ha_mqttport          = 1883;
  char* ha_mqttuser          = "";
  char* ha_mqttpassword      = "";
  char* ha_brokeraddress     = "";
  int   brightness           = 50;
  int   color_alert          = 0;
  int   color_clear          = 120;
  int   color_new_alert      = 40;
  int   color_alert_over     = 150;
  int   weather_min_temp     = 5;
  int   weather_max_temp     = 30;
  int   alarms_auto_switch   = 1;
  int   home_district        = 7;
  int   kyiv_district_mode   = 1;
  int   map_mode             = 1;
  int   alarms_notify_mode   = 2;
  // ------- web config end
};

Settings settings;

NeoPixelBus<NeoGrbFeature, NeoWs2812xMethod> strip(settings.pixelcount, settings.pixelpin);
NeoGamma<NeoGammaTableMethod> colorGamma;

int     alarm_leds[26];
double  weather_leds[26];
int     flag_leds[26] = {
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
int d21[] = {21,16,17,18,1920,22};
int d22[] = {22,6,7,16,20,21,23,24,25};
int d23[] = {23,2,5,6,22,24};
int d24[] = {24,1,2,22,23};
int d25[] = {25,6,7,8,19,20,22};

int* neighboring_districts[] = {
  d0,d1,d2,d3,d4,d5,d6,d7,d8,d9,
  d10,d11,d12,d13,d14,d15,d16,d17,d18,d19,
  d20,d21,d22,d23,d24,d25
};

byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x38, 0x4A};
//byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x00, 0x4A}; //big
//byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x10, 0x4A}; //small

bool enableHA;
bool isConnected = false;
bool blink = false;
int  mapMode;

String haUptimeString         = settings.broadcastname + "_uptime";
String haWifiSignalString     = settings.broadcastname + "_wifi_signal";
String haFreeMemoryString     = settings.broadcastname + "_free_memory";
String haUsedMemoryString     = settings.broadcastname + "_used_memory";
String haBrightnessString     = settings.broadcastname + "_brightness";
String haMapModeString        = settings.broadcastname + "_map_mode";
String haMapModeCurrentString = settings.broadcastname + + "_map_mode_current";
String haMapApiConnectString  = settings.broadcastname + + "_map_api_connect";


const char* haUptimeChar          = haUptimeString.c_str();
const char* haWifiSignalChar      = haWifiSignalString.c_str();
const char* haFreeMemoryChar      = haFreeMemoryString.c_str();
const char* haUsedMemoryChar      = haUsedMemoryString.c_str();
const char* haBrightnessChar      = haBrightnessString.c_str();
const char* haMapModeChar         = haMapModeString.c_str();
const char* haMapModeCurrentChar  = haMapModeCurrentString.c_str();
const char* haMapApiConnectChar   = haMapApiConnectString.c_str();


HADevice        device(mac, sizeof(mac));
HAMqtt          mqtt(client, device, 9);
HASensorNumber  haUptime(haUptimeChar);
HASensorNumber  haWifiSignal(haWifiSignalChar);
HASensorNumber  haFreeMemory(haFreeMemoryChar);
HASensorNumber  haUsedMemory(haUsedMemoryChar);
HANumber        haBrightness(haBrightnessChar);
HASelect        haMapMode(haMapModeChar);
HASensor        haMapModeCurrent(haMapModeCurrentChar);
HABinarySensor  haMapApiConnect(haMapApiConnectChar);

char* mapModes [] = {
  "Вимкнено",
  "Tpивoгa",
  "Погода",
  "Прапор"
};

//--Init start
void initSettings(){
  Serial.println("Init settings");
  preferences.begin("storage", false);
  settings.brightness         = preferences.getInt("brightness", settings.brightness);
  settings.color_alert        = preferences.getInt("coloral", settings.color_alert);
  settings.color_clear        = preferences.getInt("colorcl", settings.color_clear);
  settings.color_new_alert    = preferences.getInt("colorna", settings.color_new_alert);
  settings.color_alert_over   = preferences.getInt("colorao", settings.color_alert_over);
  settings.alarms_auto_switch = preferences.getInt("aas", settings.alarms_auto_switch);
  settings.home_district      = preferences.getInt("hd", settings.home_district);
  settings.kyiv_district_mode = preferences.getInt("kdm", settings.kyiv_district_mode);
  settings.map_mode           = preferences.getInt("mapmode", settings.map_mode);
  settings.alarms_notify_mode = preferences.getInt("anm", settings.alarms_notify_mode);
  settings.weather_min_temp   = preferences.getInt("mintemp", settings.weather_min_temp);
  settings.weather_max_temp   = preferences.getInt("maxtemp", settings.weather_max_temp);
  preferences.end();
  mapMode                     = settings.map_mode;
}
void initStrip(){
  Serial.println("Init leds");
  strip.Begin();
  mapFlag();
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
    wm.setConnectTimeout(2);
    wm.setConnectRetries(10);
    if(wm.autoConnect(settings.apssid, settings.appassword)){
        Serial.println("connected...yeey :)");
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
        delay(5000);
        ESP.restart();
    }
}

void initBroadcast() {
  Serial.println("Init network device broadcast");

  if (!MDNS.begin(settings.broadcastname)) {
    Serial.println("Error setting up mDNS responder");
    while (1) {
      delay(1000);
    }
  }
  Serial.println("Device broadcasted to network: " + settings.broadcastname + ".local");
}

void initHA() {
  Serial.println("Init Home assistant API");
  String  brokerAddress_s      = preferences.getString("ha_brokeraddr", settings.ha_brokeraddress);
  int     mqttPort             = preferences.getInt("ha_mqttport", settings.ha_mqttport);
  String  mqttUser_s           = preferences.getString("ha_mqttuser", settings.ha_mqttuser);
  String  mqttPassword_s       = preferences.getString("ha_mqttpass", settings.ha_mqttpassword);


  char* deviceName             = new char[settings.devicename.length() + 1];
  char* deviceDescr            = new char[settings.devicedescription.length() + 1];
  char* brokerAddress          = new char[brokerAddress_s.length() + 1];
  char* mqttUser               = new char[mqttUser_s.length() + 1];
  char* mqttPassword           = new char[mqttPassword_s.length() + 1];

  strcpy(deviceName, settings.devicename.c_str());
  strcpy(deviceDescr, settings.devicedescription.c_str());
  strcpy(brokerAddress, brokerAddress_s.c_str());
  strcpy(mqttUser, mqttUser_s.c_str());
  strcpy(mqttPassword, mqttPassword_s.c_str());

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
    haBrightness.setIcon("mdi:brightness-percent");
    haBrightness.setName(haBrightnessChar);
    haBrightness.setCurrentState(settings.brightness);

    haMapMode.setOptions("Вимкнено;Тривога;Погода;Прапор");
    haMapMode.onCommand(onHaMapModeCommand);
    haMapMode.setIcon("mdi:map");
    haMapMode.setName(haMapModeChar);
    haMapMode.setCurrentState(settings.map_mode);

    haMapModeCurrent.setIcon("mdi:map");
    haMapModeCurrent.setName(haMapModeCurrentChar);
    haMapModeCurrent.setValue(mapModes[mapMode]);

    haMapApiConnect.setName(haMapApiConnectChar);
    haMapApiConnect.setDeviceClass("connectivity");
    haMapApiConnect.setCurrentState(false);

    device.enableLastWill();
    mqtt.begin(brokerAddr,mqttPort,mqttUser,mqttPassword);
    Serial.print("Home Assistant MQTT connected: ");
    Serial.println(mqtt.isConnected());
  }
}

void onHaBrightnessCommand(HANumeric haBrightness, HANumber* sender)
{
    if (!haBrightness.isSet()) {
        //Serial.println('number not set');
    } else {
        int8_t numberInt8 = haBrightness.toInt8();
        settings.brightness = numberInt8;
        preferences.begin("storage", false);
        preferences.putInt("brightness", settings.brightness);
        preferences.end();
        Serial.println("map_mode commited to preferences");
    }
    sender->setState(haBrightness);
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
//--Init end

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
  html +="    </style>";
  html +="</head>";
  html +="<body>";
  html +="    <div class='container mt-3'>";
  html +="        <div class='row'>";
  html +="            <div class='col-md-6 offset-md-3'>";
  html +="            <h2 class='mt-4'>" + settings.devicedescription + " ";
  html +=             settings.softwareversion;
  html +="            </h2>";
  html +="            <h4 class='mt-4'>Локальна IP-адреса: ";
  html +=             WiFi.localIP().toString();
  html +="            </h4>";
  html +="                <form action='/save' method='POST'>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='inputField'>Input Field</label>";
  html +="                        <input type='text' class='form-control' id='inputField' placeholder='Enter value'>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='slider1'>Загальна яскравість: <span id='sliderValue1'>" + String(settings.brightness) + "</span></label>";
  html +="                        <input type='range' name='brightness' class='form-control-range' id='slider1' min='0' max='100' value='" + String(settings.brightness) + "'>";
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
  html +="                        <label for='selectBox3'>Домашній регіон</label>";
  html +="                        <select name='home_district' class='form-control' id='selectBox3'>";
   html +="<option value='7'";
  if (settings.home_district == 7) html += " selected";
  html +=">Київська область</option>";
  html +="<option value='25'";
  if (settings.home_district == 25) html += " selected";
  html +=">Київ</option>";
   html +="<option value='10'";
  if (settings.home_district == 10) html += " selected";
  html +=">Харківська область</option>";
  html +="                        </select>";
  html +="                    </div>";
  html +="                    <div class='form-group'>";
  html +="                        <label for='selectBox4'>Відображення на мапі новіх тривого та відбою</label>";
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
  html +="        const sliders = ['slider1', 'slider3', 'slider4', 'slider5', 'slider6', 'slider7', 'slider8'];";
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
  if (request->hasParam("ha_brokeraddress", true)){
    preferences.putString("ha_brokeraddr", request->getParam("ha_brokeraddress", true)->value());
    Serial.println("ha_brokeraddress commited to preferences");
  }
  if (request->hasParam("ha_mqttport", true)){
    preferences.putInt("ha_mqttport", request->getParam("ha_mqttport", true)->value().toInt());
    Serial.println("ha_mqttport commited to preferences");
  }
  if (request->hasParam("ha_mqttuser", true)){
    preferences.putString("ha_mqttuser", request->getParam("ha_mqttuser", true)->value());
    Serial.println("ha_mqttuser commited to preferences");
  }
  if (request->hasParam("ha_mqttpassword", true)){
    preferences.putString("ha_mqttpass", request->getParam("ha_mqttpassword", true)->value());
    Serial.println("ha_mqttpassword commited to preferences");
  }
  if (request->hasParam("brightness", true)){
    settings.brightness = request->getParam("brightness", true)->value().toInt();
    preferences.putInt("brightness", settings.brightness);
    haBrightness.setState(settings.brightness);
    Serial.println("brightness commited to preferences");
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
    preferences.putInt("aas", settings.alarms_auto_switch);
    Serial.println("alarms_auto_switch commited to preferences");
  }else{
    settings.alarms_auto_switch = 0;
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
  preferences.end();
  request->redirect("/");
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
    haMapApiConnect.setState(client_tcp.connected());
  }


}
//--Service messages end

//--TCP process start
void tcpConnect(){
  if (!client_tcp.connected()) {
    Serial.println("Connecting to map API...");
    while (!client_tcp.connect(settings.tcphost, settings.tcpport))
    {
        Serial.println("Failed");
        haMapApiConnect.setState(false);
        delay(1000);
    }
    Serial.println("Connected");
    haMapApiConnect.setState(true);
  }
}

void tcpReconnect(){
  if (!client_tcp.connected()) {
    Serial.print("Reconnecting to map API: ");
    if (!client_tcp.connect(settings.tcphost, settings.tcpport))
    {
      Serial.println("Failed");
      haMapApiConnect.setState(false);
    }else{
      Serial.println("Connected");
      haMapApiConnect.setState(true);
    }
  }
}

void tcpProcess(){
  String data;
  while (client_tcp.available() > 0)
  {
      data += (char)client_tcp.read();
  }
  if (data.length()) {
    Serial.print("New data: ");
    Serial.println(data);
    parseString(data);
  }
}

void parseString(String str) {
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
    alarm_leds[index++] = atoi(token);
    token = strtok(NULL, ",");
  }
}

void extractWeather(String str, int size) {
  int index = 0;
  char *token = strtok(const_cast<char*>(str.c_str()), ",");
  while (token != NULL && index < size) {
    weather_leds[index++] = atof(token);
    token = strtok(NULL, ",");
  }
}
//--TCP process end

//--Map processing start
HsbColor processAlarms(int led) {
  HsbColor hue;
  float local_brightness;
  int local_color;
  if(blink and settings.alarms_notify_mode == 2){
    local_brightness = settings.brightness/200.0f;
  } else {
    local_brightness = settings.brightness/600.0f;
  }
  switch (led) {
  case 0:
      hue = HsbColor(settings.color_clear/360.0f,1.0,settings.brightness/200.0f);
      break;
  case 1:
      hue = HsbColor(settings.color_alert/360.0f,1.0,settings.brightness/200.0f);
      break;
  case 2:
      local_color = settings.color_alert_over;
      if (settings.alarms_notify_mode == 0){
        local_color = settings.color_clear;
      }
      hue = HsbColor(local_color/360.0f,1.0,local_brightness);
      break;
  case 3:
      local_color = settings.color_new_alert;
      if (settings.alarms_notify_mode == 0){
        local_color = settings.color_alert;
      }
      hue = HsbColor(local_color/360.0f,1.0,local_brightness);
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
  int hue = 240 + normalizedValue * (0 - 240);
  hue = (int)hue % 360;
  return hue/360.0f;
}

void mapCycle(){
  Serial.println("Map update");
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
  for (uint16_t i = 0; i < strip.PixelCount(); i++) {
    strip.SetPixelColor(i, HslColor(0.0,0.0,0.0));
  }
  strip.Show();
}

void mapAlarms(){
  int adapted_alarm_leds[26];
  int lastValue = alarm_leds[25];
  for (uint16_t i = 0; i < strip.PixelCount(); i++) {
    adapted_alarm_leds[i] = alarm_leds[i];
  }
  if (settings.kyiv_district_mode == 2){
    adapted_alarm_leds[7] = alarm_leds[25];
  }
  if (settings.kyiv_district_mode == 3){
    for (int i = 24; i >= 7; i--) {
      adapted_alarm_leds[i + 1] = alarm_leds[i];
    }
    adapted_alarm_leds[7] = alarm_leds[25];
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
  for (uint16_t i = 0; i < strip.PixelCount(); i++) {
    strip.SetPixelColor(i, processAlarms(adapted_alarm_leds[i]));
  }
  strip.Show();
  blink = !blink;
}

void mapWeather(){
  int adapted_weather_leds[26];
  int lastValue = weather_leds[25];
  for (uint16_t i = 0; i < strip.PixelCount(); i++) {
    adapted_weather_leds[i] = weather_leds[i];
  }
  if (settings.kyiv_district_mode == 2){
    adapted_weather_leds[7] = weather_leds[25];
  }
  if (settings.kyiv_district_mode == 3){
    for (int i = 24; i >= 7; i--) {
      adapted_weather_leds[i + 1] = weather_leds[i];
    }
    adapted_weather_leds[7] = weather_leds[25];
  }
  if (settings.kyiv_district_mode == 3){
    adapted_weather_leds[7] = (weather_leds[25]+weather_leds[7])/2.0f;
  }
  for (uint16_t i = 0; i < strip.PixelCount(); i++) {
    strip.SetPixelColor(i, HslColor(processWeather(adapted_weather_leds[i]),1.0,settings.brightness/200.0f));
  }
  strip.Show();
}

void mapFlag(){
  int adapted_flag_leds[26];
  int lastValue = flag_leds[25];
  for (uint16_t i = 0; i < strip.PixelCount(); i++) {
    adapted_flag_leds[i] = flag_leds[i];
  }
  if (settings.kyiv_district_mode == 2){
    adapted_flag_leds[7] = flag_leds[25];
  }
  if (settings.kyiv_district_mode == 3){
    for (int i = 24; i >= 7; i--) {
      adapted_flag_leds[i + 1] = flag_leds[i];
    }
    adapted_flag_leds[7] = flag_leds[25];
  }
  for (uint16_t i = 0; i < strip.PixelCount(); i++) {
    strip.SetPixelColor(i, HsbColor(adapted_flag_leds[i]/360.0f,1.0,settings.brightness/200.0f));
  }
  strip.Show();
}

void alarmTrigger(){
  bool returnToMapInitMode = true;
  if(settings.alarms_auto_switch){
    int size = sizeof(neighboring_districts[settings.home_district]);
    for (int j = 0; j <= size; j++) {
      int alarm_led_id = neighboring_districts[settings.home_district][j];
      if (alarm_leds[alarm_led_id] != 0)   {
        returnToMapInitMode = false;
        mapMode = 1;
        haMapModeCurrent.setValue(mapModes[mapMode]);
      }
    }
  }
  if (returnToMapInitMode) {
    mapMode = settings.map_mode;
    haMapModeCurrent.setValue(mapModes[mapMode]);
  }
}
//--Map processing end

void setup() {
  Serial.begin(115200);

  initSettings();
  initStrip();

  initWifi();

  asyncEngine.setInterval(uptime, 60000);
  asyncEngine.setInterval(tcpProcess, 10);
  asyncEngine.setInterval(connectStatuses, 10000);
  asyncEngine.setInterval(tcpReconnect, 5000);
  asyncEngine.setInterval(mapCycle, 1000);
  asyncEngine.setInterval(alarmTrigger, 1000);
}

void loop() {
  wm.process();
  asyncEngine.run();
  ArduinoOTA.handle();
  if(enableHA){
    mqtt.loop();
  }
}
