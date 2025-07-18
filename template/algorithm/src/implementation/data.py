from dataclasses import dataclass

@dataclass
class ModelParameters:
    model: str = "nomic-embed-text"


@dataclass
class InputParameters:
    model: ModelParameters
