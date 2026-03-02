#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import requests
from typing import Tuple


def get_coordinates_from_nominatim(location_name, country="Ukraine"):
    """
    Отримання координат з OpenStreetMap Nominatim API з дотриманням політики використання

    Args:
        location_name (str): Назва населеного пункту
        country (str): Країна (за замовчуванням "Ukraine")

    Returns:
        tuple: (latitude, longitude) або None якщо не знайдено
    """
    max_retries = 3

    for attempt in range(max_retries):
        try:
            # URL для Nominatim API
            url = "https://nominatim.openstreetmap.org/search"

            # Параметри запиту з обмеженням по країні
            params = {
                "q": f"{location_name}, {country}",
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
                "countrycodes": "ua",  # Обмеження пошуку лише Україною
            }

            # Заголовки згідно з політикою Nominatim
            headers = {
                "User-Agent": "JAAM Fusion Location Mapper/1.0 (https://github.com/J-A-A-M/jaam_fusion; contact@jaam.dev)",
                "Accept-Language": "uk",  # Українська локаль
            }

            print(f"  🌍 Запитую координати через API для: {location_name} (спроба {attempt + 1}/{max_retries})")

            response = requests.get(url, params=params, headers=headers, timeout=10)

            # Обробка rate limiting (HTTP 429)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))  # За замовчуванням 60 сек
                print(f"  ⏳ Rate limit досягнуто. Очікую {retry_after} секунд...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                print(f"  ✅ Знайдено: {lat:.6f}, {lon:.6f}")
                return (lat, lon)
            else:
                print("  ❌ Не знайдено в API")
                return None

        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:  # Остання спроба
                print(f"  🔥 Помилка мережі для '{location_name}' після {max_retries} спроб: {e}")
                return None
            else:
                print(f"  ⚠️ Помилка мережі (спроба {attempt + 1}/{max_retries}): {e}")
                time.sleep(2**attempt)  # Exponential backoff
                continue
        except (KeyError, ValueError, TypeError) as e:
            print(f"  🔥 Помилка обробки даних для '{location_name}': {e}")
            return None

    # Якщо всі спроби вичерпано
    print(f"  ❌ Не вдалося отримати координати для '{location_name}' після {max_retries} спроб")
    return None


def get_coordinates(location_name: str) -> Tuple[float, float]:
    """
    Отримує координати для локації через API.

    Args:
        location_name: Назва локації

    Returns:
        (latitude, longitude)
    """
    # Спеціальний випадок для "Вся Україна"
    if location_name == "Вся Україна":
        print("  📍 Використовую центр України")
        return (49.0, 32.0)  # Центр України

    # Використовуємо API для отримання координат
    coords = get_coordinates_from_nominatim(location_name)
    if coords:
        return coords

    # Якщо API не спрацював, повертаємо координати центру України
    print(f"  ⚠️  Не вдалося знайти координати для '{location_name}', використовую центр України")
    return (49.0, 32.0)


def format_json_data(data: dict) -> str:
    """
    Форматує дані JSON з правильним вирівнюванням.

    Args:
        data: Словник з даними для форматування

    Returns:
        Відформатований JSON рядок
    """
    # Обробка порожніх даних
    if not data:
        return "{}"

    # Знаходимо максимальну довжину ключа для вирівнювання (SIM118: без .keys())
    max_key_length = max(len(key) for key in data)

    # Знаходимо максимальну довжину назви для вирівнювання
    max_name_length = max(len(value.get("name", "")) for value in data.values())

    # Формуємо вихідний рядок
    output_lines = ["{"]

    items = list(data.items())
    for i, (key, value) in enumerate(items):
        # Вирівнюємо ключ з екрануванням через json.dumps
        escaped_key = json.dumps(key, ensure_ascii=False)
        padded_key = escaped_key.ljust(max_key_length + 2)

        # Вирівнюємо назву з екрануванням через json.dumps
        name = value.get("name", "")
        escaped_name = json.dumps(name, ensure_ascii=False)
        padded_name = escaped_name.ljust(max_name_length + 2)

        # Форматуємо числові значення з вирівнюванням
        region_id = str(value.get("regionId", 0)).rjust(4)
        legacy_id = str(value.get("legacyId", 0)).rjust(2)
        state_id = str(value.get("stateId", 0)).rjust(4)

        # Додаємо кому після кожного елемента, крім останнього
        comma = "," if i < len(items) - 1 else ""

        # Формуємо location частину якщо є
        if "location" in value:
            location = value["location"]
            lat = location.get("lat", 0)
            lon = location.get("lon", 0)
            # Форматуємо координати з вирівнюванням
            lat_str = f"{lat:>12}"
            lon_str = f"{lon:>12}"
            location_str = f', "location": {{"lat": {lat_str}, "lon": {lon_str}}}'
        else:
            location_str = ""

        # Додаємо рядок для цього елемента з вирівнюванням
        line = f'  {padded_key} : {{ "name": {padded_name}, "regionId": {region_id}, "legacyId": {legacy_id}, "stateId": {state_id}{location_str} }}{comma}'
        output_lines.append(line)

    output_lines.append("}")

    return "\n".join(output_lines)


def add_coordinates_to_json(input_file: str, output_file: str):
    """
    Додає географічні координати до кожного запису у JSON файлі.

    Args:
        input_file: Шлях до вхідного JSON файлу
        output_file: Шлях до вихідного JSON файлу
    """
    print(f"Читаю файл: {input_file}")

    # Обробка помилок читання файлу
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Помилка: Файл '{input_file}' не знайдено!")
        print("   Перевірте шлях до файлу та спробуйте ще раз.")
        return
    except PermissionError:
        print(f"❌ Помилка: Немає прав для читання файлу '{input_file}'!")
        print("   Перевірте права доступу до файлу.")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Помилка: Невірний формат JSON у файлі '{input_file}'!")
        print(f"   Деталі: {e}")
        print("   Перевірте синтаксис JSON файлу.")
        return
    except UnicodeDecodeError as e:
        print(f"❌ Помилка: Проблема з кодуванням файлу '{input_file}'!")
        print(f"   Деталі: {e}")
        print("   Файл повинен бути у форматі UTF-8.")
        return
    except Exception as e:
        print(f"❌ Непередбачена помилка при читанні файлу '{input_file}': {e}")
        return

    if not isinstance(data, dict):
        print(f"❌ Помилка: Файл '{input_file}' повинен містити JSON об'єкт (словник)!")
        print(f"   Поточний тип даних: {type(data).__name__}")
        return

    total_locations = len(data)
    if total_locations == 0:
        print(f"⚠️  Попередження: Файл '{input_file}' містить порожній JSON об'єкт!")
        print("   Немає даних для обробки.")
        return

    processed = 0

    print(f"Обробляю {total_locations} локацій...")

    for key, location_data in data.items():
        try:
            # Перевіряємо структуру даних
            if not isinstance(location_data, dict):
                print(f"⚠️  Пропускаю '{key}': невірний формат даних (очікується словник)")
                continue

            location_name = location_data.get("name", "")
            if not location_name:
                print(f"⚠️  Пропускаю '{key}': відсутня назва локації")
                continue

            print(f"[{processed + 1}/{total_locations}] Обробляю: {location_name}")

            # Отримуємо координати з обробкою помилок
            try:
                lat, lon = get_coordinates(location_name)

                # Перевіряємо валідність координат
                if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                    print(f"⚠️  Отримано невірні координати для '{location_name}': lat={lat}, lon={lon}")
                    lat, lon = 49.0, 32.0  # Використовуємо центр України як fallback

            except Exception as e:
                print(f"❌ Помилка при отриманні координат для '{location_name}': {e}")
                lat, lon = 49.0, 32.0  # Використовуємо центр України як fallback
                print(f"   Використовую координати центру України: {lat}, {lon}")

            # Додаємо координати до даних (використовуємо lat/lon замість latitude/longitude)
            location_data["location"] = {"lat": lat, "lon": lon}

        except Exception as e:
            print(f"❌ Помилка при обробці запису '{key}': {e}")
            print("   Пропускаю цей запис та продовжую...")
            continue

        processed += 1

        # Затримка між запитами до API для ввічливого використання (крім "Вся Україна")
        if location_name != "Вся Україна":
            print("  ⏳ Чекаю 1 секунду перед наступним запитом...")
            time.sleep(1.0)  # 1 секунда - рекомендована затримка для Nominatim API

    print(f"Зберігаю результат у файл: {output_file}")
    print("Форматую JSON з правильним вирівнюванням...")

    # Використовуємо нашу функцію форматування замість стандартного json.dump
    try:
        formatted_json = format_json_data(data)
    except Exception as e:
        print(f"❌ Помилка при форматуванні даних: {e}")
        print("   Спробую зберегти без форматування...")
        try:
            formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e2:
            print(f"❌ Критична помилка при серіалізації даних: {e2}")
            return

    # Обробка помилок запису файлу
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(formatted_json)
    except PermissionError:
        print(f"❌ Помилка: Немає прав для запису у файл '{output_file}'!")
        print("   Перевірте права доступу до папки або виберіть інший шлях.")
        return
    except OSError as e:
        print(f"❌ Помилка файлової системи при записі '{output_file}': {e}")
        print("   Можливо, недостатньо місця на диску або невірний шлях.")
        return
    except UnicodeEncodeError as e:
        print(f"❌ Помилка кодування при записі файлу '{output_file}': {e}")
        print("   Деякі символи не можна закодувати у UTF-8.")
        return
    except Exception as e:
        print(f"❌ Непередбачена помилка при записі файлу '{output_file}': {e}")
        return

    print("✅ Готово! Файл успішно збережено.")


if __name__ == "__main__":
    input_file = "gen_data.json"
    output_file = "gen_data_with_locations.json"

    print("🚀 Запуск скрипту додавання координат...")
    print(f"📁 Вхідний файл: {input_file}")
    print(f"📁 Вихідний файл: {output_file}")
    print("-" * 50)

    try:
        add_coordinates_to_json(input_file, output_file)
    except KeyboardInterrupt:
        print("\n\n⚠️  Операцію перервано користувачем (Ctrl+C)")
        print("   Частково оброблені дані можуть бути втрачені.")
    except Exception as e:
        print(f"\n❌ Критична помилка у скрипті: {e}")
        print(f"   Тип помилки: {type(e).__name__}")
        import traceback

        print("   Детальна інформація:")
        traceback.print_exc()
