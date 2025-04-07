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
"""Main scripts to run audio classification."""

import time
import queue
import wave
import os
import threading

from mediapipe.tasks import python
from mediapipe.tasks.python.audio.core import audio_record
from mediapipe.tasks.python.components import containers
from mediapipe.tasks.python import audio
from utils import getScoreByNames
from message import (
    msgAttr,
    msgCmd,
    msgHandler,
    message,
    msgRespType,
    msgStatus,
    msgType,
)


def runDetector(model: str, msgHandler: msgHandler) -> None:
    detector = Detector(model, msgHandler)
    detector.run()


class Detector:
    msgHandler: msgHandler
    classification_result_list = []
    filtered_list = {}
    classifier: audio.AudioClassifier
    interval_between_inferance: float
    audio_format: containers.AudioDataFormat
    record: audio_record.AudioRecord
    audio_data: containers.AudioData
    buffer_size, sample_rate, num_channels = 15600, 16000, 1
    listening_q_time = 3  # listening buffer length in seconds
    listening_q_size: int
    runLoop: bool
    is_recording: bool
    recording_q: queue.Queue
    recording_timeout = 40
    record_threshold = 0.15

    def __init__(self, model: str, msgHandler: msgHandler):
        self.msgHandler = msgHandler
        self.recording_q = queue.Queue()
        self.is_recording = False

        # Initialize the audio classification model.
        base_options = python.BaseOptions(model_asset_path=model)
        options = audio.AudioClassifierOptions(
            base_options=base_options,
            running_mode=audio.RunningMode.AUDIO_STREAM,
            max_results=4,
            score_threshold=0.0,
            result_callback=self.save_result,
        )
        self.classifier = audio.AudioClassifier.create_from_options(options)

        # Initialize the audio recorder and a tensor to store the audio input.
        # The sample rate may need to be changed to match your input device.
        # For example, an AT2020 requires sample_rate 44100.
        self.audio_format = containers.AudioDataFormat(
            self.num_channels, self.sample_rate
        )
        self.record = audio_record.AudioRecord(
            self.num_channels, self.sample_rate, self.buffer_size
        )
        self.audio_data = containers.AudioData(self.buffer_size, self.audio_format)

        # We'll try to run inference every interval_between_inference seconds.
        # This is usually half of the model's input length to create an overlapping
        # between incoming audio segments to improve classification accuracy.
        input_length_in_second = (
            float(len(self.audio_data.buffer))
            / self.audio_data.audio_format.sample_rate
        )
        self.interval_between_inference = input_length_in_second * (0.5)

        self.listening_q_size = self.sample_rate * self.listening_q_time

    def save_result(self, result: audio.AudioClassifierResult, timestamp_ms: int):
        result.timestamp_ms = timestamp_ms
        self.classification_result_list.append(result)

    def run(self):
        pause_time = self.interval_between_inference * 0.1
        last_inference_time = time.time()
        last_heard_time = 0.0

        # Start audio recording in the background.
        self.record.start_recording()

        # Loop until the user close the classification results plot.
        self.runLoop = True
        while self.runLoop:
            # Wait until at least interval_between_inference seconds has passed since
            # the last inference.
            now = time.time()
            diff = now - last_inference_time
            if diff < self.interval_between_inference:
                time.sleep(pause_time)
                continue
            last_inference_time = now

            # Load the input audio from the AudioRecord instance and run classify.
            data = self.record.read(self.buffer_size)
            # audio_data.load_from_array(data.astype(np.float32))
            self.audio_data.load_from_array(data)
            self.classifier.classify_async(
                self.audio_data, round(last_inference_time * 1000)
            )

            if not self.is_recording:
                # remove old samples from the q to make room for new ones while listening
                while not self.recording_q.empty() and (
                    self.recording_q.qsize() + data.size > self.listening_q_size
                ):
                    self.recording_q.get()

            for sample in data:
                self.recording_q.put(sample)

            fileWriteThread = threading.Thread(
                target=self.saveRecording, args=(), daemon=True
            )

            # filter the classification result
            if self.classification_result_list:
                self.filtered_list = getScoreByNames(self.classification_result_list[0])
                self.classification_result_list.clear()

                if self.filtered_list["Dog"] >= self.record_threshold:
                    print("dog detected")
                    last_heard_time = time.time()

                    if not self.is_recording:
                        print("start recording")
                        self.is_recording = True
                        fileWriteThread.start()

            # check if we have heard a bark within the timeout
            if self.is_recording and (
                time.time() - last_heard_time > self.recording_timeout
            ):
                print("barking stopped")
                self.is_recording = False
                self.recording_q.put(
                    None
                )  # trigger the final blocking "get" in the file writing thread
                # fileWriteThread.join()

            if self.is_recording:
                print("time since last bark: ", time.time() - last_heard_time)

            self.handleCmd()

            # put the classification data into the pipe
            if self.filtered_list:
                # print(self.filtered_list)
                self.filtered_list.clear()

        print("detector ended")

    def saveRecording(self):
        print("recording thread")
        filename = os.path.join(os.getcwd(), "{}.wav".format("test_record"))
        maxChunkSize = self.sample_rate * 1  # 1 second of recording
        wf = wave.open(filename, "wb")
        wf.setnchannels(self.num_channels)
        wf.setsampwidth(2)
        wf.setframerate(self.sample_rate)
        chunk = []
        while self.is_recording:
            sample = self.recording_q.get()

            if sample:
                chunk.append(sample)

            if len(chunk) >= maxChunkSize or (len(chunk) > 0 and not sample):
                wf.writeframes(b"".join(chunk))
                chunk.clear()

        wf.close()

    def handleCmd(self):
        cmdMsg = self.msgHandler.recv(False)

        if cmdMsg.hasAttr(msgAttr.MSG_TYPE) and cmdMsg.checkMsgType(msgType.CMD):
            if cmdMsg.checkCmd(msgCmd.GET_RESULT):
                if self.filtered_list:
                    resp = (
                        message()
                        .setMsgType(msgType.RESPONSE)
                        .setRespType(msgRespType.CLASS_DATA)
                        .setData(self.filtered_list.copy())
                    )
                    self.msgHandler.send(resp)
                else:
                    resp = (
                        message()
                        .setMsgType(msgType.RESPONSE)
                        .setRespType(msgRespType.STATUS)
                        .setStatus(msgStatus.ERROR)
                    )
                    self.msgHandler.send(resp)
            elif cmdMsg.checkCmd(msgCmd.QUIT):
                self.runLoop = False
                resp = (
                    message()
                    .setMsgType(msgType.RESPONSE)
                    .setRespType(msgRespType.STATUS)
                    .setStatus(msgStatus.SUCCESS)
                )
                self.msgHandler.send(resp)
