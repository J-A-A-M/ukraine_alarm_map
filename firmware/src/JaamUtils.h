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
* Fuction to check what alert last time to use in home district alarm calculation for specific alert
* @param state state alarm with status and time of last status change
* @param notification time of last notification
* @param current_time timeClient.unixGMT()
* @param period time in seconds where status cant be changes
*/
static bool isLocalAlarmNow(std::pair<int, long int> state, long notification, int current_time, int period) {
  if (state.first == 1) {
    return true;
  }
  return current_time - notification < period;
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

static bool isInArray(int value, int* array, int arraySize) {
  if (!array || arraySize <= 0) {
    return false;
  }
  for (int i = 0; i < arraySize; i++) {
    if (array[i] == value) return true;
  }
  return false;
}