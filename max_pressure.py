# -*- coding: utf-8 -*-
# @Time        : 2023/11/17 13:51
# @File        : max_pressure.py
# @Description :


def connect_exit_link(approach_link_id: str):
    direction = ['E', 'S', 'W', 'N']
    approach_link_dir = approach_link_id[0]
    connect_links = [conn_dir + 'O' for conn_dir in direction if conn_dir != approach_link_dir]
    return connect_links


def max_pressure_policy(queues, downstream_queues):
    """
    根据MaxPressure策略选择相位
    Args:
        queues: 当前交叉口各转向排队长度
        downstream_queues: 下游交叉口各转向排队长度

    Returns:
        当前步选择激活的相位

    References：https://www.sciencedirect.com/science/article/pii/S0968090X13001782
    """
    SATURATION_FLOW = 1400 / 3600
    movement_pressure_weight = {}
    for link_id, queue_length in queues.items():
        downstream_queue_lengths = []
        for exit_link_id in connect_exit_link(link_id):
            downstream_queue_lengths.append(downstream_queues[exit_link_id])
        downstream_avg_queue_length = sum(downstream_queue_lengths) / len(downstream_queue_lengths)
        pressure = queue_length - downstream_avg_queue_length
        movement_pressure_weight[link_id] = pressure * SATURATION_FLOW

    activated_link_id, current_max_weight = max(movement_pressure_weight.items(), key=lambda x: x[1])
    return activated_link_id, current_max_weight
