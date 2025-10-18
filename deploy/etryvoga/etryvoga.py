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
  "ALL"                         : { "name": "Вся Україна"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":         49.0, "lon":         32.0} },
  "IVANOFRANKIWSKA"             : { "name": "Івано-Франківська область"        , "regionId":   13, "legacyId":  2, "stateId":   13, "location": {"lat":   48.7481718, "lon":   24.5207477} },
  "IVANO-FRANKIVSKYI-DSTR"      : { "name": "Івано-Франківський район"         , "regionId":   68, "legacyId":  2, "stateId":   13, "location": {"lat":   49.0336758, "lon":   24.7516914} },
  "IVANO-FRANKIVSK-CITY"        : { "name": "Івано-Франківськ"                 , "regionId":  632, "legacyId":  2, "stateId":   13, "location": {"lat":   48.9224763, "lon":    24.710334} },
  "BOHORODCHANY-CITY"           : { "name": "Богородчани"                      , "regionId":   68, "legacyId":  2, "stateId":   13, "location": {"lat":   48.8092602, "lon":   24.5456201} },
  "BURSHTYN-CITY"               : { "name": "Бурштин"                          , "regionId":   68, "legacyId":  2, "stateId":   13, "location": {"lat":   49.2621603, "lon":   24.6159932} },
  "HALYCH-CITY"                 : { "name": "Галич"                            , "regionId":   68, "legacyId":  2, "stateId":   13, "location": {"lat":    49.123317, "lon":   24.7299495} },
  "ROHATYN-CITY"                : { "name": "Рогатин"                          , "regionId":   68, "legacyId":  2, "stateId":   13, "location": {"lat":   49.4092703, "lon":   24.6105811} },
  "TLUMACH-CITY"                : { "name": "Тлумач"                           , "regionId":   68, "legacyId":  2, "stateId":   13, "location": {"lat":   48.8665866, "lon":   25.0011978} },
  "VERKHOVYNSKYI-DSTR"          : { "name": "Верховинський район"              , "regionId":   67, "legacyId":  2, "stateId":   13, "location": {"lat":   48.0011714, "lon":   24.7426724} },
  "VERKHOVYNA-CITY"             : { "name": "Верховина"                        , "regionId":   67, "legacyId":  2, "stateId":   13, "location": {"lat":   48.1538102, "lon":     24.82793} },
  "KALUSKYI-DSTR"               : { "name": "Калуський район"                  , "regionId":   71, "legacyId":  2, "stateId":   13, "location": {"lat":   48.8453757, "lon":   23.9646725} },
  "DOLYNA-CITY"                 : { "name": "Долина"                           , "regionId":   71, "legacyId":  2, "stateId":   13, "location": {"lat":   48.9782308, "lon":   23.9789588} },
  "KALUSH"                      : { "name": "Калуш"                            , "regionId":   71, "legacyId":  2, "stateId":   13, "location": {"lat":    49.028894, "lon":   24.3613198} },
  "ROZHNIATIV-CITY"             : { "name": "Рожнятів"                         , "regionId":   71, "legacyId":  2, "stateId":   13, "location": {"lat":   48.9402225, "lon":   24.1580976} },
  "KOLOMYISKYI-DSTR"            : { "name": "Коломийський район"               , "regionId":   70, "legacyId":  2, "stateId":   13, "location": {"lat":   48.6150911, "lon":   25.1861214} },
  "HORODENKA-CITY"              : { "name": "Городенка"                        , "regionId":   70, "legacyId":  2, "stateId":   13, "location": {"lat":   48.6720598, "lon":   25.4952722} },
  "KOLOMYIA-CITY"               : { "name": "Коломия"                          , "regionId":   70, "legacyId":  2, "stateId":   13, "location": {"lat":   48.5259211, "lon":   25.0380538} },
  "SNIATYN-CITY"                : { "name": "Снятин"                           , "regionId":   70, "legacyId":  2, "stateId":   13, "location": {"lat":   48.4523142, "lon":   25.5518046} },
  "KOSIVSKYI-DSTR"              : { "name": "Косівський район"                 , "regionId":   69, "legacyId":  2, "stateId":   13, "location": {"lat":   48.3088262, "lon":   24.9864628} },
  "KOSIV-CITY"                  : { "name": "Косів"                            , "regionId":   69, "legacyId":  2, "stateId":   13, "location": {"lat":    48.315802, "lon":   25.0983417} },
  "NADVIRNIANSKYI-DSTR"         : { "name": "Надвірнянський район"             , "regionId":   72, "legacyId":  2, "stateId":   13, "location": {"lat":   48.4371696, "lon":   24.4385373} },
  "NADVIRNA-CITY"               : { "name": "Надвірна"                         , "regionId":   72, "legacyId":  2, "stateId":   13, "location": {"lat":   48.6335887, "lon":   24.5684038} },
  "YAREMCHE-CITY"               : { "name": "Яремче"                           , "regionId":   72, "legacyId":  2, "stateId":   13, "location": {"lat":   48.4504129, "lon":    24.550955} },
  "VOLYNSKA"                    : { "name": "Волинська область"                , "regionId":    8, "legacyId":  5, "stateId":    8, "location": {"lat":   51.5451167, "lon":   24.6627893} },
  "VOLODIMIR-VOLINSKYI-DSTR"    : { "name": "Володимир-Волинський район"       , "regionId":   38, "legacyId":  5, "stateId":    8, "location": {"lat":   50.8780726, "lon":   24.3467403} },
  "IVANYCHI-CITY"               : { "name": "Іваничі"                          , "regionId":   38, "legacyId":  5, "stateId":    8, "location": {"lat":   50.6405719, "lon":   24.3614426} },
  "VOLODYMYR-CITY"              : { "name": "Володимир"                        , "regionId":   38, "legacyId":  5, "stateId":    8, "location": {"lat":   50.8474669, "lon":    24.319319} },
  "LOKACHI-CITY"                : { "name": "Локачі"                           , "regionId":   38, "legacyId":  5, "stateId":    8, "location": {"lat":    50.738946, "lon":   24.6482949} },
  "NOVOVOLYNSK-CITY"            : { "name": "Нововолинськ"                     , "regionId":   38, "legacyId":  5, "stateId":    8, "location": {"lat":   50.7224829, "lon":   24.1648399} },
  "KAMIN-KASHIRSKYI-DSTR"       : { "name": "Камінь-Каширський район"          , "regionId":   41, "legacyId":  5, "stateId":    8, "location": {"lat":   51.5487281, "lon":   25.1730185} },
  "KAMIN-KASHIRSKIJ-CITY"       : { "name": "Камінь-Каширський"                , "regionId":   41, "legacyId":  5, "stateId":    8, "location": {"lat":   51.6271153, "lon":    24.961357} },
  "LIUBESHIV-CITY"              : { "name": "Любешів"                          , "regionId":   41, "legacyId":  5, "stateId":    8, "location": {"lat":   51.7632795, "lon":   25.5048264} },
  "MANEVYCHI-CITY"              : { "name": "Маневичі"                         , "regionId":   41, "legacyId":  5, "stateId":    8, "location": {"lat":   51.2908106, "lon":    25.537878} },
  "KOVELSKYI-DSTR"              : { "name": "Ковельський район"                , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":   51.3893976, "lon":   24.2896333} },
  "HOLOBY-CITY"                 : { "name": "Голоби"                           , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":   51.0859784, "lon":    25.015465} },
  "KOVEL-CITY"                  : { "name": "Ковель"                           , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":   51.2120807, "lon":   24.7088806} },
  "LIUBOML-CITY"                : { "name": "Любомль"                          , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":   51.2234546, "lon":   24.0315783} },
  "RATNE-CITY"                  : { "name": "Ратне"                            , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":     51.67145, "lon":     24.52458} },
  "STARA-VYZHIVKA-CITY"         : { "name": "Стара Вижівка"                    , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":   51.4422955, "lon":    24.438565} },
  "TURIISTK-CITY"               : { "name": "Турійськ"                         , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":     51.08299, "lon":     24.52389} },
  "SHATSK-CITY"                 : { "name": "Шацьк"                            , "regionId":   40, "legacyId":  5, "stateId":    8, "location": {"lat":   51.4909494, "lon":   23.9219323} },
  "LUCKYI-DSTR"                 : { "name": "Луцький район"                    , "regionId":   39, "legacyId":  5, "stateId":    8, "location": {"lat":   50.7597625, "lon":    25.410405} },
  "HOROKHIV-CITY"               : { "name": "Горохів"                          , "regionId":   39, "legacyId":  5, "stateId":    8, "location": {"lat":   50.4986166, "lon":   24.7600734} },
  "KIVERTSI-CITY"               : { "name": "Ківерці"                          , "regionId":   39, "legacyId":  5, "stateId":    8, "location": {"lat":   50.8333448, "lon":   25.4648622} },
  "LUTSK-CITY"                  : { "name": "Луцьк"                            , "regionId":  225, "legacyId":  5, "stateId":    8, "location": {"lat":   50.7450733, "lon":    25.320078} },
  "ROZHYSHCHE-CITY"             : { "name": "Рожище"                           , "regionId":   39, "legacyId":  5, "stateId":    8, "location": {"lat":    50.916332, "lon":   25.2712543} },
  "VINNYTSA"                    : { "name": "Вінницька область"                , "regionId":    4, "legacyId": 23, "stateId":    4, "location": {"lat":   48.8990315, "lon":    28.516068} },
  "VINNYTSKYI-DSTR"             : { "name": "Вінницький район"                 , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   49.2421465, "lon":    28.884796} },
  "ILLINTSI-CITY"               : { "name": "Іллінці"                          , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   49.1136358, "lon":   29.2024356} },
  "VINNYTSIA-CITY"              : { "name": "Вінниця"                          , "regionId":  155, "legacyId": 23, "stateId":    4, "location": {"lat":   49.2320162, "lon":    28.467975} },
  "HNIVAN-CITY"                 : { "name": "Гнівань"                          , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   49.0933696, "lon":    28.338343} },
  "LYPOVETS-CITY"               : { "name": "Липовець"                         , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   49.2296415, "lon":   29.0642148} },
  "LITYN-CITY"                  : { "name": "Літин"                            , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   49.3289764, "lon":   28.0740254} },
  "NEMYRIV-CITY"                : { "name": "Немирів"                          , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   48.9654035, "lon":   28.8430131} },
  "ORATIV-CITY"                 : { "name": "Оратів"                           , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":     49.19472, "lon":     29.53056} },
  "POHREBYSHCHE-CITY"           : { "name": "Погребище"                        , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   49.4848166, "lon":   29.2579157} },
  "TYVRIV-CITY"                 : { "name": "Тиврів"                           , "regionId":   36, "legacyId": 23, "stateId":    4, "location": {"lat":   49.0139727, "lon":    28.507999} },
  "HAISYNSKYI-DSTR"             : { "name": "Гайсинський район"                , "regionId":   37, "legacyId": 23, "stateId":    4, "location": {"lat":   48.6069668, "lon":   29.5472586} },
  "BERSHAD-CITY"                : { "name": "Бершадь"                          , "regionId":   37, "legacyId": 23, "stateId":    4, "location": {"lat":     48.36594, "lon":     29.51889} },
  "HAISYN-CITY"                 : { "name": "Гайсин"                           , "regionId":   37, "legacyId": 23, "stateId":    4, "location": {"lat":   48.8120874, "lon":   29.3893874} },
  "LADYZHYN-CITY"               : { "name": "Ладижин"                          , "regionId":   37, "legacyId": 23, "stateId":    4, "location": {"lat":   48.6810505, "lon":   29.2567642} },
  "TEPLYK-CITY"                 : { "name": "Теплик"                           , "regionId":   37, "legacyId": 23, "stateId":    4, "location": {"lat":      48.6636, "lon":     29.74686} },
  "TROSTIANETS-CITY"            : { "name": "Тростянець"                       , "regionId":  118, "legacyId": 10, "stateId":   20, "location": {"lat":     50.48046, "lon":     34.96467} },
  "CHECHELNYK-CITY"             : { "name": "Чечельник"                        , "regionId":   37, "legacyId": 23, "stateId":    4, "location": {"lat":   48.2126987, "lon":   29.3598689} },
  "ZHMERYNSKYI-DSTR"            : { "name": "Жмеринський район"                , "regionId":   35, "legacyId": 23, "stateId":    4, "location": {"lat":   48.9175452, "lon":   27.8781458} },
  "BAR-CITY"                    : { "name": "Бар"                              , "regionId":   35, "legacyId": 23, "stateId":    4, "location": {"lat":    49.077621, "lon":   27.6813781} },
  "ZHMERYNKA-CITY"              : { "name": "Жмеринка"                         , "regionId":   35, "legacyId": 23, "stateId":    4, "location": {"lat":   49.0354593, "lon":   28.1147317} },
  "SHARHOROD-CITY"              : { "name": "Шаргород"                         , "regionId":   35, "legacyId": 23, "stateId":    4, "location": {"lat":   48.7498267, "lon":     28.08317} },
  "MOHYLIV-PODILSKYI-DSTR"      : { "name": "Могилів-Подільський район"        , "regionId":   33, "legacyId": 23, "stateId":    4, "location": {"lat":   48.4946015, "lon":    27.903484} },
  "MOHYLIV-PODILSKYI-CITY"      : { "name": "Могилів-Подільський"              , "regionId":   33, "legacyId": 23, "stateId":    4, "location": {"lat":    48.442544, "lon":   27.7991124} },
  "MURAVANIKURYLIVTSI-CITY"     : { "name": "Муровані Курилівці"               , "regionId":   33, "legacyId": 23, "stateId":    4, "location": {"lat":   48.7130055, "lon":   27.5355762} },
  "CHERNIVTSI-VIN-CITY"         : { "name": "Чернівці"                         , "regionId": 1542, "legacyId": 25, "stateId":   26, "location": {"lat":   48.2864702, "lon":   25.9376532} },
  "YAMPIL-CITY"                 : { "name": "Ямпіль"                           , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":   48.2455558, "lon":   28.2852657} },
  "TULCHYNSKYI-DSTR"            : { "name": "Тульчинський район"               , "regionId":   32, "legacyId": 23, "stateId":    4, "location": {"lat":    48.500722, "lon":   28.6465137} },
  "KRYZHOPIL-CITY"              : { "name": "Крижопіль"                        , "regionId":   32, "legacyId": 23, "stateId":    4, "location": {"lat":     48.38568, "lon":     28.86941} },
  "PISHCHANKA-CITY"             : { "name": "Піщанка"                          , "regionId":   32, "legacyId": 23, "stateId":    4, "location": {"lat":   48.2077558, "lon":   28.8864581} },
  "TOMASHPIL-CITY"              : { "name": "Томашпіль"                        , "regionId":   32, "legacyId": 23, "stateId":    4, "location": {"lat":   48.5487589, "lon":   28.5188146} },
  "TULCHYN-CITY"                : { "name": "Тульчин"                          , "regionId":   32, "legacyId": 23, "stateId":    4, "location": {"lat":   48.6730485, "lon":   28.8569476} },
  "KHMILNYTSKYI-DSTR"           : { "name": "Хмільницький район"               , "regionId":   34, "legacyId": 23, "stateId":    4, "location": {"lat":   49.6142436, "lon":   28.3944358} },
  "KALYNIVKA-CITY"              : { "name": "Калинівка"                        , "regionId":   34, "legacyId": 23, "stateId":    4, "location": {"lat":   49.4583688, "lon":   28.5262638} },
  "KOZIATYN-CITY"               : { "name": "Козятин"                          , "regionId":   34, "legacyId": 23, "stateId":    4, "location": {"lat":   49.7195867, "lon":   28.8354279} },
  "HMILNIK-CITY"                : { "name": "Хмільник"                         , "regionId":   34, "legacyId": 23, "stateId":    4, "location": {"lat":    49.556175, "lon":   27.9491205} },
  "DNIPROPETROVSKAYA"           : { "name": "Дніпропетровська область"         , "regionId":    9, "legacyId": 19, "stateId":    9, "location": {"lat":    48.662589, "lon":   34.9501715} },
  "DNIPROVSKYI-DSTR"            : { "name": "Дніпровський район"               , "regionId":   44, "legacyId": 19, "stateId":    9, "location": {"lat":   48.5204464, "lon":   34.9683798} },
  "DNIPRO-CITY"                 : { "name": "Дніпро"                           , "regionId":  332, "legacyId": 19, "stateId":    9, "location": {"lat":   51.5567163, "lon":   30.6121981} },
  "PETRYKIVKA-CITY"             : { "name": "Петриківка"                       , "regionId":   44, "legacyId": 19, "stateId":    9, "location": {"lat":   48.7222177, "lon":   34.6232386} },
  "SOLONE-CITY"                 : { "name": "Солоне"                           , "regionId":   44, "legacyId": 19, "stateId":    9, "location": {"lat":     48.20423, "lon":     34.87713} },
  "TSARYCHANKA-CITY"            : { "name": "Царичанка"                        , "regionId":   44, "legacyId": 19, "stateId":    9, "location": {"lat":      48.9434, "lon":     34.48986} },
  "KAMIANSKYI-DSTR"             : { "name": "Кам'янський район"                , "regionId":   42, "legacyId": 19, "stateId":    9, "location": {"lat":   48.4812911, "lon":   34.1160828} },
  "VERKHNIODNIPROVSK-CITY"      : { "name": "Верхньодніпровськ"                , "regionId":   42, "legacyId": 19, "stateId":    9, "location": {"lat":   48.6541915, "lon":   34.3347779} },
  "VERHIVCEVE-CITY"             : { "name": "Верхівцеве"                       , "regionId":   42, "legacyId": 19, "stateId":    9, "location": {"lat":     48.48404, "lon":     34.24232} },
  "VILNOGIRSK-CITY"             : { "name": "Вільногірськ"                     , "regionId":   42, "legacyId": 19, "stateId":    9, "location": {"lat":     48.49365, "lon":     34.02328} },
  "KAMIANSKE-CITY"              : { "name": "Кам'янське"                       , "regionId":   42, "legacyId": 19, "stateId":    9, "location": {"lat":   48.5167748, "lon":   34.6068797} },
  "KRYNYCHKY-CITY"              : { "name": "Кринички"                         , "regionId":   42, "legacyId": 19, "stateId":    9, "location": {"lat":   48.3747353, "lon":   34.4569858} },
  "PIATYKHATKY-CITY"            : { "name": "П’ятихатки"                       , "regionId":   42, "legacyId": 19, "stateId":    9, "location": {"lat":   48.4124572, "lon":   33.7056731} },
  "KRYVORIZKYI-DSTR"            : { "name": "Криворізький район"               , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":   47.8877981, "lon":   33.5456276} },
  "APOSTOLOVE-CITY"             : { "name": "Апостолове"                       , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":   47.6617478, "lon":   33.7180001} },
  "VELIKA-KOSTROMKA-CITY"       : { "name": "Велика Долина"                    , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":    47.534032, "lon":   33.7220079} },
  "ZELENODOLSK-CITY"            : { "name": "Зеленодольськ"                    , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":   47.5668051, "lon":   33.6474574} },
  "KRYVYOI-RIH-CITY"            : { "name": "Кривий Ріг"                       , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":   47.9102734, "lon":   33.3917703} },
  "MAR-YANSKE-CITY"             : { "name": "Мар'янське"                       , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":    49.907786, "lon":   33.7197768} },
  "SOFIIVKA-CITY"               : { "name": "Софіївка"                         , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":    48.270333, "lon":    38.144668} },
  "SHYROKE-CITY"                : { "name": "Широке"                           , "regionId":   46, "legacyId": 19, "stateId":    9, "location": {"lat":     47.95738, "lon":      38.2307} },
  "NIKOPOLSKYI-DSTR"            : { "name": "Нікопольський район"              , "regionId":   47, "legacyId": 19, "stateId":    9, "location": {"lat":   47.7506635, "lon":   34.4912406} },
  "MARHANETS-CITY"              : { "name": "Марганець"                        , "regionId":   47, "legacyId": 19, "stateId":    9, "location": {"lat":   47.6490555, "lon":    34.649194} },
  "NIKOPOL-CITY"                : { "name": "Нікополь"                         , "regionId":   47, "legacyId": 19, "stateId":    9, "location": {"lat":   47.5692061, "lon":   34.3917272} },
  "POKROV-CITY"                 : { "name": "Покров"                           , "regionId":   47, "legacyId": 19, "stateId":    9, "location": {"lat":   47.6546589, "lon":   34.1149341} },
  "TOMAKIVKA-CITY"              : { "name": "Томаківка"                        , "regionId":   47, "legacyId": 19, "stateId":    9, "location": {"lat":   47.8071544, "lon":   34.7474529} },
  "PAVLOHRADSKYI-DSTR"          : { "name": "Павлоградський район"             , "regionId":   45, "legacyId": 19, "stateId":    9, "location": {"lat":   48.6426211, "lon":    35.911844} },
  "VASYLKIVKA-CITY"             : { "name": "Васильківка"                      , "regionId":   45, "legacyId": 19, "stateId":    9, "location": {"lat":   48.2060218, "lon":   36.0412144} },
  "PAVLOHRAD-CITY"              : { "name": "Павлоград"                        , "regionId":   45, "legacyId": 19, "stateId":    9, "location": {"lat":   48.5316759, "lon":   35.8703695} },
  "YURIVKA-CITY"                : { "name": "Юр’ївка"                          , "regionId":   45, "legacyId": 19, "stateId":    9, "location": {"lat":    48.494937, "lon":   38.9653011} },
  "NOVOMOSKOVSKYI-DSTR"         : { "name": "Новомосковський район"            , "regionId":   43, "legacyId": 19, "stateId":    9, "location": {"lat":   48.8092517, "lon":   35.2881431} },
  "MAHDALYNIVKA-CITY"           : { "name": "Магдалинівка"                     , "regionId":   43, "legacyId": 19, "stateId":    9, "location": {"lat":   48.9145571, "lon":   34.9291661} },
  "NOVOMOSKOVSK-CITY"           : { "name": "Самар"                            , "regionId":   43, "legacyId": 19, "stateId":    9, "location": {"lat":   48.6317447, "lon":   35.2245396} },
  "SYNELNYKIVSKYI-DSTR"         : { "name": "Синельниківський район"           , "regionId":   48, "legacyId": 19, "stateId":    9, "location": {"lat":   48.2395358, "lon":   36.0605474} },
  "MEZHOVA-CITY"                : { "name": "Межова"                           , "regionId":   48, "legacyId": 19, "stateId":    9, "location": {"lat":   48.2553506, "lon":   36.7322839} },
  "NOVOPAVLIVKA-CITY"           : { "name": "Новопавлівка"                     , "regionId":   48, "legacyId": 19, "stateId":    9, "location": {"lat":     48.24869, "lon":     37.22614} },
  "PETROPAVLIVKA-CITY"          : { "name": "Петропавлівка"                    , "regionId":   48, "legacyId": 19, "stateId":    9, "location": {"lat":     48.80813, "lon":     39.26685} },
  "POKROVSKE"                   : { "name": "Покровське"                       , "regionId":   48, "legacyId": 19, "stateId":    9, "location": {"lat":   47.9808528, "lon":   36.2333808} },
  "SINELNIKOVO-CITY"            : { "name": "Синельникове"                     , "regionId":   48, "legacyId": 19, "stateId":    9, "location": {"lat":   48.3269304, "lon":   35.5246984} },
  "PERSHOTRAVNENSK-CITY"        : { "name": "Шахтарське"                       , "regionId":   48, "legacyId": 19, "stateId":    9, "location": {"lat":   48.3505864, "lon":    36.402296} },
  "DONETSKAYA"                  : { "name": "Донецька область"                 , "regionId":   28, "legacyId": 13, "stateId":   28, "location": {"lat":   47.9212914, "lon":   37.7809825} },
  "BAKHMUTSKYI-DSTR"            : { "name": "Бахмутський район"                , "regionId":   54, "legacyId": 13, "stateId":   28, "location": {"lat":   48.6497545, "lon":   38.0225476} },
  "BAKHMUT-CITY"                : { "name": "Бахмут"                           , "regionId":   54, "legacyId": 13, "stateId":   28, "location": {"lat":   48.5894123, "lon":   38.0020994} },
  "SVITLODARSK-CITY"            : { "name": "Світлодарськ"                     , "regionId":   54, "legacyId": 13, "stateId":   28, "location": {"lat":     48.43803, "lon":     38.22349} },
  "SOLEDAR-CITY"                : { "name": "Соледар"                          , "regionId":   54, "legacyId": 13, "stateId":   28, "location": {"lat":   48.6956698, "lon":   38.0671791} },
  "TORECK-CITY"                 : { "name": "Торецьк"                          , "regionId":   54, "legacyId": 13, "stateId":   28, "location": {"lat":   48.3970469, "lon":   37.8501378} },
  "CHASIV-YAR-CITY"             : { "name": "Часів Яр"                         , "regionId":   54, "legacyId": 13, "stateId":   28, "location": {"lat":   48.5873911, "lon":   37.8373367} },
  "VOLNOVASKYI-DSTR"            : { "name": "Волноваський район"               , "regionId":   55, "legacyId": 13, "stateId":   28, "location": {"lat":   47.7161651, "lon":   37.1578646} },
  "VELIKA-NOVOSILKA-CITY"       : { "name": "Велика Новосілка"                 , "regionId":   55, "legacyId": 13, "stateId":   28, "location": {"lat":   47.8436751, "lon":   36.8396472} },
  "VUGLEDAR-CITY"               : { "name": "Вугледар"                         , "regionId":   55, "legacyId": 13, "stateId":   28, "location": {"lat":   47.7809924, "lon":   37.2460771} },
  "HORLIVSKYI-DSTR"             : { "name": "Горлівський район"                , "regionId":   51, "legacyId": 13, "stateId":   28, "location": {"lat":   48.1719554, "lon":   38.3761575} },
  "IENAKIIEVE-CITY"             : { "name": "Єнакієве"                         , "regionId":   51, "legacyId": 13, "stateId":   28, "location": {"lat":   48.2305107, "lon":    38.185045} },
  "HORLIVKA-CITY"               : { "name": "Горлівка"                         , "regionId":   51, "legacyId": 13, "stateId":   28, "location": {"lat":   48.3058686, "lon":   38.0027664} },
  "SNIZHNE-CITY"                : { "name": "Сніжне"                           , "regionId":   51, "legacyId": 13, "stateId":   28, "location": {"lat":   48.0220754, "lon":   38.7634612} },
  "CHYSTIAKOVE-CITY"            : { "name": "Чистякове"                        , "regionId":   51, "legacyId": 13, "stateId":   28, "location": {"lat":   48.0261217, "lon":    38.618137} },
  "SHAKHTARSK-CITY"             : { "name": "Шахтарськ"                        , "regionId":   51, "legacyId": 13, "stateId":   28, "location": {"lat":   48.0550423, "lon":   38.4459474} },
  "DONETSKYI-DSTR"              : { "name": "Донецький район"                  , "regionId":   53, "legacyId": 13, "stateId":   28, "location": {"lat":   47.9076011, "lon":   38.2070319} },
  "DONETSK-CITY"                : { "name": "Донецьк"                          , "regionId":   53, "legacyId": 13, "stateId":   28, "location": {"lat":   48.0158753, "lon":   37.8013407} },
  "MAKIIVKA-CITY"               : { "name": "Макіївка"                         , "regionId":   53, "legacyId": 13, "stateId":   28, "location": {"lat":   48.0448144, "lon":   37.9635093} },
  "KHARTSYZK-CITY"              : { "name": "Харцизьк"                         , "regionId":   53, "legacyId": 13, "stateId":   28, "location": {"lat":   48.0339524, "lon":    38.149804} },
  "KALMIUSKYI-DSTR"             : { "name": "Кальміуський район"               , "regionId":   49, "legacyId": 13, "stateId":   28, "location": {"lat":   47.4729328, "lon":   38.0970005} },
  "KALMIUSKE-CITY"              : { "name": "Кальміуське"                      , "regionId":   49, "legacyId": 13, "stateId":   28, "location": {"lat":   47.6687951, "lon":   38.0739208} },
  "KRAMATORSKYI-DSTR"           : { "name": "Краматорський район"              , "regionId":   50, "legacyId": 13, "stateId":   28, "location": {"lat":   48.7476967, "lon":   37.4275175} },
  "DRUZHKIVKA-CITY"             : { "name": "Дружківка"                        , "regionId":   50, "legacyId": 13, "stateId":   28, "location": {"lat":   48.6198614, "lon":    37.524945} },
  "KOSTIANTYNIVKA-CITY"         : { "name": "Костянтинівка"                    , "regionId":   50, "legacyId": 13, "stateId":   28, "location": {"lat":    48.534905, "lon":   37.6923754} },
  "KRAMATORSK-CITY"             : { "name": "Краматорськ"                      , "regionId":   50, "legacyId": 13, "stateId":   28, "location": {"lat":   48.7389415, "lon":   37.5843812} },
  "LIMAN-CITY"                  : { "name": "Лиман"                            , "regionId":   50, "legacyId": 13, "stateId":   28, "location": {"lat":   48.9801314, "lon":   37.8168012} },
  "SVYATOGIRSK-CITY"            : { "name": "Святогірськ"                      , "regionId":   50, "legacyId": 13, "stateId":   28, "location": {"lat":   49.0355675, "lon":   37.5653551} },
  "SLOVIANSK-CITY"              : { "name": "Слов'янськ"                       , "regionId":   50, "legacyId": 13, "stateId":   28, "location": {"lat":   48.8522691, "lon":   37.6058241} },
  "MARIUPOLSKYI-DSTR"           : { "name": "Маріупольський район"             , "regionId":   52, "legacyId": 13, "stateId":   28, "location": {"lat":   47.1676099, "lon":    37.402692} },
  "MARIUPOL-CITY"               : { "name": "Маріуполь"                        , "regionId":   52, "legacyId": 13, "stateId":   28, "location": {"lat":   47.0957648, "lon":   37.5499621} },
  "POKROVSKYI-DSTR"             : { "name": "Покровський район"                , "regionId":   56, "legacyId": 13, "stateId":   28, "location": {"lat":   48.2039822, "lon":   37.4461031} },
  "AVDIYIVKA-CITY"              : { "name": "Авдіївка"                         , "regionId":   56, "legacyId": 13, "stateId":   28, "location": {"lat":   48.1338824, "lon":   37.7466719} },
  "DOBROPILLYA-CITY"            : { "name": "Добропілля"                       , "regionId":   56, "legacyId": 13, "stateId":   28, "location": {"lat":   48.4683035, "lon":   37.0903243} },
  "KURAHOVE-CITY"               : { "name": "Курахове"                         , "regionId":   56, "legacyId": 13, "stateId":   28, "location": {"lat":   47.9835214, "lon":   37.2826414} },
  "MAR-YINKA-CITY"              : { "name": "Мар'їнка"                         , "regionId":   56, "legacyId": 13, "stateId":   28, "location": {"lat":   47.9401242, "lon":   37.5022312} },
  "MYRNOHRAD-CITY"              : { "name": "Мирноград"                        , "regionId":   56, "legacyId": 13, "stateId":   28, "location": {"lat":     48.30791, "lon":      37.2591} },
  "POKROVSK-CITY"               : { "name": "Покровськ"                        , "regionId":   56, "legacyId": 13, "stateId":   28, "location": {"lat":   48.2771086, "lon":   37.1772482} },
  "ZHYTOMYRSKA"                 : { "name": "Житомирська область"              , "regionId":   10, "legacyId":  7, "stateId":   10, "location": {"lat":   50.9080532, "lon":   28.3867504} },
  "BERDYCHIVSKYI-DSTR"          : { "name": "Бердичівський район"              , "regionId":   57, "legacyId":  7, "stateId":   10, "location": {"lat":   49.8687337, "lon":   28.4967909} },
  "ANDRUSHIVKA-CITY"            : { "name": "Андрушівка"                       , "regionId":   57, "legacyId":  7, "stateId":   10, "location": {"lat":   50.0301392, "lon":   29.0222111} },
  "BERDYCHIV-CITY"              : { "name": "Бердичів"                         , "regionId":   57, "legacyId":  7, "stateId":   10, "location": {"lat":   49.8940442, "lon":   28.5814912} },
  "RUZHYN-CITY"                 : { "name": "Ружин"                            , "regionId":   57, "legacyId":  7, "stateId":   10, "location": {"lat":   49.7230517, "lon":   29.2095565} },
  "ZHYTOMYRSKYI-DSTR"           : { "name": "Житомирський район"               , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.2478799, "lon":   28.7751975} },
  "BRUSYLIV-CITY"               : { "name": "Брусилів"                         , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":     50.28305, "lon":     29.51889} },
  "ZHYTOMYR-CITY"               : { "name": "Житомир"                          , "regionId":  442, "legacyId":  7, "stateId":   10, "location": {"lat":   50.2601065, "lon":   28.6696281} },
  "KOROSTYSHIV-CITY"            : { "name": "Коростишів"                       , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.3201518, "lon":   29.0584885} },
  "LIUBAR-CITY"                 : { "name": "Любар"                            , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   49.9231632, "lon":   27.7487535} },
  "OZERNE-CITY"                 : { "name": "Озерне"                           , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.1808751, "lon":    28.735195} },
  "POPILNIA-CITY"               : { "name": "Попільня"                         , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   49.9452183, "lon":   29.4592233} },
  "PULYNY-CITY"                 : { "name": "Пулини"                           , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.4690331, "lon":    28.270617} },
  "RADOMISHL-CITY"              : { "name": "Радомишль"                        , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.4961812, "lon":   29.2289588} },
  "RADOMYSHL-CITY"              : { "name": "Радомишль"                        , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.4961812, "lon":   29.2289588} },
  "ROMANIV-CITY"                : { "name": "Романів"                          , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.1476608, "lon":   27.9313692} },
  "KHOROSHIV-CITY"              : { "name": "Хорошів"                          , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.5959845, "lon":    28.445337} },
  "CHERNIAKHIV-CITY"            : { "name": "Черняхів"                         , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":     50.45299, "lon":     28.66573} },
  "CHUDNIV-CITY"                : { "name": "Чуднів"                           , "regionId":   59, "legacyId":  7, "stateId":   10, "location": {"lat":   50.0524287, "lon":   28.1153765} },
  "NOVOHRAD-VOLYNSKYI-DSTR"     : { "name": "Звягельський район"               , "regionId":   60, "legacyId":  7, "stateId":   10, "location": {"lat":   50.6262055, "lon":   27.7007816} },
  "YEMILCHYNE-CITY"             : { "name": "Ємільчине"                        , "regionId":   60, "legacyId":  7, "stateId":   10, "location": {"lat":    50.872091, "lon":   27.8047443} },
  "BARANIVKA-CITY"              : { "name": "Баранівка"                        , "regionId":   60, "legacyId":  7, "stateId":   10, "location": {"lat":     50.29369, "lon":     27.66666} },
  "NOVOHRAD-VOLYNSKYOI-CITY"    : { "name": "Звягель"                          , "regionId":   60, "legacyId":  7, "stateId":   10, "location": {"lat":   50.5917622, "lon":   27.6066973} },
  "KOROSTENSKYI-DSTR"           : { "name": "Коростенський район"              , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":   51.1623642, "lon":   28.3447957} },
  "IRSHANSK-CITY"               : { "name": "Іршанськ"                         , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":   50.7504379, "lon":    28.721134} },
  "KOROSTEN-CITY"               : { "name": "Коростень"                        , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":   50.9491068, "lon":   28.6417552} },
  "LUHYNY-CITY"                 : { "name": "Лугини"                           , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":     51.07853, "lon":      28.3976} },
  "MALYN-CITY"                  : { "name": "Малин"                            , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":   50.7677902, "lon":   29.2414346} },
  "NARODYCHI-CITY"              : { "name": "Народичі"                         , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":   51.2024469, "lon":   29.0808107} },
  "OVRUCK-CITY"                 : { "name": "Овруч"                            , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":   51.3259771, "lon":   28.8026718} },
  "OLEVSK-CITY"                 : { "name": "Олевськ"                          , "regionId":   58, "legacyId":  7, "stateId":   10, "location": {"lat":     51.22272, "lon":     27.64881} },
  "ZAKARPATSKA"                 : { "name": "Закарпатська область"             , "regionId":   11, "legacyId":  1, "stateId":   11, "location": {"lat":   48.2953664, "lon":   23.4466092} },
  "BEREHIVSKYI-DSTR"            : { "name": "Берегівський район"               , "regionId":   61, "legacyId":  1, "stateId":   11, "location": {"lat":   48.1798175, "lon":    22.873873} },
  "BEREHOVE-CITY"               : { "name": "Берегове"                         , "regionId":   61, "legacyId":  1, "stateId":   11, "location": {"lat":   48.2050985, "lon":   22.6453246} },
  "VYNOHRADIV-CITY"             : { "name": "Виноградів"                       , "regionId":   61, "legacyId":  1, "stateId":   11, "location": {"lat":    48.140417, "lon":   23.0360182} },
  "MUKACHIVSKYI-DSTR"           : { "name": "Мукачівський район"               , "regionId":   65, "legacyId":  1, "stateId":   11, "location": {"lat":   48.6028594, "lon":   22.9252171} },
  "VOLOVETS-CITY"               : { "name": "Воловець"                         , "regionId":   65, "legacyId":  1, "stateId":   11, "location": {"lat":   48.7146406, "lon":   23.1888322} },
  "MUKACHEVO-CITY"              : { "name": "Мукачево"                         , "regionId":   65, "legacyId":  1, "stateId":   11, "location": {"lat":   48.4421119, "lon":   22.7185408} },
  "SVALIAVA-CITY"               : { "name": "Свалява"                          , "regionId":   65, "legacyId":  1, "stateId":   11, "location": {"lat":   48.5460735, "lon":   22.9895489} },
  "RAKHIVSKYI-DSTR"             : { "name": "Рахівський район"                 , "regionId":   63, "legacyId":  1, "stateId":   11, "location": {"lat":    48.147406, "lon":   24.2366795} },
  "RAKHIV-CITY"                 : { "name": "Рахів"                            , "regionId":   63, "legacyId":  1, "stateId":   11, "location": {"lat":   48.0556765, "lon":   24.2057063} },
  "TIACHIVSKYI-DSTR"            : { "name": "Тячівський район"                 , "regionId":   64, "legacyId":  1, "stateId":   11, "location": {"lat":   48.2474081, "lon":   23.8111468} },
  "TIACHIV-CITY"                : { "name": "Тячів"                            , "regionId":   64, "legacyId":  1, "stateId":   11, "location": {"lat":     48.01163, "lon":   23.5783799} },
  "UZHHORODSKYI-DSTR"           : { "name": "Ужгородський район"               , "regionId":   66, "legacyId":  1, "stateId":   11, "location": {"lat":   48.7257783, "lon":   22.6098018} },
  "VELYKYI-BEREZNYI-CITY"       : { "name": "Великий Березний"                 , "regionId":   66, "legacyId":  1, "stateId":   11, "location": {"lat":     48.88985, "lon":     22.45812} },
  "PERECHYN-CITY"               : { "name": "Перечин"                          , "regionId":   66, "legacyId":  1, "stateId":   11, "location": {"lat":     48.73707, "lon":     22.48764} },
  "UZHHOROD-CITY"               : { "name": "Ужгород"                          , "regionId":  500, "legacyId":  1, "stateId":   11, "location": {"lat":   48.6223731, "lon":   22.3022572} },
  "KHUSTSKYI-DSTR"              : { "name": "Хустський район"                  , "regionId":   62, "legacyId":  1, "stateId":   11, "location": {"lat":   48.3691737, "lon":   23.3201295} },
  "IRSHAVA-CITY"                : { "name": "Іршава"                           , "regionId":   62, "legacyId":  1, "stateId":   11, "location": {"lat":    48.439656, "lon":   22.9747006} },
  "MIZHHIRIA-CITY"              : { "name": "Міжгір’я"                         , "regionId":   62, "legacyId":  1, "stateId":   11, "location": {"lat":   48.5281184, "lon":   23.5009289} },
  "KHUST-CITY"                  : { "name": "Хуст"                             , "regionId":   62, "legacyId":  1, "stateId":   11, "location": {"lat":   48.1764917, "lon":    23.291166} },
  "ZAPORIZKA"                   : { "name": "Запорізька область"               , "regionId":   12, "legacyId": 14, "stateId":   12, "location": {"lat":   47.4165079, "lon":    35.922969} },
  "BERDIANSKYI-DSTR"            : { "name": "Бердянський район"                , "regionId":  147, "legacyId": 14, "stateId":   12, "location": {"lat":   46.9120891, "lon":   36.5440609} },
  "BERDIANSK-CITY"              : { "name": "Бердянськ"                        , "regionId":  147, "legacyId": 14, "stateId":   12, "location": {"lat":    46.755678, "lon":   36.7887623} },
  "PRYMORSK-CITY"               : { "name": "Приморськ"                        , "regionId":  147, "legacyId": 14, "stateId":   12, "location": {"lat":   46.7126463, "lon":   36.3664164} },
  "CHERNIHIVKA-CITY"            : { "name": "Чернігівка"                       , "regionId":  147, "legacyId": 14, "stateId":   12, "location": {"lat":     47.19486, "lon":      36.2075} },
  "VASYLIVSKYI-DSTR"            : { "name": "Василівський район"               , "regionId":  146, "legacyId": 14, "stateId":   12, "location": {"lat":   47.3705619, "lon":   34.9357658} },
  "VELYKA-BILOZERKA-CITY"       : { "name": "Велика Білозерка"                 , "regionId":  146, "legacyId": 14, "stateId":   12, "location": {"lat":     47.26936, "lon":    34.684521} },
  "ENERHODAR-CITY"              : { "name": "Енергодар"                        , "regionId":  146, "legacyId": 14, "stateId":   12, "location": {"lat":   47.4900575, "lon":   34.6602709} },
  "KAMIANKA-DNIPROVSKA-CITY"    : { "name": "Кам'янка-Дніпровська"             , "regionId":  146, "legacyId": 14, "stateId":   12, "location": {"lat":   47.4900938, "lon":   34.4109101} },
  "MYKHAILIVKA-CITY"            : { "name": "Михайлівка"                       , "regionId":  146, "legacyId": 14, "stateId":   12, "location": {"lat":   48.4967699, "lon":   38.9021342} },
  "ZAPORIZKYI-DSTR"             : { "name": "Запорізький район"                , "regionId":  149, "legacyId": 14, "stateId":   12, "location": {"lat":   47.8247608, "lon":   35.3400244} },
  "BILENKE-CITY"                : { "name": "Біленьке"                         , "regionId":  149, "legacyId": 14, "stateId":   12, "location": {"lat":   48.7592059, "lon":   37.6177633} },
  "VILNIANSK-CITY"              : { "name": "Вільнянськ"                       , "regionId":  149, "legacyId": 14, "stateId":   12, "location": {"lat":   47.9444345, "lon":   35.4390183} },
  "ZAPORIZHZHIA-CITY"           : { "name": "Запоріжжя"                        , "regionId":  564, "legacyId": 14, "stateId":   12, "location": {"lat":   47.8507859, "lon":   35.1182867} },
  "KOMISHUVAHA-CITY"            : { "name": "Комишуваха"                       , "regionId":  149, "legacyId": 14, "stateId":   12, "location": {"lat":     48.64025, "lon":     37.45582} },
  "NOVOMYKHAILIVKA-CITY"        : { "name": "Новомихайлівка"                   , "regionId":  149, "legacyId": 14, "stateId":   12, "location": {"lat":   47.8552316, "lon":   37.4863822} },
  "TAVRIISKE-CITY"              : { "name": "Таврійське"                       , "regionId":  149, "legacyId": 14, "stateId":   12, "location": {"lat":    47.652512, "lon":     35.69733} },
  "MELITOPOLSKYI-DSTR"          : { "name": "Мелітопольський район"            , "regionId":  148, "legacyId": 14, "stateId":   12, "location": {"lat":   46.7331394, "lon":   35.3124202} },
  "VESELE-CITY"                 : { "name": "Веселе"                           , "regionId":  148, "legacyId": 14, "stateId":   12, "location": {"lat":   47.0179164, "lon":   34.9211323} },
  "MELITOPOL-CITY"              : { "name": "Мелітополь"                       , "regionId":  148, "legacyId": 14, "stateId":   12, "location": {"lat":   46.8467267, "lon":   35.3827281} },
  "PRYAZOVSKE-CITY"             : { "name": "Приазовське"                      , "regionId":  148, "legacyId": 14, "stateId":   12, "location": {"lat":   46.7372477, "lon":   35.6405813} },
  "YAKYMIVKA-CITY"              : { "name": "Якимівка"                         , "regionId":  148, "legacyId": 14, "stateId":   12, "location": {"lat":   46.7013037, "lon":   35.1602576} },
  "POLOHIVSKYI-DSTR"            : { "name": "Пологівський район"               , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":   47.4240821, "lon":   36.4483018} },
  "BILMAK-CITY"                 : { "name": "Більмак"                          , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":      47.3624, "lon":     36.65108} },
  "GULYAJPOLE-CITY"             : { "name": "Гуляйполе"                        , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":   47.6655382, "lon":   36.2656849} },
  "KAM-YANKA-CITY"              : { "name": "Кам'янка"                         , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":   49.0401185, "lon":   32.1008691} },
  "ORIHIV-CITY"                 : { "name": "Оріхів"                           , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":   47.5754426, "lon":   35.7855471} },
  "POLOGI-CITY"                 : { "name": "Пологи"                           , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":   47.4784803, "lon":   36.2531412} },
  "ROZIVKA-CITY"                : { "name": "Розівка"                          , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":    47.458549, "lon":   29.3374948} },
  "TOKMAK-CITY"                 : { "name": "Токмак"                           , "regionId":  145, "legacyId": 14, "stateId":   12, "location": {"lat":   47.2550191, "lon":   35.7092206} },
  "KIYEW"                       : { "name": "Київ"                             , "regionId":   31, "legacyId": 26, "stateId":   31, "location": {"lat":   50.4500336, "lon":   30.5241361} },
  "KIYEWSKAYA"                  : { "name": "Київська область"                 , "regionId":   14, "legacyId":  8, "stateId":   14, "location": {"lat":    50.178595, "lon":   30.4924884} },
  "BORYSPILSKYI-DSTR"           : { "name": "Бориспільський район"             , "regionId":   78, "legacyId":  8, "stateId":   14, "location": {"lat":   50.1631027, "lon":   31.0949361} },
  "BORYSPIL-CITY"               : { "name": "Бориспіль"                        , "regionId":   78, "legacyId":  8, "stateId":   14, "location": {"lat":   50.3512101, "lon":     30.95077} },
  "PEREYASLAV-CITY"             : { "name": "Переяслав"                        , "regionId":   78, "legacyId":  8, "stateId":   14, "location": {"lat":   50.0643984, "lon":   31.4447327} },
  "YAGOTIN-CITY"                : { "name": "Яготин"                           , "regionId":   78, "legacyId":  8, "stateId":   14, "location": {"lat":   50.2758913, "lon":   31.7634861} },
  "BROVARSKYI-DSTR"             : { "name": "Броварський район"                , "regionId":   79, "legacyId":  8, "stateId":   14, "location": {"lat":   50.4739896, "lon":   31.5360893} },
  "BARYSHIVKA-CITY"             : { "name": "Баришівка"                        , "regionId":   79, "legacyId":  8, "stateId":   14, "location": {"lat":   50.3645295, "lon":   31.3256722} },
  "BROVARY-CITY"                : { "name": "Бровари"                          , "regionId":   79, "legacyId":  8, "stateId":   14, "location": {"lat":   50.5111168, "lon":   30.7900482} },
  "ZGURIVKA-CITY"               : { "name": "Згурівка"                         , "regionId":   79, "legacyId":  8, "stateId":   14, "location": {"lat":   50.4950666, "lon":   31.7691817} },
  "SEMIPOLKI-CITY"              : { "name": "Семиполки"                        , "regionId":   79, "legacyId":  8, "stateId":   14, "location": {"lat":    50.723526, "lon":    30.946077} },
  "BUCHANSKYI-DSTR"             : { "name": "Бучанський район"                 , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":   50.5449137, "lon":   29.8986825} },
  "IRPIN-CITY"                  : { "name": "Ірпінь"                           , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":   50.5206777, "lon":   30.2448725} },
  "BORODYANKA-CITY"             : { "name": "Бородянка"                        , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":     50.64738, "lon":   29.9173936} },
  "BUCHA-CITY"                  : { "name": "Буча"                             , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":   50.5503127, "lon":   30.2106925} },
  "BILOGORODKA-CITY"            : { "name": "Білогородка"                      , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":    50.390171, "lon":     30.22785} },
  "VISHNEVE-CITY"               : { "name": "Вишневе"                          , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":   50.3917497, "lon":   30.3678999} },
  "VORZEL-CITY"                 : { "name": "Ворзель"                          , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":   50.5457287, "lon":   30.1562891} },
  "GOSTOMEL-CITY"               : { "name": "Гостомель"                        , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":     50.58826, "lon":     30.25909} },
  "MAKARIV-CITY"                : { "name": "Макарів"                          , "regionId":   75, "legacyId":  8, "stateId":   14, "location": {"lat":   50.4639897, "lon":   29.8068986} },
  "BILOTSERKIVSKYI-DSTR"        : { "name": "Білоцерківський район"            , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":   49.6479344, "lon":   30.1050008} },
  "BILA-TSERKVA-CITY"           : { "name": "Біла Церква"                      , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":   49.7969703, "lon":   30.1158069} },
  "VOLODARKA-CITY"              : { "name": "Володарка"                        , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":   49.5224979, "lon":   29.9280475} },
  "SKVIRA-CITY"                 : { "name": "Сквира"                           , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":   49.7337685, "lon":   29.6624138} },
  "STAVYSCHE-CITY"              : { "name": "Ставище"                          , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":   49.3897213, "lon":   30.1921389} },
  "TARASHCHA-CITY"              : { "name": "Тараща"                           , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":    49.555498, "lon":   30.5023421} },
  "TETIIV-CITY"                 : { "name": "Тетіїв"                           , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":   49.3686166, "lon":   29.6771098} },
  "UZIN-CITY"                   : { "name": "Узин"                             , "regionId":   73, "legacyId":  8, "stateId":   14, "location": {"lat":   49.8284745, "lon":   30.4197205} },
  "VYSHHORODSKYI-DSTR"          : { "name": "Вишгородський район"              , "regionId":   74, "legacyId":  8, "stateId":   14, "location": {"lat":   51.0362006, "lon":   29.9910115} },
  "IVANKIV-CITY"                : { "name": "Іванків"                          , "regionId":   74, "legacyId":  8, "stateId":   14, "location": {"lat":   50.9376396, "lon":   29.8978571} },
  "VISHGOROD-CITY"              : { "name": "Вишгород"                         , "regionId":   74, "legacyId":  8, "stateId":   14, "location": {"lat":   50.5824332, "lon":    30.485121} },
  "DYMER-CITY"                  : { "name": "Димер"                            , "regionId":   74, "legacyId":  8, "stateId":   14, "location": {"lat":   50.7863705, "lon":   30.3036843} },
  "POLISKE-CITY"                : { "name": "Поліське"                         , "regionId":   74, "legacyId":  8, "stateId":   14, "location": {"lat":    51.240486, "lon":     29.38896} },
  "SLAVUTICH-CITY"              : { "name": "Славутич"                         , "regionId":   74, "legacyId":  8, "stateId":   14, "location": {"lat":   51.5201397, "lon":   30.7562301} },
  "OBUKHIVSKYI-DSTR"            : { "name": "Обухівський район"                , "regionId":   76, "legacyId":  8, "stateId":   14, "location": {"lat":   49.8792055, "lon":   30.9335568} },
  "BOHUSLAV-CITY"               : { "name": "Богуслав"                         , "regionId":   76, "legacyId":  8, "stateId":   14, "location": {"lat":     49.54765, "lon":      30.8733} },
  "VASYLKIV-CITY"               : { "name": "Васильків"                        , "regionId":   76, "legacyId":  8, "stateId":   14, "location": {"lat":    50.178137, "lon":   30.3175045} },
  "KAGARLIK-CITY"               : { "name": "Кагарлик"                         , "regionId":   76, "legacyId":  8, "stateId":   14, "location": {"lat":   49.8650658, "lon":   30.8226786} },
  "MIRONIVKA-CITY"              : { "name": "Миронівка"                        , "regionId":   76, "legacyId":  8, "stateId":   14, "location": {"lat":   49.6583412, "lon":   30.9824887} },
  "OBUHIV-CITY"                 : { "name": "Обухів"                           , "regionId":   76, "legacyId":  8, "stateId":   14, "location": {"lat":   50.1101633, "lon":   30.6269696} },
  "RZHYSHCHIV-CITY"             : { "name": "Ржищів"                           , "regionId":   76, "legacyId":  8, "stateId":   14, "location": {"lat":     49.96822, "lon":     31.04118} },
  "FASTIVSKYI-DSTR"             : { "name": "Фастівський район"                , "regionId":   77, "legacyId":  8, "stateId":   14, "location": {"lat":   50.1405424, "lon":    29.942547} },
  "BOIARKA-CITY"                : { "name": "Боярка"                           , "regionId":   77, "legacyId":  8, "stateId":   14, "location": {"lat":   50.3356709, "lon":   30.2847595} },
  "FASTIV-CITY"                 : { "name": "Фастів"                           , "regionId":   77, "legacyId":  8, "stateId":   14, "location": {"lat":   50.0799307, "lon":   29.9162821} },
  "KRIMEA"                      : { "name": "Автономна Республіка Крим"        , "regionId": 9999, "legacyId": 16, "stateId": 9999, "location": {"lat":   45.6856952, "lon":   33.9329411} },
  "YEVPATORIISKYI-DSTR"         : { "name": "Євпаторійський район"             , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.3511857, "lon":   33.4262698} },
  "YEVPATORIIA-CITY"            : { "name": "Євпаторія"                        , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.1907635, "lon":   33.3679049} },
  "BAKHCHYSARAISKYI-DSTR"       : { "name": "Бахчисарайський район"            , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   44.6768054, "lon":   33.9790105} },
  "BAKHCHYSARAI-CITY"           : { "name": "Бахчисарай"                       , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   44.7451986, "lon":    33.848728} },
  "BILOHIRSKYI-DSTR"            : { "name": "Білогірський район"               , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.0635762, "lon":   34.5928321} },
  "BILOHIRSK-CITY"              : { "name": "Білогірськ"                       , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.0584385, "lon":    34.594959} },
  "DZHANKOISKYI-DSTR"           : { "name": "Джанкойський район"               , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.8195325, "lon":   34.4378963} },
  "DZHANKOJ-CITY"               : { "name": "Джанкой"                          , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.7119746, "lon":   34.3927394} },
  "KERCHENSKYI-DSTR"            : { "name": "Керченський район"                , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.3805589, "lon":   36.3407614} },
  "KERCH-CITY"                  : { "name": "Керч"                             , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.3563405, "lon":    36.467061} },
  "SEVASTOPOL-CITY"             : { "name": "Севастополь"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   44.6054434, "lon":   33.5220842} },
  "KURMANSKYI-DSTR"             : { "name": "Курманський район"                , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.4223602, "lon":   34.2882404} },
  "KURMAN-CITY"                 : { "name": "Курман"                           , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.4959593, "lon":   34.2950929} },
  "PEREKOPSKYI-DSTR"            : { "name": "Перекопський район"               , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.9851269, "lon":   33.8452384} },
  "YANY-KAPU-CITY"              : { "name": "Яни Капу"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.9568404, "lon":   33.7974907} },
  "SIMFEROPOLSKYI-DSTR"         : { "name": "Сімферопольський район"           , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":    44.988397, "lon":   33.9850873} },
  "SIMFEROPOL-CITY"             : { "name": "Сімферополь"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   44.9521459, "lon":   34.1024858} },
  "FEODOSIISKYI-DSTR"           : { "name": "Феодосійський район"              , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   45.1901535, "lon":   35.0966297} },
  "FEODOSIIA-CITY"              : { "name": "Феодосія"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":    45.033669, "lon":   35.3753628} },
  "YALTYNSKYI-DSTR"             : { "name": "Ялтинський район"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   44.6433893, "lon":   34.3277224} },
  "YALTA-CITY"                  : { "name": "Ялта"                             , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   44.4970713, "lon":   34.1586871} },
  "KIROWOGRADSKA"               : { "name": "Кіровоградська область"           , "regionId":   15, "legacyId": 22, "stateId":   15, "location": {"lat":   48.1916774, "lon":   31.6902953} },
  "HOLOVANIVSKYI-DSTR"          : { "name": "Голованівський район"             , "regionId":   82, "legacyId": 22, "stateId":   15, "location": {"lat":   48.4561282, "lon":   30.4679377} },
  "GOLOVANIVSK-CITY"            : { "name": "Голованівськ"                     , "regionId":   82, "legacyId": 22, "stateId":   15, "location": {"lat":   48.3830239, "lon":   30.4655894} },
  "KROPYVNYTSKYI-DSTR"          : { "name": "Кропивницький район"              , "regionId":   81, "legacyId": 22, "stateId":   15, "location": {"lat":    48.416213, "lon":   32.5014999} },
  "BOBRYNETS-CITY"              : { "name": "Бобринець"                        , "regionId":   81, "legacyId": 22, "stateId":   15, "location": {"lat":     48.05729, "lon":     32.15938} },
  "DOLYNSKA-CITY"               : { "name": "Долинська"                        , "regionId":   81, "legacyId": 22, "stateId":   15, "location": {"lat":     48.11282, "lon":   32.7699103} },
  "ZNAMIANKA-CITY"              : { "name": "Знам’янка"                        , "regionId":   81, "legacyId": 22, "stateId":   15, "location": {"lat":   48.7199609, "lon":   32.6659476} },
  "KROPYVNYTSKYOI-CITY"         : { "name": "Кропивницький"                    , "regionId":  761, "legacyId": 22, "stateId":   15, "location": {"lat":   48.5105805, "lon":   32.2656283} },
  "NOVOUKRAINSKYI-DSTR"         : { "name": "Новоукраїнський район"            , "regionId":   83, "legacyId": 22, "stateId":   15, "location": {"lat":   48.5003433, "lon":   31.3766601} },
  "NOVOUKRAYINSK-CITY"          : { "name": "Новоукраїнка"                     , "regionId":   83, "legacyId": 22, "stateId":   15, "location": {"lat":   48.3250616, "lon":    31.522047} },
  "OLEKSANDRIISKYI-DSTR"        : { "name": "Олександрійський район"           , "regionId":   80, "legacyId": 22, "stateId":   15, "location": {"lat":   48.6694606, "lon":   33.2848908} },
  "OLEKSANDRIIA-CITY"           : { "name": "Олександрія"                      , "regionId":   80, "legacyId": 22, "stateId":   15, "location": {"lat":    48.670609, "lon":   33.1169742} },
  "ONUFRIIVKA-CITY"             : { "name": "Онуфріївка"                       , "regionId":   80, "legacyId": 22, "stateId":   15, "location": {"lat":   48.9046489, "lon":   33.4472744} },
  "SVITLOVODSK-CITY"            : { "name": "Світловодськ"                     , "regionId":   80, "legacyId": 22, "stateId":   15, "location": {"lat":     49.04537, "lon":     33.20721} },
  "LUGANSKA"                    : { "name": "Луганська область"                , "regionId":   16, "legacyId": 12, "stateId":   16, "location": {"lat":   49.2724587, "lon":   38.9150477} },
  "ALCHEVSKYI-DSTR"             : { "name": "Алчевський район"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.5110909, "lon":   38.7696715} },
  "ALCHEVSK-CITY"               : { "name": "Алчевськ"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.4701987, "lon":   38.8010178} },
  "BRIANKA-CITY"                : { "name": "Брянка"                           , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":     48.50361, "lon":     38.66432} },
  "KADIIVKA-CITY"               : { "name": "Кадіївка"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.5595971, "lon":   38.6499847} },
  "DOVZHANSKYI-DSTR"            : { "name": "Довжанський район"                , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":    48.209041, "lon":   39.7741686} },
  "DOVZHANSK-CITY"              : { "name": "Довжанськ"                        , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.0811324, "lon":    39.642561} },
  "LUHANSKYI-DSTR"              : { "name": "Луганський район"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.4756187, "lon":   39.3673717} },
  "LUHANSK-CITY"                : { "name": "Луганськ"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.5717084, "lon":   39.2973153} },
  "ROVENKIVSKYI-DSTR"           : { "name": "Ровеньківський район"             , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.1146468, "lon":   39.1188316} },
  "ANTRATSYT-CITY"              : { "name": "Антрацит"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.1164285, "lon":   39.0886375} },
  "ROVENKY-CITY"                : { "name": "Ровеньки"                         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.0897987, "lon":    39.368029} },
  "KHRUSTALNYOI-CITY"           : { "name": "Хрустальний"                      , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.1351471, "lon":   38.9198948} },
  "SVATIVSKYI-DSTR"             : { "name": "Сватівський район"                , "regionId":   85, "legacyId": 12, "stateId":   16, "location": {"lat":   49.6078899, "lon":   38.4240131} },
  "RUBIZHNE-CITY"               : { "name": "Рубіжне"                          , "regionId":   84, "legacyId": 12, "stateId":   16, "location": {"lat":   49.0329045, "lon":   38.3725819} },
  "STAROBILSKYI-DSTR"           : { "name": "Старобільський район"             , "regionId":   86, "legacyId": 12, "stateId":   16, "location": {"lat":   49.4329071, "lon":   39.4633304} },
  "STAROBILSK-CITY"             : { "name": "Старобільськ"                     , "regionId":   86, "legacyId": 12, "stateId":   16, "location": {"lat":   49.2822424, "lon":    38.897386} },
  "SIEVIERODONETSKYI-DSTR"      : { "name": "Сіверськодонецький район"         , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.8687059, "lon":   38.4672866} },
  "ZOLOTE-CITY"                 : { "name": "Золоте"                           , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.6901104, "lon":   38.5121584} },
  "LYSYCHANSK-CITY"             : { "name": "Лисичанськ"                       , "regionId":   84, "legacyId": 12, "stateId":   16, "location": {"lat":    48.917267, "lon":   38.4285981} },
  "SIEVIERODONETSK-CITY"        : { "name": "Сіверськодонецьк"                 , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   48.9478698, "lon":   38.4936475} },
  "SHCHASTYNSKYI-DSTR"          : { "name": "Щастинський район"                , "regionId":   87, "legacyId": 12, "stateId":   16, "location": {"lat":   48.8509227, "lon":   39.3581318} },
  "NOVOAIDAR-CITY"              : { "name": "Новоайдар"                        , "regionId":   87, "legacyId": 12, "stateId":   16, "location": {"lat":   48.9596084, "lon":   38.9937733} },
  "LVIVKA"                      : { "name": "Львівська область"                , "regionId":   27, "legacyId":  4, "stateId":   27, "location": {"lat":   49.6512234, "lon":   23.8266948} },
  "DROGOBICKYI-DSTR"            : { "name": "Дрогобицький район"               , "regionId":   91, "legacyId":  4, "stateId":   27, "location": {"lat":   49.2874524, "lon":   23.4157025} },
  "DROHOBYCH-CITY"              : { "name": "Дрогобич"                         , "regionId":   91, "legacyId":  4, "stateId":   27, "location": {"lat":   49.3513996, "lon":   23.5061662} },
  "ZOLOCHIVSKYI-DSTR"           : { "name": "Золочівський район"               , "regionId":   94, "legacyId":  4, "stateId":   27, "location": {"lat":   49.9493387, "lon":   24.9235532} },
  "BUSK-CITY"                   : { "name": "Буськ"                            , "regionId":   94, "legacyId":  4, "stateId":   27, "location": {"lat":    49.965355, "lon":   24.6089531} },
  "ZOLOCHIV-LV-CITY"            : { "name": "Золочів (Львівська)"              , "regionId":   94, "legacyId":  4, "stateId":   27, "location": {"lat":   49.8069245, "lon":   24.9031505} },
  "LVIVSKYI-DSTR"               : { "name": "Львівський район"                 , "regionId":   90, "legacyId":  4, "stateId":   27, "location": {"lat":   49.9109229, "lon":   24.1804539} },
  "BIBRKA-CITY"                 : { "name": "Бібрка"                           , "regionId":   90, "legacyId":  4, "stateId":   27, "location": {"lat":   49.6375667, "lon":   24.2973942} },
  "LVIV-CITY"                   : { "name": "Львів"                            , "regionId":  845, "legacyId":  4, "stateId":   27, "location": {"lat":    49.841952, "lon":   24.0315921} },
  "SAMBIRSKYI-DSTR"             : { "name": "Самбірський район"                , "regionId":   88, "legacyId":  4, "stateId":   27, "location": {"lat":   49.2956067, "lon":   22.9313607} },
  "SAMBIR-CITY"                 : { "name": "Самбір"                           , "regionId":   88, "legacyId":  4, "stateId":   27, "location": {"lat":   49.5182214, "lon":   23.1970412} },
  "STRIJSKYI-DSTR"              : { "name": "Стрийський район"                 , "regionId":   89, "legacyId":  4, "stateId":   27, "location": {"lat":   49.1884941, "lon":   23.9776615} },
  "STRYOI-CITY"                 : { "name": "Стрий"                            , "regionId":   89, "legacyId":  4, "stateId":   27, "location": {"lat":    49.255875, "lon":   23.8530863} },
  "CHERVONOGRADSKYI-DSTR"       : { "name": "Червоноградський район"           , "regionId":   92, "legacyId":  4, "stateId":   27, "location": {"lat":   50.3736563, "lon":   24.2117266} },
  "CHERVONOHRAD-CITY"           : { "name": "Шептицький"                       , "regionId":   92, "legacyId":  4, "stateId":   27, "location": {"lat":   50.3940289, "lon":   24.2396098} },
  "YAVORIVSKYI-DSTR"            : { "name": "Яворівський район"                , "regionId":   93, "legacyId":  4, "stateId":   27, "location": {"lat":   49.9116882, "lon":   23.4968231} },
  "YAVORIV-CITY"                : { "name": "Яворів"                           , "regionId":   93, "legacyId":  4, "stateId":   27, "location": {"lat":   49.9456001, "lon":   23.3886319} },
  "MYKOLAYIV"                   : { "name": "Миколаївська область"             , "regionId":   17, "legacyId": 18, "stateId":   17, "location": {"lat":   47.3886032, "lon":   31.9442334} },
  "BASHTANSKYI-DSTR"            : { "name": "Баштанський район"                , "regionId":   96, "legacyId": 18, "stateId":   17, "location": {"lat":   47.4331746, "lon":   32.5541105} },
  "BASHTANKA-CITY"              : { "name": "Баштанка"                         , "regionId":   96, "legacyId": 18, "stateId":   17, "location": {"lat":   47.4056348, "lon":   32.4440934} },
  "NOVIJ-BUG-CITY"              : { "name": "Новий Буг"                        , "regionId":   96, "legacyId": 18, "stateId":   17, "location": {"lat":   47.6866817, "lon":   32.5027638} },
  "SNIHURIVKA-CITY"             : { "name": "Снігурівка"                       , "regionId":   96, "legacyId": 18, "stateId":   17, "location": {"lat":    47.070721, "lon":   32.7924643} },
  "VOZNESENSKYI-DSTR"           : { "name": "Вознесенський район"              , "regionId":   95, "legacyId": 18, "stateId":   17, "location": {"lat":   47.6387683, "lon":   31.4898065} },
  "YELANEC-CITY"                : { "name": "Єланець"                          , "regionId":   95, "legacyId": 18, "stateId":   17, "location": {"lat":    47.696378, "lon":   31.8489152} },
  "VOZNESENSK-CITY"             : { "name": "Вознесенськ"                      , "regionId":   95, "legacyId": 18, "stateId":   17, "location": {"lat":   47.5679582, "lon":   31.3338636} },
  "YUZHNOUKRAYINSK-CITY"        : { "name": "Південноукраїнськ (Южноукраїнськ)", "regionId":   95, "legacyId": 18, "stateId":   17, "location": {"lat":   47.8108662, "lon":    31.219312} },
  "MYKOLAIVSKYI-DSTR"           : { "name": "Миколаївський район"              , "regionId":   98, "legacyId": 18, "stateId":   17, "location": {"lat":   46.9625824, "lon":    31.780024} },
  "KUTSURUB-CITY"               : { "name": "Куцуруб"                          , "regionId":   98, "legacyId": 18, "stateId":   17, "location": {"lat":   46.6529086, "lon":   31.6211184} },
  "MYKOLAIV-CITY"               : { "name": "Миколаїв"                         , "regionId":  926, "legacyId": 18, "stateId":   17, "location": {"lat":   46.9758615, "lon":   31.9939666} },
  "OCHAKIV-CITY"                : { "name": "Очаків"                           , "regionId":   98, "legacyId": 18, "stateId":   17, "location": {"lat":   46.6145957, "lon":   31.5452994} },
  "PERVOMAISKYI-DSTR"           : { "name": "Первомайський район"              , "regionId":   97, "legacyId": 18, "stateId":   17, "location": {"lat":   49.3454661, "lon":   36.3923097} },
  "ARBUZINKA-CITY"              : { "name": "Арбузинка"                        , "regionId":   97, "legacyId": 18, "stateId":   17, "location": {"lat":      47.9076, "lon":     31.31516} },
  "KRIVE-OZERO-CITY"            : { "name": "Криве Озеро"                      , "regionId":   97, "legacyId": 18, "stateId":   17, "location": {"lat":   47.9532217, "lon":   30.3425878} },
  "PERVOMAOISK-CITY"            : { "name": "Первомайськ"                      , "regionId":   97, "legacyId": 18, "stateId":   17, "location": {"lat":    48.045745, "lon":   30.8475997} },
  "ODESKA"                      : { "name": "Одеська область"                  , "regionId":   18, "legacyId": 17, "stateId":   18, "location": {"lat":   46.1147226, "lon":   29.9567193} },
  "IZMAILSKYI-DSTR"             : { "name": "Ізмаїльський район"               , "regionId":  101, "legacyId": 17, "stateId":   18, "location": {"lat":   45.5068979, "lon":   29.1975076} },
  "IZMAIL-CITY"                 : { "name": "Ізмаїл"                           , "regionId":  101, "legacyId": 17, "stateId":   18, "location": {"lat":   45.3511307, "lon":   28.8361514} },
  "VYLKOVE-CITY"                : { "name": "Вилкове"                          , "regionId":  101, "legacyId": 17, "stateId":   18, "location": {"lat":     45.40306, "lon":     29.58309} },
  "KILIYA-CITY"                 : { "name": "Кілія"                            , "regionId":  101, "legacyId": 17, "stateId":   18, "location": {"lat":   45.4409767, "lon":   29.2652788} },
  "BEREZIVSKYI-DSTR"            : { "name": "Березівський район"               , "regionId":  100, "legacyId": 17, "stateId":   18, "location": {"lat":   47.2074444, "lon":   30.6502496} },
  "BEREZIVKA-CITY"              : { "name": "Березівка"                        , "regionId":  100, "legacyId": 17, "stateId":   18, "location": {"lat":   49.9043196, "lon":   36.0674414} },
  "BOLHRADSKYI-DSTR"            : { "name": "Болградський район"               , "regionId":  105, "legacyId": 17, "stateId":   18, "location": {"lat":   46.0110562, "lon":   29.2694744} },
  "ARTSYZ-CITY"                 : { "name": "Арциз"                            , "regionId":  105, "legacyId": 17, "stateId":   18, "location": {"lat":   45.9962017, "lon":    29.431517} },
  "BOLHRAD-CITY"                : { "name": "Болград"                          , "regionId":  105, "legacyId": 17, "stateId":   18, "location": {"lat":   45.6779137, "lon":   28.6132404} },
  "BILHOROD-DNISTROVSKYI-DSTR"  : { "name": "Білгород-Дністровський район"     , "regionId":  102, "legacyId": 17, "stateId":   18, "location": {"lat":   46.0138179, "lon":    29.973242} },
  "BILHOROD-DNISTROVSKYOI-CITY" : { "name": "Білгород-Дністровський"           , "regionId":  102, "legacyId": 17, "stateId":   18, "location": {"lat":   46.1909823, "lon":    30.345784} },
  "SARATA-CITY"                 : { "name": "Сарата"                           , "regionId":  102, "legacyId": 17, "stateId":   18, "location": {"lat":   46.0211575, "lon":   29.6629546} },
  "SERGIYIVKA-CITY"             : { "name": "Сергіївка"                        , "regionId":  102, "legacyId": 17, "stateId":   18, "location": {"lat":     46.02756, "lon":     30.37273} },
  "TATARBUNARY-CITY"            : { "name": "Татарбунари"                      , "regionId":  102, "legacyId": 17, "stateId":   18, "location": {"lat":   45.8398696, "lon":   29.6166537} },
  "TUZLY-CITY"                  : { "name": "Тузли"                            , "regionId":  102, "legacyId": 17, "stateId":   18, "location": {"lat":    45.871349, "lon":     30.08778} },
  "ODESKYI-DSTR"                : { "name": "Одеський район"                   , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":   46.5334679, "lon":   30.3213673} },
  "BILYAYIVKA-CITY"             : { "name": "Біляївка"                         , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":   46.4844245, "lon":   30.2120913} },
  "ZATOKA-CITY"                 : { "name": "Затока"                           , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":     46.06396, "lon":     30.45033} },
  "OVIDIOPOL-CITY"              : { "name": "Овідіополь"                       , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":   46.2473734, "lon":   30.4448614} },
  "ODESA-CITY"                  : { "name": "Одеса"                            , "regionId":  964, "legacyId": 17, "stateId":   18, "location": {"lat":   46.4843023, "lon":   30.7322878} },
  "YUZHNE-CITY"                 : { "name": "Південне (Южне)"                  , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":   46.6233765, "lon":   31.1059727} },
  "USATOVE-CITY"                : { "name": "Усатове"                          , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":    46.537399, "lon":    30.654261} },
  "CHORNOMORSK-CITY"            : { "name": "Чорноморськ"                      , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":   46.3020943, "lon":    30.653466} },
  "CHORNOMORSKE-CITY"           : { "name": "Чорноморське"                     , "regionId":  104, "legacyId": 17, "stateId":   18, "location": {"lat":   45.5109579, "lon":   32.6996211} },
  "PODILSKYI-DSTR"              : { "name": "Подільський район"                , "regionId":   99, "legacyId": 17, "stateId":   18, "location": {"lat":   47.7715473, "lon":   29.8402598} },
  "PODILSK-CITY"                : { "name": "Подільськ"                        , "regionId":   99, "legacyId": 17, "stateId":   18, "location": {"lat":   47.7497422, "lon":   29.5304957} },
  "ROZDILNIANSKYI-DSTR"         : { "name": "Роздільнянський район"            , "regionId":  103, "legacyId": 17, "stateId":   18, "location": {"lat":   47.0718751, "lon":   29.8684678} },
  "LIMANSKE-CITY"               : { "name": "Лиманське"                        , "regionId":  103, "legacyId": 17, "stateId":   18, "location": {"lat":   46.6618481, "lon":   29.9760782} },
  "ROZDILNA-CITY"               : { "name": "Роздільна"                        , "regionId":  103, "legacyId": 17, "stateId":   18, "location": {"lat":   46.8495966, "lon":   30.0720722} },
  "POLTASKA"                    : { "name": "Полтавська область"               , "regionId":   19, "legacyId": 20, "stateId":   19, "location": {"lat":   49.8607809, "lon":   33.7498787} },
  "KREMENCHUTSKYI-DSTR"         : { "name": "Кременчуцький район"              , "regionId":  107, "legacyId": 20, "stateId":   19, "location": {"lat":   49.3454009, "lon":   33.2229663} },
  "HLOBYNE-CITY"                : { "name": "Глобине"                          , "regionId":  107, "legacyId": 20, "stateId":   19, "location": {"lat":    49.393102, "lon":   33.2484159} },
  "HORISHNI-PLAVNI-CITY"        : { "name": "Горішні Плавні"                   , "regionId":  107, "legacyId": 20, "stateId":   19, "location": {"lat":    49.035262, "lon":   33.6315798} },
  "KREMENCHUK-CITY"             : { "name": "Кременчук"                        , "regionId":  107, "legacyId": 20, "stateId":   19, "location": {"lat":   49.0928529, "lon":   33.4308188} },
  "LUBENSKYI-DSTR"              : { "name": "Лубенський район"                 , "regionId":  106, "legacyId": 20, "stateId":   19, "location": {"lat":   50.0220954, "lon":   32.8483705} },
  "GREBINKA-CITY"               : { "name": "Гребінка"                         , "regionId":  106, "legacyId": 20, "stateId":   19, "location": {"lat":   50.1242526, "lon":   32.4377587} },
  "LUBNY-CITY"                  : { "name": "Лубни"                            , "regionId":  106, "legacyId": 20, "stateId":   19, "location": {"lat":   50.0118206, "lon":   33.0030821} },
  "PIRYATIN-CITY"               : { "name": "Пирятин"                          , "regionId":  106, "legacyId": 20, "stateId":   19, "location": {"lat":   50.2389532, "lon":   32.5026526} },
  "HOROL-CITY"                  : { "name": "Хорол"                            , "regionId":  106, "legacyId": 20, "stateId":   19, "location": {"lat":   49.7831496, "lon":   33.2719474} },
  "MYRHORODSKYI-DSTR"           : { "name": "Миргородський район"              , "regionId":  108, "legacyId": 20, "stateId":   19, "location": {"lat":   50.0323291, "lon":    33.792143} },
  "HADIACH-CITY"                : { "name": "Гадяч"                            , "regionId":  108, "legacyId": 20, "stateId":   19, "location": {"lat":   50.3701299, "lon":   33.9950534} },
  "LOKHVYTSIA-CITY"             : { "name": "Лохвиця"                          , "regionId":  108, "legacyId": 20, "stateId":   19, "location": {"lat":   50.3595181, "lon":   33.2741725} },
  "MIRGOROD-CITY"               : { "name": "Миргород"                         , "regionId":  108, "legacyId": 20, "stateId":   19, "location": {"lat":   49.9568658, "lon":   33.6153865} },
  "POLTAVSKYI-DSTR"             : { "name": "Полтавський район"                , "regionId":  109, "legacyId": 20, "stateId":   19, "location": {"lat":   49.5454739, "lon":   34.5568252} },
  "KARLOVKA-CITY"               : { "name": "Карлівка"                         , "regionId":  109, "legacyId": 20, "stateId":   19, "location": {"lat":   49.4541311, "lon":   35.1295481} },
  "KOBELIAKY-CITY"              : { "name": "Кобеляки"                         , "regionId":  109, "legacyId": 20, "stateId":   19, "location": {"lat":   49.1433333, "lon":   34.2002778} },
  "NOVISANZHARY-CITY"           : { "name": "Нові Санжари"                     , "regionId":  109, "legacyId": 20, "stateId":   19, "location": {"lat":   49.3338321, "lon":   34.3148631} },
  "POLTAVA-CITY"                : { "name": "Полтава"                          , "regionId": 1060, "legacyId": 20, "stateId":   19, "location": {"lat":   49.5897423, "lon":   34.5507948} },
  "RESHETYLVKA-CITY"            : { "name": "Решетилівка"                      , "regionId":  109, "legacyId": 20, "stateId":   19, "location": {"lat":   49.5586111, "lon":   34.0791667} },
  "RIVENSKA"                    : { "name": "Рівненська область"               , "regionId":    5, "legacyId":  6, "stateId":    5, "location": {"lat":   51.2074112, "lon":   26.5208033} },
  "VARASKYI-DSTR"               : { "name": "Вараський район"                  , "regionId":  110, "legacyId":  6, "stateId":    5, "location": {"lat":   51.5674977, "lon":   25.9495998} },
  "VARASH-CITY"                 : { "name": "Вараш"                            , "regionId":  110, "legacyId":  6, "stateId":    5, "location": {"lat":   51.3481736, "lon":   25.8500623} },
  "DUBENSKYI-DSTR"              : { "name": "Дубенський район"                 , "regionId":  111, "legacyId":  6, "stateId":    5, "location": {"lat":     50.36444, "lon":   25.5663768} },
  "DUBNO-CITY"                  : { "name": "Дубно"                            , "regionId":  111, "legacyId":  6, "stateId":    5, "location": {"lat":   50.4187918, "lon":   25.7455972} },
  "RIVNENSKYI-DSTR"             : { "name": "Рівненський район"                , "regionId":  112, "legacyId":  6, "stateId":    5, "location": {"lat":    50.689143, "lon":    26.562183} },
  "BEREZNE-CITY"                : { "name": "Березне"                          , "regionId":  112, "legacyId":  6, "stateId":    5, "location": {"lat":   51.0035653, "lon":   26.7524487} },
  "ZDOLBUNIV-CITY"              : { "name": "Здолбунів"                        , "regionId":  112, "legacyId":  6, "stateId":    5, "location": {"lat":   50.5330913, "lon":   26.2487622} },
  "KOREC-CITY"                  : { "name": "Корець"                           , "regionId":  112, "legacyId":  6, "stateId":    5, "location": {"lat":   50.6194566, "lon":    27.159712} },
  "KOSTOPIL-CITY"               : { "name": "Костопіль"                        , "regionId":  112, "legacyId":  6, "stateId":    5, "location": {"lat":   50.8792198, "lon":   26.4533981} },
  "OSTROH-CITY"                 : { "name": "Острог"                           , "regionId":  112, "legacyId":  6, "stateId":    5, "location": {"lat":    50.329021, "lon":   26.5203627} },
  "RIVNE-CITY"                  : { "name": "Рівне"                            , "regionId": 1133, "legacyId":  6, "stateId":    5, "location": {"lat":   50.6196175, "lon":   26.2513165} },
  "SARNENSKYI-DSTR"             : { "name": "Сарненський район"                , "regionId":  113, "legacyId":  6, "stateId":    5, "location": {"lat":   51.4107839, "lon":   26.9703997} },
  "DUBROVYTSIA-CITY"            : { "name": "Дубровиця"                        , "regionId":  113, "legacyId":  6, "stateId":    5, "location": {"lat":   51.5709462, "lon":   26.5660889} },
  "ROKYTNE-CITY"                : { "name": "Рокитне"                          , "regionId":  113, "legacyId":  6, "stateId":    5, "location": {"lat":   49.6867282, "lon":    30.473034} },
  "SARNI-CITY"                  : { "name": "Сарни"                            , "regionId":  113, "legacyId":  6, "stateId":    5, "location": {"lat":   51.3350028, "lon":   26.6171275} },
  "SUMSKA"                      : { "name": "Сумська область"                  , "regionId":   20, "legacyId": 10, "stateId":   20, "location": {"lat":   50.7696518, "lon":   34.3289305} },
  "KONOTOPSKYI-DSTR"            : { "name": "Конотопський район"               , "regionId":  117, "legacyId": 10, "stateId":   20, "location": {"lat":   51.3383683, "lon":   33.6817402} },
  "BURIN-CITY"                  : { "name": "Буринь"                           , "regionId":  117, "legacyId": 10, "stateId":   20, "location": {"lat":   51.1960431, "lon":   33.8288042} },
  "KONOTOP-CITY"                : { "name": "Конотоп"                          , "regionId":  117, "legacyId": 10, "stateId":   20, "location": {"lat":   51.2397495, "lon":    33.206675} },
  "KROLEVETS-CITY"              : { "name": "Кролевець"                        , "regionId":  117, "legacyId": 10, "stateId":   20, "location": {"lat":   51.5548654, "lon":   33.3875984} },
  "NOVA-SLOBODA-CITY"           : { "name": "Нова Слобода"                     , "regionId":  117, "legacyId": 10, "stateId":   20, "location": {"lat":   51.3749282, "lon":    34.132125} },
  "PUTIVL-CITY"                 : { "name": "Путивль"                          , "regionId":  117, "legacyId": 10, "stateId":   20, "location": {"lat":   51.3359821, "lon":   33.8715451} },
  "OKHTYRSKYI-DSTR"             : { "name": "Охтирський район"                 , "regionId":  118, "legacyId": 10, "stateId":   20, "location": {"lat":   50.4320321, "lon":   35.0469765} },
  "VELIKA-PISARIVKA-CITY"       : { "name": "Велика Писарівка"                 , "regionId":  118, "legacyId": 10, "stateId":   20, "location": {"lat":   50.4253238, "lon":   35.4838569} },
  "OKHTYRKA-CITY"               : { "name": "Охтирка"                          , "regionId":  118, "legacyId": 10, "stateId":   20, "location": {"lat":   50.3115386, "lon":   34.8868923} },
  "TROSTYANEC-CITY"             : { "name": "Тростянець"                       , "regionId":  118, "legacyId": 10, "stateId":   20, "location": {"lat":     50.48046, "lon":     34.96467} },
  "ROMENSKYI-DSTR"              : { "name": "Роменський район"                 , "regionId":  116, "legacyId": 10, "stateId":   20, "location": {"lat":   50.7647804, "lon":   33.6763294} },
  "LYPOVA-DOLYNA-CITY"          : { "name": "Липова Долина"                    , "regionId":  116, "legacyId": 10, "stateId":   20, "location": {"lat":   50.5637857, "lon":   33.7990004} },
  "NEDRIGAJLIV-CITY"            : { "name": "Недригайлів"                      , "regionId":  116, "legacyId": 10, "stateId":   20, "location": {"lat":   50.8358991, "lon":   33.8782826} },
  "ROMNI-CITY"                  : { "name": "Ромни"                            , "regionId":  116, "legacyId": 10, "stateId":   20, "location": {"lat":     50.74207, "lon":      33.4877} },
  "SUMSKYI-DSTR"                : { "name": "Сумський район"                   , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   50.8215478, "lon":     34.79122} },
  "ISKRISKIVSHIVSHINA-CITY"     : { "name": "Іскрисківщина"                    , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.2394221, "lon":   34.3759417} },
  "ATINSKE-CITY"                : { "name": "Атинське"                         , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.2310551, "lon":   34.2763356} },
  "BASIVKA-CITY"                : { "name": "Басівка"                          , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":    49.780231, "lon":     23.90766} },
  "YABUDKI-CITY"                : { "name": "Будки"                            , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   49.2337045, "lon":   31.8236904} },
  "BILOPILLIA-CITY"             : { "name": "Білопілля"                        , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.1460449, "lon":   34.3121992} },
  "VOLFINE-CITY"                : { "name": "Волфине"                          , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.2390814, "lon":   34.4592809} },
  "VOROZHBA-CITY"               : { "name": "Ворожба"                          , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.1722411, "lon":   34.2245008} },
  "KATERINIVKA-CITY"            : { "name": "Катеринівка"                      , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   48.4387871, "lon":   38.7214859} },
  "KRASNOPILLYA-CITY"           : { "name": "Краснопілля"                      , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   50.7712539, "lon":   35.2563391} },
  "KINDRATIVKA-CITY"            : { "name": "Кіндратівка"                      , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   48.5906423, "lon":   37.5754875} },
  "LEBEDIN-CITY"                : { "name": "Лебедин"                          , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   50.5809626, "lon":   34.4753069} },
  "MEZENIVKA-CITY"              : { "name": "Мезенівка"                        , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":     50.63084, "lon":    35.313492} },
  "MIKOLAYIVKA-CITY"            : { "name": "Миколаївка"                       , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   48.8610868, "lon":   37.7619191} },
  "MIROPILLYA-CITY"             : { "name": "Миропілля"                        , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.0273334, "lon":   35.2470264} },
  "MOGRICYA-CITY"               : { "name": "Могриця"                          , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":    51.034958, "lon":    35.103451} },
  "OBODI-CITY"                  : { "name": "Ободи"                            , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.2254604, "lon":   34.6257695} },
  "PAVLIVKA-CITY"               : { "name": "Павлівка"                         , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":    50.627998, "lon":     24.46138} },
  "RIZHIVKA-CITY"               : { "name": "Рижівка"                          , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.2535571, "lon":   34.2444244} },
  "SUMY-CITY"                   : { "name": "Суми"                             , "regionId": 1187, "legacyId": 10, "stateId":   20, "location": {"lat":   50.9119775, "lon":   34.8027723} },
  "UGROYIDI-CITY"               : { "name": "Угроїди"                          , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   50.8597669, "lon":   35.2702982} },
  "HOTIN-CITY"                  : { "name": "Хотінь"                           , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.0786763, "lon":     34.78001} },
  "YUNAKIVKA-CITY"              : { "name": "Юнаківка"                         , "regionId":  114, "legacyId": 10, "stateId":   20, "location": {"lat":   51.1227143, "lon":    35.032302} },
  "SHOSTKYNSKYI-DSTR"           : { "name": "Шосткинський район"               , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":   51.9046918, "lon":   33.7202369} },
  "VORONIZH-CITY"               : { "name": "Вороніж"                          , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":   51.7778331, "lon":   33.4660287} },
  "GLUHIV-CITY"                 : { "name": "Глухів"                           , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":     51.67831, "lon":      33.9093} },
  "ESMAN-CITY"                  : { "name": "Есмань"                           , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":    51.767231, "lon":     34.06345} },
  "ZNOB-NOVGORODSKE-CITY"       : { "name": "Зноб-Новгородське"                , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":    52.264019, "lon":    33.598251} },
  "SVESA-CITY"                  : { "name": "Свеса"                            , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":     51.94816, "lon":     33.93299} },
  "SEREDINA-BUDA-CITY"          : { "name": "Середина-Буда"                    , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":   52.1886906, "lon":   34.0306022} },
  "SHALIGINE-CITY"              : { "name": "Шалигине"                         , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":    51.575661, "lon":    34.099838} },
  "SHOSTKA-CITY"                : { "name": "Шостка"                           , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":    51.864355, "lon":   33.4728542} },
  "YAMPILS-SUM-CITY"            : { "name": "Ямпіль"                           , "regionId":  115, "legacyId": 10, "stateId":   20, "location": {"lat":   48.2455558, "lon":   28.2852657} },
  "TERNOPILSKA"                 : { "name": "Тернопільська область"            , "regionId":   21, "legacyId":  3, "stateId":   21, "location": {"lat":   49.6630002, "lon":   25.6167516} },
  "KREMENECKYI-DSTR"            : { "name": "Кременецький район"               , "regionId":  120, "legacyId":  3, "stateId":   21, "location": {"lat":   49.9838572, "lon":   25.7809942} },
  "KREMENETS-CITY"              : { "name": "Кременець"                        , "regionId":  120, "legacyId":  3, "stateId":   21, "location": {"lat":   50.0960966, "lon":   25.7260783} },
  "TERNOPILSKYI-DSTR"           : { "name": "Тернопільський район"             , "regionId":  119, "legacyId":  3, "stateId":   21, "location": {"lat":    49.534387, "lon":   25.4427785} },
  "BEREZHANY-CITY"              : { "name": "Бережани"                         , "regionId":  119, "legacyId":  3, "stateId":   21, "location": {"lat":   49.4450296, "lon":    24.938854} },
  "ZBARAZH-CITY"                : { "name": "Збараж"                           , "regionId":  119, "legacyId":  3, "stateId":   21, "location": {"lat":   49.6607393, "lon":   25.7768485} },
  "KOZOVA-CITY"                 : { "name": "Козова"                           , "regionId":  119, "legacyId":  3, "stateId":   21, "location": {"lat":   49.4332743, "lon":   25.1484661} },
  "TERNOPIL-CITY"               : { "name": "Тернопіль"                        , "regionId": 1241, "legacyId":  3, "stateId":   21, "location": {"lat":   49.5557908, "lon":   25.5923753} },
  "CHORTKIVSKYI-DSTR"           : { "name": "Чортківський район"               , "regionId":  121, "legacyId":  3, "stateId":   21, "location": {"lat":   48.9460274, "lon":   25.6751286} },
  "CHORTKIV-CITY"               : { "name": "Чортків"                          , "regionId":  121, "legacyId":  3, "stateId":   21, "location": {"lat":   49.0160555, "lon":   25.7925191} },
  "TEST"                        : { "name": "Тест"                             , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":   50.4217218, "lon":   30.6452053} },
  "TEST-DSTR"                   : { "name": "Тестовий район"                   , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":         49.0, "lon":         32.0} },
  "TEST-CITY"                   : { "name": "Тестове місто"                    , "regionId":   -1, "legacyId": -1, "stateId":   -1, "location": {"lat":         49.0, "lon":         32.0} },
  "HARKIVSKA"                   : { "name": "Харківська область"               , "regionId":   22, "legacyId": 11, "stateId":   22, "location": {"lat":   49.8299582, "lon":   36.3788957} },
  "IZIUMSKYI-DSTR"              : { "name": "Ізюмський район"                  , "regionId":  125, "legacyId": 11, "stateId":   22, "location": {"lat":   49.1975781, "lon":   37.0714174} },
  "IZIUM-CITY"                  : { "name": "Ізюм"                             , "regionId":  125, "legacyId": 11, "stateId":   22, "location": {"lat":   49.1913721, "lon":   37.2784125} },
  "BALAKLIYA-CITY"              : { "name": "Балаклія"                         , "regionId":  125, "legacyId": 11, "stateId":   22, "location": {"lat":   49.4521336, "lon":   36.8397826} },
  "BOROVA-CITY"                 : { "name": "Борова"                           , "regionId":  125, "legacyId": 11, "stateId":   22, "location": {"lat":   49.3838133, "lon":   37.6330137} },
  "KRASNOHRADSKYI-DSTR"         : { "name": "Красноградський район"            , "regionId":  127, "legacyId": 11, "stateId":   22, "location": {"lat":   49.3168261, "lon":   35.6553118} },
  "KRASNOGRAD-CITY"             : { "name": "Берестин"                         , "regionId":  127, "legacyId": 11, "stateId":   22, "location": {"lat":   49.3741326, "lon":   35.4494234} },
  "BOHODUKHIVSKYI-DSTR"         : { "name": "Богодухівський район"             , "regionId":  126, "legacyId": 11, "stateId":   22, "location": {"lat":   50.0481828, "lon":   35.3659782} },
  "BOGODUHIV-CITY"              : { "name": "Богодухів"                        , "regionId":  126, "legacyId": 11, "stateId":   22, "location": {"lat":   50.1601711, "lon":   35.5220539} },
  "ZOLOCHIV-CITY"               : { "name": "Золочів"                          , "regionId":  126, "legacyId": 11, "stateId":   22, "location": {"lat":   49.8056522, "lon":   24.8988858} },
  "KUPIANSKYI-DSTR"             : { "name": "Куп'янський район"                , "regionId":  123, "legacyId": 11, "stateId":   22, "location": {"lat":   49.8814105, "lon":   37.6177087} },
  "KUP-YANSK-CITY"              : { "name": "Куп'янськ"                        , "regionId":  123, "legacyId": 11, "stateId":   22, "location": {"lat":   49.7132963, "lon":   37.6141992} },
  "LOZIVSKYI-DSTR"              : { "name": "Лозівський район"                 , "regionId":  128, "legacyId": 11, "stateId":   22, "location": {"lat":   49.0365215, "lon":     36.36994} },
  "PERVOMAJSKIJ-CITY"           : { "name": "Златопіль"                        , "regionId":  128, "legacyId": 11, "stateId":   22, "location": {"lat":   49.3754529, "lon":   36.2143454} },
  "LOZOVA-KHARKIVSKA-CITY"      : { "name": "Лозова"                           , "regionId":  128, "legacyId": 11, "stateId":   22, "location": {"lat":   48.8842428, "lon":   36.3160254} },
  "KHARKIVSKYI-DSTR"            : { "name": "Харківський район"                , "regionId":  124, "legacyId": 11, "stateId":   22, "location": {"lat":   49.9940733, "lon":   36.2299778} },
  "DERGACHI-CITY"               : { "name": "Дергачі"                          , "regionId":  124, "legacyId": 11, "stateId":   22, "location": {"lat":   50.1070567, "lon":   36.1205802} },
  "KOZACHA-LOPAN-CITY"          : { "name": "Козача Лопань"                    , "regionId":  124, "legacyId": 11, "stateId":   22, "location": {"lat":   50.3295857, "lon":   36.1921383} },
  "LIPCI-CITY"                  : { "name": "Липці"                            , "regionId":  124, "legacyId": 11, "stateId":   22, "location": {"lat":   50.2037009, "lon":   36.4243526} },
  "MEREFA-CITY"                 : { "name": "Мерефа"                           , "regionId":  124, "legacyId": 11, "stateId":   22, "location": {"lat":   49.8183386, "lon":   36.0628675} },
  "PISOCHINO-CITY"              : { "name": "Пісочин"                          , "regionId":  124, "legacyId": 11, "stateId":   22, "location": {"lat":   49.9622881, "lon":   36.1239316} },
  "KHARKIV-CITY"                : { "name": "Харків"                           , "regionId": 1293, "legacyId": 11, "stateId":   22, "location": {"lat":   49.9923181, "lon":   36.2310146} },
  "CIRKUNI-CITY"                : { "name": "Циркуни"                          , "regionId":  124, "legacyId": 11, "stateId":   22, "location": {"lat":   50.0820419, "lon":   36.3870514} },
  "CHUHUIVSKYI-DSTR"            : { "name": "Чугуївський район"                , "regionId":  122, "legacyId": 11, "stateId":   22, "location": {"lat":   49.9590995, "lon":   36.8900622} },
  "BILIJ-KOLODYAZ-CITY"         : { "name": "Білий Колодязь"                   , "regionId":  122, "legacyId": 11, "stateId":   22, "location": {"lat":    50.204914, "lon":   37.1144832} },
  "VOVCHANSK-CITY"              : { "name": "Вовчанськ"                        , "regionId":  122, "legacyId": 11, "stateId":   22, "location": {"lat":   50.2928843, "lon":   36.9370028} },
  "KOROBOCHKINE-CITY"           : { "name": "Коробочкине"                      , "regionId":  122, "legacyId": 11, "stateId":   22, "location": {"lat":    49.779049, "lon":    36.816898} },
  "CHUGUYIV-CITY"               : { "name": "Чугуїв"                           , "regionId":  122, "legacyId": 11, "stateId":   22, "location": {"lat":    49.836626, "lon":   36.6899391} },
  "HERSONSKA"                   : { "name": "Херсонська область"               , "regionId":   23, "legacyId": 15, "stateId":   23, "location": {"lat":   46.5421715, "lon":   33.4079326} },
  "BERYSLAVSKYI-DSTR"           : { "name": "Бериславський район"              , "regionId":  129, "legacyId": 15, "stateId":   23, "location": {"lat":   47.1710647, "lon":   33.4042631} },
  "BERISLAV-CITY"               : { "name": "Берислав"                         , "regionId":  129, "legacyId": 15, "stateId":   23, "location": {"lat":   46.8357749, "lon":    33.416743} },
  "NOVOVORONTSOVKA-CITY"        : { "name": "Нововоронцовка"                   , "regionId":  129, "legacyId": 15, "stateId":   23, "location": {"lat":   47.4957983, "lon":   33.9198174} },
  "OSOKORIVKA-CITY"             : { "name": "Осокорівка"                       , "regionId":  129, "legacyId": 15, "stateId":   23, "location": {"lat":   47.4322208, "lon":   33.9193051} },
  "HENICHESKYI-DSTR"            : { "name": "Генічеський район"                , "regionId":  133, "legacyId": 15, "stateId":   23, "location": {"lat":   46.4284952, "lon":   34.5760512} },
  "GENICHESK-CITY"              : { "name": "Генічеськ"                        , "regionId":  133, "legacyId": 15, "stateId":   23, "location": {"lat":   46.1661695, "lon":   34.8088828} },
  "KAKHOVSKYI-DSTR"             : { "name": "Каховський район"                 , "regionId":  131, "legacyId": 15, "stateId":   23, "location": {"lat":   46.8093053, "lon":   33.7264917} },
  "KAHOVKA-CITY"                : { "name": "Каховка"                          , "regionId":  131, "legacyId": 15, "stateId":   23, "location": {"lat":   46.8054626, "lon":   33.4817825} },
  "NOVA-KAKHOVKA-CITY"          : { "name": "Нова Каховка"                     , "regionId":  131, "legacyId": 15, "stateId":   23, "location": {"lat":   46.7583404, "lon":   33.3566678} },
  "TAVRIJSK-CITY"               : { "name": "Таврійськ"                        , "regionId":  131, "legacyId": 15, "stateId":   23, "location": {"lat":   46.7550442, "lon":   33.4248309} },
  "CHAPLINKA-CITY"              : { "name": "Чаплинка"                         , "regionId":  131, "legacyId": 15, "stateId":   23, "location": {"lat":   46.3617756, "lon":   33.5380219} },
  "SKADOVSKYI-DSTR"             : { "name": "Скадовський район"                , "regionId":  130, "legacyId": 15, "stateId":   23, "location": {"lat":   46.2975708, "lon":   32.2979329} },
  "SKADOVSK-CITY"               : { "name": "Скадовськ"                        , "regionId":  130, "legacyId": 15, "stateId":   23, "location": {"lat":   46.1203932, "lon":    32.910339} },
  "KHERSONSKYI-DSTR"            : { "name": "Херсонський район"                , "regionId":  132, "legacyId": 15, "stateId":   23, "location": {"lat":   46.6355225, "lon":   32.5341741} },
  "ANTONIVKA-CITY"              : { "name": "Антонівка"                        , "regionId":  132, "legacyId": 15, "stateId":   23, "location": {"lat":    46.679927, "lon":   32.7368083} },
  "BILOZERKA-CITY"              : { "name": "Білозерка"                        , "regionId":  132, "legacyId": 15, "stateId":   23, "location": {"lat":     46.63078, "lon":     32.44537} },
  "OLEKSANDRIVKA-CITY"          : { "name": "Олександрівка"                    , "regionId":  132, "legacyId": 15, "stateId":   23, "location": {"lat":   47.9218584, "lon":   37.5726397} },
  "OLESHKI-CITY"                : { "name": "Олешки"                           , "regionId":  132, "legacyId": 15, "stateId":   23, "location": {"lat":   46.6260908, "lon":   32.7220187} },
  "KHERSON-CITY"                : { "name": "Херсон"                           , "regionId": 1370, "legacyId": 15, "stateId":   23, "location": {"lat":   46.6401295, "lon":   32.6143922} },
  "CHORNOBAYIVKA-CITY"          : { "name": "Чорнобаївка"                      , "regionId":  132, "legacyId": 15, "stateId":   23, "location": {"lat":   46.6926512, "lon":   32.5455178} },
  "HMELNYCKA"                   : { "name": "Хмельницька область"              , "regionId":    3, "legacyId": 24, "stateId":    3, "location": {"lat":    49.268624, "lon":   27.0635998} },
  "KAMIANETS-PODILSKYI-DSTR"    : { "name": "Кам'янець-Подільський район"      , "regionId":  135, "legacyId": 24, "stateId":    3, "location": {"lat":   48.8135044, "lon":   26.8341264} },
  "KAMIANETS-PODILSKYOI-CITY"   : { "name": "Кам'янець-Подільський"            , "regionId":  135, "legacyId": 24, "stateId":    3, "location": {"lat":   48.6781294, "lon":   26.5854027} },
  "KHMELNYTSKYI-DSTR"           : { "name": "Хмельницький район"               , "regionId":  134, "legacyId": 24, "stateId":    3, "location": {"lat":   49.4325584, "lon":   27.0041816} },
  "ADAMPIL-CITY"                : { "name": "Адампіль"                         , "regionId":  134, "legacyId": 24, "stateId":    3, "location": {"lat":   49.6671432, "lon":   27.6566484} },
  "VOLOCHISK-CITY"              : { "name": "Волочиськ"                        , "regionId":  134, "legacyId": 24, "stateId":    3, "location": {"lat":   49.5358446, "lon":   26.2126215} },
  "KRASYLIV-CITY"               : { "name": "Красилів"                         , "regionId":  134, "legacyId": 24, "stateId":    3, "location": {"lat":   49.6544431, "lon":   26.9709084} },
  "STAROKOSTYANTINIV-CITY"      : { "name": "Старокостянтинів"                 , "regionId":  134, "legacyId": 24, "stateId":    3, "location": {"lat":    49.756163, "lon":   27.2087889} },
  "TEOFIPOL-CITY"               : { "name": "Теофіполь"                        , "regionId":  134, "legacyId": 24, "stateId":    3, "location": {"lat":     49.84463, "lon":     26.41525} },
  "KHMELNYTSKYOI-CITY"          : { "name": "Хмельницький"                     , "regionId": 1400, "legacyId": 24, "stateId":    3, "location": {"lat":   49.4196404, "lon":   26.9793793} },
  "SHEPETIVSKYI-DSTR"           : { "name": "Шепетівський район"               , "regionId":  136, "legacyId": 24, "stateId":    3, "location": {"lat":   50.2300515, "lon":   26.9170674} },
  "NETISHYN-CITY"               : { "name": "Нетішин"                          , "regionId":  136, "legacyId": 24, "stateId":    3, "location": {"lat":   50.3338348, "lon":   26.6496599} },
  "POLONNE-CITY"                : { "name": "Полонне"                          , "regionId":  136, "legacyId": 24, "stateId":    3, "location": {"lat":   50.1193439, "lon":   27.5089702} },
  "SLAVUTA-CITY"                : { "name": "Славута"                          , "regionId":  136, "legacyId": 24, "stateId":    3, "location": {"lat":   50.2962398, "lon":   26.8658254} },
  "SHEPETIVKA-CITY"             : { "name": "Шепетівка"                        , "regionId":  136, "legacyId": 24, "stateId":    3, "location": {"lat":   50.1809437, "lon":   27.0651783} },
  "CHERKASKA"                   : { "name": "Черкаська область"                , "regionId":   24, "legacyId": 21, "stateId":   24, "location": {"lat":   49.1460165, "lon":   31.2271744} },
  "ZVENYHORODSKYI-DSTR"         : { "name": "Звенигородський район"            , "regionId":  150, "legacyId": 21, "stateId":   24, "location": {"lat":   49.1022969, "lon":   31.0738727} },
  "VATUTINE-CITY"               : { "name": "Багачеве"                         , "regionId":  150, "legacyId": 21, "stateId":   24, "location": {"lat":   49.0172494, "lon":   31.0618502} },
  "ZVENIGORODKA-CITY"           : { "name": "Звенигородка"                     , "regionId":  150, "legacyId": 21, "stateId":   24, "location": {"lat":   49.0767158, "lon":     30.96138} },
  "ZOLOTONISKYI-DSTR"           : { "name": "Золотоніський район"              , "regionId":  153, "legacyId": 21, "stateId":   24, "location": {"lat":   49.7739881, "lon":   32.1258903} },
  "ZOLOTONOSHA-CITY"            : { "name": "Золотоноша"                       , "regionId":  153, "legacyId": 21, "stateId":   24, "location": {"lat":   49.6689719, "lon":   32.0427439} },
  "UMANSKYI-DSTR"               : { "name": "Уманський район"                  , "regionId":  151, "legacyId": 21, "stateId":   24, "location": {"lat":   48.8935207, "lon":   30.0828794} },
  "ZHASHKIV-CITY"               : { "name": "Жашків"                           , "regionId":  151, "legacyId": 21, "stateId":   24, "location": {"lat":   49.2478012, "lon":   30.1066179} },
  "UMAN-CITY"                   : { "name": "Умань"                            , "regionId":  151, "legacyId": 21, "stateId":   24, "location": {"lat":   48.7497621, "lon":   30.2203052} },
  "CHERKASKYI-DSTR"             : { "name": "Черкаський район"                 , "regionId":  152, "legacyId": 21, "stateId":   24, "location": {"lat":   49.4361742, "lon":   31.7602711} },
  "KANIV-CITY"                  : { "name": "Канів"                            , "regionId":  152, "legacyId": 21, "stateId":   24, "location": {"lat":   49.7551031, "lon":   31.4610802} },
  "KORSUN-CITY"                 : { "name": "Корсунь-Шевченківський"           , "regionId":  152, "legacyId": 21, "stateId":   24, "location": {"lat":    49.418037, "lon":   31.2556741} },
  "SMILA-CITY"                  : { "name": "Сміла"                            , "regionId":  152, "legacyId": 21, "stateId":   24, "location": {"lat":   49.2336897, "lon":   31.8829216} },
  "CHERKASY-CITY"               : { "name": "Черкаси"                          , "regionId": 1473, "legacyId": 21, "stateId":   24, "location": {"lat":   49.4447056, "lon":   32.0588085} },
  "CHERNIVETSKA"                : { "name": "Чернівецька область"              , "regionId":   26, "legacyId": 25, "stateId":   26, "location": {"lat":   48.3810791, "lon":   26.1081673} },
  "VYZHNYTSKYI-DSTR"            : { "name": "Вижницький район"                 , "regionId":  138, "legacyId": 25, "stateId":   26, "location": {"lat":   48.0642168, "lon":   25.1629793} },
  "VYZHNYTSIA-CITY"             : { "name": "Вижниця"                          , "regionId":  138, "legacyId": 25, "stateId":   26, "location": {"lat":    48.248441, "lon":   25.1893807} },
  "PUTYLA-CITY"                 : { "name": "Путила"                           , "regionId":  138, "legacyId": 25, "stateId":   26, "location": {"lat":     47.99515, "lon":     25.08453} },
  "DNISTROVSKYI-DSTR"           : { "name": "Дністровський район"              , "regionId":  139, "legacyId": 25, "stateId":   26, "location": {"lat":   48.4199458, "lon":   26.5284293} },
  "KELMENTSI-CITY"              : { "name": "Кельменці"                        , "regionId":  139, "legacyId": 25, "stateId":   26, "location": {"lat":   48.4654946, "lon":   26.8318791} },
  "SOKYRIANY-CITY"              : { "name": "Сокиряни"                         , "regionId":  139, "legacyId": 25, "stateId":   26, "location": {"lat":   48.4460307, "lon":    27.411193} },
  "KHOTYN-CITY"                 : { "name": "Хотин"                            , "regionId":  139, "legacyId": 25, "stateId":   26, "location": {"lat":   48.5068418, "lon":   26.4859086} },
  "CHERNIVETSKYI-DSTR"          : { "name": "Чернівецький район"               , "regionId":  137, "legacyId": 25, "stateId":   26, "location": {"lat":   48.3009284, "lon":   26.0578235} },
  "HERTSA-CITY"                 : { "name": "Герца"                            , "regionId":  137, "legacyId": 25, "stateId":   26, "location": {"lat":   48.1505805, "lon":   26.2589723} },
  "CHERNIVTSI-CITY"             : { "name": "Чернівці"                         , "regionId": 1542, "legacyId": 25, "stateId":   26, "location": {"lat":   48.2864702, "lon":   25.9376532} },
  "CHERNIGIWSKA"                : { "name": "Чернігівська область"             , "regionId":   25, "legacyId":  9, "stateId":   25, "location": {"lat":    51.272593, "lon":   31.7417235} },
  "KORIUKIVSKYI-DSTR"           : { "name": "Корюківський район"               , "regionId":  144, "legacyId":  9, "stateId":   25, "location": {"lat":   51.7297727, "lon":   32.2680013} },
  "KORIUKIVKA-CITY"             : { "name": "Корюківка"                        , "regionId":  144, "legacyId":  9, "stateId":   25, "location": {"lat":   51.7744549, "lon":   32.2512927} },
  "MENA-CITY"                   : { "name": "Мена"                             , "regionId":  144, "legacyId":  9, "stateId":   25, "location": {"lat":     51.52279, "lon":     32.21638} },
  "SNOVSK-CITY"                 : { "name": "Сновськ"                          , "regionId":  144, "legacyId":  9, "stateId":   25, "location": {"lat":   51.8187527, "lon":   31.9448953} },
  "SOSNYTSIA-CITY"              : { "name": "Сосниця"                          , "regionId":  144, "legacyId":  9, "stateId":   25, "location": {"lat":   51.5244906, "lon":   32.5028975} },
  "KHOLMY-CITY"                 : { "name": "Холми"                            , "regionId":  144, "legacyId":  9, "stateId":   25, "location": {"lat":    51.872562, "lon":    32.595619} },
  "NOVHOROD-SIVERSKYI-DSTR"     : { "name": "Новгород-Сіверський район"        , "regionId":  141, "legacyId":  9, "stateId":   25, "location": {"lat":   51.8499077, "lon":   32.9947239} },
  "KOROP-CITY"                  : { "name": "Короп"                            , "regionId":  141, "legacyId":  9, "stateId":   25, "location": {"lat":   51.5671394, "lon":   32.9520532} },
  "NOVHOROD-SIVERSKYI"          : { "name": "Новгород-Сіверський"              , "regionId":  141, "legacyId":  9, "stateId":   25, "location": {"lat":    52.004259, "lon":   33.2779899} },
  "SEMENIVKA-CITY"              : { "name": "Семенівка"                        , "regionId":  141, "legacyId":  9, "stateId":   25, "location": {"lat":     52.17853, "lon":     32.57755} },
  "NIZHYNSKYI-DSTR"             : { "name": "Ніжинський район"                 , "regionId":  142, "legacyId":  9, "stateId":   25, "location": {"lat":   50.9814575, "lon":    31.730417} },
  "BATURYN-CITY"                : { "name": "Батурин"                          , "regionId":  142, "legacyId":  9, "stateId":   25, "location": {"lat":   51.3413087, "lon":   32.8778317} },
  "BAHMACH-CITY"                : { "name": "Бахмач"                           , "regionId":  142, "legacyId":  9, "stateId":   25, "location": {"lat":   51.1826768, "lon":   32.8291034} },
  "BOBROVYTSIA-СITY"            : { "name": "Бобровиця"                        , "regionId":  142, "legacyId":  9, "stateId":   25, "location": {"lat":   50.7415033, "lon":   31.3860852} },
  "BORZNA-CITY"                 : { "name": "Борзна"                           , "regionId":  142, "legacyId":  9, "stateId":   25, "location": {"lat":   51.2534475, "lon":   32.4263156} },
  "NOSIVKA-CITY"                : { "name": "Носівка"                          , "regionId":  142, "legacyId":  9, "stateId":   25, "location": {"lat":   50.9377744, "lon":   31.5812258} },
  "NIZHYN-CITY"                 : { "name": "Ніжин"                            , "regionId":  142, "legacyId":  9, "stateId":   25, "location": {"lat":   51.0464747, "lon":   31.8806289} },
  "PRYLUTSKYI-DSTR"             : { "name": "Прилуцький район"                 , "regionId":  143, "legacyId":  9, "stateId":   25, "location": {"lat":   50.7146824, "lon":   32.5991597} },
  "ICHNYA-CITY"                 : { "name": "Ічня"                             , "regionId":  143, "legacyId":  9, "stateId":   25, "location": {"lat":   50.8623444, "lon":   32.3910144} },
  "VARVA-CITY"                  : { "name": "Варва"                            , "regionId":  143, "legacyId":  9, "stateId":   25, "location": {"lat":   50.4982561, "lon":   32.7228573} },
  "PRYLUKY-CITY"                : { "name": "Прилуки"                          , "regionId":  143, "legacyId":  9, "stateId":   25, "location": {"lat":   50.5885068, "lon":   32.3965412} },
  "SRIBNE-CITY"                 : { "name": "Срібне"                           , "regionId":  143, "legacyId":  9, "stateId":   25, "location": {"lat":    50.661573, "lon":   32.9174152} },
  "TALALAYIVKA-CITY"            : { "name": "Талалаївка"                       , "regionId":  143, "legacyId":  9, "stateId":   25, "location": {"lat":     50.83168, "lon":     33.13442} },
  "CHERNIHIVSKYI-DSTR"          : { "name": "Чернігівський район"              , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   51.4385146, "lon":   31.2062763} },
  "GONCHARIVSKE-CITY"           : { "name": "Гончарівське"                     , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   51.2990164, "lon":   30.9276044} },
  "HORODNIA-CITY"               : { "name": "Городня"                          , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   51.8915393, "lon":    31.595545} },
  "DESNA-CITY"                  : { "name": "Десна"                            , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   52.1990294, "lon":   33.2998917} },
  "KOZELETS-CITY"               : { "name": "Козелець"                         , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   50.9160647, "lon":   31.1167509} },
  "KULYKIVKA-CITY"              : { "name": "Куликівка"                        , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   51.3735623, "lon":   31.6455818} },
  "OSTER-CITY"                  : { "name": "Остер"                            , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   50.9508278, "lon":   30.8782419} },
  "RIPKY-CITY"                  : { "name": "Ріпки"                            , "regionId":  140, "legacyId":  9, "stateId":   25, "location": {"lat":   51.8036433, "lon":   31.0931453} },
  "CHERNIHIV-CITY"              : { "name": "Чернігів"                         , "regionId": 1591, "legacyId":  9, "stateId":   25, "location": {"lat":    51.494099, "lon":    31.294332} }
}

def make_hex(json_doc):
    json_str = json.dumps(json_doc, sort_keys=True)
    json_bytes = json_str.encode("utf-8")
    hash_object = hashlib.sha256()
    hash_object.update(json_bytes)
    current_hex = hash_object.hexdigest()
    return current_hex


# def get_slug(name, districts_slug):
#     slug_name = districts_slug.get(name) or "UNKNOWN"
#     return slug_name

def get_region_data(slug):
    if slug not in regions:
        return 'UNKNOWN', -1
    _name = regions[slug]["name"]
    _id = regions[slug]["regionId"]
    return _name, _id
    

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
    # while True:
    #     if await get_cache_data(mc, b"etryvoga_districts"):
    #         break
    #     else:
    #         logger.warning("get_etryvoga_data: wait for districts cache")
    #     await asyncio.sleep(1)
    while True:
        try:
            logger.debug("start get_etryvoga_data")

            cache_keys = [
                #b"etryvoga_districts_struct",
                b"explosions_etryvoga",
                b"missiles_etryvoga",
                b"drones_etryvoga",
                b"kabs_etryvoga",
            ]
            cached_data = await asyncio.gather(*(mc.get(key) for key in cache_keys))

            explosions_cached, missiles_cached, drones_cached, kabs_cached = cached_data

            # if districts_slug_cached:
            #     districts_slug_cached = json.loads(districts_slug_cached)
            # else:
            #     districts_slug_cached = {}

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

                        _name, _id = get_region_data(message.get("region", "ERROR"))
                        message["regionId"] = _id
                        logger.debug(
                            "{type:<12} {time:<5} {rid:<5}{region:<25} {state:<25} {body}".format(
                                type=message["type"],
                                state=_name,
                                rid=_id,
                                region=message.get("region", "ERROR"),
                                body=message["body"],
                                time=calculate_time_difference(
                                    format_time(message["createdAt"]), get_current_datetime()
                                ),
                            )
                        )
                        if _name == "UNKNOWN":
                            continue
                        region_data = {
                            "lastUpdate": format_time(message["createdAt"]),
                        }
                        match message["type"]:
                            case "EXPLOSION":
                                explosions_cached_data["states"][_id] = region_data
                            case "ROCKET" | "ROCKET_FIRE":
                                missiles_cached_data["states"][_id] = region_data
                            case "DRONE" | "RECON_DRONE":
                                drones_cached_data["states"][_id] = region_data
                            case "KAB":
                                kabs_cached_data["states"][_id] = region_data
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
            #get_etryvoga_districts(mc)
        )
    except asyncio.exceptions.CancelledError:
        logger.error("App stopped.")


if __name__ == "__main__":
    asyncio.run(main())
