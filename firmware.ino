// Обов'зяково прочитай інструкцію перед використанням https://drukarnia.com.ua/articles/bagatofunkcionalna-proshivka-karta-povitryanikh-trivog-rjK3N
// ============ НАЛАШТУЙ МЕНЕ ============
//Налаштування WiFi
char* ssid = "rabbits"; //Назва твоєї мережі WiFi
char* password = "zayatcs25521243"; //Пароль від твого WiFi
//Налштування за замовчуванням
bool enabled = true; //Ввімкнена/вимкнена карта
int brightness = 100; //Яскравість %
bool autoBrightness = true; //Ввімкнена/вимкнена авто яскравість
int mode = 1; //Режим 
bool autoSwitch = true; //Автоматичне переключення карти на режим тривоги при початку тривоги в вибраній області, після заверешення тривоги в вибраній області режим не повертається на своє місце
static bool greenStates = true; //true - області без тривоги будуть зелені; false - не будуть світитися
//Налаштування телеграм бота 
#define BOTtoken ""
#define CHAT_ID ""
//Налаштування авто-яскравості
const int day = 8; //Початок дня
const int night = 23; //Початок ночі
const int dayBrightness = 100; //Денна яскравість %
const int nightBrightness = 50; //Нічна яскравість %
//Для погоди
const char* apiKey = "c42681760f292b7bd667e4010a1e5ea8"; //API погоди
float minTemp = -10.0; // мінімальна температура у градусах Цельсія для налашутвання діапазону кольорів
float maxTemp = 35.0; // максимальна температура у градусах Цельсія для налашутвання діапазону кольорів
//Налаштуванння режимів
int statesIdsCheck[] = { //Вибери області при тривозі в яких буде пермикатися режим на тривоги (1 - область активована; 0 - не активована)
0, //Закарпатська область
0, //Івано-Франківська область
0, //Тернопільська область
0, //Львівська область
0, //Волинська область
0, //Рівненська область
0, //Житомирська область
0, //Київ
0, //Київська область
0, //Чернігівська область
0, //Сумська область
0, //Харківська область
0, //Луганська область
0, //Донецька область
0, //Запорізька область
0, //Херсонська область
0, //АР Крим
0, //Одеська область
0, //Одеська область
0, //Миколаївська область
0, //Дніпропетровська область
0, //Полтавська область
0, //Черкаська область
0, //Кіровоградська область
0, //Вінницька область
0, //Хмельницька область
0  //Чернівецька область
};
// =======================================

#include <ArduinoJson.h> //json для аналізу інформації
#include <Adafruit_NeoPixel.h> //neopixel для управління стрічкою
#include <WiFi.h> //для зв'язку
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <UniversalTelegramBot.h> //Telegram бот
#include <WiFiManager.h> //Керування WiFi
#include <NTPClient.h> //Час
#include <HTTPUpdate.h> //Оновлення прошивки через тг бота
#include <WebServer.h>
#define LED_PIN 25
#define LED_COUNT 27

// JSON data buffer
StaticJsonDocument<250> jsonDocument;
char buffer[250];

WebServer server(80);

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
DynamicJsonDocument doc(30000);
String baseURL = "https://vadimklimenko.com/map/statuses.json";
static String states[] = {"Закарпатська область", "Івано-Франківська область", "Тернопільська область", "Львівська область", "Волинська область", "Рівненська область", "Житомирська область", "м. Київ", "Київська область", "Чернігівська область", "Сумська область", "Харківська область", "Луганська область", "Донецька область", "Запорізька область", "Херсонська область", "АР Крим", "Одеська область", "Одеська область", "Миколаївська область", "Дніпропетровська область", "Полтавська область", "Черкаська область", "Кіровоградська область", "Вінницька область", "Хмельницька область", "Чернівецька область" };
int statesIds[] = { 690548, 707471, 691650, 702550, 702569, 695594, 686967, 703447, 703448, 710735, 692194, 706483, 702658, 709717, 687700, 706448, 703883, 698740, 698740, 700569, 709930, 696643, 710719, 705811, 689558, 706369, 710719 };
WiFiClientSecure client;
WiFiManager wm;
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "ua.pool.ntp.org", 7200);
UniversalTelegramBot bot(BOTtoken, client);
unsigned long lastTimeBotRan;
static unsigned long times[27];
static int ledColor[27];
static int ledColorBlue[] = { 4,5,6,7,8,9,10,11,12,21,22, };
static int ledColorYellow[] = { 0,1,2,3,12,13,14,15,16,17,18,19,20,23,24,25,26 };
int arrAlarms = sizeof(ledColor) / sizeof(int);
int arrSize = sizeof(states) / sizeof(String);
bool startMessage = false;
bool enable = false;
int period = 15000;
unsigned long lastTime;
static int alarmsNowCount = 0;
static int prevAlarms = 0;
static bool wifiConnected;
static bool firstUpdate = true;


void setup_routing() {	 	 ;	 	 
  server.on("/params", HTTP_POST, handlePost);
  server.on("/params", HTTP_GET, getEnv);	 	 
  	 	 
  // start server	 	 
  server.begin();	 	 
}

void handlePost() {
  if (server.hasArg("plain") == false) {
    //handle error here
  }
  String body = server.arg("plain");
  deserializeJson(jsonDocument, body);
  
  // Get brightness
  int brightness = jsonDocument["brightness"];
  int auto_brightness_on = jsonDocument["auto_brightness_on"];
  int green_states_on = jsonDocument["green_states_on"];
  int green_states_off = jsonDocument["green_states_off"];
  int map_enable = jsonDocument["map_enable"];
  int map_disable = jsonDocument["map_disable"];
  int set_mode = jsonDocument["mode"];
  Serial.print("brightness: ");
  Serial.print(brightness);

  if(brightness) {
    autoBrightness = false;
    strip.setBrightness(brightness * 2.55);
    strip.show();
  }

  if(auto_brightness_on) {
    autoBrightness = true;
  }

  if(green_states_on) {
    greenStates = true;
  }

  if(green_states_off) {
    greenStates = false;
  }

  if(set_mode) {
    mode = set_mode;
  }

  if(map_enable) {
    enabled = true;
  }

  if(map_disable) {
    enabled = false;
  }

  // Respond to the client
  server.send(200, "application/json", "{}");
}

void getEnv() {
  Serial.println("Get temperature");
  jsonDocument.clear();  
  jsonDocument["brightness"] = brightness;
  jsonDocument["autobrightness"] = autoBrightness;
  jsonDocument["mode"] = mode;
  jsonDocument["autoSwitch"] = autoSwitch;
  jsonDocument["enabled"] = enabled;
  jsonDocument["greenStates"] = greenStates;
  jsonDocument["alarmsNowCount"] = alarmsNowCount;
  jsonDocument["greenStates"] = greenStates;
  serializeJson(jsonDocument, buffer);
  server.send(200, "application/json", buffer);
}


void initWiFi() {
	WiFi.mode(WIFI_STA);
	WiFi.begin(ssid, password);
	if (WiFi.status() != WL_CONNECTED) {
		bool res;
		res = wm.autoConnect("AlarmMap", ""); //точка достпу для налаштування WiFi, другі лапки - пароль
		if (!res) {
			Serial.println("Помилка підключення");
			ESP.restart();
		}
		else {
			Serial.println("Підключено :)");
		}
	}
}
void colorWipe(int wait) {
	int count = sizeof(ledColorYellow) / sizeof(int);
	for (int i = 0; i < count; i++) { // For each pixel in strip...
		strip.setPixelColor(ledColorBlue[i], strip.Color(0,191,255));
		strip.setPixelColor(ledColorYellow[i], strip.Color(255,255,51));//  Set pixel's color (in RAM)
		strip.show();                          //  Update strip to match
		delay(wait);                           //  Pause for a moment
	}
}
void initStrip() {
	strip.begin();           // INITIALIZE NeoPixel strip object (REQUIRED)
	strip.show();            // Turn OFF all pixels ASAP
	strip.setBrightness(brightness * 2.55);
	colorWipe(60);
}
void initTime() {
	// Встановлюємо початкове значення літнього часу на false
	bool isDaylightSaving = false;

	// Отримуємо поточну дату та час з сервера NTP
	timeClient.begin();
	timeClient.update();
	String formattedTime = timeClient.getFormattedTime();

	// Розбиваємо рядок з форматованим часом на складові
	int day, month, year, hour, minute, second;
	sscanf(formattedTime.c_str(), "%d-%d-%d %d:%d:%d", &year, &month, &day, &hour, &minute, &second);

	// Перевіряємо, чи поточний місяць знаходиться в інтервалі березень-жовтень
	if (month >= 3 && month <= 10) {
		// Якщо так, встановлюємо літній час на true
		isDaylightSaving = true;
	}

	// Встановлюємо зміщення часового поясу для врахування літнього часу
	if (isDaylightSaving) {
		timeClient.setTimeOffset(14400); // UTC+3 для України
	}
	else {
		timeClient.setTimeOffset(10800); // UTC+2 для України
	}
}

uint32_t celsiusToRGB(float temperature) {
	float normTemp = 0.0;   // нормалізована температура
	if (temperature < 0) {
		normTemp = (temperature - minTemp) / (0.0 - minTemp);
	}
	else {
		normTemp = (temperature - 0.0) / (maxTemp - 0.0);
	}
	float red = 255 * normTemp;  // значення червоного кольору
	float blue = 255 * (1 - normTemp);  // значення синього кольору
	uint8_t green = 0;  // значення зеленого кольору
	return ((uint8_t)red << 16) | ((uint8_t)green << 8) | (uint8_t)blue;  // повертає RGB колір
}
void setup() {
	initStrip();
	initWiFi();
	Serial.begin(115200);
	initTime();
  setup_routing();
}
void loop() {
	wifiConnected = WiFi.status() == WL_CONNECTED;
	if (wifiConnected) {
    server.handleClient();
		if (!startMessage && WiFi.status() == WL_CONNECTED) {
			startMessage = true;
		}
		if (enabled) {
			if (millis() - lastTime > period || firstUpdate) {
				if (autoBrightness) {
					//авто яскравість
					timeClient.update();
					int currentHour = timeClient.getHours();
					bool isDay = currentHour >= day && currentHour < night;
					brightness = isDay ? dayBrightness : nightBrightness;
					for (int i = 0; i < LED_COUNT; i++) {
						strip.setBrightness(brightness * 2.55);
					}
					strip.show();
				}
				firstUpdate = false;
				String response;
				HTTPClient http;
				http.begin(baseURL.c_str());
				// Send HTTP GET request
				int httpResponseCode = http.GET();

				if (httpResponseCode == 200) {
					response = http.getString();
				}
				else {
					return;
				}
				// Free resources
				http.end();
				DeserializationError error = deserializeJson(doc, response);
				if (error) {
					return;

				}
				unsigned long  t = millis();
				unsigned long hv = 180000;
				lastTime = t;
				alarmsNowCount = 0;
				for (int i = 0; i < arrSize; i++) {
					enable = doc["states"][states[i]]["enabled"].as<bool>();
					if (enable && times[i] == 0) {
						times[i] = t;
						ledColor[i] = 2;
					}
					else if (enable && times[i] + hv > t && ledColor[i] != 1) {
						ledColor[i] = 2;

					}
					else if (enable) {
						ledColor[i] = 1;
						times[i] = t;
					}

					if (!enable && times[i] + hv > t && times[i] != 0) {
						ledColor[i] = 3;
					}
					else if (!enable) {
						ledColor[i] = 0;
						times[i] = 0;
					}

					if (autoSwitch && enable && statesIdsCheck[i]==1&& mode != 1) {
							mode = 1;
					}					
				}
				if (mode == 1) {
					//тривоги    
					for (int i = 0; i < arrSize; i++)
					{
						switch (ledColor[i]) {
						case 1: strip.setPixelColor(i, strip.Color(255,0,0)); break;
						case 2: strip.setPixelColor(i, strip.Color(255,140,0)); break;
						case 0: if (greenStates) {} else {strip.setPixelColor(i, strip.Color(0, 0, 0)); break;}
						case 3: strip.setPixelColor(i, strip.Color(0,255,0)); break;
						}
					}
					strip.show();

				}
				if (mode == 2) {
					// Loop through the city IDs and get the current weather for each city
					for (int i = 0; i < sizeof(statesIds) / sizeof(int); i++) {
						// Construct the URL for the API call
						String apiUrl = "http://api.openweathermap.org/data/2.5/weather?id=" + String(statesIds[i]) + "&units=metric&appid=" + String(apiKey);
						// Make the HTTP request
						HTTPClient http;
						http.begin(apiUrl);
						int httpResponseCode = http.GET();
						Serial.println(httpResponseCode);
						// If the request was successful, parse the JSON response
						if (httpResponseCode == 200) {
							String payload = http.getString();
							StaticJsonDocument<512> doc;
							deserializeJson(doc, payload);

							// Extract the temperature from the JSON response
							double temp = doc["main"]["temp"];
							uint32_t color = celsiusToRGB(temp);

							// Update the corresponding pixels on the NeoPixel strip
							int startPixel = i * (LED_COUNT / (sizeof(statesIds) / sizeof(int)));
							Serial.println(startPixel);
							int endPixel = startPixel + (LED_COUNT / (sizeof(statesIds) / sizeof(int)));
							Serial.println(endPixel);
							for (int j = startPixel; j < endPixel; j++) {
								strip.setPixelColor(j, color);
								Serial.println(color);
							}
						}
						else {
							Serial.print("Error getting weather data for city ID ");
							Serial.println(statesIds[i]);
						}
						// Clean up the HTTP connection
						http.end();
						strip.show();
					}
					lastTime = millis();
				}
				if (mode == 3) {
					int count = sizeof(ledColorYellow) / sizeof(int);
					for (int i = 0; i < count; i++) { // For each pixel in strip...
						strip.setPixelColor(ledColorBlue[i], strip.Color(0,191,255));
		        strip.setPixelColor(ledColorYellow[i], strip.Color(255,255,51));//  Set pixel's color (in RAM)
						strip.show();
					}
				}
			}
		}
		else {
			strip.clear();
			strip.show();
			// success_message();
		}
	}
	else {
		strip.clear();
		strip.show();
		delay(10000);
		ESP.restart();
	}
}