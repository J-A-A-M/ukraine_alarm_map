import json
from pathlib import Path
import hashlib

# Примітивний мапінг латиниці в кирилицю для назв (можна розширити)
TRANSLIT_MAP = {
    "A": "А",
    "B": "Б",
    "V": "В",
    "H": "Г",
    "G": "Ґ",
    "D": "Д",
    "E": "Е",
    "Ye": "Є",
    "Zh": "Ж",
    "Z": "З",
    "Y": "И",
    "I": "І",
    "Yi": "Ї",
    "J": "Й",
    "K": "К",
    "L": "Л",
    "M": "М",
    "N": "Н",
    "O": "О",
    "P": "П",
    "R": "Р",
    "S": "С",
    "T": "Т",
    "U": "У",
    "F": "Ф",
    "Kh": "Х",
    "Ts": "Ц",
    "Ch": "Ч",
    "Sh": "Ш",
    "Shch": "Щ",
    "Yu": "Ю",
    "Ya": "Я",
    "a": "а",
    "b": "б",
    "v": "в",
    "h": "г",
    "g": "ґ",
    "d": "д",
    "e": "е",
    "ye": "є",
    "zh": "ж",
    "z": "з",
    "y": "и",
    "i": "і",
    "yi": "ї",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "f": "ф",
    "kh": "х",
    "ts": "ц",
    "ch": "ч",
    "sh": "ш",
    "shch": "щ",
    "yu": "ю",
    "ya": "я",
    "'": "'",
    "’": "’",
    "-": "-",
    " ": " ",
}

# Найпростіший варіант: заміна відомих латинських назв на кирилицю (можна розширити)
SPECIAL_MAP = {}

# Додаткові мапінги для районів з помилками у джерелі
district_name_map = {
    "Берестинський район": "Красноградський район",
    "Володимирський район": "Володимир-Волинський район",
    "Самарівський район": "Новомосковський район",
    "Шептицький район": "Червоноградський район",
    "Крим": "Автономна Республіка Крим",
}

# Кастомні regionId
custom_region_ids = {
    "Київ": 31,
    "Харків": 1293,
    "Запоріжжя": 564,
    "Херсон": 1370,
    "Суми": 1187,
    "Чернігів": 1591,
    "Полтава": 1060,
    "Житомир": 442,
    "Дніпро": 332,
    "Миколаїв": 926,
    "Кропивницький": 761,
    "Черкаси": 1473,
    "Вінниця": 155,
    "Одеса": 964,
    "Рівне": 1133,
    "Хмельницький": 1400,
    "Чернівці": 1542,
    "Луцьк": 225,
    "Львів": 845,
    "Тернопіль": 1241,
    "Івано-Франківськ": 632,
    "Ужгород": 500,
}

custom_state_ids = {
    "Київ": 31,
}


# Масив виключень для slug, які треба перемапити на особливі ключі
slug_exceptions = {
    "ZOLOCHIV-LV-CITY": "Золочів (Львівська)",
    "TROSTIANETS-CITY": "Тростянець (Вінницька)",
    "YAMPIL-CITY": "Ямпіль (Вінницька)",
    "KALYNIVKA-CITY": "Калинівка (Вінницька)",
    "MYKOLAIVKA-CITY": "Миколаївка (Дніпропетровська)",
    "CHERNIVTSI-VIN-CITY": "Чернівці (Вінницька)",
    "OLEKSANDRIVKA-K-CITY": "Олександрівка (Кіровоградська)",
    "OLEKSANDRIVKA-OD-CITY": "Олександрівка (Одеська)",
}

legacy_map = {
    "Закарпатська область": 1,
    "Івано-Франківська область": 2,
    "Тернопільська область": 3,
    "Львівська область": 4,
    "Волинська область": 5,
    "Рівненська область": 6,
    "Житомирська область": 7,
    "Київська область": 8,
    "Чернігівська область": 9,
    "Сумська область": 10,
    "Харківська область": 11,
    "Луганська область": 12,
    "Донецька область": 13,
    "Запорізька область": 14,
    "Херсонська область": 15,
    "Автономна Республіка Крим": 16,
    "Одеська область": 17,
    "Миколаївська область": 18,
    "Дніпропетровська область": 19,
    "Полтавська область": 20,
    "Черкаська область": 21,
    "Кіровоградська область": 22,
    "Вінницька область": 23,
    "Хмельницька область": 24,
    "Чернівецька область": 25,
    "м. Київ": 26,
    "Київ": 26,
}


def get_deterministic_missing_id(slug):
    """
    Генерує детермінований ID для регіону з діапазону 7000-7999 на основі slug.
    Забезпечує стабільність ID при змінах порядку або додаванні нових записів.
    """
    # Використовуємо SHA256 для хеша slug
    hash_obj = hashlib.sha256(slug.encode("utf-8"))
    hash_int = int(hash_obj.hexdigest(), 16)
    # Обмежуємо діапазон 7000-7999
    region_id = 7000 + (hash_int % 1000)
    return region_id


def normalize_apostrophe(s):
    # Замінюємо всі типи апострофів на стандартний '
    return s.replace("’", "'").replace("`", "'").replace("ʼ", "'")


def translit_to_cyrillic(name):
    name = normalize_apostrophe(name)

    # Спробуємо просту заміну (тільки для латиниці)
    res = ""
    i = 0
    while i < len(name):
        # Пробуємо знайти довгі комбінації
        for chunk_len in [4, 3, 2, 1]:
            if i + chunk_len <= len(name) and name[i : i + chunk_len] in TRANSLIT_MAP:
                res += TRANSLIT_MAP[name[i : i + chunk_len]]
                i += chunk_len
                break
        else:
            res += name[i]
            i += 1
    return res


def find_slug_in_uaapi(name, uaapi, level):
    # name — вже транслітерована і нормалізована назва
    if level == "state":
        for state in uaapi["states"]:
            if translit_to_cyrillic(state["regionName"]) == name:
                return state.get("slug")
    elif level == "district":
        for state in uaapi["states"]:
            for district in state.get("regionChildIds", []):
                if translit_to_cyrillic(district["regionName"]) == name:
                    return district.get("slug")
    elif level == "city":
        for state in uaapi["states"]:
            for district in state.get("regionChildIds", []):
                for city in district.get("regionChildIds", []):
                    if city["regionName"].startswith("м. "):
                        city_name = city["regionName"].split(" та ")[0].replace("м. ", "").strip()
                        if translit_to_cyrillic(city_name) == name:
                            return city.get("slug")
    return None


def build_name_to_id_map(uaapi):
    name_to_id = {}
    district_to_state = {}
    city_to_district = {}
    city_to_state = {}
    for state in uaapi["states"]:
        state_cyr = translit_to_cyrillic(state["regionName"])
        name_to_id[state_cyr] = state["regionId"]
        for district in state.get("regionChildIds", []):
            district_cyr = translit_to_cyrillic(district["regionName"])
            name_to_id[district_cyr] = district["regionId"]
            district_to_state[district_cyr] = state_cyr
            for community in district.get("regionChildIds", []):
                if community["regionName"].startswith("м. "):
                    city_name = community["regionName"].split(" та ")[0].replace("м. ", "").strip()
                    city_cyr = translit_to_cyrillic(city_name)
                    name_to_id[city_cyr] = district["regionId"]
                    city_to_district[city_cyr] = district_cyr
                    city_to_state[city_cyr] = state_cyr
    return name_to_id, district_to_state, city_to_district, city_to_state


base = Path(__file__).parent
etryvoga_path = base / "etryvoga.json"
uaapi_path = base / "uaapi.json"

with open(etryvoga_path, encoding="utf-8") as f:
    etryvoga = json.load(f)
with open(uaapi_path, encoding="utf-8") as f:
    uaapi = json.load(f)

name_to_id, district_to_state, city_to_district, city_to_state = build_name_to_id_map(uaapi)

result = {}
not_found_districts = {}
not_found_cities = {}
slug_map = {}

for region in etryvoga:
    print("\n" + "-" * 60)
    region_name = region["name"]
    region_source_name = region["name"]  # Зберігаємо оригінальне ім'я з etryvoga.json
    # Застосовую мапінг для областей
    mapped_region_name = district_name_map.get(region_name, region_name)
    region_cyr = translit_to_cyrillic(mapped_region_name)
    region_id = name_to_id.get(region_cyr)
    legacy_id = None
    # Якщо не знайдено region_id, пробую з "область" замість "обл."
    if region_id is None and mapped_region_name.endswith(" обл."):
        alt_name = mapped_region_name.replace(" обл.", " область")
        alt_cyr = translit_to_cyrillic(alt_name)
        region_id = name_to_id.get(alt_cyr)
        # legacy_id теж шукаємо по alt_cyr
        for state in uaapi["states"]:
            if translit_to_cyrillic(state["regionName"]) == alt_cyr:
                legacy_id = legacy_map.get(translit_to_cyrillic(state["regionName"]))
                break
    else:
        for state in uaapi["states"]:
            if translit_to_cyrillic(state["regionName"]) == region_cyr:
                legacy_id = legacy_map.get(translit_to_cyrillic(state["regionName"]))
                break
    # Якщо slug у виключеннях — використовуємо особливий ключ для області
    if region.get("slug") in slug_exceptions:
        result_key = slug_exceptions[region["slug"]]
    elif mapped_region_name.endswith(" обл."):
        result_key = mapped_region_name.replace(" обл.", " область")
    else:
        result_key = mapped_region_name
    # Перевіряю кастомний regionId для областей
    if region_id is not None:
        region_id_final = custom_region_ids.get(result_key, int(region_id))
    else:
        # Якщо region_id не знайдено, генеруємо детермінований ID на основі slug
        region_id_final = custom_region_ids.get(
            result_key, get_deterministic_missing_id(region.get("slug", result_key))
        )
    state_id_final = custom_state_ids.get(result_key, int(region_id) if region_id is not None else -1)
    # Якщо legacy_id не знайдено — пробую взяти по result_key
    if legacy_id is None:
        legacy_id = legacy_map.get(result_key)
    result[result_key] = {
        "regionId": region_id_final,
        "legacyId": int(legacy_id) if legacy_id is not None else -1,
        "stateId": state_id_final,
    }
    slug_map[region["slug"]] = {
        "name": result_key,
        "regionId": result[result_key]["regionId"],
        "source_name": region_source_name,
    }

    total_districts = len(region.get("districts", []))
    found_districts = 0
    not_found_districts[region_name] = []
    for district in region.get("districts", []):
        district_name = district["name"]
        # Додаємо назву області в дужках до назви району
        district_source_name = f"{district['name']} ({region_source_name})"
        mapped_district_name = district_name_map.get(district_name, district_name)
        district_cyr = translit_to_cyrillic(mapped_district_name)
        district_id = name_to_id.get(district_cyr)
        state_cyr = district_to_state.get(district_cyr)
        legacy_id = legacy_map.get(state_cyr)
        state_id = name_to_id.get(state_cyr)
        # Якщо slug у виключеннях — використовуємо особливий ключ для району
        if district.get("slug") in slug_exceptions:
            district_key = slug_exceptions[district["slug"]]
        else:
            district_key = mapped_district_name
        # Для районів — аналогічно
        if district_id is not None:
            district_id_final = custom_region_ids.get(district_key, int(district_id))
        else:
            district_id_final = custom_region_ids.get(
                district_key, get_deterministic_missing_id(district.get("slug", district_key))
            )
        state_id_final = custom_state_ids.get(district_key, int(state_id) if state_id is not None else -1)
        # Якщо legacy_id не знайдено — пробую взяти по district_key
        if legacy_id is None:
            legacy_id = legacy_map.get(district_key)
        result[district_key] = {
            "regionId": district_id_final,
            "legacyId": int(legacy_id) if legacy_id is not None else -1,
            "stateId": state_id_final,
        }
        slug_map[district["slug"]] = {
            "name": district_key,
            "regionId": result[district_key]["regionId"],
            "source_name": district_source_name,
        }
        if district_id:
            found_districts += 1
        else:
            not_found_districts[region_name].append(district_name)
        total_cities = len(district.get("cities", []))
        found_cities = 0
        not_found_cities[district_name] = []
        city_names = [city["name"] for city in district.get("cities", [])]
        if mapped_district_name != district_name:
            log_district = f"{mapped_district_name} ({district_name})"
        else:
            log_district = mapped_district_name
        print(f"  Район: {log_district} — міста: {', '.join(city_names)}")
        for city in district.get("cities", []):
            city_name = city["name"]
            # Додаємо назву області в дужках до назви міста
            city_source_name = f"{city['name']} ({region_source_name})"
            # Для міст — застосовую мапінг
            mapped_city_name = district_name_map.get(city_name, city_name)
            city_cyr = translit_to_cyrillic(mapped_city_name)
            city_id = name_to_id.get(city_cyr)
            # Якщо slug у виключеннях — використовуємо особливий ключ для міста
            if city.get("slug") in slug_exceptions:
                city_key = slug_exceptions[city["slug"]]
                # Для виключень назва міста може бути неоднозначною (є в кількох областях),
                # тому ігноруємо city_to_state і покладаємось на контекст району
                city_id = None
                state_cyr = district_to_state.get(district_cyr)
            else:
                city_key = (
                    mapped_city_name.replace("м. ", "", 1) if mapped_city_name.startswith("м. ") else mapped_city_name
                )
                state_cyr = city_to_state.get(city_cyr) or district_to_state.get(district_cyr)
            legacy_id = legacy_map.get(state_cyr)
            state_id = name_to_id.get(state_cyr)
            # Для міст — якщо немає city_id, генеруємо на основі slug
            if city_id is not None:
                region_id_final = custom_region_ids.get(city_key, int(city_id))
            elif district_id is not None:
                region_id_final = custom_region_ids.get(city_key, int(district_id))
            else:
                region_id_final = custom_region_ids.get(
                    city_key, get_deterministic_missing_id(city.get("slug", city_key))
                )
            state_id_final = custom_state_ids.get(city_key, state_id if state_id is not None else -1)
            # Якщо legacy_id не знайдено — пробую взяти по city_key
            if legacy_id is None:
                legacy_id = legacy_map.get(city_key)
            result[city_key] = {
                "regionId": int(region_id_final),
                "legacyId": int(legacy_id) if legacy_id is not None else -1,
                "stateId": int(state_id_final),
            }
            slug_map[city["slug"]] = {
                "name": city_key,
                "regionId": result[city_key]["regionId"],
                "source_name": city_source_name,
            }
            if city_id or district_id:
                found_cities += 1
            else:
                not_found_cities[district_name].append(city_name)
        print(f"    міста знайдено: {found_cities}/{total_cities}")
        if not_found_cities[district_name]:
            print(f"    Не знайдено міст: {not_found_cities[district_name]}")
    print(f"Область: {region_name} — райони знайдено: {found_districts}/{total_districts}")
    if not_found_districts[region_name]:
        print(f"  Не знайдено районів: {not_found_districts[region_name]}")

# with open(base / "gen_updater.json", "w", encoding="utf-8") as f:
#     # Визначаємо максимальну довжину ключа (назви)
#     max_key_len = max(len(str(k)) for k in result.keys())
#     # Визначаємо максимальну довжину чисел для кожного id
#     max_regionid_len = max(len(str(v["regionId"])) for v in result.values() if v)
#     max_legacyid_len = max(len(str(v["legacyId"])) for v in result.values() if v)
#     max_stateid_len = max(len(str(v["stateId"])) for v in result.values() if v)
#     # Формуємо шаблон для вирівнювання
#     id_block = (
#         f'{{{{ "regionId": {{regionid:>{max_regionid_len}}}, '
#         f'"legacyId": {{legacyid:>{max_legacyid_len}}}, '
#         f'"stateId": {{stateid:>{max_stateid_len}}} }}}}'
#     )
#     f.write('{\n')
#     items = list(result.items())
#     for i, (k, v) in enumerate(items):
#         if v is None:
#             continue
#         key_pad = ' ' * (max_key_len - len(str(k)))
#         line = (
#             f'  "{k}"{key_pad}: '
#             + id_block.format(
#                 regionid=v["regionId"],
#                 legacyid=v["legacyId"],
#                 stateid=v["stateId"]
#             )
#         )
#         if i < len(items) - 1:
#             line += ','
#         f.write(line + '\n')
#     f.write('}\n')

# Додаю збереження slug_map
with open(base / "../regions.json", "w", encoding="utf-8") as f:
    # Визначаємо максимальну довжину slug і назви
    max_slug_len = max(len(str(k)) for k in slug_map.keys()) if slug_map else 0
    max_name_len = max(len(str(v["name"])) for v in slug_map.values()) if slug_map else 0
    max_source_name_len = max(len(str(v.get("source_name", ""))) for v in slug_map.values()) if slug_map else 0
    max_regionid_len = (
        max(len(str(result[v["name"]]["regionId"])) for v in slug_map.values() if v["name"] in result)
        if slug_map
        else 0
    )
    max_legacyid_len = (
        max(len(str(result[v["name"]]["legacyId"])) for v in slug_map.values() if v["name"] in result)
        if slug_map
        else 0
    )
    max_stateid_len = (
        max(len(str(result[v["name"]]["stateId"])) for v in slug_map.values() if v["name"] in result) if slug_map else 0
    )
    f.write("{\n")
    items = list(slug_map.items())
    for i, (slug, v) in enumerate(items):
        slug_pad = " " * (max_slug_len - len(str(slug)))
        name_pad = " " * (max_name_len - len(str(v["name"])))
        source_name = v.get("source_name", "")
        source_name_pad = " " * (max_source_name_len - len(str(source_name)))
        # Додаю legacyId та stateId з result
        regionId = result[v["name"]]["regionId"] if v["name"] in result else -1
        legacyId = result[v["name"]]["legacyId"] if v["name"] in result else -1
        stateId = result[v["name"]]["stateId"] if v["name"] in result else -1
        regionid_pad = str(regionId).rjust(max_regionid_len)
        legacyid_pad = str(legacyId).rjust(max_legacyid_len)
        stateid_pad = str(stateId).rjust(max_stateid_len)
        line = f'  "{slug}"{slug_pad}: {{ "name": "{v["name"]}"{name_pad}, "source_name": "{source_name}"{source_name_pad}, "regionId": {regionid_pad}, "legacyId": {legacyid_pad}, "stateId": {stateid_pad} }}'
        if i < len(items) - 1:
            line += ","
        f.write(line + "\n")
    f.write("}\n")
