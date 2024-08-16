#include <async.h>

void blinkLed();
void stopInterval();

Async asyncEngine = Async(); // Instances the engine
short id = -1;

void setup() {
  pinMode(13, OUTPUT);

  id = asyncEngine.setInterval(blinkLed, 10); // Save the id to stop later
  asyncEngine.setTimeout(stopInterval, 10000); // Stops the blinking function after 10 seconds
}

void loop() {
  asyncEngine.run(); // Runing the engine
}

/*
  Blink the internal led 1 time per second
  Using millis to avoid blocking code
  millis: https://www.arduino.cc/reference/en/language/functions/time/millis/
*/
void blinkLed() {
  static unsigned long start = millis();

  if((millis() - start) >= 500 && (millis() - start) < 1000) {
    digitalWrite(13, HIGH);
  }

  if((millis() - start) >= 1000) {
    digitalWrite(13, LOW);
    start = millis();
  }
}

/*
  Interrupts the interval that causes the led to blink
*/
void stopInterval() {
  digitalWrite(13, LOW);
  asyncEngine.clearInterval(id);
}
