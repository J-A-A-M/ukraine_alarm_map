import json
import os
import asyncio
import aiohttp
import logging
import hashlib
import datetime
import contextlib
from aiomcache import Client
from functools import partial


version = 2

debug_level = os.environ.get("LOGGING") or "INFO"
etryvoga_url = os.environ.get("ETRYVOGA_HOST")
etryvoga_districts_url = os.environ.get("ETRYVOGA_DISTRICTS_HOST")
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
etryvoga_loop_time = int(os.environ.get("ETRYVOGA_PERIOD", 30))
etryvoga_districts_loop_time = int(os.environ.get("ETRYVOGA_DISTRICTS_PERIOD", 600))

if not etryvoga_url:
    raise ValueError("ETRYVOGA_HOST environment variable is required")
if not etryvoga_districts_url:
    raise ValueError("ETRYVOGA_DISTRICTS_HOST environment variable is required")
if etryvoga_loop_time < 10:
    raise ValueError("ETRYVOGA_PERIOD must be >= 10")
if etryvoga_districts_loop_time < 600:
    raise ValueError("ETRYVOGA_PERIOD must be >= 600")

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


regions = {
  "Вся Україна"                      : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Івано-Франківська область"        : { "regionId":   13, "legacyId":  2, "stateId":   13 },
  "Івано-Франківський район"         : { "regionId":   68, "legacyId":  2, "stateId":   13 },
  "Івано-Франківськ"                 : { "regionId":   68, "legacyId":  2, "stateId":   13 },
  "Верховинський район"              : { "regionId":   67, "legacyId":  2, "stateId":   13 },
  "Верховина"                        : { "regionId":   67, "legacyId":  2, "stateId":   13 },
  "Калуський район"                  : { "regionId":   71, "legacyId":  2, "stateId":   13 },
  "Калуш"                            : { "regionId":   71, "legacyId":  2, "stateId":   13 },
  "Коломийський район"               : { "regionId":   70, "legacyId":  2, "stateId":   13 },
  "Коломия"                          : { "regionId":   70, "legacyId":  2, "stateId":   13 },
  "Косівський район"                 : { "regionId":   69, "legacyId":  2, "stateId":   13 },
  "Косів"                            : { "regionId":   69, "legacyId":  2, "stateId":   13 },
  "Надвірнянський район"             : { "regionId":   72, "legacyId":  2, "stateId":   13 },
  "Надвірна"                         : { "regionId":   72, "legacyId":  2, "stateId":   13 },
  "Волинська область"                : { "regionId":    8, "legacyId":  5, "stateId":    8 },
  "Володимир-Волинський район"       : { "regionId":   38, "legacyId":  5, "stateId":    8 },
  "Нововолинськ"                     : { "regionId":   38, "legacyId":  5, "stateId":    8 },
  "Камінь-Каширський район"          : { "regionId":   41, "legacyId":  5, "stateId":    8 },
  "Камінь-Каширський"                : { "regionId":   41, "legacyId":  5, "stateId":    8 },
  "Ковельський район"                : { "regionId":   40, "legacyId":  5, "stateId":    8 },
  "Ковель"                           : { "regionId":   40, "legacyId":  5, "stateId":    8 },
  "Луцький район"                    : { "regionId":   39, "legacyId":  5, "stateId":    8 },
  "Луцьк"                            : { "regionId":   39, "legacyId":  5, "stateId":    8 },
  "Вінницька область"                : { "regionId":    4, "legacyId": 23, "stateId":    4 },
  "Вінницький район"                 : { "regionId":   36, "legacyId": 23, "stateId":    4 },
  "Вінниця"                          : { "regionId":   36, "legacyId": 23, "stateId":    4 },
  "Гайсинський район"                : { "regionId":   37, "legacyId": 23, "stateId":    4 },
  "Гайсин"                           : { "regionId":   37, "legacyId": 23, "stateId":    4 },
  "Жмеринський район"                : { "regionId":   35, "legacyId": 23, "stateId":    4 },
  "Жмеринка"                         : { "regionId":   35, "legacyId": 23, "stateId":    4 },
  "Могилів-Подільський район"        : { "regionId":   33, "legacyId": 23, "stateId":    4 },
  "Могилів-Подільський"              : { "regionId":   33, "legacyId": 23, "stateId":    4 },
  "Тульчинський район"               : { "regionId":   32, "legacyId": 23, "stateId":    4 },
  "Тульчин"                          : { "regionId":   32, "legacyId": 23, "stateId":    4 },
  "Хмільницький район"               : { "regionId":   34, "legacyId": 23, "stateId":    4 },
  "Хмільник"                         : { "regionId":   34, "legacyId": 23, "stateId":    4 },
  "Дніпропетровська область"         : { "regionId":    9, "legacyId": 19, "stateId":    9 },
  "Дніпровський район"               : { "regionId":   44, "legacyId": 19, "stateId":    9 },
  "Дніпро"                           : { "regionId":   44, "legacyId": 19, "stateId":    9 },
  "Кам'янський район"                : { "regionId":   42, "legacyId": 19, "stateId":    9 },
  "Верхівцеве"                       : { "regionId":   42, "legacyId": 19, "stateId":    9 },
  "Вільногірськ"                     : { "regionId":   42, "legacyId": 19, "stateId":    9 },
  "Кам'янське"                       : { "regionId":   42, "legacyId": 19, "stateId":    9 },
  "Криворізький район"               : { "regionId":   46, "legacyId": 19, "stateId":    9 },
  "Апостолове"                       : { "regionId":   46, "legacyId": 19, "stateId":    9 },
  "Велика Долина"                    : { "regionId":   46, "legacyId": 19, "stateId":    9 },
  "Зеленодольськ"                    : { "regionId":   46, "legacyId": 19, "stateId":    9 },
  "Кривий Ріг"                       : { "regionId":   46, "legacyId": 19, "stateId":    9 },
  "Мар'янське"                       : { "regionId":   46, "legacyId": 19, "stateId":    9 },
  "Нікопольський район"              : { "regionId":   47, "legacyId": 19, "stateId":    9 },
  "Марганець"                        : { "regionId":   47, "legacyId": 19, "stateId":    9 },
  "Нікополь"                         : { "regionId":   47, "legacyId": 19, "stateId":    9 },
  "Покров"                           : { "regionId":   47, "legacyId": 19, "stateId":    9 },
  "Павлоградський район"             : { "regionId":   45, "legacyId": 19, "stateId":    9 },
  "Павлоград"                        : { "regionId":   45, "legacyId": 19, "stateId":    9 },
  "Новомосковський район"            : { "regionId":   43, "legacyId": 19, "stateId":    9 },
  "Самар"                            : { "regionId":   43, "legacyId": 19, "stateId":    9 },
  "Синельниківський район"           : { "regionId":   48, "legacyId": 19, "stateId":    9 },
  "Межова"                           : { "regionId":   48, "legacyId": 19, "stateId":    9 },
  "Новопавлівка"                     : { "regionId":   48, "legacyId": 19, "stateId":    9 },
  "Покровське"                       : { "regionId":   48, "legacyId": 19, "stateId":    9 },
  "Синельникове"                     : { "regionId":   48, "legacyId": 19, "stateId":    9 },
  "Шахтарське"                       : { "regionId":   48, "legacyId": 19, "stateId":    9 },
  "Донецька область"                 : { "regionId":   28, "legacyId": 13, "stateId":   28 },
  "Бахмутський район"                : { "regionId":   54, "legacyId": 13, "stateId":   28 },
  "Бахмут"                           : { "regionId":   54, "legacyId": 13, "stateId":   28 },
  "Світлодарськ"                     : { "regionId":   54, "legacyId": 13, "stateId":   28 },
  "Соледар"                          : { "regionId":   54, "legacyId": 13, "stateId":   28 },
  "Торецьк"                          : { "regionId":   54, "legacyId": 13, "stateId":   28 },
  "Часів Яр"                         : { "regionId":   54, "legacyId": 13, "stateId":   28 },
  "Волноваський район"               : { "regionId":   55, "legacyId": 13, "stateId":   28 },
  "Велика Новосілка"                 : { "regionId":   55, "legacyId": 13, "stateId":   28 },
  "Вугледар"                         : { "regionId":   55, "legacyId": 13, "stateId":   28 },
  "Горлівський район"                : { "regionId":   51, "legacyId": 13, "stateId":   28 },
  "Єнакієве"                         : { "regionId":   51, "legacyId": 13, "stateId":   28 },
  "Горлівка"                         : { "regionId":   51, "legacyId": 13, "stateId":   28 },
  "Сніжне"                           : { "regionId":   51, "legacyId": 13, "stateId":   28 },
  "Чистякове"                        : { "regionId":   51, "legacyId": 13, "stateId":   28 },
  "Шахтарськ"                        : { "regionId":   51, "legacyId": 13, "stateId":   28 },
  "Донецький район"                  : { "regionId":   53, "legacyId": 13, "stateId":   28 },
  "Донецьк"                          : { "regionId":   53, "legacyId": 13, "stateId":   28 },
  "Макіївка"                         : { "regionId":   53, "legacyId": 13, "stateId":   28 },
  "Харцизьк"                         : { "regionId":   53, "legacyId": 13, "stateId":   28 },
  "Кальміуський район"               : { "regionId":   49, "legacyId": 13, "stateId":   28 },
  "Кальміуське"                      : { "regionId":   49, "legacyId": 13, "stateId":   28 },
  "Краматорський район"              : { "regionId":   50, "legacyId": 13, "stateId":   28 },
  "Дружківка"                        : { "regionId":   50, "legacyId": 13, "stateId":   28 },
  "Костянтинівка"                    : { "regionId":   50, "legacyId": 13, "stateId":   28 },
  "Краматорськ"                      : { "regionId":   50, "legacyId": 13, "stateId":   28 },
  "Лиман"                            : { "regionId":   50, "legacyId": 13, "stateId":   28 },
  "Святогірськ"                      : { "regionId":   50, "legacyId": 13, "stateId":   28 },
  "Слов'янськ"                       : { "regionId":   50, "legacyId": 13, "stateId":   28 },
  "Маріупольський район"             : { "regionId":   52, "legacyId": 13, "stateId":   28 },
  "Маріуполь"                        : { "regionId":   52, "legacyId": 13, "stateId":   28 },
  "Покровський район"                : { "regionId":   56, "legacyId": 13, "stateId":   28 },
  "Авдіївка"                         : { "regionId":   56, "legacyId": 13, "stateId":   28 },
  "Добропілля"                       : { "regionId":   56, "legacyId": 13, "stateId":   28 },
  "Курахове"                         : { "regionId":   56, "legacyId": 13, "stateId":   28 },
  "Мар'їнка"                         : { "regionId":   56, "legacyId": 13, "stateId":   28 },
  "Мирноград"                        : { "regionId":   56, "legacyId": 13, "stateId":   28 },
  "Покровськ"                        : { "regionId":   56, "legacyId": 13, "stateId":   28 },
  "Житомирська область"              : { "regionId":   10, "legacyId":  7, "stateId":   10 },
  "Бердичівський район"              : { "regionId":   57, "legacyId":  7, "stateId":   10 },
  "Бердичів"                         : { "regionId":   57, "legacyId":  7, "stateId":   10 },
  "Житомирський район"               : { "regionId":   59, "legacyId":  7, "stateId":   10 },
  "Житомир"                          : { "regionId":   59, "legacyId":  7, "stateId":   10 },
  "Радомишль"                        : { "regionId":   59, "legacyId":  7, "stateId":   10 },
  "Звягельський район"               : { "regionId":   60, "legacyId":  7, "stateId":   10 },
  "Звягель"                          : { "regionId":   60, "legacyId":  7, "stateId":   10 },
  "Коростенський район"              : { "regionId":   58, "legacyId":  7, "stateId":   10 },
  "Коростень"                        : { "regionId":   58, "legacyId":  7, "stateId":   10 },
  "Овруч"                            : { "regionId":   58, "legacyId":  7, "stateId":   10 },
  "Закарпатська область"             : { "regionId":   11, "legacyId":  1, "stateId":   11 },
  "Берегівський район"               : { "regionId":   61, "legacyId":  1, "stateId":   11 },
  "Берегове"                         : { "regionId":   61, "legacyId":  1, "stateId":   11 },
  "Мукачівський район"               : { "regionId":   65, "legacyId":  1, "stateId":   11 },
  "Мукачево"                         : { "regionId":   65, "legacyId":  1, "stateId":   11 },
  "Рахівський район"                 : { "regionId":   63, "legacyId":  1, "stateId":   11 },
  "Рахів"                            : { "regionId":   63, "legacyId":  1, "stateId":   11 },
  "Тячівський район"                 : { "regionId":   64, "legacyId":  1, "stateId":   11 },
  "Тячів"                            : { "regionId":   64, "legacyId":  1, "stateId":   11 },
  "Ужгородський район"               : { "regionId":   66, "legacyId":  1, "stateId":   11 },
  "Ужгород"                          : { "regionId":   66, "legacyId":  1, "stateId":   11 },
  "Хустський район"                  : { "regionId":   62, "legacyId":  1, "stateId":   11 },
  "Хуст"                             : { "regionId":   62, "legacyId":  1, "stateId":   11 },
  "Запорізька область"               : { "regionId":   12, "legacyId": 14, "stateId":   12 },
  "Бердянський район"                : { "regionId":  147, "legacyId": 14, "stateId":   12 },
  "Бердянськ"                        : { "regionId":  147, "legacyId": 14, "stateId":   12 },
  "Василівський район"               : { "regionId":  146, "legacyId": 14, "stateId":   12 },
  "Енергодар"                        : { "regionId":  146, "legacyId": 14, "stateId":   12 },
  "Запорізький район"                : { "regionId":  149, "legacyId": 14, "stateId":   12 },
  "Біленьке"                         : { "regionId":  149, "legacyId": 14, "stateId":   12 },
  "Вільнянськ"                       : { "regionId":  149, "legacyId": 14, "stateId":   12 },
  "Запоріжжя"                        : { "regionId":  564, "legacyId": 14, "stateId":  564 },
  "Комишуваха"                       : { "regionId":  149, "legacyId": 14, "stateId":   12 },
  "Таврійське"                       : { "regionId":  149, "legacyId": 14, "stateId":   12 },
  "Мелітопольський район"            : { "regionId":  148, "legacyId": 14, "stateId":   12 },
  "Мелітополь"                       : { "regionId":  148, "legacyId": 14, "stateId":   12 },
  "Пологівський район"               : { "regionId":  145, "legacyId": 14, "stateId":   12 },
  "Гуляйполе"                        : { "regionId":  145, "legacyId": 14, "stateId":   12 },
  "Кам'янка"                         : { "regionId":  145, "legacyId": 14, "stateId":   12 },
  "Оріхів"                           : { "regionId":  145, "legacyId": 14, "stateId":   12 },
  "Пологи"                           : { "regionId":  145, "legacyId": 14, "stateId":   12 },
  "Токмак"                           : { "regionId":  145, "legacyId": 14, "stateId":   12 },
  "Київ"                             : { "regionId":   31, "legacyId": 26, "stateId":   31 },
  "Київська область"                 : { "regionId":   14, "legacyId":  8, "stateId":   14 },
  "Бориспільський район"             : { "regionId":   78, "legacyId":  8, "stateId":   14 },
  "Бориспіль"                        : { "regionId":   78, "legacyId":  8, "stateId":   14 },
  "Переяслав"                        : { "regionId":   78, "legacyId":  8, "stateId":   14 },
  "Яготин"                           : { "regionId":   78, "legacyId":  8, "stateId":   14 },
  "Броварський район"                : { "regionId":   79, "legacyId":  8, "stateId":   14 },
  "Бровари"                          : { "regionId":   79, "legacyId":  8, "stateId":   14 },
  "Згурівка"                         : { "regionId":   79, "legacyId":  8, "stateId":   14 },
  "Семиполки"                        : { "regionId":   79, "legacyId":  8, "stateId":   14 },
  "Бучанський район"                 : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Ірпінь"                           : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Бородянка"                        : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Буча"                             : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Білогородка"                      : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Вишневе"                          : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Гостомель"                        : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Макарів"                          : { "regionId":   75, "legacyId":  8, "stateId":   14 },
  "Білоцерківський район"            : { "regionId":   73, "legacyId":  8, "stateId":   14 },
  "Біла Церква"                      : { "regionId":   73, "legacyId":  8, "stateId":   14 },
  "Сквира"                           : { "regionId":   73, "legacyId":  8, "stateId":   14 },
  "Узин"                             : { "regionId":   73, "legacyId":  8, "stateId":   14 },
  "Вишгородський район"              : { "regionId":   74, "legacyId":  8, "stateId":   14 },
  "Вишгород"                         : { "regionId":   74, "legacyId":  8, "stateId":   14 },
  "Славутич"                         : { "regionId":   74, "legacyId":  8, "stateId":   14 },
  "Обухівський район"                : { "regionId":   76, "legacyId":  8, "stateId":   14 },
  "Богуслав"                         : { "regionId":   76, "legacyId":  8, "stateId":   14 },
  "Васильків"                        : { "regionId":   76, "legacyId":  8, "stateId":   14 },
  "Кагарлик"                         : { "regionId":   76, "legacyId":  8, "stateId":   14 },
  "Миронівка"                        : { "regionId":   76, "legacyId":  8, "stateId":   14 },
  "Обухів"                           : { "regionId":   76, "legacyId":  8, "stateId":   14 },
  "Фастівський район"                : { "regionId":   77, "legacyId":  8, "stateId":   14 },
  "Боярка"                           : { "regionId":   77, "legacyId":  8, "stateId":   14 },
  "Фастів"                           : { "regionId":   77, "legacyId":  8, "stateId":   14 },
  "Автономна Республіка Крим"        : { "regionId": 9999, "legacyId": 16, "stateId": 9999 },
  "Євпаторійський район"             : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Євпаторія"                        : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Бахчисарайський район"            : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Бахчисарай"                       : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Білогірський район"               : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Білогірськ"                       : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Джанкойський район"               : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Джанкой"                          : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Керченський район"                : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Керч"                             : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Севастополь"                      : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Курманський район"                : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Курман"                           : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Перекопський район"               : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Яни Капу"                         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Сімферопольський район"           : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Сімферополь"                      : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Феодосійський район"              : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Феодосія"                         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Ялтинський район"                 : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Ялта"                             : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Кіровоградська область"           : { "regionId":   15, "legacyId": 22, "stateId":   15 },
  "Голованівський район"             : { "regionId":   82, "legacyId": 22, "stateId":   15 },
  "Голованівськ"                     : { "regionId":   82, "legacyId": 22, "stateId":   15 },
  "Кропивницький район"              : { "regionId":   81, "legacyId": 22, "stateId":   15 },
  "Кропивницький"                    : { "regionId":   81, "legacyId": 22, "stateId":   15 },
  "Новоукраїнський район"            : { "regionId":   83, "legacyId": 22, "stateId":   15 },
  "Новоукраїнка"                     : { "regionId":   83, "legacyId": 22, "stateId":   15 },
  "Олександрійський район"           : { "regionId":   80, "legacyId": 22, "stateId":   15 },
  "Олександрія"                      : { "regionId":   80, "legacyId": 22, "stateId":   15 },
  "Світловодськ"                     : { "regionId":   80, "legacyId": 22, "stateId":   15 },
  "Луганська область"                : { "regionId":   16, "legacyId": 12, "stateId":   16 },
  "Алчевський район"                 : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Алчевськ"                         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Брянка"                           : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Кадіївка"                         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Довжанський район"                : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Довжанськ"                        : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Луганський район"                 : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Луганськ"                         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Ровеньківський район"             : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Антрацит"                         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Ровеньки"                         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Хрустальний"                      : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Сватівський район"                : { "regionId":   85, "legacyId": 12, "stateId":   16 },
  "Рубіжне"                          : { "regionId":   84, "legacyId": 12, "stateId":   16 },
  "Старобільський район"             : { "regionId":   86, "legacyId": 12, "stateId":   16 },
  "Старобільськ"                     : { "regionId":   86, "legacyId": 12, "stateId":   16 },
  "Сіверськодонецький район"         : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Золоте"                           : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Лисичанськ"                       : { "regionId":   84, "legacyId": 12, "stateId":   16 },
  "Сіверськодонецьк"                 : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Щастинський район"                : { "regionId":   87, "legacyId": 12, "stateId":   16 },
  "Новоайдар"                        : { "regionId":   87, "legacyId": 12, "stateId":   16 },
  "Львівська область"                : { "regionId":   27, "legacyId":  4, "stateId":   27 },
  "Дрогобицький район"               : { "regionId":   91, "legacyId":  4, "stateId":   27 },
  "Дрогобич"                         : { "regionId":   91, "legacyId":  4, "stateId":   27 },
  "Золочівський район"               : { "regionId":   94, "legacyId":  4, "stateId":   27 },
  "Золочів (Львівська)"              : { "regionId":   94, "legacyId":  4, "stateId":   27 },
  "Львівський район"                 : { "regionId":   90, "legacyId":  4, "stateId":   27 },
  "Львів"                            : { "regionId":   90, "legacyId":  4, "stateId":   27 },
  "Самбірський район"                : { "regionId":   88, "legacyId":  4, "stateId":   27 },
  "Самбір"                           : { "regionId":   88, "legacyId":  4, "stateId":   27 },
  "Стрийський район"                 : { "regionId":   89, "legacyId":  4, "stateId":   27 },
  "Стрий"                            : { "regionId":   89, "legacyId":  4, "stateId":   27 },
  "Червоноградський район"           : { "regionId":   92, "legacyId":  4, "stateId":   27 },
  "Шептицький"                       : { "regionId":   92, "legacyId":  4, "stateId":   27 },
  "Яворівський район"                : { "regionId":   93, "legacyId":  4, "stateId":   27 },
  "Яворів"                           : { "regionId":   93, "legacyId":  4, "stateId":   27 },
  "Миколаївська область"             : { "regionId":   17, "legacyId": 18, "stateId":   17 },
  "Баштанський район"                : { "regionId":   96, "legacyId": 18, "stateId":   17 },
  "Баштанка"                         : { "regionId":   96, "legacyId": 18, "stateId":   17 },
  "Новий Буг"                        : { "regionId":   96, "legacyId": 18, "stateId":   17 },
  "Снігурівка"                       : { "regionId":   96, "legacyId": 18, "stateId":   17 },
  "Вознесенський район"              : { "regionId":   95, "legacyId": 18, "stateId":   17 },
  "Єланець"                          : { "regionId":   95, "legacyId": 18, "stateId":   17 },
  "Вознесенськ"                      : { "regionId":   95, "legacyId": 18, "stateId":   17 },
  "Південноукраїнськ (Южноукраїнськ)": { "regionId":   95, "legacyId": 18, "stateId":   17 },
  "Миколаївський район"              : { "regionId":   98, "legacyId": 18, "stateId":   17 },
  "Куцуруб"                          : { "regionId":   98, "legacyId": 18, "stateId":   17 },
  "Миколаїв"                         : { "regionId":   98, "legacyId": 18, "stateId":   17 },
  "Очаків"                           : { "regionId":   98, "legacyId": 18, "stateId":   17 },
  "Первомайський район"              : { "regionId":   97, "legacyId": 18, "stateId":   17 },
  "Арбузинка"                        : { "regionId":   97, "legacyId": 18, "stateId":   17 },
  "Криве Озеро"                      : { "regionId":   97, "legacyId": 18, "stateId":   17 },
  "Первомайськ"                      : { "regionId":   97, "legacyId": 18, "stateId":   17 },
  "Одеська область"                  : { "regionId":   18, "legacyId": 17, "stateId":   18 },
  "Ізмаїльський район"               : { "regionId":  101, "legacyId": 17, "stateId":   18 },
  "Ізмаїл"                           : { "regionId":  101, "legacyId": 17, "stateId":   18 },
  "Кілія"                            : { "regionId":  101, "legacyId": 17, "stateId":   18 },
  "Березівський район"               : { "regionId":  100, "legacyId": 17, "stateId":   18 },
  "Березівка"                        : { "regionId":  100, "legacyId": 17, "stateId":   18 },
  "Болградський район"               : { "regionId":  105, "legacyId": 17, "stateId":   18 },
  "Болград"                          : { "regionId":  105, "legacyId": 17, "stateId":   18 },
  "Білгород-Дністровський район"     : { "regionId":  102, "legacyId": 17, "stateId":   18 },
  "Білгород-Дністровський"           : { "regionId":  102, "legacyId": 17, "stateId":   18 },
  "Сергіївка"                        : { "regionId":  102, "legacyId": 17, "stateId":   18 },
  "Одеський район"                   : { "regionId":  104, "legacyId": 17, "stateId":   18 },
  "Біляївка"                         : { "regionId":  104, "legacyId": 17, "stateId":   18 },
  "Затока"                           : { "regionId":  104, "legacyId": 17, "stateId":   18 },
  "Одеса"                            : { "regionId":  104, "legacyId": 17, "stateId":   18 },
  "Південне (Южне)"                  : { "regionId":  104, "legacyId": 17, "stateId":   18 },
  "Чорноморськ"                      : { "regionId":  104, "legacyId": 17, "stateId":   18 },
  "Подільський район"                : { "regionId":   99, "legacyId": 17, "stateId":   18 },
  "Подільськ"                        : { "regionId":   99, "legacyId": 17, "stateId":   18 },
  "Роздільнянський район"            : { "regionId":  103, "legacyId": 17, "stateId":   18 },
  "Лиманське"                        : { "regionId":  103, "legacyId": 17, "stateId":   18 },
  "Роздільна"                        : { "regionId":  103, "legacyId": 17, "stateId":   18 },
  "Полтавська область"               : { "regionId":   19, "legacyId": 20, "stateId":   19 },
  "Кременчуцький район"              : { "regionId":  107, "legacyId": 20, "stateId":   19 },
  "Горішні Плавні"                   : { "regionId":  107, "legacyId": 20, "stateId":   19 },
  "Кременчук"                        : { "regionId":  107, "legacyId": 20, "stateId":   19 },
  "Лубни"                            : { "regionId":  106, "legacyId": 20, "stateId":   19 },
  "Миргород"                         : { "regionId":  108, "legacyId": 20, "stateId":   19 },
  "Хорол"                            : { "regionId":  107, "legacyId": 20, "stateId":   19 },
  "Лубенський район"                 : { "regionId":  106, "legacyId": 20, "stateId":   19 },
  "Гребінка"                         : { "regionId":  106, "legacyId": 20, "stateId":   19 },
  "Пирятин"                          : { "regionId":  106, "legacyId": 20, "stateId":   19 },
  "Миргородський район"              : { "regionId":  108, "legacyId": 20, "stateId":   19 },
  "Полтавський район"                : { "regionId":  109, "legacyId": 20, "stateId":   19 },
  "Карлівка"                         : { "regionId":  109, "legacyId": 20, "stateId":   19 },
  "Полтава"                          : { "regionId":  109, "legacyId": 20, "stateId":   19 },
  "Рівненська область"               : { "regionId":    5, "legacyId":  6, "stateId":    5 },
  "Вараський район"                  : { "regionId":  110, "legacyId":  6, "stateId":    5 },
  "Вараш"                            : { "regionId":  110, "legacyId":  6, "stateId":    5 },
  "Дубенський район"                 : { "regionId":  111, "legacyId":  6, "stateId":    5 },
  "Дубно"                            : { "regionId":  111, "legacyId":  6, "stateId":    5 },
  "Рівненський район"                : { "regionId":  112, "legacyId":  6, "stateId":    5 },
  "Березне"                          : { "regionId":  112, "legacyId":  6, "stateId":    5 },
  "Корець"                           : { "regionId":  112, "legacyId":  6, "stateId":    5 },
  "Рівне"                            : { "regionId":  112, "legacyId":  6, "stateId":    5 },
  "Сарненський район"                : { "regionId":  113, "legacyId":  6, "stateId":    5 },
  "Сарни"                            : { "regionId":  113, "legacyId":  6, "stateId":    5 },
  "Сумська область"                  : { "regionId":   20, "legacyId": 10, "stateId":   20 },
  "Конотопський район"               : { "regionId":  117, "legacyId": 10, "stateId":   20 },
  "Буринь"                           : { "regionId":  117, "legacyId": 10, "stateId":   20 },
  "Конотоп"                          : { "regionId":  117, "legacyId": 10, "stateId":   20 },
  "Кролевець"                        : { "regionId":  117, "legacyId": 10, "stateId":   20 },
  "Нова Слобода"                     : { "regionId":  117, "legacyId": 10, "stateId":   20 },
  "Путивль"                          : { "regionId":  117, "legacyId": 10, "stateId":   20 },
  "Охтирський район"                 : { "regionId":  118, "legacyId": 10, "stateId":   20 },
  "Велика Писарівка"                 : { "regionId":  118, "legacyId": 10, "stateId":   20 },
  "Охтирка"                          : { "regionId":  118, "legacyId": 10, "stateId":   20 },
  "Тростянець"                       : { "regionId":  118, "legacyId": 10, "stateId":   20 },
  "Роменський район"                 : { "regionId":  116, "legacyId": 10, "stateId":   20 },
  "Недригайлів"                      : { "regionId":  116, "legacyId": 10, "stateId":   20 },
  "Ромни"                            : { "regionId":  116, "legacyId": 10, "stateId":   20 },
  "Сумський район"                   : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Іскрисківщина"                    : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Атинське"                         : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Басівка"                          : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Будки"                            : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Білопілля"                        : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Волфине"                          : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Ворожба"                          : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Катеринівка"                      : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Краснопілля"                      : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Кіндратівка"                      : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Лебедин"                          : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Мезенівка"                        : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Миколаївка"                       : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Миропілля"                        : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Могриця"                          : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Ободи"                            : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Павлівка"                         : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Рижівка"                          : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Суми"                             : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Угроїди"                          : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Хотінь"                           : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Юнаківка"                         : { "regionId":  114, "legacyId": 10, "stateId":   20 },
  "Шосткинський район"               : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Вороніж"                          : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Глухів"                           : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Есмань"                           : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Зноб-Новгородське"                : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Свеса"                            : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Середина-Буда"                    : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Шалигине"                         : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Шостка"                           : { "regionId":  115, "legacyId": 10, "stateId":   20 },
  "Тернопільська область"            : { "regionId":   21, "legacyId":  3, "stateId":   21 },
  "Кременецький район"               : { "regionId":  120, "legacyId":  3, "stateId":   21 },
  "Кременець"                        : { "regionId":  120, "legacyId":  3, "stateId":   21 },
  "Тернопільський район"             : { "regionId":  119, "legacyId":  3, "stateId":   21 },
  "Тернопіль"                        : { "regionId":  119, "legacyId":  3, "stateId":   21 },
  "Чортківський район"               : { "regionId":  121, "legacyId":  3, "stateId":   21 },
  "Чортків"                          : { "regionId":  121, "legacyId":  3, "stateId":   21 },
  "Тест"                             : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Тестовий район"                   : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Тестове місто"                    : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Харківська область"               : { "regionId":   22, "legacyId": 11, "stateId":   22 },
  "Ізюмський район"                  : { "regionId":  125, "legacyId": 11, "stateId":   22 },
  "Ізюм"                             : { "regionId":  125, "legacyId": 11, "stateId":   22 },
  "Балаклія"                         : { "regionId":  125, "legacyId": 11, "stateId":   22 },
  "Борова"                           : { "regionId":  125, "legacyId": 11, "stateId":   22 },
  "Красноградський район"            : { "regionId":  127, "legacyId": 11, "stateId":   22 },
  "Берестин"                         : { "regionId":  127, "legacyId": 11, "stateId":   22 },
  "Богодухівський район"             : { "regionId":  126, "legacyId": 11, "stateId":   22 },
  "Богодухів"                        : { "regionId":  126, "legacyId": 11, "stateId":   22 },
  "Золочів"                          : { "regionId":  126, "legacyId": 11, "stateId":   22 },
  "Куп'янський район"                : { "regionId":  123, "legacyId": 11, "stateId":   22 },
  "Куп'янськ"                        : { "regionId":  123, "legacyId": 11, "stateId":   22 },
  "Лозівський район"                 : { "regionId":  128, "legacyId": 11, "stateId":   22 },
  "Златопіль"                        : { "regionId":  128, "legacyId": 11, "stateId":   22 },
  "Лозова"                           : { "regionId":  128, "legacyId": 11, "stateId":   22 },
  "Харківський район"                : { "regionId":  124, "legacyId": 11, "stateId":   22 },
  "Дергачі"                          : { "regionId":  124, "legacyId": 11, "stateId":   22 },
  "Козача Лопань"                    : { "regionId":  124, "legacyId": 11, "stateId":   22 },
  "Липці"                            : { "regionId":  124, "legacyId": 11, "stateId":   22 },
  "Мерефа"                           : { "regionId":  124, "legacyId": 11, "stateId":   22 },
  "Пісочин"                          : { "regionId":  124, "legacyId": 11, "stateId":   22 },
  "Харків"                           : { "regionId": 1293, "legacyId": 11, "stateId": 1293 },
  "Циркуни"                          : { "regionId":  124, "legacyId": 11, "stateId":   22 },
  "Чугуївський район"                : { "regionId":  122, "legacyId": 11, "stateId":   22 },
  "Білий Колодязь"                   : { "regionId":  122, "legacyId": 11, "stateId":   22 },
  "Вовчанськ"                        : { "regionId":  122, "legacyId": 11, "stateId":   22 },
  "Коробочкине"                      : { "regionId":  122, "legacyId": 11, "stateId":   22 },
  "Чугуїв"                           : { "regionId":  122, "legacyId": 11, "stateId":   22 },
  "Херсонська область"               : { "regionId":   23, "legacyId": 15, "stateId":   23 },
  "Бериславський район"              : { "regionId":  129, "legacyId": 15, "stateId":   23 },
  "Берислав"                         : { "regionId":  129, "legacyId": 15, "stateId":   23 },
  "Генічеський район"                : { "regionId":  133, "legacyId": 15, "stateId":   23 },
  "Генічеськ"                        : { "regionId":  133, "legacyId": 15, "stateId":   23 },
  "Каховський район"                 : { "regionId":  131, "legacyId": 15, "stateId":   23 },
  "Каховка"                          : { "regionId":  131, "legacyId": 15, "stateId":   23 },
  "Нова Каховка"                     : { "regionId":  131, "legacyId": 15, "stateId":   23 },
  "Таврійськ"                        : { "regionId":  131, "legacyId": 15, "stateId":   23 },
  "Чаплинка"                         : { "regionId":  131, "legacyId": 15, "stateId":   23 },
  "Скадовський район"                : { "regionId":  130, "legacyId": 15, "stateId":   23 },
  "Скадовськ"                        : { "regionId":  130, "legacyId": 15, "stateId":   23 },
  "Херсонський район"                : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Антонівка"                        : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Білозерка"                        : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Олександрівка"                    : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Олешки"                           : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Херсон"                           : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Чорнобаївка"                      : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Хмельницька область"              : { "regionId":    3, "legacyId": 24, "stateId":    3 },
  "Кам'янець-Подільський район"      : { "regionId":  135, "legacyId": 24, "stateId":    3 },
  "Кам'янець-Подільський"            : { "regionId":  135, "legacyId": 24, "stateId":    3 },
  "Хмельницький район"               : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Волочиськ"                        : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Старокостянтинів"                 : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Теофіполь"                        : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Хмельницький"                     : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Шепетівський район"               : { "regionId":  136, "legacyId": 24, "stateId":    3 },
  "Нетішин"                          : { "regionId":  136, "legacyId": 24, "stateId":    3 },
  "Славута"                          : { "regionId":  136, "legacyId": 24, "stateId":    3 },
  "Шепетівка"                        : { "regionId":  136, "legacyId": 24, "stateId":    3 },
  "Черкаська область"                : { "regionId":   24, "legacyId": 21, "stateId":   24 },
  "Звенигородський район"            : { "regionId":  150, "legacyId": 21, "stateId":   24 },
  "Багачеве"                         : { "regionId":  150, "legacyId": 21, "stateId":   24 },
  "Звенигородка"                     : { "regionId":  150, "legacyId": 21, "stateId":   24 },
  "Золотоніський район"              : { "regionId":  153, "legacyId": 21, "stateId":   24 },
  "Золотоноша"                       : { "regionId":  153, "legacyId": 21, "stateId":   24 },
  "Уманський район"                  : { "regionId":  151, "legacyId": 21, "stateId":   24 },
  "Жашків"                           : { "regionId":  151, "legacyId": 21, "stateId":   24 },
  "Умань"                            : { "regionId":  151, "legacyId": 21, "stateId":   24 },
  "Черкаський район"                 : { "regionId":  152, "legacyId": 21, "stateId":   24 },
  "Канів"                            : { "regionId":  152, "legacyId": 21, "stateId":   24 },
  "Корсунь-Шевченківський"           : { "regionId":  152, "legacyId": 21, "stateId":   24 },
  "Сміла"                            : { "regionId":  152, "legacyId": 21, "stateId":   24 },
  "Черкаси"                          : { "regionId":  152, "legacyId": 21, "stateId":   24 },
  "Чернівецька область"              : { "regionId":   26, "legacyId": 25, "stateId":   26 },
  "Вижницький район"                 : { "regionId":  138, "legacyId": 25, "stateId":   26 },
  "Вижниця"                          : { "regionId":  138, "legacyId": 25, "stateId":   26 },
  "Дністровський район"              : { "regionId":  139, "legacyId": 25, "stateId":   26 },
  "Кельменці"                        : { "regionId":  139, "legacyId": 25, "stateId":   26 },
  "Чернівецький район"               : { "regionId":  137, "legacyId": 25, "stateId":   26 },
  "Чернівці"                         : { "regionId":  137, "legacyId": 25, "stateId":   26 },
  "Чернігівська область"             : { "regionId":   25, "legacyId":  9, "stateId":   25 },
  "Корюківський район"               : { "regionId":  144, "legacyId":  9, "stateId":   25 },
  "Корюківка"                        : { "regionId":  144, "legacyId":  9, "stateId":   25 },
  "Новгород-Сіверський район"        : { "regionId":  141, "legacyId":  9, "stateId":   25 },
  "Новгород-Сіверський"              : { "regionId":  141, "legacyId":  9, "stateId":   25 },
  "Семенівка"                        : { "regionId":  141, "legacyId":  9, "stateId":   25 },
  "Ніжинський район"                 : { "regionId":  142, "legacyId":  9, "stateId":   25 },
  "Бахмач"                           : { "regionId":  142, "legacyId":  9, "stateId":   25 },
  "Борзна"                           : { "regionId":  142, "legacyId":  9, "stateId":   25 },
  "Носівка"                          : { "regionId":  142, "legacyId":  9, "stateId":   25 },
  "Ніжин"                            : { "regionId":  142, "legacyId":  9, "stateId":   25 },
  "Прилуцький район"                 : { "regionId":  143, "legacyId":  9, "stateId":   25 },
  "Ічня"                             : { "regionId":  143, "legacyId":  9, "stateId":   25 },
  "Прилуки"                          : { "regionId":  143, "legacyId":  9, "stateId":   25 },
  "Талалаївка"                       : { "regionId":  143, "legacyId":  9, "stateId":   25 },
  "Чернігівський район"              : { "regionId":  140, "legacyId":  9, "stateId":   25 },
  "Гончарівське"                     : { "regionId":  140, "legacyId":  9, "stateId":   25 },
  "Десна"                            : { "regionId":  140, "legacyId":  9, "stateId":   25 },
  "Остер"                            : { "regionId":  140, "legacyId":  9, "stateId":   25 },
  "Чернігів"                         : { "regionId":  140, "legacyId":  9, "stateId":   25 }
}






def make_hex(json_doc):
    json_str = json.dumps(json_doc, sort_keys=True)
    json_bytes = json_str.encode("utf-8")
    hash_object = hashlib.sha256()
    hash_object.update(json_bytes)
    current_hex = hash_object.hexdigest()
    return current_hex


def get_slug(name, districts_slug):
    slug_name = districts_slug.get(name) or "UNKNOWN"
    return slug_name


def format_time(time):
    dt = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
    formatted_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return formatted_timestamp


async def get_cache_data(mc, key_b, default_response=None):
    if default_response is None:
        default_response = {}

    cache = await mc.get(key_b)

    if cache:
        cache = json.loads(cache.decode("utf-8"))
    else:
        cache = default_response

    return cache


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def calculate_time_difference(timestamp1, timestamp2):
    format_str = "%Y-%m-%dT%H:%M:%SZ"

    time1 = datetime.datetime.strptime(timestamp1, format_str)
    time2 = datetime.datetime.strptime(timestamp2, format_str)

    time_difference = (time2 - time1).total_seconds()
    return int(abs(time_difference))


async def service_is_fine(mc, key_b):
    await mc.set(key_b, get_current_datetime().encode("utf-8"))


async def get_etryvoga_data(mc):
    while True:
        if await get_cache_data(mc, b"etryvoga_districts"):
            break
        else:
            logger.warning("get_etryvoga_data: wait for districts cache")
        await asyncio.sleep(1)
    while True:
        try:
            logger.debug("start get_etryvoga_data")

            cache_keys = [
                b"etryvoga_districts_struct",
                b"explosions_etryvoga",
                b"missiles_etryvoga",
                b"drones_etryvoga",
                b"kabs_etryvoga",
            ]
            cached_data = await asyncio.gather(*(mc.get(key) for key in cache_keys))

            districts_slug_cached, explosions_cached, missiles_cached, drones_cached, kabs_cached = cached_data

            if districts_slug_cached:
                districts_slug_cached = json.loads(districts_slug_cached)
            else:
                districts_slug_cached = {}

            if explosions_cached:
                explosions_cached_data = json.loads(explosions_cached.decode("utf-8"))
            else:
                explosions_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

            if missiles_cached:
                missiles_cached_data = json.loads(missiles_cached.decode("utf-8"))
            else:
                missiles_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

            if drones_cached:
                drones_cached_data = json.loads(drones_cached.decode("utf-8"))
            else:
                drones_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

            if kabs_cached:
                kabs_cached_data = json.loads(kabs_cached.decode("utf-8"))
            else:
                kabs_cached_data = {"version": 1, "states": {}, "info": {"last_update": None, "last_id": 0}}

            last_id = None

            async with aiohttp.ClientSession() as session:
                response = await session.get(etryvoga_url)
                if response.status == 200:
                    etryvoga_full = await response.text()
                    data = json.loads(etryvoga_full)
                    logger.debug(
                        "{type:<12} {time:<5} {region:<25} {state:<25} {body}".format(
                            type="type", state="state_name", region="region", body="body", time="diff"
                        )
                    )
                    logger.debug("------------ ----- ------------------------- ------------------------- -----------")
                    for message in data[::-1]:
                        current_hex = make_hex(message)

                        state_name = regions[get_slug(message["region"], districts_slug_cached)]["name"]
                        state_id = regions[get_slug(message["region"], districts_slug_cached)]["regionId"]
                        message["regionId"] = state_id
                        logger.debug(
                            "{type:<12} {time:<5} {rid:<5}{region:<25} {state:<25} {body}".format(
                                type=message["type"],
                                state=state_name,
                                rid=state_id,
                                region=message["region"],
                                body=message["body"],
                                time=calculate_time_difference(
                                    format_time(message["createdAt"]), get_current_datetime()
                                ),
                            )
                        )
                        if state_name == "Невідомо":
                            continue
                        region_data = {
                            "lastUpdate": format_time(message["createdAt"]),
                        }
                        match message["type"]:
                            case "EXPLOSION":
                                explosions_cached_data["states"][state_id] = region_data
                            case "ROCKET" | "ROCKET_FIRE":
                                missiles_cached_data["states"][state_id] = region_data
                            case "DRONE" | "RECON_DRONE":
                                drones_cached_data["states"][state_id] = region_data
                            case "KAB":
                                kabs_cached_data["states"][state_id] = region_data
                            case _:
                                pass
                        last_id = current_hex
                    logger.debug("------------ ----- ------------------------- ------------------------- -----------")

                    with contextlib.suppress(KeyError):
                        del explosions_cached_data["states"]["Невідомо"]

                    explosions_cached_data["info"]["last_id"] = last_id
                    explosions_cached_data["info"]["last_update"] = get_current_datetime()
                    missiles_cached_data["info"]["last_id"] = last_id
                    missiles_cached_data["info"]["last_update"] = get_current_datetime()
                    drones_cached_data["info"]["last_id"] = last_id
                    drones_cached_data["info"]["last_update"] = get_current_datetime()
                    kabs_cached_data["info"]["last_id"] = last_id
                    kabs_cached_data["info"]["last_update"] = get_current_datetime()
                    logger.debug("store etryvoga data")
                    await asyncio.gather(
                        mc.set(b"explosions_etryvoga", json.dumps(explosions_cached_data).encode("utf-8")),
                        mc.set(b"missiles_etryvoga", json.dumps(missiles_cached_data).encode("utf-8")),
                        mc.set(b"drones_etryvoga", json.dumps(drones_cached_data).encode("utf-8")),
                        mc.set(b"kabs_etryvoga", json.dumps(kabs_cached_data).encode("utf-8")),
                        mc.set(b"etryvoga_last_id", json.dumps({"last_id": last_id}).encode("utf-8")),
                        mc.set(b"etryvoga_full", json.dumps(data).encode("utf-8")),
                        service_is_fine(mc, b"etryvoga_api_last_call"),
                    )
                    logger.info("etryvoga data stored")
                    logger.debug("end get_etryvoga_data")
                else:
                    logger.error(f"get_etryvoga_data: Request failed with status code {response.status}")
            await asyncio.sleep(etryvoga_loop_time)
        except KeyError as e:
            logger.error(f"get_etryvoga_data: Помилка доступу до ключа {e.args[0]}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)
        except aiohttp.ClientError as e:
            logger.error(f"get_etryvoga_data: Помилка мережі: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)
        except json.JSONDecodeError as e:
            logger.error(f"get_etryvoga_data: Помилка парсингу JSON: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"get_etryvoga_data: Неочікувана помилка: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
            await asyncio.sleep(60)


async def get_etryvoga_districts(mc):
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(etryvoga_districts_url)
                if response.status == 200:
                    etryvoga_full = await response.text()
                    data = json.loads(etryvoga_full)
                    data_struct = make_districts_struct(data)
                    logger.debug("store etryvoga_districts")
                    await asyncio.gather(
                        mc.set(b"etryvoga_districts", json.dumps(data).encode("utf-8")),
                        mc.set(b"etryvoga_districts_struct", json.dumps(data_struct).encode("utf-8")),
                        service_is_fine(mc, b"etryvoga_districts_api_last_call"),
                    )
                    logger.info("etryvoga_districts stored")
                else:
                    logger.error(f"get_etryvoga_districts: Request failed with status code {response.status}")
        except Exception as e:
            logger.error(f"get_etryvoga_districts: {str(e)}")
        await asyncio.sleep(etryvoga_districts_loop_time)


def make_districts_struct(data):
    region_keys = regions.keys()
    struct = {}
    for area in data:
        area_slug = area["slug"]
        struct[area_slug] = area_slug
        for district in area["districts"]:
            district_slug = district["slug"]
            struct[district["slug"]] = district_slug
            for city in district["cities"]:
                if city["slug"] in region_keys:
                    struct[city["slug"]] = city["slug"]
                else:
                    struct[city["slug"]] = district_slug

    return struct


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(
            get_etryvoga_data(mc), 
            get_etryvoga_districts(mc))
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
