from datetime import datetime
import re
import time

import cv2
import os
import base64
import numpy as np
import requests
from rich import print
from rich.markdown import Markdown
from typing import Dict, List

import logger, logging
from simInfo.EnvDescriptor import EnvDescription
from trafficManager.traffic_manager import TrafficManager, LaneChangeException
from simModel.Model import Model
from simModel.MPGUI import GUI

from simModel.DataQueue import QuestionAndAnswer

from trafficManager.common.vehicle import Behaviour
from simInfo.CustomExceptions import (
    CollisionException, LaneChangeException, 
    CollisionChecker, record_result,
    BrainDeadlockException, TimeOutException
)

decision_logger = logger.setup_app_level_logger(
    logger_name="LLMAgent", file_name="llm_decision.log")
LLM_logger = logging.getLogger("LLMAgent").getChild(__name__)


    
def NPImageEncode(npimage: np.ndarray) -> str:
    _, buffer = cv2.imencode('.png', npimage)
    npimage_base64 = base64.b64encode(buffer).decode('utf-8')
    return npimage_base64

class VLMAgent:
    def __init__(self, max_tokens: int = 4000) -> None:
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.max_tokens = max_tokens
        self.content = []

    def addImageBase64(self, image_base64: str):
        imagePrompt = {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_base64}",
                "detail": "low"
            }
        }
        self.content.append(imagePrompt)

    def addTextPrompt(self, textPrompt: str):
        textPrompt = {
            "type": "text",
            "text": textPrompt
        }
        self.content.append(textPrompt)

    def request(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": self.content
                }
            ],
            "max_tokens": self.max_tokens
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        self.content = []

        return response.json()

    def str2behavior(self, decision: str) -> Behaviour:
            if decision == 'IDLE':
                return Behaviour.IDLE
            elif decision == 'Acceleration':
                return Behaviour.AC
            elif decision == 'Deceleration':
                return Behaviour.DC
            elif decision == 'Turn-right':
                return Behaviour.LCR
            elif decision == 'Turn-left':
                return Behaviour.LCL
            else:
                errorStr = f'The decision `{decision}` is not implemented yet!'
            raise NotImplementedError(errorStr)


    def makeDecision(self):
        start = time.time()
        response = self.request()
        print(response)
        ans = response['choices'][0]['message']['content']
        prompt_tokens = response['usage']['prompt_tokens']
        completion_tokens = response['usage']['completion_tokens']
        total_tokens = response['usage']['total_tokens']
        end = time.time()
        timeCost = end - start
        print('GPT-4V: ')
        print(Markdown(ans))
        match = re.search(r'## Decison\n(.*)\n', ans)
        behavior = None
        if match:
            decision = match.group(1)
            behavior = self.str2behavior(decision)
        else:
            raise ValueError('GPT-4V did not return a valid decision')
        return (
            behavior, ans, prompt_tokens, 
            completion_tokens, total_tokens, timeCost)
    

SYSTEM_PROMPT = """
You are GPT-4V(ision), a large multi-modal model trained by OpenAI. Now you act as a mature driving assistant, who can give accurate and correct advice for human driver in complex urban driving scenarios. You'll receive some images from the onboard camera. You'll need to make driving inferences and decisions based on the information in the images. At each decision frame, you receive navigation information and a collection of actions. You will perform scene description, and reasoning based on the navigation information and the front-view image. Eventually you will select the appropriate action output from the action set.
Make sure that all of your reasoning is output in the `## Reasoning` section, and in the `## Decision` section you should only output the name of the action, e.g. `AC`, `IDLE` etc.

Your answer should follow this format:
## Description
Your description of the front-view image.
## Reasoning
reasoning based on the navigation information and the front-view image.
## Decison
one of the actions in the action set.(SHOULD BE exactly same and no other words!)
"""
if __name__ == '__main__':
    ego_id = '139'
    sumo_gui = False
    sumo_cfg_file = './networkFiles/CarlaTown06/Town06.sumocfg'
    sumo_net_file = "./networkFiles/CarlaTown06/Town06.net.xml"
    sumo_rou_file = "./networkFiles/CarlaTown06/carlavtypes.rou.xml,networkFiles/CarlaTown06/Town06.rou.xml"
    carla_host = '127.0.0.1'
    carla_port = 2000
    step_length = 0.1
    tls_manager = 'sumo'
    sync_vehicle_color = True
    sync_vehicle_lights = True

    stringTimestamp = datetime.strftime(datetime.now(), '%Y-%m-%d_%H-%M-%S')
    database = './experiments/zeroshot/gpt4v/' + stringTimestamp + '.db'

    # init LLMDriver
    model = Model(
        egoID=ego_id, netFile=sumo_net_file, rouFile=sumo_rou_file,
        cfgFile=sumo_cfg_file, dataBase=database, SUMOGUI=sumo_gui,
        CARLACosim=True, carla_host=carla_host, carla_port=carla_port
    )
    planner = TrafficManager(model)
    descriptor = EnvDescription(planner.config)
    collision_checker = CollisionChecker()
    model.start()

    gui = GUI(model)
    gui.start()

    gpt4v = VLMAgent()

    total_start_time = time.time()
    try:
        while not model.tpEnd:
            model.moveStep()
            collision_checker.CollisionCheck(model)
            if model.timeStep % 10 == 0:
                roadgraph, vehicles = model.exportSce()
                if model.tpStart and roadgraph:
                    actionInfo, naviInfo = descriptor.getDescription(
                        roadgraph, vehicles, planner, model.timeStep * 0.1, only_info=True)
                    # actionInfo = descriptor.availableActionsDescription(roadgraph)
                    # naviInfo = descriptor.getNavigationInfo(roadgraph)
                    # egoInfo = descriptor.getEgoInfo()
                    TotalInfo = '## Available actions\n\n' + actionInfo + '\n\n' + '## Navigation information\n\n' + naviInfo
                    images = model.getCARLAImage(1, 1)
                    # if images:
                    front_img = images[-1].CAM_FRONT
                    front_left_img = images[-1].CAM_FRONT_LEFT
                    front_right_img = images[-1].CAM_FRONT_RIGHT
                    if isinstance(front_img, np.ndarray):
                        gpt4v.addTextPrompt(SYSTEM_PROMPT)
                        gpt4v.addTextPrompt('The next three images are images captured by the left front, front, and right front cameras.\n')
                        gpt4v.addImageBase64(NPImageEncode(front_left_img))
                        gpt4v.addImageBase64(NPImageEncode(front_img))
                        gpt4v.addImageBase64(NPImageEncode(front_right_img))
                        gpt4v.addTextPrompt(f'\nThe current frame information is:\n{TotalInfo}')
                        gpt4v.addTextPrompt('Now, please tell me your answer. Please think step by step and make sure it is right.')
                        behaviour, ans, prompt_tokens, completion_tokens, total_tokens,timecost = gpt4v.makeDecision()
                        print('[blue]behavior: {}[/blue]'.format(behaviour))
                        model.putQA(
                            QuestionAndAnswer(
                                '', naviInfo, actionInfo, '', 
                                ans, prompt_tokens, completion_tokens, total_tokens, 
                                timecost, int(behaviour)
                            )
                        )
                        trajectories = planner.plan(
                            model.timeStep * 0.1, roadgraph, vehicles, Behaviour(behaviour), other_plan=False
                        )
                        model.setTrajectories(trajectories)
                else:
                    model.ego.exitControlMode()

            model.updateVeh()
    except (
        CollisionException, LaneChangeException, 
        BrainDeadlockException, TimeOutException
        ) as e:
        record_result(model, total_start_time, False, str(e))
        model.dbBridge.commitData()
    except Exception as e:
        model.dbBridge.commitData()
        raise e
    else:
        record_result(model, total_start_time, True, None)
    finally:
        model.destroy()
        gui.terminate()
        gui.join()