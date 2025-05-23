import math
import multiprocessing as mp
import sounddevice as sd

from detector import runDetector
from flask import Flask, request
from utils import checkSettingsFile, readSettings, updateSetting, Settings
from message import (
    MsgAttr,
    Message,
    createMsgHandlers,
    MsgCmd,
    MsgRespType,
    MsgStatus,
    MsgType,
    convertSettingDict,
)

serverMsgHandler, detectorMsgHandler = createMsgHandlers()
detectorProcess = mp.Process

app = Flask(__name__)


@app.route("/detectresult")
def hello_world():
    if detectorProcess.is_alive():
        msg = Message().setMsgType(MsgType.CMD).setCmd(MsgCmd.GET_RESULT)
        resp = serverMsgHandler.send(msg, True, 1)
        print(resp)
        if (
            resp.hasAttr(MsgAttr.MSG_TYPE)
            and resp.checkMsgType(MsgType.RESPONSE)
            and resp.checkRespType(MsgRespType.CLASS_DATA)
        ):
            return resp.getData()
        else:
            return "no data"
    else:
        return "detector not started"


@app.route("/quit")
def quit_detector():
    if detectorProcess.is_alive():
        msg = Message().setMsgType(MsgType.CMD).setCmd(MsgCmd.QUIT)
        resp = serverMsgHandler.send(msg, True, 1)
        print(resp)
        if (
            resp.hasAttr(MsgAttr.MSG_TYPE)
            and resp.checkMsgType(MsgType.RESPONSE)
            and resp.checkRespType(MsgRespType.STATUS)
            and resp.checkStatus(MsgStatus.SUCCESS)
        ):
            return "detector successfully quit"
        else:
            return "detector quit failed"
    else:
        return "detector not started"


@app.route("/detectorsetting", methods=["GET"])
def get_detector_settings():
    if detectorProcess.is_alive():
        msg = Message().setMsgType(MsgType.CMD).setCmd(MsgCmd.GET_SETTINGS)
        resp = serverMsgHandler.send(msg, True, 1)
        print(resp)
        if (
            resp.hasAttr(MsgAttr.MSG_TYPE)
            and resp.checkMsgType(MsgType.RESPONSE)
            and resp.checkRespType(MsgRespType.STATUS)
            and resp.checkStatus(MsgStatus.SUCCESS)
        ):
            return convertSettingDict(resp.getData())
        else:
            return "detector get settings failed"
    else:
        return "detector not started"


@app.route("/detectorsetting", methods=["POST"])
def set_detector_setting():
    data = request.get_json()
    if detectorProcess.is_alive():
        msg = (
            Message()
            .setMsgType(MsgType.CMD)
            .setCmd(MsgCmd.UPDATE_SETTING)
            .setData({data.get("settingName"): data.get("settingVal")})
        )
        resp = serverMsgHandler.send(msg, True, 1)
        print(resp)
        if (
            resp.hasAttr(MsgAttr.MSG_TYPE)
            and resp.checkMsgType(MsgType.RESPONSE)
            and resp.checkRespType(MsgRespType.STATUS)
            and resp.checkStatus(MsgStatus.SUCCESS)
        ):
            return convertSettingDict(resp.getData())
        else:
            return "detector setting failed"
    else:
        return "detector not started"


def chooseDevice():
    settings = readSettings()
    if settings[Settings.REC_DEVICE_ID.value] != -1:
        return

    deviceList = sd.query_devices()
    print("### Select a recording device to use as a microphone ###")
    print(deviceList)
    devId = int(input("device id: "))
    settings[Settings.REC_DEVICE_ID.value] = devId
    updateSetting(Settings.REC_DEVICE_ID, devId)

    sampleRate = math.trunc(deviceList[devId]["default_samplerate"])

    useSR = input(f"Use selected devices default samplerate? ({sampleRate}hz) (Y/N): ")

    print(useSR)
    if useSR.upper() == "Y":
        print("AAA")
        settings[Settings.SAMPLE_RATE.value] = sampleRate
        updateSetting(Settings.SAMPLE_RATE, sampleRate)


if __name__ == "__main__":
    checkSettingsFile()
    chooseDevice()

    detectorProcess = mp.Process(
        target=runDetector,
        args=("yamnet.tflite", detectorMsgHandler),
        daemon=True,
    )
    detectorProcess.start()

    app.run(host="0.0.0.0")

    if detectorProcess.is_alive():
        detectorProcess.terminate()

        while detectorProcess.is_alive():
            continue

        detectorProcess.close()

    print("done")
