#include "JaamButton.h"
#include <OneButton.h>

typedef void (*duringLongClickCallback)(JaamButton::Action action);

int button1Pin = -1;
int button2Pin = -1;
OneButton button1;
OneButton button2;
duringLongClickCallback button1DuringLongClickListener;
duringLongClickCallback button2DuringLongClickListener;


JaamButton::JaamButton() {
}

void JaamButton::tick() {
    if (isButton1Enabled()) button1.tick();
    if (isButton2Enabled()) button2.tick();
}

void JaamButton::setButton1Pin(int pin) {
    button1Pin = pin;
    if (isButton1Enabled()) {
        button1.setup(button1Pin);
        button1.setLongPressIntervalMs(100);
    }
}

void JaamButton::setButton2Pin(int pin) {
    button2Pin = pin;
    if (isButton1Enabled()) {
        button2.setup(button2Pin);
        button2.setLongPressIntervalMs(100);
    }
}

void JaamButton::setButton1ClickListener(void (*listener)(void)) {
    if (isButton1Enabled()) {
        button1.attachClick(listener);
    }
}

void JaamButton::setButton2ClickListener(void (*listener)(void)) {
    if (isButton2Enabled()) {
        button2.attachClick(listener);
    }
}

void JaamButton::setButton1LongClickListener(void (*listener)(void)) {
    if (isButton1Enabled()) {
        button1.attachLongPressStart(listener);
    }
}

void JaamButton::setButton2LongClickListener(void (*listener)(void)) {
    if (isButton2Enabled()) {
        button2.attachLongPressStart(listener);
    }
}

void JaamButton::setButton1DuringLongClickListener(void (*listener)(Action action)) {
    if (isButton1Enabled()) {
        button1DuringLongClickListener = listener;
        button1.attachDuringLongPress([] {
            button1DuringLongClickListener(DURING_LONG_CLICK);
        });
        button1.attachLongPressStop([] {
            button1DuringLongClickListener(LONG_CLICK_END);
        });
    }
}

void JaamButton::setButton2DuringLongClickListener(void (*listener)(Action action)) {
    if (isButton2Enabled()) {
        button2DuringLongClickListener = listener;
        button2.attachDuringLongPress([]() {
            button2DuringLongClickListener(DURING_LONG_CLICK);
        });
        button2.attachLongPressStop([]() {
            button2DuringLongClickListener(LONG_CLICK_END);
        });
    }
}

bool JaamButton::isButton1Enabled() {
    return button1Pin >= 0;
}

bool JaamButton::isButton2Enabled() {
    return button2Pin >= 0;
}

bool JaamButton::isAnyButtonEnabled() {
    return isButton1Enabled() || isButton2Enabled();
}
