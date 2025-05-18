#include "JaamSound.h"
#include "JaamLogs.h"

#if BUZZER_ENABLED || DFPLAYER_PRO_ENABLED
/**
 * @brief Initializes sound hardware pin assignments and volume settings.
 *
 * Sets the pins for the buzzer and DFPlayer modules, and configures the current, day, and night volume levels.
 *
 * @param bPin Pin number for the buzzer.
 * @param rxPin RX pin number for the DFPlayer module.
 * @param txPin TX pin number for the DFPlayer module.
 * @param volCurrent Volume level for the current mode.
 * @param volDay Volume level for day mode.
 * @param volNight Volume level for night mode.
 */
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

/**
 * @brief Sets the current volume level for sound playback.
 *
 * Updates the internal variable representing the current volume setting.
 *
 * @param volume The desired volume level.
 */
void JaamSound::setVolumeCurrent(int volume) {
    volumeCurrent = volume;
}
/**
 * @brief Sets the daytime volume level for sound playback.
 *
 * Updates the internal variable representing the volume to be used during daytime operation.
 *
 * @param volume The desired daytime volume level (range depends on implementation).
 */
void JaamSound::setVolumeDay(int volume) {
    volumeDay = volume;
}
/**
 * @brief Sets the night mode volume level.
 *
 * Updates the internal volume setting used for night mode playback.
 *
 * @param volume The desired night mode volume level (0–100).
 */
void JaamSound::setVolumeNight(int volume) {
    volumeNight = volume;
}
/**
 * @brief Sets the current sound source identifier.
 *
 * @param source Integer value representing the desired sound source.
 */
void JaamSound::setSoundSource(int source) {
    soundSource = source;
}

#if BUZZER_ENABLED
/**
 * @brief Initializes the buzzer for sound playback.
 *
 * Creates a MelodyPlayer instance on the configured buzzer pin and sets the initial volume based on the current volume setting.
 */
void JaamSound::initBuzzer() {
    LOG.println("Init Buzzer");
    player = new MelodyPlayer(buzzerPin, 0, LOW);
    player->setVolume(expMap(volumeCurrent, 0, 100, 0, 255));
    LOG.printf("Set initial volume to: %d\n", volumeCurrent);

}

/**
 * @brief Plays a melody on the buzzer asynchronously from an RTTTL string.
 *
 * If the buzzer is not initialized, the function does nothing.
 *
 * @param melodyRtttl RTTTL-formatted string representing the melody to play.
 */
void JaamSound::playBuzzer(const char* melodyRtttl) {
    if (player == nullptr) {
        LOG.println("Buzzer not initialised, cannot play melody");
        return;
    }
    Melody melody = MelodyFactory.loadRtttlString(melodyRtttl);
    player->playAsync(melody);
}

/**
 * @brief Sets the buzzer volume to the specified level.
 *
 * Adjusts the buzzer's output volume using an exponential mapping from a 0–100 scale to the hardware's 0–255 range.
 *
 * @param volume Desired volume level (0–100).
 */
void JaamSound::setBuzzerVolume(int volume) {
    if (player == nullptr) {
        LOG.println("Buzzer not initialised, cannot set volume");
        return;
    }
    player->setVolume(expMap(volume, 0, 100, 0, 255));
    LOG.printf("Set buzzer volume to: %d\n", volume);
}
#endif

/**
 * @brief Checks if the buzzer is enabled and properly configured.
 *
 * @return true if the buzzer feature is enabled and the buzzer pin is set; false otherwise.
 */
bool JaamSound::isBuzzerEnabled() {
#if BUZZER_ENABLED
    if (buzzerPin > 0) {
        return true;
    }
#endif
    return false;
}

/**
 * @brief Checks if the buzzer is currently playing a melody.
 *
 * @return true if the buzzer is enabled and playing; false otherwise.
 */
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

/**
     * @brief Finds the index of a track matching the given number in the TRACKS array.
     *
     * Formats the number as a zero-padded MP3 filename (e.g., "/01.mp3") and searches for it in the TRACKS array.
     * 
     * @param number The track number to search for.
     * @return Index of the matching track in TRACKS, or -1 if not found.
     */
    int JaamSound::findTrackIndex(int number) {
    #if DFPLAYER_PRO_ENABLED
      String trackName = String("/") + (number < 10 ? "0" : "") + String(number) + ".mp3";
    
      for (int i = 0; i < TRACKS_COUNT; i++) {
        if (TRACKS[i] == trackName) {
          return i;
        }
      }
    #endif
      return -1;
    }
/**
 * @brief Retrieves the file path of a track by its ID if the DFPlayer is connected.
 *
 * Searches the loaded track list for a track with the specified ID and returns its file path. Returns an empty string if the DFPlayer is not connected or the ID is not found.
 *
 * @param id The unique identifier of the track.
 * @return String The file path of the track, or an empty string if not found or not connected.
 */
String JaamSound::getTrackById(int id) {
    if (dfConnected) {
        for (int i = 0; i < dfTotalFiles; i++) {
            if (dynamicTrackNames[i].id == id) {
            return dynamicTracks[i];
            }
        }
    }
    return "";
}

#if DFPLAYER_PRO_ENABLED
/**
 * @brief Checks if the DFPlayer's file count exceeds the allowed maximum.
 *
 * @param dfTotalFiles The total number of files detected on the DFPlayer.
 * @return true if the file count exceeds the maximum allowed; false otherwise or if the DFPlayer is not connected.
 */
bool JaamSound::isDFPlayerFilesLimitReached(int dfTotalFiles) {
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot check files limit");
        return false;
    }
    if (dfTotalFiles > maxFilesCount) {
        LOG.printf("DFPlayer files limit reached: %d/%d\n", dfTotalFiles, maxFilesCount);
        return true;
    }
    return false;
}
/**
 * @brief Initializes the DFPlayer Pro audio module and loads available audio tracks.
 *
 * Attempts to establish communication with the DFPlayer Pro using the configured serial pins, disables the startup prompt, and verifies bidirectional communication. Sets initial volume, playback mode, and disables the onboard LED. Retrieves the total number of playable files, checks against the maximum allowed, and dynamically allocates arrays for track paths and names. Populates these arrays with either predefined or default track information for each available file.
 */
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
      if (count > attempts) {
        LOG.println("DFPlayer init failed: max attempts reached");
        return;
      }
      
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

    dfTotalFiles = getDFPlayerFilesCount();
    if (dfTotalFiles <= 0) {
    LOG.printf("DFPlayer has no playable files\n");
      return;
    }
    if (isDFPlayerFilesLimitReached(dfTotalFiles)) {
      LOG.printf("DFPlayer files limit reached: (%d/%d)\n", dfTotalFiles, maxFilesCount);
      return;
    }

    dynamicTracks = new String[dfTotalFiles];
    dynamicTrackNames = new SettingListItem[dfTotalFiles];

    for (int i = 0; i < dfTotalFiles; i++) {
      int fileNumber = i + 1;

      int foundIndex = findTrackIndex(fileNumber);

      if (foundIndex >= 0) {
        dynamicTracks[i] = TRACKS[foundIndex];
        dynamicTrackNames[i] = TRACK_NAMES[foundIndex];
      } else {
        String trackPath = String("/") + (fileNumber < 10 ? "0" : "") + String(fileNumber) + ".mp3";
        dynamicTracks[i] = trackPath;

        char buf[16];   
        snprintf(buf, sizeof(buf), "%d", fileNumber);

        dynamicTrackNames[i].id = i;
        dynamicTrackNames[i].name = strdup(buf);
        dynamicTrackNames[i].ignore = false;
      }
    }

    for (int i = 0; i < dfTotalFiles; i++) {
      LOG.print(dynamicTrackNames[i].id);
      LOG.print(": ");
      LOG.print(dynamicTracks[i]);
      LOG.print(" - ");
      LOG.println(dynamicTrackNames[i].name);
    }
}

/**
 * @brief Plays the specified audio track on the DFPlayer module.
 *
 * If the DFPlayer is not connected, the function does nothing.
 *
 * @param trackPath The file path of the audio track to play.
 */
void JaamSound::playDFPlayer(String trackPath) {
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot play track");
        return;
    }
    dfplayer.playSpecFile(trackPath);
    LOG.printf("Track played: %s (%s)\n", trackPath.c_str(), dfplayer.getFileName());
}


/**
 * @brief Sets the DFPlayer Pro module's playback volume.
 *
 * Adjusts the DFPlayer's volume based on a 0-100 input scale, mapping it to the device's maximum volume range. Has no effect if the DFPlayer is not connected.
 *
 * @param volume Desired volume level (0-100).
 */
void JaamSound::setDFPlayerVolume(int volume) {
    if (!dfConnected) {
        LOG.println("DFPlayer not connected, cannot set volume");
        return;
    }
    dfplayer.setVol(map(volume, 0, 100, 0, dfPlayerMaxVolume));
    LOG.printf("Set DFPlayer volume to: %d\n", volume);
}



/**
 * @brief Returns the total number of audio files available on the connected DFPlayer module.
 *
 * @return The number of files if the DFPlayer is connected; otherwise, returns 0.
 */
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

/**
 * @brief Checks if the DFPlayer Pro hardware is enabled based on pin configuration.
 *
 * @return true if both DFPlayer RX and TX pins are set; false otherwise.
 */
bool JaamSound::isDFPlayerEnabled() {
    return dfRxPin > -1 && dfTxPin > -1;
}

/**
 * @brief Checks if the DFPlayer Pro module is currently playing audio.
 *
 * @return true if the DFPlayer is connected and playing audio; false otherwise.
 */
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

/**
 * @brief Checks if the DFPlayer Pro module is currently connected.
 *
 * @return true if the DFPlayer Pro is connected; false otherwise.
 */
bool JaamSound::isDFPlayerConnected() {
#if DFPLAYER_PRO_ENABLED
    return dfConnected;
#else
    return false;
#endif
}

