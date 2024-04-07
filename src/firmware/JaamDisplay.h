
#include <Adafruit_SSD1306.h>
#include <Adafruit_SH110X.h>

class JaamDisplay {

public:
    enum DisplayModel {
        NONE = 0,
        SSD1306 = 1,
        SH1106G = 2,
        SH1107 = 3,
    };
    
    enum Icon {
        NO_ICON = 0,
        TRINDENT = 1,
    };

    JaamDisplay();
    bool begin(DisplayModel mode, int displayWidth, int displayHeight);
    void display();
    void clearDisplay();
    void dim(bool dim);
    void setCursor(int x, int y);
    void setTextColor(int color);
    void setTextSize(int size);
    void setTextWrap(bool wrap);
    void invertDisplay(bool i);
    int width();
    int height();
    int getTextSizeToFitDisplay(const char* text);
    void displayCenter(const char* text, bool withTitle, int textSize);
    void displayMessage(const char* message, const char* title, int messageTextSize);
    void displayTextWithIcon(Icon icon, const char* text1, const char* text2, const char* text3);
    void drawBitmap(int x, int y, const uint8_t *bitmap, int w, int h, int color);
    void getTextBounds(const char *string, int16_t x, int16_t y, int16_t *x1,
                     int16_t *y1, uint16_t *w, uint16_t *h);
    size_t print(const char *str);
    size_t println(const char *str);
};