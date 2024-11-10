import time
import heapq
import random
import math
import numpy as np
from datetime import datetime
from trafficManager.vehicle import Vehicle
from simModel.movingScene import MovingScene
from simModel.networkBuild import NetworkBuild
from simModel.common.dataQueue import RenderQueue, FocusPos, SimPause
from simModel.common.dataBase import Database
from trafficManager.vehicle import Vehicle, DummyVehicle
from trafficManager.planning import planning, routingLane
from trafficManager.evaluation import ScoreCalculator


class Model:

    def __init__(
        self, netFile: str, run_time: int = None, demands: str = None, output_dir = "", seed = 0, egoID: int = -1
    ) -> None:
        
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(
            "-" * 10,
            time_now,
            "model initializes ...",
            "-" * 10,
        )
        # create a name with netfile, runtime, demands, system time
        db_name = netFile.split("/")[-1].split(".")[0] + "_SimTime" + str(run_time) + "_" + demands.split("/")[-1].split(".")[0] + "_Seed" + str(seed) + "_" + time_now
        # replace all the special characters with "_"
        db_name = "".join([c if c.isalnum() else "_" for c in db_name])
        # add the output_dir as directory, add / or \ based on the OS
        if output_dir:  
            if output_dir[-1] != "/" and output_dir[-1] != "\\":
                output_dir += "/"
        db_name = output_dir + db_name + ".db"
        print(db_name)

        self.run_time = run_time
        self.demands = demands
        self.timeStep = 0
        self.frequency = 4
        self.plotEngine = None
        self.ego = Vehicle(egoID)
        self.vehRunning: dict[str, Vehicle] = {}
        self.vehDemand: dict[str, Vehicle] = {}
        self.netInfo = NetworkBuild(netFile)
        self.netInfo.getData()
        self.ms = MovingScene(self.netInfo)
        self.renderQueue = RenderQueue(10)
        self.focusPos = FocusPos()
        self.simPause = SimPause()
        self.db = Database(db_name)

    def start(self,seed=0):
        """
        Initializes the simulation by generating the initial vehicle flow,
        routing lanes for the vehicles, creating traffic lights, and initializing the database.
        """
        self.getDemand(seed)  # init flow
        self.route = routingLane(self.netInfo, self.vehDemand)
        self.netInfo.createTrafficLight(self.frequency)
        self.db.initDB()

    def getVehInfo(self, veh: Vehicle):
        """Retrieves and updates the information of a given vehicle."""
        veh.xQ.append(veh.x)
        veh.yQ.append(veh.y)
        veh.hdgQ.append(veh.hdg)
        veh.velQ.append(veh.vel)
        veh.accQ.append(veh.acc)
        veh.yawQ.append(veh.yaw)
        veh.roadIdQ.append(veh.roadId)
        veh.planXQ = veh.planTra.xQ
        veh.planYQ = veh.planTra.yQ
        veh.planHdgQ = veh.planTra.hdgQ
        veh.planVelQ = veh.planTra.velQ
        veh.planAccQ = veh.planTra.accQ
        veh.planYawQ = veh.planTra.yawQ
        veh.planRoadIdQ = veh.planTra.roadIdQ

    def getVehFlow(self, period, seed=0):
        """Generates vehicle flow for a given period by reading demand data from a file."""
        # 这行代码设置了随机数生成器的种子为 0，以确保每次运行时生成的随机数序列相同，从而使结果可重复。
        random.seed(seed)
        print("seed:",seed)
        # carFlow 是一个空字典，用于存储生成的车辆信息。V_MIN 和 V_MAX 是车辆速度的最小值和最大值，初始值均为 0。
        carFlow = dict()
        V_MIN, V_MAX = 0, 0
        infilie = open(self.demands)
        demand = infilie.readline()  # skip the first line
        demand = infilie.readline()
        velID = 1
        while len(demand) > 1:
            sub = demand.strip("\n").split(",")
            fromNone, toNone, direction, qr = (
                str(sub[0]),
                str(sub[1]),
                int(sub[2]),
                int(sub[3]),
            )
            lampda = qr / 3600
            arrivalTime = 0
            length, width = 5.0, 2.0
            # 在这个循环中，代码生成每辆车的到达时间 arrivalTime 和初始速度 initVel。
            # timeHeadway 是车辆之间的时间间隔，通过指数分布生成。
            # 然后，创建一个 Vehicle 实例，并将其添加到 carFlow 字典中。
            while arrivalTime < period:
                # generate arrival time
                timeHeadway = round(-1 / lampda * math.log(random.random()), 2)
                arrivalTime += timeHeadway
                initVel = round(random.random() * (V_MAX - V_MIN), 2) + V_MIN
                carFlow[velID] = Vehicle(
                    velID,
                    arrivalTime,
                    fromNone,
                    toNone,
                    direction,
                    initVel,
                    length,
                    width,
                )
                velID += 1
            demand = infilie.readline()
        return carFlow

    def getDemand(self,seed=0):
        """
        Retrieves the vehicle demand for a given period of time.

        The demand is calculated by first determining the period of time to consider (30% of the total run time).
        Then, it generates the vehicle flow for this period using the `getVehFlow` method.
        Finally, it updates the `vehDemand` dictionary with the vehicles that have an arrival time greater than the current time step.
        """
        period = self.run_time * 0.3
        carFlow = self.getVehFlow(period,seed)
        for t in np.arange(period):
            for vehId, veh in carFlow.items():
                if vehId not in self.vehDemand and veh.arrivalTime > t:
                    self.vehDemand[vehId] = veh

    def update_evluation_data(self):
        """Updates the evaluation data for the current simulation."""
        vehs = list(self.ms.vehInAoI.values())
        score_calc = ScoreCalculator(self.ego, vehs, self.netInfo, self.frequency)
        self.ego.drivingScore = score_calc.calculate()

    def moveStep(self):
        """
        Advances the simulation by one time step.

        Increments the internal time step counter, updates the state of traffic lights,
        and plans the movement of vehicles based on the current time step and simulation frequency.
        """
        self.timeStep += 1
        for index in self.netInfo.tls:
            self.netInfo.tls[index].state_calculation(self.timeStep)
        self.vehDemand, self.vehRunning = planning(
            self.netInfo, self.vehDemand, self.vehRunning, self.timeStep, self.frequency
        )

    def updateVeh(self):
        """
        Updates the vehicle information and its surroundings in the simulation.

        This function checks the status of the ego vehicle and updates its information
        accordingly. It also updates the evaluation data, scene, and surrounding vehicles.
        """
        if self.ego.id == -1 and self.vehRunning:
            self.ego = list(self.vehRunning.values())[0]
        # if ego arrive the destination
        if self.vehRunning and self.ego.id != 0 and self.ego.id not in self.vehRunning:
            state = [
                self.ego.x,
                self.ego.y,
                self.ego.scf,
                self.ego.tcf,
                self.ego.roadId,
            ]
            self.ego = DummyVehicle(id=0, state=state)
        if self.ego.id in self.vehRunning or self.ego.id == 0:
            for veh in self.vehRunning.values():
                self.getVehInfo(veh)
            if self.ego.id > 0:
                self.update_evluation_data()
            self.ms.updateScene(self.ego)
            self.ms.updateSurroudVeh(self.ego, self.vehRunning)
            self.simTime = self.timeStep / self.frequency
            self.ms.getPlotInfo(self.ego, self.netInfo.tls)
            self.renderQueue.put((self.ms.vehInfo, self.simTime))
            self.db.updateDB(self.vehRunning, self.netInfo.tls, self.timeStep)
        self.updateFocusPos()

    def updateFocusPos(self):
        """
        Updates the focus position in the simulation.

        If a new focus position is available, it retrieves the position, removes it from the queue,
        and checks if there is a nearby vehicle. If a nearby vehicle is found, it updates the ego vehicle.
        Otherwise, it converts the mouse position to Frenet coordinates and creates a dummy vehicle.
        If the conversion fails, it prints an error message.
        """
        if self.focusPos.getPos():
            newFocusPos = self.focusPos.getPos()
            self.focusPos.queue.pop()
            nearVehId = self.getNearVeh(newFocusPos)
            if nearVehId:
                self.ego = self.vehRunning[nearVehId]
            else:
                get_mouse_info = self.netInfo.cartesian2Frenet(
                    newFocusPos[0], newFocusPos[1]
                )
                if get_mouse_info:
                    state = newFocusPos + get_mouse_info
                    self.ego = DummyVehicle(id=0, state=state)
                else:
                    print("please choose a road or a vehicle")

    def getNearVeh(self, pos: list):
        """Retrieves the ID of the nearest vehicle to a given position."""
        disList = []
        for vehId, veh in self.vehRunning.items():
            dis = np.hypot(veh.x - pos[0], veh.y - pos[1])
            disList.append([dis, vehId])
        heapq.heapify(disList)
        if len(disList) > 0:
            minDis, nearVehId = heapq.heappop(disList)
            if minDis <= 10:
                return nearVehId

    def replayMoveStep(self):
        """
        Advances the simulation by one time step. If the run time is not set, 
        it retrieves the run time from the database.

        Attributes:
            timeStep (int): The current time step of the simulation.
            run_time (int): The total run time of the simulation.
            db (Database): The database instance to retrieve the run time from.
        """
        self.timeStep += 1
        if not self.run_time:
            self.run_time = self.db.getRunTime()

    def replayUpdateVeh(self):
        """
        Updates the vehicle information for the current simulation time step.

        This method retrieves vehicle and traffic light information from the database,
        updates the ego vehicle and surrounding vehicles, and updates the scene and 
        rendering queue accordingly.

        Steps:
        1. Calculate the current simulation time.
        2. Retrieve vehicle and traffic light information from the database.
        3. Update the running vehicles dictionary.
        4. Update the ego vehicle based on its current state.
        5. If the ego vehicle is running or has arrived at the destination:
            - Update evaluation data if the ego vehicle is running.
            - Update the scene and surrounding vehicles.
            - Retrieve plot information.
            - Add the vehicle information and simulation time to the render queue.
        6. Update the focus position.

        Exceptions:
        - If there is an error retrieving data from the database, the method returns early.

        Returns:
        None
        """
        # 1. Calculate the current simulation time.
        self.simTime = self.timeStep / self.frequency
        # 2. Retrieve vehicle and traffic light information from the database.
        try:
            vehInfo, tlsInfo = self.db.getDB(self.timeStep)
        except:
            return
        self.vehRunning = {}
        for vehId in vehInfo:
            self.vehRunning[vehId] = vehInfo[vehId]
        if self.vehRunning:
            if self.ego.id == -1:
                self.ego = list(self.vehRunning.values())[0]
            elif self.ego.id > 0 and self.ego.id in self.vehRunning:
                self.ego = self.vehRunning[self.ego.id]
            elif self.ego.id != 0:
                # the ego arrives the destination
                state = [
                    self.ego.x,
                    self.ego.y,
                    self.ego.scf,
                    self.ego.tcf,
                    self.ego.roadId,
                ]
                self.ego = DummyVehicle(id=0, state=state)
        if self.ego.id in self.vehRunning or self.ego.id == 0:
            if self.ego.id > 0:
                self.update_evluation_data()
            self.ms.updateScene(self.ego)
            self.ms.updateSurroudVeh(self.ego, self.vehRunning)
            self.ms.getPlotInfo(self.ego, tlsInfo)
            self.renderQueue.put((self.ms.vehInfo, self.simTime))
        self.updateFocusPos()

    def destroy(self):
        self.db.closeDB()
        time.sleep(2)
        if self.plotEngine:
            self.plotEngine.gui.destroy()

    def end(self):
        return self.timeStep >= self.run_time
