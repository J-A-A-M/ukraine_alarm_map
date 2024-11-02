#include "JaamClimateSensor.h"
#include <Arduino.h>

#if BME280_ENABLED
ForcedBME280Float *bme280;
#endif
#if SHT2X_ENABLED
SHTSensor *sht2x;
#endif
#if SHT3X_ENABLED
SHTSensor *sht3x;
#endif
bool bme280Initialized = false;
bool bmp280Initialized = false;
bool sht2xInitialized = false;
bool sht3xInitialized = false;
float localTemp = -273;
float localHum = -1;
float localPressure = -1;

JaamClimateSensor::JaamClimateSensor() {
}

bool JaamClimateSensor::begin() {
#if BME280_ENABLED || SHT2X_ENABLED || SHT3X_ENABLED
  Wire.begin();
#endif
#if BME280_ENABLED
  bme280 = new ForcedBME280Float();
  bme280->begin();
  switch (bme280->getChipID()) {
    case CHIP_ID_BME280:
      bme280Initialized = true;
      Serial.println("Found BME280 temp/hum/presure sensor! Success.");
      break;
    case CHIP_ID_BMP280:
      bmp280Initialized = true;
      Serial.println("Found BMP280 temp/presure sensor! No Humidity available.");
      break;
    default:
      bme280Initialized = false;
      bmp280Initialized = false;
      Serial.println("Not found BME280 or BMP280!");
  }
#endif
#if SHT2X_ENABLED
  sht2x = new SHTSensor(SHTSensor::SHT2X);
  sht2xInitialized = sht2x->init();
  if (sht2xInitialized) {
    Serial.println("Found HTU2x temp/hum sensor! Success.");
  } else {
    Serial.println("Not found HTU2x temp/hum sensor!");
  }
#endif
#if SHT3X_ENABLED
  sht3x = new SHTSensor(SHTSensor::SHT3X);
  sht3xInitialized = sht3x->init();
  if (sht3xInitialized) {
    Serial.println("Found SHT3x temp/hum sensor! Success.");
  } else {
    Serial.println("Not found SHT3x temp/hum sensor!");
  }
#endif
return bme280Initialized || bmp280Initialized || sht2xInitialized || sht3xInitialized;
}

void JaamClimateSensor::read() {
#if BME280_ENABLED
  if (bme280Initialized || bmp280Initialized) {
    bme280->takeForcedMeasurement();

    localTemp = bme280->getTemperatureCelsiusAsFloat();
    localPressure = bme280->getPressureAsFloat() * 0.75006157584566;  //mmHg

    if (bme280Initialized) {
      localHum = bme280->getRelativeHumidityAsFloat();
    }

    // Serial.print("BME280! Temp: ");
    // Serial.print(localTemp);
    // Serial.print("°C");
    // Serial.print("\tHumidity: ");
    // Serial.print(localHum);
    // Serial.print("%");
    // Serial.print("\tPressure: ");
    // Serial.print(localPressure);
    // Serial.println("mmHg");
    return;
  }
#endif
#if SHT3X_ENABLED
  if (sht3xInitialized && sht3x->readSample()) {
    localTemp = sht3x->getTemperature();
    localHum = sht3x->getHumidity();

    // Serial.print("SHT3X! Temp: ");
    // Serial.print(localTemp);
    // Serial.print("°C");
    // Serial.print("\tHumidity: ");
    // Serial.print(localHum);
    // Serial.println("%");
    return;
  }
#endif
#if SHT2X_ENABLED
  if (sht2xInitialized && sht2x->readSample()) {
    localTemp = sht2x->getTemperature();
    localHum = sht2x->getHumidity();

    // Serial.print("SHT2X! Temp: ");
    // Serial.print(localTemp);
    // Serial.print("°C");
    // Serial.print("\tHumidity: ");
    // Serial.print(localHum);
    // Serial.println("%");
    return;
  }
#endif
}

bool JaamClimateSensor::isTemperatureAvailable() {
  return (bme280Initialized || bmp280Initialized || sht2xInitialized || sht3xInitialized) && localTemp > -273;
}

bool JaamClimateSensor::isHumidityAvailable() {
  return (bme280Initialized || sht2xInitialized || sht3xInitialized) && localHum >= 0;
}

bool JaamClimateSensor::isPressureAvailable() {
  return (bme280Initialized || bmp280Initialized) && localPressure >= 0;
}

float JaamClimateSensor::getTemperature(float tempCorrection) {
  return localTemp + tempCorrection;
}

float JaamClimateSensor::getHumidity(float humCorrection) {
  return localHum + humCorrection;
}

float JaamClimateSensor::getPressure(float pressCorrection) {
  return localPressure + pressCorrection;
}

String JaamClimateSensor::getSensorModel() {
  if (bme280Initialized) {
    return "BME280";
  }
  if (bmp280Initialized) {
    return "BMP280";
  }
  if (sht3xInitialized) {
    return "SHT3X";
  }
  if (sht2xInitialized) {
    return "SHT2X";
  }
  return "Немає";
}

bool JaamClimateSensor::isAnySensorAvailable() {
  return isBME280Available() || isBMP280Available() || isSHT2XAvailable() || isSHT3XAvailable();
}

bool JaamClimateSensor::isAnySensorEnabled() {
  return BME280_ENABLED || SHT2X_ENABLED || SHT3X_ENABLED;
}

bool JaamClimateSensor::isBME280Available() {

  return bme280Initialized;
}

bool JaamClimateSensor::isBMP280Available() {
  return bmp280Initialized;
}

bool JaamClimateSensor::isSHT2XAvailable() {
  return sht2xInitialized;
}

bool JaamClimateSensor::isSHT3XAvailable() {
  return sht3xInitialized;
}
