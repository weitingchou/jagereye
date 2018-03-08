from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import ray
import numpy as np


class DuplicatedModel(Exception):
    pass


@ray.remote
class NeuralNetworkManager(object):
    def __init__(self):
        self._models = dict()

    def register_model(self, name, model):
        if name in self._models:
            raise DuplicatedModel()
        self._models[name] = model
        self._models[name].load_model()

    def run_model(self, name, inputs):
        return self._models[name].run(inputs)
