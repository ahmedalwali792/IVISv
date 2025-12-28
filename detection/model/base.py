# FILE: detection/model/base.py
# ------------------------------------------------------------------------------
from abc import ABC, abstractmethod
import numpy as np

class BaseModel(ABC):
    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def input_shape(self):
        pass

    @abstractmethod
    def predict(self, input_tensor: np.ndarray):
        pass
