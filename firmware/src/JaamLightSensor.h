#if BH1750_ENABLED
#include <BH1750_WE.h>
#endif
#include <WString.h>

class JaamLightSensor {
public:
    JaamLightSensor();
    bool begin(int legacy);
    void setPhotoresistorPin(int pin);
    void read();
    float getLightLevel(float lightFactor = 1.0);
    int getPhotoresistorValue(float lightFactor = 1.0);
    bool isLightSensorAvailable();
    bool isLightSensorEnabled();
    bool isAnySensorAvailable();
    String getSensorModel();
};
