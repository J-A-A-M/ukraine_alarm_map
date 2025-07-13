import json
import os
import asyncio
import logging
import datetime
import struct
from aiomcache import Client
from copy import deepcopy
from collections import defaultdict

version = 3

debug_level = os.environ.get("LOGGING") or "INFO"
memcached_host = os.environ.get("MEMCACHED_HOST") or "memcached"
update_period = int(os.environ.get("UPDATE_PERIOD", 1))
update_period_long = int(os.environ.get("UPDATE_PERIOD_LONG", 60))

logging.basicConfig(level=debug_level, format="%(asctime)s %(levelname)s : %(message)s")
logger = logging.getLogger(__name__)


TYPE_ALERTS_BATCH      = 0xA1
TYPE_RADIATION_BATCH   = 0xA2
TYPE_TEMPERATURE_BATCH = 0xA3
TYPE_GRID_BATCH        = 0xA4


regions = {
  "Вся Україна"                      : { "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "Івано-Франківська область"        : { "regionId":   13, "legacyId":  2, "stateId":   13 },
  "Івано-Франківський район"         : { "regionId":   68, "legacyId":  2, "stateId":   13 },
  "Івано-Франківськ"                 : { "regionId":  632, "legacyId":  2, "stateId":   13 },
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
  "Луцьк"                            : { "regionId":  225, "legacyId":  5, "stateId":    8 },
  "Вінницька область"                : { "regionId":    4, "legacyId": 23, "stateId":    4 },
  "Вінницький район"                 : { "regionId":   36, "legacyId": 23, "stateId":    4 },
  "Вінниця"                          : { "regionId":  155, "legacyId": 23, "stateId":    4 },
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
  "Дніпро"                           : { "regionId":  332, "legacyId": 19, "stateId":    9 },
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
  "Житомир"                          : { "regionId":  442, "legacyId":  7, "stateId":   10 },
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
  "Ужгород"                          : { "regionId":  500, "legacyId":  1, "stateId":   11 },
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
  "Запоріжжя"                        : { "regionId":  564, "legacyId": 14, "stateId":   12 },
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
  "Кропивницький"                    : { "regionId":  761, "legacyId": 22, "stateId":   15 },
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
  "Львів"                            : { "regionId":  845, "legacyId":  4, "stateId":   27 },
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
  "Миколаїв"                         : { "regionId":  926, "legacyId": 18, "stateId":   17 },
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
  "Одеса"                            : { "regionId":  964, "legacyId": 17, "stateId":   18 },
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
  "Полтава"                          : { "regionId": 1060, "legacyId": 20, "stateId":   19 },
  "Рівненська область"               : { "regionId":    5, "legacyId":  6, "stateId":    5 },
  "Вараський район"                  : { "regionId":  110, "legacyId":  6, "stateId":    5 },
  "Вараш"                            : { "regionId":  110, "legacyId":  6, "stateId":    5 },
  "Дубенський район"                 : { "regionId":  111, "legacyId":  6, "stateId":    5 },
  "Дубно"                            : { "regionId":  111, "legacyId":  6, "stateId":    5 },
  "Рівненський район"                : { "regionId":  112, "legacyId":  6, "stateId":    5 },
  "Березне"                          : { "regionId":  112, "legacyId":  6, "stateId":    5 },
  "Корець"                           : { "regionId":  112, "legacyId":  6, "stateId":    5 },
  "Рівне"                            : { "regionId": 1133, "legacyId":  6, "stateId":    5 },
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
  "Суми"                             : { "regionId": 1187, "legacyId": 10, "stateId":   20 },
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
  "Тернопіль"                        : { "regionId": 1241, "legacyId":  3, "stateId":   21 },
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
  "Харків"                           : { "regionId": 1293, "legacyId": 11, "stateId":   22 },
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
  "Херсон"                           : { "regionId": 1370, "legacyId": 15, "stateId":   23 },
  "Чорнобаївка"                      : { "regionId":  132, "legacyId": 15, "stateId":   23 },
  "Хмельницька область"              : { "regionId":    3, "legacyId": 24, "stateId":    3 },
  "Кам'янець-Подільський район"      : { "regionId":  135, "legacyId": 24, "stateId":    3 },
  "Кам'янець-Подільський"            : { "regionId":  135, "legacyId": 24, "stateId":    3 },
  "Хмельницький район"               : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Волочиськ"                        : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Старокостянтинів"                 : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Теофіполь"                        : { "regionId":  134, "legacyId": 24, "stateId":    3 },
  "Хмельницький"                     : { "regionId": 1400, "legacyId": 24, "stateId":    3 },
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
  "Черкаси"                          : { "regionId": 1473, "legacyId": 21, "stateId":   24 },
  "Чернівецька область"              : { "regionId":   26, "legacyId": 25, "stateId":   26 },
  "Вижницький район"                 : { "regionId":  138, "legacyId": 25, "stateId":   26 },
  "Вижниця"                          : { "regionId":  138, "legacyId": 25, "stateId":   26 },
  "Дністровський район"              : { "regionId":  139, "legacyId": 25, "stateId":   26 },
  "Кельменці"                        : { "regionId":  139, "legacyId": 25, "stateId":   26 },
  "Чернівецький район"               : { "regionId":  137, "legacyId": 25, "stateId":   26 },
  "Чернівці"                         : { "regionId": 1542, "legacyId": 25, "stateId":   26 },
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
  "Чернігів"                         : { "regionId": 1591, "legacyId":  9, "stateId":   25 }
}

LEGACY_LED_COUNT = 28


async def get_cache_data(mc, key_b, default_response=None):
    if default_response is None:
        default_response = {}

    cache = await mc.get(key_b)

    if cache:
        cache = json.loads(cache.decode("utf-8"))
    else:
        cache = default_response

    return cache

async def get_byte_data(mc, key_b, default_response=None):
    if default_response is None:
        default_response = b''

    cache = await mc.get(key_b)

    if not cache:
        cache = default_response

    return cache


async def get_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_historical_alerts(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_regions(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


async def get_weather(mc, key_b, default_response={}):
    return await get_cache_data(mc, key_b, default_response={})


def convert_region_ids(key_value, initial_key, result_key):
    for region_name, region_data in regions.items():
        if region_data[initial_key] == key_value and not region_data.get("skip"):
            return region_name, region_data[result_key]
    return None, None


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_current_timestamp():
    return int(datetime.datetime.now(datetime.UTC).timestamp())


def get_legacy_state_id(region_id, regions_cache):
    try:
        state_id = regions_cache[region_id]["stateId"]
        state_name = regions_cache[state_id]["regionName"]
        legacy_state_id = regions[state_name]["legacyId"]
        return legacy_state_id
    except KeyError:
        return None


async def check_states(data, cache):
    index = 0
    for old_alert_data in cache:
        new_alert_data = data[index]
        is_new_alert = bool(new_alert_data[0] in [1, 2])
        is_old_alert = bool(old_alert_data[0] in [1, 2])
        is_new_data_set = bool(new_alert_data[1] != 1645674000)
        is_old_data_set = bool(old_alert_data[1] != 1645674000)

        if not is_new_alert and is_old_alert and is_old_data_set:
            now = get_current_timestamp()
            data[index] = [0, now]
        if not is_new_alert and not is_old_alert and not is_new_data_set and is_old_data_set:
            data[index] = [0, old_alert_data[1]]

        index += 1


async def      check_notifications(data, cache):
    index = 0
    for old_data in cache:
        new_data = data[index]

        if new_data < old_data:
            data[index] = old_data

        index += 1


async def store_websocket_data(mc, data, data_websocket, key, key_b):
    if data_websocket != data:
        logger.debug(f"store {key}")
        await mc.set(key_b, json.dumps(data).encode("utf-8"))
        logger.info(f"{key} stored")
    else:
        logger.debug(f"{key} not changed")

async def store_websocket_byte_data(mc, data, data_websocket, key, key_b):
    if data_websocket != data:
        logger.debug(f"store {key}")
        await mc.set(key_b, data)
        logger.info(f"{key} stored")
    else:
        logger.debug(f"{key} not changed")


async def update_alerts_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v1 = await get_cache_data(mc, b"alerts_websocket_v1", [])

            alerts = [0] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id, regions_cache)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    if alert_type in ["AIR"] and region_type in ["State", "District"]:
                        alerts[legacy_state_id - 1] = 1

            if alerts_websocket_v1 != alerts:
                logger.debug("store alerts_websocket_v1")
                await mc.set(b"alerts_websocket_v1", json.dumps(alerts).encode("utf-8"))
                logger.info("alerts_websocket_v1 stored")
            else:
                logger.debug("alerts_websocket_v1 not changed")

        except Exception as e:
            logger.error(f"update_alerts_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_alerts_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v2 = await get_cache_data(mc, b"alerts_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)

            alerts = [[0, 1645674000]] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                if alert["regionType"] not in ["State", "District"]:
                    continue
                state_alert = any(item["regionType"] == "State" for item in alert["activeAlerts"])
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id, regions_cache)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    alert_start_time = active_alert["lastUpdate"]
                    alert_start_time = int(
                        datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp()
                    )
                    old_alert_data = alerts_websocket_v2[legacy_state_id - 1]
                    is_old_state_alert = bool(old_alert_data[0] == 1)
                    if alert_type in ["AIR"]:
                        if region_type == "District" and not state_alert:
                            if is_old_state_alert:
                                alerts[legacy_state_id - 1] = [1, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [1, alert_start_time]
                        if region_type == "State":
                            if is_old_state_alert:
                                alerts[legacy_state_id - 1] = [1, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [1, alert_start_time]

            await check_states(alerts, alerts_websocket_v2)
            await store_websocket_data(mc, alerts, alerts_websocket_v2, "alerts_websocket_v2", b"alerts_websocket_v2")

        except Exception as e:
            logger.error(f"update_alerts_websocket_v2: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_alerts_websocket_v3(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)

            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            regions_cache = await get_regions(mc, b"regions_api", {})
            alerts_websocket_v3 = await get_cache_data(mc, b"alerts_websocket_v3", [[0, 1645674000]] * LEGACY_LED_COUNT)

            alerts = [[0, 1645674000]] * LEGACY_LED_COUNT

            for alert in alerts_cache:
                if alert["regionType"] not in ["State", "District"]:
                    continue
                state_alert = any(item["regionType"] == "State" for item in alert["activeAlerts"])
                for active_alert in alert["activeAlerts"]:
                    region_id = active_alert["regionId"]
                    region_type = active_alert["regionType"]
                    legacy_state_id = get_legacy_state_id(region_id, regions_cache)
                    if not legacy_state_id:
                        continue
                    alert_type = active_alert["type"]
                    alert_start_time = active_alert["lastUpdate"]
                    alert_start_time = int(
                        datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp()
                    )
                    old_alert_data = alerts_websocket_v3[legacy_state_id - 1]
                    is_old_state_alert = bool(old_alert_data[0] == 1)
                    is_old_district_alert = bool(old_alert_data[0] == 2)
                    if alert_type in ["AIR"]:
                        if region_type == "District" and not state_alert:
                            if is_old_district_alert or is_old_state_alert:
                                alerts[legacy_state_id - 1] = [2, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [2, alert_start_time]
                        if region_type == "State":
                            if is_old_district_alert or is_old_state_alert:
                                alerts[legacy_state_id - 1] = [1, old_alert_data[1]]
                            else:
                                alerts[legacy_state_id - 1] = [1, alert_start_time]

            await check_states(alerts, alerts_websocket_v3)
            await store_websocket_data(mc, alerts, alerts_websocket_v3, "alerts_websocket_v3", b"alerts_websocket_v3")
        except Exception as e:
            logger.error(f"update_alerts_websocket_v3: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def ertyvoga_v1(mc, cache_key, data_key, alert_key=None):
    cache = await get_cache_data(mc, cache_key.encode("utf-8"), {"states:{}"})
    websocket = await get_cache_data(mc, data_key.encode("utf-8"), [1645674000] * LEGACY_LED_COUNT)
    if alert_key:
        alerts_websocket = await get_cache_data(mc, alert_key.encode("utf-8"), [[0, 1645674000]] * LEGACY_LED_COUNT)

    data = [0] * LEGACY_LED_COUNT

    for _, state_data in regions.items():
        state_id = state_data["regionId"]
        state_id_str = str(state_id)
        legacy_state_id = state_data["legacyId"]
        if alert_key:
            is_alert = True if alerts_websocket[legacy_state_id - 1][0] == 1 else False
        else:
            is_alert = False
        if state_id_str in cache["states"] and not is_alert:
            alert_start_time = cache["states"][state_id_str]["lastUpdate"]
            alert_start_time = int(datetime.datetime.fromisoformat(alert_start_time.replace("Z", "+00:00")).timestamp())
            if alert_start_time > data[legacy_state_id - 1]:
                data[legacy_state_id - 1] = alert_start_time

    await check_notifications(data, websocket)
    await store_websocket_data(mc, data, websocket, data_key, data_key.encode("utf-8"))


async def update_drones_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "drones_etryvoga", "drones_websocket_v1", "drones_websocket_v2")
            #await ertyvoga_v1(mc, "drones_etryvoga", "drones_websocket_v1")

        except Exception as e:
            logger.error(f"update_drones_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_missiles_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "missiles_etryvoga", "missiles_websocket_v1", "missiles_websocket_v2")
            #await ertyvoga_v1(mc, "missiles_etryvoga", "missiles_websocket_v1")

        except Exception as e:
            logger.error(f"update_missiles_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_explosions_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "explosions_etryvoga", "explosions_websocket_v1")

        except Exception as e:
            logger.error(f"update_explosions_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_kabs_etryvoga_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await ertyvoga_v1(mc, "kabs_etryvoga", "kabs_websocket_v1")

        except Exception as e:
            logger.error(f"update_kabs_etryvoga_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_weather_openweathermap_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            cache = await get_weather(mc, b"weather_openweathermap", {"states": {}, "info": {"last_update": None}})
            websocket = await get_cache_data(mc, b"weather_websocket_v1", [0] * LEGACY_LED_COUNT)

            data = [0] * LEGACY_LED_COUNT

            for _, state_data in regions.items():
                legacy_state_id = state_data["legacyId"]
                state_id = state_data["stateId"]
                state_id_str = str(state_id)
                if state_id_str in cache["states"]:
                    data[legacy_state_id - 1] = int(round(cache["states"][state_id_str]["temp"], 0))

            await store_websocket_data(mc, data, websocket, "weather_websocket_v1", b"weather_websocket_v1")

        except Exception as e:
            logger.error(f"update_weather_openweathermap_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_alerts_historical_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            alerts_historical_cache = await get_historical_alerts(mc, b"alerts_historical_api", [])

            websocket = await get_cache_data(mc, b"alerts_historical_v1", {})

            alerts_data = {
                alert["regionId"]: alert for alert in alerts_cache if alert["regionType"] in ["State", "District"]
            }
            if websocket:
                data = deepcopy(websocket)
            else:
                data = {
                    alert["regionId"]: alert
                    for alert in alerts_historical_cache
                    if alert["regionType"] in ["State", "District"]
                }

            data.update(alerts_data)

            for region_id, region_data in data.items():
                if region_id not in alerts_data and data[region_id]["activeAlerts"] != []:
                    data[region_id]["activeAlerts"] = []
                    data[region_id]["lastUpdate"] = get_current_datetime()

            await store_websocket_data(mc, data, websocket, "alerts_historical_v1", b"alerts_historical_v1")
        except Exception as e:
            logger.error(f"update_alerts_historical: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


def calculate_reason_date(websocket, legacy_state_id):
    old_alert_data = websocket[legacy_state_id - 1]
    is_old_state_alert = bool(old_alert_data[0] == 1)
    is_old_district_alert = bool(old_alert_data[0] == 2)
    now = get_current_timestamp()
    if is_old_district_alert or is_old_state_alert:
        return old_alert_data[1]
    else:
        return now


async def alert_reasons_v1(mc, alert_type, cache_key, default_value):
    reasons_cache = await get_cache_data(mc, b"ws_info")
    reasons = reasons_cache.get("reasons", [])
    websocket_data = await get_cache_data(mc, cache_key, default_value)
    alerts_websocket_data = await get_cache_data(mc, b"alerts_websocket_v1", [0] * LEGACY_LED_COUNT)
    alerts = default_value.copy()

    for reason in reasons:
        state_id = reason["parentRegionId"]
        _, legacy_state_id = convert_region_ids(int(state_id), "stateId", "legacyId")
        if not legacy_state_id:
            continue

        if alert_type in reason["alertTypes"] and alerts_websocket_data[legacy_state_id - 1] == 1:
            alerts[legacy_state_id - 1] = [1, calculate_reason_date(websocket_data, legacy_state_id)]

    await check_states(alerts, websocket_data)
    await store_websocket_data(mc, alerts, websocket_data, cache_key.decode(), cache_key)


async def update_drones_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await alert_reasons_v1(mc, "Drones", b"drones_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)
        except Exception as e:
            logger.error(f"update_drones_websocket_v2: {str(e)}")
            logger.debug("Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_missiles_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await alert_reasons_v1(mc, "Missile", b"missiles_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)
        except Exception as e:
            logger.error(f"update_missiles_websocket_v2: {str(e)}")
            logger.debug("Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_kabs_websocket_v2(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            await alert_reasons_v1(mc, "Ballistic", b"kabs_websocket_v2", [[0, 1645674000]] * LEGACY_LED_COUNT)
        except Exception as e:
            logger.error(f"update_kabs_websocket_v2: {str(e)}")
            logger.debug("Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_energy_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            cache = await get_cache_data(mc, b"energy_ukrenergo", {"states": {}, "info": {"last_update": None}})
            websocket = await get_cache_data(mc, b"energy_websocket_v1", [[0, 1645674000]] * LEGACY_LED_COUNT)

            data = [[0, 1645674000]] * LEGACY_LED_COUNT

            for _, state_data in regions.items():
                legacy_state_id = state_data["legacyId"]
                state_id = state_data["stateId"]
                state_id_str = str(state_id)
                if state_id_str in cache["states"]:
                    old_state = websocket[legacy_state_id - 1][0]
                    old_date = websocket[legacy_state_id - 1][1]
                    new_state = int(cache["states"][state_id_str]["state"]["id"])
                    new_date = get_current_timestamp() if old_state != new_state else old_date
                    data[legacy_state_id - 1] = [new_state, new_date]

            await store_websocket_data(mc, data, websocket, "energy_websocket_v1", b"energy_websocket_v1")
        except Exception as e:
            logger.error(f"update_alerts_historical: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_radiation_websocket_v1(mc, run_once=False):
    while True:
        try:
            data_cache = await get_cache_data(
                mc, b"radiation_data_saveecobot", {"states": {}, "info": {"last_update": None}}
            )
            sensors_cache = await get_cache_data(
                mc, b"radiation_sensors_saveecobot", {"states": {}, "info": {"last_update": None}}
            )
            websocket = await get_cache_data(mc, b"radiation_websocket_v1", [0] * LEGACY_LED_COUNT)

            data = [0] * LEGACY_LED_COUNT

            temp_data = {}
            for sensor_data in data_cache["states"]:
                if sensor_data["is_old"]:
                    continue
                state_name = sensors_cache["states"].get(str(sensor_data["sensor_id"]), {}).get("region_name")
                if not state_name:
                    continue
                if not temp_data.get(state_name):
                    temp_data[state_name] = []
                temp_data[state_name].append(sensor_data["gamma_nsv_h"])

            for state_name, state_data in regions.items():
                legacy_state_id = state_data["legacyId"]
                state_radiation_data = temp_data.get(state_name, [])
                if state_radiation_data:
                    data[legacy_state_id - 1] = round(sum(state_radiation_data) / len(state_radiation_data))

            await store_websocket_data(mc, data, websocket, "radiation_websocket_v1", b"radiation_websocket_v1")
            await asyncio.sleep(update_period_long)
        except Exception as e:
            logger.error(f"update_radiation_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def update_global_notifications_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            cache = await get_cache_data(mc, b"ws_alerts", {})
            websocket = await get_cache_data(mc, b"notifications_websocket_v1", {})
            notifications = cache.get("mapNotifications", {})
            data = {
                "mig": 1 if notifications.get("hasMig") else 0,
                "ships": 1 if notifications.get("hasBoats") else 0,
                "tactical": 1 if notifications.get("hasTacticalAviation") else 0,
                "strategic": 1 if notifications.get("hasStrategicAviation") else 0,
                "ballistic_missiles": 1 if notifications.get("hasBallistics") else 0,
                "mig_missiles": 1 if notifications.get("migRockets") else 0,
                "ships_missiles": 1 if notifications.get("boatsRockets") else 0,
                "tactical_missiles": 1 if notifications.get("tacticalAviationRockets") else 0,
                "strategic_missiles": 1 if notifications.get("strategicAviationRockets") else 0,
            }
            await store_websocket_data(mc, data, websocket, "notifications_websocket_v1", b"notifications_websocket_v1")
        except Exception as e:
            logger.error(f"update_notifications_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

def update_alerts_batch_state(old_state: dict[str, int], new_state: dict[str, int]):
    """
    Оновлює стан alerts_batch_state, повертає діф (region_ids, де flags16 змінився).
    """
    diff_region_ids = []
    for region_id, flags16 in new_state.items():
        prev_flags = old_state.get(region_id)
        if prev_flags != flags16:
            diff_region_ids.append(region_id)
    return diff_region_ids

def make_alert_batch(diff_region_ids: list[int], new_state: dict[int,int]) -> bytes:
    """
    Формат пакета:
    - region_id: 2 байти (unsigned short)
    - flags16: 2 байти (unsigned short)

    body: послідовність пар (region_id, flags16) для кожного регіону
    diff_region_ids: список регіонів з змінами(наприклад, [0, 1, 2, ...])
    new_state: повний словник даних тривог, де ключ — region_id, а значення — flags16 (наприклад, {0: 3, 1: 1, ...})
    """
    body = bytearray()
    for rid in diff_region_ids:
        flags16 = new_state.get(rid, 0)
        body += struct.pack('<H H', int(rid), flags16)
    return body

async def update_alerts_fusion_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            data = {}
            alerts_cache = await get_alerts(mc, b"alerts_api", [])
            reasons_cache = await get_cache_data(mc, b"ws_info")
            reasons = reasons_cache.get("reasons", [])
            websocket = await get_cache_data(mc, b"alerts_fusion_websocket_v1", {})
            for alert in alerts_cache:
                for active_alert in alert["activeAlerts"]:
                    regionId = active_alert["regionId"]
                    if regionId not in data:
                        data[regionId] = 0
                    if active_alert["type"] == "AIR":
                        data[regionId] |= (1 << 0) 
                    if active_alert["type"] == "ARTILLERY":
                        data[regionId] |= (1 << 1) 
                    if active_alert["type"] == "URBAN_FIGHTS":
                        data[regionId] |= (1 << 2) 
                    if active_alert["type"] == "CHEMICAL":
                        data[regionId] |= (1 << 3) 
                    if active_alert["type"] == "NUCLEAR":
                        data[regionId] |= (1 << 4)
            for reason_alert in reasons:
                regionId = reason_alert["regionId"]
                if regionId not in data:
                    data[regionId] = 0
                for alert_type in reason_alert["alertTypes"]:
                    if alert_type == "Drones":
                        data[regionId] |= (1 << 5) 
                    if alert_type == "Missile":
                        data[regionId] |= (1 << 6) 
                    if alert_type == "Ballistic": # це насправді "Kabs"
                        data[regionId] |= (1 << 7) 
            await store_websocket_data(mc, data, websocket, "alerts_fusion_websocket_v1", b"alerts_fusion_websocket_v1")
            
        except Exception as e:
            logger.error(f"update_alerts_fusion_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_etryvoga_fusion_websocket_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            alerts_cache = await get_cache_data(mc, b"etryvoga_full")
            websocket = await get_cache_data(mc, b"etryvoga_fusion_websocket_v1", {})
            last_processed_id = await get_cache_data(mc, b"etryvoga_last_processed_id", 0)
            first_processed_id = None

            data = {}

            for alert in alerts_cache:
                alert_id = int(alert["id"])
                
                if first_processed_id is None:
                    first_processed_id = alert_id
                if alert_id <= last_processed_id:
                    continue

                regionId = alert["regionId"]
                if regionId not in data:
                    data[regionId] = 0

                if alert["type"] == "DRONE":
                    data[regionId] |= (1 << 5) 
                elif alert["type"] == "ROCKET":
                    data[regionId] |= (1 << 6) 
                elif alert["type"] == "KAB":
                    data[regionId] |= (1 << 7) 
                elif alert["type"] == "EXPLOSION":
                    data[regionId] |= (1 << 9) 
                elif alert["type"] == "RECON_DRONE":
                    data[regionId] |= (1 << 5)
                
                if data[regionId] == 0:
                    del data[regionId]
            if not data:
                logger.debug("update_etryvoga_fusion_websocket_v1: No new data to process")
                continue
            logger.debug(f" DATA: {str(data)}")
            await store_websocket_data(mc, data, websocket, "etryvoga_fusion_websocket_v1", b"etryvoga_fusion_websocket_v1")
            await store_websocket_data(mc, first_processed_id, last_processed_id, "etryvoga_last_processed_id", b"etryvoga_last_processed_id")


        except Exception as e:
            logger.error(f"update_etryvoga_fusion_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break


async def main():
    mc = Client(memcached_host, 11211)
    try:
        await asyncio.gather(
            update_alerts_websocket_v1(mc),
            update_alerts_websocket_v2(mc),
            update_alerts_websocket_v3(mc),
            update_drones_etryvoga_v1(mc),
            update_missiles_etryvoga_v1(mc),
            update_explosions_etryvoga_v1(mc),
            update_kabs_etryvoga_v1(mc),
            update_weather_openweathermap_v1(mc),
            update_alerts_historical_v1(mc),
            update_drones_websocket_v2(mc),
            update_missiles_websocket_v2(mc),
            update_kabs_websocket_v2(mc),
            update_energy_websocket_v1(mc),
            update_radiation_websocket_v1(mc),
            update_global_notifications_v1(mc),
            update_alerts_fusion_websocket_v1(mc),
            update_etryvoga_fusion_websocket_v1(mc),
        )
        
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
