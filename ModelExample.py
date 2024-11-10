from datetime import datetime
from simModel.model import Model
from visualization.plotEngine import PlotEngine
import sys
import logger
import time

log = logger.setup_app_level_logger(file_name="app_debug.log")


file_paths = {
    "CarlaTown01": "networkFiles/CarlaTown/Town01.xodr",
    "CarlaTown02": "networkFiles/CarlaTown/Town02.xodr",
    "CarlaTown03": "networkFiles/CarlaTown/Town03.xodr",
    "CarlaTown04": "networkFiles/CarlaTown/Town04.xodr",
    "CarlaTown05": "networkFiles/CarlaTown/Town05.xodr",
    "CarlaTown06": "networkFiles/CarlaTown/Town06.xodr",
    "CarlaTown07": "networkFiles/CarlaTown/Town07.xodr",
    "m510": "networkFiles/M510_FTX_TrafficSignals_Simple.xodr",
    "m210": "networkFiles/M210_FTX_FourWay_Protected_Left.xodr",
    "m211": "networkFiles/M211_FTX_FourWay_Permited_Left.xodr",
    "m244": "networkFiles/M244_FTX_Highway_Consecutive_Merges.xodr",
    "m480": "networkFiles/M480_FTX_Complex_Junction_noSignals.xodr",
    "m422": "networkFiles/M422_FTX_suburban_EuroNcap_junction.xodr",
}


def run_model(net_file, run_time, demands, seed=0, output_dir=""):
    model = Model(net_file, run_time, demands, output_dir, seed)
    model.start(seed)
    model.updateVeh()
    print(
        "-" * 10,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "real-time simulation is running ...",
        "-" * 10,
    )
    plotEngine = PlotEngine(model)
    plotEngine.start()

    while not model.end():
        if model.simPause.pause.value == 0:
            model.moveStep()
        model.updateVeh()
        time.sleep(0.00)
        if model.timeStep % 10 == 0:
            print(
                "running time: {:>4d} / {} | number of vehicles on the road: {:>3d}".format(
                    model.timeStep, model.run_time, len(model.vehRunning)
                )
            )
    print(
        "-" * 10,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "the simulation is end.",
        "-" * 10,
    )
    model.destroy()
    plotEngine.terminate()
    plotEngine.join()


def replay_model(net_file):
    model = Model(net_file)
    model.replayMoveStep()
    model.replayUpdateVeh()
    print(
        "-" * 10,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "replayed simulation is running ...",
        "-" * 10,
    )
    plotEngine = PlotEngine(model)
    plotEngine.start()
    while not model.end():
        if model.simPause.pause.value == 0:
            model.replayMoveStep()
        model.replayUpdateVeh()
        time.sleep(0.03)
        if model.timeStep % 10 == 0:
            print(
                "running time: {:>4d} / {} | number of vehicles on the road: {:>3d}".format(
                    model.timeStep, model.run_time, len(model.vehRunning)
                )
            )
    print(
        "-" * 10,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "the simulation is end.",
        "-" * 10,
    )
    model.destroy()
    plotEngine.terminate()
    plotEngine.join()


if __name__ == "__main__":
    
    if len(sys.argv) < 4:
        print("Usage: python ModelExample.py <net_file_key> <demands_file> <seed> <sim_time> [replay]")
        sys.exit(1)

    net_file_key = sys.argv[1]
    demands_file = sys.argv[2]
    seed = sys.argv[3]
    sim_time = sys.argv[4]

    net_file = file_paths[net_file_key]
    # Two modes are avialable for simulation
    # The replay mode requires reading database information
    if len(sys.argv) > 5 and sys.argv[5] == "replay":
        replay_model(net_file)
    else:
        run_model(net_file, run_time=int(sim_time), demands=demands_file, seed=int(seed), output_dir="")
