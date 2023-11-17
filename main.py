import os
from itertools import chain

import pandas as pd
import sumolib
import traci
import traci.constants as tc
from tqdm import tqdm

from max_pressure import max_pressure_policy

JUNCTION_ID = 'J0'
APPROACH_LINK = ['NI', 'EI', 'SI', 'WI']
EXIT_LINK = ['NO', 'EO', 'SO', 'WO']

LINK_LENGTH = {'NI': 172.8, 'EI': 172.8, 'SI': 172.8, 'WI': 172.8, 'NO': 42.8, 'EO': 42.8, 'SO': 42.8, 'WO': 42.8}

STEP_LENGTH_SEC = 3
CONTROL_LENGTH_SEC = 12


def get_link_vehicle_num(links: list):
    vehicle_num = {}
    for link_id in links:
        sub_result = traci.edge.getSubscriptionResults(link_id)
        last_step_vehicle_num = sub_result[tc.LAST_STEP_VEHICLE_NUMBER]
        vehicle_num[link_id] = last_step_vehicle_num
    return vehicle_num


def get_current_phase():
    PHASE_ORDER_MAPPING = {0: 'N', 1: 'E', 2: 'S', 3: 'W'}
    state = traci.trafficlight.getRedYellowGreenState(JUNCTION_ID)
    # print(state)
    green_index = state.index('G')
    activate_phase = PHASE_ORDER_MAPPING[green_index // 3]
    return activate_phase


def info_retrieve():
    """

    Returns:
        1) state record: dict[str, int], {'NI': 2, 'NO': 3, ...}
        2) action record: dict[str, int], {'N': 0, 'E':1, 'S': 0, 'W': 0}

    """
    vehicles_num = get_link_vehicle_num(APPROACH_LINK)
    vehicles_num.update(get_link_vehicle_num(EXIT_LINK))
    state_record = {}
    for link_id, veh_num in vehicles_num.items():
        length = LINK_LENGTH[link_id]
        density = veh_num / length
        state_record[link_id] = density
    activate_phase = get_current_phase()
    action_record = {direction: 1 if direction == activate_phase else 0 for direction in ['N', 'E', 'S', 'W']}
    return state_record, action_record


def info_to_series(state_record, action_record, sim_step, signal_change_flag):
    action_record = {signal_dir + '_TL': state for signal_dir, state in action_record.items()}
    record = {'timestamp': sim_step, 'change': signal_change_flag}
    record.update(**state_record, **action_record)
    return pd.Series(record)


def get_links_queue(links: list[str]):
    queue_res = {}
    for link_id in links:
        queue_num = traci.edge.getLastStepHaltingNumber(link_id)
        queue_res[link_id] = queue_num
    return queue_res


def pack_state_string(activate_phase):
    direction_orders = ['N', 'E', 'S', 'W']
    green_index = direction_orders.index(activate_phase[0])
    state_str = ['r'] * 12
    for i in range(3):
        state_str[3 * green_index + i] = 'G'
    return ''.join(state_str)


def max_pressure_signal_update():
    approach_link_queue = get_links_queue(APPROACH_LINK)
    exit_link_queue = get_links_queue(EXIT_LINK)
    activate_phase, _ = max_pressure_policy(queues=approach_link_queue, downstream_queues=exit_link_queue)
    set_state_string = pack_state_string(activate_phase)
    traci.trafficlight.setRedYellowGreenState(JUNCTION_ID, set_state_string)


def simulation_start(sumo_cfg_fp: str, seed: int = 0):
    sumoBinary = sumolib.checkBinary('sumo-gui')
    sumo_cmd = [sumoBinary, '-c', sumo_cfg_fp]
    sumo_cmd.extend(['--seed', str(seed)])
    traci.start(sumo_cmd)
    subscribe_data()


def simulation_run(warm_up_time: int = 0):
    data_cache = []
    while traci.simulation.getTime() < traci.simulation.getEndTime():
        traci.simulationStep(0)
        sim_step = traci.simulation.getTime()
        if sim_step < warm_up_time:
            continue

        change_flag = 0
        if sim_step % CONTROL_LENGTH_SEC == 0:
            max_pressure_signal_update()
            change_flag = 1

        if sim_step % STEP_LENGTH_SEC == 0:
            state_record, action_record = info_retrieve()
            series_data = info_to_series(state_record, action_record, sim_step, change_flag)
            data_cache.append(series_data)
    return pd.DataFrame(data_cache)


def simulation_finish():
    traci.close()

def subscribe_data():
    for link_id in chain(APPROACH_LINK, EXIT_LINK):
        traci.edge.subscribe(link_id, varIDs=(tc.LAST_STEP_VEHICLE_NUMBER,))


def save_data(data: pd.DataFrame, save_dir: str = 'output'):
    existed_file_name = [int(file.split('.')[0]) for file in os.listdir(save_dir)]
    current_max_record_index = max(existed_file_name) if len(existed_file_name) else 0
    file_name = str(current_max_record_index + 1) + '.csv'
    data.to_csv(os.path.join(save_dir, file_name), index=False)


def main():
    for i in tqdm(range(100)):
        simulation_start(sumo_cfg_fp='network/single.sumocfg', seed=i)
        output_data = simulation_run(warm_up_time=200)
        save_data(output_data, save_dir='output/2high')
        simulation_finish()


if __name__ == '__main__':
    main()
