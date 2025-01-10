#include "Definitions.h"
#include <Arduino.h>

#if BUZZER_ENABLED
static const char UA_ANTHEM[]            PROGMEM = "UkraineAnthem:d=4,o=5,b=200:2d5,4d5,32p,4d5,32p,4d5,32p,4c5,4d5,4d#5,2f5,4f5,4d#5,2d5,2c5,2a#4,2d5,2a4,2d5,1g4,32p,1g4";
static const char OI_U_LUZI[]            PROGMEM = "OiULuzi:d=32,o=5,b=200:2d,32p,2d,2f.,4d,4e,4f,4e,4d,2c#,2a#4,2d.,4e,2f,2e,2d.";
static const char COSSACKS_MARCH[]       PROGMEM = "CossacksMarch:d=32,o=5,b=200:2d.,8a#4,8d,2f.,8d,8f,4d,8a#4,8d,4f,8d,8f,4d,8a#4,8d,4f,8d,8f,1d.";
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

static const char CLOCK_BEEP[]           PROGMEM = "ClockBeep:d=8,o=7,b=300:4g,32p,4g";
static const char MOS_BEEP[]             PROGMEM = "MosBeep:d=4,o=4,b=250:g";
static const char SINGLE_CLICK_SOUND[]   PROGMEM = "SingleClick:d=8,o=4,b=300:f";
static const char LONG_CLICK_SOUND[]     PROGMEM = "LongClick:d=8,o=4,b=300:4f";

#define MELODIES_COUNT 19
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
  SIREN2
};

static const char* MELODY_NAMES[MELODIES_COUNT] PROGMEM = {
  "Гімн України",
  "Ой у лузі",
  "Козацький марш",
  "Гаррі Поттер",
  "Сирена",
  "Комунікатор",
  "Зоряні війни",
  "Імперський марш",
  "Зоряний шлях",
  "Індіана Джонс",
  "Назад у майбутнє",
  "Kiss - I Was Made",
  "Русалонька",
  "Nokia tune",
  "Пакмен",
  "Щедрик",
  "Люди Х",
  "Месники",
  "Сирена 2"
};
#endif


static const int WDT_TIMEOUT = 15; // seconds
static const int CLEAR = 0;
static const int ALERT = 1;

#define BR_LEVELS_COUNT 20
#define MAX_BINS_LIST_SIZE 10

static const uint8_t LEGACY_FLAG_LEDS[26] PROGMEM = {
  60, 60, 60, 180, 180, 180, 180, 180, 180,
  180, 180, 180, 60, 60, 60, 60, 60, 60, 60,
  180, 180, 60, 60, 60, 60, 180
};

static const uint8_t D0[] PROGMEM = { 0, 1, 3 };
static const uint8_t D1[] PROGMEM = { 1, 0, 2, 3, 24 };
static const uint8_t D2[] PROGMEM = { 2, 1, 3, 4, 5, 23, 24 };
static const uint8_t D3[] PROGMEM = { 3, 0, 1, 2, 4 };
static const uint8_t D4[] PROGMEM = { 4, 2, 3, 5 };
static const uint8_t D5[] PROGMEM = { 5, 2, 3, 4, 6, 23 };
static const uint8_t D6[] PROGMEM = { 6, 5, 7, 22, 23, 25 };
static const uint8_t D7[] PROGMEM = { 7, 6, 8, 19, 20, 22, 25 };
static const uint8_t D8[] PROGMEM = { 8, 7, 9, 19, 20 };
static const uint8_t D9[] PROGMEM = { 9, 8, 10, 19 };
static const uint8_t D10[] PROGMEM = { 10, 9, 12, 18, 19 };
static const uint8_t D11[] PROGMEM = { 11, 10, 12 };
static const uint8_t D12[] PROGMEM = { 12, 10, 13, 18 };
static const uint8_t D13[] PROGMEM = { 13, 12, 14, 18 };
static const uint8_t D14[] PROGMEM = { 14, 13, 17, 18 };
static const uint8_t D15[] PROGMEM = { 15, 14 };
static const uint8_t D16[] PROGMEM = { 16, 17, 20, 21, 22 };
static const uint8_t D17[] PROGMEM = { 17, 14, 16, 18, 21 };
static const uint8_t D18[] PROGMEM = { 18, 10, 12, 13, 14, 17, 19, 21 };
static const uint8_t D19[] PROGMEM = { 19, 7, 8, 9, 10, 18, 20, 21, 25 };
static const uint8_t D20[] PROGMEM = { 20, 7, 8, 19, 21, 22, 25 };
static const uint8_t D21[] PROGMEM = { 21, 16, 17, 18, 19, 20, 22 };
static const uint8_t D22[] PROGMEM = { 22, 6, 7, 16, 20, 21, 23, 24, 25 };
static const uint8_t D23[] PROGMEM = { 23, 2, 5, 6, 22, 24 };
static const uint8_t D24[] PROGMEM = { 24, 1, 2, 22, 23 };
static const uint8_t D25[] PROGMEM = { 25, 7 };

static const uint8_t COUNTERS[] PROGMEM = { 3, 5, 7, 5, 4, 6, 6, 6, 5, 4, 5, 3, 4, 4, 4, 2, 5, 5, 8, 8, 7, 7, 9, 6, 5, 2 };

#define DISTRICTS_COUNT 26

static const char* DISTRICTS[DISTRICTS_COUNT] = {
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

static const char* DISTRICTS_ALPHABETICAL[DISTRICTS_COUNT] = {
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

static const uint8_t* NEIGHBORING_DISTRICS[DISTRICTS_COUNT] PROGMEM = {
  D0, D1, D2, D3, D4, D5, D6, D7, D8, D9,
  D10, D11, D12, D13, D14, D15, D16, D17, D18, D19,
  D20, D21, D22, D23, D24, D25
};

#define MAP_MODES_COUNT 6
static const char* MAP_MODES[MAP_MODES_COUNT] = {
  "Вимкнено",
  "Тривога",
  "Погода",
  "Прапор",
  "Випадкові кольори",
  "Лампа"
};

#define DISPLAY_MODE_OPTIONS_MAX 6
static const char* DISPLAY_MODES[DISPLAY_MODE_OPTIONS_MAX] = {
  "Вимкнено",
  "Годинник",
  "Погода",
  "Технічна інформація",
  "Мікроклімат",
  "Перемикання"
};

#define AUTO_ALARM_MODES_COUNT 3
static const char* AUTO_ALARM_MODES[AUTO_ALARM_MODES_COUNT] = {
  "Вимкнено",
  "Домашній та суміжні",
  "Лише домашній"
};

#define SINGLE_CLICK_OPTIONS_MAX 7
static const char* SINGLE_CLICK_OPTIONS[SINGLE_CLICK_OPTIONS_MAX] = {
  "Вимкнено",
  "Перемикання режимів мапи",
  "Перемикання режимів дисплея",
  "Увімк./Вимк. мапу",
  "Увімк./Вимк. дисплей",
  "Увімк./Вимк. мапу та дисплей",
  "Увімк./Вимк. нічний режим"
};

#define LONG_CLICK_OPTIONS_MAX 8
static const char* LONG_CLICK_OPTIONS[LONG_CLICK_OPTIONS_MAX] = {
  "Вимкнено",
  "Перемикання режимів мапи",
  "Перемикання режимів дисплея",
  "Увімк./Вимк. мапу",
  "Увімк./Вимк. дисплей",
  "Увімк./Вимк. мапу та дисплей",
  "Увімк./Вимк. нічний режим",
  "Перезавантаження пристрою"
};

#define ALERT_PIN_MODES_COUNT 2
static const char* ALERT_PIN_MODES_OPTIONS[ALERT_PIN_MODES_COUNT] = {
  "Бістабільний",
  "Імпульсний"
};

#if FW_UPDATE_ENABLED
#define FW_UPDATE_CHANNELS_COUNT 2
static const char* FW_UPDATE_CHANNELS[FW_UPDATE_CHANNELS_COUNT] = {
  "Production",
  "Beta"
};
#endif

#define AUTO_BRIGHTNESS_OPTIONS_COUNT 3
static const char* AUTO_BRIGHTNESS_MODES[AUTO_BRIGHTNESS_OPTIONS_COUNT] = {
  "Вимкнено",
  "День/Ніч",
  "Сенсор освітлення"
};

#define KYIV_LED_MODE_COUNT 4
static const char* KYIV_LED_MODE_OPTIONS[KYIV_LED_MODE_COUNT] = {
  "Київська область",
  "Київ",
  "Київська область + Київ (2 діода)",
  "Київська область + Київ (1 діод)"
};

#define ALERT_NOTIFY_OPTIONS_COUNT 3
static const char* ALERT_NOTIFY_OPTIONS[ALERT_NOTIFY_OPTIONS_COUNT] = {
  "Вимкнено",
  "Колір",
  "Колір + зміна яскравості"
};

#define DISPLAY_MODEL_OPTIONS_COUNT 4
static const char* DISPLAY_MODEL_OPTIONS[DISPLAY_MODEL_OPTIONS_COUNT] = {
  "Без дисплея",
  "SSD1306",
  "SH1106G",
  "SH1107"
};

#define DISPLAY_HEIGHT_OPTIONS_COUNT 2
static const char* DISPLAY_HEIGHT_OPTIONS[DISPLAY_HEIGHT_OPTIONS_COUNT] = {
  "128x32",
  "128x64"
};

#define LEGACY_OPTIONS_COUNT 4
static const char* LEGACY_OPTIONS[LEGACY_OPTIONS_COUNT] = {
  "Плата JAAM 1.3",
  "Початок на Закарпатті",
  "Початок на Одещині",
  "Плата JAAM 2.x",
};

static const char* SETTINGS_KEYS[] = {
  "dn",
  "dd",
  "bn",
  "wshost",
  "ntph",
  "id",
  "wsnp",
  "upp",
  "legacy",
  "cbr",
  "brightness",
  "brd",
  "brn",
  "bra",
  "hat",
  "coloral",
  "colorcl",
  "colorna",
  "colorao",
  "colorex",
  "colormi",
  "colordr",
  "colorhd",
  "ba",
  "bc",
  "bna",
  "bao",
  "bex",
  "bhd",
  "bbg",
  "bs",
  "aas",
  "hd",
  "kdm",
  "mapmode",
  "dm",
  "dmt",
  "tmt",
  "tmh",
  "tmp",
  "bm",
  "b2m",
  "bml",
  "b2ml",
  "anm",
  "eex",
  "emi",
  "edr",
  "mintemp",
  "maxtemp",
  "ha_brokeraddr",
  "ha_mqttport",
  "ha_mqttuser",
  "ha_mqttpass",
  "dsmd",
  "dw",
  "dh",
  "ds",
  "ns",
  "pp",
  "bpp",
  "bpc",
  "slp",
  "bp",
  "b2p",
  "acpm",
  "ap",
  "cp",
  "acpt",
  "bzp",
  "lp",
  "sdm",
  "nfwn",
  "wsat",
  "wsrt",
  "ha_lbri",
  "ha_lr",
  "ha_lg",
  "ha_lb",
  "mos",
  "fwuc",
  "ltc",
  "lhc",
  "lpc",
  "lsf",
  "somos",
  "soa",
  "soae",
  "soeh",
  "sobc",
  "soex",
  "moa",
  "moae",
  "moex",
  "mson",
  "invd",
  "ddon",
  "tz",
  "imoa",
  "aont",
  "aoft",
  "ext",
  "abt",
  "mv"
};

static const char* PF_STRING = "S";
static const char* PF_INT = "I";
static const char* PF_FLOAT = "F";
static const size_t MAX_JSON_SIZE = 6000; // 6KB
