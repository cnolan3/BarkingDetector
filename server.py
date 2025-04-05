import multiprocessing as mp

from detector import runDetector
from flask import Flask
from message import msgBuilder, createMsgHandlers

serverMsgHandler, detectorMsgHandler = createMsgHandlers()
detectorProcess = mp.Process

app = Flask(__name__)


@app.route("/")
def hello_world():
    if detectorProcess.is_alive():
        msg = msgBuilder().setMsgType("cmd").setCmd("get_result").build()
        resp = serverMsgHandler.send(msg, True, 1)
        print(resp)
        if (
            "msg_type" in resp
            and resp["msg_type"] == "response"
            and resp["resp_type"] == "classification_data"
        ):
            return resp["data"]
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
