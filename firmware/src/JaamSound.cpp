#include "JaamSound.h"
#include "JaamLogs.h"

#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
void JaamSound::init(int bPin, int rxPin, int txPin, int volCurrent, int volDay, int volNight) {
    volumeCurrent = volCurrent;
    volumeDay = volDay;
    volumeNight = volNight;
    buzzerPin = bPin;
    dfRxPin = rxPin;
    dfTxPin = txPin;
    LOG.printf("Sound pins set: buzzerPin %d, rx %d, tx %d\n", bPin, rxPin, txPin);
}
#endif

void JaamSound::setVolumeCurrent(int volume) {
    volumeCurrent = volume;
}
void JaamSound::setVolumeDay(int volume) {
    volumeDay = volume;
}
void JaamSound::setVolumeNight(int volume) {
    volumeNight = volume;
}
void JaamSound::setSoundSource(int source) {
    soundSource = source;
}

#if BUZZER_ENABLED
void JaamSound::initBuzzer() {
    LOG.println("Init Buzzer");
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

bool JaamSound::isBuzzerEnabled() {
#if BUZZER_ENABLED
    if (buzzerPin > 0) {
        return true;
    }
#endif
    return false;
}

bool JaamSound::isBuzzerPlaying() {
#if BUZZER_ENABLED
    if (!isBuzzerEnabled()) {
        LOG.println("Buzzer not enabled, cannot check if playing");
        return false;
    }
    return player->isPlaying();
#else
    return false;
#endif
}

#if DFPLAYER_PRO_ENABLED
bool JaamSound::isDFPlayerFilesLimitReached(int totalFiles) {
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot check files limit");
        return false;
    }
    if (totalFiles > maxFilesCount) {
        LOG.printf("DFPlayer files limit reached: %d/%d\n", totalFiles, maxFilesCount);
        return true;
    }
    return false;
}
void JaamSound::initDFPlayer() {
    int8_t attempts = 5;
    int8_t count = 1;
    dfSerial.begin(115200, SERIAL_8N1, dfRxPin, dfTxPin); // RX, TX

    LOG.println("Init DFPlayer");
    LOG.printf("rx, tx: %d, %d\n", dfRxPin, dfTxPin);

    // Turn off the start prompt
    dfSerial.print("AT+PROMPT=OFF\r\n");
    delay(100);
    while (dfSerial.available()) {
        LOG.println(dfSerial.read());
    }

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

    dfplayer.setPlayMode(dfplayer.SINGLECYCLE);
    LOG.print("PlayMode: ");
    LOG.println(dfplayer.getPlayMode());
    delay(500);

    dfplayer.setLED(false);
}

void JaamSound::playDFPlayer(String trackPath) {
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot play track");
        return;
    }
    dfplayer.playSpecFile(trackPath);
    LOG.printf("Track played: %s (%s)\n", trackPath.c_str(), dfplayer.getFileName());
}


void JaamSound::setDFPlayerVolume(int volume) {
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot set volume");
        return;
    }
    dfplayer.setVol(map(volume, 0, 100, 0, dfPlayerMaxVolume));
    LOG.printf("Set DFPlayer volume to: %d\n", volume);
}



int JaamSound::getDFPlayerFilesCount() {
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot get files count");
        return 0;
    }
    int filesCount = dfplayer.getTotalFile();
    LOG.printf("DFPlayer files count: %d\n", filesCount);
    return filesCount;
}
#endif

bool JaamSound::isDFPlayerEnabled() {
    return dfRxPin > -1 && dfTxPin > -1;
}

bool JaamSound::isDFPlayerPlaying() {
#if DFPLAYER_PRO_ENABLED
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot check if playing");
        return false;
    }
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

