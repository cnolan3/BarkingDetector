"""A module with util functions."""

from enum import Enum
from pathlib import Path
import os
import datetime
import yaml


maxTimestamp = datetime.datetime(3000, 1, 1).timestamp()


def getTodaysFirstTimestamp():
    now = datetime.datetime.now()
    today = datetime.datetime(now.year, now.month, now.day)
    return today.timestamp()


class Settings(Enum):
    BARK_THRESHOLD = "bark_threshold"
    REC_TIMEOUT = "recording_timeout"
    PRE_BUFFER_TIME = "pre_record_buffer_time"
    REC_BUFFER_SIZE = "recorder_buffer_size"
    SAMPLE_RATE = "sample_rate"
    NUM_CHANNELS = "num_channels"
    WRITE_BUFFER_LENGTH = "write_buffer_length"
    RECORDING_FILE_PATH = "recording_file_path"


settingsPath = os.path.join(os.getcwd(), "settings.yaml")
defaultSettings = {
    Settings.BARK_THRESHOLD.value: 0.15,  # number between 0 and 1, threshold confidence of a bark to trigger a recording
    Settings.REC_TIMEOUT.value: 30,  # stop recorder after X seconds of not hearing a bark
    Settings.PRE_BUFFER_TIME.value: 3,  # amount of time to keep in memory before a bark is detected
    Settings.REC_BUFFER_SIZE.value: 15600,  # size of internal audio recording buffer (shouldn't need to edit this)
    Settings.SAMPLE_RATE.value: 160000,  # sample rate of audio (shouldn't need to edit this)
    Settings.NUM_CHANNELS.value: 1,  # number of audio channels to use (shouldn't need to edit this)
    Settings.WRITE_BUFFER_LENGTH.value: 3,  # number of seconds (in samples) between file flush() calls (shouldn't need to edit this)
    Settings.RECORDING_FILE_PATH.value: "",  # path to save recordings to
}


def checkSettingsFile():
    settingsFile = Path(settingsPath)
    if not settingsFile.is_file():
        with settingsFile.open("w") as f:
            f.write(yaml.dump(defaultSettings))


def readSettings():
    data = {}
    settingsFile = Path(settingsPath)
    if settingsFile.is_file():
        with settingsFile.open("r") as f:
            data = yaml.safe_load(f)

    return data


def updateSetting(id: Settings, val):
    settingsFile = Path(settingsPath)
    if settingsFile.is_file():
        data = {}
        with settingsFile.open("r") as f:
            data = yaml.safe_load(f)

        if id.value in data:
            data[id.value] = val

            with settingsFile.open("w") as f:
                f.write(yaml.dump(data))


scoreNames = ["Dog", "Bark", "Bow-wow", "Whimper (dog)"]


def getScoreByNames(result):
    classification = result.classifications[0]
    categories = classification.categories
    scores = dict.fromkeys(scoreNames, 0)

    for cat in categories:
        if cat.category_name in scoreNames:
            scores[cat.category_name] = cat.score

    return scores


def scoreDictToList(scoreDict):
    res = []

    for idx, name in enumerate(scoreNames):
        res[idx] = scoreDict[name]

    return res


def scoreListToDict(scoreList):
    res = {}

    for idx, name in enumerate(scoreNames):
        res[name] = scoreList[idx]

    return res
