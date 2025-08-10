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
  "ALL"                        : { "name": "Вся Україна"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "IVANOFRANKIWSKA"            : { "name": "Івано-Франківська область"        , "regionId":   13, "legacyId":  2, "stateId":   13 },
  "IVANO-FRANKIVSKYI-DSTR"     : { "name": "Івано-Франківський район"         , "regionId":   68, "legacyId":  2, "stateId":   13 },
  "IVANO-FRANKIVSK-CITY"       : { "name": "Івано-Франківськ"                 , "regionId":  632, "legacyId":  2, "stateId":   13 },
  "VERKHOVYNSKYI-DSTR"         : { "name": "Верховинський район"              , "regionId":   67, "legacyId":  2, "stateId":   13 },
  "VERKHOVYNA-CITY"            : { "name": "Верховина"                        , "regionId":   67, "legacyId":  2, "stateId":   13 },
  "KALUSKYI-DSTR"              : { "name": "Калуський район"                  , "regionId":   71, "legacyId":  2, "stateId":   13 },
  "KALUSH"                     : { "name": "Калуш"                            , "regionId":   71, "legacyId":  2, "stateId":   13 },
  "KOLOMYISKYI-DSTR"           : { "name": "Коломийський район"               , "regionId":   70, "legacyId":  2, "stateId":   13 },
  "KOLOMYIA-CITY"              : { "name": "Коломия"                          , "regionId":   70, "legacyId":  2, "stateId":   13 },
  "KOSIVSKYI-DSTR"             : { "name": "Косівський район"                 , "regionId":   69, "legacyId":  2, "stateId":   13 },
  "KOSIV-CITY"                 : { "name": "Косів"                            , "regionId":   69, "legacyId":  2, "stateId":   13 },
  "NADVIRNIANSKYI-DSTR"        : { "name": "Надвірнянський район"             , "regionId":   72, "legacyId":  2, "stateId":   13 },
  "NADVIRNA-CITY"              : { "name": "Надвірна"                         , "regionId":   72, "legacyId":  2, "stateId":   13 },
  "VOLYNSKA"                   : { "name": "Волинська область"                , "regionId":    8, "legacyId":  5, "stateId":    8 },
  "VOLODIMIR-VOLINSKYI-DSTR"   : { "name": "Володимир-Волинський район"       , "regionId":   38, "legacyId":  5, "stateId":    8 },
  "NOVOVOLYNSK-CITY"           : { "name": "Нововолинськ"                     , "regionId":   38, "legacyId":  5, "stateId":    8 },
  "KAMIN-KASHIRSKYI-DSTR"      : { "name": "Камінь-Каширський район"          , "regionId":   41, "legacyId":  5, "stateId":    8 },
  "KAMIN-KASHIRSKIJ-CITY"      : { "name": "Камінь-Каширський"                , "regionId":   41, "legacyId":  5, "stateId":    8 },
  "KOVELSKYI-DSTR"             : { "name": "Ковельський район"                , "regionId":   40, "legacyId":  5, "stateId":    8 },
  "KOVEL-CITY"                 : { "name": "Ковель"                           , "regionId":   40, "legacyId":  5, "stateId":    8 },
  "LUCKYI-DSTR"                : { "name": "Луцький район"                    , "regionId":   39, "legacyId":  5, "stateId":    8 },
  "LUTSK-CITY"                 : { "name": "Луцьк"                            , "regionId":  225, "legacyId":  5, "stateId":    8 },
  "VINNYTSA"                   : { "name": "Вінницька область"                , "regionId":    4, "legacyId": 23, "stateId":    4 },
  "VINNYTSKYI-DSTR"            : { "name": "Вінницький район"                 , "regionId":   36, "legacyId": 23, "stateId":    4 },
  "VINNYTSIA-CITY"             : { "name": "Вінниця"                          , "regionId":  155, "legacyId": 23, "stateId":    4 },
  "HAISYNSKYI-DSTR"            : { "name": "Гайсинський район"                , "regionId":   37, "legacyId": 23, "stateId":    4 },
  "HAISYN-CITY"                : { "name": "Гайсин"                           , "regionId":   37, "legacyId": 23, "stateId":    4 },
  "ZHMERYNSKYI-DSTR"           : { "name": "Жмеринський район"                , "regionId":   35, "legacyId": 23, "stateId":    4 },
  "ZHMERYNKA-CITY"             : { "name": "Жмеринка"                         , "regionId":   35, "legacyId": 23, "stateId":    4 },
  "MOHYLIV-PODILSKYI-DSTR"     : { "name": "Могилів-Подільський район"        , "regionId":   33, "legacyId": 23, "stateId":    4 },
  "MOHYLIV-PODILSKYI-CITY"     : { "name": "Могилів-Подільський"              , "regionId":   33, "legacyId": 23, "stateId":    4 },
  "TULCHYNSKYI-DSTR"           : { "name": "Тульчинський район"               , "regionId":   32, "legacyId": 23, "stateId":    4 },
  "TULCHYN-CITY"               : { "name": "Тульчин"                          , "regionId":   32, "legacyId": 23, "stateId":    4 },
  "KHMILNYTSKYI-DSTR"          : { "name": "Хмільницький район"               , "regionId":   34, "legacyId": 23, "stateId":    4 },
  "HMILNIK-CITY"               : { "name": "Хмільник"                         , "regionId":   34, "legacyId": 23, "stateId":    4 },
  "DNIPROPETROVSKAYA"          : { "name": "Дніпропетровська область"         , "regionId":    9, "legacyId": 19, "stateId":    9 },
  "DNIPROVSKYI-DSTR"           : { "name": "Дніпровський район"               , "regionId":   44, "legacyId": 19, "stateId":    9 },
  "DNIPRO-CITY"                : { "name": "Дніпро"                           , "regionId":  332, "legacyId": 19, "stateId":    9 },
  "KAMIANSKYI-DSTR"            : { "name": "Кам'янський район"                , "regionId":   42, "legacyId": 19, "stateId":    9 },
  "VERHIVCEVE-CITY"            : { "name": "Верхівцеве"                       , "regionId":   42, "legacyId": 19, "stateId":    9 },
  "VILNOGIRSK-CITY"            : { "name": "Вільногірськ"                     , "regionId":   42, "legacyId": 19, "stateId":    9 },
  "KAMIANSKE-CITY"             : { "name": "Кам'янське"                       , "regionId":   42, "legacyId": 19, "stateId":    9 },
  "KRYVORIZKYI-DSTR"           : { "name": "Криворізький район"               , "regionId":   46, "legacyId": 19, "stateId":    9 },
  "APOSTOLOVE-CITY"            : { "name": "Апостолове"                       , "regionId":   46, "legacyId": 19, "stateId":    9 },
  "VELIKA-KOSTROMKA-CITY"      : { "name": "Велика Долина"                    , "regionId":   46, "legacyId": 19, "stateId":    9 },
  "ZELENODOLSK-CITY"           : { "name": "Зеленодольськ"                    , "regionId":   46, "legacyId": 19, "stateId":    9 },
  "KRYVYOI-RIH-CITY"           : { "name": "Кривий Ріг"                       , "regionId":   46, "legacyId": 19, "stateId":    9 },
  "MAR-YANSKE-CITY"            : { "name": "Мар'янське"                       , "regionId":   46, "legacyId": 19, "stateId":    9 },
  "NIKOPOLSKYI-DSTR"           : { "name": "Нікопольський район"              , "regionId":   47, "legacyId": 19, "stateId":    9 },
  "MARHANETS-CITY"             : { "name": "Марганець"                        , "regionId":   47, "legacyId": 19, "stateId":    9 },
  "NIKOPOL-CITY"               : { "name": "Нікополь"                         , "regionId":   47, "legacyId": 19, "stateId":    9 },
  "POKROV-CITY"                : { "name": "Покров"                           , "regionId":   47, "legacyId": 19, "stateId":    9 },
  "PAVLOHRADSKYI-DSTR"         : { "name": "Павлоградський район"             , "regionId":   45, "legacyId": 19, "stateId":    9 },
  "PAVLOHRAD-CITY"             : { "name": "Павлоград"                        , "regionId":   45, "legacyId": 19, "stateId":    9 },
  "NOVOMOSKOVSKYI-DSTR"        : { "name": "Новомосковський район"            , "regionId":   43, "legacyId": 19, "stateId":    9 },
  "NOVOMOSKOVSK-CITY"          : { "name": "Самар"                            , "regionId":   43, "legacyId": 19, "stateId":    9 },
  "SYNELNYKIVSKYI-DSTR"        : { "name": "Синельниківський район"           , "regionId":   48, "legacyId": 19, "stateId":    9 },
  "MEZHOVA-CITY"               : { "name": "Межова"                           , "regionId":   48, "legacyId": 19, "stateId":    9 },
  "NOVOPAVLIVKA-CITY"          : { "name": "Новопавлівка"                     , "regionId":   48, "legacyId": 19, "stateId":    9 },
  "POKROVSKE"                  : { "name": "Покровське"                       , "regionId":   48, "legacyId": 19, "stateId":    9 },
  "SINELNIKOVO-CITY"           : { "name": "Синельникове"                     , "regionId":   48, "legacyId": 19, "stateId":    9 },
  "PERSHOTRAVNENSK-CITY"       : { "name": "Шахтарське"                       , "regionId":   48, "legacyId": 19, "stateId":    9 },
  "DONETSKAYA"                 : { "name": "Донецька область"                 , "regionId":   28, "legacyId": 13, "stateId":   28 },
  "BAKHMUTSKYI-DSTR"           : { "name": "Бахмутський район"                , "regionId":   54, "legacyId": 13, "stateId":   28 },
  "BAKHMUT-CITY"               : { "name": "Бахмут"                           , "regionId":   54, "legacyId": 13, "stateId":   28 },
  "SVITLODARSK-CITY"           : { "name": "Світлодарськ"                     , "regionId":   54, "legacyId": 13, "stateId":   28 },
  "SOLEDAR-CITY"               : { "name": "Соледар"                          , "regionId":   54, "legacyId": 13, "stateId":   28 },
  "TORECK-CITY"                : { "name": "Торецьк"                          , "regionId":   54, "legacyId": 13, "stateId":   28 },
  "CHASIV-YAR-CITY"            : { "name": "Часів Яр"                         , "regionId":   54, "legacyId": 13, "stateId":   28 },
  "VOLNOVASKYI-DSTR"           : { "name": "Волноваський район"               , "regionId":   55, "legacyId": 13, "stateId":   28 },
  "VELIKA-NOVOSILKA-CITY"      : { "name": "Велика Новосілка"                 , "regionId":   55, "legacyId": 13, "stateId":   28 },
  "VUGLEDAR-CITY"              : { "name": "Вугледар"                         , "regionId":   55, "legacyId": 13, "stateId":   28 },
  "HORLIVSKYI-DSTR"            : { "name": "Горлівський район"                , "regionId":   51, "legacyId": 13, "stateId":   28 },
  "IENAKIIEVE-CITY"            : { "name": "Єнакієве"                         , "regionId":   51, "legacyId": 13, "stateId":   28 },
  "HORLIVKA-CITY"              : { "name": "Горлівка"                         , "regionId":   51, "legacyId": 13, "stateId":   28 },
  "SNIZHNE-CITY"               : { "name": "Сніжне"                           , "regionId":   51, "legacyId": 13, "stateId":   28 },
  "CHYSTIAKOVE-CITY"           : { "name": "Чистякове"                        , "regionId":   51, "legacyId": 13, "stateId":   28 },
  "SHAKHTARSK-CITY"            : { "name": "Шахтарськ"                        , "regionId":   51, "legacyId": 13, "stateId":   28 },
  "DONETSKYI-DSTR"             : { "name": "Донецький район"                  , "regionId":   53, "legacyId": 13, "stateId":   28 },
  "DONETSK-CITY"               : { "name": "Донецьк"                          , "regionId":   53, "legacyId": 13, "stateId":   28 },
  "MAKIIVKA-CITY"              : { "name": "Макіївка"                         , "regionId":   53, "legacyId": 13, "stateId":   28 },
  "KHARTSYZK-CITY"             : { "name": "Харцизьк"                         , "regionId":   53, "legacyId": 13, "stateId":   28 },
  "KALMIUSKYI-DSTR"            : { "name": "Кальміуський район"               , "regionId":   49, "legacyId": 13, "stateId":   28 },
  "KALMIUSKE-CITY"             : { "name": "Кальміуське"                      , "regionId":   49, "legacyId": 13, "stateId":   28 },
  "KRAMATORSKYI-DSTR"          : { "name": "Краматорський район"              , "regionId":   50, "legacyId": 13, "stateId":   28 },
  "DRUZHKIVKA-CITY"            : { "name": "Дружківка"                        , "regionId":   50, "legacyId": 13, "stateId":   28 },
  "KOSTIANTYNIVKA-CITY"        : { "name": "Костянтинівка"                    , "regionId":   50, "legacyId": 13, "stateId":   28 },
  "KRAMATORSK-CITY"            : { "name": "Краматорськ"                      , "regionId":   50, "legacyId": 13, "stateId":   28 },
  "LIMAN-CITY"                 : { "name": "Лиман"                            , "regionId":   50, "legacyId": 13, "stateId":   28 },
  "SVYATOGIRSK-CITY"           : { "name": "Святогірськ"                      , "regionId":   50, "legacyId": 13, "stateId":   28 },
  "SLOVIANSK-CITY"             : { "name": "Слов'янськ"                       , "regionId":   50, "legacyId": 13, "stateId":   28 },
  "MARIUPOLSKYI-DSTR"          : { "name": "Маріупольський район"             , "regionId":   52, "legacyId": 13, "stateId":   28 },
  "MARIUPOL-CITY"              : { "name": "Маріуполь"                        , "regionId":   52, "legacyId": 13, "stateId":   28 },
  "POKROVSKYI-DSTR"            : { "name": "Покровський район"                , "regionId":   56, "legacyId": 13, "stateId":   28 },
  "AVDIYIVKA-CITY"             : { "name": "Авдіївка"                         , "regionId":   56, "legacyId": 13, "stateId":   28 },
  "DOBROPILLYA-CITY"           : { "name": "Добропілля"                       , "regionId":   56, "legacyId": 13, "stateId":   28 },
  "KURAHOVE-CITY"              : { "name": "Курахове"                         , "regionId":   56, "legacyId": 13, "stateId":   28 },
  "MAR-YINKA-CITY"             : { "name": "Мар'їнка"                         , "regionId":   56, "legacyId": 13, "stateId":   28 },
  "MYRNOHRAD-CITY"             : { "name": "Мирноград"                        , "regionId":   56, "legacyId": 13, "stateId":   28 },
  "POKROVSK-CITY"              : { "name": "Покровськ"                        , "regionId":   56, "legacyId": 13, "stateId":   28 },
  "ZHYTOMYRSKA"                : { "name": "Житомирська область"              , "regionId":   10, "legacyId":  7, "stateId":   10 },
  "BERDYCHIVSKYI-DSTR"         : { "name": "Бердичівський район"              , "regionId":   57, "legacyId":  7, "stateId":   10 },
  "BERDYCHIV-CITY"             : { "name": "Бердичів"                         , "regionId":   57, "legacyId":  7, "stateId":   10 },
  "ZHYTOMYRSKYI-DSTR"          : { "name": "Житомирський район"               , "regionId":   59, "legacyId":  7, "stateId":   10 },
  "ZHYTOMYR-CITY"              : { "name": "Житомир"                          , "regionId":  442, "legacyId":  7, "stateId":   10 },
  "RADOMISHL-CITY"             : { "name": "Радомишль"                        , "regionId":   59, "legacyId":  7, "stateId":   10 },
  "NOVOHRAD-VOLYNSKYI-DSTR"    : { "name": "Звягельський район"               , "regionId":   60, "legacyId":  7, "stateId":   10 },
  "NOVOHRAD-VOLYNSKYOI-CITY"   : { "name": "Звягель"                          , "regionId":   60, "legacyId":  7, "stateId":   10 },
  "KOROSTENSKYI-DSTR"          : { "name": "Коростенський район"              , "regionId":   58, "legacyId":  7, "stateId":   10 },
  "KOROSTEN-CITY"              : { "name": "Коростень"                        , "regionId":   58, "legacyId":  7, "stateId":   10 },
  "OVRUCK-CITY"                : { "name": "Овруч"                            , "regionId":   58, "legacyId":  7, "stateId":   10 },
  "ZAKARPATSKA"                : { "name": "Закарпатська область"             , "regionId":   11, "legacyId":  1, "stateId":   11 },
  "BEREHIVSKYI-DSTR"           : { "name": "Берегівський район"               , "regionId":   61, "legacyId":  1, "stateId":   11 },
  "BEREHOVE-CITY"              : { "name": "Берегове"                         , "regionId":   61, "legacyId":  1, "stateId":   11 },
  "MUKACHIVSKYI-DSTR"          : { "name": "Мукачівський район"               , "regionId":   65, "legacyId":  1, "stateId":   11 },
  "MUKACHEVO-CITY"             : { "name": "Мукачево"                         , "regionId":   65, "legacyId":  1, "stateId":   11 },
  "RAKHIVSKYI-DSTR"            : { "name": "Рахівський район"                 , "regionId":   63, "legacyId":  1, "stateId":   11 },
  "RAKHIV-CITY"                : { "name": "Рахів"                            , "regionId":   63, "legacyId":  1, "stateId":   11 },
  "TIACHIVSKYI-DSTR"           : { "name": "Тячівський район"                 , "regionId":   64, "legacyId":  1, "stateId":   11 },
  "TIACHIV-CITY"               : { "name": "Тячів"                            , "regionId":   64, "legacyId":  1, "stateId":   11 },
  "UZHHORODSKYI-DSTR"          : { "name": "Ужгородський район"               , "regionId":   66, "legacyId":  1, "stateId":   11 },
  "UZHHOROD-CITY"              : { "name": "Ужгород"                          , "regionId":  500, "legacyId":  1, "stateId":   11 },
  "KHUSTSKYI-DSTR"             : { "name": "Хустський район"                  , "regionId":   62, "legacyId":  1, "stateId":   11 },
  "KHUST-CITY"                 : { "name": "Хуст"                             , "regionId":   62, "legacyId":  1, "stateId":   11 },
  "ZAPORIZKA"                  : { "name": "Запорізька область"               , "regionId":   12, "legacyId": 14, "stateId":   12 },
  "BERDIANSKYI-DSTR"           : { "name": "Бердянський район"                , "regionId":  147, "legacyId": 14, "stateId":   12 },
  "BERDIANSK-CITY"             : { "name": "Бердянськ"                        , "regionId":  147, "legacyId": 14, "stateId":   12 },
  "VASYLIVSKYI-DSTR"           : { "name": "Василівський район"               , "regionId":  146, "legacyId": 14, "stateId":   12 },
  "ENERHODAR-CITY"             : { "name": "Енергодар"                        , "regionId":  146, "legacyId": 14, "stateId":   12 },
  "ZAPORIZKYI-DSTR"            : { "name": "Запорізький район"                , "regionId":  149, "legacyId": 14, "stateId":   12 },
  "BILENKE-CITY"               : { "name": "Біленьке"                         , "regionId":  149, "legacyId": 14, "stateId":   12 },
  "VILNIANSK-CITY"             : { "name": "Вільнянськ"                       , "regionId":  149, "legacyId": 14, "stateId":   12 },
  "ZAPORIZHZHIA-CITY"          : { "name": "Запоріжжя"                        , "regionId":  564, "legacyId": 14, "stateId":   12 },
  "KOMISHUVAHA-CITY"           : { "name": "Комишуваха"                       , "regionId":  149, "legacyId": 14, "stateId":   12 },
  "TAVRIISKE-CITY"             : { "name": "Таврійське"                       , "regionId":  149, "legacyId": 14, "stateId":   12 },
  "MELITOPOLSKYI-DSTR"         : { "name": "Мелітопольський район"            , "regionId":  148, "legacyId": 14, "stateId":   12 },
  "MELITOPOL-CITY"             : { "name": "Мелітополь"                       , "regionId":  148, "legacyId": 14, "stateId":   12 },
  "POLOHIVSKYI-DSTR"           : { "name": "Пологівський район"               , "regionId":  145, "legacyId": 14, "stateId":   12 },
  "GULYAJPOLE-CITY"            : { "name": "Гуляйполе"                        , "regionId":  145, "legacyId": 14, "stateId":   12 },
  "KAM-YANKA-CITY"             : { "name": "Кам'янка"                         , "regionId":  145, "legacyId": 14, "stateId":   12 },
  "ORIHIV-CITY"                : { "name": "Оріхів"                           , "regionId":  145, "legacyId": 14, "stateId":   12 },
  "POLOGI-CITY"                : { "name": "Пологи"                           , "regionId":  145, "legacyId": 14, "stateId":   12 },
  "TOKMAK-CITY"                : { "name": "Токмак"                           , "regionId":  145, "legacyId": 14, "stateId":   12 },
  "KIYEW"                      : { "name": "Київ"                             , "regionId":   31, "legacyId": 26, "stateId":   31 },
  "KIYEWSKAYA"                 : { "name": "Київська область"                 , "regionId":   14, "legacyId":  8, "stateId":   14 },
  "BORYSPILSKYI-DSTR"          : { "name": "Бориспільський район"             , "regionId":   78, "legacyId":  8, "stateId":   14 },
  "BORYSPIL-CITY"              : { "name": "Бориспіль"                        , "regionId":   78, "legacyId":  8, "stateId":   14 },
  "PEREYASLAV-CITY"            : { "name": "Переяслав"                        , "regionId":   78, "legacyId":  8, "stateId":   14 },
  "YAGOTIN-CITY"               : { "name": "Яготин"                           , "regionId":   78, "legacyId":  8, "stateId":   14 },
  "BROVARSKYI-DSTR"            : { "name": "Броварський район"                , "regionId":   79, "legacyId":  8, "stateId":   14 },
  "BROVARY-CITY"               : { "name": "Бровари"                          , "regionId":   79, "legacyId":  8, "stateId":   14 },
  "ZGURIVKA-CITY"              : { "name": "Згурівка"                         , "regionId":   79, "legacyId":  8, "stateId":   14 },
  "SEMIPOLKI-CITY"             : { "name": "Семиполки"                        , "regionId":   79, "legacyId":  8, "stateId":   14 },
  "BUCHANSKYI-DSTR"            : { "name": "Бучанський район"                 , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "IRPIN-CITY"                 : { "name": "Ірпінь"                           , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "BORODYANKA-CITY"            : { "name": "Бородянка"                        , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "BUCHA-CITY"                 : { "name": "Буча"                             , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "BILOGORODKA-CITY"           : { "name": "Білогородка"                      , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "VISHNEVE-CITY"              : { "name": "Вишневе"                          , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "GOSTOMEL-CITY"              : { "name": "Гостомель"                        , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "MAKARIV-CITY"               : { "name": "Макарів"                          , "regionId":   75, "legacyId":  8, "stateId":   14 },
  "BILOTSERKIVSKYI-DSTR"       : { "name": "Білоцерківський район"            , "regionId":   73, "legacyId":  8, "stateId":   14 },
  "BILA-TSERKVA-CITY"          : { "name": "Біла Церква"                      , "regionId":   73, "legacyId":  8, "stateId":   14 },
  "SKVIRA-CITY"                : { "name": "Сквира"                           , "regionId":   73, "legacyId":  8, "stateId":   14 },
  "UZIN-CITY"                  : { "name": "Узин"                             , "regionId":   73, "legacyId":  8, "stateId":   14 },
  "VYSHHORODSKYI-DSTR"         : { "name": "Вишгородський район"              , "regionId":   74, "legacyId":  8, "stateId":   14 },
  "VISHGOROD-CITY"             : { "name": "Вишгород"                         , "regionId":   74, "legacyId":  8, "stateId":   14 },
  "SLAVUTICH-CITY"             : { "name": "Славутич"                         , "regionId":   74, "legacyId":  8, "stateId":   14 },
  "OBUKHIVSKYI-DSTR"           : { "name": "Обухівський район"                , "regionId":   76, "legacyId":  8, "stateId":   14 },
  "BOHUSLAV-CITY"              : { "name": "Богуслав"                         , "regionId":   76, "legacyId":  8, "stateId":   14 },
  "VASYLKIV-CITY"              : { "name": "Васильків"                        , "regionId":   76, "legacyId":  8, "stateId":   14 },
  "KAGARLIK-CITY"              : { "name": "Кагарлик"                         , "regionId":   76, "legacyId":  8, "stateId":   14 },
  "MIRONIVKA-CITY"             : { "name": "Миронівка"                        , "regionId":   76, "legacyId":  8, "stateId":   14 },
  "OBUHIV-CITY"                : { "name": "Обухів"                           , "regionId":   76, "legacyId":  8, "stateId":   14 },
  "FASTIVSKYI-DSTR"            : { "name": "Фастівський район"                , "regionId":   77, "legacyId":  8, "stateId":   14 },
  "BOIARKA-CITY"               : { "name": "Боярка"                           , "regionId":   77, "legacyId":  8, "stateId":   14 },
  "FASTIV-CITY"                : { "name": "Фастів"                           , "regionId":   77, "legacyId":  8, "stateId":   14 },
  "KRIMEA"                     : { "name": "Автономна Республіка Крим"        , "regionId": 9999, "legacyId": 16, "stateId": 9999 },
  "YEVPATORIISKYI-DSTR"        : { "name": "Євпаторійський район"             , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "YEVPATORIIA-CITY"           : { "name": "Євпаторія"                        , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "BAKHCHYSARAISKYI-DSTR"      : { "name": "Бахчисарайський район"            , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "BAKHCHYSARAI-CITY"          : { "name": "Бахчисарай"                       , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "BILOHIRSKYI-DSTR"           : { "name": "Білогірський район"               , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "BILOHIRSK-CITY"             : { "name": "Білогірськ"                       , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "DZHANKOISKYI-DSTR"          : { "name": "Джанкойський район"               , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "DZHANKOJ-CITY"              : { "name": "Джанкой"                          , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "KERCHENSKYI-DSTR"           : { "name": "Керченський район"                , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "KERCH-CITY"                 : { "name": "Керч"                             , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "SEVASTOPOL-CITY"            : { "name": "Севастополь"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "KURMANSKYI-DSTR"            : { "name": "Курманський район"                , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "KURMAN-CITY"                : { "name": "Курман"                           , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "PEREKOPSKYI-DSTR"           : { "name": "Перекопський район"               , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "YANY-KAPU-CITY"             : { "name": "Яни Капу"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "SIMFEROPOLSKYI-DSTR"        : { "name": "Сімферопольський район"           , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "SIMFEROPOL-CITY"            : { "name": "Сімферополь"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "FEODOSIISKYI-DSTR"          : { "name": "Феодосійський район"              , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "FEODOSIIA-CITY"             : { "name": "Феодосія"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "YALTYNSKYI-DSTR"            : { "name": "Ялтинський район"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "YALTA-CITY"                 : { "name": "Ялта"                             , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "KIROWOGRADSKA"              : { "name": "Кіровоградська область"           , "regionId":   15, "legacyId": 22, "stateId":   15 },
  "HOLOVANIVSKYI-DSTR"         : { "name": "Голованівський район"             , "regionId":   82, "legacyId": 22, "stateId":   15 },
  "GOLOVANIVSK-CITY"           : { "name": "Голованівськ"                     , "regionId":   82, "legacyId": 22, "stateId":   15 },
  "KROPYVNYTSKYI-DSTR"         : { "name": "Кропивницький район"              , "regionId":   81, "legacyId": 22, "stateId":   15 },
  "KROPYVNYTSKYOI-CITY"        : { "name": "Кропивницький"                    , "regionId":  761, "legacyId": 22, "stateId":   15 },
  "NOVOUKRAINSKYI-DSTR"        : { "name": "Новоукраїнський район"            , "regionId":   83, "legacyId": 22, "stateId":   15 },
  "NOVOUKRAYINSK-CITY"         : { "name": "Новоукраїнка"                     , "regionId":   83, "legacyId": 22, "stateId":   15 },
  "OLEKSANDRIISKYI-DSTR"       : { "name": "Олександрійський район"           , "regionId":   80, "legacyId": 22, "stateId":   15 },
  "OLEKSANDRIIA-CITY"          : { "name": "Олександрія"                      , "regionId":   80, "legacyId": 22, "stateId":   15 },
  "SVITLOVODSK-CITY"           : { "name": "Світловодськ"                     , "regionId":   80, "legacyId": 22, "stateId":   15 },
  "LUGANSKA"                   : { "name": "Луганська область"                , "regionId":   16, "legacyId": 12, "stateId":   16 },
  "ALCHEVSKYI-DSTR"            : { "name": "Алчевський район"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "ALCHEVSK-CITY"              : { "name": "Алчевськ"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "BRIANKA-CITY"               : { "name": "Брянка"                           , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "KADIIVKA-CITY"              : { "name": "Кадіївка"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "DOVZHANSKYI-DSTR"           : { "name": "Довжанський район"                , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "DOVZHANSK-CITY"             : { "name": "Довжанськ"                        , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "LUHANSKYI-DSTR"             : { "name": "Луганський район"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "LUHANSK-CITY"               : { "name": "Луганськ"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "ROVENKIVSKYI-DSTR"          : { "name": "Ровеньківський район"             , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "ANTRATSYT-CITY"             : { "name": "Антрацит"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "ROVENKY-CITY"               : { "name": "Ровеньки"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "KHRUSTALNYOI-CITY"          : { "name": "Хрустальний"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "SVATIVSKYI-DSTR"            : { "name": "Сватівський район"                , "regionId":   85, "legacyId": 12, "stateId":   16 },
  "RUBIZHNE-CITY"              : { "name": "Рубіжне"                          , "regionId":   84, "legacyId": 12, "stateId":   16 },
  "STAROBILSKYI-DSTR"          : { "name": "Старобільський район"             , "regionId":   86, "legacyId": 12, "stateId":   16 },
  "STAROBILSK-CITY"            : { "name": "Старобільськ"                     , "regionId":   86, "legacyId": 12, "stateId":   16 },
  "SIEVIERODONETSKYI-DSTR"     : { "name": "Сіверськодонецький район"         , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "ZOLOTE-CITY"                : { "name": "Золоте"                           , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "LYSYCHANSK-CITY"            : { "name": "Лисичанськ"                       , "regionId":   84, "legacyId": 12, "stateId":   16 },
  "SIEVIERODONETSK-CITY"       : { "name": "Сіверськодонецьк"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "SHCHASTYNSKYI-DSTR"         : { "name": "Щастинський район"                , "regionId":   87, "legacyId": 12, "stateId":   16 },
  "NOVOAIDAR-CITY"             : { "name": "Новоайдар"                        , "regionId":   87, "legacyId": 12, "stateId":   16 },
  "LVIVKA"                     : { "name": "Львівська область"                , "regionId":   27, "legacyId":  4, "stateId":   27 },
  "DROGOBICKYI-DSTR"           : { "name": "Дрогобицький район"               , "regionId":   91, "legacyId":  4, "stateId":   27 },
  "DROHOBYCH-CITY"             : { "name": "Дрогобич"                         , "regionId":   91, "legacyId":  4, "stateId":   27 },
  "ZOLOCHIVSKYI-DSTR"          : { "name": "Золочівський район"               , "regionId":   94, "legacyId":  4, "stateId":   27 },
  "ZOLOCHIV-LV-CITY"           : { "name": "Золочів (Львівська)"              , "regionId":   94, "legacyId":  4, "stateId":   27 },
  "LVIVSKYI-DSTR"              : { "name": "Львівський район"                 , "regionId":   90, "legacyId":  4, "stateId":   27 },
  "LVIV-CITY"                  : { "name": "Львів"                            , "regionId":  845, "legacyId":  4, "stateId":   27 },
  "SAMBIRSKYI-DSTR"            : { "name": "Самбірський район"                , "regionId":   88, "legacyId":  4, "stateId":   27 },
  "SAMBIR-CITY"                : { "name": "Самбір"                           , "regionId":   88, "legacyId":  4, "stateId":   27 },
  "STRIJSKYI-DSTR"             : { "name": "Стрийський район"                 , "regionId":   89, "legacyId":  4, "stateId":   27 },
  "STRYOI-CITY"                : { "name": "Стрий"                            , "regionId":   89, "legacyId":  4, "stateId":   27 },
  "CHERVONOGRADSKYI-DSTR"      : { "name": "Червоноградський район"           , "regionId":   92, "legacyId":  4, "stateId":   27 },
  "CHERVONOHRAD-CITY"          : { "name": "Шептицький"                       , "regionId":   92, "legacyId":  4, "stateId":   27 },
  "YAVORIVSKYI-DSTR"           : { "name": "Яворівський район"                , "regionId":   93, "legacyId":  4, "stateId":   27 },
  "YAVORIV-CITY"               : { "name": "Яворів"                           , "regionId":   93, "legacyId":  4, "stateId":   27 },
  "MYKOLAYIV"                  : { "name": "Миколаївська область"             , "regionId":   17, "legacyId": 18, "stateId":   17 },
  "BASHTANSKYI-DSTR"           : { "name": "Баштанський район"                , "regionId":   96, "legacyId": 18, "stateId":   17 },
  "BASHTANKA-CITY"             : { "name": "Баштанка"                         , "regionId":   96, "legacyId": 18, "stateId":   17 },
  "NOVIJ-BUG-CITY"             : { "name": "Новий Буг"                        , "regionId":   96, "legacyId": 18, "stateId":   17 },
  "SNIGURIVKA-CITY"            : { "name": "Снігурівка"                       , "regionId":   96, "legacyId": 18, "stateId":   17 },
  "VOZNESENSKYI-DSTR"          : { "name": "Вознесенський район"              , "regionId":   95, "legacyId": 18, "stateId":   17 },
  "YELANEC-CITY"               : { "name": "Єланець"                          , "regionId":   95, "legacyId": 18, "stateId":   17 },
  "VOZNESENSK-CITY"            : { "name": "Вознесенськ"                      , "regionId":   95, "legacyId": 18, "stateId":   17 },
  "YUZHNOUKRAYINSK-CITY"       : { "name": "Південноукраїнськ (Южноукраїнськ)", "regionId":   95, "legacyId": 18, "stateId":   17 },
  "MYKOLAIVSKYI-DSTR"          : { "name": "Миколаївський район"              , "regionId":   98, "legacyId": 18, "stateId":   17 },
  "KUTSURUB-CITY"              : { "name": "Куцуруб"                          , "regionId":   98, "legacyId": 18, "stateId":   17 },
  "MYKOLAIV-CITY"              : { "name": "Миколаїв"                         , "regionId":  926, "legacyId": 18, "stateId":   17 },
  "OCHAKIV-CITY"               : { "name": "Очаків"                           , "regionId":   98, "legacyId": 18, "stateId":   17 },
  "PERVOMAISKYI-DSTR"          : { "name": "Первомайський район"              , "regionId":   97, "legacyId": 18, "stateId":   17 },
  "ARBUZINKA-CITY"             : { "name": "Арбузинка"                        , "regionId":   97, "legacyId": 18, "stateId":   17 },
  "KRIVE-OZERO-CITY"           : { "name": "Криве Озеро"                      , "regionId":   97, "legacyId": 18, "stateId":   17 },
  "PERVOMAOISK-CITY"           : { "name": "Первомайськ"                      , "regionId":   97, "legacyId": 18, "stateId":   17 },
  "ODESKA"                     : { "name": "Одеська область"                  , "regionId":   18, "legacyId": 17, "stateId":   18 },
  "IZMAILSKYI-DSTR"            : { "name": "Ізмаїльський район"               , "regionId":  101, "legacyId": 17, "stateId":   18 },
  "IZMAIL-CITY"                : { "name": "Ізмаїл"                           , "regionId":  101, "legacyId": 17, "stateId":   18 },
  "KILIYA-CITY"                : { "name": "Кілія"                            , "regionId":  101, "legacyId": 17, "stateId":   18 },
  "BEREZIVSKYI-DSTR"           : { "name": "Березівський район"               , "regionId":  100, "legacyId": 17, "stateId":   18 },
  "BEREZIVKA-CITY"             : { "name": "Березівка"                        , "regionId":  100, "legacyId": 17, "stateId":   18 },
  "BOLHRADSKYI-DSTR"           : { "name": "Болградський район"               , "regionId":  105, "legacyId": 17, "stateId":   18 },
  "BOLHRAD-CITY"               : { "name": "Болград"                          , "regionId":  105, "legacyId": 17, "stateId":   18 },
  "BILHOROD-DNISTROVSKYI-DSTR" : { "name": "Білгород-Дністровський район"     , "regionId":  102, "legacyId": 17, "stateId":   18 },
  "BILHOROD-DNISTROVSKYOI-CITY": { "name": "Білгород-Дністровський"           , "regionId":  102, "legacyId": 17, "stateId":   18 },
  "SERGIYIVKA-CITY"            : { "name": "Сергіївка"                        , "regionId":  102, "legacyId": 17, "stateId":   18 },
  "ODESKYI-DSTR"               : { "name": "Одеський район"                   , "regionId":  104, "legacyId": 17, "stateId":   18 },
  "BILYAYIVKA-CITY"            : { "name": "Біляївка"                         , "regionId":  104, "legacyId": 17, "stateId":   18 },
  "ZATOKA-CITY"                : { "name": "Затока"                           , "regionId":  104, "legacyId": 17, "stateId":   18 },
  "ODESA-CITY"                 : { "name": "Одеса"                            , "regionId":  964, "legacyId": 17, "stateId":   18 },
  "YUZHNE-CITY"                : { "name": "Південне (Южне)"                  , "regionId":  104, "legacyId": 17, "stateId":   18 },
  "CHORNOMORSK-CITY"           : { "name": "Чорноморськ"                      , "regionId":  104, "legacyId": 17, "stateId":   18 },
  "PODILSKYI-DSTR"             : { "name": "Подільський район"                , "regionId":   99, "legacyId": 17, "stateId":   18 },
  "PODILSK-CITY"               : { "name": "Подільськ"                        , "regionId":   99, "legacyId": 17, "stateId":   18 },
  "ROZDILNIANSKYI-DSTR"        : { "name": "Роздільнянський район"            , "regionId":  103, "legacyId": 17, "stateId":   18 },
  "LIMANSKE-CITY"              : { "name": "Лиманське"                        , "regionId":  103, "legacyId": 17, "stateId":   18 },
  "ROZDILNA-CITY"              : { "name": "Роздільна"                        , "regionId":  103, "legacyId": 17, "stateId":   18 },
  "POLTASKA"                   : { "name": "Полтавська область"               , "regionId":   19, "legacyId": 20, "stateId":   19 },
  "KREMENCHUTSKYI-DSTR"        : { "name": "Кременчуцький район"              , "regionId":  107, "legacyId": 20, "stateId":   19 },
  "HORISHNI-PLAVNI-CITY"       : { "name": "Горішні Плавні"                   , "regionId":  107, "legacyId": 20, "stateId":   19 },
  "KREMENCHUK-CITY"            : { "name": "Кременчук"                        , "regionId":  107, "legacyId": 20, "stateId":   19 },
  "LUBNY-CITY"                 : { "name": "Лубни"                            , "regionId":  106, "legacyId": 20, "stateId":   19 },
  "MIRGOROD-CITY"              : { "name": "Миргород"                         , "regionId":  108, "legacyId": 20, "stateId":   19 },
  "HOROL-CITY"                 : { "name": "Хорол"                            , "regionId":  107, "legacyId": 20, "stateId":   19 },
  "LUBENSKYI-DSTR"             : { "name": "Лубенський район"                 , "regionId":  106, "legacyId": 20, "stateId":   19 },
  "GREBINKA-CITY"              : { "name": "Гребінка"                         , "regionId":  106, "legacyId": 20, "stateId":   19 },
  "PIRYATIN-CITY"              : { "name": "Пирятин"                          , "regionId":  106, "legacyId": 20, "stateId":   19 },
  "MYRHORODSKYI-DSTR"          : { "name": "Миргородський район"              , "regionId":  108, "legacyId": 20, "stateId":   19 },
  "POLTAVSKYI-DSTR"            : { "name": "Полтавський район"                , "regionId":  109, "legacyId": 20, "stateId":   19 },
  "KARLOVKA-CITY"              : { "name": "Карлівка"                         , "regionId":  109, "legacyId": 20, "stateId":   19 },
  "POLTAVA-CITY"               : { "name": "Полтава"                          , "regionId": 1060, "legacyId": 20, "stateId":   19 },
  "RIVENSKA"                   : { "name": "Рівненська область"               , "regionId":    5, "legacyId":  6, "stateId":    5 },
  "VARASKYI-DSTR"              : { "name": "Вараський район"                  , "regionId":  110, "legacyId":  6, "stateId":    5 },
  "VARASH-CITY"                : { "name": "Вараш"                            , "regionId":  110, "legacyId":  6, "stateId":    5 },
  "DUBENSKYI-DSTR"             : { "name": "Дубенський район"                 , "regionId":  111, "legacyId":  6, "stateId":    5 },
  "DUBNO-CITY"                 : { "name": "Дубно"                            , "regionId":  111, "legacyId":  6, "stateId":    5 },
  "RIVNENSKYI-DSTR"            : { "name": "Рівненський район"                , "regionId":  112, "legacyId":  6, "stateId":    5 },
  "BEREZNE-CITY"               : { "name": "Березне"                          , "regionId":  112, "legacyId":  6, "stateId":    5 },
  "KOREC-CITY"                 : { "name": "Корець"                           , "regionId":  112, "legacyId":  6, "stateId":    5 },
  "RIVNE-CITY"                 : { "name": "Рівне"                            , "regionId": 1133, "legacyId":  6, "stateId":    5 },
  "SARNENSKYI-DSTR"            : { "name": "Сарненський район"                , "regionId":  113, "legacyId":  6, "stateId":    5 },
  "SARNI-CITY"                 : { "name": "Сарни"                            , "regionId":  113, "legacyId":  6, "stateId":    5 },
  "SUMSKA"                     : { "name": "Сумська область"                  , "regionId":   20, "legacyId": 10, "stateId":   20 },
  "KONOTOPSKYI-DSTR"           : { "name": "Конотопський район"               , "regionId":  117, "legacyId": 10, "stateId":   20 },
  "BURIN-CITY"                 : { "name": "Буринь"                           , "regionId":  117, "legacyId": 10, "stateId":   20 },
  "KONOTOP-CITY"               : { "name": "Конотоп"                          , "regionId":  117, "legacyId": 10, "stateId":   20 },
  "KROLEVETS-CITY"             : { "name": "Кролевець"                        , "regionId":  117, "legacyId": 10, "stateId":   20 },
  "NOVA-SLOBODA-CITY"          : { "name": "Нова Слобода"                     , "regionId":  117, "legacyId": 10, "stateId":   20 },
  "PUTIVL-CITY"                : { "name": "Путивль"                          , "regionId":  117, "legacyId": 10, "stateId":   20 },
  "OKHTYRSKYI-DSTR"            : { "name": "Охтирський район"                 , "regionId":  118, "legacyId": 10, "stateId":   20 },
  "VELIKA-PISARIVKA-CITY"      : { "name": "Велика Писарівка"                 , "regionId":  118, "legacyId": 10, "stateId":   20 },
  "OKHTYRKA-CITY"              : { "name": "Охтирка"                          , "regionId":  118, "legacyId": 10, "stateId":   20 },
  "TROSTYANEC-CITY"            : { "name": "Тростянець"                       , "regionId":  118, "legacyId": 10, "stateId":   20 },
  "ROMENSKYI-DSTR"             : { "name": "Роменський район"                 , "regionId":  116, "legacyId": 10, "stateId":   20 },
  "NEDRIGAJLIV-CITY"           : { "name": "Недригайлів"                      , "regionId":  116, "legacyId": 10, "stateId":   20 },
  "ROMNI-CITY"                 : { "name": "Ромни"                            , "regionId":  116, "legacyId": 10, "stateId":   20 },
  "SUMSKYI-DSTR"               : { "name": "Сумський район"                   , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "ISKRISKIVSHIVSHINA-CITY"    : { "name": "Іскрисківщина"                    , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "ATINSKE-CITY"               : { "name": "Атинське"                         , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "BASIVKA-CITY"               : { "name": "Басівка"                          , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "YABUDKI-CITY"               : { "name": "Будки"                            , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "BILOPILLIA-CITY"            : { "name": "Білопілля"                        , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "VOLFINE-CITY"               : { "name": "Волфине"                          , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "VOROZHBA-CITY"              : { "name": "Ворожба"                          , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "KATERINIVKA-CITY"           : { "name": "Катеринівка"                      , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "KRASNOPILLYA-CITY"          : { "name": "Краснопілля"                      , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "KINDRATIVKA-CITY"           : { "name": "Кіндратівка"                      , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "LEBEDIN-CITY"               : { "name": "Лебедин"                          , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "MEZENIVKA-CITY"             : { "name": "Мезенівка"                        , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "MIKOLAYIVKA-CITY"           : { "name": "Миколаївка"                       , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "MIROPILLYA-CITY"            : { "name": "Миропілля"                        , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "MOGRICYA-CITY"              : { "name": "Могриця"                          , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "OBODI-CITY"                 : { "name": "Ободи"                            , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "PAVLIVKA-CITY"              : { "name": "Павлівка"                         , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "RIZHIVKA-CITY"              : { "name": "Рижівка"                          , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "SUMY-CITY"                  : { "name": "Суми"                             , "regionId": 1187, "legacyId": 10, "stateId":   20 },
  "UGROYIDI-CITY"              : { "name": "Угроїди"                          , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "HOTIN-CITY"                 : { "name": "Хотінь"                           , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "YUNAKIVKA-CITY"             : { "name": "Юнаківка"                         , "regionId":  114, "legacyId": 10, "stateId":   20 },
  "SHOSTKYNSKYI-DSTR"          : { "name": "Шосткинський район"               , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "VORONIZH-CITY"              : { "name": "Вороніж"                          , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "GLUHIV-CITY"                : { "name": "Глухів"                           , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "ESMAN-CITY"                 : { "name": "Есмань"                           , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "ZNOB-NOVGORODSKE-CITY"      : { "name": "Зноб-Новгородське"                , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "SVESA-CITY"                 : { "name": "Свеса"                            , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "SEREDINA-BUDA-CITY"         : { "name": "Середина-Буда"                    , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "SHALIGINE-CITY"             : { "name": "Шалигине"                         , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "SHOSTKA-CITY"               : { "name": "Шостка"                           , "regionId":  115, "legacyId": 10, "stateId":   20 },
  "TERNOPILSKA"                : { "name": "Тернопільська область"            , "regionId":   21, "legacyId":  3, "stateId":   21 },
  "KREMENECKYI-DSTR"           : { "name": "Кременецький район"               , "regionId":  120, "legacyId":  3, "stateId":   21 },
  "KREMENEC-CITY"              : { "name": "Кременець"                        , "regionId":  120, "legacyId":  3, "stateId":   21 },
  "TERNOPILSKYI-DSTR"          : { "name": "Тернопільський район"             , "regionId":  119, "legacyId":  3, "stateId":   21 },
  "TERNOPIL-CITY"              : { "name": "Тернопіль"                        , "regionId": 1241, "legacyId":  3, "stateId":   21 },
  "CHORTKIVSKYI-DSTR"          : { "name": "Чортківський район"               , "regionId":  121, "legacyId":  3, "stateId":   21 },
  "CHORTKIV-CITY"              : { "name": "Чортків"                          , "regionId":  121, "legacyId":  3, "stateId":   21 },
  "TEST"                       : { "name": "Тест"                             , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "TEST-DSTR"                  : { "name": "Тестовий район"                   , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "TEST-CITY"                  : { "name": "Тестове місто"                    , "regionId":   -1, "legacyId": -1, "stateId":   -1 },
  "HARKIVSKA"                  : { "name": "Харківська область"               , "regionId":   22, "legacyId": 11, "stateId":   22 },
  "IZIUMSKYI-DSTR"             : { "name": "Ізюмський район"                  , "regionId":  125, "legacyId": 11, "stateId":   22 },
  "IZIUM-CITY"                 : { "name": "Ізюм"                             , "regionId":  125, "legacyId": 11, "stateId":   22 },
  "BALAKLIYA-CITY"             : { "name": "Балаклія"                         , "regionId":  125, "legacyId": 11, "stateId":   22 },
  "BOROVA-CITY"                : { "name": "Борова"                           , "regionId":  125, "legacyId": 11, "stateId":   22 },
  "KRASNOHRADSKYI-DSTR"        : { "name": "Красноградський район"            , "regionId":  127, "legacyId": 11, "stateId":   22 },
  "KRASNOGRAD-CITY"            : { "name": "Берестин"                         , "regionId":  127, "legacyId": 11, "stateId":   22 },
  "BOHODUKHIVSKYI-DSTR"        : { "name": "Богодухівський район"             , "regionId":  126, "legacyId": 11, "stateId":   22 },
  "BOGODUHIV-CITY"             : { "name": "Богодухів"                        , "regionId":  126, "legacyId": 11, "stateId":   22 },
  "ZOLOCHIV-CITY"              : { "name": "Золочів"                          , "regionId":  126, "legacyId": 11, "stateId":   22 },
  "KUPIANSKYI-DSTR"            : { "name": "Куп'янський район"                , "regionId":  123, "legacyId": 11, "stateId":   22 },
  "KUP-YANSK-CITY"             : { "name": "Куп'янськ"                        , "regionId":  123, "legacyId": 11, "stateId":   22 },
  "LOZIVSKYI-DSTR"             : { "name": "Лозівський район"                 , "regionId":  128, "legacyId": 11, "stateId":   22 },
  "PERVOMAJSKIJ-CITY"          : { "name": "Златопіль"                        , "regionId":  128, "legacyId": 11, "stateId":   22 },
  "LOZOVA-KHARKIVSKA-CITY"     : { "name": "Лозова"                           , "regionId":  128, "legacyId": 11, "stateId":   22 },
  "KHARKIVSKYI-DSTR"           : { "name": "Харківський район"                , "regionId":  124, "legacyId": 11, "stateId":   22 },
  "DERGACHI-CITY"              : { "name": "Дергачі"                          , "regionId":  124, "legacyId": 11, "stateId":   22 },
  "KOZACHA-LOPAN-CITY"         : { "name": "Козача Лопань"                    , "regionId":  124, "legacyId": 11, "stateId":   22 },
  "LIPCI-CITY"                 : { "name": "Липці"                            , "regionId":  124, "legacyId": 11, "stateId":   22 },
  "MEREFA-CITY"                : { "name": "Мерефа"                           , "regionId":  124, "legacyId": 11, "stateId":   22 },
  "PISOCHINO-CITY"             : { "name": "Пісочин"                          , "regionId":  124, "legacyId": 11, "stateId":   22 },
  "KHARKIV-CITY"               : { "name": "Харків"                           , "regionId": 1293, "legacyId": 11, "stateId":   22 },
  "CIRKUNI-CITY"               : { "name": "Циркуни"                          , "regionId":  124, "legacyId": 11, "stateId":   22 },
  "CHUHUIVSKYI-DSTR"           : { "name": "Чугуївський район"                , "regionId":  122, "legacyId": 11, "stateId":   22 },
  "BILIJ-KOLODYAZ-CITY"        : { "name": "Білий Колодязь"                   , "regionId":  122, "legacyId": 11, "stateId":   22 },
  "VOVCHANSK-CITY"             : { "name": "Вовчанськ"                        , "regionId":  122, "legacyId": 11, "stateId":   22 },
  "KOROBOCHKINE-CITY"          : { "name": "Коробочкине"                      , "regionId":  122, "legacyId": 11, "stateId":   22 },
  "CHUGUYIV-CITY"              : { "name": "Чугуїв"                           , "regionId":  122, "legacyId": 11, "stateId":   22 },
  "HERSONSKA"                  : { "name": "Херсонська область"               , "regionId":   23, "legacyId": 15, "stateId":   23 },
  "BERYSLAVSKYI-DSTR"          : { "name": "Бериславський район"              , "regionId":  129, "legacyId": 15, "stateId":   23 },
  "BERISLAV-CITY"              : { "name": "Берислав"                         , "regionId":  129, "legacyId": 15, "stateId":   23 },
  "HENICHESKYI-DSTR"           : { "name": "Генічеський район"                , "regionId":  133, "legacyId": 15, "stateId":   23 },
  "GENICHESK-CITY"             : { "name": "Генічеськ"                        , "regionId":  133, "legacyId": 15, "stateId":   23 },
  "KAKHOVSKYI-DSTR"            : { "name": "Каховський район"                 , "regionId":  131, "legacyId": 15, "stateId":   23 },
  "KAHOVKA-CITY"               : { "name": "Каховка"                          , "regionId":  131, "legacyId": 15, "stateId":   23 },
  "NOVA-KAKHOVKA-CITY"         : { "name": "Нова Каховка"                     , "regionId":  131, "legacyId": 15, "stateId":   23 },
  "TAVRIJSK-CITY"              : { "name": "Таврійськ"                        , "regionId":  131, "legacyId": 15, "stateId":   23 },
  "CHAPLINKA-CITY"             : { "name": "Чаплинка"                         , "regionId":  131, "legacyId": 15, "stateId":   23 },
  "SKADOVSKYI-DSTR"            : { "name": "Скадовський район"                , "regionId":  130, "legacyId": 15, "stateId":   23 },
  "SKADOVSK-CITY"              : { "name": "Скадовськ"                        , "regionId":  130, "legacyId": 15, "stateId":   23 },
  "KHERSONSKYI-DSTR"           : { "name": "Херсонський район"                , "regionId":  132, "legacyId": 15, "stateId":   23 },
  "ANTONIVKA-CITY"             : { "name": "Антонівка"                        , "regionId":  132, "legacyId": 15, "stateId":   23 },
  "BILOZERKA-CITY"             : { "name": "Білозерка"                        , "regionId":  132, "legacyId": 15, "stateId":   23 },
  "OLEKSANDRIVKA-CITY"         : { "name": "Олександрівка"                    , "regionId":  132, "legacyId": 15, "stateId":   23 },
  "OLESHKI-CITY"               : { "name": "Олешки"                           , "regionId":  132, "legacyId": 15, "stateId":   23 },
  "KHERSON-CITY"               : { "name": "Херсон"                           , "regionId": 1370, "legacyId": 15, "stateId":   23 },
  "CHORNOBAYIVKA-CITY"         : { "name": "Чорнобаївка"                      , "regionId":  132, "legacyId": 15, "stateId":   23 },
  "HMELNYCKA"                  : { "name": "Хмельницька область"              , "regionId":    3, "legacyId": 24, "stateId":    3 },
  "KAMIANETS-PODILSKYI-DSTR"   : { "name": "Кам'янець-Подільський район"      , "regionId":  135, "legacyId": 24, "stateId":    3 },
  "KAMIANETS-PODILSKYOI-CITY"  : { "name": "Кам'янець-Подільський"            , "regionId":  135, "legacyId": 24, "stateId":    3 },
  "KHMELNYTSKYI-DSTR"          : { "name": "Хмельницький район"               , "regionId":  134, "legacyId": 24, "stateId":    3 },
  "VOLOCHISK-CITY"             : { "name": "Волочиськ"                        , "regionId":  134, "legacyId": 24, "stateId":    3 },
  "STAROKOSTYANTINIV-CITY"     : { "name": "Старокостянтинів"                 , "regionId":  134, "legacyId": 24, "stateId":    3 },
  "TEOFIPOL-CITY"              : { "name": "Теофіполь"                        , "regionId":  134, "legacyId": 24, "stateId":    3 },
  "KHMELNYTSKYOI-CITY"         : { "name": "Хмельницький"                     , "regionId": 1400, "legacyId": 24, "stateId":    3 },
  "SHEPETIVSKYI-DSTR"          : { "name": "Шепетівський район"               , "regionId":  136, "legacyId": 24, "stateId":    3 },
  "NETISHYN-CITY"              : { "name": "Нетішин"                          , "regionId":  136, "legacyId": 24, "stateId":    3 },
  "SLAVUTA-CITY"               : { "name": "Славута"                          , "regionId":  136, "legacyId": 24, "stateId":    3 },
  "SHEPETIVKA-CITY"            : { "name": "Шепетівка"                        , "regionId":  136, "legacyId": 24, "stateId":    3 },
  "CHERKASKA"                  : { "name": "Черкаська область"                , "regionId":   24, "legacyId": 21, "stateId":   24 },
  "ZVENYHORODSKYI-DSTR"        : { "name": "Звенигородський район"            , "regionId":  150, "legacyId": 21, "stateId":   24 },
  "VATUTINE-CITY"              : { "name": "Багачеве"                         , "regionId":  150, "legacyId": 21, "stateId":   24 },
  "ZVENIGORODKA-CITY"          : { "name": "Звенигородка"                     , "regionId":  150, "legacyId": 21, "stateId":   24 },
  "ZOLOTONISKYI-DSTR"          : { "name": "Золотоніський район"              , "regionId":  153, "legacyId": 21, "stateId":   24 },
  "ZOLOTONOSHA-CITY"           : { "name": "Золотоноша"                       , "regionId":  153, "legacyId": 21, "stateId":   24 },
  "UMANSKYI-DSTR"              : { "name": "Уманський район"                  , "regionId":  151, "legacyId": 21, "stateId":   24 },
  "ZHASHKIV-CITY"              : { "name": "Жашків"                           , "regionId":  151, "legacyId": 21, "stateId":   24 },
  "UMAN-CITY"                  : { "name": "Умань"                            , "regionId":  151, "legacyId": 21, "stateId":   24 },
  "CHERKASKYI-DSTR"            : { "name": "Черкаський район"                 , "regionId":  152, "legacyId": 21, "stateId":   24 },
  "KANIV-CITY"                 : { "name": "Канів"                            , "regionId":  152, "legacyId": 21, "stateId":   24 },
  "KORSUN-CITY"                : { "name": "Корсунь-Шевченківський"           , "regionId":  152, "legacyId": 21, "stateId":   24 },
  "SMILA-CITY"                 : { "name": "Сміла"                            , "regionId":  152, "legacyId": 21, "stateId":   24 },
  "CHERKASY-CITY"              : { "name": "Черкаси"                          , "regionId": 1473, "legacyId": 21, "stateId":   24 },
  "CHERNIVETSKA"               : { "name": "Чернівецька область"              , "regionId":   26, "legacyId": 25, "stateId":   26 },
  "VYZHNYTSKYI-DSTR"           : { "name": "Вижницький район"                 , "regionId":  138, "legacyId": 25, "stateId":   26 },
  "VYZHNYTSIA-CITY"            : { "name": "Вижниця"                          , "regionId":  138, "legacyId": 25, "stateId":   26 },
  "DNISTROVSKYI-DSTR"          : { "name": "Дністровський район"              , "regionId":  139, "legacyId": 25, "stateId":   26 },
  "KELMENTSI-CITY"             : { "name": "Кельменці"                        , "regionId":  139, "legacyId": 25, "stateId":   26 },
  "CHERNIVETSKYI-DSTR"         : { "name": "Чернівецький район"               , "regionId":  137, "legacyId": 25, "stateId":   26 },
  "CHERNIVTSI-CITY"            : { "name": "Чернівці"                         , "regionId": 1542, "legacyId": 25, "stateId":   26 },
  "CHERNIGIWSKA"               : { "name": "Чернігівська область"             , "regionId":   25, "legacyId":  9, "stateId":   25 },
  "KORIUKIVSKYI-DSTR"          : { "name": "Корюківський район"               , "regionId":  144, "legacyId":  9, "stateId":   25 },
  "KORIUKIVKA-CITY"            : { "name": "Корюківка"                        , "regionId":  144, "legacyId":  9, "stateId":   25 },
  "NOVHOROD-SIVERSKYI-DSTR"    : { "name": "Новгород-Сіверський район"        , "regionId":  141, "legacyId":  9, "stateId":   25 },
  "NOVHOROD-SIVERSKYI"         : { "name": "Новгород-Сіверський"              , "regionId":  141, "legacyId":  9, "stateId":   25 },
  "SEMENIVKA-CITY"             : { "name": "Семенівка"                        , "regionId":  141, "legacyId":  9, "stateId":   25 },
  "NIZHYNSKYI-DSTR"            : { "name": "Ніжинський район"                 , "regionId":  142, "legacyId":  9, "stateId":   25 },
  "BAHMACH-CITY"               : { "name": "Бахмач"                           , "regionId":  142, "legacyId":  9, "stateId":   25 },
  "BORZNA-CITY"                : { "name": "Борзна"                           , "regionId":  142, "legacyId":  9, "stateId":   25 },
  "NOSIVKA-CITY"               : { "name": "Носівка"                          , "regionId":  142, "legacyId":  9, "stateId":   25 },
  "NIZHYN-CITY"                : { "name": "Ніжин"                            , "regionId":  142, "legacyId":  9, "stateId":   25 },
  "PRYLUTSKYI-DSTR"            : { "name": "Прилуцький район"                 , "regionId":  143, "legacyId":  9, "stateId":   25 },
  "ICHNYA-CITY"                : { "name": "Ічня"                             , "regionId":  143, "legacyId":  9, "stateId":   25 },
  "PRYLUKY-CITY"               : { "name": "Прилуки"                          , "regionId":  143, "legacyId":  9, "stateId":   25 },
  "TALALAYIVKA-CITY"           : { "name": "Талалаївка"                       , "regionId":  143, "legacyId":  9, "stateId":   25 },
  "CHERNIHIVSKYI-DSTR"         : { "name": "Чернігівський район"              , "regionId":  140, "legacyId":  9, "stateId":   25 },
  "GONCHARIVSKE-CITY"          : { "name": "Гончарівське"                     , "regionId":  140, "legacyId":  9, "stateId":   25 },
  "DESNA-CITY"                 : { "name": "Десна"                            , "regionId":  140, "legacyId":  9, "stateId":   25 },
  "OSTER-CITY"                 : { "name": "Остер"                            , "regionId":  140, "legacyId":  9, "stateId":   25 },
  "CHERNIHIV-CITY"             : { "name": "Чернігів"                         , "regionId": 1591, "legacyId":  9, "stateId":   25 }
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
    for _, region_data in regions.items():
        if region_data[initial_key] == key_value and not region_data.get("skip"):
            return region_data['name'], region_data[result_key]
    return None, None


def get_current_datetime():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_current_timestamp():
    return int(datetime.datetime.now(datetime.UTC).timestamp())


def get_legacy_state_id(region_id, regions_cache):
    try:
        for _, region_data in regions.items():
            if region_data["regionId"] == int(region_id):
                legacy_state_id = region_data["legacyId"]
                return legacy_state_id
        return None
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


def encode_temperature_to_mask(temp_c) -> int:
    """
    Упаковує температуру у бітову маску (1 байт).
    Діапазон значень: від -50 до 50 включно.
    Схема кодування:
      - біти [0..6] (7 біт): модуль температури (0..50)
      - біт [7]: знак (1 — від'ємна, 0 — додатна або нуль)
    Приклад:
      +25 -> 0b0011001 (25)
      -12 -> 0b1_0001100 (128 + 12 = 140)
    """
    try:
        t = int(round(float(temp_c), 0))
    except Exception:
        return 0
    # Обмежуємо діапазон
    if t < -127:
        t = -127
    elif t > 127:
        t = 127
    sign = 1 if t < 0 else 0
    magnitude = -t if t < 0 else t  # 0..127
    return (sign << 7) | magnitude


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

            for _, state_data in regions.items():
                state_name = state_data["name"]
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
                    # if alert_type == "Ballistic": # це насправді "Kabs"
                    #     data[regionId] |= (1 << 8) 
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
                    data[regionId] |= (1 << 10)
                
                if data[regionId] == 0:
                    del data[regionId]
            if data:
                logger.info(f" DATA: {str(data)}")
                await store_websocket_data(mc, data, websocket, "etryvoga_fusion_websocket_v1", b"etryvoga_fusion_websocket_v1")
            await store_websocket_data(mc, first_processed_id, last_processed_id, "etryvoga_last_processed_id", b"etryvoga_last_processed_id")


        except Exception as e:
            logger.error(f"update_etryvoga_fusion_websocket_v1: {str(e)}")
            logger.debug(f"Повний стек помилки:", exc_info=True)
        if run_once:
            break

async def update_weather_openweathermap_fusion_v1(mc, run_once=False):
    while True:
        try:
            await asyncio.sleep(update_period)
            weather_cache = await get_weather(mc, b"weather_openweathermap", {"states": {}, "info": {"last_update": None}})
            websocket = await get_cache_data(mc, b"weather_fusion_websocket_v1")

            data = {}

            for state_id, state_data in weather_cache["states"].items():
                # було: data[state_id] = int(round(state_data["temp"], 0))
                data[state_id] = encode_temperature_to_mask(state_data.get("temp"))

            await store_websocket_data(mc, data, websocket, "weather_fusion_websocket_v1", b"weather_fusion_websocket_v1")

        except Exception as e:
            logger.error(f"update_weather_openweathermap_fusion_v1: {str(e)}")
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
            update_weather_openweathermap_fusion_v1(mc),
        )
        
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
