// ============ НАЛАШТУВАННЯ ============
char* ssid = ""; //Назва твоєї мережі WiFi
char* password = ""; //Пароль від твого WiFi
char* APSsid = "AlarmMap"; //Назва точки доступу
char* APPassword = ""; //Пароль від точки доступу
int brightness = ; //Яскравість %
bool autoBrightness = true; //Ввімкнена/вимкнена авто яскравість
static bool greenStates = true; //Області без тривоги будуть зелені
bool autoSwitch = true; //Автоматичне переключення карти на режим тривоги при початку тривоги в вибраній області
String mode = ""; //Режим
#define BOTtoken ""
#define CHAT_ID ""
const int day = ; //Початок дня
const int night = ; //Початок ночі
const int dayBrightness = ; //Денна яскравість %
const int nightBrightness = ; //Нічна яскравість %
const char* apiKey = ""; //API погоди
int statesIdsCheck[] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
int displayMode = ;
String myCity = "";
int myCityId = ;
float minTemp = -10; // мінімальна температура у градусах Цельсія для налашутвання діапазону кольорів
float maxTemp = 35; // максимальна температура у градусах Цельсія для налашутвання діапазону кольорів
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
  #include <Wire.h>
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>

  #define LED_PIN 13
  #define LED_COUNT 25
  #define SCREEN_WIDTH 128
  #define SCREEN_HEIGHT 32
  #define TOUCH_PIN 15

  Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
  Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
  DynamicJsonDocument doc(30000);
  String baseURL = "https://vadimklimenko.com/map/statuses.json";
  static String states[] = {"Закарпатська область", "Івано-Франківська область", "Тернопільська область", "Львівська область", "Волинська область", "Рівненська область", "Житомирська область", "Київська область", "Чернігівська область", "Сумська область", "Харківська область", "Луганська область", "Донецька область", "Запорізька область", "Херсонська область", "АР Крим", "Одеська область", "Миколаївська область", "Дніпропетровська область", "Полтавська область", "Черкаська область", "Кіровоградська область", "Вінницька область", "Хмельницька область", "Чернівецька область" };
  int statesIds[] = { 690548, 707471, 691650, 702550, 702569, 695594, 686967, 703448, 710735, 692194, 706483, 702658, 709717, 687700, 706448, 703883, 698740, 700569, 709930, 696643, 710719, 705811, 689558, 706369, 710719 };
  WiFiClientSecure client;
  WiFiManager wm;
  WiFiUDP ntpUDP;
  NTPClient timeClient(ntpUDP, "ua.pool.ntp.org", 7200);
  UniversalTelegramBot bot(BOTtoken, client);
  // String utf8cyr(String source);
  unsigned long lastTimeBotRan;
  unsigned long duration;
  static unsigned long times[25];
  String color;
  static int ledColor[25];
  static int ledColorBlue[] = { 2,3,4,5,6,7,20,8,9,19,10,11,25 };
  static int ledColorYellow[] = { 0,1,24,23,22,21,16,17,18,14,15,13,12 };
  int arrAlarms = sizeof(ledColor) / sizeof(int);
  int arrSize = sizeof(states) / sizeof(String);
  // int red, green, blue;
  // bool startMessage = false;
  bool enable = false;
  bool myCityEnable = false;
  int period = 15000;
  unsigned long lastTime;
  static int alarmsNowCount = 0;
  static int prevAlarms = 0;
  static bool wifiConnected;
  static bool firstUpdate = true;
  bool enabled = true;
  int disy = 0;
  // Перевірка останніх повідомлень
  int botRequestDelay = 1000;


  static const uint8_t strips4[] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x1f, 0xf8, 0x00, 0x01, 0xff, 0xff, 0x80, 0x07, 0xff, 0xff, 0xe0,
    0x0f, 0xc0, 0x03, 0xf0, 0x3f, 0x00, 0x00, 0xfc, 0x7c, 0x00, 0x00, 0x3e, 0x70, 0x07, 0xf0, 0x0f,
    0x60, 0x3f, 0xfc, 0x06, 0x00, 0xff, 0xff, 0x00, 0x03, 0xfc, 0x1f, 0xc0, 0x07, 0xe0, 0x07, 0xe0,
    0x07, 0x80, 0x01, 0xe0, 0x03, 0x00, 0x00, 0x40, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x1f, 0xf8, 0x00,
    0x00, 0x3f, 0xfc, 0x00, 0x00, 0x38, 0x1c, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x01, 0x80, 0x00, 0x00, 0x03, 0xc0, 0x00, 0x00, 0x01, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
  };
  static const uint8_t strips3[] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0f, 0xf0, 0x00,
    0x00, 0x7f, 0xfe, 0x00, 0x00, 0xff, 0xff, 0x00, 0x03, 0xf8, 0x1f, 0xc0, 0x07, 0xe0, 0x07, 0xe0,
    0x07, 0x80, 0x01, 0xe0, 0x03, 0x00, 0x00, 0xc0, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x1f, 0xf8, 0x00,
    0x00, 0x3f, 0xfc, 0x00, 0x00, 0x38, 0x1c, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x01, 0xc0, 0x00, 0x00, 0x03, 0xc0, 0x00, 0x00, 0x01, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
  };
  static const uint8_t strips2[] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x1f, 0xf8, 0x00,
    0x00, 0x3f, 0xfc, 0x00, 0x00, 0x38, 0x1c, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x03, 0xc0, 0x00, 0x00, 0x03, 0xc0, 0x00, 0x00, 0x01, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
  };
  static const uint8_t strip1[] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x03, 0xc0, 0x00, 0x00, 0x03, 0xc0, 0x00, 0x00, 0x01, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
  };
  static const uint8_t dino[] = {
    0x00, 0x03, 0xff, 0xe0, 0x00, 0x07, 0xff, 0xf0, 0x00, 0x06, 0x7f, 0xf0, 0x00, 0x06, 0x7f, 0xf0,
    0x00, 0x07, 0xff, 0xf0, 0x00, 0x07, 0xff, 0xf0, 0x00, 0x07, 0xff, 0xf0, 0x00, 0x07, 0xff, 0xf0,
    0x00, 0x07, 0xff, 0xf0, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x07, 0xe0, 0x00, 0x00, 0x07, 0xff, 0x00,
    0x00, 0x07, 0xc0, 0x00, 0x80, 0x0f, 0xc0, 0x00, 0xc0, 0x1f, 0xc0, 0x00, 0xe0, 0x7f, 0xc0, 0x00,
    0xf1, 0xff, 0xf8, 0x00, 0xff, 0xff, 0xd8, 0x00, 0xff, 0xff, 0xc0, 0x00, 0xff, 0xff, 0xc0, 0x00,
    0x7f, 0xff, 0x80, 0x00, 0x7f, 0xff, 0x80, 0x00, 0x3f, 0xff, 0x80, 0x00, 0x1f, 0xfe, 0x00, 0x00,
    0x0f, 0xf8, 0x00, 0x00, 0x07, 0xf8, 0x00, 0x00, 0x01, 0xd8, 0x00, 0x00, 0x01, 0x08, 0x00, 0x00,
    0x01, 0xc8, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x00
  };
  static const uint8_t clear[] = { //Сонячно
    0x00, 0x18, 0x18, 0x00, 0x00, 0x18, 0x18, 0x00, 0x00, 0x18, 0x18, 0x00, 0x18, 0x18, 0x18, 0x18,
    0x18, 0x18, 0x18, 0x18, 0x06, 0x1f, 0xf8, 0x60, 0x06, 0x1f, 0xf8, 0x60, 0x01, 0xff, 0xff, 0x80,
    0x01, 0xff, 0xff, 0x80, 0x01, 0xff, 0xff, 0x80, 0x01, 0xff, 0xff, 0x80, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0x07, 0xff, 0xff, 0xe0, 0x07, 0xff, 0xff, 0xe0, 0x07, 0xff, 0xff, 0xe0,
    0x07, 0xff, 0xff, 0xe0, 0x07, 0xff, 0xff, 0xe0, 0x07, 0xff, 0xff, 0xe0, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0x01, 0xff, 0xff, 0x80, 0x01, 0xff, 0xff, 0x80, 0x01, 0xff, 0xff, 0x80,
    0x01, 0xff, 0xff, 0x80, 0x06, 0x1f, 0xf8, 0x60, 0x06, 0x1f, 0xf8, 0x60, 0x18, 0x18, 0x18, 0x18,
    0x18, 0x18, 0x18, 0x18, 0x00, 0x18, 0x18, 0x00, 0x00, 0x18, 0x18, 0x00, 0x00, 0x18, 0x18, 0x00
  };
  const unsigned char clouds[] PROGMEM = { //Хмарно
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0f, 0xf0, 0x00,
    0x00, 0x0f, 0xf0, 0x00, 0x00, 0x1f, 0xf8, 0x00, 0x00, 0x3f, 0xfc, 0x00, 0x00, 0x7f, 0xfe, 0x00,
    0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00,
    0x01, 0xff, 0xff, 0x80, 0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0, 0x3f, 0xff, 0xff, 0xfc,
    0x3f, 0xff, 0xff, 0xfc, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc, 0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0,
    0x07, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
  };
  const unsigned char drizzle[] PROGMEM = { //Мряка
    0x00, 0x0f, 0xf0, 0x00, 0x00, 0x0f, 0xf0, 0x00, 0x00, 0x3f, 0xfc, 0x00, 0x00, 0x3f, 0xfc, 0x00,
    0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x01, 0xff, 0xff, 0x80,
    0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0, 0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc, 0x1f, 0xff, 0xff, 0xf8,
    0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1c, 0x18, 0x30, 0x38, 0x08, 0x18, 0x30, 0x10,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xc0, 0xc1, 0x83, 0x03, 0xc0, 0xc1, 0x83, 0x03
  };
  const unsigned char atmosphere[] PROGMEM = { //Туман
    0x00, 0x03, 0xff, 0x00, 0x00, 0x03, 0xff, 0x00, 0x00, 0x0c, 0x00, 0xc0, 0x00, 0x0c, 0x00, 0xc0,
    0x00, 0x3c, 0x00, 0xf0, 0x00, 0x3c, 0x00, 0xf0, 0x00, 0xc3, 0x03, 0x0c, 0x00, 0xc3, 0x03, 0x0c,
    0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03, 0x03, 0x0f, 0xf0, 0x03, 0x03, 0x0f, 0xf0, 0x03,
    0x02, 0x3f, 0xfc, 0x03, 0x00, 0x3f, 0xfc, 0x03, 0x00, 0x7f, 0xfe, 0x03, 0x00, 0xff, 0xff, 0x0c,
    0x00, 0xff, 0xff, 0x0c, 0x00, 0xff, 0xff, 0x00, 0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0,
    0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc, 0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0
  };
  const unsigned char snow[] PROGMEM = { //Сніг
    0x00, 0x0f, 0xf0, 0x00, 0x00, 0x0f, 0xf0, 0x00, 0x00, 0x3f, 0xfc, 0x00, 0x00, 0x3f, 0xfc, 0x00,
    0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x01, 0xff, 0xff, 0x80,
    0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0, 0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc, 0x0f, 0xff, 0xff, 0xf0,
    0x0f, 0xff, 0xff, 0xf0, 0x07, 0xff, 0xff, 0xe0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x3c, 0x03, 0xc0, 0x3c, 0x3c, 0x03, 0xc0, 0x3c, 0xff, 0x0f, 0xf0, 0xff, 0xff, 0x0f, 0xf0, 0xff,
    0xff, 0x0f, 0xf0, 0xff, 0xff, 0x0f, 0xf0, 0xff, 0x3c, 0x03, 0xc0, 0x3c, 0x3c, 0x03, 0xc0, 0x3c
  };
  const unsigned char rain[] PROGMEM = { //Дощ
    0x00, 0x0f, 0xf0, 0x00, 0x00, 0x0f, 0xf0, 0x00, 0x00, 0x3f, 0xfc, 0x00, 0x00, 0x3f, 0xfc, 0x00,
    0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x00, 0xff, 0xff, 0x00, 0x01, 0xff, 0xff, 0x80,
    0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0, 0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0x3f, 0xff, 0xff, 0xfc, 0x3f, 0xff, 0xff, 0xfc, 0x1f, 0xff, 0xff, 0xf8,
    0x0f, 0xff, 0xff, 0xf0, 0x0f, 0xff, 0xff, 0xf0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x30, 0xc1, 0x81, 0x83, 0x30, 0xc1, 0x81, 0x83, 0xc3, 0x06, 0x06, 0x0c, 0xc3, 0x06, 0x06, 0x0c,
    0x0c, 0x18, 0x18, 0x30, 0x0c, 0x18, 0x18, 0x30, 0x30, 0x60, 0x60, 0xc0, 0x30, 0x60, 0x60, 0xc0
  };
  const unsigned char thunderstorm[] PROGMEM = { //Гроза
    0x00, 0x0f, 0xf0, 0x00, 0x00, 0x0f, 0xf0, 0x00, 0x00, 0x30, 0x0c, 0x00, 0x00, 0x30, 0x0c, 0x00,
    0x00, 0xc0, 0x03, 0x00, 0x00, 0xc0, 0x03, 0x00, 0x00, 0xc0, 0x03, 0x00, 0x0f, 0xc0, 0x03, 0xf0,
    0x0f, 0xc0, 0x03, 0xf0, 0x30, 0x30, 0x0c, 0x0c, 0x30, 0x30, 0x0c, 0x0c, 0xc0, 0x00, 0x00, 0x03,
    0xc0, 0x00, 0x00, 0x03, 0xc0, 0x3f, 0xfe, 0x03, 0xc0, 0x3f, 0xfe, 0x03, 0xc0, 0x3f, 0xfe, 0x03,
    0xc0, 0x3f, 0xfe, 0x03, 0x30, 0x3f, 0xfe, 0x0c, 0x30, 0x3f, 0xfe, 0x0c, 0x0c, 0x3f, 0xfe, 0x70,
    0x0c, 0x3f, 0xf8, 0x70, 0x04, 0x3f, 0xf8, 0x60, 0x00, 0xff, 0xe0, 0x00, 0x00, 0xff, 0xe0, 0x00,
    0x00, 0xff, 0xf8, 0x00, 0x00, 0xff, 0xf8, 0x00, 0x00, 0xff, 0xf8, 0x00, 0x00, 0xff, 0xf8, 0x00,
    0x00, 0x0f, 0xe0, 0x00, 0x00, 0x0f, 0xe0, 0x00, 0x00, 0x0f, 0x80, 0x00, 0x00, 0x0f, 0x80, 0x00
  };
  static const uint8_t alarma[] = { //Тривога
    0x00, 0x07, 0xe0, 0x00, 0x00, 0x7f, 0xfe, 0x00, 0x01, 0xff, 0xff, 0x80, 0x03, 0xff, 0xff, 0xc0,
    0x07, 0xff, 0xff, 0xe0, 0x0f, 0xf8, 0x1f, 0xf0, 0x1f, 0xf8, 0x1f, 0xf8, 0x1f, 0xf8, 0x1f, 0xfc,
    0x3f, 0xf8, 0x1f, 0xfc, 0x7f, 0xf8, 0x1f, 0xfe, 0x7f, 0xf8, 0x1f, 0xfe, 0x7f, 0xf8, 0x1f, 0xff,
    0xff, 0xf8, 0x1f, 0xff, 0xff, 0xf8, 0x1f, 0xff, 0xff, 0xf8, 0x1f, 0xff, 0xff, 0xf8, 0x1f, 0xff,
    0xff, 0xf8, 0x1f, 0xff, 0xff, 0xf8, 0x1f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0x7f, 0xff, 0xff, 0xff, 0x7f, 0xff, 0xff, 0xfe, 0x7f, 0xff, 0xff, 0xfe, 0x3f, 0xff, 0xff, 0xfc,
    0x3f, 0xf8, 0x1f, 0xfc, 0x1f, 0xf8, 0x1f, 0xf8, 0x0f, 0xf8, 0x1f, 0xf0, 0x07, 0xf8, 0x1f, 0xf0,
    0x03, 0xff, 0xff, 0xc0, 0x01, 0xff, 0xff, 0x80, 0x00, 0x7f, 0xfe, 0x00, 0x00, 0x1f, 0xf8, 0x00
  };
  static const uint8_t no_alarm[] = { //Без тривоги
    0x00, 0x0f, 0xf0, 0x00, 0x00, 0x7f, 0xfe, 0x00, 0x01, 0xff, 0xff, 0x80, 0x03, 0xff, 0xff, 0xc0,
    0x07, 0xff, 0xff, 0xe0, 0x0f, 0xff, 0xff, 0xf0, 0x1f, 0xff, 0xff, 0xf8, 0x3f, 0xff, 0xff, 0xfc,
    0x3f, 0xff, 0xff, 0xfc, 0x7f, 0xff, 0xff, 0xfe, 0x7f, 0xff, 0xf8, 0xfe, 0x7f, 0xff, 0xf0, 0x7e,
    0xff, 0xff, 0xe0, 0x7f, 0xff, 0xff, 0xc0, 0xff, 0xff, 0xff, 0x81, 0xff, 0xff, 0x1f, 0x03, 0xff,
    0xfe, 0x0e, 0x07, 0xff, 0xfe, 0x04, 0x0f, 0xff, 0xff, 0x00, 0x1f, 0xff, 0xff, 0x80, 0x3f, 0xff,
    0x7f, 0xc0, 0x7f, 0xfe, 0x7f, 0xe0, 0xff, 0xfe, 0x7f, 0xf1, 0xff, 0xfe, 0x3f, 0xfb, 0xff, 0xfc,
    0x3f, 0xff, 0xff, 0xfc, 0x1f, 0xff, 0xff, 0xf8, 0x0f, 0xff, 0xff, 0xf0, 0x07, 0xff, 0xff, 0xe0,
    0x03, 0xff, 0xff, 0xc0, 0x01, 0xff, 0xff, 0x80, 0x00, 0x7f, 0xfe, 0x00, 0x00, 0x0f, 0xf0, 0x00
  };
  void initWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    display.clearDisplay();
    display.drawBitmap(0, 0 + disy, strips4, 32, 32, 1);
    display.setCursor(35, 8 + disy);
    display.setTextSize(1);
    display.println(utf8cyr("Підключення до:"));
    display.setCursor(35, 16 + disy);
    display.setTextSize(1);
    display.println(ssid);
    display.display();
    delay(500);
    display.clearDisplay();
    display.drawBitmap(0, 0 + disy, strips3, 32, 32, 1);
    display.setCursor(35, 8 + disy);
    display.setTextSize(1);
    display.println(utf8cyr("Підключення до:"));
    display.setCursor(35, 16 + disy);
    display.setTextSize(1);
    display.println(ssid);
    display.display();
    delay(500);
    display.clearDisplay();
    display.drawBitmap(0, 0 + disy, strips2, 32, 32, 1);
    display.setCursor(35, 8 + disy);
    display.setTextSize(1);
    display.println(utf8cyr("Підключення до:"));
    display.setCursor(35, 16 + disy);
    display.setTextSize(1);
    display.println(ssid);
    display.display();
    delay(500);
    display.clearDisplay();
    display.drawBitmap(0, 0 + disy, strip1, 32, 32, 1);
    display.setCursor(35, 8 + disy);
    display.setTextSize(1);
    display.println(utf8cyr("Підключення до:"));
    display.setCursor(35, 16 + disy);
    display.setTextSize(1);
    display.println(ssid);
    display.display();
    delay(500);
    display.clearDisplay();
    display.drawBitmap(0, 0 + disy, strips2, 32, 32, 1);
    display.setCursor(35, 8 + disy);
    display.setTextSize(1);
    display.println(utf8cyr("Підключення до:"));
    display.setCursor(35, 16 + disy);
    display.setTextSize(1);
    display.println(ssid);
    display.display();
    delay(500);
    display.clearDisplay();
    display.drawBitmap(0, 0 + disy, strips3, 32, 32, 1);
    display.setCursor(35, 8 + disy);
    display.setTextSize(1);
    display.println(utf8cyr("Підключення до:"));
    display.setCursor(35, 16 + disy);
    display.setTextSize(1);
    display.println(ssid);
    display.display();
    delay(500);
    if (WiFi.status() != WL_CONNECTED) {
      // Draw bitmap on the screen
      display.clearDisplay();
      display.drawBitmap(0, 0 + disy, dino, 28, 32, 1);
      display.setTextSize(2);
      if (APPassword == "") {
        display.setCursor(23, 16 + disy);
        display.println(APSsid);
      } else {
        display.setCursor(30, 0 + disy);
        display.println(APSsid);
        display.setCursor(23, 16 + disy);
        display.println(APPassword);
      }
      display.display();
      bool res;
      res = wm.autoConnect(APSsid, APPassword);
      if (!res) {
        Serial.println("Помилка підключення");
        ESP.restart();
      }
      else {
        Serial.println("Підключено :)");
      }
    }
  }
  void initStrip() {
    strip.begin();           // INITIALIZE NeoPixel strip object (REQUIRED)
    strip.show();            // Turn OFF all pixels ASAP
    strip.setBrightness(brightness * 2.55);
    colorWipe(60);
  }
  void initDisplay() {
    display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
    display.clearDisplay();
    display.setTextColor(WHITE);
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
    if (month >= 4 && month <= 10) {
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
  void dsiplayInfo() {
    timeClient.update();
    int hour = timeClient.getHours();
    int minute = timeClient.getMinutes();

    if(displayMode == 1) {
      display.setCursor(0, 0 + disy);
      // Форматуємо час у рядок для виведення на дисплей
      String time = "";
      if (hour < 10) time += "0";
      time += hour;
      time += ":";
      if (minute < 10) time += "0";
      time += minute;

      display.clearDisplay(); // clear display
      display.setTextSize(4);
      oledDisplayCenter(time, 0, 132, 0);
    }
    if(displayMode == 2) {
      String previousDate;
      int day = timeClient.getDay();
      String daysOfWeek[] = {"Неділя", "Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота"};
      time_t now = timeClient.getEpochTime();
      struct tm * timeinfo;
      timeinfo = localtime(&now);
      // int day = timeinfo->tm_mday;
      // int month = ;
      String date = "";
      if (timeinfo->tm_mday < 10) date += "0";
      date += timeinfo->tm_mday;
      date += ".";
      if (timeinfo->tm_mon < 10) date += "0";
      date += timeinfo->tm_mon + 1;
      date += ".";
      date += timeinfo->tm_year + 1900;
      if (date != previousDate) {
        previousDate = date;
        display.setTextSize(2);
        display.clearDisplay();
        oledDisplayCenter(utf8cyr(daysOfWeek[day]), 0, 132, 0);
        oledDisplayCenter(date, 16, 132, 0);
      }
    }
    if(displayMode == 3) {
      unsigned long previousMillis = 0;
      const long interval = 10000;
      if (millis() - previousMillis >= interval) {
        previousMillis = millis();
        // Construct the URL for the API call
        String apiUrl = "http://api.openweathermap.org/data/2.5/weather?id=" + String(myCityId) + "&units=metric&appid=" + String(apiKey);
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
          int weatherId = doc["weather"][0]["id"].as<int>();
          Serial.println(weatherId);
          int temp = doc["main"]["temp"];
          int humidity = doc["main"]["humidity"].as<int>();
          // String cityName = doc["name"].as<String>();
          if (weatherId <= 800) weatherId = weatherId / 100;
          if (weatherId > 800) weatherId = 9;
          Serial.println(weatherId);
          display.clearDisplay();
          if (weatherId == 2) display.drawBitmap(0, 0 + disy, thunderstorm, 32, 32, 1);
          if (weatherId == 3) display.drawBitmap(0, 0 + disy, drizzle, 32, 32, 1);
          if (weatherId == 5) display.drawBitmap(0, 0 + disy, rain, 32, 32, 1);
          if (weatherId == 6) display.drawBitmap(0, 0 + disy, snow, 32, 32, 1);
          if (weatherId == 7) display.drawBitmap(0, 0 + disy, atmosphere, 32, 32, 1);
          if (weatherId == 8) display.drawBitmap(0, 0 + disy, clear, 32, 32, 1);
          if (weatherId == 9) display.drawBitmap(0, 0 + disy, clouds, 32, 32, 1);
          String weather = "";
          weather += temp;
          weather += "C ";
          weather += humidity;
          weather += "%";
          display.setTextSize(2);
          oledDisplayCenter(weather, 8, 100, 32);
        } else {
          Serial.println("HTTP request failed: " + String(myCityId));
        }
        http.end();
      }
    }
    if(displayMode == 4) {
      unsigned long minutes = (duration / 60000) % 60;
      unsigned long hours = (duration / 3600000) % 24;
      if (myCityEnable) {
        display.clearDisplay();
        display.drawBitmap(0, 0 + disy, alarma, 32, 32, 1);
      } else {
        display.clearDisplay();
        display.drawBitmap(0, 0 + disy, no_alarm, 32, 32, 1);
      }
      display.setTextSize(3);
      String durationTransformed = "";
      if (hours < 10) durationTransformed += "0";
      durationTransformed += hours;
      durationTransformed += ":";
      if (minutes < 10) durationTransformed += "0";
      durationTransformed += minutes;
      oledDisplayCenter(durationTransformed, 4, 100, 32);
      display.display();
    }
  }
  void oledDisplayCenter(String text, int y, int screenWidth, int offset) {
    int16_t x1;
    int16_t y1;
    uint16_t width;
    uint16_t height;

    display.getTextBounds(text, 0, 0, &x1, &y1, &width, &height);

    // display on horizontal and vertical center
    display.setCursor(((screenWidth - width) / 2) + offset, y + disy);
    display.println(text); // text to display
    display.display();
  }
  void colorWipe(int wait) {
    int count = sizeof(ledColorYellow) / sizeof(int);
    for (int i = 0; i < count; i++) { // For each pixel in strip...
      strip.setPixelColor(ledColorBlue[i], strip.Color(0, 0, 255));
      strip.setPixelColor(ledColorYellow[i], strip.Color(255, 255, 0));//  Set pixel's color (in RAM)
      strip.show();                          //  Update strip to match
      delay(wait);                           //  Pause for a moment
    }
  }
  void success(String message) {
    String keyboardJson = "[[\"" + String(enabled ? "⏸ Вимкнути" : "▶️ Ввімкнути") + "\"], [\"🔆 Змінити яскравість (" + String(autoBrightness ? "🤖": String(brightness) + "%") + ")\"], [\"🔢 Змінити режим (" + String(autoSwitch ? "🤖" : "") + String(mode == "alarms" ? "🚨" : mode == "flag" ? "🇺🇦" : mode == "weather" ? "🌡" : mode == "flashlight" ? "🔦" + String(color == "white" ? "⚪" : color == "red" ? "🔴" : color == "orange" ? "🟠" : color == "yellow" ? "🟡" : color == "green" ? "🟢" : color = "blue" ? "🔵" : color = "purple" ? "🟣" : "❌")  : "❌") + ")\"], [\"🔄 Рестарт\"], [\"🔧 Оновити прошивку\"]]";
    bot.sendMessageWithReplyKeyboard(CHAT_ID, message, "", keyboardJson, true);
  }
  // Handle what happens when you receive new messages
  void handleNewMessages(int numNewMessages) {
    Serial.println("handleNewMessages");
    Serial.println(String(numNewMessages));
    for (int i=0; i<numNewMessages; i++) {
      String chat_id = String(bot.messages[i].chat_id);
      // Chat id of the requester
      if (chat_id != CHAT_ID){
        bot.sendMessage(chat_id, "Незареєстрований користувач");
        continue;
      }
      String text = bot.messages[i].text;
      Serial.println(text);
      String from_name = bot.messages[i].from_name;
      if (text == "/start") {
        success("Привіт, " + from_name + ".\nДля керування використовуй кнопки в меню бота");
      }
      if (text == String(enabled ? "⏸ Вимкнути" : "▶️ Ввімкнути")) {
        if (enabled) {
           enabled = false;
          success("⏸");
        } else {
          enabled = true;
          success("▶️");
        }
      }
      if (text == "🔆 Змінити яскравість (" + String(autoBrightness ? "🤖": String(brightness) + "%") + ")") {
        // bot.sendMessage(chat_id, "Введи значення у відстотках:\n*Щоб активувати авто-яскравість введи значення 0");
        String keyboardJson = "[[\"100%\", \"75%\", \"50%\", \"25%\", \"1%\"], [\"" + String(autoBrightness ? "" : "🤖 Активувати автояскравість") + "\"], [\"❌ Скасувати\"]]";
        bot.sendMessageWithReplyKeyboard(chat_id, "🔆 Введи значення у відстотках:", "", keyboardJson, true);
        while (true) {
          int numNewMessages = bot.getUpdates(bot.last_message_received + 1);
          if (numNewMessages > 0) {
            String text = bot.messages[0].text;
            if (text.toInt() >= 1 && text.toInt() <= 100) {
              autoBrightness = false;
              brightness = text.toInt();
              strip.setBrightness(brightness * 2.55);
              strip.show();
              success("✅");
              break;
            } else if (text == "❌ Скасувати") {
                success("✅");
                break;
              } else if (text == "🤖 Активувати автояскравість") {
                autoBrightness = true;
                success("🤖");
                break;
              } else {
                bot.sendMessage(chat_id, "🔆 Значення введено неправильно, введи відсоток від 1 до 100:");
                bot.sendMessage(chat_id, "🤷");
              }
          }
          delay(1000);
        }
      }
      if (text == "🔢 Змінити режим (" + String(autoSwitch ? "🤖" : "") + String(mode == "alarms" ? "🚨" : mode == "flag" ? "🇺🇦" : mode == "weather" ? "🌡" : mode == "flashlight" ? "🔦" + String(color == "white" ? "⚪" : color == "red" ? "🔴" : color == "orange" ? "🟠" : color == "yellow" ? "🟡" : color == "green" ? "🟢" : color = "blue" ? "🔵" : color = "purple" ? "🟣" : "❌")  : "❌") + ")") {
        // bot.sendMessage(chat_id, "Введи значення у відстотках:\n*Щоб активувати авто-яскравість введи значення 0");
        String keyboardJson = "[[\"" + String(mode == "alarms" ? "" : "🚨 Тривоги") + "\"], [\"" + String(mode == "weather" ? "" : "🌡 Погода") + "\"], [\"" + String(mode == "flag" ? "" : "🇺🇦 Прапор") + "\"], [\"🔦 Ліхтарик\"], [\"" + String(autoSwitch ? "🤖 Деактивувати автозмінення" : "🤖 Активувати автозмінення") + "\"], [\"❌ Скасувати\"]]";
        bot.sendMessageWithReplyKeyboard(chat_id, "🔢 Вибери режим:", "", keyboardJson, true);
        while (true) {
          int numNewMessages = bot.getUpdates(bot.last_message_received + 1);
          if (numNewMessages > 0) {
            String text = bot.messages[0].text;
            if (text == "🚨 Тривоги") {
              mode = "alarms";
              success("🚨");
              break;
            } else if (text == "🌡 Погода") {
              mode = "weather";
              success("🌡");
              break;
            } else if (text == "🇺🇦 Прапор") {
              mode = "flag";
              success("🇺🇦");
              break;
            } else if (text == "🔦 Ліхтарик") {
              String colors = "[[\"⚪️ Білий\"], [\"🔴 Червоний\"], [\"🟠 Помаранчевий\"], [\"🟡 Жовтий\"], [\"🟢 Зелений\"], [\"🔵 Синій\"], [\"🟣 Фіолетовий\"], [\"❌ Скасувати\"]]";
              bot.sendMessageWithReplyKeyboard(chat_id, "🔦 Вибери колір в меню:", "", colors, true);
              while (true) {
                int numNewMessages = bot.getUpdates(bot.last_message_received + 1);
                if (numNewMessages > 0) {
                  String text = bot.messages[0].text;
                  if (text == "⚪️ Білий") {
                    color = "white";
                    mode = "flashlight";
                    success("🔦⚪️");
                    break;
                  } else if (text == "🔴 Червоний") {
                    color = "red";
                    mode = "flashlight";
                    success("🔦🔴");
                    break;
                  } else if (text == "🟠 Помаранчевий") {
                    color = "orange";
                    mode = "flashlight";
                    success("🔦🟠");
                    break;
                  } else if (text == "🟡 Жовтий") {
                    color = "yellow";
                    mode = "flashlight";
                    success("🔦🟡");
                    break;
                  } else if (text == "🟢 Зелений") {
                    color = "green";
                    mode = "flashlight";
                    success("🔦🟢");
                    break;
                  } else if(text == "🔵 Синій") {
                    color = "blue";
                    mode = "flashlight";
                    success("🔦🔵");
                    break;
                  } else if(text == "🟣 Фіолетовий") {
                    color = "purple";
                    mode = "flashlight";
                    success("🔦🟣");
                    break;
                  } else if (text == "❌ Скасувати") {
                    success("✅");
                    break;
                  } else {
                    bot.sendMessage(chat_id, "🔦 Колір недоступний, вмбери колір в меню:");
                    bot.sendMessage(chat_id, "🤷");
                  }
                }
              }
              break;
            } else if (text == "🤖 Активувати автозмінення") {
              autoSwitch = true;
              success("🤖");
              break;
            } else if (text == "🤖 Деактивувати автозмінення") {
              autoSwitch = false;
              success("✅");
              break;
            } else if (text == "❌ Скасувати") {
              success("✅");
              break;
            } else {
              bot.sendMessage(chat_id, "🔢 Не зрозумілий режим, вмбери режим в меню:");
              bot.sendMessage(chat_id, "🤷");
            }
          }
          delay(1000);
        }
      }
      if (text == "🔄 Рестарт") {
        success("🔄");
        numNewMessages = bot.getUpdates(bot.last_message_received + 1);
        ESP.restart();
      }
      if (text == "🔧 Оновити прошивку") {
        success("");
        String keyboardJson = "[[{ \"text\" : \"Інструкція\", \"url\" : \"https://code.sdl.pp.ua/alarm-map/#update-firmware\" }]]";
        bot.sendMessageWithInlineKeyboard(chat_id, "🔧 Щоб оновити прошивку відправ файл у форматі .bin\nІнструкцію як завантажити такий файл ти знайдеш натиснувши кнопку нижче", "", keyboardJson);
      }
      if (bot.messages[i].hasDocument) {
        httpUpdate.rebootOnUpdate(false);
        t_httpUpdate_return ret = (t_httpUpdate_return)3;
        bot.sendMessage(chat_id, "🔧 Завантаження прошивки...", "");
        ret = httpUpdate.update(client, bot.messages[i].file_path);
        switch (ret) {
          case HTTP_UPDATE_FAILED:
            bot.sendMessage(chat_id, "❌ " + String(httpUpdate.getLastError()) + ": " + httpUpdate.getLastErrorString(), "");
            // break;
          case HTTP_UPDATE_NO_UPDATES:
            bot.sendMessage(chat_id, "❌ Немає оновлень", "");
            // break;
          case HTTP_UPDATE_OK:
            bot.sendMessage(chat_id, "✅ Оновлення успішне", "");
            bot.sendMessage(chat_id, "🔄 Перезапуск...", "");
            numNewMessages = bot.getUpdates(bot.last_message_received + 1);
            ESP.restart();
            // break;
          // default:
          //   break;
        }
      }
    }
  }
  uint32_t celsiusToRGB(float temperature, float maxTemp, float minTemp) {
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
  void IRAM_ATTR touchInterrupt() {
    unsigned long previousMillis = 0;
    const long interval = 1000;
    if (millis() - previousMillis >= interval) {
      previousMillis = millis();
      Serial.println("Touch");
      if(displayMode < 4) {
        displayMode = displayMode + 1;
      } else {
        displayMode = 1;
      }
    }
  }
  void setup() {
    initStrip();
    initDisplay();
    pinMode(TOUCH_PIN, INPUT);
    attachInterrupt(digitalPinToInterrupt(TOUCH_PIN), touchInterrupt, RISING);
    initWiFi();
    initTime();
    Serial.begin(115200);
    client.setCACert(TELEGRAM_CERTIFICATE_ROOT);
    success("💡");
  }
  void loop() {
    dsiplayInfo();
    wifiConnected = WiFi.status() == WL_CONNECTED;
    if (wifiConnected) {
      if (millis() > lastTimeBotRan + botRequestDelay) {
        int numNewMessages = bot.getUpdates(bot.last_message_received + 1);

        while (numNewMessages) {
          Serial.println("got response");
          handleNewMessages(numNewMessages);
          numNewMessages = bot.getUpdates(bot.last_message_received + 1);
        }
        lastTimeBotRan = millis();
      }
      if (enabled) {
        if (millis() - lastTime > period || firstUpdate) {
          if (autoBrightness) {
            if (mode != "flashlight") {
              //авто яскравість
              timeClient.update();
              int hour = timeClient.getHours();
              bool isDay = hour >= day && hour < night;
              brightness = isDay ? dayBrightness : nightBrightness;
            } else {
              brightness = 100;
            }
            strip.setBrightness(brightness * 2.55);
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
          } else {
            return;
          }
          // Free resources
          http.end();
          DeserializationError error = deserializeJson(doc, response);
          if (error) {
            return;
          }

          bool lastEnable;
          unsigned long startTime = 0;
          myCityEnable = doc["states"][myCity]["enabled"].as<bool>();
          if (lastEnable != myCityEnable) {
            startTime = millis();
            lastEnable = myCityEnable;
          }
          duration = millis() - startTime;

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

            if (autoSwitch && enable && statesIdsCheck[i]==1 && mode != "alarms") {
                mode = "alarms";
                success("🤖🚨");
            }
          }
          if (mode == "alarms") {
            //тривоги
            for (int i = 0; i < arrSize; i++)
            {
              switch (ledColor[i]) {
              case 1: strip.setPixelColor(i, strip.Color(255, 0, 0)); break;
              case 2: strip.setPixelColor(i, strip.Color(255, 55, 0)); break;
              case 0: if (greenStates) {} else {strip.setPixelColor(i, strip.Color(0, 0, 0)); break;}
              case 3: strip.setPixelColor(i, strip.Color(0, 255, 0)); break;
              }
            }
            strip.show();

          }
          if (mode == "weather") {
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
                uint32_t color = celsiusToRGB(temp, maxTemp, minTemp);

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
          if (mode == "flag") {
            int count = sizeof(ledColorYellow) / sizeof(int);
            for (int i = 0; i < count; i++) { // For each pixel in strip...
              strip.setPixelColor(ledColorBlue[i], strip.Color(0, 0, 255));
              strip.setPixelColor(ledColorYellow[i], strip.Color(255, 255, 0));//  Set pixel's color (in RAM)
              strip.show();
            }
          }
          if (mode == "flashlight") {
            for (int i = 0; i < LED_COUNT; i++) {
              if (color == "white") strip.setPixelColor(i, 255, 255, 255);
              if (color == "red") strip.setPixelColor(i, 255, 0, 0);
              if (color == "orange") strip.setPixelColor(i, 255, 165, 0);
              if (color == "yellow") strip.setPixelColor(i, 255, 255, 0);
              if (color == "green") strip.setPixelColor(i, 0, 255, 0);
              if (color == "blue") strip.setPixelColor(i, 0, 0, 255);
              if (color == "purple") strip.setPixelColor(i, 128, 0, 128);
            }
            strip.show();
          }
        }
      } else {
        strip.clear();
        strip.show();
        // success_message();
      }
    } else {
      strip.clear();
      strip.show();
      delay(10000);
      ESP.restart();
    }
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
          case 0xD0: {                                // перекодировать 0 блок (прописные)
            n = source[i]; i++;
            if (n == 0x81) { n = 0xA8; break; }       // перекодировать букву Ё
            if (n == 0x84) { n = 0xAA; break; }       // перекодировать букву Є
            if (n == 0x86) { n = 0xB1; break; }       // перекодировать букву І
            if (n == 0x87) { n = 0xAF; break; }       // перекодировать букву Ї
            if (n >= 0x90 && n <= 0xBF) n = n + 0x2F; break; // перекодировать остальные буквы 0 блока
          }
          case 0xD1: {                                // перекодировать 1 блок (строчные)
            n = source[i]; i++;
            if (n == 0x91) { n = 0xB7; break; }       // перекодировать букву ё
            if (n == 0x94) { n = 0xB9; break; }       // перекодировать букву є
            if (n == 0x96) { n = 0xB2; break; }       // перекодировать букву і
            if (n == 0x97) { n = 0xBE; break; }       // перекодировать букву ї
            if (n >= 0x80 && n <= 0x8F) n = n + 0x6F; break; // перекодировать остальные буквы 1 блока
          }
          case 0xD2: {                                // перекодировать 2 блок (всё вместе)
            n = source[i]; i++;
            if (n == 0x90) { n = 0xA5; break; }       // перекодировать букву Ґ
            if (n == 0x91) { n = 0xB3; break; }       // перекодировать букву ґ
          }
        }
      }
      m[0] = n;
      target = target + String(m);
    }
    return target;
  }
