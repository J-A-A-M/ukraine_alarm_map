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
int (*mapModeTransform)(int haMapMode);
bool (*displayModeChanged)(int newDisplayMode);
int (*displayModeTransform)(int haDisplayMode);
void (*onMapModeToogleClick)(void);
void (*onDisplayModeToogleClick)(void);
bool (*onShowHomeAlarmChanged)(bool newState);
bool (*onHaAutoAlarmModeChanged)(int newAutoAlarmMode);
int (*onHaAutoAlarmModeTransform)(int haAutoAlarmMode);
bool (*onHaAutoBrightnessModeChanged)(int newAutoBrightnessMode);
int (*onHaAutoBrightnessModeTransform)(int haAutoBrightnessMode);
void (*onRebootClick)(void);
bool (*onLampStateChanged)(bool newState);
bool (*onLampBrightnessChanged)(int newBrightness);
bool (*onLampColorChanged)(int newR, int newG, int newB);
bool (*onNightModeChanged)(bool newState);
void (*onMqqtConnectionStatusChanged)(bool connected);

char configUrl[35];
byte macAddress[6];

#define SENSORS_COUNT 28

char deviceUniqueID[15];

/**
 * @brief Calculates the total length of strings in a character array.
 *
 * Computes the sum of the lengths of all strings in the provided array.
 * This is a utility function for determining the total character count.
 *
 * @param array An array of constant character pointers (strings)
 * @param arraySize The number of elements in the array
 * @return int Total number of characters across all strings in the array
 *
 * @note Time complexity is O(n * m), where n is arraySize and m is the average string length
 */
static int sizeOfCharsArray(const char* array[], int arraySize) {
  int result = 0;
  for (int i = 0; i < arraySize; i++) {
    result += strlen(array[i]);
  }
  return result;
}

#endif

bool haEnabled = false;

JaamHomeAssistant::JaamHomeAssistant() {
}

/**
 * @brief Initialize the Home Assistant device configuration.
 *
 * Sets up the device parameters for Home Assistant integration, including MQTT server connection,
 * device identification, and metadata. The device is configured only if Home Assistant is enabled
 * and a valid MQTT server IP is provided.
 *
 * @param localIP Local IP address of the device
 * @param mqttServerIp IP address of the MQTT server
 * @param deviceName Friendly name of the device
 * @param currentFwVersion Current firmware version of the device
 * @param deviceDescription Detailed description of the device
 * @param chipID Unique hardware identifier for the device
 *
 * @return bool Indicates whether Home Assistant is successfully enabled and configured
 *
 * @note This method is conditionally compiled based on the HA_ENABLED preprocessor directive
 * @note Device configuration includes MAC address, unique ID, manufacturer, model, and configuration URL
 */
bool JaamHomeAssistant::initDevice(const char* localIP, const char* mqttServerIp, const char* deviceName, const char* currentFwVersion, const char* deviceDescription, const char* chipID) {
#if HA_ENABLED
  if (strlen(mqttServerIp) > 0) {
    haEnabled = true;
  }
  mqttServer = mqttServerIp;
  if (!haEnabled) return false;
  strcpy(deviceUniqueID, chipID);
  WiFi.macAddress(macAddress);
  sprintf(configUrl, "http://%s:80", localIP);
  device = new HADevice(macAddress, sizeof(macAddress));
  mqtt = new HAMqtt(netClient, *device, SENSORS_COUNT);
  device->setName(deviceName);
  device->setSoftwareVersion(currentFwVersion);
  device->setManufacturer("JAAM");
  device->setModel(deviceDescription);
  Serial.printf("HA Device configurationUrl: '%s'\n", configUrl);
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

/**
 * @brief Initializes the night brightness sensor for Home Assistant integration.
 *
 * This method sets up a configurable night brightness sensor that can be controlled
 * through Home Assistant. It creates a new HANumber sensor with a unique identifier
 * and configures its properties such as icon, name, and initial state.
 *
 * @param currentBrightness The initial brightness level for night mode
 * @param onChange A callback function that will be invoked when the brightness is changed
 *
 * @note This method only executes if Home Assistant is enabled and the home assistant
 *       functionality is not disabled
 *
 * @see HANumber
 * @see brightnessNightChanged
 */
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

/**
 * @brief Initializes a map mode sensor for Home Assistant integration.
 *
 * This method sets up a map mode selection sensor with configurable options and a change handler.
 * It is only executed if Home Assistant is enabled and the device's home assistant functionality is active.
 *
 * @param currentMapMode The initial selected map mode index
 * @param mapModes An array of map mode names/descriptions
 * @param mapModesSize The number of map modes in the array
 * @param onChange A callback function triggered when the map mode is changed
 * @param transform Optional function to transform the Home Assistant map mode value
 *
 * @note The function uses preprocessor directive #HA_ENABLED to conditionally compile the code
 * @note Creates a unique sensor ID based on the device's unique identifier
 * @note Sets sensor icon to "mdi:map" and name to "Map Mode"
 */
void JaamHomeAssistant::initMapModeSensor(int currentMapMode, const char* mapModes[], int mapModesSize, bool (*onChange)(int newMapMode), int (*transform)(int haMapMode)) {
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

/**
 * @brief Initializes a display mode sensor for Home Assistant integration.
 *
 * This method sets up a display mode selector in Home Assistant with configurable options
 * and transformation capabilities. It allows dynamic configuration of display modes
 * with optional value transformation and change handling.
 *
 * @param currentDisplayMode The initial display mode to set
 * @param displayModes Array of display mode names/descriptions
 * @param displayModesSize Number of display modes in the array
 * @param onChange Callback function invoked when display mode changes
 * @param transform Optional function to transform Home Assistant mode value before processing
 *
 * @note Only executed if Home Assistant is enabled
 * @note Sets a digital clock icon for the display mode selector
 * @note Generates a unique sensor ID based on the device's unique identifier
 */
void JaamHomeAssistant::initDisplayModeSensor(int currentDisplayMode, const char* displayModes[], int displayModesSize,
    bool (*onChange)(int newDisplayMode), int (*transform)(int haDisplayMode)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haDisplayModeID, "%s_display_mode", deviceUniqueID);
  haDisplayMode = new HASelect(haDisplayModeID);
  char displayModeOptions[sizeOfCharsArray(displayModes, displayModesSize) + displayModesSize];
  getHaOptions(displayModeOptions, displayModes, displayModesSize);
  haDisplayMode->setOptions(displayModeOptions);
  displayModeChanged = onChange;
  displayModeTransform = transform;
  haDisplayMode->onCommand([](int8_t index, HASelect* sender) { displayModeChanged(displayModeTransform(index)); });
  haDisplayMode->setIcon("mdi:clock-digital");
  haDisplayMode->setName("Display Mode");
  haDisplayMode->setCurrentState(currentDisplayMode);
#else
  return;
#endif
}

/**
 * @brief Initializes a toggle button sensor for map mode in Home Assistant.
 *
 * This method creates a button sensor that allows toggling the map mode when pressed.
 * The button is only initialized if Home Assistant is enabled and the home assistant
 * functionality is active.
 *
 * @param onClick Function pointer to be called when the map mode toggle button is clicked
 *
 * @note The button is configured with a unique ID based on the device's unique identifier
 * @note The button is set with a descriptive name "Toggle Map Mode" and an icon "mdi:map-plus"
 *
 * @pre Home Assistant must be enabled via HA_ENABLED preprocessor directive
 * @pre haEnabled flag must be true
 *
 * @see HAButton
 */
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

/**
 * @brief Initializes a sensor for controlling the visibility of home alarm time.
 *
 * This method sets up a Home Assistant switch sensor that allows toggling the display
 * of home alarm time. The sensor is only initialized if Home Assistant is enabled.
 *
 * @param currentState The initial state of the show home alarm time switch
 * @param onChange A callback function invoked when the switch state changes
 *
 * @note The sensor is configured with a timer alert icon and a descriptive name
 * @note If Home Assistant is disabled, the method returns immediately without action
 *
 * @see HASwitch
 */
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

/**
 * @brief Initialize the auto alarm mode sensor for Home Assistant integration.
 *
 * This method sets up a sensor for configuring automatic alarm modes in a home automation system.
 * It creates a selectable sensor with predefined alarm mode options and configures its properties.
 *
 * @param currentAutoAlarmMode The initial/current auto alarm mode setting
 * @param autoAlarms Array of string labels for available auto alarm modes
 * @param autoAlarmsSize Number of auto alarm modes in the array
 * @param onChange Callback function triggered when the auto alarm mode is changed
 * @param transform Optional transformation function to modify the received Home Assistant mode value
 *
 * @note This method only executes if Home Assistant is enabled and the home assistant flag is set
 * @note The sensor is configured with a default icon "mdi:alert-outline" and named "Auto Alarm"
 *
 * @see HASelect
 * @see onHaAutoAlarmModeChanged
 * @see onHaAutoAlarmModeTransform
 */
void JaamHomeAssistant::initAutoAlarmModeSensor(int currentAutoAlarmMode, const char* autoAlarms[], int autoAlarmsSize, bool (*onChange)(int newAutoAlarmMode), int (*transform)(int haAutoAlarmMode)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haAutoAlarmModeID, "%s_alarms_auto", deviceUniqueID);
  haAutoAlarmMode = new HASelect(haAutoAlarmModeID);
  char autoAlarmsModeOptions[sizeOfCharsArray(autoAlarms, autoAlarmsSize) + autoAlarmsSize];
  getHaOptions(autoAlarmsModeOptions, autoAlarms, autoAlarmsSize);
  haAutoAlarmMode->setOptions(autoAlarmsModeOptions);
  onHaAutoAlarmModeChanged = onChange;
  onHaAutoAlarmModeTransform = transform;
  haAutoAlarmMode->onCommand([](int8_t index, HASelect* sender) { onHaAutoAlarmModeChanged(onHaAutoAlarmModeTransform(index)); });
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

/**
 * @brief Initializes the Map API connectivity sensor for Home Assistant.
 *
 * This method sets up a binary sensor representing the connection status of the Map API.
 * The sensor is only initialized if Home Assistant is enabled.
 *
 * @param currentApiState The initial connection state of the Map API (true if connected, false otherwise)
 *
 * @note The sensor is configured with:
 * - A unique identifier based on the device's unique ID
 * - An icon representing network connectivity
 * - A descriptive name "Map API Connect"
 * - A device class of "connectivity"
 *
 * @pre Home Assistant functionality must be enabled via HA_ENABLED preprocessor directive
 * @pre The device's unique ID must be set before calling this method
 *
 * @warning If Home Assistant is not enabled, the method will return immediately without creating the sensor
 */
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

/**
 * @brief Initialize the auto brightness mode sensor for Home Assistant integration.
 *
 * This method sets up a Home Assistant select sensor for controlling the device's auto brightness mode.
 * It configures the sensor with a unique ID, available options, icon, and name. When a new mode is selected,
 * it triggers a callback function that can transform and process the selected mode.
 *
 * @param currentAutoBrightnessMode The initial auto brightness mode setting
 * @param autoBrightnessModes Array of available auto brightness mode names
 * @param autoBrightmesSize Number of auto brightness modes in the array
 * @param onChange Callback function to handle auto brightness mode changes
 * @param transform Optional transformation function to modify the selected mode before processing
 *
 * @note This method only executes if Home Assistant is enabled and the home assistant functionality is active
 * @note The sensor is configured with a "mdi:brightness-auto" icon and named "Auto Brightness"
 */
void JaamHomeAssistant::initAutoBrightnessModeSensor(int currentAutoBrightnessMode, const char* autoBrightnessModes[], int autoBrightmesSize, bool (*onChange)(int newAutoBrightnessMode), int (*transform)(int haAutoBrightnessMode)) {
#if HA_ENABLED
  if (!haEnabled) return;
  sprintf(haBrightnessAutoID, "%s_brightness_auto", deviceUniqueID);
  haAutoBrightnessMode = new HASelect(haBrightnessAutoID);
  char autoBrightnessOptions[sizeOfCharsArray(autoBrightnessModes, autoBrightmesSize) + autoBrightmesSize];
  getHaOptions(autoBrightnessOptions, autoBrightnessModes, autoBrightmesSize);
  haAutoBrightnessMode->setOptions(autoBrightnessOptions);
  onHaAutoBrightnessModeChanged = onChange;
  onHaAutoBrightnessModeTransform = transform;
  haAutoBrightnessMode->onCommand([](int8_t index, HASelect* sender) { onHaAutoBrightnessModeChanged(onHaAutoBrightnessModeTransform(index)); });
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
