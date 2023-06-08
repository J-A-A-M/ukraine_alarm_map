// Обов'зяково прочитай інструкцію перед використанням https://drukarnia.com.ua/articles/bagatofunkcionalna-proshivka-karta-povitryanikh-trivog-rjK3N
// ============ НАЛАШТУВАННЯ ============
//Налаштування WiFi
char* wifiSSID = ""; //Назва твоєї мережі WiFi
char* wifiPassword = ""; //Пароль від твого WiFi
char* apSSID = "AlarmMap"; //Назва точки доступу щоб переналаштувати WiFi
char* apPassword = ""; //Пароль від точки доступу щоб переналаштувати WiFi. Пусте - без пароля, рекомендую так і залишити (пароль від 8 симолів)
bool wifiStatusBlink = true;

//Налштування яскравості
int brightness = 100; //Яскравість %

float brightnessGreen = 50; //Яскравість %
float brightnessOrange = 75; //Яскравість %
float brightnessRed = 100; //Яскравість %

//Налаштування авто-яскравості
bool autoBrightness = true; //Ввімкнена/вимкнена авто яскравість
const int day = 8; //Початок дня
const int night = 22; //Початок ночі
const int dayBrightness = 100; //Денна яскравість %
const int nightBrightness = 20; //Нічна яскравість %

bool autoSwitch = false; //Автоматичне переключення карти на режим тривоги при початку тривоги в вибраній області
//static bool greenStates = true; //true - області без тривоги будуть зелені; false - не будуть світитися

int mapModeInit = 2;
int mapMode = 1;

int blinkDistricts[] = {
  0,
  1,
  2,
  7,
  8
};

int modulationMode = 2;
int modulationLevel = 50;
int modulationStep = 5;
int modulationTime = 200;
int modulationCount = 3;
bool modulationGreen = false;
bool modulationOrange = true;
bool modulationRed = true;
bool modulationSelected = false;

int newAlarmPeriod = 180000;

//Для погоди
const char* apiKey = ""; //API погоди
float minTemp = 10.0; // мінімальна температура у градусах Цельсія для налашутвання діапазону кольорів
float maxTemp = 35.0; // максимальна температура у градусах Цельсія для налашутвання діапазону кольорів

//Налаштуванння режимів
int statesIdsAlarmCheck[] = {0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
// =======================================

static String states[] = {
  "Закарпатська область",
  "Івано-Франківська область",
  "Тернопільська область",
  "Львівська область",
  "Волинська область",
  "Рівненська область",
  "Житомирська область",
  "м. Київ",
  "Київська область",
  "Чернігівська область",
  "Сумська область",
  "Харківська область",
  "Луганська область",
  "Донецька область",
  "Запорізька область",
  "Херсонська область",
  "Автономна Республіка Крим",
  "Одеська область",
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

int statesIdsWeather[] = {
  690548,
  707471,
  691650,
  702550,
  702569,
  695594,
  686967,
  703447,
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

// =======================================

#include <ArduinoJson.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WiFiManager.h>
#include <NTPClient.h>
#include <HTTPUpdate.h>
#include <WebServer.h>

#define LED_PIN     25
#define NUM_LEDS    27
#define LED_TYPE    WS2812
#define COLOR_ORDER GRB

CRGB leds[NUM_LEDS];

StaticJsonDocument<250> jsonDocument;
char buffer[250];

WebServer server(80);

DynamicJsonDocument doc(30000);
//String baseURL = "https://vadimklimenko.com/map/statuses.json";
String baseURL = "https://map.vglskr.net.ua/alarm_map";
WiFiClientSecure client;
WiFiManager wm;
WiFiUDP ntpUDP;
HTTPClient http;
NTPClient timeClient(ntpUDP, "ua.pool.ntp.org", 7200);
unsigned long lastTimeBotRan;
static unsigned long times[NUM_LEDS];
static int ledColor[NUM_LEDS];
static int flagColor[] {HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,HUE_AQUA,HUE_AQUA,
HUE_AQUA,HUE_AQUA,HUE_AQUA,HUE_AQUA,HUE_AQUA,HUE_AQUA,HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,
HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,HUE_AQUA,HUE_AQUA,
HUE_YELLOW,HUE_YELLOW,HUE_YELLOW,HUE_YELLOW};
int arrDistrictsSize = sizeof(blinkDistricts) / sizeof(int);
int arrAlarms = sizeof(ledColor) / sizeof(int);
int arrSize = sizeof(states) / sizeof(String);
int arrWeather = sizeof(statesIdsWeather) / sizeof(int);
int alarmsPeriod = 30000;
int weatherPeriod = 600000;
unsigned long lastAlarmsTime;
unsigned long lastWeatherTime;
static bool firstAlarmsUpdate = true;
static bool firstWeatherUpdate = true;
int alarmsNowCount = 0;
static bool wifiConnected;

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
    FastLED.setBrightness(2.54 * set_brightness);  // Set the overall brightness of the LEDs
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
    if(wifiStatusBlink) {
      //movingBlink(HUE_RED,1);
      colorFill(HUE_RED, 50);
      FlashAll(10,1);
    }
    delay(1000);
    Serial.println("Connecting to WiFi...");
    if (WiFi.status() == WL_CONNECT_FAILED) {
      Serial.println("Connection failed. Starting AP mode.");
      startAPMode();
      break;
    }
  }
  if (WiFi.status() == WL_CONNECTED) {
    if(wifiStatusBlink) {
      //movingBlink(HUE_GREEN,3);
      colorFill(HUE_GREEN, 50);
      FlashAll(10,3);
    }
    Serial.println("Connected to WiFi");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  }

}

void startAPMode() {
  Serial.println("Start AP");
  if(wifiStatusBlink) {
    //movingBlink(HUE_YELLOW,3);
    colorFill(HUE_YELLOW, 50);
    FlashAll(10,3);
  }
  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSSID, apPassword);

  Serial.println("AP mode started");
  Serial.print("AP SSID: ");
  Serial.println(apSSID);
  Serial.print("AP Password: ");
  Serial.println(apPassword);
  Serial.print("IP Address: ");
  Serial.println(WiFi.softAPIP());
}

void Modulation() {
  Serial.println("Modulation: start");
  int localModulationTime = modulationTime / 2 / ((100-modulationLevel) / modulationStep);
  int selectedStates[NUM_LEDS];
  for (int i = 0; i < NUM_LEDS; i++) {
    selectedStates[i] = 0;
  }
  for (int i = 0; i < sizeof(blinkDistricts) / sizeof(int); i++) {
    int position = blinkDistricts[i];
    selectedStates[position] = 1;
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
          case 2: if (modulationOrange|| selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * stepBrightness * brightnessOrange / 100); break;} else { break;}
          case 4: if (modulationGreen || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 180, 2.55 * stepBrightness * brightnessGreen / 100); break;} else { break;}
          case 3: if (modulationGreen|| selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 255, 2.55 * stepBrightness * brightnessGreen / 100); break;} else { break;}
        }
      }
      FastLED.show();
      //Serial.print("stepBrightness: ");
      //Serial.println(stepBrightness);
      //Serial.print("pixelBrightness: ");
      //Serial.println(pixelBrightness);
      if (fadeCycleEnded){
        //Serial.println("acs");
        stepBrightness += modulationStep;
      } else{
        //Serial.println("desc");
        stepBrightness -= modulationStep;
      }
      if (stepBrightness < modulationLevel) {
        fadeCycleEnded = true;
        //Serial.println("fadeCycleEnded");
      }
      if (stepBrightness > 100) {
        //Serial.println("rizeCycleEnded");
        rizeCycleEnded = true;
      }
      delay(localModulationTime);
    }
    //Serial.println("Cycle: end");
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
  Serial.print("selectedStates: ");
  for (int i = 0; i < sizeof(blinkDistricts) / sizeof(int); i++) {
    int position = blinkDistricts[i];
    selectedStates[position] = 1;
  }
  Serial.println(" ");
  Serial.println("selectedStates: ");
  for (int i = 0; i < NUM_LEDS; i++) {
    Serial.print(selectedStates[i]);
    Serial.print(" ");
  }
  Serial.println(" ");
  for (int i = 0; i < modulationCount; i++) {
    for (int i = 0; i < NUM_LEDS; i++) {
        switch (ledColor[i]) {
        case 1: if (modulationRed || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 0); break;} else { break;}
        case 2: if (modulationOrange || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 0); break;} else { break;}
        case 4: if (modulationGreen || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 180, 0); break;} else { break;}
        case 3: if (modulationGreen || selectedStates[i]) {leds[i] =CHSV(HUE_GREEN, 255, 0); break;} else { break;}
        }
    }
    FastLED.show();
    delay(localModulationTime);
    for (int i = 0; i < NUM_LEDS; i++) {
        switch (ledColor[i]) {
        case 1: if (modulationRed || selectedStates[i]) {leds[i] = CHSV(HUE_RED, 255, 2.55 * brightnessRed); break;} else { break;}
        case 2: if (modulationOrange || selectedStates[i]) {leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * brightnessOrange); break;} else { break;}
        case 4: if (modulationGreen || selectedStates[i]) {leds[i] = CHSV(HUE_GREEN, 180, 2.55 * brightnessGreen); break;} else { break;}
        case 3: if (modulationGreen || selectedStates[i]) {leds[i] =CHSV(HUE_GREEN, 255, 2.55 * brightnessGreen); break;} else { break;}
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
      leds[dot] = CHSV(0, 00, 255);
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

void initFastLED() {
  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(2.54 * brightness);
  FastLED.clear();
  FastLED.show();
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
  initFastLED();
  Flag(50);
  initWiFi();
  Serial.begin(115200);
  initTime();
  setupRouting();
}
void loop() {
	wifiConnected = WiFi.status() == WL_CONNECTED;
  if (!wifiConnected) {
    Flag(10);
    delay(10000);
    ESP.restart();
  }

  server.handleClient();

  if (autoBrightness) {
    Serial.println("Autobrightness start");
    timeClient.update();
    int currentHour = timeClient.getHours();
    int currentBrightness = 0;
    bool isDay = currentHour >= day && currentHour < night;
    currentBrightness = isDay ? dayBrightness : nightBrightness;
    if (currentBrightness != brightness) {
      brightness = currentBrightness;
      FastLED.setBrightness(2.54 * brightness);
      FastLED.show();
    }
  }
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
    for (int i = 0; i < arrSize; i++) {
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
    for (int i = 0; i < arrSize; i++)
    {
      switch (ledColor[i]) {
      case 1: leds[i] = CHSV(HUE_RED, 255, 2.55 * brightnessRed); break;
      case 2: leds[i] = CHSV(HUE_ORANGE, 255, 2.55 * brightnessOrange); break;
      case 4: leds[i] = CHSV(HUE_GREEN, 180, 2.55 * brightnessGreen); break;
      case 3: leds[i] = CHSV(HUE_GREEN, 255, 2.55 * brightnessGreen); break;
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
      for (int i = 0; i < arrWeather; i++) {
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
          int hue = 170 + normalizedValue * (0 - 170);
          hue = (int)hue % 256;
          leds[i] = CHSV(hue, 255, 255);
        }
        else {
          Serial.print("Error getting weather data for city ID ");
          Serial.println(statesIdsWeather[i]);
        }
        http.end();
      }
      FastLED.show();
    }
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
  delay(1000);
}