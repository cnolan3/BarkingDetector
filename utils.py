# Copyright 2023 The MediaPipe Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A module with util functions."""

import multiprocessing as mp

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

    def send(self, msg: dict, wait: bool = True):
        self.sendPipe.send(msg)

        if wait:
            return self.recvPipe.recv()

        return {}

    def recv(self, wait: bool = True):
        if wait:
            return self.recvPipe.recv()

        if self.recvPipe.poll():
            return self.recvPipe.recv()

        return {}

    def checkForMsg(self):
        return self.recvPipe.poll()
