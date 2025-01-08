#include "JaamButton.h"
#include <OneButton.h>


int button1Pin = -1;
int button2Pin = -1;
OneButton button1;
OneButton button2;

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
    }
}

void JaamButton::setButton2Pin(int pin) {
    button2Pin = pin;
    if (isButton1Enabled()) {
        button2.setup(button2Pin);
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

bool JaamButton::isButton1Enabled() {
    return button1Pin >= 0;
}

bool JaamButton::isButton2Enabled() {
    return button2Pin >= 0;
}

bool JaamButton::isAnyButtonEnabled() {
    return isButton1Enabled() || isButton2Enabled();
}
