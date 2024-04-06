#include "JaamDisplay.h"

Adafruit_SSD1306 *ssd1306;
Adafruit_SH1106G *sh1106g;
Adafruit_SH1107 *sh1107;
JaamDisplay::DisplayModel displayModel;
bool displayConnected;
#define MAX_DISPLAY_BRIGHTNESS_SSD1306 0xCF
#define MAX_DISPLAY_BRIGHTNESS_SH110X 0x7F
#define MIN_DISPLAY_BRIGHTNESS 0x01

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

bool JaamDisplay::init(JaamDisplay::DisplayModel type,int displayWidth, int displayHeight) {
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
        sh1106g = new Adafruit_SH1106G(displayWidth, displayHeight, &Wire, -1);
        sh1106g->begin(0x3C);
            break;
        case JaamDisplay::SH1107:
        sh1107 = new Adafruit_SH1107(displayWidth, displayHeight, &Wire, -1);
        sh1107->begin(0x3C);
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
        sh1106g->display();
        break;
    case JaamDisplay::SH1107:
        sh1107->display();
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
        sh1106g->clearDisplay();
        break;
    case JaamDisplay::SH1107:
        sh1107->clearDisplay();
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
        sh1106g->setContrast(dim ? MIN_DISPLAY_BRIGHTNESS : MAX_DISPLAY_BRIGHTNESS_SH110X);
        break;
    case JaamDisplay::SH1107:
        sh1107->setContrast(dim ? MIN_DISPLAY_BRIGHTNESS : MAX_DISPLAY_BRIGHTNESS_SH110X);
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
        sh1106g->setCursor(x, y);
        break;
    case JaamDisplay::SH1107:   
        sh1107->setCursor(x, y);
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
        sh1106g->setTextColor(color);
        break;
    case JaamDisplay::SH1107:
        sh1107->setTextColor(color);
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
        sh1106g->setTextSize(size);
        break;
    case JaamDisplay::SH1107:
        sh1107->setTextSize(size);
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
        sh1106g->getTextBounds(string, x, y, x1, y1, w, h);
        break;
    case JaamDisplay::SH1107:
        sh1107->getTextBounds(string, x, y, x1, y1, w, h);
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
        return sh1106g->print(str);
    case JaamDisplay::SH1107:
        return sh1107->print(str);
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
        return sh1106g->println(str);
    case JaamDisplay::SH1107:
        return sh1107->println(str);
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
        sh1106g->setTextWrap(wrap);
        break;
    case JaamDisplay::SH1107:
        sh1107->setTextWrap(wrap);
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
        sh1106g->invertDisplay(invert);
        break;
    case JaamDisplay::SH1107:
        sh1107->invertDisplay(invert);
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
        return sh1106g->width();
    case JaamDisplay::SH1107:
        return sh1107->width();
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
        return sh1106g->height();
    case JaamDisplay::SH1107:
        return sh1107->height();
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
        sh1106g->drawBitmap(x, y, bitmap, w, h, color);
        break;
    case JaamDisplay::SH1107:
        sh1107->drawBitmap(x, y, bitmap, w, h, color);
        break;
    default:
        break;
    }
}
