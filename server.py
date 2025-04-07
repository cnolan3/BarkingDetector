import multiprocessing as mp

from detector import runDetector
from flask import Flask
from message import (
    msgAttr,
    message,
    createMsgHandlers,
    msgCmd,
    msgRespType,
    msgType,
)

serverMsgHandler, detectorMsgHandler = createMsgHandlers()
detectorProcess = mp.Process

app = Flask(__name__)


@app.route("/")
def hello_world():
    if detectorProcess.is_alive():
        msg = message().setMsgType(msgType.CMD).setCmd(msgCmd.GET_RESULT)
        resp = serverMsgHandler.send(msg, True, 1)
        print(resp)
        if (
            resp.hasAttr(msgAttr.MSG_TYPE)
            and resp.checkMsgType(msgType.RESPONSE)
            and resp.checkRespType(msgRespType.CLASS_DATA)
        ):
            return resp.getData()
        else:
            return "no data"
    else:
        return "detector not started"


if __name__ == "__main__":
    toDetector = mp.Queue()
    fromDetector = mp.Queue()

    detectorProcess = mp.Process(
        target=runDetector,
        args=("yamnet.tflite", detectorMsgHandler),
        daemon=True,
    )
    detectorProcess.start()

    app.run()

    toDetector.close()
    fromDetector.close()
    # dataPipeRecv.close()
    # dataPipeSend.close()

    if detectorProcess.is_alive():
        detectorProcess.terminate()

        while detectorProcess.is_alive():
            continue

        detectorProcess.close()

    print("done")
