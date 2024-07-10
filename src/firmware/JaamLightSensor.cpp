#include "JaamLightSensor.h"
#include <Arduino.h>

#if BH1750_ENABLED
BH1750_WE *bh1750;
#endif
bool bh1750Initialized = false;
int photoresistorPin = A4;
float lightLevel = -1;

JaamLightSensor::JaamLightSensor() {
}

bool JaamLightSensor::begin() {
#if BH1750_ENABLED
  Wire.begin();

  // init BH1750 
  pinMode(19, OUTPUT);
  digitalWrite(19, HIGH); 
  digitalWrite(19, LOW);
  delay(50); 
  digitalWrite(19, HIGH);

  bh1750 = new BH1750_WE();
  bh1750Initialized = bh1750->init();
  if (bh1750Initialized) {
    bh1750->setMode(CHM_2);
    Serial.println("Found BH1750 light sensor! Success.");
  } else {
    Serial.println("Not found BH1750 light sensor!");
  }
#endif
return bh1750Initialized;
}

void JaamLightSensor::setPhotoresistorPin(int pin) {
    photoresistorPin = pin;
}

void JaamLightSensor::read() {
#if BH1750_ENABLED
    if (!bh1750Initialized) return;
    lightLevel = bh1750->getLux();
    // Serial.print("BH1750!\tLight: ");
    // Serial.print(lightLevel);
    // Serial.println(" lx");
#endif
}

float JaamLightSensor::getLightLevel(float lightFactor) {
#if BH1750_ENABLED
    if (bh1750Initialized) {
        return lightLevel * lightFactor;
    }
#endif
  return -1;
}

int JaamLightSensor::getPhotoresistorValue(float lightFactor) {
  return analogRead(photoresistorPin) * lightFactor;
}

bool JaamLightSensor::isLightSensorAvailable() {
#if BH1750_ENABLED
  return bh1750Initialized;
#else
    return false;
#endif
}

bool JaamLightSensor::isLightSensorEnabled() {
#if BH1750_ENABLED
  return true;
#else
  return false;
#endif
}

String JaamLightSensor::getSensorModel() {
  if (bh1750Initialized) {
    return "BH1750";
  }
  return "Немає";
}
