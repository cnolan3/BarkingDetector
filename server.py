import multiprocessing as mp

from detector import runDetector
from flask import Flask, request
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


if __name__ == "__main__":
    detectorProcess = mp.Process(
        target=runDetector,
        args=("yamnet.tflite", detectorMsgHandler),
        daemon=True,
    )
    detectorProcess.start()

    app.run()

    if detectorProcess.is_alive():
        detectorProcess.terminate()

        while detectorProcess.is_alive():
            continue

        detectorProcess.close()

    print("done")
