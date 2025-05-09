#include "JaamSettings.h"
#include <Preferences.h>
#include <ArduinoJson.h>
#include <JaamUtils.h>
#include <stdexcept>
#include <map>

JaamSettings::JaamSettings() {
}

const char* PF_STRING = "S";
const char* PF_INT = "I";
const char* PF_FLOAT = "F";

struct SettingItemInt {
    const char* key;
    int value;
};

struct SettingItemString {
    const char* key;
    String value;
};

struct SettingItemFloat {
    const char* key;
    float value;
};

std::map<Type, SettingItemInt> intSettings = {
    {WS_SERVER_PORT, {"wsnp", 80}},
    {UPDATE_SERVER_PORT, {"upp", 80}},
    {LEGACY, {"legacy", 1}},
    {MAIN_LED_PIN, {"pp", 13}},
    {BG_LED_PIN, {"bpp", -1}},
    {BG_LED_COUNT, {"bpc", 0}},
    {SERVICE_LED_PIN, {"slp", -1}},
    {BUTTON_1_PIN, {"bp", -1}},
    {BUTTON_2_PIN, {"b2p", -1}},
    {ALERT_PIN, {"ap", -1}},
    {CLEAR_PIN, {"cp", -1}},
    {BUZZER_PIN, {"bzp", -1}},
    {DF_RX_PIN, {"dfrx", -1}},
    {DF_TX_PIN, {"dftx", -1}},
    {LIGHT_SENSOR_PIN, {"lp", -1}},
    {POWER_PIN, {"powp", -1}},
    {WIFI_PIN, {"wifip", -1}},
    {DATA_PIN, {"datap", -1}},
    {HA_PIN, {"hap", -1}},
    {UPD_AVAILABLE_PIN, {"resp", -1}},
    {ALERT_CLEAR_PIN_MODE, {"acpm", 0}},
    {HA_MQTT_PORT, {"ha_mqttport", 1883}},
    {CURRENT_BRIGHTNESS, {"cbr", 50}},
    {BRIGHTNESS, {"brightness", 50}},
    {BRIGHTNESS_DAY, {"brd", 50}},
    {BRIGHTNESS_NIGHT, {"brn", 5}},
    {BRIGHTNESS_MODE, {"bra", 0}},
    {HOME_ALERT_TIME, {"hat", 0}},
    {COLOR_ALERT, {"coloral", 0}},
    {COLOR_CLEAR, {"colorcl", 120}},
    {COLOR_NEW_ALERT, {"colorna", 30}},
    {COLOR_ALERT_OVER, {"colorao", 100}},
    {COLOR_EXPLOSION, {"colorex", 180}},
    {COLOR_MISSILES, {"colormi", 275}},
    {COLOR_DRONES, {"colordr", 330}},
    {COLOR_KABS, {"colorkab", 55}},
    {COLOR_HOME_DISTRICT, {"colorhd", 120}},
    {COLOR_BG_NEIGHBOR_ALERT, {"colorbna", 30}},
    {ENABLE_EXPLOSIONS, {"eex", 1}},
    {ENABLE_MISSILES, {"emi", 1}},
    {ENABLE_DRONES, {"edr", 1}},
    {ENABLE_KABS, {"ekab", 1}},
    {BRIGHTNESS_ALERT, {"ba", 100}},
    {BRIGHTNESS_CLEAR, {"bc", 100}},
    {BRIGHTNESS_NEW_ALERT, {"bna", 100}},
    {BRIGHTNESS_ALERT_OVER, {"bao", 100}},
    {BRIGHTNESS_EXPLOSION, {"bex", 100}},
    {BRIGHTNESS_HOME_DISTRICT, {"bhd", 100}},
    {BRIGHTNESS_BG, {"bbg", 100}},
    {BRIGHTNESS_SERVICE, {"bs", 50}},
    {WEATHER_MIN_TEMP, {"mintemp", -10}},
    {WEATHER_MAX_TEMP, {"maxtemp", 30}},
    {RADIATION_MAX, {"maxrad", 2000}},
    {ALARMS_AUTO_SWITCH, {"aas", 1}},
    {HOME_DISTRICT, {"hmd", 31}},
    {MIGRATION_LED_MAPPING, {"mgrlm", 0}},
    {KYIV_DISTRICT_MODE, {"kdm", 1}},
    {DISTRICT_MODE_KYIV, {"dmkv", 0}},
    {DISTRICT_MODE_KHARKIV, {"dmkh", 0}},
    {DISTRICT_MODE_ZP, {"dmzp", 0}},
    {KYIV_LED, {"kvld", 0}},
    {SERVICE_DIODES_MODE, {"sdm", 0}},
    {NEW_FW_NOTIFICATION, {"nfwn", 1}},
    {HA_LIGHT_BRIGHTNESS, {"ha_lbri", 50}},
    {HA_LIGHT_R, {"ha_lr", 215}},
    {HA_LIGHT_G, {"ha_lg", 7}},
    {HA_LIGHT_B, {"ha_lb", 255}},
    {SOUND_SOURCE, {"ss", 0}},
    {SOUND_ON_MIN_OF_SL, {"somos", 0}},
    {SOUND_ON_ALERT, {"soa", 0}},
    {MELODY_ON_ALERT, {"moa", 4}},
    {TRACK_ON_ALERT, {"toa", 0}},
    {SOUND_ON_ALERT_END, {"soae", 0}},
    {MELODY_ON_ALERT_END, {"moae", 5}},
    {TRACK_ON_ALERT_END, {"toae", 5}},
    {SOUND_ON_EXPLOSION, {"soex", 1}},
    {MELODY_ON_EXPLOSION, {"moex", 18}},
    {TRACK_ON_EXPLOSION, {"toex", 18}},
    {SOUND_ON_CRITICAL_MIG, {"socrm", 1}},
    {MELODY_ON_CRITICAL_MIG, {"mocrm", 24}},
    {TRACK_ON_CRITICAL_MIG, {"tocrm", 24}},
    {SOUND_ON_CRITICAL_STRATEGIC, {"socrs", 1}},
    {MELODY_ON_CRITICAL_STRATEGIC, {"mocrs", 25}},
    {TRACK_ON_CRITICAL_STRATEGIC, {"tocrs", 25}},
    {SOUND_ON_CRITICAL_MIG_MISSILES, {"socrmm", 1}},
    {MELODY_ON_CRITICAL_MIG_MISSILES, {"mocrmm", 26}},
    {TRACK_ON_CRITICAL_MIG_MISSILES, {"tocrmm", 26}},
    {SOUND_ON_CRITICAL_STRATEGIC_MISSILES, {"socrsm", 1}},
    {MELODY_ON_CRITICAL_STRATEGIC_MISSILES, {"mocrsm", 27}},
    {TRACK_ON_CRITICAL_STRATEGIC_MISSILES, {"tocrsm", 27}},
    {SOUND_ON_CRITICAL_BALLISTIC_MISSILES, {"socrbm", 1}},
    {MELODY_ON_CRITICAL_BALLISTIC_MISSILES, {"mocrbm", 28}},
    {TRACK_ON_CRITICAL_BALLISTIC_MISSILES, {"tocrbm", 28}},
    {CRITICAL_NOTIFICATIONS_DISPLAY_TIME, {"crndt", 30}},
    {ENABLE_CRITICAL_NOTIFICATIONS, {"ecn", 1}},
    {SOUND_ON_EVERY_HOUR, {"soeh", 0}},
    {SOUND_ON_BUTTON_CLICK, {"sobc", 0}},
    {MUTE_SOUND_ON_NIGHT, {"mson", 0}},
    {MELODY_VOLUME_DAY, {"mv", 100}},
    {MELODY_VOLUME_NIGHT, {"mvn", 30}},
    {MELODY_VOLUME_CURRENT, {"mvc", 100}},
    {INVERT_DISPLAY, {"invd", 0}},
    {DIM_DISPLAY_ON_NIGHT, {"ddon", 1}},
    {IGNORE_MUTE_ON_ALERT, {"imoa", 0}},
    {MAP_MODE, {"mapmode", 1}},
    {DISPLAY_MODE, {"dm", 2}},
    {DISPLAY_MODE_TIME, {"dmt", 5}},
    {TOGGLE_MODE_WEATHER, {"tmw", 1}},
    {TOGGLE_MODE_RADIATION, {"tmr", 1}},
    {TOGGLE_MODE_ENERGY, {"tme", 1}},
    {TOGGLE_MODE_TEMP, {"tmt", 1}},
    {TOGGLE_MODE_HUM, {"tmh", 1}},
    {TOGGLE_MODE_PRESS, {"tmp", 1}},
    {BUTTON_1_MODE, {"bm", 0}},
    {BUTTON_2_MODE, {"b2m", 0}},
    {BUTTON_1_MODE_LONG, {"bml", 0}},
    {BUTTON_2_MODE_LONG, {"b2ml", 0}},
    {USE_TOUCH_BUTTON_1, {"utb1", 0}},
    {USE_TOUCH_BUTTON_2, {"utb2", 0}},
    {ALARMS_NOTIFY_MODE, {"anm", 2}},
    {DISPLAY_MODEL, {"dsmd", 1}},
    {DISPLAY_WIDTH, {"dw", 128}},
    {DISPLAY_HEIGHT, {"dh", 32}},
    {DAY_START, {"ds", 8}},
    {NIGHT_START, {"ns", 22}},
    {WS_ALERT_TIME, {"wsat", 150000}},
    {WS_REBOOT_TIME, {"wsrt", 300000}},
    {MIN_OF_SILENCE, {"mos", 1}},
    {FW_UPDATE_CHANNEL, {"fwuc", 0}},
    {TIME_ZONE, {"tz", 2}},
    {ALERT_ON_TIME, {"aont", 5}},
    {ALERT_OFF_TIME, {"aoft", 5}},
    {EXPLOSION_TIME, {"ext", 3}},
    {ALERT_BLINK_TIME, {"abt", 3}},

};

std::map<Type, SettingItemString> stringSettings = {
    {ID, {"id", "github"}},
    {DEVICE_NAME, {"dn", "JAAM"}},
    {DEVICE_DESCRIPTION, {"dd", "JAAM Informer"}},
    {BROADCAST_NAME, {"bn", "jaam"}},
    {WS_SERVER_HOST, {"wshost", "ws.jaam.net.ua"}},
    {NTP_HOST, {"ntph", "time.google.com"}},
    {HA_MQTT_USER, {"ha_mqttuser", ""}},
    {HA_MQTT_PASSWORD, {"ha_mqttpass", ""}},
    {HA_BROKER_ADDRESS, {"ha_brokeraddr", ""}},
};

std::map<Type, SettingItemFloat> floatSettings = {
    {ALERT_CLEAR_PIN_TIME, {"acpt", 1.0f}},
    {TEMP_CORRECTION, {"ltc", 0.0f}},
    {HUM_CORRECTION, {"lhc", 0.0f}},
    {PRESSURE_CORRECTION, {"lpc", 0.0f}},
    {LIGHT_SENSOR_FACTOR, {"lsf", 1.0f}},
};

Preferences preferences;
const char* PREFS_NAME = "storage";

void JaamSettings::init() {
    preferences.begin(PREFS_NAME, true);

    // home district migration to regionID
    if (preferences.isKey("hd")) {
        int homeDistrict = preferences.getInt("hd", KYIV_REGION_ID);
        int newRegionId = mapIndexToRegionId(homeDistrict);
        if (newRegionId == -1) {
            LOG.printf("Failed to map old home district %d to new region ID\n", homeDistrict);
            newRegionId = KYIV_REGION_ID;
        }
        preferences.remove("hd");
        preferences.putInt("hmd", newRegionId);
    }

    // led map migration
    if (preferences.isKey("kdm")) {
        LOG.printf("migrateLedMapping init\n");
        int kyivDistrict = preferences.getInt("kdm", KYIV_DISTRICT_MODE);
        if (kyivDistrict == 1) {
            preferences.putInt("dmkv", 1);
            LOG.printf("DISTRICT_MODE_KYIV 1 migration done\n");
        }
        if (kyivDistrict == 2) {
            preferences.putInt("dmkv", 2);
            LOG.printf("DISTRICT_MODE_KYIV 2 migration done\n");
        }
        if (kyivDistrict == 3) {
            preferences.putInt("kvld", 1);
            LOG.printf("DISTRICT_MODE_KYIV 3 migration done\n");
        }
        if (kyivDistrict == 4) {
            preferences.putInt("dmkv", 3);
            LOG.printf("DISTRICT_MODE_KYIV 4 migration done\n");
        }
        preferences.remove("kdm");
        LOG.printf("migrateLedMapping done\n");
    };

    for (auto it = stringSettings.begin(); it != stringSettings.end(); ++it) {
        SettingItemString setting = it->second;
        setting.value = preferences.getString(setting.key, setting.value);
        it->second = setting;
    }

    for (auto it = intSettings.begin(); it != intSettings.end(); ++it) {
        SettingItemInt setting = it->second;
        setting.value = preferences.getInt(setting.key, setting.value);
        it->second = setting;
    }

    for (auto it = floatSettings.begin(); it != floatSettings.end(); ++it) {
        SettingItemFloat setting = it->second;
        setting.value = preferences.getFloat(setting.key, setting.value);
        it->second = setting;
    }

    preferences.end();
}

const char* JaamSettings::getKey(Type type) {
    if (intSettings.find(type) != intSettings.end()) {
        return intSettings[type].key;
    } else if (stringSettings.find(type) != stringSettings.end()) {
        return stringSettings[type].key;
    } else if (floatSettings.find(type) != floatSettings.end()) {
        return floatSettings[type].key;
    }
    LOG.println("Unknown setting type");
    throw std::runtime_error("Unknown setting type");
}

int JaamSettings::getInt(Type type) {
    if (intSettings.find(type) != intSettings.end()) {
        return intSettings[type].value;
    }
    LOG.println("Unknown setting type");
    throw std::runtime_error("Unknown setting type");
}

void JaamSettings::saveInt(Type type, int value, bool saveToPrefs) {
    if (intSettings.find(type) != intSettings.end()) {
        SettingItemInt setting = intSettings[type];
        if (saveToPrefs) {
            preferences.begin(PREFS_NAME, false);
            preferences.putInt(setting.key, value);
            preferences.end();
        }
        setting.value = value;
        intSettings[type] = setting;
        LOG.printf("Saved setting %s: %d (to prefs - %s)\n", setting.key, value, saveToPrefs ? "true" : "false");
        return;
    }
    LOG.println("Unknown setting type");
    throw std::runtime_error("Unknown setting type");
}

const char* JaamSettings::getString(Type type) {
    if (stringSettings.find(type) != stringSettings.end()) {
        return stringSettings[type].value.c_str();
    }
    LOG.println("Unknown setting type");
    throw std::runtime_error("Unknown setting type");
}

void JaamSettings::saveString(Type type, const char* value, bool saveToPrefs) {
    if (stringSettings.find(type) != stringSettings.end()) {
        SettingItemString setting = stringSettings[type];
        if (saveToPrefs) {
            preferences.begin(PREFS_NAME, false);
            preferences.putString(setting.key, value);
            preferences.end();
        }
        setting.value = value;
        stringSettings[type] = setting;
        LOG.printf("Saved setting %s: '%s' (to prefs - %s)\n", setting.key, value, saveToPrefs ? "true" : "false");
        return;
    }
    LOG.println("Unknown setting type");
    throw std::runtime_error("Unknown setting type");
}

float JaamSettings::getFloat(Type type) {
    if (floatSettings.find(type) != floatSettings.end()) {
        return floatSettings[type].value;
    }
    LOG.println("Unknown setting type");
    throw std::runtime_error("Unknown setting type");
}

void JaamSettings::saveFloat(Type type, float value, bool saveToPrefs) {
    if (floatSettings.find(type) != floatSettings.end()) {
        SettingItemFloat setting = floatSettings[type];
        if (saveToPrefs) {
            preferences.begin(PREFS_NAME, false);
            preferences.putFloat(setting.key, value);
            preferences.end();
        }
        setting.value = value;
        floatSettings[type] = setting;
        LOG.printf("Saved setting %s: %.1f (to prefs - %s)\n", setting.key, value, saveToPrefs ? "true" : "false");
        return;
    }
    LOG.println("Unknown setting type");
    throw std::runtime_error("Unknown setting type");
}

bool JaamSettings::getBool(Type type) {
    return getInt(type) == 1;
}

void JaamSettings::saveBool(Type type, bool value, bool saveToPrefs) {
    saveInt(type, value ? 1 : 0, saveToPrefs);
}

void JaamSettings::getSettingsBackup(Print* stream, const char* fwVersion, const char* chipID, const char* time) {
    JsonDocument doc;
    doc["fw_version"] = fwVersion;
    doc["chip_id"] = chipID;
    doc["time"] = time;
    JsonArray settingsArray = doc["settings"].to<JsonArray>();
    preferences.begin("storage", true);

    for (auto it = stringSettings.begin(); it != stringSettings.end(); ++it) {
        SettingItemString setting = it->second;
        const char* key = setting.key;
        if (preferences.isKey(key)) {
            JsonObject settingObj = settingsArray.add<JsonObject>();
            settingObj["key"] = key;
            settingObj["value"] = preferences.getString(key);
            settingObj["type"] = PF_STRING;
        }
    }

    for (auto it = intSettings.begin(); it != intSettings.end(); ++it) {
        SettingItemInt setting = it->second;
        const char* key = setting.key;
        if (preferences.isKey(key)) {
            JsonObject settingObj = settingsArray.add<JsonObject>();
            settingObj["key"] = key;
            settingObj["value"] = preferences.getInt(key);
            settingObj["type"] = PF_INT;
        }
    }

    for (auto it = floatSettings.begin(); it != floatSettings.end(); ++it) {
        SettingItemFloat setting = it->second;
        const char* key = setting.key;
        if (preferences.isKey(key)) {
            JsonObject settingObj = settingsArray.add<JsonObject>();
            settingObj["key"] = key;
            settingObj["value"] = preferences.getFloat(key);
            settingObj["type"] = PF_FLOAT;
        }
    }

    preferences.end();

    stream->print(doc.as<String>());
}

bool JaamSettings::restoreSettingsBackup(const char* settings) {
    JsonDocument doc;
    deserializeJson(doc, settings);
    JsonArray settingsArray = doc["settings"].as<JsonArray>();
    preferences.begin("storage", false);
    bool restored = false;

    for (JsonObject settingObj : settingsArray) {
        const char* key = settingObj["key"];
        const char* type = settingObj["type"];

        // skip id key, we do not need to restore it
        if (strcmp(key, "id") == 0) continue;

        if (strcmp(type, PF_STRING) == 0) {
            String valueString = settingObj["value"].as<String>();
            preferences.putString(key, valueString);
            LOG.printf("Restored setting: '%s' with value '%s'\n", key, valueString.c_str());
        } else if (strcmp(type, PF_INT) == 0) {
            int valueInt = settingObj["value"].as<int>();
            preferences.putInt(key, valueInt);
            LOG.printf("Restored setting: '%s' with value '%d'\n", key, valueInt);
        } else if (strcmp(type, PF_FLOAT) == 0) {
            float valueFloat = settingObj["value"].as<float>();
            preferences.putFloat(key, valueFloat);
            LOG.printf("Restored setting: '%s' with value '%.1f'\n", key, valueFloat);
        }
        restored = true;
    }

    preferences.end();

    return restored;
}
