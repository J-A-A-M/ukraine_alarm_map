#include "Definitions.h"
#if HA_ENABLED
#include <ArduinoHA.h>
#endif
#include <Arduino.h>
#include <map>

class JaamHomeAssistant {
public:
    JaamHomeAssistant();
    
    void initDevice(Client& netClient, const byte* mac, const char* deviceName,
        const char* currentFwVersion, const char* deviceDescription, const char* configUrl);
    void loop();

    bool isHaAvailable();
    bool isHaEnabled();

    void setChipID(const char* chipID);
    void setMqttServer(const char* mqttServer);
    bool connectToMqtt(const uint16_t serverPort, const char* mqttUser, const char* mqttPassword, void (*onStatusChanged)(bool connected));
    bool isMqttConnected();

    void initUptimeSensor();
    void initWifiSignalSensor();
    void initFreeMemorySensor();
    void initUsedMemorySensor();
    void initBrightnessSensor(int currentBrightness, bool (*onChange)(int newBrightness));
    void initMapModeSensor(int currentMapMode, char* mapModes[], int mapModesSize, bool (*onChange)(int newMapMode));
    std::map<int, int> initDisplayModeSensor(int currentDisplayMode, char* displayModes[], int displayModesSize, int ignoreOptions[],
        bool (*onChange)(int newDisplayMode), int (*transform)(int haDisplayMode));
    void initMapModeToggleSensor(void (*onClick)(void));
    void initDisplayModeToggleSensor(void (*onClick)(void));
    void initShowHomeAlarmTimeSensor(bool currentState, bool (*onChange)(bool newState));
    void initAutoAlarmModeSensor(int currentAutoAlarmMode, char* autoAlarms[], int autoAlarmsSize, bool (*onChange)(int newAutoAlarmMode));
    void initMapModeCurrentSensor();
    void initMapApiConnectSensor(bool currentApiState);
    void initAutoBrightnessModeSensor(int currentAutoBrightnessMode, char* autoBrightnessModes[], int autoBrightmesSize, bool (*onChange)(int newAutoBrightnessMode));
    void initRebootSensor(void (*onClick)(void));
    void initCpuTempSensor(float currentCpuTemp);
    void initHomeDistrictSensor();
    void initLampSensor(bool currentState, int currentBrightness, int currentR, int currentG, int currentB, bool (*onStateChange)(bool newState),
        bool (*onBrightnessChange)(int newBrightness), bool (*onColorChange)(int newR, int newG, int newB));
    void initAlarmAtHomeSensor(bool currentAlarmState);
    void initLocalTemperatureSensor(float currentLocalTemperature);
    void initLocalHumiditySensor(float currentLocalHumidity);
    void initLocalPressureSensor(float currentLocalPressure);
    void initLightLevelSensor(float currentLightLevel);
    void initHomeTemperatureSensor();
    void initNightModeSensor(bool currentState, bool (*onChange)(bool newState));

    void setUptime(int uptime);
    void setWifiSignal(int wifiSignal);
    void setFreeMemory(int freeMemory);
    void setUsedMemory(int usedMemory);
    void setBrightness(int brightness);
    void setMapMode(int mapMode);
    void setDisplayMode(int displayMode);
    void setMapModeCurrent(const char* mapMode);
    void setAutoAlarmMode(int autoAlarmMode);
    void setShowHomeAlarmTime(bool showHomeAlarmTime);
    void setMapApiConnect(bool apiState);
    void setAutoBrightnessMode(int autoBrightnessMode);
    void setCpuTemp(float cpuTemp);
    void setHomeDistrict(const char* homeDistrict);
    void setLampState(bool lampState);
    void setLampBrightness(int brightness);
    void setLampColor(int r, int g, int b);
    void setAlarmAtHome(bool alarmState);
    void setLocalTemperature(float localTemperature);
    void setLocalHumidity(float localHumidity);
    void setLocalPressure(float localPressure);
    void setLightLevel(float lightLevel);
    void setHomeTemperature(float homeTemperature);
    void setNightMode(bool nightMode);
};
    