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

import wavfile

# import wave
import os
import threading

from numpy import float32
import numpy as np
import audio_record

from mediapipe.tasks import python
from mediapipe.tasks.python.components import containers
from mediapipe.tasks.python import audio
from utils import getScoreByNames, scoreNames
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
    buffer_size, sample_rate, num_channels, sample_width = 15600, 16000, 1, 4
    listening_q_time = 3  # listening buffer length in seconds
    listening_q_size: int
    runLoop: bool
    is_recording: bool
    recording_q: queue.Queue
    recording_timeout = 10
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

        self.runLoop = True

    def save_result(self, result: audio.AudioClassifierResult, timestamp_ms: int):
        result.timestamp_ms = timestamp_ms
        self.classification_result_list.append(result)

    def run(self):
        filteredListLock = threading.Lock()
        recordingQLock = threading.Lock()
        recordingBarrier = threading.Barrier(2)

        # Start audio recording in the background.
        self.record.start_recording()

        detectListenThread = threading.Thread(target=self.detectorListen, args=(filteredListLock, recordingQLock, recordingBarrier, ))
        detectListenThread.start()

        recordListenThread = threading.Thread(
            target=self.recordingListen, args=(recordingQLock, recordingBarrier, ), daemon=True
        )
        recordListenThread.start()

        while self.runLoop:
            cmdMsg = self.msgHandler.recv()

            if cmdMsg.hasAttr(msgAttr.MSG_TYPE) and cmdMsg.checkMsgType(msgType.CMD):
                if cmdMsg.checkCmd(msgCmd.GET_RESULT):
                    filteredListLock.acquire()
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
                    filteredListLock.release()
                elif cmdMsg.checkCmd(msgCmd.QUIT):
                    self.runLoop = False
                    resp = (
                        message()
                        .setMsgType(msgType.RESPONSE)
                        .setRespType(msgRespType.STATUS)
                        .setStatus(msgStatus.SUCCESS)
                    )
                    self.msgHandler.send(resp)

        detectListenThread.join()
        recordListenThread.join()
        print("detector ended")

    def detectorListen(self, filteredListLock: threading.Lock, recordingQLock: threading.Lock, recordingBarrier: threading.Barrier):
        pause_time = self.interval_between_inference * 0.1
        last_inference_time = time.time()
        last_heard_time = 0.0
        fileWriteThread: threading.Thread
        barking_started_at: time.time
        barking_stopped_at: time.time

        # wait for recording thread to flush the recorder
        recordingBarrier.wait()
        recordingBarrier.wait()

        # Loop until the user close the classification results plot.
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
            data = self.record.read_rolled_buffer(self.buffer_size)
            self.audio_data.load_from_array(data.astype(float32))
            # self.audio_data.load_from_array(data)
            self.classifier.classify_async(
                self.audio_data, round(last_inference_time * 1000)
            )

            # filter the classification result
            if self.classification_result_list:
                filteredListLock.acquire()
                self.filtered_list.clear()
                self.filtered_list = getScoreByNames(self.classification_result_list[0])
                filteredListLock.release()
                self.classification_result_list.clear()

                if self.filtered_list[scoreNames[0]] >= self.record_threshold:
                    print("dog detected")
                    last_heard_time = time.time()

                    if not self.is_recording:
                        # print("start recording")
                        self.is_recording = True
                        barking_started_at = last_heard_time

                        fileWriteThread = threading.Thread(
                            target=self.saveRecording,
                            args=(recordingQLock,),
                            daemon=True,
                        )
                        fileWriteThread.start()

            # check if we have heard a bark within the timeout
            if self.is_recording and (
                time.time() - last_heard_time > self.recording_timeout
            ):
                print("barking stopped")
                self.is_recording = False
                barking_stopped_at = time.time()
                print(
                    "barking lasted for {} seconds".format(
                        barking_stopped_at - barking_started_at
                    )
                )
                fileWriteThread.join()

            if self.is_recording:
                print("time since last bark: ", time.time() - last_heard_time)

    def recordingListen(self, recordingQLock: threading.Lock, recordingBarrier: threading.Barrier):
        recordingBarrier.wait()

        self.record.flush_queue()

        recordingBarrier.wait()

        while self.runLoop:
            tmpData = self.record.read_queue()

            for sample in tmpData:
                self.recording_q.put(sample.reshape(1, self.num_channels))

            if not self.is_recording:
                recordingQLock.acquire()
                while self.recording_q.qsize() > self.listening_q_size:
                    self.recording_q.get()
                recordingQLock.release()

    def saveRecording(self, recordingQLock: threading.Lock):
        # print("recording thread")
        filename = os.path.join(os.getcwd(), "{}.wav".format("test_record"))
        # maxChunkSize = self.sample_rate * 1  # 1 second of recording
        # chunk = np.zeros([0, self.num_channels], dtype=np.float32)
        wf = wavfile.open(
            filename,
            "wb",
            sample_rate=self.sample_rate,
            num_channels=self.num_channels,
            bits_per_sample=(self.sample_width * 8),
            fmt=wavfile.chunk.WavFormat.PCM,
        )
        while self.is_recording:
            recordingQLock.acquire()
            sample = self.recording_q.get()
            recordingQLock.release()

            # print(type(sample), sample.shape, sample.dtype)

            if sample is not None:
                wf.write_float(sample)
                # chunk = np.concatenate(chunk, sample)

            # if np.size(chunk, 0) >= maxChunkSize or (
            #     np.size(chunk, 0) > 0 and not sample
            # ):
            #     wf.write_float(chunk)
            #     chunk = np.zeros([0, self.num_channels], dtype=np.float32)

        wf.close()
