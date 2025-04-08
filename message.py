from enum import Enum
import multiprocessing as mp


class MsgAttr(Enum):
    MSG_TYPE = "message_type"
    RESP_TYPE = "response_type"
    DATA = "data"
    STATUS = "status"
    CMD = "command"


class MsgType(Enum):
    RESPONSE = "response"
    CMD = "cmd"


class MsgRespType(Enum):
    CLASS_DATA = "classification_data"
    STATUS = "status"
    MSG = "message"


class MsgCmd(Enum):
    GET_RESULT = "get_result"
    QUIT = "end"


class MsgStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"


class Message(object):
    msg: {}

    def __init__(self):
        self.msg = {}

    def hasAttr(self, msgAttr: MsgAttr):
        return msgAttr.value in self.msg

    def setMsgType(self, msgType: MsgType):
        self.msg[MsgAttr.MSG_TYPE.value] = msgType.value
        return self

    def checkMsgType(self, msgType: MsgType):
        if self.hasAttr(MsgAttr.MSG_TYPE):
            return self.msg[MsgAttr.MSG_TYPE.value] == msgType.value

        return False

    def getMsgType(self):
        if self.hasAttr(MsgAttr.MSG_TYPE):
            return self.msg[MsgAttr.MSG_TYPE.value]

        return ""

    def setRespType(self, respType: MsgRespType):
        self.msg[MsgAttr.RESP_TYPE.value] = respType.value
        return self

    def checkRespType(self, respType: MsgRespType):
        if self.hasAttr(MsgAttr.RESP_TYPE):
            return self.msg[MsgAttr.RESP_TYPE.value] == respType.value

        return False

    def getRespType(self):
        if self.hasAttr(MsgAttr.RESP_TYPE):
            return self.msg[MsgAttr.RESP_TYPE.value]

        return ""

    def setData(self, data: str | dict):
        self.msg[MsgAttr.DATA.value] = data
        return self

    def getData(self):
        if self.hasAttr(MsgAttr.DATA):
            return self.msg[MsgAttr.DATA.value]

        return False

    def setStatus(self, status: MsgStatus):
        self.msg[MsgAttr.STATUS.value] = status.value
        return self

    def checkStatus(self, status: MsgStatus):
        if self.hasAttr(MsgAttr.STATUS):
            return self.msg[MsgAttr.STATUS.value] == status.value

        return False

    def getStatus(self):
        if self.hasAttr(MsgAttr.STATUS):
            return self.msg[MsgAttr.STATUS.value]

        return ""

    def setCmd(self, cmd: MsgCmd):
        self.msg[MsgAttr.CMD.value] = cmd.value
        return self

    def checkCmd(self, cmd: MsgCmd):
        if self.hasAttr(MsgAttr.CMD):
            return self.msg[MsgAttr.CMD.value] == cmd.value

        return False

    def getCmd(self):
        if self.hasAttr(MsgAttr.CMD):
            return self.msg[MsgAttr.CMD.value]

        return ""

    def buildDict(self):
        if MsgAttr.STATUS.value not in self.msg:
            self.msg[MsgAttr.STATUS.value] = MsgStatus.SUCCESS.value

        return self.msg


def createMsgHandlers():
    pipeARecv, pipeASend = mp.Pipe()
    pipeBRecv, pipeBSend = mp.Pipe()

    handlerA = MsgHandler(pipeASend, pipeBRecv)
    handlerB = MsgHandler(pipeBSend, pipeARecv)

    return handlerA, handlerB


class MsgHandler:
    sendPipe: mp.Pipe
    recvPipe: mp.Pipe

    def __init__(self, sendPipe: mp.Pipe, recvPipe: mp.Pipe):
        self.sendPipe = sendPipe
        self.recvPipe = recvPipe

    def send(self, msg: Message, wait: bool = True, timeout: int = 0) -> Message:
        self.sendPipe.send(msg)

        if wait and timeout != 0:
            return self.recvPipe.recv()
        elif wait:
            if self.recvPipe.poll(timeout):
                return self.recvPipe.recv()

        return Message()

    def recv(self, wait: bool = True, timeout: int = 0) -> Message:
        if wait:
            return self.recvPipe.recv()

        if self.recvPipe.poll(timeout):
            return self.recvPipe.recv()

        return Message()

    def checkForMsg(self):
        return self.recvPipe.poll()
