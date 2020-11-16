import dataclasses

import torch

from labml import tracker
from labml_helpers.train_valid2 import StateModule


class Metric(StateModule):
    pass


@dataclasses.dataclass
class AccuracyState:
    samples: int = 0
    correct: int = 0

    def reset(self):
        self.samples = 0
        self.correct = 0


class Accuracy(Metric):
    data: AccuracyState

    def __init__(self):
        super().__init__()

    def __call__(self, output: torch.Tensor, target: torch.Tensor):
        output = output.view(-1, output.shape[-1])
        target = target.view(-1)
        pred = output.argmax(dim=-1)
        self.data.correct += pred.eq(target).sum().item()
        self.data.samples += len(target)

    def create_state(self):
        return AccuracyState()

    def set_state(self, data: any):
        self.data = data

    def on_epoch_start(self):
        self.data.reset()

    def on_epoch_end(self):
        if self.data.samples == 0:
            return
        tracker.add("accuracy.", self.data.correct / self.data.samples)
