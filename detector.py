"""Main scripts to run audio classification."""

import datetime
import time
import queue

import os
import threading
import sqlite3
import db

from numpy import float32
import audio_record
import sounddevice as sd

from pathlib import Path
from soundfile import SoundFile
from mediapipe.tasks import python
from mediapipe.tasks.python.components import containers
from mediapipe.tasks.python import audio
from utils import (
    getScoreByNames,
    scoreNames,
    checkSettingsFile,
    readSettings,
    Settings,
    maxTimestamp,
    updateSetting,
)
from message import (
    MsgAttr,
    MsgCmd,
    MsgHandler,
    Message,
    MsgRespType,
    MsgStatus,
    MsgType,
)


def runDetector(model: str, msgHandler: MsgHandler) -> None:
    checkSettingsFile()
    detector = Detector(model, msgHandler)
    detector.run()


class Detector:
    msgHandler: MsgHandler
    classification_result_list = []
    filtered_list = {}
    classifier: audio.AudioClassifier
    interval_between_inferance: float
    audio_format: containers.AudioDataFormat
    record: audio_record.AudioRecord
    audio_data: containers.AudioData
    listening_q_size: int
    runLoop: bool
    is_recording: bool
    recording_q: queue.Queue
    barking_stopped_at_q: queue.Queue
    is_writing: bool
    bufferSum: int
    settings: {}

    def __init__(self, model: str, msgHandler: MsgHandler):
        self.settings = {}
        self.loadSettings()
        self.msgHandler = msgHandler
        self.recording_q = queue.Queue()
        self.barking_stopped_at_q = queue.Queue()
        self.is_recording = False
        self.is_writing = False
        self.bufferSum = 0

        # create tables in db if not already
        db_conn = sqlite3.connect(db.dbname)
        db.createTables(db_conn)
        db_conn.close()

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
            self.settings[Settings.NUM_CHANNELS], self.settings[Settings.SAMPLE_RATE]
        )
        self.record = audio_record.AudioRecord(
            self.settings[Settings.NUM_CHANNELS],
            self.settings[Settings.SAMPLE_RATE],
            self.settings[Settings.REC_BUFFER_SIZE],
            self.settings[Settings.REC_DEVICE_ID],
        )

        self.audio_data = containers.AudioData(
            self.settings[Settings.REC_BUFFER_SIZE], self.audio_format
        )

        # We'll try to run inference every interval_between_inference seconds.
        # This is usually half of the model's input length to create an overlapping
        # between incoming audio segments to improve classification accuracy.
        input_length_in_second = (
            float(len(self.audio_data.buffer))
            / self.audio_data.audio_format.sample_rate
        )
        self.interval_between_inference = input_length_in_second * (0.5)

        self.listening_q_size = (
            self.settings[Settings.SAMPLE_RATE]
            * self.settings[Settings.PRE_BUFFER_TIME]
        )

        self.runLoop = True

    def save_result(self, result: audio.AudioClassifierResult, timestamp_ms: int):
        result.timestamp_ms = timestamp_ms
        self.classification_result_list.append(result)

    def loadSettings(self):
        loadedSettings = readSettings()

        if loadedSettings:
            for attr in Settings:
                # if attr.value not in loadedSettings:
                #     return  # settings file not valid

                self.settings[attr] = loadedSettings[attr.value]

        if (
            self.settings[Settings.RECORDING_FILE_PATH] != ""
            and not Path(self.settings[Settings.RECORDING_FILE_PATH]).is_dir()
        ):
            # TODO raise an exception or something
            print(
                "{} is not a valid path, resorting to default".format(
                    self.settings[Settings.RECORDING_FILE_PATH]
                )
            )
            self.settings[Settings.RECORDING_FILE_PATH] = ""

        if self.settings[Settings.RECORDING_FILE_PATH] == "":
            self.settings[Settings.RECORDING_FILE_PATH] = os.path.join(
                os.getcwd(), "recordings/"
            )
            Path(self.settings[Settings.RECORDING_FILE_PATH]).mkdir(
                parents=True, exist_ok=True
            )

    def run(self):
        filteredListLock = threading.Lock()
        recordingQLock = threading.Lock()
        recordingBarrier = threading.Barrier(2)

        # Start audio recording in the background.
        self.record.start_recording()

        detectListenThread = threading.Thread(
            target=self.detectorListen,
            args=(
                filteredListLock,
                recordingQLock,
                recordingBarrier,
            ),
            daemon=True,
        )
        detectListenThread.start()

        recordListenThread = threading.Thread(
            target=self.recordingListen,
            args=(
                recordingQLock,
                recordingBarrier,
            ),
            daemon=True,
        )
        recordListenThread.start()

        while self.runLoop:
            cmdMsg = self.msgHandler.recv()

            if cmdMsg.hasAttr(MsgAttr.MSG_TYPE) and cmdMsg.checkMsgType(MsgType.CMD):
                if cmdMsg.checkCmd(MsgCmd.GET_RESULT):
                    filteredListLock.acquire()
                    if self.filtered_list:
                        resp = (
                            Message()
                            .setMsgType(MsgType.RESPONSE)
                            .setRespType(MsgRespType.CLASS_DATA)
                            .setData(self.filtered_list.copy())
                        )
                        self.msgHandler.send(resp)
                    else:
                        resp = (
                            Message()
                            .setMsgType(MsgType.RESPONSE)
                            .setRespType(MsgRespType.STATUS)
                            .setStatus(MsgStatus.ERROR)
                        )
                        self.msgHandler.send(resp)
                    filteredListLock.release()
                elif cmdMsg.checkCmd(MsgCmd.UPDATE_SETTING):
                    data = cmdMsg.getData()
                    if data is str:
                        resp = (
                            Message()
                            .setMsgType(MsgType.RESPONSE)
                            .setRespType(MsgRespType.STATUS)
                            .setStatus(MsgStatus.ERROR)
                            .setData("Setting request format invalid")
                        )
                        self.msgHandler.send(resp)
                        continue
                    for key, value in data.items():
                        for setting in Settings:
                            if key == setting.value:
                                self.settings[setting] = value
                                updateSetting(setting, value)
                    resp = (
                        Message()
                        .setMsgType(MsgType.RESPONSE)
                        .setRespType(MsgRespType.STATUS)
                        .setStatus(MsgStatus.SUCCESS)
                        .setData(self.settings)
                    )
                    self.msgHandler.send(resp)
                elif cmdMsg.checkCmd(MsgCmd.GET_SETTINGS):
                    resp = (
                        Message()
                        .setMsgType(MsgType.RESPONSE)
                        .setRespType(MsgRespType.STATUS)
                        .setStatus(MsgStatus.SUCCESS)
                        .setData(self.settings)
                    )
                    self.msgHandler.send(resp)
                elif cmdMsg.checkCmd(MsgCmd.QUIT):
                    self.runLoop = False
                    resp = (
                        Message()
                        .setMsgType(MsgType.RESPONSE)
                        .setRespType(MsgRespType.STATUS)
                        .setStatus(MsgStatus.SUCCESS)
                    )
                    self.msgHandler.send(resp)

        detectListenThread.join()
        recordListenThread.join()
        print("detector ended")

    def detectorListen(
        self,
        filteredListLock: threading.Lock,
        recordingQLock: threading.Lock,
        recordingBarrier: threading.Barrier,
    ):
        pause_time = self.interval_between_inference * 0.1
        last_inference_time = time.time()
        last_heard_time = 0.0
        fileWriteThread: threading.Thread
        barking_started_at: int
        barking_stopped_at: int

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
            (data, timestamp) = self.record.read_rolled_buffer(
                self.settings[Settings.REC_BUFFER_SIZE]
            )
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

                if (
                    self.filtered_list[scoreNames[0]]
                    >= self.settings[Settings.BARK_THRESHOLD]
                ):
                    print("dog detected")
                    insertBarkThread = threading.Thread(
                        target=self.dbInsertBark, args=(timestamp,), daemon=True
                    )
                    insertBarkThread.start()
                    last_heard_time = timestamp.timestamp()

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
                time.time() - last_heard_time > self.settings[Settings.REC_TIMEOUT]
            ):
                print("barking stopped")
                barking_stopped_at = timestamp.timestamp()
                self.barking_stopped_at_q.put(barking_stopped_at)
                print(
                    "barking lasted for {} seconds".format(
                        barking_stopped_at - barking_started_at
                    )
                )
                self.is_recording = False
                fileWriteThread.join()

            # if self.is_recording:
            #     print("time since last bark: ", time.time() - last_heard_time)

    def recordingListen(
        self, recordingQLock: threading.Lock, recordingBarrier: threading.Barrier
    ):
        recordingBarrier.wait()

        self.record.flush_queue()

        recordingBarrier.wait()

        self.bufferSum = 0
        while self.runLoop:
            data = self.record.read_queue()

            self.recording_q.put(data)
            self.bufferSum += data[0].shape[0]

            if not self.is_recording and not self.is_writing:
                recordingQLock.acquire()
                while self.bufferSum > self.listening_q_size:
                    tmp = self.recording_q.get()[0]
                    self.bufferSum -= tmp.shape[0]
                recordingQLock.release()

    def saveRecording(self, recordingQLock: threading.Lock):
        db_conn = sqlite3.connect(db.dbname)
        now = datetime.datetime.now()
        nextDayId = db.getNextDayId(db_conn)
        filename = f"{now.strftime('%b-%d-%Y_%I:%M%p')}_#{nextDayId}"
        filepath = os.path.join(
            self.settings[Settings.RECORDING_FILE_PATH], f"{filename}.wav"
        )
        sf = SoundFile(
            filepath,
            "w",
            samplerate=self.settings[Settings.SAMPLE_RATE],
            channels=self.settings[Settings.NUM_CHANNELS],
            subtype="PCM_16",
            format="WAV",
        )

        maxChunkSize = (
            self.settings[Settings.SAMPLE_RATE]
            * self.settings[Settings.WRITE_BUFFER_LENGTH]
        )
        curChunkSize = 0

        firstTimestamp = None
        latestTimestamp = time.time()
        totalSampleCount = 0
        barking_stopped_at = maxTimestamp
        tsobj: datetime.datetime = None

        self.is_writing = True

        while latestTimestamp < barking_stopped_at:
            if (
                barking_stopped_at == maxTimestamp
                and not self.barking_stopped_at_q.empty()
            ):
                barking_stopped_at = self.barking_stopped_at_q.get()

            recordingQLock.acquire()

            (sample, tsobj) = self.recording_q.get()
            latestTimestamp = tsobj.timestamp()
            self.bufferSum -= sample.shape[0]

            recordingQLock.release()

            if sample is not None:
                sf.write(sample)
                curChunkSize += sample.shape[0]
                totalSampleCount += sample.shape[0]
                if firstTimestamp is None:
                    firstTimestamp = latestTimestamp

            if curChunkSize >= maxChunkSize:
                sf.flush()
                curChunkSize = 0

            # if (
            #     not self.is_recording
            #     and barking_stopped_at is not maxTimestamp
            #     and latestTimestamp < barking_stopped_at
            # ):
            #     print(
            #         "still recording... difference: ",
            #         barking_stopped_at - latestTimestamp,
            #     )

        sf.close()
        self.is_writing = False

        db.insertRecording(
            db_conn, filename, now, latestTimestamp - firstTimestamp, nextDayId
        )

        db_conn.close()

        # print("duration: ", latestTimestamp - firstTimestamp)
        # print("number of samples: ", totalSampleCount)
        # print("duration by samples: ", totalSampleCount / self.sample_rate)
        # print("first timestamp: ", firstTimestamp)
        # print("last timestamp: ", latestTimestamp)
        # print("barking stopped at: ", barking_stopped_at)

    def dbInsertBark(self, timestamp: datetime.datetime):
        dbConn = sqlite3.connect(db.dbname)
        db.insertBark(dbConn, timestamp)
        dbConn.close()
