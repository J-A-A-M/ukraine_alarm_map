#include "Constants.h"
#include "JaamLogs.h"
#include <string>

struct Firmware {
  int major = 0;
  int minor = 0;
  int patch = 0;
  int betaBuild = 0;
  bool isBeta = false;
};

static Firmware parseFirmwareVersion(const char* version) {

  Firmware firmware;

  char* versionCopy = strdup(version);
  char* token = strtok(versionCopy, ".-");

  int part = 0;
  while (token) {
    if (isdigit(token[0])) {
      if (part == 0)
        firmware.major = atoi(token);
      else if (part == 1)
        firmware.minor = atoi(token);
      else if (part == 2)
        firmware.patch = atoi(token);
      part++;
    } else if (token[0] == 'b' && strcmp(token, "bin") != 0) {
      firmware.isBeta = true;
      firmware.betaBuild = atoi(token + 1); // Skip the 'b' character
    }
    token = strtok(NULL, ".-");
  }

  free(versionCopy);

  return firmware;
}

static void fillFwVersion(char* result, Firmware firmware) {
  std::string version = std::to_string(firmware.major) + "." + std::to_string(firmware.minor);

  if (firmware.patch > 0) {
    version += "." + std::to_string(firmware.patch);
  }

  if (firmware.isBeta) {
    version += "-b" + std::to_string(firmware.betaBuild);
  }

#if ARDUINO_ESP32S3_DEV
  version += "-s3";
#elif ARDUINO_ESP32C3_DEV
  version += "-c3";
#endif

#if LITE
  version += "-lite";
#endif

#if TEST_MODE
  version += "-test";
#endif

  strcpy(result, version.c_str());
}

#if FW_UPDATE_ENABLED
static bool prefix(const char *pre, const char *str) {
  return strncmp(pre, str, strlen(pre)) == 0;
}

static bool firstIsNewer(Firmware first, Firmware second) {
  if (first.major > second.major) return true;
  if (first.major == second.major) {
    if (first.minor > second.minor) return true;
    if (first.minor == second.minor) {
      if (first.patch > second.patch) return true;
      if (first.patch == second.patch) {
        if (first.isBeta && second.isBeta) {
          if (first.betaBuild > second.betaBuild) return true;
        } else {
          return !first.isBeta && second.isBeta;
        }
      }
    }
  }
  return false;
}
#endif

static bool isInIgnoreList(int value, SettingListItem array[], int arraySize) {
  for (int i = 0; i < arraySize; i++) {
    if (array[i].ignore && array[i].id == value) return true;
  }
  return false;
}

static const char* disableRange(bool isDisabled) {
  return isDisabled ? " disabled" : "";
}

static int getCurrentPeriodIndex(int periodLength, int periodCount, long currentSeconds) {
  return (currentSeconds / periodLength) % periodCount;
}

static char getDivider(long currentSeconds) {
  // Change every second
  int periodIndex = getCurrentPeriodIndex(1, 2, currentSeconds);
  if (periodIndex) {
    return ' ';
  } else {
    return ':';
  }
}

static void fillFromTimer(char* result, long timerSeconds) {
  unsigned long seconds = timerSeconds;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  if (hours >= 99) {
    strcpy(result, "99+ год.");
  } else {
    seconds %= 60;
    minutes %= 60;
    char divider = getDivider(timerSeconds);
    if (hours > 0) {
      sprintf(result, "%02d%c%02d", hours, divider, minutes);
    } else {
      sprintf(result, "%02d%c%02d", minutes, divider, seconds);
    }
  }
}

struct RGBColor {
  uint8_t r;
  uint8_t g;
  uint8_t b;
};

static RGBColor hue2rgb(int hue) {
  float r, g, b;

  float h = hue / 360.0;
  float s = 1.0;
  float v = 1.0;

  int i = floor(h * 6);
  float f = h * 6 - i;
  float p = v * (1 - s);
  float q = v * (1 - f * s);
  float t = v * (1 - (1 - f) * s);

  switch (i % 6) {
    case 0: r = v, g = t, b = p; break;
    case 1: r = q, g = v, b = p; break;
    case 2: r = p, g = v, b = t; break;
    case 3: r = p, g = q, b = v; break;
    case 4: r = t, g = p, b = v; break;
    case 5: r = v, g = p, b = q; break;
    default: r = 1.0, g = 1.0, b = 1.0; break;
  }
  RGBColor rgb;
  rgb.r = round(r * 255);
  rgb.g = round(g * 255);
  rgb.b = round(b * 255);
  return rgb;
}

static int rgb2hue(uint8_t red, uint8_t green, uint8_t blue) {
  float r = red / 255.0;
  float g = green / 255.0;
  float b = blue / 255.0;

  float max = fmax(r, fmax(g, b));
  float min = fmin(r, fmin(g, b));
  float delta = max - min;

  float h = 0;
  if (delta == 0) {
    h = 0;
  } else if (max == r) {
    h = 60 * fmod((g - b) / delta, 6);
  } else if (max == g) {
    h = 60 * ((b - r) / delta + 2);
  } else if (max == b) {
    h = 60 * ((r - g) / delta + 4);
  }

  if (h < 0) {
    h += 360;
  }

  return round(h);
}

/**
* Maps LED sequences to values.
* @tparam V Type of the value to map to LEDs
* @param ledsSequence Function that returns LED sequence for a given key
* @param values Map of district IDs to values
* @return Mapped LED values
*/
template <typename V>
static std::map<int, V> mapLeds(std::pair<int, int*> (*ledsSequence)(int key), std::map<int, V> values, V (*combiModeHandler)(V kyiv, V kyivObl) = NULL) {
  if (!ledsSequence) {
    return {};
  }
  std::map<int, V> remaped = {};
  for (int i = 0; i < DISTRICTS_COUNT; i++) {
    int regId = DISTRICTS[i].id;
    auto sequence = ledsSequence(regId);
    int ledCount = sequence.first;
    int *ledList = sequence.second;
    if (!ledList) {
      continue;
    }
    V valueForKey = values[regId];
    if (combiModeHandler && regId == KYIV_REGION_ID) {
        V kyivOblValue = values[KYIV_OBL_REGION_ID];
        valueForKey = combiModeHandler(valueForKey, kyivOblValue);
    }
    for (int i = 0; i < ledCount; i++) {
      remaped[ledList[i]] = valueForKey;
    }
    delete[] ledList; // Free the allocated array
  }
  return remaped;
}

static float mapf(float value, float istart, float istop, float ostart, float ostop) {
  return ostart + (ostop - ostart) * ((value - istart) / (istop - istart));
}

static void distributeBrightnessLevelsFor(int dayBrightness, int nightBrightness, int *brightnessLevels, const char* logTitle) {
  int minBrightness = min(dayBrightness, nightBrightness);
  int maxBrightness = max(dayBrightness, nightBrightness);
  float step = (maxBrightness - minBrightness) / (BR_LEVELS_COUNT - 1.0);
  LOG.printf("%s brightness levels: [", logTitle);
  for (int i = 0; i < BR_LEVELS_COUNT; i++) {
    brightnessLevels[i] = round(i == BR_LEVELS_COUNT - 1 ? maxBrightness : minBrightness + i * step), maxBrightness;
    LOG.print(brightnessLevels[i]);
    if (i < BR_LEVELS_COUNT - 1) LOG.print(", ");
  }
  LOG.println("]");
}

static void fillUptime(int uptimeValue, char* uptimeChar) {
  unsigned long seconds = uptimeValue;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  seconds %= 60;
  minutes %= 60;
  if (hours > 0) {
    sprintf(uptimeChar, "%d год. %d хв.", hours, minutes);
  } else {
    sprintf(uptimeChar, "%d хв. %d сек.", minutes, seconds);
  }
}

static void getHaOptions(char* result, const char* options[], int optionsSize) {
  strcpy(result, "");
  int haIndex = 0;
  for (int i = 0; i < optionsSize; i++) {
    const char* option = options[i];
    if (i > 0) {
      strcat(result, ";");
    }
    strcat(result, option);
    haIndex++;
  }
}

static std::pair<int, int*> mapTranscarpatiaStart1(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{0});
    case 13: return std::make_pair(1, new int[1]{1});
    case 21: return std::make_pair(1, new int[1]{2});
    case 27: return std::make_pair(1, new int[1]{3});
    case 8: return std::make_pair(1, new int[1]{4});
    case 5: return std::make_pair(1, new int[1]{5});
    case 10: return std::make_pair(1, new int[1]{6});
    case 14: return std::make_pair(1, new int[1]{7});
    case 25: return std::make_pair(1, new int[1]{8});
    case 20: return std::make_pair(1, new int[1]{9});
    case 22: return std::make_pair(1, new int[1]{10});
    case 16: return std::make_pair(1, new int[1]{11});
    case 28: return std::make_pair(1, new int[1]{12});
    case 12: return std::make_pair(1, new int[1]{13});
    case 23: return std::make_pair(1, new int[1]{14});
    case 9999: return std::make_pair(1, new int[1]{15});
    case 18: return std::make_pair(1, new int[1]{16});
    case 17: return std::make_pair(1, new int[1]{17});
    case 9: return std::make_pair(1, new int[1]{18});
    case 19: return std::make_pair(1, new int[1]{19});
    case 24: return std::make_pair(1, new int[1]{20});
    case 15: return std::make_pair(1, new int[1]{21});
    case 4: return std::make_pair(1, new int[1]{22});
    case 3: return std::make_pair(1, new int[1]{23});
    case 26: return std::make_pair(1, new int[1]{24});
    default: return std::make_pair(0, new int[0]{});
  }
}

static std::pair<int, int*> mapOdessaStart1(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{9});
    case 13: return std::make_pair(1, new int[1]{10});
    case 21: return std::make_pair(1, new int[1]{11});
    case 27: return std::make_pair(1, new int[1]{12});
    case 8: return std::make_pair(1, new int[1]{13});
    case 5: return std::make_pair(1, new int[1]{14});
    case 10: return std::make_pair(1, new int[1]{15});
    case 14: return std::make_pair(1, new int[1]{16});
    case 25: return std::make_pair(1, new int[1]{17});
    case 20: return std::make_pair(1, new int[1]{18});
    case 22: return std::make_pair(1, new int[1]{19});
    case 16: return std::make_pair(1, new int[1]{20});
    case 28: return std::make_pair(1, new int[1]{21});
    case 12: return std::make_pair(1, new int[1]{22});
    case 23: return std::make_pair(1, new int[1]{23});
    case 9999: return std::make_pair(1, new int[1]{24});
    case 18: return std::make_pair(1, new int[1]{0});
    case 17: return std::make_pair(1, new int[1]{1});
    case 9:  return std::make_pair(1, new int[1]{2});
    case 19: return std::make_pair(1, new int[1]{3});
    case 24: return std::make_pair(1, new int[1]{4});
    case 15: return std::make_pair(1, new int[1]{5});
    case 4:  return std::make_pair(1, new int[1]{6});
    case 3:  return std::make_pair(1, new int[1]{7});
    case 26: return std::make_pair(1, new int[1]{8});
    default: return std::make_pair(0, new int[0]{});
  }
}

static std::pair<int, int*> mapTranscarpatiaStart2(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{0});
    case 13: return std::make_pair(1, new int[1]{1});
    case 21: return std::make_pair(1, new int[1]{2});
    case 27: return std::make_pair(1, new int[1]{3});
    case 8: return std::make_pair(1, new int[1]{4});
    case 5: return std::make_pair(1, new int[1]{5});
    case 10: return std::make_pair(1, new int[1]{6});
    case 14: return std::make_pair(0, new int[0]{});
    case 25: return std::make_pair(1, new int[1]{8});
    case 20: return std::make_pair(1, new int[1]{9});
    case 22: return std::make_pair(1, new int[1]{10});
    case 16: return std::make_pair(1, new int[1]{11});
    case 28: return std::make_pair(1, new int[1]{12});
    case 12: return std::make_pair(1, new int[1]{13});
    case 23: return std::make_pair(1, new int[1]{14});
    case 9999: return std::make_pair(1, new int[1]{15});
    case 18: return std::make_pair(1, new int[1]{16});
    case 17: return std::make_pair(1, new int[1]{17});
    case 9:  return std::make_pair(1, new int[1]{18});
    case 19: return std::make_pair(1, new int[1]{19});
    case 24: return std::make_pair(1, new int[1]{20});
    case 15: return std::make_pair(1, new int[1]{21});
    case 4:  return std::make_pair(1, new int[1]{22});
    case 3:  return std::make_pair(1, new int[1]{23});
    case 26: return std::make_pair(1, new int[1]{24});
    case 31: return std::make_pair(1, new int[1]{7});
    default: return std::make_pair(0, new int[0]{});
  }
}

static std::pair<int, int*> mapOdessaStart2(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{9});
    case 13: return std::make_pair(1, new int[1]{10});
    case 21: return std::make_pair(1, new int[1]{11});
    case 27: return std::make_pair(1, new int[1]{12});
    case 8: return std::make_pair(1, new int[1]{13});
    case 5: return std::make_pair(1, new int[1]{14});
    case 10: return std::make_pair(1, new int[1]{15});
    case 14: return std::make_pair(0, new int[0]{});
    case 25: return std::make_pair(1, new int[1]{17});
    case 20: return std::make_pair(1, new int[1]{18});
    case 22: return std::make_pair(1, new int[1]{19});
    case 16: return std::make_pair(1, new int[1]{20});
    case 28: return std::make_pair(1, new int[1]{21});
    case 12: return std::make_pair(1, new int[1]{22});
    case 23: return std::make_pair(1, new int[1]{23});
    case 9999: return std::make_pair(1, new int[1]{24});
    case 18: return std::make_pair(1, new int[1]{0});
    case 17: return std::make_pair(1, new int[1]{1});
    case 9:  return std::make_pair(1, new int[1]{2});
    case 19: return std::make_pair(1, new int[1]{3});
    case 24: return std::make_pair(1, new int[1]{4});
    case 15: return std::make_pair(1, new int[1]{5});
    case 4:  return std::make_pair(1, new int[1]{6});
    case 3:  return std::make_pair(1, new int[1]{7});
    case 26: return std::make_pair(1, new int[1]{8});
    case 31: return std::make_pair(1, new int[1]{16});
    default: return std::make_pair(0, new int[0]{});
  }
}

static std::pair<int, int*> mapTranscarpatiaStart3(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{0});
    case 13: return std::make_pair(1, new int[1]{1});
    case 21: return std::make_pair(1, new int[1]{2});
    case 27: return std::make_pair(1, new int[1]{3});
    case 8: return std::make_pair(1, new int[1]{4});
    case 5: return std::make_pair(1, new int[1]{5});
    case 10: return std::make_pair(1, new int[1]{6});
    case 14: return std::make_pair(1, new int[1]{7});
    case 25: return std::make_pair(1, new int[1]{9});
    case 20: return std::make_pair(1, new int[1]{10});
    case 22: return std::make_pair(1, new int[1]{11});
    case 16: return std::make_pair(1, new int[1]{12});
    case 28: return std::make_pair(1, new int[1]{13});
    case 12: return std::make_pair(1, new int[1]{14});
    case 23: return std::make_pair(1, new int[1]{15});
    case 9999: return std::make_pair(1, new int[1]{16});
    case 18: return std::make_pair(1, new int[1]{17});
    case 17: return std::make_pair(1, new int[1]{18});
    case 9: return std::make_pair(1, new int[1]{19});
    case 19: return std::make_pair(1, new int[1]{20});
    case 24: return std::make_pair(1, new int[1]{21});
    case 15: return std::make_pair(1, new int[1]{22});
    case 4: return std::make_pair(1, new int[1]{23});
    case 3: return std::make_pair(1, new int[1]{24});
    case 26: return std::make_pair(1, new int[1]{25});
    case 31: return std::make_pair(1, new int[1]{8});
    default: return std::make_pair(0, new int[0]{});
  }
}

static std::pair<int, int*> mapOdessaStart3(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{9});
    case 13: return std::make_pair(1, new int[1]{10});
    case 21: return std::make_pair(1, new int[1]{11});
    case 27: return std::make_pair(1, new int[1]{12});
    case 8: return std::make_pair(1, new int[1]{13});
    case 5: return std::make_pair(1, new int[1]{14});
    case 10: return std::make_pair(1, new int[1]{15});
    case 14: return std::make_pair(1, new int[1]{16});
    case 25: return std::make_pair(1, new int[1]{18});
    case 20: return std::make_pair(1, new int[1]{19});
    case 22: return std::make_pair(1, new int[1]{20});
    case 16: return std::make_pair(1, new int[1]{21});
    case 28: return std::make_pair(1, new int[1]{22});
    case 12: return std::make_pair(1, new int[1]{23});
    case 23: return std::make_pair(1, new int[1]{24});
    case 9999: return std::make_pair(1, new int[1]{25});
    case 18: return std::make_pair(1, new int[1]{0});
    case 17: return std::make_pair(1, new int[1]{1});
    case 9:  return std::make_pair(1, new int[1]{2});
    case 19: return std::make_pair(1, new int[1]{3});
    case 24: return std::make_pair(1, new int[1]{4});
    case 15: return std::make_pair(1, new int[1]{5});
    case 4:  return std::make_pair(1, new int[1]{6});
    case 3:  return std::make_pair(1, new int[1]{7});
    case 26: return std::make_pair(1, new int[1]{8});
    case 31: return std::make_pair(1, new int[1]{17});
    default: return std::make_pair(0, new int[0]{});
  }
}

static std::pair<int, int*> mapTranscarpatiaStart4(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{0});
    case 13: return std::make_pair(1, new int[1]{1});
    case 21: return std::make_pair(1, new int[1]{2});
    case 27: return std::make_pair(1, new int[1]{3});
    case 8: return std::make_pair(1, new int[1]{4});
    case 5: return std::make_pair(1, new int[1]{5});
    case 10: return std::make_pair(1, new int[1]{6});
    case 14: return std::make_pair(1, new int[1]{7});
    case 25: return std::make_pair(1, new int[1]{8});
    case 20: return std::make_pair(1, new int[1]{9});
    case 22: return std::make_pair(1, new int[1]{10});
    case 16: return std::make_pair(1, new int[1]{11});
    case 28: return std::make_pair(1, new int[1]{12});
    case 12: return std::make_pair(1, new int[1]{13});
    case 23: return std::make_pair(1, new int[1]{14});
    case 9999: return std::make_pair(1, new int[1]{15});
    case 18: return std::make_pair(1, new int[1]{16});
    case 17: return std::make_pair(1, new int[1]{17});
    case 9:  return std::make_pair(1, new int[1]{18});
    case 19: return std::make_pair(1, new int[1]{19});
    case 24: return std::make_pair(1, new int[1]{20});
    case 15: return std::make_pair(1, new int[1]{21});
    case 4:  return std::make_pair(1, new int[1]{22});
    case 3:  return std::make_pair(1, new int[1]{23});
    case 26: return std::make_pair(1, new int[1]{24});
    case 31: return std::make_pair(1, new int[1]{7});
    default: return std::make_pair(0, new int[0]{});
  }
}

static std::pair<int, int*> mapOdessaStart4(int key) {
  switch (key) {
    case 11: return std::make_pair(1, new int[1]{9});
    case 13: return std::make_pair(1, new int[1]{10});
    case 21: return std::make_pair(1, new int[1]{11});
    case 27: return std::make_pair(1, new int[1]{12});
    case 8: return std::make_pair(1, new int[1]{13});
    case 5: return std::make_pair(1, new int[1]{14});
    case 10: return std::make_pair(1, new int[1]{15});
    case 14: return std::make_pair(1, new int[1]{16});
    case 25: return std::make_pair(1, new int[1]{17});
    case 20: return std::make_pair(1, new int[1]{18});
    case 22: return std::make_pair(1, new int[1]{19});
    case 16: return std::make_pair(1, new int[1]{20});
    case 28: return std::make_pair(1, new int[1]{21});
    case 12: return std::make_pair(1, new int[1]{22});
    case 23: return std::make_pair(1, new int[1]{23});
    case 9999: return std::make_pair(1, new int[1]{24});
    case 18: return std::make_pair(1, new int[1]{0});
    case 17: return std::make_pair(1, new int[1]{1});
    case 9:  return std::make_pair(1, new int[1]{2});
    case 19: return std::make_pair(1, new int[1]{3});
    case 24: return std::make_pair(1, new int[1]{4});
    case 15: return std::make_pair(1, new int[1]{5});
    case 4:  return std::make_pair(1, new int[1]{6});
    case 3:  return std::make_pair(1, new int[1]{7});
    case 26: return std::make_pair(1, new int[1]{8});
    case 31: return std::make_pair(1, new int[1]{16});
    default: return std::make_pair(0, new int[0]{});
  }
}

static bool isInArray(int value, int* array, int arraySize) {
  if (!array || arraySize <= 0) {
    return false;
  }
  for (int i = 0; i < arraySize; i++) {
    if (array[i] == value) return true;
  }
  return false;
}

static int mapIndexToRegionId(int index) {
  switch (index) {
    case 0: return 11; // Закарпатська обл.
    case 1: return 13; // Івано-Франківська обл.
    case 2: return 21; // Тернопільська обл.
    case 3: return 27; // Львівська обл.
    case 4: return 8; // Волинська обл.
    case 5: return 5; // Рівненська обл.
    case 6: return 10; // Житомирська обл.
    case 7: return 14; // Київська обл.
    case 8: return 25; // Чернігівська обл.
    case 9: return 20; // Сумська обл.
    case 10: return 22; // Харківська обл.
    case 11: return 16; // Луганська обл.
    case 12: return 28; // Донецька обл.
    case 13: return 12; // Запорізька обл.
    case 14: return 23; // Херсонська обл.
    case 15: return 9999; // Автономна Республіка Крим
    case 16: return 18; // Одеська обл.
    case 17: return 17; // Миколаївська обл.
    case 18: return 9; // Дніпропетровська обл.
    case 19: return 19; // Полтавська обл.
    case 20: return 24; // Черкаська обл.
    case 21: return 15; // Кіровоградська обл.
    case 22: return 4; // Вінницька обл.
    case 23: return 3; // Хмельницька обл.
    case 24: return 26; // Чернівецька обл.
    case 25: return 31; // м. Київ
    default: return -1;
  }
}
