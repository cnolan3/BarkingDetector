import multiprocessing as mp

from detector import runDetector
from flask import Flask
from utils import scoreListToDict, msgHandler, createMsgHandlers

serverMsgHander, detectorMsgHander = createMsgHandlers()
detectorProcess = mp.Process

app = Flask(__name__)


@app.route("/")
def hello_world():
    if detectorProcess.is_alive():
        if shared:
            return scoreListToDict(shared)
        else:
            return "no data"
    else:
        return "detector not started"


if __name__ == "__main__":
    toDetector = mp.Queue()
    fromDetector = mp.Queue()

    detectorProcess = mp.Process(
        target=runDetector,
        args=(
            "yamnet.tflite",
            toDetector,
            fromDetector,
            shared,
        ),
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
