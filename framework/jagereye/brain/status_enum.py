from enum import Enum

class WorkerStatus(Enum):
    CREATE = 'create'
    INITIAL = 'initial'
    HSHAKE_1 = 'hshake_1'
    CONFIG = 'config'
    READY = 'ready'
    RUNNING = 'running'
    DOWN = 'down'
