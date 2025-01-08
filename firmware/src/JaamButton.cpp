#include "JaamButton.h"
#include <OneButton.h>


OneButton button1;
OneButton button2;

JaamButton::JaamButton() {
}

void JaamButton::tick() {
    if (isButton1Enabled()) button1.tick();
    if (isButton2Enabled()) button2.tick();
}

void JaamButton::setButton1Pin(int pin) {
    button1.setup(pin);
}

void JaamButton::setButton2Pin(int pin) {
    button2.setup(pin);
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
    return button1.pin() >= 0;
}

bool JaamButton::isButton2Enabled() {
    return button2.pin() >= 0;
}

bool JaamButton::isAnyButtonEnabled() {
    return isButton1Enabled() || isButton2Enabled();
}
