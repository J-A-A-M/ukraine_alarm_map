#if BME280_ENABLED
#include <forcedBMX280.h>
#endif
#if SHT2X_ENABLED || SHT3X_ENABLED
#include <SHTSensor.h>
#endif
#include <WString.h>

class JaamClimateSensor {
    public:
        JaamClimateSensor();
        bool begin();
        void read();
        bool isTemperatureAvailable();
        bool isHumidityAvailable();
        bool isPressureAvailable();
        bool isAnySensorAvailable();
        bool isAnySensorEnabled();
        bool isBME280Available();
        bool isBMP280Available();
        bool isSHT2XAvailable();
        bool isSHT3XAvailable();
        float getTemperature(float tempCorrection = 0.0);
        float getHumidity(float humCorrection = 0.0);
        float getPressure(float pressCorrection = 0.0);
        String getSensorModel();
};
