[![SWUbanner](https://github.com/vshymanskyy/StandWithUkraine/blob/main/badges/StandWithUkraine.svg)](http://stand-with-ukraine.pp.ua/)
[![SWUbanner](https://github.com/vshymanskyy/StandWithUkraine/blob/main/badges/RussianWarship.svg)](http://stand-with-ukraine.pp.ua/)

Репозиторій містить файли прошивки JAAM. JAAM це прошивка для ESP32, що дозволяє за допомогою розміщений на мапі України адресних світлодіодів відображати таку інформацію: повітряні тривоги, погода, візуальні зображення накшталт прапору України. Крім цього, є окремий диспей, який може відображати потончий час, погоду та сервісні повідомлення

<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/map-alerts.jpg" width="400"/><img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/map-weather.jpg" width="400"/><img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/map-flag.jpg" width="400"/>



Вітаю Вас в репозіторії проєкту JAAM - Just another alerts map :-)

<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-full.png" width="600"/>


[WIKI по прошивці](https://github.com/v00g100skr/ukraine_alarm_map/wiki)

[Багтрекер](https://github.com/v00g100skr/ukraine_alarm_map/issues)

[Питання та пропозиції](https://github.com/v00g100skr/ukraine_alarm_map/discussions)

-->> [ТЕЛЕГРАМ КАНАЛ ПРОЕКТУ](https://t.me/jaam_project) <<--

-->> [ПОРТАЛ ДАНИХ](http://alerts.net.ua) <<--

Прошивка використовує бібліотеку **_NeoPixelBus_** (треба додатково встановити в Arduinо IDE по аналогії з іншими попередніми, останню версію брати [тут](https://github.com/Makuna/NeoPixelBus))

Прошивка використовує _**async**_ в роботі, що дозволяє запускати декілька процесів одночасно і більш швидко реагувати на зміни

Прошивка використовує _**власний сервер даних**_ [alerts.net.ua](http://alerts.net.ua/) для отримування даних про тривоги і погоду

Прошивка використовує _**TCP-сокет**_ для коннекта з сервером даних, що дозволяє майже миттєво отримувати оновлення даних

### Прошивка має такі можливості: 
 - режим відображення повітряних тривог, оснований на офіційному api https://www.ukrainealarm.com/
 - режим відображення погоди, оснований на даних сайту https://openweathermap.org/
 - режим прапора
 - режим offline - мапа не відображає нічого

### Для отримання даних не треба мати ключі для апи тривог або openweathermap - все вже є в нашому api

Мапа може бути обладнана _**дисплеєм**_ (128 * 32 SSD1306 та 128 * 64 SSD1306). 

### Режим дисплея вмикається окремо через налаштування:
 - поточний час
 - погода
 - також є сервісні сповіщення при старті мапи та при проблемних ситуаціях з мапою

### Мапа має _**вбудований web-сервер**_ 
для керування всіми налаштуваннями. Сторінка керування знаходиться по адресі [alarmmap.local](http://alarmmap.local) (або по ip). Також доступна сервісна сторінка  [alarmmap.local:8080](http://alarmmap.local:8080), де можна змініти wifi, перевантажити мапу або перепрошити, якшо у вас e готовий зібраний файл прошивки і ви не хочете використовувати arduino ide

### Всі _**налаштування зберігаються у внутрішній пам'яті**_
Відновлюються після перезавантаження та після перепрошивки мапи (якшо не вказувати примусове очищення) 

### Мапа інтегрується в сервіс _**home assistant**_ 
HA бачить мапу як окремий прилад розумного будинку і має можливість керувати мапою

### Мапа може бути обладнана _**сенсорною кнопкою**_ ttp223 (на платі jaam кнопка вже є)
Кнопка дозволяє перемикати всі наявні режими в мапі
 - саму мапу (тривога,погода, прапор, вимикання)
 - дисплей (вимикання, годинник, погода)


### Мапа підтримуе певний рівень кастомізацій:
 - загальна яскравість
 - яскравість, основана на часі (нічний режим з зниженою яскравістю)
 - можливість окремого світодіода для Кієва, або замість Київської області, або обидна одночасно (дана кастомізація потребує окремого світодіода в позиції 8 перед Киівською областю, загальна довжина стрічкі збільшиться с 25 до 26 світодіодів). Також є комбінований режим "Кіїв-Киівська область" для одного діода, який показує тривогу, якщо вона є в Києві або області 
 - можливість підсвічування нових тривог та відбоїв тривог певний час іншим кольором
 - можливість окремо і незалежно виставити яскравість різних зон тривог відносно одна одної
 - можливість окремо і незалежно виставити кольори різних зон тривог відносно одна одної
 - можливість окремо і незалежно виставити колір домашнього регіону

### Для плати jaam окремо є функціонал сервісних світодіодів на задній панелі:
 - наявність живлення
 - підключення до wifi
 - підключення до сервера даних
 - підключення до home assistant


[![CodeQL](https://github.com/v00g100skr/ukraine_alarm_map/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/v00g100skr/ukraine_alarm_map/actions/workflows/github-code-scanning/codeql)

[![GitHub version](https://img.shields.io/github/release/v00g100skr/ukraine_alarm_map.svg)](https://github.com/v00g100skr/ukraine_alarm_map/releases/latest)
[![GitHub commits](https://img.shields.io/github/commit-activity/t/v00g100skr/ukraine_alarm_map.svg)](https://github.com/v00g100skr/ukraine_alarm_map/commits/master)
[![GitHub issues](https://img.shields.io/github/issues/v00g100skr/ukraine_alarm_map.svg)](https://github.com/v00g100skr/ukraine_alarm_map/issues)


[![SWUbanner](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner2-direct.svg)](https://vshymanskyy.github.io/StandWithUkraine)




