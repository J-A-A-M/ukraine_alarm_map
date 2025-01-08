class JaamButton {
public:
    JaamButton();
    void tick();
    void setButton1Pin(int pin);
    void setButton2Pin(int pin);
    void setButton1ClickListener(void (*listener)(void));
    void setButton2ClickListener(void (*listener)(void));
    void setButton1LongClickListener(void (*listener)(void));
    void setButton2LongClickListener(void (*listener)(void));
    bool isButton1Enabled();
    bool isButton2Enabled();
    bool isAnyButtonEnabled();
};