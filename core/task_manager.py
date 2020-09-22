from core.tracing_pipelines import TracingPipelines


class TracingCAJ:
    def __init__(self, task_manager, pipelines, valves):
        self.__pipelines = pipelines
        self.__valves = valves
        self.__tm = task_manager

    def start(self):
        tracing_task = TracingPipelines(self.__pipelines, self.__valves)
        self.__tm.addTask(tracing_task)
