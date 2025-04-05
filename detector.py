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

from mediapipe.tasks import python
from mediapipe.tasks.python.audio.core import audio_record
from mediapipe.tasks.python.components import containers
from mediapipe.tasks.python import audio
from utils import getScoreByNames, msgHandler, msgBuilder


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

    def __init__(self, model: str, msgHandler: msgHandler):
        self.msgHandler = msgHandler

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

    def save_result(self, result: audio.AudioClassifierResult, timestamp_ms: int):
        result.timestamp_ms = timestamp_ms
        self.classification_result_list.append(result)

    def run(self):
        pause_time = self.interval_between_inference * 0.1
        last_inference_time = time.time()

        # Start audio recording in the background.
        self.record.start_recording()

        # Loop until the user close the classification results plot.
        while True:
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

            # filter the classification result
            if self.classification_result_list:
                self.filtered_list = getScoreByNames(self.classification_result_list[0])
                self.classification_result_list.clear()

            cmdMsg = self.msgHandler.recv(False)

            if "msg_type" in cmdMsg and cmdMsg["msg_type"] == "cmd":
                if cmdMsg["cmd"] == "get_result":
                    if self.filtered_list:
                        resp = (
                            msgBuilder()
                            .setMsgType("response")
                            .setRespType("classification_data")
                            .setData(self.filtered_list.copy())
                            .build()
                        )
                        self.msgHandler.send(resp)
                    else:
                        resp = (
                            msgBuilder()
                            .setMsgType("response")
                            .setRespType("status")
                            .setStatus("error")
                            .build()
                        )
                        self.msgHandler.send(resp)
                elif cmdMsg["cmd"] == "end":
                    resp = (
                        msgBuilder()
                        .setMsgType("response")
                        .setRespType("message")
                        .setData("ended")
                        .build()
                    )
                    self.msgHandler.send(resp)
                    break

            # put the classification data into the pipe
            if self.filtered_list:
                # print(classification_result_list)
                self.sharedData = self.filtered_list
                self.filtered_list.clear()

        print("detector ended")
