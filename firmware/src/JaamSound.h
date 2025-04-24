#if BUZZER_ENABLED
#include <melody_player.h>
#include <melody_factory.h>
#endif
#if DFPLAYER_PRO_ENABLED
#include <DFRobot_DF1201S.h>
#include <HardwareSerial.h>
#endif


class JaamSound {

    public:
        JaamSound();
#if BUZZER_ENABLED
        void initBuzzer(int buzzerPin, int volumeCurrent);
        void playBuzzer(const char* melodyRtttl);
        void setBuzzerVolume(int volume);
#endif
#if DFPLAYER_PRO_ENABLED
        void initDFPlayer(int rxPin, int txPin, int volumeCurrent);
        void playDfPlayer(String trackPath);
        void setDFPlayerVolume(int volume);
        int getDfPlayerFilesCount();
#endif
        bool isBuzzerPlaying();
        bool isDFPlayerPlaying();
        bool isDFPlayerConnected();
};