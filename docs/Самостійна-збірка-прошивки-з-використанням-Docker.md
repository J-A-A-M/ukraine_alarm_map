### Загальна інформація та підготовка

Самостійно зібрати прошивку для мапи тривог можна за допомогою [PlatformIO](https://platformio.org/), який є частиною Visual Studio Code. Для цього необхідно встановити розширення PlatformIO IDE, або ж скористатись [PlatformIO Core](https://docs.platformio.org/en/latest/core.html) з командного рядка. Це може бути корисно, якщо ви хочете внести зміни в код мапи, протестувати свої зміни перед створенням PR-у, або ж просто зібрати прошивку для себе.

Використання Docker для збірки прошивки не є обовʼязковим, але може бути корисним, якщо ви хочете уникнути проблем з залежностями та налаштуванням середовища. Якщо ви не знайомі з Docker, рекомендуємо спочатку ознайомитись з його основами.

### Підготовка середовища

Запустіть докер-контейнер з Python (рекомендую версію 3.12, оскільки вона використовується у CI цього проекту) знаходячись у директорії з проектом:
```bash
docker run -it --rm -v "$PWD":/workspace -w /workspace python:3.12-slim bash
```

Встановіть Git, PlatformIO CLI та інші необхідні інструменти:
```bash
apt-get update && apt-get install -y git curl
rm -rf /var/lib/apt/lists/*
pip install --no-cache-dir platformio
pio pkg install -d firmware
```

В результаті ви отримаєте робоче середовище для збірки прошивки мапи тривог. Тепер ви можете перейти до збірки прошивки.

### Збірка прошивки

Для збірки прошивки використовуйте команду PlatformIO:
```bash
pio run -d firmware
```
Ця команда збере прошивку для середовища, яке зазначене як `default_envs` у файлі [platformio.ini](https://github.com/J-A-A-M/ukraine_alarm_map/blob/develop/firmware/platformio.ini). Ви можете вказати конкретне середовище для збірки, наприклад:

```bash
pio run -d firmware -e firmware_esp32c3
```
або

```bash
pio run -d firmware -e firmware_lite
```

В результаті збірки ви отримаєте файл прошивки у директорії `firmware/.pio/build/{назва середовища}/`