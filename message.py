from enum import Enum
import multiprocessing as mp


class msgAttr(Enum):
    MSG_TYPE = "message_type"
    RESP_TYPE = "response_type"
    DATA = "data"
    STATUS = "status"
    CMD = "command"


class msgType(Enum):
    RESPONSE = "response"
    CMD = "cmd"


class msgRespType(Enum):
    CLASS_DATA = "classification_data"
    STATUS = "status"
    MSG = "message"


class msgCmd(Enum):
    GET_RESULT = "get_result"
    QUIT = "end"


class msgStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"


class message(object):
    msg: {}

    def __init__(self):
        self.msg = {}

    def hasAttr(self, msgAttr: msgAttr):
        return msgAttr.value in self.msg

    def setMsgType(self, msgType: msgType):
        self.msg[msgAttr.MSG_TYPE.value] = msgType.value
        return self

    def checkMsgType(self, msgType: msgType):
        return self.msg[msgAttr.MSG_TYPE.value] == msgType.value

    def getMsgType(self):
        return self.msg[msgAttr.MSG_TYPE.value]

    def setRespType(self, respType: msgRespType):
        self.msg[msgAttr.RESP_TYPE.value] = respType.value
        return self

    def checkRespType(self, respType: msgRespType):
        return self.msg[msgAttr.RESP_TYPE.value] == respType.value

    def getRespType(self):
        return self.msg[msgAttr.RESP_TYPE.value]

    def setData(self, data: str | dict):
        self.msg[msgAttr.DATA.value] = data
        return self

    def getData(self):
        return self.msg[msgAttr.DATA.value]

    def setStatus(self, status: msgStatus):
        self.msg[msgAttr.STATUS.value] = status.value
        return self

    def checkStatus(self, status: msgStatus):
        return self.msg[msgAttr.STATUS.value] == status.value

    def getStatus(self):
        return self.msg[msgAttr.STATUS.value]

    def setCmd(self, cmd: msgCmd):
        self.msg[msgAttr.CMD.value] = cmd.value
        return self

    def checkCmd(self, cmd: msgCmd):
        return self.msg[msgAttr.CMD.value] == cmd.value

    def getCmd(self):
        return self.msg[msgAttr.CMD.value]

    def buildDict(self):
        if msgAttr.STATUS.value not in self.msg:
            self.msg[msgAttr.STATUS.value] = msgStatus.SUCCESS.value

        return self.msg


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

    def send(self, msg: message, wait: bool = True, timeout: int = 0) -> message:
        self.sendPipe.send(msg)

        if wait and timeout != 0:
            return self.recvPipe.recv()
        elif wait:
            if self.recvPipe.poll(timeout):
                return self.recvPipe.recv()

        return message()

    def recv(self, wait: bool = True, timeout: int = 0) -> message:
        if wait:
            return self.recvPipe.recv()

        if self.recvPipe.poll(timeout):
            return self.recvPipe.recv()

        return message()

    def checkForMsg(self):
        return self.recvPipe.poll()
