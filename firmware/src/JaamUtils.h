#include "Constants.h"

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

  while (token) {
    if (isdigit(token[0])) {
      if (firmware.major == 0)
        firmware.major = atoi(token);
      else if (firmware.minor == 0)
        firmware.minor = atoi(token);
      else if (firmware.patch == 0)
        firmware.patch = atoi(token);
    } else if (firmware.betaBuild == 0 && token[0] == 'b' && strcmp(token, "bin") != 0) {
      firmware.isBeta = true;
      firmware.betaBuild = atoi(token + 1); // Skip the 'b' character
    }
    token = strtok(NULL, ".-");
  }

  free(versionCopy);

  return firmware;
}

static void fillFwVersion(char* result, Firmware firmware) {
  char patch[5] = "";
  if (firmware.patch > 0) {
    sprintf(patch, ".%d", firmware.patch);
  }
  char beta[5] = "";
  if (firmware.isBeta) {
    sprintf(beta, "-b%d", firmware.betaBuild);
  }
#if LITE
  sprintf(result, "%d.%d%s%s-lite", firmware.major, firmware.minor, patch, beta);
#else
  sprintf(result, "%d.%d%s%s", firmware.major, firmware.minor, patch, beta);
#endif
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
  return round(h);
}

template <typename T>

static void adaptLeds(int kyivDistrictMode, T *leds, T *adaptedLeds, int size, int offset) {
  T lastValue = leds[size - 1];
  for (uint16_t i = 0; i < size; i++) {
    adaptedLeds[i] = leds[i];
  }
  if (kyivDistrictMode == 2) {
    adaptedLeds[7 + offset] = leds[25];
  }
  if (kyivDistrictMode == 3) {
    for (int i = 24; i >= 8 + offset; i--) {
      adaptedLeds[i + 1] = leds[i];
    }
    adaptedLeds[8 + offset] = lastValue;
  }
}

static int calculateOffset(int initial_position, int offset) {
  int position;
  if (initial_position == 25) {
    position = 25;
  } else {
    position = initial_position + offset;
    if (position >= 25) {
      position -= 25;
    }
  }
  return position;
}

static int calculateOffsetDistrict(int kyivDistrictMode, int initialPosition, int offset) {
  int position;
  if (initialPosition == 25) {
    position = 25;
  } else {
    position = initialPosition + offset;
    if (position >= 25) {
      position -= 25;
    }
  }
  if (kyivDistrictMode == 2) {
    if (position == 25) {
      return 7 + offset;
    }
  }
  if (kyivDistrictMode == 3) {

    if (position == 25) {
      return 8 + offset;
    }
    if (position > 7 + offset) {
      return position + 1;
    }
  }
  if (kyivDistrictMode == 4) {
    if (position == 25) {
      return 7 + offset;
    }
  }
  return position;
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
