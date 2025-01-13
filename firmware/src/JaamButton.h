class JaamButton {

public:
    enum Action {
        SINGLE_CLICK,
        LONG_CLICK,
        DURING_LONG_CLICK,
        LONG_CLICK_END
    };
    JaamButton();
    void tick();
    void setButton1Pin(int pin);
    void setButton2Pin(int pin);
    void setButton1ClickListener(void (*listener)(void));
    void setButton2ClickListener(void (*listener)(void));
    void setButton1LongClickListener(void (*listener)(void));
    void setButton2LongClickListener(void (*listener)(void));
    void setButton1DuringLongClickListener(void (*listener)(Action action));
    void setButton2DuringLongClickListener(void (*listener)(Action action));
    bool isButton1Enabled();
    bool isButton2Enabled();
    bool isAnyButtonEnabled();
};
