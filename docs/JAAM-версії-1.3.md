Текстолітова плата у формі України

Фронтальна частина - 29 світлодіодів ws2812b (початок йде з Одеської області), поєднаних в одну лінію с трьома паралельними на 1му, 17му та 25му світлодіодах (Одеська,Київська та Крим + окремий діод на Київ) та дисплейний модуль SSD1036 з екраном 128 * 64

Конектор живлення і прошивки  - USB Type-C

Бутлоадер активовано

На задній частині розташований модуль керування ESP32, перемикач живлення, кнопка керування і інфрачервоний модуль-приймач (для майбутнього функціоналу)

В нижній частині плати є виводи пінів ESP32 - 6,7,8,9,10,23,32,33,34,rx,tx. Також виведено дві пари 3.3 і 5 вольт - це дозволяє вносити в контрукцію плати певні доробки і зовнішні сенсори і модулі 

Також на задній частині виведено 5 мікродіодів для індикації режимів роботи плати - наявність живлення, підклюючення wifi, підключення map-api, підключення home assistant + 1 для майбутнього функціоналу

Розміри - 17 на 25 см, плата має отвори для кріплення корпусу


<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-textolite.png" width="500"/>
<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-iso-textolite.png" width="500"/>
<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/back-textolite.png" width="500"/>

***

Варіанти корпусів - креслення є в цьому репозіторії

для pборки підходять гвинти m3-16 у витадку павного корпусу і m3-12 часткового

<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-base.png" width="500"/>
<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-iso-base.png" width="500"/>
<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-iso-mesh.png" width="500"/>
<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-without-3mm-mesh.png" width="500"/>

***

у випадку повного корпусу є можливість додати між шарами фронтальної сітки розсіювач світа з будь-якого матеріалу (я пробував офісний папір, фоамін, картон, повсть)

<img src="https://github.com/v00g100skr/ukraine_alarm_map/blob/master/img/front-full.png" width="500"/>