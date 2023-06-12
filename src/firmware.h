#include <ArduinoJson.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WiFiManager.h>
#include <NTPClient.h>
#include <HTTPUpdate.h>
#include <WebServer.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>

// ============ НАЛАШТУВАННЯ ============

//Налаштування WiFi
char* wifiSSID = ""; //Назва мережі WiFi
char* wifiPassword = ""; //Пароль  WiFi
char* apSSID = "AlarmMap"; //Назва точки доступу щоб переналаштувати WiFi
char* apPassword = ""; //Пароль від точки доступу щоб переналаштувати WiFi. Пусте - без пароля
bool wifiStatusBlink = true; //Статуси wifi на дісплеі

//Налштування яскравості
int brightness = 100; //Яскравість %

float brightnessGreen = 50; //Яскравість зон без тривог%
float brightnessOrange = 75; //Яскравість зон з новими тривогами %
float brightnessRed = 100; //Яскравість зон з тривогами%

//Налаштування авто-яскравості
bool autoBrightness = true; //Ввімкнена/вимкнена авто яскравість
const int day = 8; //Початок дня
const int night = 22; //Початок ночі
const int dayBrightness = 100; //Денна яскравість %
const int nightBrightness = 20; //Нічна яскравість %

bool autoSwitch = false; //Автоматичне переключення карти на режим тривоги при початку тривоги в вибраній області

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
int modulationTime = 400; //Тривалість модуляції
int modulationCount = 3; //Кількість модуляцій в циклі
bool modulationGreen = false; //Зони без тривог в модуляції
bool modulationOrange = true; //Зони нових тривог в модуляції
bool modulationRed = true; //Зони тривог в модуляції
bool modulationSelected = false; //Майбутній функціонал, не працює

int newAlarmPeriod = 300000; //Час індикації нових тривог

//Дісплей
int displayMode = 1; //Режим дісплея
bool displayWarningStatus = true; //Статуси wifi на дісплеі

//Погода
const char* apiKey = ""; //API погоди
float minTemp = 5.0; // мінімальна температура у градусах Цельсія для налашутвання діапазону кольорів
float maxTemp = 25.0; // максимальна температура у градусах Цельсія для налашутвання діапазону кольорів

//Налаштуванння повернення в режим тривог
int statesIdsAlarmCheck[] = {
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

static String states[] = {
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
int statesIdsWeather[] = {
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
static int flagColor[] {
  HUE_YELLOW,
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

#define DISPLAY_WIDTH   128
#define DISPLAY_HEIGHT  32
// ======== КІНЕЦь НАЛАШТУВАННЯ =========

CRGB leds[NUM_LEDS];

Adafruit_SSD1306 display(DISPLAY_WIDTH, DISPLAY_HEIGHT, &Wire, -1);

StaticJsonDocument<250> jsonDocument;
char buffer[250];

WebServer server(80);

DynamicJsonDocument doc(30000);
String baseURL = "https://vadimklimenko.com/map/statuses.json";

WiFiClientSecure client;
WiFiManager wm;
WiFiUDP ntpUDP;
HTTPClient http;
NTPClient timeClient(ntpUDP, "ua.pool.ntp.org", 7200);

int alarmsPeriod = 30000;
int weatherPeriod = 600000;
unsigned long lastAlarmsTime;
unsigned long lastWeatherTime;
static bool firstAlarmsUpdate = true;
static bool firstWeatherUpdate = true;
int alarmsNowCount = 0;
static bool wifiConnected;
static unsigned long times[NUM_LEDS];
static int ledColor[NUM_LEDS];

static  bool mapModeFirstUpdate1= true;
static  bool mapModeFirstUpdate2= true;
static  bool mapModeFirstUpdate3= true;
static  bool mapModeFirstUpdate4= true;

void setupRouting() {
  server.on("/params", HTTP_POST, handlePost);
  server.on("/params", HTTP_GET, getEnv);
  server.begin();
}

void handlePost() {
  if (server.hasArg("plain") == false) {

  }

  String body = server.arg("plain");
  deserializeJson(jsonDocument, body);

  int set_brightness = jsonDocument["brightness"];
  int auto_brightness = jsonDocument["auto_brightness"];
  int map_mode = jsonDocument["map_mode"];
  int green_states_on = jsonDocument["green_states_on"];
  int green_states_off = jsonDocument["green_states_off"];
  int map_enable = jsonDocument["map_enable"];
  int map_disable = jsonDocument["map_disable"];
  int modulation_mode = jsonDocument["modulation_mode"];
  int set_new_alarm_period = jsonDocument["new_alarm_period"];

  if(set_brightness) {
    autoBrightness = false;
    brightness = set_brightness;
    FastLED.setBrightness(2.55 * set_brightness);  // Set the overall brightness of the LEDs
    FastLED.show();
    Serial.print("Brightness: ");
    Serial.println(brightness);
  }
  if(auto_brightness) {
    autoBrightness = true;
  }
  if(map_mode) {
    mapModeInit = map_mode;
  }
  if(modulation_mode) {
    modulationMode = modulation_mode;
  }
  if (set_new_alarm_period) {
    newAlarmPeriod = set_new_alarm_period*1000;
  }
  server.send(200, "application/json", "{}");
}

void getEnv() {
  Serial.println("Get temperature");
  jsonDocument.clear();
  jsonDocument["brightness"] = brightness;
  jsonDocument["autobrightness"] = autoBrightness;
  jsonDocument["mapMode"] = mapMode;
  jsonDocument["mapModeInit"] = mapModeInit;
  jsonDocument["autoSwitch"] = autoSwitch;
  jsonDocument["alarmsNowCount"] = alarmsNowCount;
  jsonDocument["modulationMode"] = modulationMode;
  jsonDocument["newAlarmPeriod"] = newAlarmPeriod;
  jsonDocument["weatherKey"] = apiKey;
  serializeJson(jsonDocument, buffer);
  server.send(200, "application/json", buffer);
}


void initWiFi() {
  Serial.println("WiFi init");
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSSID, wifiPassword);
  int connectionAttempts;
  while (WiFi.status() != WL_CONNECTED) {
    connectionAttempts++;
    if(displayMode != 1 && displayWarningStatus) {
      display.clearDisplay();
      display.setCursor(0, 0);
      display.setTextSize(1);
      display.println("WiFi connecting:");
      display.setCursor(0, 10);
      display.setTextSize(1);
      display.println(wifiSSID);
      display.print("Attempt: ");
      display.println(connectionAttempts);
      display.display();
    }
    if(wifiStatusBlink) {
      colorFill(HUE_RED, 50);
      FlashAll(10,1);
    }
    delay(2000);
    Serial.println("Connecting to WiFi...");
    Serial.print("WIFI status: ");
    Serial.println(WiFi.status());
    if (WiFi.status() == WL_CONNECT_FAILED) {
      Serial.println("Connection failed. Starting AP mode.");
      startAPMode();
      break;
    }
    if (connectionAttempts == 10) {
      break;
    }
  }
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnectionSuccess();
  } else {
    startAPMode();
  }
}

void wifiConnectionSuccess() {
  if(displayMode != 1 && displayWarningStatus) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(2);
    display.println("CONNECTED");
    display.setCursor(0, 16);
    display.setTextSize(1);
    display.print("IP: ");
    display.println(WiFi.localIP());
    display.display();
  }
  if(wifiStatusBlink) {
    colorFill(HUE_GREEN, 50);
    FlashAll(10,3);
    delay(3000);
  }
  Serial.println("Connected to WiFi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void startAPMode() {
  Serial.println("Start AP");
  if(displayMode != 1 && displayWarningStatus) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.print("AP: ");
    display.println(apSSID);
    display.print("Password: ");
    display.println(apPassword);
    display.display();
  }
  if(wifiStatusBlink) {
    colorFill(HUE_YELLOW, 50);
    FlashAll(10,3);
  }
  Serial.println("AP mode started");
  Serial.print("AP SSID: ");
  Serial.println(apSSID);
  Serial.print("AP Password: ");
  Serial.println(apPassword);
  bool connection;
  connection = wm.autoConnect(apSSID, apPassword);
  if (!connection) {
    if(displayMode != 1 && displayWarningStatus) {
      display.clearDisplay();
      display.setTextSize(1);
      display.println("Connection error");
      display.println("Restarting... ");
      Serial.println("Помилка підключення");
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
  Serial.println("selectedStates: ");
  for (int i = 0; i < NUM_LEDS; i++) {
    Serial.print(selectedStates[i]);
    Serial.print(" ");
  }
  Serial.println(" ");
  for (int i = 0; i < modulationCount; i++) {
    bool fadeCycleEnded = false;
    bool rizeCycleEnded = false;
    int stepBrightness = 100;
    //Serial.println("Cycle: start");
    while (!fadeCycleEnded || !rizeCycleEnded) {
      for (int i = 0; i < NUM_LEDS; i++) {
        switch (ledColor[i]) {
          case 1: if (modulationRed || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 2.55 * stepBrightness * brightnessRed / 100); break;} else { break;}
          case 2: if (modulationOrange || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * stepBrightness * brightnessOrange / 100); break;} else { break;}
          case 3: if (modulationGreen || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 255, 2.55 * stepBrightness * brightnessGreen / 100); break;} else { break;}
          case 4: if (modulationGreen || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 160, 2.55 * stepBrightness * brightnessGreen / 100); break;} else { break;}
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
  Serial.println("Modulation: end");
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
  Serial.println("Start blink");
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
          case 1: if (modulationRed || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 0); break;} else { break;}
          case 2: if (modulationOrange || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 0); break;} else { break;}
          case 3: if (modulationGreen || selectedStates[i]) {leds[i] =CHSV(HUE_GREEN, 255, 0); break;} else { break;}
          case 4: if (modulationGreen || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 160, 0); break;} else { break;}
        }
    }
    FastLED.show();
    delay(localModulationTime);
    for (int i = 0; i < NUM_LEDS; i++) {
        switch (ledColor[i]) {
          case 1: if (modulationRed || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 2.55 * brightnessRed); break;} else { break;}
          case 2: if (modulationOrange || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * brightnessOrange); break;} else { break;}
          case 3: if (modulationGreen || selectedStates[i]) {leds[i] =CHSV(HUE_GREEN, 255, 2.55 * brightnessGreen); break;} else { break;}
          case 4: if (modulationGreen || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 160, 2.55 * brightnessGreen); break;} else { break;}
        }
    }
    FastLED.show();
    delay(localModulationTime);
  }
  Serial.println("End blink");
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
  if (displayMode != 1) {
    timeClient.update();
    int hour = timeClient.getHours();
    int minute = timeClient.getMinutes();

    if(displayMode == 2) {
      display.setCursor(0, 0);
      String time = "";
      if (hour < 10) time += "0";
      time += hour;
      time += ":";
      if (minute < 10) time += "0";
      time += minute;
      display.clearDisplay();
      display.setTextSize(4);
      DisplayCenter(time);
    }
  }
}

void DisplayCenter(String text) {
    int16_t x;
    int16_t y;
    uint16_t width;
    uint16_t height;
    display.getTextBounds(text, 0, 0, &x, &y, &width, &height);
    display.setCursor(((DISPLAY_WIDTH - width) / 2), ((DISPLAY_HEIGHT - height) / 2));
    display.println(text);
    display.display();
  }

void initFastLED() {
    //FastLED.setMaxPowerInVoltsAndMilliamps(5, 300);
    FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
    FastLED.setBrightness(2.55 * brightness);
    FastLED.clear();
    FastLED.show();
}

void initDisplay() {
  if (displayMode != 1) {
    display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
    display.clearDisplay();
    display.setTextColor(WHITE);
  }
}

void autoBrightnessUpdate() {
    if (autoBrightness) {
      Serial.println("Autobrightness start");
      timeClient.update();
      int currentHour = timeClient.getHours();
      int currentBrightness = 0;
      bool isDay = currentHour >= day && currentHour < night;
      currentBrightness = isDay ? dayBrightness : nightBrightness;
      if (currentBrightness != brightness) {
        brightness = currentBrightness;
        FastLED.setBrightness(2.55 * brightness);
        FastLED.show();
      }
    }
  }

void alamsUpdate() {
  if (millis() - lastAlarmsTime > alarmsPeriod || firstAlarmsUpdate) {
    Serial.println("Alarms fetch start");
    lastAlarmsTime = millis();
    unsigned long  s1 = millis();
    firstAlarmsUpdate = false;
    String response;
    HTTPClient http;
    Serial.print("Fetch alarm data: ");
    Serial.println(baseURL);
    http.begin(baseURL.c_str());
    int httpResponseCode = http.GET();

    if (httpResponseCode == 200) {
      response = http.getString();
    }
    else {
      return;
    }
    http.end();
    unsigned long  s2 = millis();
    DeserializationError error = deserializeJson(doc, response);
    if (error) {
      return;
    }
    unsigned long  t = millis();
    alarmsNowCount = 0;
    bool return_to_init_mode = true;
    unsigned long  s3 = millis();
    bool enable;
    for (int i = 0; i < NUM_LEDS; i++) {
      enable = doc["states"][states[i]]["enabled"].as<bool>();
      if (enable) {
        if (times[i] == 0) {
          times[i] = t;
          ledColor[i] = 2;
          alarmsNowCount++;
        }
        if (times[i] + newAlarmPeriod > t){
          ledColor[i] = 2;
          alarmsNowCount++;
        }
        if (times[i] + newAlarmPeriod <= t){
          ledColor[i] = 1;
          alarmsNowCount++;
        }
      } else {
        if (times[i] == 0) {
          times[i] = t;
          ledColor[i] = 4;
        }
        if (times[i] + newAlarmPeriod > t && (ledColor[i] == 1 || ledColor[i] == 2)){
          ledColor[i] = 4;
        }
        if (times[i] + newAlarmPeriod > t){
          ledColor[i] = 4;
        }
        if (times[i] + newAlarmPeriod <= t){
          ledColor[i] = 3;
        }
      }
      if (autoSwitch && enable && statesIdsAlarmCheck[i]==1) {
          mapMode = 2;
          return_to_init_mode = false;
      }
    }
    unsigned long  s4 = millis();
    if (return_to_init_mode) {
      mapMode = mapModeInit;
    }
    Serial.print("get data: ");
    Serial.println(s2-s1);
    Serial.print("parse data: ");
    Serial.println(s3-s2);
    Serial.print("set data: ");
    Serial.println(s4-s3);
    Serial.print("Alarms fetch end: ");
    Serial.println(s4-s1);
  }
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
        case 4: leds[i] = CHSV(HUE_GREEN, 160, 2.55 * brightnessGreen); break;
      }
    }
    FastLED.show();
    if (modulationMode == 3) {
      Blink();
    }
    if (modulationMode == 2) {
      Modulation();
    }
  }
  if (mapMode == 3) {
    mapModeFirstUpdate1 = true;
    mapModeFirstUpdate2 = true;
    mapModeFirstUpdate4 = true;
    Serial.println("Map mode 3");
    if (millis() - lastWeatherTime > weatherPeriod || mapModeFirstUpdate3) {
      Serial.println("Weather fetch start");
      lastWeatherTime = millis();
      mapModeFirstUpdate3 = false;
      for (int i = 0; i < NUM_LEDS; i++) {
        String apiUrl = "http://api.openweathermap.org/data/2.5/weather?id=" + String(statesIdsWeather[i]) + "&units=metric&appid=" + String(apiKey);
        http.begin(apiUrl);
        int httpResponseCode = http.GET();
        Serial.println(httpResponseCode);
        JsonObject obj = doc.to<JsonObject>();
        if (httpResponseCode == 200) {
          String payload = http.getString();
          StaticJsonDocument<512> doc;
          deserializeJson(doc, payload);
          double temp = doc["main"]["temp"];
          float normalizedValue = float(temp - minTemp) / float(maxTemp - minTemp);
          int hue = 192 + normalizedValue * (0 - 192);
          hue = (int)hue % 256;
          leds[i] = CHSV(hue, 255, 255);
        }
        else {
          Serial.print("Error getting weather data for city ID ");
          Serial.println(statesIdsWeather[i]);
        }
        http.end();
      }
      Serial.println('.');
      Serial.println("Weather fetch end");
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

void initTime() {
  bool isDaylightSaving = false;
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

void setup() {
  Serial.begin(115200);
  initFastLED();
  Flag(50);
  initDisplay();
  initWiFi();
  initTime();
  setupRouting();
}
void loop() {
  wifiConnected = WiFi.status() == WL_CONNECTED;
  if (!wifiConnected) {
    Flag(10);
    delay(5000);
    ESP.restart();
  }
  server.handleClient();
  displayInfo();
  autoBrightnessUpdate();
  alamsUpdate();
  mapInfo();
  delay(1000);
}