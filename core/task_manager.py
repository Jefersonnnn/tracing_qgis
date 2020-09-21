from core.tracing_networks import TracingNetworks


class TracingCAJ:
    def __init__(self, task_manager, networks, registers):
        self.__networks = networks
        self.__registers = registers
        self.__tm = task_manager

    def start(self):
        tracing_task = TracingNetworks(self.__networks, self.__registers)
        self.__tm.addTask(tracing_task)
