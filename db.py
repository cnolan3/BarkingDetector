import sqlite3
import datetime
from utils import getTodaysFirstTimestamp

dbname = "recordings.db"


def createTables(dbConn: sqlite3.Connection):
    cur = dbConn.cursor()
    cur.execute(
        "CREATE TABLE if NOT EXISTS AUDIO_FILES(\
            ID  INTEGER PRIMARY KEY  NOT NULL,\
            NAME        TEXT    NOT NULL,\
            TIMESTAMP   REAL    NOT NULL,\
            LENGTH      REAL    NOT NULL,\
            DAY_ID      INT     NOT NULL\
        )"
    )
    dbConn.commit()


def getNextDayId(dbConn: sqlite3.Connection):
    cur = dbConn.cursor()
    today = getTodaysFirstTimestamp()

    lastDayId = cur.execute(
        f"SELECT max(DAY_ID) from AUDIO_FILES WHERE TIMESTAMP >= {today}"
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
        f"INSERT INTO AUDIO_FILES (NAME, TIMESTAMP, LENGTH, DAY_ID)\
                VALUES({name!r}, {tsseconds}, {length}, {nextDayId})\
            "
    )

    dbConn.commit()
