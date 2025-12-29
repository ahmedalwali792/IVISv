# [2025-12-29] results/sinks/base.py
from abc import ABC, abstractmethod

class BaseSink(ABC):
    @abstractmethod
    def handle(self, result: dict): pass