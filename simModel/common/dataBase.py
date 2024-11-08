import peewee as pw

import os
import base64
import pickle
from dataclasses import dataclass

# This module provides a database interface for storing and retrieving simulation data using SQLite and Peewee ORM.

# Classes:
#     VehicleInfo: A dataclass representing vehicle information.
#     Database: A class for managing the SQLite database operations.
#     VehicleDB: A Peewee model representing the vehicle database table.
#     tlsDB: A Peewee model representing the traffic light system database table.

# Functions:
#     Database.__init__: Initializes the Database instance and sets up the SQLite database connection.
#     Database.initDB: Initializes the database by creating the necessary tables.
#     Database.updateDB: Updates the database with the current vehicle and traffic light system data.
#     Database.getRunTime: Retrieves the maximum time step from the VehicleDB.
#     Database.getDB: Retrieves the vehicle and traffic light system data for a specific time step.
#     Database.closeDB: Closes the database connection.

dbName = "simulationDatabase1.db"

# dbName = "simulationDatabase.db"

@dataclass
class VehicleInfo:
    id: int
    length: float
    width: float
    x: float
    y: float
    scf: float
    tcf: float
    hdg: float
    deArea: float
    roadId: str
    EXPECT_VEL: float
    xQ: list[float]
    yQ: list[float]
    hdgQ: list[float]
    velQ: list[float]
    accQ: list[float]
    yawQ: list[float]
    roadIdQ: list[str]
    planXQ: list[float]
    planYQ: list[float]
    planHdgQ: list[float]
    planVelQ: list[float]
    planAccQ: list[float]
    planYawQ: list[float]
    planRoadIdQ: list[str]


class Database:
    def __init__(self, db_Name = dbName) -> None:
        self.db = pw.SqliteDatabase(db_Name)

    def initDB(self):
        if os.path.exists(dbName):
            os.remove(dbName)
        self.db.connect()
        self.db.create_tables([VehicleDB, tlsDB])

    def updateDB(self, vehRunning, tls, timeStep: int):
        vehs = dict()
        for veh in vehRunning.values():
            vehs[veh.id] = VehicleInfo(
                veh.id,
                veh.length,
                veh.width,
                veh.x,
                veh.y,
                veh.scf,
                veh.tcf,
                veh.hdg,
                veh.deArea,
                veh.roadId,
                veh.EXPECT_VEL,
                veh.xQ,
                veh.yQ,
                veh.hdgQ,
                veh.velQ,
                veh.accQ,
                veh.yawQ,
                veh.roadIdQ,
                veh.planXQ,
                veh.planYQ,
                veh.planHdgQ,
                veh.planVelQ,
                veh.planAccQ,
                veh.planYawQ,
                veh.planRoadIdQ,
            )

        newVeh = VehicleDB(
            timeStep=timeStep,
            info=base64.b64encode(pickle.dumps(vehs)).decode("utf-8"),
        )
        newVeh.save()
        newTls = tlsDB(
            timeStep=timeStep,
            info=base64.b64encode(pickle.dumps(tls)).decode("utf-8"),
        )
        newTls.save()

    def getRunTime(self):
        """
        Retrieves the maximum time step from the VehicleDB.

        Returns:
            int: The maximum time step value from the VehicleDB.
        """
        return VehicleDB.select(pw.fn.Max(VehicleDB.timeStep)).scalar()

    def getDB(self, timeStep: int):
        """
        Retrieves vehicle and traffic light information from the database for a given time step.

        Args:
            timeStep (int): The time step for which to retrieve the data.

        Returns:
            tuple: A tuple containing two elements:
                - vehInfo: The vehicle information decoded from the database.
                - tls: The traffic light system information decoded from the database.

        Raises:
            Exception: If there is an error connecting to the database or decoding the data.
        """
        try:
            self.db.connect()
        except:
            pass
        vehInfo = pickle.loads(
            base64.b64decode(VehicleDB.get(timeStep=timeStep).info.encode("utf-8"))
        )
        tls = pickle.loads(
            base64.b64decode(tlsDB.get(timeStep=timeStep).info.encode("utf-8"))
        )
        return vehInfo, tls

    def closeDB(self):
        try:
            if self.db:
                self.db.close()
                print("Database connection closed successfully.")
            else:
                print("Database connection is already closed or was never opened.")
        except Exception as e:
            print(f"An error occurred while closing the database: {e}")


class VehicleDB(pw.Model):
    timeStep = pw.IntegerField()
    info = pw.TextField()

    class Meta:
        database = pw.SqliteDatabase(dbName)


class tlsDB(pw.Model):
    timeStep = pw.IntegerField()
    info = pw.TextField()

    class Meta:
        database = pw.SqliteDatabase(dbName)
