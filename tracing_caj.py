from tracing_qgis import TracingQGIS

class TracingCAJ:
    def __init__(self, task_manager, networks, registers):
        self.networks = networks
        self.registers = registers
        self.task_manger = task_manager

        print(self.networks, self.registers, self.task_manger)

    def start(self):
        print('Instanciando TracingQGIS')
        tracing_task = TracingQGIS(self.networks, self.registers)
        print('Adicionando em Tasks')
        self.task_manger.addTask(tracing_task)
