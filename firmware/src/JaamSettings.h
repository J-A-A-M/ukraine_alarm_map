#include <Print.h>
#include <Constants.h>

class JaamSettings {

public:
    JaamSettings();
    void init();
    const char* getKey(Type type);
    int getInt(Type type);
    void saveInt(Type type, int value, bool saveToPrefs = true);
    const char* getString(Type type);
    void saveString(Type type, const char* value, bool saveToPrefs = true);
    float getFloat(Type type);
    void saveFloat(Type type, float value, bool saveToPrefs = true);
    bool getBool(Type type);
    void saveBool(Type type, bool value, bool saveToPrefs = true);
    void getSettingsBackup(Print* stream, const char* fwVersion, const char* chipID, const char* time);
    bool restoreSettingsBackup(const char* settings);
};