#include <Arduino.h>
#include <map>

#define MAIN_LEDS_COUNT 26
#define DISTRICTS_COUNT 26
#define KYIV_REGION_ID 31
#define KYIV_OBL_REGION_ID 14

struct SettingListItem {
  int id;
  const char* name;
  bool ignore;
};

#if BUZZER_ENABLED
static const char UA_ANTHEM[]            PROGMEM = "UkraineAnthem:d=4,o=5,b=200:2d5,4d5,32p,4d5,32p,4d5,32p,4c5,4d5,4d#5,2f5,4f5,4d#5,2d5,2c5,2a#4,2d5,2a4,2d5,1g4,32p,1g4";
static const char OI_U_LUZI[]            PROGMEM = "OiULuzi:d=32,o=5,b=200:2d,32p,2d,2f.,4d,4e,4f,4e,4d,2c#,2a4,2d.,4e,2f,2e,2d.";
static const char COSSACKS_MARCH[]       PROGMEM = "CossacksMarch:d=32,o=5,b=200:2d.,8a4,8d,2f.,8d,8f,4d,8a4,8d,4f,8d,8f,4d,8a4,8d,4f,8d,8f,1d.";
static const char HARRY_POTTER[]         PROGMEM = "HarryPotter:d=8,o=6,b=100:b5,e.,16g,f#,4e,b,4a.,4f#.,e.,16g,f#,4d,f,2b5";
static const char SIREN[]                PROGMEM = "Siren:d=32,o=6,b=225:16c#,d,d#,4e.,d#,d,8c#,16c#,d,d#,4e.,d#,d,8c#,16c#,d,d#,4e.,d#,d,8c#";
static const char COMMUNICATION[]        PROGMEM = "Communicator:d=32,o=7,b=180:d#,e,g,d#,g,d#,f#,e,f,2p,d#,e,g,d#,g,d#,f#,e,f,2p,d#,e,g,d#,g,d#,f#,e,f";
static const char STAR_WARS[]            PROGMEM = "StarWars:d=4,o=5,b=180:8f,8f,8f,2a#.,2f.6,8d#6,8d6,8c6,2a#.6,f.6,8d#6,8d6,8c6,2a#.6,f.6,8d#6,8d6,8d#6,2c6";
static const char IMPERIAL_MARCH[]       PROGMEM = "ImperialMarch:d=4,o=5,b=112:8d.,16p,8d.,16p,8d.,16p,8a#4,16p,16f,8d.,16p,8a#4,16p,16f,d.,8p,8a.,16p,8a.,16p,8a.,16p,8a#,16p,16f,8c#.,16p,8a#4,16p,16f,d.";
static const char STAR_TRACK[]           PROGMEM = "StarTrek:d=4,o=5,b=63:32p,8f.,16a#,d#.6,8d6,16a#.,16g.,16c.6,f6";
static const char INDIANA_JONES[]        PROGMEM = "IndianaJones:d=4,o=5,b=250:e,8p,8f,8g,8p,2c.6,8p.,d,8p,8e,1f,p.,g,8p,8a,8b,8p,2f.6,p,a,8p,8b,2c6,2d6,2e6";
static const char BACK_TO_THE_FUTURE[]   PROGMEM = "BackToTheFuture:d=4,o=6,b=180:2c,8b5,8a5,b5,a5,g5,1a5,p,d,2c,8b5,8a5,b5,a5,g5,1a5";
static const char KISS_I_WAS_MADE[]      PROGMEM = "KissIWasMade:d=4,o=5,b=125:c6,d6,8d#6,8p,8f6,8g6,8p,8g6,f6,d#6,d6,c6,d6,8d#6,8p,8f6,8g6,8p,8g6,f.6";
static const char THE_LITTLE_MERMAID[]   PROGMEM = "TheLittleMermaid:d=32,o=7,b=100:16c5,16f5,16a5,16c6,16p,16c6,16p,16c6,8a#5,8d6,8c6,8a5,16f4,16a4,16c5,16f5,16p,16f5,16p,16f5,8e5,8g5,8f5";
static const char NOKIA_TUN[]            PROGMEM = "NokiaTun:d=4,o=5,b=225:8e6,8d6,f#,g#,8c#6,8b,d,e,8b,8a,c#,e,2a";
static const char PACKMAN[]              PROGMEM = "Pacman:d=32,o=5,b=112:32p,b,p,b6,p,f#6,p,d#6,p,b6,f#6,16p,16d#6,16p,c6,p,c7,p,g6,p,e6,p,c7,g6,16p,16e6,16p,b,p,b6,p,f#6,p,d#6,p,b6,f#6,16p,16d#6,16p,d#6,e6,f6,p,f6,f#6,g6,p,g6,g#6,a6,p,b.6";
static const char SHCHEDRYK[]            PROGMEM = "Shchedryk:d=8,o=5,b=180:4a,g#,a,4f#,4a,g#,a,4f#";
static const char XMEN[]                 PROGMEM = "XMen:d=4,o=6,b=125:16d#4,16g4,16c5,16d#5,4d5,8c5,8g4,4p,16d#4,16g4,16c5,16d#5,4d5,8c5,8g#4,4p,16d#4,16g4,16c5,16d#5,4d5,8c5,8d#5,2p,8d5,8c5,8g5,16g5,32a5,32b5,4c6";
static const char AVENGERS[]             PROGMEM = "Avengers:d=16,o=6,b=70:4e4,4p.,16e4,16p,8e4,16p,16b4,4a4,4p,4g4,4f#4,16d4,16e4,8p,16e4,16f#4,8p,16d5,16e5,8p,16e5,16f#5,8p,4e4";
static const char SIREN2[]               PROGMEM = "Siren2:d=4,o=5,b=200:a.,8g#,a.,8g#,a.,8g#";
static const char SIREN3[]               PROGMEM = "Siren3:o=6,d=4,b=100:8b5,8d,8b5,8d,8b5,8d";
static const char SIREN4[]               PROGMEM = "Siren4:o=5,d=4,b=200:16a,16b,16a,16b,16a,16b,16a,16b,16a,16b,16a,16b,16a,16b,16a,16b,16a,16b";
static const char SQUIDGAME[]            PROGMEM = "SquidGame:d=32,o=4,b=200:8f,32p,8f,32p,8f,32p,4d,32p,8d#.,4f.,4p.,8f,32p,8f,32p,8f,32p,4d,32p,8d#.,4f.,4p.,4g,32p,8g.,32p,4g,32p,8c5.,32p,4a#,32p,8a.,4g,32p,8a.,4a#.,16p.,4a#.,16p.,4a#.";
static const char BANDERA[]              PROGMEM = "Bandera:d=32,o=4,b=140:8e,32p,8e,8c5,8b,8a,32p,8a,4p,8c5,32p,8c5,8d5,8c5,4b.,32p,8b,32p,8b,8b,8b,8b,8e5,8d5,8c5,8b,4a,32p,8a.,16a,32p,8a,8a";
static const char HUILO[]                PROGMEM = "Huilo:d=32,o=4,b=150:8e5,8p,4e5,4d5,2c5,2p5,8g,8c5,8d5,8e5,8d5,8c5,8e5,2a,2p,8g,8a,8b,8c5,8b,8a,8e,2f,2p,8e,8f,8e,8f,8e,8f,8f#,2g";
static const char HELLDIVERS[]           PROGMEM = "Helldivers:d=4,o=5,b=120:8f,8e,8d,1a4,4a4,4p,4c.,1d,2p,8f,8e,8d,1f,8c.,32p,8c.,8d.,4a,8d,2g";
static const char SIREN5[]               PROGMEM = "Siren5:d=16,o=5,b=200:c6,f6,c7,c6,f6,c7,c6,f6,c7,8p,c,f,c6,c,f,c6,c,f,c6";
static const char SIREN6[]               PROGMEM = "Siren6:d=16,o=6,b=160:8d,p,2d,p,8d,p,2d,p,8d,p,2d";
static const char SIREN7[]               PROGMEM = "Siren7:d=4,o=5,b=140:16c,16e,16g,16a,16c,16e,16g,16a,16c,16e,16g,16a";
static const char SIREN8[]               PROGMEM = "Siren8:=8,o=5,b=300:c,e,g,c,e,g,c,e,g,c6,e6,g6,c6,e6,g6,c6,e6,g6,c7,e7,g7,c7,e7,g7,c7,e7,g7";

static const char CLOCK_BEEP[]           PROGMEM = "ClockBeep:d=8,o=7,b=300:4g,32p,4g";
static const char MOS_BEEP[]             PROGMEM = "MosBeep:d=4,o=4,b=250:g";
static const char SINGLE_CLICK_SOUND[]   PROGMEM = "SingleClick:d=8,o=4,b=300:f";
static const char LONG_CLICK_SOUND[]     PROGMEM = "LongClick:d=8,o=4,b=300:4f";

#define MELODIES_COUNT 29
static const char* MELODIES[MELODIES_COUNT] PROGMEM = {
  UA_ANTHEM,
  OI_U_LUZI,
  COSSACKS_MARCH,
  HARRY_POTTER,
  SIREN,
  COMMUNICATION,
  STAR_WARS,
  IMPERIAL_MARCH,
  STAR_TRACK,
  INDIANA_JONES,
  BACK_TO_THE_FUTURE,
  KISS_I_WAS_MADE,
  THE_LITTLE_MERMAID,
  NOKIA_TUN,
  PACKMAN,
  SHCHEDRYK,
  XMEN,
  AVENGERS,
  SIREN2,
  SQUIDGAME,
  BANDERA,
  HUILO,
  HELLDIVERS,
  SIREN3,
  SIREN4,
  SIREN5,
  SIREN6,
  SIREN7,
  SIREN8,
};

static SettingListItem MELODY_NAMES[MELODIES_COUNT] PROGMEM = {
  {0, "Гімн України", false},
  {20, "Батько наш Бандера", false},
  {15, "Щедрик", false},
  {1, "Ой у лузі", false},
  {2, "Козацький марш", false},
  {4, "Сирена 1", false},
  {18, "Сирена 2", false},
  {23, "Сирена 3", false},
  {24, "Сирена 4", false},
  {25, "Сирена 5", false},
  {26, "Сирена 6", false},
  {27, "Сирена 7", false},
  {28, "Сирена 8", false},
  {5, "Комунікатор", false},
  {3, "Гаррі Поттер", false},
  {6, "Зоряні війни", false},
  {7, "Імперський марш", false},
  {8, "Зоряний шлях", false},
  {9, "Індіана Джонс", false},
  {10, "Назад у майбутнє", false},
  {11, "Kiss - I Was Made", false},
  {12, "Little Mermaid - Under the Sea", false},
  {13, "Рінгтон Nokia", false},
  {14, "Пакмен", false},
  {16, "Люди Х", false},
  {17, "Месники", false},
  {19, "Squid Game", false},
  {21, "ПТН ХЙЛ", false},
  {22, "Helldivers 2 - A cup of Liber-Tea", false}
};
#endif

#if DFPLAYER_PRO_ENABLED
static const String DF_CLOCK_BEEP = "/01.mp3";
static const String DF_CLOCK_TICK = "/02.mp3";
static const String DF_UA_ANTHEM = "/03.mp3";
static const String DF_SIREN_1 = "/04.mp3";
static const String DF_SIREN_2 = "/05.mp3";
static const String DF_SIREN_3 = "/06.mp3";
static const String DF_SIREN_4 = "/07.mp3";
static const String DF_SIREN_5 = "/08.mp3";
static const String DF_SIREN_6 = "/09.mp3";
static const String DF_SIREN_7 = "/10.mp3";
static const String DF_SIREN_8 = "/11.mp3";
static const String DF_SIREN_9 = "/12.mp3";
static const String DF_SIREN_10 = "/13.mp3";
static const String DF_THE_HOBBIT = "/14.mp3";
static const String DF_THE_MATRIX = "/15.mp3";
static const String DF_AVENGERS = "/16.mp3";
static const String DF_TERMINATOR_SHORT = "/17.mp3";
static const String DF_PIRATES_OF_THE_CARRIBEAN = "/18.mp3";
static const String DF_SIREN_11 = "/19.mp3";
static const String DF_NOTIFICATION_NEWS = "/20.mp3";
static const String DF_GOOd_MORNING_VIETNAM = "/21.mp3";
static const String DF_NOTIFICATION_R2D2 = "/22.mp3";
static const String DF_NOTIFICATION_STARTREK = "/23.mp3";
static const String DF_AIR_RAID_1 = "/24.mp3";
static const String DF_CAROL_OF_THE_BELLS = "/25.mp3";
static const String DF_NOTIFICATION_BACK_TO_THE_FUTURE = "/26.mp3";
static const String DF_IMPERIAL_MARCH = "/27.mp3";
static const String DF_GOOD_BAD_UGLY = "/28.mp3";
static const String DF_HARRY_POTTER = "/29.mp3";
static const String DF_MARCH = "/30.mp3";
static const String DF_MANDALORIAN_CALL = "/31.mp3";
static const String DF_MARIO = "/32.mp3";
static const String DF_PACMAN = "/33.mp3"; 

#define TRACKS_COUNT 3
static const String TRACKS[TRACKS_COUNT] = {
  DF_CLOCK_TICK,
  DF_CLOCK_BEEP,
  DF_UA_ANTHEM
};

static SettingListItem TRACK_NAMES[TRACKS_COUNT] PROGMEM = {
  {0, "Годинникова стрілка", false},
  {1, "Годинник", false},
  {2, "Гімн України", false}
};
#endif

static const int WDT_TIMEOUT = 15; // seconds
static const int CLEAR = 0;
static const int ALERT = 1;

#define BR_LEVELS_COUNT 20
#define MAX_BINS_LIST_SIZE 10

static const std::map<int, int> FLAG_COLORS = {
  {11, 60},
  {13, 60},
  {21, 60},
  {27, 180},
  {8, 180},
  {5, 180},
  {10, 180},
  {14, 180},
  {25, 180},
  {20, 180},
  {22, 180},
  {16, 180},
  {28, 60},
  {12, 60},
  {23, 60},
  {9999, 60},
  {18, 60},
  {17, 60},
  {9, 60},
  {19, 180},
  {24, 180},
  {15, 60},
  {4, 60},
  {3, 60},
  {26, 60},
  {31, 180},
};

static const int D11[] PROGMEM = {13, 27}; // Закарпатська обл.
static const int D13[] PROGMEM = {11, 21, 27, 26 }; // Івано-Франківська обл.
static const int D21[] PROGMEM = {13, 27, 5, 3, 26}; // Тернопільська обл.
static const int D27[] PROGMEM = {11, 13, 21, 8}; // Львівська обл.
static const int D8[] PROGMEM = {27, 5}; // Волинська обл.
static const int D5[] PROGMEM = {21, 27, 8, 10, 3 }; // Рівненська обл.
static const int D10[] PROGMEM = {5, 14, 4, 3}; // Житомирська обл.
static const int D14[] PROGMEM = {10, 25, 19, 24, 4, 31 }; // Київська обл.
static const int D25[] PROGMEM = {14, 20, 19}; // Чернігівська обл.
static const int D20[] PROGMEM = {8, 22, 19}; // Сумська обл.
static const int D22[] PROGMEM = {20, 28, 9, 19}; // Харківська обл.
static const int D16[] PROGMEM = {22, 28}; // Луганська обл.
static const int D28[] PROGMEM = {22, 12, 9}; // Донецька обл.
static const int D12[] PROGMEM = {28, 23, 9}; // Запорізька обл.
static const int D23[] PROGMEM = {12, 17, 9}; // Херсонська обл.
static const int D9999[] PROGMEM = {23}; // Автономна Республіка Крим
static const int D18[] PROGMEM = {17, 15, 4}; // Одеська обл.
static const int D17[] PROGMEM = {23, 18, 9, 15}; // Миколаївська обл.
static const int D9[] PROGMEM = {22, 28, 12, 23, 17, 19, 15}; // Дніпропетровська обл.
static const int D19[] PROGMEM = {14, 25, 20, 22, 9, 24, 15}; // Полтавська обл.
static const int D24[] PROGMEM = {14, 19, 15, 4}; // Черкаська обл.
static const int D15[] PROGMEM = {9, 17, 18, 19, 24, 4}; // Кіровоградська обл.
static const int D4[] PROGMEM = {10, 14, 18, 24, 15, 3, 26}; // Вінницька обл.
static const int D3[] PROGMEM = {21, 5, 10, 4, 26}; // Хмельницька обл.
static const int D26[] PROGMEM = {13, 21, 4, 3}; // Чернівецька обл.
static const int D31[] PROGMEM = {14}; // Київ

static SettingListItem DISTRICTS[DISTRICTS_COUNT] = {
  {9999, "АР Крим", false},
  {4, "Вінницька обл.", false},
  {8, "Волинська обл.", false},
  {9, "Дніпропетровська обл.", false},
  {28, "Донецька обл.", false},
  {10, "Житомирська обл.", false},
  {11, "Закарпатська обл.", false},
  {12, "Запорізька обл.", false},
  {13, "Ів.-Франківська обл.", false},
  {14, "Київська обл.", false},
  {31, "Київ", false},
  {15, "Кіровоградська обл.", false},
  {16, "Луганська обл.", false},
  {27, "Львівська обл.", false},
  {17, "Миколаївська обл.", false},
  {18, "Одеська обл.", false},
  {19, "Полтавська обл.", false},
  {5, "Рівненська обл.", false},
  {20, "Сумська обл.", false},
  {21, "Тернопільська обл.", false},
  {22, "Харківська обл.", false},
  {23, "Херсонська обл.", false},
  {3, "Хмельницька обл.", false},
  {24, "Черкаська обл.", false},
  {26, "Чернівецька обл.", false},
  {25, "Чернігівська обл.", false},
};

static std::map<int, std::pair<int, int*>> NEIGHBORING_DISTRICS = {
  {11, std::make_pair(2, (int*)D11)},
  {13, std::make_pair(4, (int*)D13)},
  {21, std::make_pair(5, (int*)D21)},
  {27, std::make_pair(4, (int*)D27)},
  {8, std::make_pair(2, (int*)D8)},
  {5, std::make_pair(5, (int*)D5)},
  {10, std::make_pair(4, (int*)D10)},
  {14, std::make_pair(6, (int*)D14)},
  {25, std::make_pair(3, (int*)D25)},
  {20, std::make_pair(3, (int*)D20)},
  {22, std::make_pair(4, (int*)D22)},
  {16, std::make_pair(2, (int*)D16)},
  {28, std::make_pair(3, (int*)D28)},
  {12, std::make_pair(3, (int*)D12)},
  {23, std::make_pair(3, (int*)D23)},
  {9999, std::make_pair(1, (int*)D9999)},
  {18, std::make_pair(3, (int*)D18)},
  {17, std::make_pair(4, (int*)D17)},
  {9, std::make_pair(7, (int*)D9)},
  {19, std::make_pair(7, (int*)D19)},
  {24, std::make_pair(4, (int*)D24)},
  {15, std::make_pair(6, (int*)D15)},
  {4, std::make_pair(7, (int*)D4)},
  {3, std::make_pair(5, (int*)D3)},
  {26, std::make_pair(4, (int*)D26)},
  {31, std::make_pair(1, (int*)D31)},
};

#define MAP_MODES_COUNT 8
static SettingListItem MAP_MODES[MAP_MODES_COUNT] = {
  {0, "Вимкнено", false},
  {1, "Тривога", false},
  {6, "Енергосистема", false},
  {2, "Погода", false},
  {7, "Радіація", false},
  {3, "Прапор", false},
  {4, "Випадкові кольори", false},
  {5, "Лампа", false},
};

#define DISPLAY_MODE_OPTIONS_MAX 8
static SettingListItem DISPLAY_MODES[DISPLAY_MODE_OPTIONS_MAX] = {
  {0, "Вимкнено", false},
  {1, "Годинник", false},
  {5, "Енергосистема", false},
  {2, "Погода", false},
  {6, "Радіація", false},
  {3, "Технічна інформація", false},
  {4, "Мікроклімат", false},
  {9, "Перемикання", false},
};

#define AUTO_ALARM_MODES_COUNT 3
static SettingListItem AUTO_ALARM_MODES[AUTO_ALARM_MODES_COUNT] = {
  {0, "Вимкнено", false},
  {1, "Домашній та суміжні", false},
  {2, "Лише домашній", false},
};

#define SINGLE_CLICK_OPTIONS_MAX 8
static SettingListItem SINGLE_CLICK_OPTIONS[SINGLE_CLICK_OPTIONS_MAX] = {
  {0, "Вимкнено", false},
  {1, "Перемикання режимів мапи", false},
  {2, "Перемикання режимів дисплея", false},
  {3, "Увімк./Вимк. мапу", false},
  {4, "Увімк./Вимк. дисплей", false},
  {5, "Увімк./Вимк. мапу та дисплей", false},
  {6, "Увімк./Вимк. нічний режим", false},
  {7, "Увімк./Вимк. режим лампи", false},
};

#define LONG_CLICK_OPTIONS_MAX 10
static SettingListItem LONG_CLICK_OPTIONS[LONG_CLICK_OPTIONS_MAX] = {
  {0, "Вимкнено", false},
  {1, "Перемикання режимів мапи", false},
  {2, "Перемикання режимів дисплея", false},
  {3, "Увімк./Вимк. мапу", false},
  {4, "Увімк./Вимк. дисплей", false},
  {5, "Увімк./Вимк. мапу та дисплей", false},
  {6, "Увімк./Вимк. нічний режим", false},
  {8, "Збільшити яскравість лампи", false},
  {9, "Зменшити яскравість лампи", false},
  {7, "Перезавантаження пристрою", false},
};

#define ALERT_PIN_MODES_COUNT 2
static SettingListItem ALERT_PIN_MODES_OPTIONS[ALERT_PIN_MODES_COUNT] = {
  {0, "Бістабільний", false},
  {1, "Імпульсний", false}
};

#if FW_UPDATE_ENABLED
#define FW_UPDATE_CHANNELS_COUNT 2
static SettingListItem FW_UPDATE_CHANNELS[FW_UPDATE_CHANNELS_COUNT] = {
  {0, "Production", false},
  {1, "Beta", false}
};
#endif

#define AUTO_BRIGHTNESS_OPTIONS_COUNT 3
static SettingListItem AUTO_BRIGHTNESS_MODES[AUTO_BRIGHTNESS_OPTIONS_COUNT] = {
  {0, "Вимкнено", false},
  {1, "День/Ніч", false},
  {2, "Сенсор освітлення", false}
};

#define KYIV_LED_MODE_COUNT 4
static SettingListItem KYIV_LED_MODE_OPTIONS[KYIV_LED_MODE_COUNT] = {
  {1, "Київська область", false},
  {2, "Київ", false},
  {3, "Київська область + Київ (2 діода)", false},
  {4, "Київська область + Київ (1 діод)", false}
};

#define ALERT_NOTIFY_OPTIONS_COUNT 3
static SettingListItem ALERT_NOTIFY_OPTIONS[ALERT_NOTIFY_OPTIONS_COUNT] = {
  {0, "Вимкнено", false},
  {1, "Колір", false},
  {2, "Колір + зміна яскравості", false}
};

#define DISPLAY_MODEL_OPTIONS_COUNT 4
static SettingListItem DISPLAY_MODEL_OPTIONS[DISPLAY_MODEL_OPTIONS_COUNT] = {
  {0, "Без дисплея", false},
  {1, "SSD1306", false},
  {2, "SH1106G", false},
  {3, "SH1107", false}
};

#define DISPLAY_HEIGHT_OPTIONS_COUNT 2
static SettingListItem DISPLAY_HEIGHT_OPTIONS[DISPLAY_HEIGHT_OPTIONS_COUNT] = {
  {32, "128x32", false},
  {64, "128x64", false}
};

#if ARDUINO_ESP32_DEV
#define LEGACY_OPTIONS_COUNT 4
#else
#define LEGACY_OPTIONS_COUNT 2
#endif
static SettingListItem LEGACY_OPTIONS[LEGACY_OPTIONS_COUNT] = {
#if ARDUINO_ESP32_DEV
  {3, "Плата JAAM 2.x", false},
  {0, "Плата JAAM 1.3", false},
#endif
  {1, "Початок на Закарпатті", false},
  {2, "Початок на Одещині", false},
};

static const size_t MAX_JSON_SIZE = 6000; // 6KB

// Визначення пінів для різних плат
#if ARDUINO_ESP32_DEV
    #define SUPPORTED_LEDS_PINS {2, 4, 12, 13, 14, 15, 16, 17, 18, 25, 26, 27, 32, 33}
#elif ARDUINO_ESP32S3_DEV
    #define SUPPORTED_LEDS_PINS {2, 4, 12, 13, 14, 15, 18, 21, 25, 26, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42}
#elif ARDUINO_ESP32C3_DEV
    #define SUPPORTED_LEDS_PINS {2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19, 20, 21}
#else
    #error "Платформа не підтримується!"
#endif

// Макрос для генерації switch-case для кожного піна
#define GENERATE_PIN_CASE(pin) \
    case pin: FastLED.addLeds<NEOPIXEL, pin>(const_cast<CRGB*>(leds), pixelcount); break;
