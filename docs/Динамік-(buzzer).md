## Загальна інформація
**Починаючи з версії 3.8 прошивка підтримує відтворення звуків та мелодій через динамік (buzzer).**

Мелодії, та сигнали можна налаштовувати на різні події, такі як:
* Увімкнення мапи (можна обрати мелодію зі списку)
* Режимі "Хвилина мовчання" (відтворюються звуки годинника протягом хвилини та Гімн України після)
* Тривога у домашньому регіоні (можна обрати мелодію зі списку)
* Відбій тривоги у домашньому регіоні (можна обрати мелодію зі списку)
* Звукове сповіщення щогодини
* Сигнали при натисканні кнопки (різні звуки для Click та Long Click)

Є можливість увімкнути чи вимкнути звуки для кожної події незалежно, а також окрема опція для вимикання всіх звуків у "нічному режимі".

## Технічна інформація
Для можливості відтворювати звуки до ESP32 має бути підключено динамік (типу passive buzzer).

Приклад динаміка:

<img src="https://github.com/v00g100skr/ukraine_alarm_map/assets/925166/73225c05-21f3-4ed3-aa3a-c8b95ee0f692" width=500>

Схема підключення до ESP32:

Buzzer | ESP32
-- | --
\- | GND
\+ | GPIO 30

<img src="https://github.com/v00g100skr/ukraine_alarm_map/assets/925166/86f82ee2-c43f-4557-ac22-3ba469c38f14" width=500>

Для підключення підходить будь-який вільний IO пін ESP32.
Цей пін необхідно вказати в DEV налаштуваннях мапи, після цього пристрій перезавантажиться.

Мінімальний скетч для тестування динаміка (використовується бібліотека [Melody Player](https://github.com/fabianoriccardi/melody-player)):
```
/**
 * Play a simple melody hard-coded in the sketch.
 *
 * You can observe the difference between the blocking play(..),
 * which blocks the sketch for the entire duration of the melody, and
 * playAsync(..) which returns immediately.
 */
#include <melody_player.h>
#include <melody_factory.h>

int buzzerPin = 30;
const char uaAnthem[] PROGMEM = "UkraineAnthem:d=4,o=5,b=200:2d5,4d5,32p,4d5,32p,4d5,32p,4c5,4d5,4d#5,2f5,4f5,4d#5,2d5,2c5,2a#4,2d5,2a4,2d5,1g4,32p,1g4";

// specify the buzzer's pin and the standby voltage level
MelodyPlayer player(buzzerPin, HIGH);

void setup() {
  Serial.begin(115200);

  Serial.println();
  Serial.println("Melody Player - Simple non-blocking play");

  // Load melody
  Melody melody = MelodyFactory.loadRtttlString(uaAnthem);

  // get basic info about the melody
  Serial.println(String(" Title:") + melody.getTitle());
  Serial.println(String(" Time unit:") + melody.getTimeUnit());

  Serial.print("Start playing in non-blocking mode...");
  player.playAsync(melody);
  Serial.println(" Melody is playing!");
}

void loop() {}
```

