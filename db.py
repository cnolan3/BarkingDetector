import sqlite3
import datetime
from utils import getTodaysFirstTimestamp

dbname = "barking_detector.db"


def createTables(dbConn: sqlite3.Connection):
    cur = dbConn.cursor()
    cur.execute(
        "CREATE TABLE if NOT EXISTS audio_files(\
            id  INTEGER PRIMARY KEY  NOT NULL,\
            name        TEXT    NOT NULL,\
            timestamp   REAL    NOT NULL,\
            length      REAL    NOT NULL,\
            day_id      INT     NOT NULL\
        )"
    )

    cur.execute(
        "CREATE TABLE if NOT EXISTS barks(\
            id  INTEGER PRIMARY KEY  NOT NULL,\
            timestamp   REAL    NOT NULL,\
            confidence  REAL    NOT NULL\
        )"
    )

    dbConn.commit()


def getNextDayId(dbConn: sqlite3.Connection):
    cur = dbConn.cursor()
    today = getTodaysFirstTimestamp()

    lastDayId = cur.execute(
        f"SELECT max(day_id) from audio_files WHERE timestamp >= {today}"
    ).fetchone()[0]

    nextDayId = 1
    if lastDayId:
        nextDayId = lastDayId + 1

    return nextDayId


def insertRecording(
    dbConn: sqlite3.Connection,
    name: str,
    timestamp: datetime.datetime,
    length: float,
    nextDayId: int,
):
    cur = dbConn.cursor()
    tsseconds = timestamp.timestamp()

    cur.execute(
        f"INSERT INTO audio_files (name, timestamp, length, day_id)\
                VALUES({name!r}, {tsseconds}, {length}, {nextDayId})\
            "
    )

    dbConn.commit()


def insertBark(
    dbConn: sqlite3.Connection, timestamp: datetime.datetime, confidence: float
):
    cur = dbConn.cursor()
    tsseconds = timestamp.timestamp()

    cur.execute(
        f"INSERT INTO barks (timestamp, confidence) VALUES({tsseconds}, {confidence})"
    )

    dbConn.commit()
