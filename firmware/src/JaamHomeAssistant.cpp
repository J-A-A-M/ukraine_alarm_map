#include "JaamHomeAssistant.h"
#include "JaamUtils.h"
#include <WiFi.h>

#if HA_ENABLED
WiFiClient       netClient;
HADevice*        device;
HAMqtt*          mqtt;

char haUptimeID[20];
char haWifiSignalID[25];
char haFreeMemoryID[25];
char haUsedMemoryID[25];
char haCpuTempID[22];
char haBrightnessID[24];
char haBrightnessDayID[28];
char haBrightnessNightID[30];
char haMapModeID[22];
char haDisplayModeID[26];
char haAutoAlarmModeID[25];
char haBrightnessAutoID[29];
char haMapModeCurrentID[30];
char haHomeDistrictID[27];
char haMapApiConnectID[29];
char haShowHomeAlarmTimeID[34];
char haRebootID[20];
char haToggleMapModeID[29];
char haToggleDisplayModeID[33];
char haLightID[19];
char haAlarmAtHomeID[27];
char haLocalTempID[24];
char haLocalHumID[23];
char haLocalPressureID[28];
char haLightLevelID[25];
char haHomeTempID[23];
char haNightModeID[24];

HASensorNumber*  haUptime;
HASensorNumber*  haWifiSignal;
HASensorNumber*  haFreeMemory;
HASensorNumber*  haUsedMemory;
HASensorNumber*  haCpuTemp;
HANumber*        haBrightness;
HANumber*        haBrightnessDay;
HANumber*        haBrightnessNight;
HASelect*        haMapMode;
HASelect*        haDisplayMode;
HASwitch*        haShowHomeAlarmTime;
HAButton*        haToggleDisplayMode;
HASelect*        haAutoAlarmMode;
HASelect*        haAutoBrightnessMode;
HASensor*        haMapModeCurrent;
HASensor*        haHomeDistrict;
HABinarySensor*  haMapApiConnect;
HAButton*        haReboot;
HAButton*        haToggleMapMode;
HALight*         haLamp;
HABinarySensor*  haAlarmAtHome;
HASensorNumber*  haLocalTemp;
HASensorNumber*  haLocalHum;
HASensorNumber*  haLocalPressure;
HASensorNumber*  haLightLevel;
HASensorNumber*  haHomeTemp;
HASwitch*        haNightMode;

const char* mqttServer;

bool (*brightnessChanged)(int newBrightness);
bool (*brightnessDayChanged)(int newBrightness);
bool (*brightnessNightChanged)(int newBrightness);
bool (*mapModeChanged)(int newMapMode);
bool (*displayModeChanged)(int newDisplayMode);
int (*displayModeTransform)(int haDisplayMode);
void (*onMapModeToogleClick)(void);
void (*onDisplayModeToogleClick)(void);
bool (*onShowHomeAlarmChanged)(bool newState);
bool (*onHaAutoAlarmModeChanged)(int newAutoAlarmMode);
bool (*onHaAutoBrightnessModeChanged)(int newAutoBrightnessMode);
void (*onRebootClick)(void);
bool (*onLampStateChanged)(bool newState);
bool (*onLampBrightnessChanged)(int newBrightness);
bool (*onLampColorChanged)(int newR, int newG, int newB);
bool (*onNightModeChanged)(bool newState);
void (*onMqqtConnectionStatusChanged)(bool connected);

char configUrl[30];
byte macAddress[6];

#define SENSORS_COUNT 28

char deviceUniqueID[15];

static int sizeOfCharsArray(const char* array[], int arraySize) {
  int result = 0;
  for (int i = 0; i < arraySize; i++) {
    result += strlen(array[i]);
  }
  return result;
}

static std::map<int, int> getHaOptions(char* result, const char* options[], int optionsSize, int ignoreOptions[]= NULL) {
  strcpy(result, "");
  int haIndex = 0;
  std::map<int, int> haMap = {};
  for (int i = 0; i < optionsSize; i++) {
    if (ignoreOptions && isInArray(i, ignoreOptions, optionsSize)) continue;
    const char* option = options[i];
    if (i > 0) {
      strcat(result, ";");
    }
    strcat(result, option);
    haMap[i] = haIndex;
    haIndex++;
  }
  return haMap;
}
#endif

bool haEnabled = false;

JaamHomeAssistant::JaamHomeAssistant() {
}

bool JaamHomeAssistant::initDevice(const char* mqttServerIp, const char* deviceName, const char* currentFwVersion, const char* deviceDescription, const char* chipID) {
#if HA_ENABLED
  if (strlen(mqttServerIp) > 0) {
    haEnabled = true;
  }
  mqttServer = mqttServerIp;
  if (!haEnabled) return false;
  strcpy(deviceUniqueID, chipID);
  WiFi.macAddress(macAddress);
  sprintf(configUrl, "http://%s:80", WiFi.localIP().toString());
  device = new HADevice(macAddress, sizeof(macAddress));
  mqtt = new HAMqtt(netClient, *device, SENSORS_COUNT);
  device->setName(deviceName);
  device->setSoftwareVersion(currentFwVersion);
  device->setManufacturer("JAAM");
  device->setModel(deviceDescription);
  LOG.printf("HA Device configurationUrl: '%s'\n", configUrl);
  device->setConfigurationUrl(configUrl);
  device->enableExtendedUniqueIds();
  device->enableSharedAvailability();
  device->enableLastWill();
#endif
return haEnabled;
}

void JaamHomeAssistant::loop() {
#if HA_ENABLED
  if (!haEnabled) return;
  mqtt->loop();
#endif
}

bool JaamHomeAssistant::isHaAvailable() {
  return haEnabled;
}

bool JaamHomeAssistant::isHaEnabled() {
#if HA_ENABLED
  return true;
#else
  return false;
#endif
}

bool JaamHomeAssistant::connectToMqtt(const uint16_t serverPort, const char* mqttUser, const char* mqttPassword, void (*onStatusChanged)(bool connected)){
#if HA_ENABLED
  if (!haEnabled) return false;
  onMqqtConnectionStatusChanged = onStatusChanged;
  mqtt->onStateChanged([](HAMqtt::ConnectionState state) { onMqqtConnectionStatusChanged(state == HAMqtt::StateConnected); });
  return mqtt->begin(mqttServer, serverPort, mqttUser, mqttPassword);
#else
  return false;
#endif
}

bool JaamHomeAssistant::isMqttConnected() {
#if HA_ENABLED
  if (!haEnabled) return false;
  return mqtt->isConnected();
#else
  return false;
#endif
}

void JaamHomeAssistant::initUptimeSensor() {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haUptimeID, "%s_uptime", deviceUniqueID);
  haUptime = new HASensorNumber(haUptimeID);
  haUptime->setIcon("mdi:timer-outline");
  haUptime->setName("Uptime");
  haUptime->setUnitOfMeasurement("s");
  haUptime->setDeviceClass("duration");
#endif
}

void JaamHomeAssistant::initWifiSignalSensor() {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haWifiSignalID, "%s_wifi_signal", deviceUniqueID);
  haWifiSignal = new HASensorNumber(haWifiSignalID);
  haWifiSignal->setIcon("mdi:wifi");
  haWifiSignal->setName("WIFI Signal");
  haWifiSignal->setUnitOfMeasurement("dBm");
  haWifiSignal->setDeviceClass("signal_strength");
  haWifiSignal->setStateClass("measurement");
#endif
}

void JaamHomeAssistant::initFreeMemorySensor() {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haFreeMemoryID, "%s_free_memory", deviceUniqueID);
  haFreeMemory = new HASensorNumber(haFreeMemoryID);
  haFreeMemory->setIcon("mdi:memory");
  haFreeMemory->setName("Free Memory");
  haFreeMemory->setUnitOfMeasurement("kB");
  haFreeMemory->setDeviceClass("data_size");
  haFreeMemory->setStateClass("measurement");
#endif
}

void JaamHomeAssistant::initUsedMemorySensor() {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haUsedMemoryID, "%s_used_memory", deviceUniqueID);
  haUsedMemory = new HASensorNumber(haUsedMemoryID);
  haUsedMemory->setIcon("mdi:memory");
  haUsedMemory->setName("Used Memory");
  haUsedMemory->setUnitOfMeasurement("kB");
  haUsedMemory->setDeviceClass("data_size");
  haUsedMemory->setStateClass("measurement");
#endif
}

void JaamHomeAssistant::initBrightnessSensor(int currentBrightness, bool (*onChange)(int newBrightness)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haBrightnessID, "%s_brightness", deviceUniqueID);
  haBrightness = new HANumber(haBrightnessID);
  brightnessChanged = onChange;
  haBrightness->onCommand([](HANumeric number, HANumber* sender) { brightnessChanged(number.toUInt8()); });
  haBrightness->setIcon("mdi:brightness-percent");
  haBrightness->setName("Brightness");
  haBrightness->setCurrentState(currentBrightness);
#endif
}

void JaamHomeAssistant::initDayBrightnessSensor(int currentBrightness, bool (*onChange)(int newBrightness)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haBrightnessDayID, "%s_brightness_day", deviceUniqueID);
  haBrightnessDay = new HANumber(haBrightnessDayID);
  brightnessDayChanged = onChange;
  haBrightnessDay->onCommand([](HANumeric number, HANumber* sender) { brightnessDayChanged(number.toUInt8()); });
  haBrightnessDay->setIcon("mdi:brightness-5");
  haBrightnessDay->setName("Brightness Day");
  haBrightnessDay->setCurrentState(currentBrightness);
#endif
}

void JaamHomeAssistant::initNightBrightnessSensor(int currentBrightness, bool (*onChange)(int newBrightness)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haBrightnessNightID, "%s_brightness_night", deviceUniqueID);
  haBrightnessNight = new HANumber(haBrightnessNightID);
  brightnessNightChanged = onChange;
  haBrightnessNight->onCommand([](HANumeric number, HANumber* sender) { brightnessNightChanged(number.toUInt8()); });
  haBrightnessNight->setIcon("mdi:brightness-4");
  haBrightnessNight->setName("Brightness Night");
  haBrightnessNight->setCurrentState(currentBrightness);
#endif
}

void JaamHomeAssistant::initMapModeSensor(int currentMapMode, const char* mapModes[], int mapModesSize, bool (*onChange)(int newMapMode)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haMapModeID, "%s_map_mode", deviceUniqueID);
  haMapMode = new HASelect(haMapModeID);
  char mapModeOptions[sizeOfCharsArray(mapModes, mapModesSize) + mapModesSize];
  getHaOptions(mapModeOptions, mapModes, mapModesSize);
  haMapMode->setOptions(mapModeOptions);
  mapModeChanged = onChange;
  haMapMode->onCommand([](int8_t index, HASelect* sender) { mapModeChanged(index); });
  haMapMode->setIcon("mdi:map");
  haMapMode->setName("Map Mode");
  haMapMode->setCurrentState(currentMapMode);
#endif
}

std::map<int, int> JaamHomeAssistant::initDisplayModeSensor(int currentDisplayMode, const char* displayModes[], int displayModesSize, int ignoreOptions[],
    bool (*onChange)(int newDisplayMode), int (*transform)(int haDisplayMode)) {
#if HA_ENABLED
  if (!haEnabled) return {};
  sprintf(haDisplayModeID, "%s_display_mode", deviceUniqueID);
  haDisplayMode = new HASelect(haDisplayModeID);
  char displayModeOptions[sizeOfCharsArray(displayModes, displayModesSize) + displayModesSize];
  std::map<int, int> displayModeHAMap = getHaOptions(displayModeOptions, displayModes, displayModesSize, ignoreOptions);
  haDisplayMode->setOptions(displayModeOptions);
  displayModeChanged = onChange;
  displayModeTransform = transform;
  haDisplayMode->onCommand([](int8_t index, HASelect* sender) { displayModeChanged(displayModeTransform(index)); });
  haDisplayMode->setIcon("mdi:clock-digital");
  haDisplayMode->setName("Display Mode");
  haDisplayMode->setCurrentState(currentDisplayMode);
  return displayModeHAMap;
#else
  return {};
#endif
}

void JaamHomeAssistant::initMapModeToggleSensor(void (*onClick)(void)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haToggleMapModeID, "%s_toggle_map_mode", deviceUniqueID);
  haToggleMapMode = new HAButton(haToggleMapModeID);
  onMapModeToogleClick = onClick;
  haToggleMapMode->onCommand([](HAButton* sender) { onMapModeToogleClick(); });
  haToggleMapMode->setName("Toggle Map Mode");
  haToggleMapMode->setIcon("mdi:map-plus");
#endif
}

void JaamHomeAssistant::initDisplayModeToggleSensor(void (*onClick)(void)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haToggleDisplayModeID, "%s_toggle_display_mode", deviceUniqueID);
  haToggleDisplayMode = new HAButton(haToggleDisplayModeID);
  onDisplayModeToogleClick = onClick;
  haToggleDisplayMode->onCommand([](HAButton* sender) { onDisplayModeToogleClick(); });
  haToggleDisplayMode->setName("Toggle Display Mode");
  haToggleDisplayMode->setIcon("mdi:card-plus");
#endif
}

void JaamHomeAssistant::initShowHomeAlarmTimeSensor(bool currentState, bool (*onChange)(bool newState)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haShowHomeAlarmTimeID, "%s_show_home_alarm_time", deviceUniqueID);
  haShowHomeAlarmTime = new HASwitch(haShowHomeAlarmTimeID);
  onShowHomeAlarmChanged = onChange;
  haShowHomeAlarmTime->onCommand([](bool state, HASwitch* sender) { onShowHomeAlarmChanged(state); });
  haShowHomeAlarmTime->setIcon("mdi:timer-alert");
  haShowHomeAlarmTime->setName("Show Home Alert Time");
  haShowHomeAlarmTime->setCurrentState(currentState);
#endif
}

void JaamHomeAssistant::initAutoAlarmModeSensor(int currentAutoAlarmMode, const char* autoAlarms[], int autoAlarmsSize, bool (*onChange)(int newAutoAlarmMode)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haAutoAlarmModeID, "%s_alarms_auto", deviceUniqueID);
  haAutoAlarmMode = new HASelect(haAutoAlarmModeID);
  char autoAlarmsModeOptions[sizeOfCharsArray(autoAlarms, autoAlarmsSize) + autoAlarmsSize];
  getHaOptions(autoAlarmsModeOptions, autoAlarms, autoAlarmsSize);
  haAutoAlarmMode->setOptions(autoAlarmsModeOptions);
  onHaAutoAlarmModeChanged = onChange;
  haAutoAlarmMode->onCommand([](int8_t index, HASelect* sender) { onHaAutoAlarmModeChanged(index); });
  haAutoAlarmMode->setIcon("mdi:alert-outline");
  haAutoAlarmMode->setName("Auto Alarm");
  haAutoAlarmMode->setCurrentState(currentAutoAlarmMode);  
#endif
}

void JaamHomeAssistant::initMapModeCurrentSensor() {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haMapModeCurrentID, "%s_map_mode_current", deviceUniqueID);
  haMapModeCurrent = new HASensor(haMapModeCurrentID);
  haMapModeCurrent->setIcon("mdi:map");
  haMapModeCurrent->setName("Current Map Mode");
#endif
}

void JaamHomeAssistant::initMapApiConnectSensor(bool currentApiState) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haMapApiConnectID, "%s_map_api_connect", deviceUniqueID);
  haMapApiConnect = new HABinarySensor(haMapApiConnectID);
  haMapApiConnect->setIcon("mdi:server-network");
  haMapApiConnect->setName("Map API Connect");
  haMapApiConnect->setDeviceClass("connectivity");
  haMapApiConnect->setCurrentState(currentApiState);
#endif
}

void JaamHomeAssistant::initAutoBrightnessModeSensor(int currentAutoBrightnessMode, const char* autoBrightnessModes[], int autoBrightmesSize, bool (*onChange)(int newAutoBrightnessMode)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haBrightnessAutoID, "%s_brightness_auto", deviceUniqueID);
  haAutoBrightnessMode = new HASelect(haBrightnessAutoID);
  char autoBrightnessOptions[sizeOfCharsArray(autoBrightnessModes, autoBrightmesSize) + autoBrightmesSize];
  getHaOptions(autoBrightnessOptions, autoBrightnessModes, autoBrightmesSize);
  haAutoBrightnessMode->setOptions(autoBrightnessOptions);
  onHaAutoBrightnessModeChanged = onChange;
  haAutoBrightnessMode->onCommand([](int8_t index, HASelect* sender) { onHaAutoBrightnessModeChanged(index); });
  haAutoBrightnessMode->setIcon("mdi:brightness-auto");
  haAutoBrightnessMode->setName("Auto Brightness");
  haAutoBrightnessMode->setCurrentState(currentAutoBrightnessMode);
#endif
}

void JaamHomeAssistant::initRebootSensor(void (*onClick)(void)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haRebootID, "%s_reboot", deviceUniqueID);
  haReboot = new HAButton(haRebootID);
  onRebootClick = onClick;
  haReboot->onCommand([](HAButton* sender) { 
    device->setAvailability(false);
    onRebootClick(); 
  });
  haReboot->setName("Reboot");
  haReboot->setDeviceClass("restart");
#endif
}

void JaamHomeAssistant::initCpuTempSensor(float currentCpuTemp) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haCpuTempID, "%s_cpu_temp", deviceUniqueID);
  haCpuTemp = new HASensorNumber(haCpuTempID, HASensorNumber::PrecisionP2);
  haCpuTemp->setIcon("mdi:chip");
  haCpuTemp->setName("CPU Temperature");
  haCpuTemp->setDeviceClass("temperature");
  haCpuTemp->setUnitOfMeasurement("°C");
  haCpuTemp->setCurrentValue(currentCpuTemp);
  haCpuTemp->setStateClass("measurement");
#endif
}

void JaamHomeAssistant::initHomeDistrictSensor() {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haHomeDistrictID, "%s_home_district", deviceUniqueID);
  haHomeDistrict = new HASensor(haHomeDistrictID);
  haHomeDistrict->setIcon("mdi:home-map-marker");
  haHomeDistrict->setName("Home District");
#endif
}

void JaamHomeAssistant::initLampSensor(bool currentState, int currentBrightness, int currentR, int currentG, int currentB, bool (*onStateChange)(bool newState),
    bool (*onBrightnessChange)(int newBrightness), bool (*onColorChange)(int newR, int newG, int newB)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haLightID, "%s_light", deviceUniqueID);
  haLamp = new HALight(haLightID, HALight::BrightnessFeature | HALight::RGBFeature);
  haLamp->setIcon("mdi:led-strip-variant");
  haLamp->setName("Lamp");
  haLamp->setBrightnessScale(100);
  haLamp->setCurrentState(currentState);
  haLamp->setCurrentBrightness(currentBrightness);
  haLamp->setCurrentRGBColor(HALight::RGBColor(currentR, currentG, currentB));
  onLampStateChanged = onStateChange;
  haLamp->onStateCommand([](bool state, HALight* sender) { onLampStateChanged(state); });
  onLampBrightnessChanged = onBrightnessChange;
  haLamp->onBrightnessCommand([](uint8_t brightness, HALight* sender) { onLampBrightnessChanged(brightness); });
  onLampColorChanged = onColorChange;
  haLamp->onRGBColorCommand([](HALight::RGBColor color, HALight* sender) { onLampColorChanged(color.red, color.green, color.blue); });
#endif
}

void JaamHomeAssistant::initAlarmAtHomeSensor(bool currentAlarmState) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haAlarmAtHomeID, "%s_alarm_at_home", deviceUniqueID);
  haAlarmAtHome = new HABinarySensor(haAlarmAtHomeID);
  haAlarmAtHome->setIcon("mdi:rocket-launch");
  haAlarmAtHome->setName("Alarm At Home");
  haAlarmAtHome->setDeviceClass("safety");
  haAlarmAtHome->setCurrentState(currentAlarmState);
#endif
}

void JaamHomeAssistant::initLocalTemperatureSensor(float currentLocalTemperature) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haLocalTempID, "%s_local_temp", deviceUniqueID);
  haLocalTemp = new HASensorNumber(haLocalTempID, HASensorNumber::PrecisionP2);
  haLocalTemp->setIcon("mdi:thermometer");
  haLocalTemp->setName("Local Temperature");
  haLocalTemp->setUnitOfMeasurement("°C");
  haLocalTemp->setDeviceClass("temperature");
  haLocalTemp->setStateClass("measurement");
  haLocalTemp->setCurrentValue(currentLocalTemperature);
#endif
}

void JaamHomeAssistant::initLocalHumiditySensor(float currentLocalHumidity) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haLocalHumID, "%s_local_hum", deviceUniqueID);
  haLocalHum = new HASensorNumber(haLocalHumID, HASensorNumber::PrecisionP2);
  haLocalHum->setIcon("mdi:water-percent");
  haLocalHum->setName("Local Humidity");
  haLocalHum->setUnitOfMeasurement("%");
  haLocalHum->setDeviceClass("humidity");
  haLocalHum->setStateClass("measurement");
  haLocalHum->setCurrentValue(currentLocalHumidity);
#endif
}

void JaamHomeAssistant::initLocalPressureSensor(float currentLocalPressure) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haLocalPressureID, "%s_local_pressure", deviceUniqueID);
  haLocalPressure = new HASensorNumber(haLocalPressureID, HASensorNumber::PrecisionP2);
  haLocalPressure->setIcon("mdi:gauge");
  haLocalPressure->setName("Local Pressure");
  haLocalPressure->setUnitOfMeasurement("mmHg");
  haLocalPressure->setDeviceClass("pressure");
  haLocalPressure->setStateClass("measurement");
  haLocalPressure->setCurrentValue(currentLocalPressure);
#endif
}

void JaamHomeAssistant::initLightLevelSensor(float currentLightLevel) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haLightLevelID, "%s_light_level", deviceUniqueID);
  haLightLevel = new HASensorNumber(haLightLevelID, HASensorNumber::PrecisionP2);
  haLightLevel->setIcon("mdi:brightness-5");
  haLightLevel->setName("Light Level");
  haLightLevel->setUnitOfMeasurement("lx");
  haLightLevel->setDeviceClass("illuminance");
  haLightLevel->setStateClass("measurement");
  haLightLevel->setCurrentValue(currentLightLevel);
#endif
}

void JaamHomeAssistant::initHomeTemperatureSensor() {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haHomeTempID, "%s_home_temp", deviceUniqueID);
  haHomeTemp = new HASensorNumber(haHomeTempID, HASensorNumber::PrecisionP2);
  haHomeTemp->setIcon("mdi:home-thermometer");
  haHomeTemp->setName("Home District Temperature");
  haHomeTemp->setUnitOfMeasurement("°C");
  haHomeTemp->setDeviceClass("temperature");
  haHomeTemp->setStateClass("measurement");
#endif
}

void JaamHomeAssistant::initNightModeSensor(bool currentState, bool (*onChange)(bool newState)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haNightModeID, "%s_night_mode", deviceUniqueID);
  haNightMode = new HASwitch(haNightModeID);
  onNightModeChanged = onChange;
  haNightMode->onCommand([](bool state, HASwitch* sender) { onNightModeChanged(state); });
  haNightMode->setIcon("mdi:shield-moon-outline");
  haNightMode->setName("Night Mode");
  haNightMode->setCurrentState(currentState);
#endif
}

void JaamHomeAssistant::setUptime(int uptime) {
#if HA_ENABLED
  if (!haEnabled) return;
  haUptime->setValue(uptime);
#endif
}

void JaamHomeAssistant::setWifiSignal(int wifiSignal) {
#if HA_ENABLED
  if (!haEnabled) return;
  haWifiSignal->setValue(wifiSignal);
#endif
}

void JaamHomeAssistant::setFreeMemory(int freeMemory) {
#if HA_ENABLED
  if (!haEnabled) return;
  haFreeMemory->setValue(freeMemory);
#endif
}

void JaamHomeAssistant::setUsedMemory(int usedMemory) {
#if HA_ENABLED
  if (!haEnabled) return;
  haUsedMemory->setValue(usedMemory);
#endif
}

void JaamHomeAssistant::setBrightness(int brightness) {
#if HA_ENABLED
  if (!haEnabled) return;
  haBrightness->setState(brightness);
#endif
}

void JaamHomeAssistant::setDayBrightness(int brightness) {
#if HA_ENABLED
  if (!haEnabled) return;
  haBrightnessDay->setState(brightness);
#endif
}

void JaamHomeAssistant::setNightBrightness(int brightness) {
#if HA_ENABLED
  if (!haEnabled) return;
  haBrightnessNight->setState(brightness);
#endif
}

void JaamHomeAssistant::setMapMode(int mapMode) {
#if HA_ENABLED
  if (!haEnabled) return;
  haMapMode->setState(mapMode);
#endif
}

void JaamHomeAssistant::setDisplayMode(int displayMode) {
#if HA_ENABLED
  if (!haEnabled) return;
  haDisplayMode->setState(displayMode);
#endif
}

void JaamHomeAssistant::setMapModeCurrent(const char* mapMode) {
#if HA_ENABLED
  if (!haEnabled) return;
  haMapModeCurrent->setValue(mapMode);
#endif
}

void JaamHomeAssistant::setAutoAlarmMode(int autoAlarmMode) {
#if HA_ENABLED
  if (!haEnabled) return;
  haAutoAlarmMode->setState(autoAlarmMode);
#endif
}

void JaamHomeAssistant::setShowHomeAlarmTime(bool showHomeAlarmTime) {
#if HA_ENABLED
  if (!haEnabled) return;
  haShowHomeAlarmTime->setState(showHomeAlarmTime);
#endif
}

void JaamHomeAssistant::setMapApiConnect(bool apiState) {
#if HA_ENABLED
  if (!haEnabled) return;
  haMapApiConnect->setState(apiState, true);
#endif
}

void JaamHomeAssistant::setAutoBrightnessMode(int autoBrightnessMode) {
#if HA_ENABLED
  if (!haEnabled) return;
  haAutoBrightnessMode->setState(autoBrightnessMode);
#endif
}

void JaamHomeAssistant::setCpuTemp(float cpuTemp) {
#if HA_ENABLED
  if (!haEnabled) return;
  haCpuTemp->setValue(cpuTemp);
#endif
}

void JaamHomeAssistant::setHomeDistrict(const char* homeDistrict) {
#if HA_ENABLED
  if (!haEnabled) return;
  haHomeDistrict->setValue(homeDistrict);
#endif
}

void JaamHomeAssistant::setLampState(bool lampState) {
#if HA_ENABLED
  if (!haEnabled) return;
  haLamp->setState(lampState);
#endif
}

void JaamHomeAssistant::setLampBrightness(int brightness) {
#if HA_ENABLED
  if (!haEnabled) return;
  haLamp->setBrightness(brightness);
#endif
}

void JaamHomeAssistant::setLampColor(int r, int g, int b) {
#if HA_ENABLED
  if (!haEnabled) return;
  haLamp->setRGBColor(HALight::RGBColor(r, g, b));
#endif
}

void JaamHomeAssistant::setAlarmAtHome(bool alarmState) {
#if HA_ENABLED
  if (!haEnabled) return;
  haAlarmAtHome->setState(alarmState);
#endif
}

void JaamHomeAssistant::setLocalTemperature(float localTemperature) {
#if HA_ENABLED
  if (!haEnabled) return;
  haLocalTemp->setValue(localTemperature);
#endif
}

void JaamHomeAssistant::setLocalHumidity(float localHumidity) {
#if HA_ENABLED
  if (!haEnabled) return;
  haLocalHum->setValue(localHumidity);
#endif
}

void JaamHomeAssistant::setLocalPressure(float localPressure) {
#if HA_ENABLED
  if (!haEnabled) return;
  haLocalPressure->setValue(localPressure);
#endif
}

void JaamHomeAssistant::setLightLevel(float lightLevel) {
#if HA_ENABLED
  if (!haEnabled) return;
  haLightLevel->setValue(lightLevel);
#endif
}

void JaamHomeAssistant::setHomeTemperature(float homeTemperature) {
#if HA_ENABLED
  if (!haEnabled) return;
  haHomeTemp->setValue(homeTemperature);
#endif
}

void JaamHomeAssistant::setNightMode(bool nightMode) {
#if HA_ENABLED
  if (!haEnabled) return;
  haNightMode->setState(nightMode);
#endif
}
