from enum import Enum

class WorkerStatus(Enum):
    CREATE = "create"
    INITIAL = "initial"
    HSHAKE_1 = "HSHAKE_1"
    READY = "READY"
    RUNNING = "RUNNING"
