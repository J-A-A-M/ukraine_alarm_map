#include "JaamDisplay.h"

Adafruit_SSD1306 *ssd1306;
Adafruit_SH110X *sh110x;
JaamDisplay::DisplayModel displayModel;
bool displayConnected;
#define MAX_DISPLAY_BRIGHTNESS_SSD1306 0xCF
#define MAX_DISPLAY_BRIGHTNESS_SH110X 0x7F
#define MIN_DISPLAY_BRIGHTNESS 0x01

const unsigned char trident_small[] PROGMEM = {
  0x04, 0x00, 0x80, 0x10, 0x06, 0x01, 0xc0, 0x30, 0x07, 0x01, 0xc0, 0x70, 0x07, 0x81, 0xc0, 0xf0,
  0x07, 0xc1, 0xc1, 0xf0, 0x06, 0xc1, 0xc1, 0xb0, 0x06, 0xe1, 0xc3, 0xb0, 0x06, 0x61, 0xc3, 0x30,
  0x06, 0x71, 0xc7, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30,
  0x06, 0x31, 0xc6, 0x30, 0x06, 0x31, 0xc6, 0x30, 0x06, 0xf1, 0xc7, 0xb0, 0x07, 0xe1, 0xc3, 0xf0,
  0x07, 0x83, 0xe0, 0xf0, 0x07, 0x03, 0x60, 0x70, 0x07, 0x87, 0x70, 0xf0, 0x07, 0xc6, 0x31, 0xf0,
  0x06, 0xee, 0x3b, 0xb0, 0x06, 0x7f, 0x7f, 0x30, 0x06, 0x3d, 0xde, 0x30, 0x06, 0x19, 0xcc, 0x30,
  0x07, 0xff, 0xff, 0xf0, 0x03, 0xff, 0xff, 0xe0, 0x01, 0xfc, 0x9f, 0xc0, 0x00, 0x0c, 0xd8, 0x00,
  0x00, 0x07, 0xf0, 0x00, 0x00, 0x03, 0xe0, 0x00, 0x00, 0x01, 0xc0, 0x00, 0x00, 0x00, 0x80, 0x00
};

JaamDisplay::JaamDisplay() {
    // Constructor implementation
}

bool detectDisplay() {
  Wire.begin();
  Wire.beginTransmission(0x3C);
  uint8_t error = Wire.endTransmission();
  if (error == 0) {
    Serial.println("Display was FOUND on address 0x3C! Success.");
    return true;
  } else {
    Serial.println("Display NOT found! Checked address - 0x3C");
    return false;
  }
}

bool JaamDisplay::begin(DisplayModel type,int displayWidth, int displayHeight) {
    displayConnected = type > 0 && detectDisplay();
    Serial.printf("Display model: %d\n", type);
    if (displayConnected) {
        displayModel = type;
        switch (type) {
        case JaamDisplay::SSD1306:
        ssd1306 = new Adafruit_SSD1306(displayWidth, displayHeight, &Wire, -1);
        ssd1306->begin(SSD1306_SWITCHCAPVCC, 0x3C);
            break;
        case JaamDisplay::SH1106G:
        sh110x = new Adafruit_SH1106G(displayWidth, displayHeight, &Wire, -1);
        ((Adafruit_SH1106G*) sh110x)->begin(0x3C);
            break;
        case JaamDisplay::SH1107:
        sh110x = new Adafruit_SH1107(displayWidth, displayHeight, &Wire, -1);
        ((Adafruit_SH1107*) sh110x)->begin(0x3C);
            break;
        default:
            break;
        }
    }
    return displayConnected;
}

void JaamDisplay::display() {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->display();
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->display();
        break;
    default:
        break;
    }
}

void JaamDisplay::clearDisplay() {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->clearDisplay();
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->clearDisplay();
        break;
    default:
        break;
    }
}

void JaamDisplay::dim(bool dim) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->ssd1306_command(SSD1306_SETCONTRAST);
        ssd1306->ssd1306_command(dim ? MIN_DISPLAY_BRIGHTNESS : MAX_DISPLAY_BRIGHTNESS_SSD1306);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->setContrast(dim ? MIN_DISPLAY_BRIGHTNESS : MAX_DISPLAY_BRIGHTNESS_SH110X);
        break;
    default:
        break;
    }
}

void JaamDisplay::setCursor(int x, int y) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->setCursor(x, y);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:   
        sh110x->setCursor(x, y);
        break;
    default:
        break;
    }
}

void JaamDisplay::setTextColor(int color) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->setTextColor(color);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->setTextColor(color);
        break;
    default:
        break;
    }
}

void JaamDisplay::setTextSize(int size) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->setTextSize(size);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->setTextSize(size);
        break;
    default:
        break;
    }
}

void JaamDisplay::getTextBounds(const char *string, int16_t x, int16_t y, int16_t *x1, int16_t *y1, uint16_t *w, uint16_t *h) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->getTextBounds(string, x, y, x1, y1, w, h);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->getTextBounds(string, x, y, x1, y1, w, h);
        break;
    default:
        break;
    }
}

size_t JaamDisplay::print(const char *str) {
    if (!displayConnected) return 0;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        return ssd1306->print(str);
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        return sh110x->print(str);
    default:
        return 0;
    }
}

size_t JaamDisplay::println(const char *str) {
    if (!displayConnected) return 0;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        return ssd1306->println(str);
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        return sh110x->println(str);
    default:
        return 0;
    }
}

void JaamDisplay::setTextWrap(bool wrap) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->setTextWrap(wrap);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->setTextWrap(wrap);
        break;
    default:
        break;
    }
}

void JaamDisplay::invertDisplay(bool invert) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->invertDisplay(invert);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->invertDisplay(invert);
        break;
    default:
        break;
    }
}

int JaamDisplay::width() {
    if (!displayConnected) return 0;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        return ssd1306->width();
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        return sh110x->width();
    default:
        return 0;
    }
}

int JaamDisplay::height() {
    if (!displayConnected) return 0;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        return ssd1306->height();
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        return sh110x->height();
    default:
        return 0;
    }
}

void JaamDisplay::drawBitmap(int x, int y, const uint8_t *bitmap, int w, int h, int color) {
    if (!displayConnected) return;
    switch (displayModel) {
    case JaamDisplay::SSD1306:
        ssd1306->drawBitmap(x, y, bitmap, w, h, color);
        break;
    case JaamDisplay::SH1106G:
    case JaamDisplay::SH1107:
        sh110x->drawBitmap(x, y, bitmap, w, h, color);
        break;
    default:
        break;
    }
}

void utf8cyr(char* target, const char* source) {
  int i, k;
  unsigned char n;
  char m[2] = { '0', '\0' };
  strcpy(target, "");

  k = strlen(source);
  i = 0;
  while (i < k) {
    n = source[i];
    i++;
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
    strcat(target, m);
  }
}

const unsigned char* getIcon(JaamDisplay::Icon icon) {
    switch (icon) {
    case JaamDisplay::TRINDENT:
        return trident_small;
    default:
        return nullptr;
    }
}

int JaamDisplay::getTextSizeToFitDisplay(const char* text) {
    if (!displayConnected) return 0;
    int16_t x;
    int16_t y;
    uint16_t textWidth;
    uint16_t textHeight;

    setTextWrap(false);
    char utf8Text[strlen(text)];
    utf8cyr(utf8Text, text);
    setCursor(0, 0);
    setTextSize(4);
    getTextBounds(utf8Text, 0, 0, &x, &y, &textWidth, &textHeight);

    if (height() > 32 && width() >= textWidth) {
        setTextWrap(true);
        return 4;
    }

    setTextSize(3);
    getTextBounds(utf8Text, 0, 0, &x, &y, &textWidth, &textHeight);

    if (width() >= textWidth) {
        setTextWrap(true);
        return 3;
    }

    setTextSize(2);
    getTextBounds(utf8Text, 0, 0, &x, &y, &textWidth, &textHeight);

    setTextWrap(true);
    if (width() >= textWidth) {
        return 2;
    }
    else {
        return 1;
    }
}

void JaamDisplay::displayMessage(const char* message, const char* title = "", int messageTextSize = -1) {
    if (messageTextSize == -1) {
    messageTextSize = getTextSizeToFitDisplay(message);
  }
  clearDisplay();
  bool withTitle = strlen(title) > 0;
  if (withTitle) {
    char cyrTitle[strlen(title)];
    setCursor(1, 1);
    setTextSize(1);
    utf8cyr(cyrTitle, title);
    println(cyrTitle);
  }
  displayCenter(message, withTitle, messageTextSize);
}

void JaamDisplay::displayTextWithIcon(Icon icon, const char* text1, const char* text2, const char* text3) {
    clearDisplay();
    if (icon != Icon::NO_ICON) {
        int16_t centerY = (height() - 32) / 2;
        drawBitmap(0, centerY, getIcon(icon), 32, 32, 1);
    }
    int textSize = 2;
    int gap = 32;
    bool hasText2 = strlen(text2) > 0;
    char string1[20] = "";
    char string2[20] = "";
    char string3[20] = "";
    utf8cyr(string1, text1);
    utf8cyr(string3, text3);
    if (hasText2) {
        textSize = 1;
        gap = 40;
        utf8cyr(string2, text2);
    }
    setTextSize(textSize);
    int16_t x;
    int16_t y;
    uint16_t textWidth;
    uint16_t textHeight;
    getTextBounds(string1, 0, 0, &x, &y, &textWidth, &textHeight);
    setCursor(gap, ((height() - textHeight) / 2) - 9);
    print(string1);
    if (hasText2) {
        setCursor(gap, ((height() - textHeight) / 2));
        print(string2);
    }
    setCursor(gap, ((height() - textHeight) / 2) + 9);
    print(string3);
    display();
}

void JaamDisplay::displayCenter(const char* text, bool withTitle, int textSize) {
  int16_t x;
  int16_t y;
  uint16_t textWidth;
  uint16_t textHeight;
  char utf8Text[strlen(text)];
  utf8cyr(utf8Text, text);
  setTextSize(textSize);
  getTextBounds(utf8Text, 0, 0, &x, &y, &textWidth, &textHeight);
  int offsetY = (withTitle ? 10 : 0);
  int cursorX = (width() - textWidth) / 2;
  int cursorY = max(((height() - textHeight - offsetY) / 2), 0) + offsetY;
  setCursor(cursorX, cursorY);
  println(utf8Text);
  display();
}
