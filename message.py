import multiprocessing as mp


def createMsgHandlers():
    pipeARecv, pipeASend = mp.Pipe()
    pipeBRecv, pipeBSend = mp.Pipe()

    handlerA = msgHandler(pipeASend, pipeBRecv)
    handlerB = msgHandler(pipeBSend, pipeARecv)

    return handlerA, handlerB


class msgHandler:
    sendPipe: mp.Pipe
    recvPipe: mp.Pipe

    def __init__(self, sendPipe: mp.Pipe, recvPipe: mp.Pipe):
        self.sendPipe = sendPipe
        self.recvPipe = recvPipe

    def send(self, msg: dict, wait: bool = True, timeout: int = 0):
        self.sendPipe.send(msg)

        if wait and timeout != 0:
            return self.recvPipe.recv()
        elif wait:
            if self.recvPipe.poll(timeout):
                return self.recvPipe.recv()

        return {}

    def recv(self, wait: bool = True, timeout: int = 0):
        if wait:
            return self.recvPipe.recv()

        if self.recvPipe.poll(timeout):
            return self.recvPipe.recv()

        return {}

    def checkForMsg(self):
        return self.recvPipe.poll()


class msgBuilder(object):
    msg: {}

    def __init__(self):
        self.msg = {}

    def setMsgType(self, msgType: str):
        self.msg["msg_type"] = msgType
        return self

    def setRespType(self, respType: str):
        self.msg["resp_type"] = respType
        return self

    def setData(self, data: str | dict):
        self.msg["data"] = data
        return self

    def setStatus(self, status: str):
        self.msg["status"] = status
        return self

    def setCmd(self, cmd: str):
        self.msg["cmd"] = cmd
        return self

    def build(self):
        if "status" not in self.msg:
            self.msg["status"] = "success"

        return self.msg
