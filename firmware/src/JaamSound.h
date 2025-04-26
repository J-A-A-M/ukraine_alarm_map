#pragma once
#include <cmath>
#include "Constants.h"
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
        int buzzerPin;
        bool dfConnected; 
        int dfRxPin;
        int dfTxPin;
        
    public:
    #if DFPLAYER_PRO_ENABLED
        int maxFilesCount;
    #endif
        int dfTotalFiles;
        int volumeCurrent;
        int volumeDay;
        int volumeNight;
        int soundSource;// 0 - Buzzer  1 - DFPlayer  2 - Any
        String* dynamicTracks;
        SettingListItem* dynamicTrackNames;

        JaamSound() : 
        #if DFPLAYER_PRO_ENABLED
            dfSerial(2), 
            dfPlayerMaxVolume(15),
            maxFilesCount(50), 
        #endif
            dfConnected(false),
            dfTotalFiles(0),
            buzzerPin(-1), 
            dfRxPin(-1), 
            dfTxPin(-1)
        {};
        void init(int buzzerPin, int rxPin, int txPin, int volCurrent, int volDay, int volNight);
        void setVolumeCurrent(int volume);
        void setVolumeDay(int volume);
        void setVolumeNight(int volume);
        void setSoundSource(int source);
    #if BUZZER_ENABLED
        void initBuzzer();
        void playBuzzer(const char* melodyRtttl);
        void setBuzzerVolume(int volume);
    #endif
    #if DFPLAYER_PRO_ENABLED
        void initDFPlayer();
        void playDFPlayer(String trackPath);
        void setDFPlayerVolume(int volume);
        int getDFPlayerFilesCount();
        bool isDFPlayerFilesLimitReached(int dfTotalFiles);
    #endif
        String getTrackById(int id);
        int findTrackIndex(int number);
        bool isBuzzerEnabled();
        bool isBuzzerPlaying();
        bool isDFPlayerEnabled();
        bool isDFPlayerPlaying();
        bool isDFPlayerConnected();
};