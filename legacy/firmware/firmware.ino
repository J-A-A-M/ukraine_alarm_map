#include <ArduinoJson.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WiFiManager.h>
#include <NTPClient.h>
#include <ESPAsyncWebServer.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
#include <ArduinoHA.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <EEPROM.h>
#include <async.h>

//#include <esp32-hal-psram.h>

String prefix = "";
char* deviceName = "Alarm Map";
char* deviceBroadcastName = "alarm-map";
char* softwareVersion = "2.10d";
//byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x38, 0x4A}; //test
byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x00, 0x4A}; //big
//byte mac[] = {0x00, 0x10, 0xFA, 0x6E, 0x10, 0x4A}; //small

// ============ НАЛАШТУВАННЯ ============

//Налаштування WiFi
char* wifiSSID = ""; //Назва мережі WiFi
char* wifiPassword = ""; //Пароль  WiFi
char* apSSID = "AlarmMap"; //Назва точки доступу щоб переналаштувати WiFi
char* apPassword = ""; //Пароль від точки доступу щоб переналаштувати WiFi. Пусте - без пароля
bool wifiStatusBlink = true; //Статуси wifi на мапі
int apModeConnectionTimeout = 120; //Час в секундах на роботу точки доступу

//Налштування Home Assistant
bool enableHA = false;
int mqttPort = 1883;
char* mqttUser = "";
char* mqttPassword = "";
char* brokerAddress = "";

//Налштування яскравості
int brightness = 100; //Яскравість %

float brightnessLightGreen = 100; //Яскравість відбою тривог%
float brightnessGreen = 75; //Яскравість зон без тривог%
float brightnessOrange = 75; //Яскравість зон з новими тривогами %
float brightnessRed = 100; //Яскравість зон з тривогами%

//Налаштування авто-яскравості
bool autoBrightness = true; //Ввімкнена/вимкнена авто яскравість
const int day = 8; //Початок дня
const int night = 23; //Початок ночі
const int dayBrightness = 100; //Денна яскравість %
const int nightBrightness = 20; //Нічна яскравість %

bool autoSwitchMap = false; //Автоматичне переключення карти на режим тривоги при початку тривоги в вибраній області

int mapModeInit = 2; //Режим мапи
int mapMode = 1;

//Майбутній функціонал, не працює
int blinkDistricts[] = {
  7,
  8
};

//Модуляція
int modulationMode = 2; //Режим модуляції
int modulationLevel = 50; //Рівень модуляції
int modulationStep = 5; //Крок модуляції
int modulationTime = 500; //Тривалість модуляції
int modulationCount = 3; //Кількість модуляцій в циклі
bool modulationAlarmsOffNew = true; //Відбій тривог в модуляції
bool modulationAlarmsOff = false; //Зони без тривог в модуляції
bool modulationAlarmsNew = true; //Зони нових тривог в модуляції
bool modulationAlarms = false; //Зони тривог в модуляції
bool modulationSelected = false; //Майбутній функціонал, не працює

int newAlarmPeriod = 300; //Час індикації нових тривог

//Дісплей
bool autoSwitchDisplay = false; //Автоматичне переключення дісплея на режим тривоги при початку тривоги в вибраній області

int displayModeInit = 1;
int displayMode = 1; //Режим дісплея
bool displayWarningStatus = false; //Статуси wifi на дісплеі

//Погода
const char* apiKey = ""; //API погоди
float minTemp = 5.0; // мінімальна температура у градусах Цельсія для налашутвання діапазону кольорів
float maxTemp = 30.0; // максимальна температура у градусах Цельсія для налашутвання діапазону кольорів

//Домашній регіон
int stateId = 8;

//Буззер
int buzzerMode = 1; //Режим буззера
int buzzerTone = 100;
int buzzerDuration = 300;
int buzzerCount = 3;
int buzzerTempo = 100;
int buzzerStartSound = 4;
int buzzerEndSound = 3;

//Кнопка
int touchMode = 1; //Режим кнопки

//Налаштуванння повернення в режим тривог
int statesIdsAlarmCheck[] PROGMEM = {
  0,
  0,
  0,
  0,
  0,
  0,
  0,

  1,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
};

static String states[] PROGMEM = {
  "Закарпатська область",
  "Івано-Франківська область",
  "Тернопільська область",
  "Львівська область",
  "Волинська область",
  "Рівненська область",
  "Житомирська область",

  "Київська область",
  "Чернігівська область",
  "Сумська область",
  "Харківська область",
  "Луганська область",
  "Донецька область",
  "Запорізька область",
  "Херсонська область",
  "АР Крим",
  "Одеська область",
  "Миколаївська область",
  "Дніпропетровська область",
  "Полтавська область",
  "Черкаська область",
  "Кіровоградська область",
  "Вінницька область",
  "Хмельницька область",
  "Чернівецька область"
};

//Погодні IDS
int statesIdsWeather[] PROGMEM = {
  690548,
  707471,
  691650,
  702550,
  702569,
  695594,
  686967,

  703448,
  710735,
  692194,
  706483,
  702658,
  709717,
  687700,
  706448,
  703883,
  698740,
  700569,
  709930,
  696643,
  710719,
  705811,
  689558,
  706369,
  710719
};

//Прапор
static int flagColor[] PROGMEM = {
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_AQUA,
  HUE_AQUA,
  HUE_AQUA,
  HUE_AQUA,

  HUE_AQUA,
  HUE_AQUA,
  HUE_AQUA,
  HUE_AQUA,
  HUE_AQUA,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_AQUA,
  HUE_AQUA,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW,
  HUE_YELLOW
};

#define LED_PIN         13
#define NUM_LEDS        25
#define LED_TYPE        WS2812
#define COLOR_ORDER     GRB

#define BUZZER_PIN      16

#define TOUCH_PIN       18

#define DISPLAY_WIDTH   128
#define DISPLAY_HEIGHT  32
// ======== КІНЕЦь НАЛАШТУВАННЯ =========

CRGB leds[NUM_LEDS];
CRGB ledWeatherColor[NUM_LEDS];

Adafruit_SSD1306 display(DISPLAY_WIDTH, DISPLAY_HEIGHT, &Wire, -1);

AsyncWebServer aserver(80);

Async asyncEngine = Async();

DynamicJsonDocument doc(30000);

const int eepromBrightnessAddress = 20;
const int eepromMapModeAddress = 21;
const int eepromDisplayModeAddress = 22;
const int eepromModulationModeAddress = 23;
const int eepromBuzzerModeAddress = 24;
const int eepromButtonModeAddress = 25;

String baseURL = "https://vadimklimenko.com/map/statuses.json";

WiFiClient client;
WiFiManager wm;
WiFiUDP ntpUDP;
HTTPClient http;
NTPClient timeClient(ntpUDP, "ua.pool.ntp.org", 7200);


String haBrightnessString = String("alarm_map") + prefix + "_brightness";
const char* haBrightnessChar = haBrightnessString.c_str();
String haMapModeString = String("alarm_map") + prefix + "_map_mode";
const char* haMapModeChar = haMapModeString.c_str();
String haDisplayModeString = String("alarm_map") + prefix + "_display_mode";
const char* haDisplayModeChar = haDisplayModeString.c_str();
String haModulationModeString = String("alarm_map") + prefix + "_modulation_mode";
const char* haModulationModeChar = haModulationModeString.c_str();
String haUptimeString = String("alarm_map") + prefix + "_uptime";
const char* haUptimeChar = haUptimeString.c_str();
String haWifiSignalString = String("alarm_map") + prefix + "_wifi_signal";
const char* haWifiSignalChar = haWifiSignalString.c_str();
String haFreeMemoryString = String("alarm_map") + prefix + "_free_memory";
const char* haFreeMemoryChar = haFreeMemoryString.c_str();
String haUsedMemoryString = String("alarm_map") + prefix + "_used_memory";
const char* haUsedMemoryChar = haUsedMemoryString.c_str();
String haMapModeCurrentString = String("alarm_map") + prefix + "_map_mode_current";
const char* haMapModeCurrentChar = haMapModeCurrentString.c_str();
String haDisplayModeCurrentString = String("alarm_map") + prefix + "_display_mode_current";
const char* haDisplayModeCurrentChar = haDisplayModeCurrentString.c_str();
String haBuzzerModeString = String("alarm_map") + prefix + "_buzzer_mode";
const char* haBuzzerModeChar = haBuzzerModeString.c_str();
String haButtonModeString = String("alarm_map") + prefix + "_button_mode";
const char* haButtonModeChar = haButtonModeString.c_str();

HADevice device(mac, sizeof(mac));
HAMqtt mqtt(client, device, 14);
HANumber haBrightness(haBrightnessChar);
HASelect haMapMode(haMapModeChar);
HASelect haDisplayMode(haDisplayModeChar);
HASelect haModulationMode(haModulationModeChar);
HASensorNumber haUptime(haUptimeChar);
HASensorNumber haWifiSignal(haWifiSignalChar);
HASensorNumber haFreeMemory(haFreeMemoryChar);
HASensorNumber haUsedMemory(haUsedMemoryChar);
HASensor haMapModeCurrent(haMapModeCurrentChar);
HASensor haDisplayModeCurrent(haDisplayModeCurrentChar);
HASelect  haBuzzerMode(haBuzzerModeChar);
HASelect  haButtonMode(haButtonModeChar);

char* mapModes [] = {
  "Вимкнено",
  "Tpивoгa",
  "Погода",
  "Прапор"
};

char* displayModes [] = {
  "Вимкнено",
  "Годинник",
  "Tpивoгa",
  "Погода"
};

char* modulationModes [] = {
  "Вимкнено",
  "Moдyляцiя",
  "Пyльcaцiя"
};

char* buzzerModes [] = {
  "Вимкнено",
  "День",
  "День+Hiчь"
};

char* buttonModes [] = {
  "Вимкнено",
  "Мапа",
  "Дicплeй",
  "Moдyляцiя",
  "Буззер"
};

int alarmsPeriod = 5000;
int weatherPeriod = 600000;
unsigned long lastAlarmsTime;
unsigned long lastWeatherTime;
static bool firstAlarmsUpdate = true;
static bool firstWeatherUpdate = true;
int alarmsNowCount = 0;
static bool wifiConnected;
static int ledColor[NUM_LEDS];

bool isAlarm = false;
bool isDaylightSaving = false;
bool isBuzzerStart = true;
bool isBuzzerEnd = true;
bool buzzerSound = true;
bool isDay;

float currentTemp;
String currentWeather;

static bool mapModeFirstUpdate1 = true;
static bool mapModeFirstUpdate2 = true;
static bool mapModeFirstUpdate3 = true;
static bool mapModeFirstUpdate4 = true;

long timeDifference;

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

#define NOTE_B0  31
#define NOTE_C1  33
#define NOTE_CS1 35
#define NOTE_D1  37
#define NOTE_DS1 39
#define NOTE_E1  41
#define NOTE_F1  44
#define NOTE_FS1 46
#define NOTE_G1  49
#define NOTE_GS1 52
#define NOTE_A1  55
#define NOTE_AS1 58
#define NOTE_B1  62
#define NOTE_C2  65
#define NOTE_CS2 69
#define NOTE_D2  73
#define NOTE_DS2 78
#define NOTE_E2  82
#define NOTE_F2  87
#define NOTE_FS2 93
#define NOTE_G2  98
#define NOTE_GS2 104
#define NOTE_A2  110
#define NOTE_AS2 117
#define NOTE_B2  123
#define NOTE_C3  131
#define NOTE_CS3 139
#define NOTE_D3  147
#define NOTE_DS3 156
#define NOTE_E3  165
#define NOTE_F3  175
#define NOTE_FS3 185
#define NOTE_G3  196
#define NOTE_GS3 208
#define NOTE_A3  220
#define NOTE_AS3 233
#define NOTE_B3  247
#define NOTE_C4  262
#define NOTE_CS4 277
#define NOTE_D4  294
#define NOTE_DS4 311
#define NOTE_E4  330
#define NOTE_F4  349
#define NOTE_FS4 370
#define NOTE_G4  392
#define NOTE_GS4 415
#define NOTE_A4  440
#define NOTE_AS4 466
#define NOTE_B4  494
#define NOTE_C5  523
#define NOTE_CS5 554
#define NOTE_D5  587
#define NOTE_DS5 622
#define NOTE_E5  659
#define NOTE_F5  698
#define NOTE_FS5 740
#define NOTE_G5  784
#define NOTE_GS5 831
#define NOTE_A5  880
#define NOTE_AS5 932
#define NOTE_B5  988
#define NOTE_C6  1047
#define NOTE_CS6 1109
#define NOTE_D6  1175
#define NOTE_DS6 1245
#define NOTE_E6  1319
#define NOTE_F6  1397
#define NOTE_FS6 1480
#define NOTE_G6  1568
#define NOTE_GS6 1661
#define NOTE_A6  1760
#define NOTE_AS6 1865
#define NOTE_B6  1976
#define NOTE_C7  2093
#define NOTE_CS7 2217
#define NOTE_D7  2349
#define NOTE_DS7 2489
#define NOTE_E7  2637
#define NOTE_F7  2794
#define NOTE_FS7 2960
#define NOTE_G7  3136
#define NOTE_GS7 3322
#define NOTE_A7  3520
#define NOTE_AS7 3729
#define NOTE_B7  3951
#define NOTE_C8  4186
#define NOTE_CS8 4435
#define NOTE_D8  4699
#define NOTE_DS8 4978
#define REST      0

int imperialMarch[] = {
  NOTE_A4,4, NOTE_A4,4, NOTE_A4,4, NOTE_F4,-8, NOTE_C5,16,
  NOTE_A4,4, NOTE_F4,-8, NOTE_C5,16, NOTE_A4, 2,
};

int ukrainianAnthem[] = {
  NOTE_D5, 3, NOTE_D5, 8, NOTE_D5, 8, NOTE_C5, 8, NOTE_D5, 8, NOTE_DS5, 8, NOTE_F5, 3,
  NOTE_DS5, 8, NOTE_D5, 4, NOTE_C5, 4,
  NOTE_AS4, 4, NOTE_D5, 4, NOTE_A4, 4, NOTE_D5, 4, NOTE_G4, 2, NOTE_G4, 2,
};

int startrek[] = {
  NOTE_D4, -8, NOTE_G4, 16, NOTE_C5, -4,
  NOTE_B4, 8, NOTE_G4, -16, NOTE_E4, -16, NOTE_A4, -16,
  NOTE_D5, 2,
};

int nokia[] = {
  NOTE_E5, 16, NOTE_D5, 16, NOTE_FS4, 8, NOTE_GS4, 8,
  NOTE_CS5, 16, NOTE_B4, 16, NOTE_D4, 8, NOTE_E4, 8,
  NOTE_B4, 16, NOTE_A4, 16, NOTE_CS4, 8, NOTE_E4, 8,
  NOTE_A4, 4,
};


void initHA() {
  IPAddress brokerAddr;
  if (!brokerAddr.fromString(brokerAddress)) {
    Serial.println("Invalid IP address format!");
    enableHA = false;
  }
  if (enableHA) {
    device.setName(deviceName);
    device.setSoftwareVersion(softwareVersion);
    device.setManufacturer("JAAM");
    device.setModel("Ukraine Alarm Map Informer");
    device.enableSharedAvailability();

    haBrightness.onCommand(onHaBrightnessCommand);
    haBrightness.setIcon("mdi:brightness-percent");
    haBrightness.setName(haBrightnessChar);
    haBrightness.setCurrentState(brightness);

    haMapMode.setOptions("Off;Alarms;Weather;Flag");
    haMapMode.onCommand(onHaMapModeCommand);
    haMapMode.setIcon("mdi:map");
    haMapMode.setName(haMapModeChar);
    haMapMode.setCurrentState(mapModeInit-1);

    haMapModeCurrent.setIcon("mdi:map");
    haMapModeCurrent.setName(haMapModeCurrentChar);
    haMapModeCurrent.setValue(mapModes[mapMode-1]);

    haDisplayMode.setOptions("Off;Clock;Alarms;Weather");
    haDisplayMode.onCommand(onHaDisplayModeCommand);
    haDisplayMode.setIcon("mdi:clock-digital");
    haDisplayMode.setName(haDisplayModeChar);
    haDisplayMode.setCurrentState(displayModeInit-1);

    haDisplayModeCurrent.setIcon("mdi:clock-digital");
    haDisplayModeCurrent.setName(haDisplayModeCurrentChar);
    haDisplayModeCurrent.setValue(displayModes[displayMode-1]);

    haModulationMode.setOptions("Off;Modulation;Blink");
    haModulationMode.onCommand(onHaModulationModeCommand);
    haModulationMode.setIcon("mdi:alarm-light");
    haModulationMode.setName(haModulationModeChar);
    haModulationMode.setCurrentState(modulationMode-1);

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

    haBuzzerMode.setOptions("Off;Day;Day+Night");
    haBuzzerMode.onCommand(onBuzzerModeCommand);
    haBuzzerMode.setIcon("mdi:timer-music");
    haBuzzerMode.setName(haBuzzerModeChar);
    haBuzzerMode.setCurrentState(buzzerMode-1);

    haButtonMode.setOptions("Off;Map;Display;Modulation;Buzzer");
    haButtonMode.onCommand(onButtonModeCommand);
    haButtonMode.setIcon("mdi:gesture-tap-button");
    haButtonMode.setName(haButtonModeChar);
    haButtonMode.setCurrentState(touchMode-1);

    device.enableLastWill();
    mqtt.begin(brokerAddr,mqttPort,mqttUser,mqttPassword);
    Serial.println("mqtt connected");
  }
}

void onButtonModeCommand(int8_t index, HASelect* sender)
{
    switch (index) {
    case 0:
        touchMode = 1;
        break;
    case 1:
        touchMode = 2;
        break;
    case 2:
        touchMode = 3;
        break;
    case 3:
        touchMode = 4;
        break;
    case 4:
        touchMode = 5;
        break;
    default:
        // unknown option
        return;
    }
    EEPROM.write(eepromButtonModeAddress, touchMode);
    EEPROM.commit();
    Serial.println("touchMode commited to eeprom");
    sender->setState(index);
}

void onBuzzerModeCommand(int8_t index, HASelect* sender)
{
    switch (index) {
    case 0:
        buzzerMode = 1;
        break;
    case 1:
        buzzerMode = 2;
        break;
    case 2:
        buzzerMode = 3;
        break;
    default:
        // unknown option
        return;
    }
    EEPROM.write(eepromBuzzerModeAddress, buzzerMode);
    EEPROM.commit();
    Serial.println("BuzzerMode commited to eeprom");
    sender->setState(index);
}

void onHaBrightnessCommand(HANumeric haBrightness, HANumber* sender)
{
    if (!haBrightness.isSet()) {
        //Serial.println('number not set');
    } else {
        int8_t numberInt8 = haBrightness.toInt8();
        autoBrightness = false;
        brightness = numberInt8;
        EEPROM.write(eepromBrightnessAddress, brightness);
        EEPROM.commit();
        Serial.println("brightness commited to eeprom");
        FastLED.setBrightness(2.55 * brightness);
        FastLED.show();
        //Serial.print('brightness from HA: ');
        //Serial.println(numberInt8);
    }
    sender->setState(haBrightness);
}

void onHaMapModeCommand(int8_t index, HASelect* sender)
{
    switch (index) {
    case 0:
        mapModeInit = 1;
        break;
    case 1:
        mapModeInit = 2;
        break;
    case 2:
        mapModeInit = 3;
        break;
    case 3:
        mapModeInit = 4;
        break;
    default:
        // unknown option
        return;
    }
    mapMode = mapModeInit;
    mapInfo();
    EEPROM.write(eepromMapModeAddress, mapModeInit);
    EEPROM.commit();
    Serial.println("mapModeInit commited to eeprom");
    sender->setState(index);
}

void onHaDisplayModeCommand(int8_t index, HASelect* sender)
{
    switch (index) {
    case 0:
        displayModeInit = 1;
        break;
    case 1:
        displayModeInit = 2;
        break;
    case 2:
        displayModeInit = 3;
        break;
    case 3:
        displayModeInit = 4;
        break;
    default:
        // unknown option
        return;
    }
    displayMode = displayModeInit;
    displayInfo();
    EEPROM.write(eepromDisplayModeAddress, displayModeInit);
    EEPROM.commit();
    Serial.println("displayModeInit commited to eeprom");
    sender->setState(index);
}

void onHaModulationModeCommand(int8_t index, HASelect* sender)
{
    switch (index) {
    case 0:
        modulationMode = 1;
        break;
    case 1:
        modulationMode = 2;
        break;
    case 2:
        modulationMode = 3;
        break;
    default:
        // unknown option
        return;
    }
    EEPROM.write(eepromModulationModeAddress, modulationMode);
    EEPROM.commit();
    Serial.println("modulationMode commited to eeprom");
    sender->setState(index);
}

void setupRouting() {
  aserver.on("/", HTTP_GET, handleRoot);
  aserver.on("/save", HTTP_POST, handleSave);
  aserver.begin();
}

void handleRoot(AsyncWebServerRequest* request){
  String html = "<html><head>";
  html += "<title>Керування мапою тривог</title>";
  html += "<meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1, shrink-to-fit=no'>";
  html += "<link rel='stylesheet' href='https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'>";
  html += "</head><body>";
  html += "<div class='container'>";
  html += "<h1 class='mt-4'>Параметри конфігурації</h1>";
  html += "<h4 class='mt-4'>Локальна IP-адреса: ";
  html += WiFi.localIP().toString();
  html += "</h4>";
  html += "<h4 class='mt-4'>Версія прошивки: ";
  html += softwareVersion;
  html += "</h4>";
  html += "<form id='configForm' action='/save' method='POST'>";
  html += "<div class='form-group'>";
  html += "<label for='brightness'>Яскравість:</label>";
  html += "<input type='range' class='form-control-range' id='brightness' name='brightness' min='0' max='100' value='" + String(brightness) + "'>";
  html += "<div class='slider-value'>" + String(brightness) + "</div>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='mapMode'>Режим мапи:</label>";
  html += "<select class='form-control' id='mapMode' name='map_mode'>";
  html += "<option value='1'";
  if (mapModeInit == 1) html += " selected";
  html += ">Вимкнена</option>";
  html += "<option value='2'";
  if (mapModeInit == 2) html += " selected";
  html += ">Тривоги</option>";
  html += "<option value='3'";
  if (mapModeInit == 3) html += " selected";
  html += ">Погода</option>";
  html += "<option value='4'";
  if (mapModeInit == 4) html += " selected";
  html += ">Прапор</option>";
  html += "</select>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='displayMode'>Режим дісплея:</label>";
  html += "<select class='form-control' id='displayMode' name='display_mode'>";
  html += "<option value='1'";
  if (displayModeInit == 1) html += " selected";
  html += ">Вимкнений</option>";
  html += "<option value='2'";
  if (displayModeInit == 2) html += " selected";
  html += ">Поточний час</option>";
  html += "<option value='3'";
  if (displayModeInit == 3) html += " selected";
  html += ">Час тривог</option>";
  html += "<option value='4'";
  if (displayModeInit == 4) html += " selected";
  html += ">Погода</option>";
  html += "</select>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='modulationMode'>Режим модуляції:</label>";
  html += "<select class='form-control' id='modulationMode' name='modulation_mode'>";
  html += "<option value='1'";
  if (modulationMode == 1) html += " selected";
  html += ">Вимкнений</option>";
  html += "<option value='2'";
  if (modulationMode == 2) html += " selected";
  html += ">Модуляція</option>";
  html += "<option value='3'";
  if (modulationMode == 3) html += " selected";
  html += ">Пульсація</option>";
  html += "</select>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='buzzerMode'>Режим буззера:</label>";
  html += "<select class='form-control' id='buzzerMode' name='buzzer_mode'>";
  html += "<option value='1'";
  if (buzzerMode == 1) html += " selected";
  html += ">Вимкнений</option>";
  html += "<option value='2'";
  if (buzzerMode == 2) html += " selected";
  html += ">Ввімкнений вдень</option>";
  html += "<option value='3'";
  if (buzzerMode == 3) html += " selected";
  html += ">Ввімкнений всю добу</option>";
  html += "</select>";
  html += "</div>";
  html += "<div class='form-group'>";
  html += "<label for='buttonMode'>Режим кнопки:</label>";
  html += "<select class='form-control' id='buttonMode' name='button_mode'>";
  html += "<option value='1'";
  if (touchMode == 1) html += " selected";
  html += ">Вимкнена</option>";
  html += "<option value='2'";
  if (touchMode == 2) html += " selected";
  html += ">Перемикання мапи</option>";
  html += "<option value='3'";
  if (touchMode == 3) html += " selected";
  html += ">Перемикання дисплея</option>";
  html += "<option value='4'";
  if (touchMode == 4) html += " selected";
  html += ">Перемикання модуляції</option>";
  html += "<option value='5'";
  if (touchMode == 5) html += " selected";
  html += ">Перемикання буззера</option>";
  html += "</select>";
  html += "</div>";
  html += "<button type='submit' class='btn btn-primary'>Зберегти налаштування</button>";
  html += "</form>";
  html += "</div>";
  html += "<div class='modal fade' id='confirmationModal' tabindex='-1' role='dialog' aria-labelledby='confirmationModalLabel' aria-hidden='true'>";
  html += "<div class='modal-dialog' role='document'>";
  html += "<div class='modal-content'>";
  html += "<div class='modal-header'>";
  html += "<h5 class='modal-title' id='confirmationModalLabel'>Підтвердження</h5>";
  html += "<button type='button' class='close' data-dismiss='modal' aria-label='Close'>";
  html += "<span aria-hidden='true'>&times;</span>";
  html += "</button>";
  html += "</div>";
  html += "<div class='modal-body'>";
  html += "<p>Налаштування збережено успішно.</p>";
  html += "</div>";
  html += "</div>";
  html += "</div>";
  html += "</div>";
  html += "<script src='https://code.jquery.com/jquery-3.5.1.slim.min.js'></script>";
  html += "<script src='https://cdn.jsdelivr.net/npm/@popperjs/core@1.16.1/dist/umd/popper.min.js'></script>";
  html += "<script src='https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js'></script>";
  html += "<script>";
  html += "$(document).ready(function() {";
  html += "var slider = $('#brightness');";
  html += "var sliderValue = $('.slider-value');";
  html += "slider.on('input', function() {";
  html += "sliderValue.text(slider.val());";
  html += "});";
  html += "$('#configForm').on('submit', function(e) {";
  html += "e.preventDefault();";
  html += "var form = $(this);";
  html += "var modal = $('#confirmationModal');";
  html += "modal.modal('show');";
  html += "setTimeout(function() {";
  html += "modal.modal('hide');";
  html += "form.unbind('submit').submit();";
  html += "}, 3000);";
  html += "});";
  html += "});";
  html += "</script>";
  html += "</body></html>";

  request->send(200, "text/html", html);
}

void handleSave(AsyncWebServerRequest* request){
  if (request->hasParam("brightness", true)){
    autoBrightness = false;
    brightness = request->getParam("brightness", true)->value().toInt();
    EEPROM.write(eepromBrightnessAddress, brightness);
    EEPROM.commit();
    Serial.println("brightness commited to eeprom");
    FastLED.setBrightness(2.55 * brightness);
    FastLED.show();
    if (enableHA) {
      haBrightness.setState(brightness);
    }
  }
  if (request->hasParam("map_mode", true)){
    mapModeInit = request->getParam("map_mode", true)->value().toInt();
    if (enableHA) {
      haMapMode.setState(mapModeInit-1);
    }
    mapMode = mapModeInit;
    mapInfo();
    EEPROM.write(eepromMapModeAddress, mapModeInit);
    EEPROM.commit();
    Serial.println("mapModeInit commited to eeprom");
  }
  if (request->hasParam("display_mode", true)){
    displayModeInit = request->getParam("display_mode", true)->value().toInt();
    if (enableHA) {
      haDisplayMode.setState(displayModeInit-1);
    }
    displayMode = displayModeInit;
    displayInfo();
    EEPROM.write(eepromDisplayModeAddress, displayModeInit);
    EEPROM.commit();
    Serial.println("displayModeInit commited to eeprom");
  }
  if (request->hasParam("modulation_mode", true)){
    modulationMode = request->getParam("modulation_mode", true)->value().toInt();
    if (enableHA) {
      haModulationMode.setState(modulationMode-1);
    }
    EEPROM.write(eepromModulationModeAddress, modulationMode);
    EEPROM.commit();
    Serial.println("modulationMode commited to eeprom");
  }
  if (request->hasParam("buzzer_mode", true)){
    buzzerMode = request->getParam("buzzer_mode", true)->value().toInt();
    if (enableHA) {
      haBuzzerMode.setState(buzzerMode-1);
    }
    EEPROM.write(eepromBuzzerModeAddress, buzzerMode);
    EEPROM.commit();
    Serial.println("buzzerMode commited to eeprom");
  }
  if (request->hasParam("button_mode", true)){
    touchMode = request->getParam("button_mode", true)->value().toInt();
    if (enableHA) {
      haButtonMode.setState(touchMode-1);
    }
    EEPROM.write(eepromButtonModeAddress, touchMode);
    EEPROM.commit();
    Serial.println("touchMode commited to eeprom");
  }
  request->redirect("/");
}


void initWiFi() {
  Serial.println("WiFi init");
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSSID, wifiPassword);
  int connectionAttempts = 1;
  while (WiFi.status() != WL_CONNECTED) {
    //Serial.print("connectionAttempts: ");
    //Serial.println(connectionAttempts);
    if(displayWarningStatus) {
      display.setCursor(0, 0);
      display.clearDisplay();
      display.setTextSize(1);
      display.print(utf8cyr("WiFi пiдключення: "));
      display.println(connectionAttempts);
      display.setTextSize(2);
      DisplayCenter(wifiSSID,3);
    }
    if(wifiStatusBlink) {
      colorFill(HUE_RED, 255);
      FlashAll(10,1);
    }
    delay(2000);
    //Serial.println("Connecting to WiFi...");
    //Serial.print("WIFI status: ");
    //Serial.println(WiFi.status());
    if (WiFi.status() == WL_CONNECT_FAILED) {
      //Serial.println("Connection failed. Starting AP mode.");
      startAPMode();
      break;
    }
    if (connectionAttempts == 10) {
      break;
    }
    connectionAttempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnectionSuccess();
  } else {
    startAPMode();
  }
}

void wifiConnectionSuccess() {
  if(displayWarningStatus) {
    display.setCursor(0, 0);
    display.clearDisplay();
    display.setTextSize(1);
    display.print("IP: ");
    display.println(WiFi.localIP());
    display.setTextSize(2);
    DisplayCenter("пiдключено",10);

  }
  if(wifiStatusBlink) {
    colorFill(HUE_GREEN, 255);
    FlashAll(10,3);
    delay(3000);
  }
  Serial.println("Connected to WiFi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void startAPMode() {
  Serial.println("Start AP");
  if(displayWarningStatus) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.print("AP: ");
    display.println(apSSID);
    display.print(utf8cyr("Пароль: "));
    display.println(apPassword);
    display.display();
  }
  if(wifiStatusBlink) {
    colorFill(HUE_YELLOW, 255);
    FlashAll(10,3);
  }
  //Serial.println("AP mode started");
  //Serial.print("AP SSID: ");
  //Serial.println(apSSID);
  //Serial.print("AP Password: ");
  //Serial.println(apPassword);
  bool connection;
  wm.setTimeout(apModeConnectionTimeout);
  connection = wm.autoConnect(apSSID, apPassword);
  if (!connection) {
    if(displayWarningStatus) {
      display.clearDisplay();
      display.setTextSize(1);
      display.println(utf8cyr("Помилка WIFI"));
      display.println(utf8cyr("Перезавантаження... "));
      //Serial.println("Помилка підключення");
    }
    delay(5000);
    ESP.restart();
  }
  else {
    wifiConnectionSuccess();
  }
}

void Modulation() {
  Serial.println("Modulation: start");
  int localModulationTime = modulationTime / 2 / ((100-modulationLevel) / modulationStep);
  int selectedStates[NUM_LEDS];
  for (int i = 0; i < NUM_LEDS; i++) {
    selectedStates[i] = 0;
  }
  if(modulationSelected) {
    for (int i = 0; i < sizeof(blinkDistricts) / sizeof(int); i++) {
      int position = blinkDistricts[i];
      selectedStates[position] = 1;
    }
  }
  for (int i = 0; i < modulationCount; i++) {
    bool fadeCycleEnded = false;
    bool rizeCycleEnded = false;
    int stepBrightness = 100;
    while (!fadeCycleEnded || !rizeCycleEnded) {
      for (int i = 0; i < NUM_LEDS; i++) {
        switch (ledColor[i]) {
          case 1: if (modulationAlarms || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 2.55 * stepBrightness * brightnessRed / 100); break;} else { break;}
          case 2: if (modulationAlarmsNew || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * stepBrightness * brightnessOrange / 100); break;} else { break;}
          case 3: if (modulationAlarmsOff || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 255, 2.55 * stepBrightness * brightnessGreen / 100); break;} else { break;}
          case 4: if (modulationAlarmsOffNew || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 160, 2.55 * stepBrightness * brightnessLightGreen / 100); break;} else { break;}
        }
      }
      FastLED.show();
      if (fadeCycleEnded){
        stepBrightness += modulationStep;
      } else{
        stepBrightness -= modulationStep;
      }
      if (stepBrightness < modulationLevel) {
        fadeCycleEnded = true;
      }
      if (stepBrightness > 100) {
        rizeCycleEnded = true;
      }
      delay(localModulationTime);
    }
  }
  //Serial.println("Modulation: end");
}

void movingBlink(int color, int count) {
  for(int i = 0; i < count; i++) {
    for(int dot = 0; dot < NUM_LEDS; dot++) {
      leds[dot] = CHSV(color, 255, 255);
      FastLED.show();
      delay(20);
      leds[dot] = CHSV(color, 255, 0);
      FastLED.show();
    }
  }
}

void colorFill(int color, int fillBrightness) {
  for(int dot = 0; dot < NUM_LEDS; dot++) {
    leds[dot] = CHSV(color, 255, fillBrightness);
  }
  FastLED.show();
}

void Blink() {
  Serial.println("Blink start ");
  int localModulationTime = modulationTime / 2;
  int selectedStates[NUM_LEDS];
  for (int i = 0; i < NUM_LEDS; i++) {
    selectedStates[i] = 0;
  }
  if(modulationSelected) {
    for (int i = 0; i < sizeof(blinkDistricts) / sizeof(int); i++) {
      int position = blinkDistricts[i];
      selectedStates[position] = 1;
    }
  }
  for (int i = 0; i < modulationCount; i++) {
    for (int i = 0; i < NUM_LEDS; i++) {
        switch (ledColor[i]) {
          case 1: if (modulationAlarms || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 0); break;} else { break;}
          case 2: if (modulationAlarmsNew || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 0); break;} else { break;}
          case 3: if (modulationAlarmsOff || selectedStates[i]) {leds[i] =CHSV(HUE_GREEN, 255, 0); break;} else { break;}
          case 4: if (modulationAlarmsOffNew || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 160, 0); break;} else { break;}
        }
    }
    FastLED.show();
    delay(localModulationTime);
    for (int i = 0; i < NUM_LEDS; i++) {
        switch (ledColor[i]) {
          case 1: if (modulationAlarms || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 2.55 * brightnessRed); break;} else { break;}
          case 2: if (modulationAlarmsNew || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * brightnessOrange); break;} else { break;}
          case 3: if (modulationAlarmsOff || selectedStates[i]) {leds[i] =CHSV(HUE_GREEN, 255, 2.55 * brightnessGreen); break;} else { break;}
          case 4: if (modulationAlarmsOffNew || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 160, 2.55 * brightnessLightGreen); break;} else { break;}
        }
    }
    FastLED.show();
    delay(localModulationTime);
  }
  //Serial.println("End blink");
}

void Flag(int wait) {
  Serial.println("Flag start");
  for (int dot = 0; dot <= NUM_LEDS; dot++) {
    if (flagColor[dot] == HUE_AQUA) {
      leds[dot] = CHSV(flagColor[dot], 255, 255);
      FastLED.show();
      delay(wait);
    }
  }
  for (int dot = NUM_LEDS; dot >= 0; dot--) {
    if (flagColor[dot] == HUE_YELLOW) {
      leds[dot] = CHSV(flagColor[dot], 255, 255);
      FastLED.show();
      delay(wait);
    }
  }
}

void FlashAll(int wait, int count) {
  for(int i = 0; i < count; i++) {
    for(int dot = 0; dot <= NUM_LEDS; dot++) {
      CRGB pixel = leds[dot];
      leds[dot] = CHSV(0, 0, 255);
      FastLED.show();
      delay(wait);
      leds[dot] = pixel;
      FastLED.show();
    }
  }
}

void FlashLed(int dot, int wait, int count) {
  for(int i = 0; i < count; i++) {
    CRGB pixel = leds[dot];
    leds[dot] = CHSV(0, 00, 255);
    FastLED.show();
    delay(wait);
    leds[dot] = pixel;
    FastLED.show();
  }
}

void displayInfo() {
  //timeClient.update();
  int hour = timeClient.getHours();
  int minute = timeClient.getMinutes();

  if (displayMode == 1) {
    Serial.println("Display mode 1");
    display.clearDisplay();
    display.display();
  }
  if (displayMode == 2) {
    Serial.println("Display mode 2");
    int day = timeClient.getDay();
    String daysOfWeek[] = {"Недiля", "Понедiлок", "Вiвторок", "Середа", "Четвер", "П\'ятниця", "Субота"};
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

    display.setTextSize(3);
    DisplayCenter(time,7);
  }
  if (displayMode == 3) {
    Serial.println("Display mode 3");
    int days = timeDifference / 86400;  // Number of seconds in a day
    int hours = (timeDifference % 86400) / 3600;
    int minutes = (timeDifference % 3600) / 60;
    int seconds = (timeDifference % 3600) % 60;

    String time = "";
    if (days > 0){
      time += days;
      time += "d ";
    }
    if (hours < 10) time += "0";
    time += hours;
    time += ":";
    if (minutes < 10) time += "0";
    time += minutes;
    //time += "m";
    // if (seconds < 10) time += "0";
    // time += seconds;
    display.setCursor(0, 0);
    display.clearDisplay();
    display.setTextSize(1);
    if (isAlarm){
      display.println(utf8cyr("Тривалiсть тривоги:"));
    }else{
      display.println(utf8cyr("Час без тривоги:"));
    }
    display.setTextSize(2);
    // display.println(time);
    // display.display();
    DisplayCenter(time,6);
  }
  if (displayMode == 4) {
    Serial.println("Display mode 4");
    int day = timeClient.getDay();
    display.setCursor(0, 0);
    display.clearDisplay();
    display.setTextSize(1);
    display.println(utf8cyr(currentWeather));
    String time = "";
    char roundedTemp[4];
    dtostrf(currentTemp, 3, 1, roundedTemp);
    time += roundedTemp;
    time += " C";
    display.setTextSize(2);
    DisplayCenter(time,6);
  }
}

void DisplayCenter(String text, int bound) {
    int16_t x;
    int16_t y;
    uint16_t width;
    uint16_t height;
    display.getTextBounds(text, 0, 0, &x, &y, &width, &height);
    display.setCursor(((DISPLAY_WIDTH - width) / 2), ((DISPLAY_HEIGHT - height) / 2) + bound);
    display.println(utf8cyr(text));
    display.display();
  }

void initFastLED() {
    //FastLED.setMaxPowerInVoltsAndMilliamps(5, 20);
    FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
    FastLED.setBrightness(2.55 * brightness);
    FastLED.clear();
    FastLED.show();
}

void initDisplay() {

  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.clearDisplay();
  display.setTextColor(WHITE);
  int16_t centerX = (DISPLAY_WIDTH - 32) / 2;    // Calculate the X coordinate
  int16_t centerY = (DISPLAY_HEIGHT - 32) / 2;
  display.drawBitmap(0, centerY, trident_small, 32, 32, 1);
  display.setTextSize(1);
  String text1 = utf8cyr("Just Another");
  String text2 = utf8cyr("Alarm Map ");
  text2 += softwareVersion;
  int16_t x;
  int16_t y;
  uint16_t width;
  uint16_t height;
  display.getTextBounds(text1, 0, 0, &x, &y, &width, &height);
  display.setCursor(35, ((DISPLAY_HEIGHT - height) / 2) - 7);
  display.print(text1);
  display.setCursor(35, ((DISPLAY_HEIGHT - height) / 2) + 2);
  display.print(text2);
  display.display();
}

void timeUpdate() {
  timeClient.update();
  int currentHour = timeClient.getHours();
  isDay = currentHour >= day && currentHour < night;
  Serial.print("isDay: ");
  Serial.println(isDay);
}

void autoBrightnessUpdate() {
    if (autoBrightness) {
      //Serial.print("Autobrightness start: ");
      int currentBrightness = 0;
      currentBrightness = isDay ? dayBrightness : nightBrightness;
      //Serial.print(" currentBrightness: ");
      //Serial.print(currentBrightness);
      if (currentBrightness != brightness) {
        brightness = currentBrightness;
        EEPROM.write(eepromBrightnessAddress, brightness);
        EEPROM.commit();
        Serial.println("brightness commited to eeprom");
        FastLED.setBrightness(2.55 * brightness);
        FastLED.show();
        if (enableHA) {
          haBrightness.setState(brightness);
        }
        Serial.print(" set brightness: ");
        Serial.println(brightness);
      }else{
        //Serial.println("");
      }
    }
  }

void weatherUpdate () {
  //if (millis() - lastWeatherTime > weatherPeriod || firstWeatherUpdate) {
    if (firstWeatherUpdate){
      Serial.println("firstWeatherUpdate");
    }
    Serial.println("Weather fetch start");
    //lastWeatherTime = millis();
    firstWeatherUpdate = false;
    for (int i = 0; i < NUM_LEDS; i++) {
      String apiUrl = "http://api.openweathermap.org/data/2.5/weather?lang=ua&id=" + String(statesIdsWeather[i]) + "&units=metric&appid=" + String(apiKey);
      http.begin(apiUrl);
      int httpResponseCode = http.GET();

      DynamicJsonDocument doc(1024);
      if (httpResponseCode == 200) {
        String payload = http.getString();
        StaticJsonDocument<512> doc;
        deserializeJson(doc, payload);
        double temp = doc["main"]["temp"];
        if (stateId == i) {
          currentTemp = doc["main"]["temp"];
          currentWeather = doc["weather"][0]["description"].as<String>();
          currentWeather.replace('і', 'i');
          //Serial.println(currentWeather);
        }
        float normalizedValue = float(temp - minTemp) / float(maxTemp - minTemp);
        //Serial.print(states[i]);
        //Serial.print(':');
        //Serial.print(temp);
        //Serial.print(':');
        //Serial.print(normalizedValue);
        //Serial.print(':');
        if (normalizedValue > 1){
          normalizedValue = 1;
        }
        if (normalizedValue < 0){
          normalizedValue = 0;
        }
        int hue = 192 + normalizedValue * (0 - 192);
        hue = (int)hue % 256;
        //Serial.println(hue);
        ledWeatherColor[i] = CHSV(hue, 255, 255);
      }
      else {
        //Serial.print("Error getting weather data for city ID ");
        //Serial.println(statesIdsWeather[i]);
      }
      http.end();
    }
    //Serial.println("Weather fetch end");
  //}
}

void alamsUpdate() {
  //if (millis() - lastAlarmsTime > alarmsPeriod || firstAlarmsUpdate) {
    if (firstAlarmsUpdate){
      Serial.println("firstAlarmsUpdate");
    }
    Serial.println("Alarms fetch start");
    //lastAlarmsTime = millis();
    unsigned long  s1 = millis();
    firstAlarmsUpdate = false;
    String response;
    HTTPClient http;
    //Serial.print("Fetch alarm data: ");
    //Serial.println(baseURL);
    http.begin(baseURL.c_str());
    int httpResponseCode = http.GET();

    if (httpResponseCode == 200) {
      response = http.getString();
    }
    else {
      //Serial.print("Fetch fail: ");
      //Serial.println(httpResponseCode);
      return;
    }
    http.end();
    unsigned long  s2 = millis();
    DeserializationError error = deserializeJson(doc, response);
    if (error) {
      return;
    }
    //unsigned long  t = millis();
    alarmsNowCount = 0;
    bool return_to_map_init_mode = true;
    bool return_to_display_init_mode = true;
    unsigned long  s3 = millis();
    bool enable;
    long timeDiffLocal;
    const char* oldDate;
    for (int i = 0; i < NUM_LEDS; i++) {
      enable = doc["states"][states[i]]["enabled"].as<bool>();
      if (enable) {
        oldDate = doc["states"][states[i]]["enabled_at"];
      } else {
        oldDate = doc["states"][states[i]]["disabled_at"];
      }

      struct tm tm;
      strptime(oldDate, "%Y-%m-%dT%H:%M:%SZ", &tm);
      time_t oldTime = mktime(&tm);
      time_t currentTime = timeClient.getEpochTime();
      timeDiffLocal = difftime(currentTime, oldTime);
      if (isDaylightSaving){timeDiffLocal -= 14400;} else {timeDiffLocal -= 10800;};
      if (enable) {
        if (newAlarmPeriod > timeDiffLocal){
          ledColor[i] = 2;
        }
        if (newAlarmPeriod <= timeDiffLocal){
          ledColor[i] = 1;
        }
        if (stateId == i) {
          timeDifference = timeDiffLocal;
          isAlarm = true;
          buzzerUpdate();
          Serial.print("isAlarm: ");
          Serial.println(isAlarm);
        }
        alarmsNowCount++;
      } else {
        if (newAlarmPeriod > timeDiffLocal){
          ledColor[i] = 4;
        }
        if (newAlarmPeriod <= timeDiffLocal){
          ledColor[i] = 3;
        }
        if (stateId == i) {
          timeDifference = timeDiffLocal;
          isAlarm = false;
          buzzerUpdate();
          Serial.print("isAlarm: ");
          Serial.println(isAlarm);
        }
      }
      if (autoSwitchMap && enable && statesIdsAlarmCheck[i]==1) {
          mapMode = 2;
          mapInfo();
          if (enableHA) {
            haMapModeCurrent.setValue(mapModes[mapMode-1]);
          }
          return_to_map_init_mode = false;
      }
      if (autoSwitchDisplay && enable && statesIdsAlarmCheck[i]==1) {
          displayMode = 3;
          displayInfo();
          if (enableHA) {
            haDisplayModeCurrent.setValue(displayModes[displayMode-1]);
          }
          return_to_display_init_mode = false;
      }
    }
    unsigned long  s4 = millis();
    if (return_to_map_init_mode) {
      mapMode = mapModeInit;
      mapInfo();
      if (enableHA) {
        haMapModeCurrent.setValue(mapModes[mapMode-1]);
        //haMapMode.setState(mapModeInit-1);
      }
      //Serial.print("switch to map mode: ");
      //Serial.println(mapMode);
    }
    if (return_to_display_init_mode) {
      displayMode = displayModeInit;
      displayInfo();
      if (enableHA) {
        haDisplayModeCurrent.setValue(displayModes[displayMode-1]);
        //haDisplayMode.setState(displayModeInit-1);
      }
      //Serial.print("switch to display mode: ");
      //Serial.println(displayMode);
    }
    //Serial.print("Alarms fetch end: ");
    //Serial.println(s4-s1);
  //}
}

void mapInfo() {
  if (mapMode == 1) {
    mapModeFirstUpdate2 = true;
    mapModeFirstUpdate3 = true;
    mapModeFirstUpdate4 = true;
    Serial.println("Map mode 1");
    FastLED.clear();
    FastLED.show();
  }
  if (mapMode == 2) {
    mapModeFirstUpdate1 = true;
    mapModeFirstUpdate3 = true;
    mapModeFirstUpdate4 = true;
    Serial.println("Map mode 2");
    for (int i = 0; i < NUM_LEDS; i++)
    {
      switch (ledColor[i]) {
        case 1: leds[i] = CHSV(HUE_RED, 255, 2.55 * brightnessRed); break;
        case 2: leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * brightnessOrange); break;
        case 3: leds[i] = CHSV(HUE_GREEN, 255, 2.55 * brightnessGreen); break;
        case 4: leds[i] = CHSV(HUE_GREEN, 160, 2.55 * brightnessLightGreen); break;
      }
    }
    FastLED.show();
  }
  if (mapMode == 3) {
    mapModeFirstUpdate1 = true;
    mapModeFirstUpdate2 = true;
    mapModeFirstUpdate4 = true;
    Serial.println("Map mode 3");
    for (int i = 0; i < NUM_LEDS; i++)
    {
      leds[i] = ledWeatherColor[i];
    }
    FastLED.show();
  }
  if (mapMode == 4) {
    mapModeFirstUpdate1 = true;
    mapModeFirstUpdate2 = true;
    mapModeFirstUpdate3 = true;
    if (mapModeFirstUpdate4) {
      mapModeFirstUpdate4 = false;
      Serial.println("Map mode 4");
      Flag(50);
    }
  }
}

void mapModeSwitch() {
  mapModeInit += 1;
  if (mapModeInit > 4) {
    mapModeInit = 1;
  }
  if (enableHA) {
    haMapMode.setState(mapModeInit-1);
  }
  mapMode = mapModeInit;
  EEPROM.write(eepromMapModeAddress, mapMode);
  EEPROM.commit();
  Serial.println("mapMode commited to eeprom");
  touchModeDisplay(utf8cyr("Режим мапи:"), utf8cyr(mapModes[mapModeInit-1]));
  mapInfo();
  displayInfo();
}

void displayModeSwitch() {
  displayModeInit += 1;
  if (displayModeInit > 4) {
    displayModeInit = 1;
  }
  if (enableHA) {
    haDisplayMode.setState(displayModeInit-1);
  }
  displayMode = displayModeInit;
  EEPROM.write(eepromDisplayModeAddress, displayMode);
  EEPROM.commit();
  Serial.println("displayMode commited to eeprom");
  touchModeDisplay(utf8cyr("Режим дисплея:"), utf8cyr(displayModes[displayModeInit-1]));
  displayInfo();
}

void modulationModeSwitch() {
  modulationMode += 1;
  if (modulationMode > 3) {
    modulationMode = 1;
  }
  if (enableHA) {
    haModulationMode.setState(modulationMode-1);
  }
  EEPROM.write(eepromModulationModeAddress, modulationMode);
  EEPROM.commit();
  Serial.println("modulationMode commited to eeprom");
  touchModeDisplay(utf8cyr("Режим модуляцii:"), utf8cyr(modulationModes[modulationMode-1]));
  displayInfo();
}

void buzzerModeSwitch() {
  buzzerMode += 1;
  if (buzzerMode > 3) {
    buzzerMode = 1;
  }
  if (enableHA) {
    haBuzzerMode.setState(buzzerMode-1);
  }
  EEPROM.write(eepromBuzzerModeAddress, buzzerMode);
  EEPROM.commit();
  Serial.println("buzzerMode commited to eeprom");
  touchModeDisplay(utf8cyr("Режим буззера:"), utf8cyr(buzzerModes[buzzerMode-1]));
  displayInfo();
}

void modulationInfo() {
  if (mapMode==2 && modulationMode == 3) {
    Blink();
  }
  if (mapMode==2 && modulationMode == 2) {
    Modulation();
  }
}

void uptime() {
  int uptimeValue = millis() / 1000;
  int32_t number = WiFi.RSSI();
  int rssi = 0 - number;

  float totalHeapSize = ESP.getHeapSize() / 1024.0;
  float freeHeapSize = ESP.getFreeHeap() / 1024.0;
  float usedHeapSize = totalHeapSize - freeHeapSize;

  haUptime.setValue(uptimeValue);
  haWifiSignal.setValue(rssi);
  haFreeMemory.setValue(freeHeapSize);
  haUsedMemory.setValue(usedHeapSize);
  //}
}

void initTime() {
  timeClient.begin();
  timeClient.update();
  String formattedTime = timeClient.getFormattedTime();
  int day, month, year, hour, minute, second;
  sscanf(formattedTime.c_str(), "%d-%d-%d %d:%d:%d", &year, &month, &day, &hour, &minute, &second);
  if (month >= 3 && month <= 10) {
    isDaylightSaving = true;
  }
  if (isDaylightSaving) {
    timeClient.setTimeOffset(14400);
  }
  else {
    timeClient.setTimeOffset(10800);
  }
}

void initBroadcast() {
  if (!MDNS.begin(deviceBroadcastName)) {
    Serial.println("Error setting up mDNS responder!");
    while (1) {
      delay(1000);
    }
  }
  Serial.println("Device bradcasted to network!");
}

void startText() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  DisplayCenter(utf8cyr("Завантаження даних..."),0);
}

void checkEEPROM() {
  EEPROM.begin(128);
  int eepromBrightness;
  eepromBrightness = EEPROM.read(eepromBrightnessAddress);
  if (eepromBrightness == 0xFF) {
    EEPROM.write(eepromBrightnessAddress, brightness);
    EEPROM.commit();
    Serial.println("Brightness value not found in EEPROM. Using default value.");
  } else {
    brightness = eepromBrightness;
    Serial.print("Brightness value found in EEPROM: ");
    Serial.println(eepromBrightness);
  }
  int eepromMapMode;
  eepromMapMode = EEPROM.read(eepromMapModeAddress);
  if (eepromMapMode == 0xFF) {
    EEPROM.write(eepromMapModeAddress, mapModeInit);
    EEPROM.commit();
    Serial.println("mapMode value not found in EEPROM. Using default value.");
  } else {
    mapModeInit = eepromMapMode;
    Serial.print("mapMode value found in EEPROM: ");
    Serial.println(eepromMapMode);
  }
  int eepromDisplayMode;
  eepromDisplayMode = EEPROM.read(eepromDisplayModeAddress);
  if (eepromDisplayMode == 0xFF) {
    EEPROM.write(eepromDisplayModeAddress, displayModeInit);
    EEPROM.commit();
    Serial.println("displayMode value not found in EEPROM. Using default value.");
  } else {
    displayModeInit = eepromDisplayMode;
    Serial.print("displayMode value found in EEPROM: ");
    Serial.println(eepromDisplayMode);
  }
  int eepromModulationMode;
  eepromModulationMode = EEPROM.read(eepromModulationModeAddress);
  if (eepromModulationMode == 0xFF) {
    EEPROM.write(eepromModulationModeAddress, modulationMode);
    EEPROM.commit();
    Serial.println("modulationMode value not found in EEPROM. Using default value.");
  } else {
    modulationMode = eepromModulationMode;
    Serial.print("modulationMode value found in EEPROM: ");
    Serial.println(eepromModulationMode);
  }
  int eepromBuzzerMode;
  eepromBuzzerMode = EEPROM.read(eepromBuzzerModeAddress);
  if (eepromBuzzerMode == 0xFF) {
    EEPROM.write(eepromBuzzerModeAddress, eepromBuzzerMode);
    EEPROM.commit();
    Serial.println("BuzzerMode value not found in EEPROM. Using default value.");
  } else {
    buzzerMode = eepromBuzzerMode;
    Serial.print("BuzzerMode value found in EEPROM: ");
    Serial.println(eepromBuzzerMode);
  }
  int eepromButtonMode;
  eepromButtonMode = EEPROM.read(eepromButtonModeAddress);
  if (eepromButtonMode == 0xFF) {
    EEPROM.write(eepromButtonModeAddress, eepromButtonMode);
    EEPROM.commit();
    Serial.println("touchMode value not found in EEPROM. Using default value.");
  } else {
    touchMode = eepromButtonMode;
    Serial.print("touchMode value found in EEPROM: ");
    Serial.println(eepromButtonMode);
  }
}

void melody(int song[], int notes) {
  Serial.println("melody start");
  Serial.print("notes: ");
  Serial.println(notes);
  int wholenote = (60000 * 4) / buzzerTempo;
  int divider = 0, noteDuration = 0;
  for (int thisNote = 0; thisNote < notes * 2; thisNote = thisNote + 2) {
    divider = song[thisNote + 1];
    if (divider > 0) {
      noteDuration = (wholenote) / divider;
    } else if (divider < 0) {
      noteDuration = (wholenote) / abs(divider);
      noteDuration *= 1.5;
    }
    tone(BUZZER_PIN, song[thisNote], noteDuration*0.9);
    delay(noteDuration);
    noTone(BUZZER_PIN);
    //Serial.println(thisNote);
  }
  Serial.println("melody end");
}

void buzzer() {
  for (int i = 0; i < buzzerCount; i++) {
    tone(BUZZER_PIN, buzzerTone);
    delay(buzzerDuration);
    noTone(BUZZER_PIN);
    delay(buzzerDuration);
  }
}

void initBuzzer() {
  if(buzzerMode > 1) {
    pinMode(BUZZER_PIN, OUTPUT);
    melody(ukrainianAnthem, sizeof(ukrainianAnthem) / sizeof(ukrainianAnthem[0]) / 2 );
  }
}

void buzzerUpdate() {
  Serial.print("buzzerMode: ");
  Serial.println(buzzerMode);
  if(buzzerMode > 1) {
    if (isAlarm && isBuzzerStart) {
      if (isDay || (!isDay && buzzerMode == 3)) {
        if (buzzerStartSound == 2){
          buzzer();
        }
        if (buzzerStartSound == 3){
          melody(ukrainianAnthem, sizeof(ukrainianAnthem) / sizeof(ukrainianAnthem[0]) / 2 );
        }
        if (buzzerStartSound == 4){
          melody(imperialMarch, sizeof(imperialMarch) / sizeof(imperialMarch[0]) / 2 );
        }
        if (buzzerStartSound == 5){
          melody(startrek, sizeof(startrek) / sizeof(startrek[0]) / 2 );
        }
        if (buzzerStartSound == 6){
          melody(nokia, sizeof(nokia) / sizeof(nokia[0]) / 2 );
        }
      }
      isBuzzerStart = false;
      isBuzzerEnd = true;
    }
    if (!isAlarm && isBuzzerEnd) {
      if (isDay || (!isDay && buzzerMode == 3)) {
        if (buzzerEndSound == 2){
          buzzer();
        }
        if (buzzerEndSound == 3){
          melody(ukrainianAnthem, sizeof(ukrainianAnthem) / sizeof(ukrainianAnthem[0]) / 2 );
        }
        if (buzzerEndSound == 4){
          melody(imperialMarch, sizeof(imperialMarch) / sizeof(imperialMarch[0]) / 2 );
        }
        if (buzzerEndSound == 5){
          melody(startrek, sizeof(startrek) / sizeof(startrek[0]) / 2 );
        }
        if (buzzerEndSound == 6){
          melody(nokia, sizeof(nokia) / sizeof(nokia[0]) / 2 );
        }
      }
      isBuzzerStart = true;
      isBuzzerEnd = false;
    }
  }
}

void touchModeDisplay(String text1, String text2) {
  display.setCursor(0, 0);
  display.clearDisplay();
  display.setTextSize(1);
  display.println(text1);
  display.setTextSize(2);
  DisplayCenter(text2,6);
  delay(2000);
}

void touchUpdate() {
  if (digitalRead(TOUCH_PIN) == HIGH) {
    if (buzzerMode > 1) {
      tone(BUZZER_PIN, 100, 100);
      delay(100);
      noTone(BUZZER_PIN);
    }
    unsigned long  buttonPressStart = millis();
    bool changeButtonMode = true;
    while (digitalRead(TOUCH_PIN) == HIGH){
      unsigned long  buttonPressEnd = millis();
      if (buttonPressEnd - buttonPressStart > 2000){
        if (buzzerMode > 1) {
          tone(BUZZER_PIN, 100, 1000);
          delay(1000);
          noTone(BUZZER_PIN);
          delay(500);
        }
        changeButtonMode = false;
      }
    }
    if (changeButtonMode) {
      if (touchMode == 2) {
        mapModeSwitch();
      }
      if (touchMode == 3) {
        displayModeSwitch();
      }
      if (touchMode == 4) {
        modulationModeSwitch();
      }
      if (touchMode == 5) {
        buzzerModeSwitch();
      }

    } else {
      touchMode += 1;
      if (touchMode > 5) {
        touchMode = 2;
      }
      if (touchMode == 2) {
        touchModeDisplay(utf8cyr("Режим кнопки:"),utf8cyr("мапа"));
      }
      if (touchMode == 3) {
        touchModeDisplay(utf8cyr("Режим кнопки:"),utf8cyr("дисплей"));
      }
      if (touchMode == 4) {
        touchModeDisplay(utf8cyr("Режим кнопки:"),utf8cyr("модуляцiя"));
      }
      if (touchMode == 5) {
        touchModeDisplay(utf8cyr("Режим кнопки:"),utf8cyr("буззер"));
      }
      if (enableHA) {
        haButtonMode.setState(touchMode-1);
      }
      EEPROM.write(eepromButtonModeAddress, touchMode);
      EEPROM.commit();
      Serial.println("touchMode commited to eeprom");
    }
  }
}

void setup() {
  Serial.begin(115200);
  checkEEPROM();
  initFastLED();
  initDisplay();
  Flag(100);
  initBuzzer();
  initWiFi();
  startText();
  initTime();
  timeUpdate();
  autoBrightnessUpdate();
  initHA();
  setupRouting();
  ArduinoOTA.begin();
  initBroadcast();
  alamsUpdate();
  weatherUpdate();
  mapInfo();
  displayInfo();
  pinMode(TOUCH_PIN, INPUT);
  asyncEngine.setInterval(alamsUpdate, 10000);
  asyncEngine.setInterval(weatherUpdate, 600000);
  asyncEngine.setInterval(modulationInfo, 3000);
  asyncEngine.setInterval(timeUpdate, 5000);
  asyncEngine.setInterval(autoBrightnessUpdate, 5000);
  //asyncEngine.setInterval(displayInfo, 1000);
  //asyncEngine.setInterval(mapInfo, 1000);
  //asyncEngine.setInterval(buzzerUpdate, 1000);
  asyncEngine.setInterval(uptime, 60000);
}

void loop() {
  wifiConnected = WiFi.status() == WL_CONNECTED;
  if (!wifiConnected) {
    Flag(10);
    delay(5000);
    ESP.restart();
  }
  if (enableHA) {
    mqtt.loop();
  }
  asyncEngine.run();
  ArduinoOTA.handle();
  touchUpdate();
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