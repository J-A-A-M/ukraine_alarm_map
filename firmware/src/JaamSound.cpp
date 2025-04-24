#include "JaamSound.h"
#include "JaamLogs.h"

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
HardwareSerial dfSerial(2);
DFRobot_DF1201S dfplayer;
int dfPlayerMaxVolume = 15;
bool dfConnected = false;
#endif



JaamSound::JaamSound() {
}


#if BUZZER_ENABLED
void JaamSound::initBuzzer(int buzzerPin, int volumeCurrent) {
    player = new MelodyPlayer(buzzerPin, 0, LOW);
    player->setVolume(expMap(volumeCurrent, 0, 100, 0, 255));
    LOG.printf("Set initial volume to: %d\n", volumeCurrent);

}

void JaamSound::playBuzzer(const char* melodyRtttl) {
    Melody melody = MelodyFactory.loadRtttlString(melodyRtttl);
    player->playAsync(melody);
}

void JaamSound::setBuzzerVolume(int volume) {
    player->setVolume(expMap(volume, 0, 100, 0, 255));
    LOG.printf("Set buzzer volume to: %d\n", volume);
}
#endif

bool JaamSound::isBuzzerPlaying() {
#if BUZZER_ENABLED
    return player->isPlaying();
#else
    return false;
#endif
}

#if DFPLAYER_PRO_ENABLED
void JaamSound::initDFPlayer(int rxPin, int txPin, int volumeCurrent) {
    int8_t attempts = 5;
    int8_t count = 1;
    dfSerial.begin(115200, SERIAL_8N1, rxPin, txPin); // RX, TX

    LOG.println("Init DFPlayer");
    LOG.printf("rx, tx: %d, %d\n", rxPin, txPin);

    while (!dfplayer.begin(dfSerial)) {
      LOG.printf("Attempt #%d of %d\n", count, attempts);
      LOG.println("DFPlayer not found...");
      delay(1000);
      count++;
      if (count > attempts) return;
      
    }
    LOG.println("DFPlayer RX OK!");
    dfplayer.setVol(2);
    delay(500); 
    if (dfplayer.getVol() != 2) {
      LOG.println("DFPlayer TX Fail!");
      return;
    }
    LOG.println("DFPlayer TX OK!");
    dfConnected = true;
    LOG.println("DFPlayer ready!");

    dfplayer.setVol(0); 
    dfplayer.switchFunction(dfplayer.MUSIC);
    dfplayer.setVol(map(volumeCurrent, 0, 100, 0, dfPlayerMaxVolume));
    LOG.print("Volume: ");
    LOG.println(dfplayer.getVol());

    dfplayer.setPlayMode(dfplayer.ALLCYCLE);
    LOG.print("PlayMode: ");
    LOG.println(dfplayer.getPlayMode());
    delay(500);

    dfplayer.setLED(false);
}

void JaamSound::playDfPlayer(String trackPath) {
    dfplayer.playSpecFile(trackPath);
    LOG.printf("Track played: %s (%s)\n", trackPath.c_str(), dfplayer.getFileName());
}


void JaamSound::setDFPlayerVolume(int volume) {
    dfplayer.setVol(map(volume, 0, 100, 0, dfPlayerMaxVolume));
    LOG.printf("Set DFPlayer volume to: %d\n", volume);
}



int JaamSound::getDfPlayerFilesCount() {
    int filesCount = dfplayer.getTotalFile();
    LOG.printf("DFPlayer files count: %d\n", filesCount);
    return filesCount;
}
#endif
bool JaamSound::isDFPlayerPlaying() {
#if DFPLAYER_PRO_ENABLED
    return dfplayer.isPlaying();
#else
    return false;
#endif
}

bool JaamSound::isDFPlayerConnected() {
#if DFPLAYER_PRO_ENABLED
    return dfConnected;
#else
    return false;
#endif
}

