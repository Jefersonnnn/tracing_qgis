from core.find_points import FindPoints
from core.tracing_pipelines import TracingPipelines


class TracingCAJ:
    def __init__(self, task_manager, pipelines, valves):
        self.__pipelines = pipelines
        self.__valves = valves
        self.__tm = task_manager

    def start(self):
        tracing_task = TracingPipelines(self.__pipelines, self.__valves, onfinish=self.select_hidrometers)
        self.__tm.addTask(tracing_task)

    def select_hidrometers(self):
        pipes_selecteds = [x for x in self.__pipelines[0].getSelectedFeatures()]
        find_hidrometers = FindPoints(pipes_selecteds)
        self.__tm.addTask(find_hidrometers)
