#if BUZZER_ENABLED
#include <melody_player.h>
#include <melody_factory.h>
#endif
#if DFPLAYER_PRO_ENABLED
#include <DFRobot_DF1201S.h>
#include <HardwareSerial.h>
#endif


class JaamSound {
    private:
    #if BUZZER_ENABLED
        MelodyPlayer* player;
        int expMap(int x, int in_min, int in_max, int out_min, int out_max) {
            // Apply exponential transformation to the original input value x
            float normalized = (float)(x - in_min) / (in_max - in_min);
            float scaled = pow(normalized, 2);
            
            // Map the scaled value to the output range
            return (int)(scaled * (out_max - out_min) + out_min);
        }
    #endif
    #if DFPLAYER_PRO_ENABLED
        HardwareSerial dfSerial;
        DFRobot_DF1201S dfplayer;
        int dfPlayerMaxVolume;
        
    #endif
        bool dfConnected; 
    public:
    #if DFPLAYER_PRO_ENABLED
        int maxFilesCount;
        JaamSound() : dfSerial(2), dfPlayerMaxVolume(15), dfConnected(false), maxFilesCount(50) {}
    #else
        JaamSound() {}
    #endif
    #if BUZZER_ENABLED
        void initBuzzer(int buzzerPin, int volumeCurrent);
        void playBuzzer(const char* melodyRtttl);
        void setBuzzerVolume(int volume);
    #endif
    #if DFPLAYER_PRO_ENABLED
        void initDFPlayer(int rxPin, int txPin, int volumeCurrent);
        void playDFPlayer(String trackPath);
        void setDFPlayerVolume(int volume);
        int getDFPlayerFilesCount();
        bool isDFPlayerfilesLimit(int totalFiles);
    #endif
        bool isBuzzerPlaying();
        bool isDFPlayerPlaying();
        bool isDFPlayerConnected();
};