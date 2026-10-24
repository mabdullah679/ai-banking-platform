import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedModel:
    """A model held in memory: a simple linear scorer."""

    name: str
    version: int
    weights: list[float]
    bias: float

    # Scores one set of features: the weighted sum plus the bias.
    def predict(self, features: list[float]) -> float:
        return sum(w * x for w, x in zip(self.weights, features, strict=True)) + self.bias


class ModelStore:
    """Holds the live model and reloads it whenever the platform rewrites the pointer file."""

    def __init__(self, pointer: Path) -> None:
        self.pointer = pointer
        self.model: LoadedModel | None = None
        self.reload_errors = 0
        self._seen: tuple[int, int] | None = None

    # Loads the pointer and the artifact it names into a LoadedModel (raises if either is bad).
    def _load(self) -> LoadedModel:
        pointer = json.loads(self.pointer.read_text())
        artifact = json.loads((self.pointer.parent / pointer["artifact"]).read_text())
        return LoadedModel(
            pointer["name"], int(pointer["version"]), list(artifact["weights"]), artifact["bias"]
        )

    # Checks whether the pointer changed since last time and reloads if so. Returns True on reload.
    # A bad new version keeps the old model serving (and is counted) instead of taking it down.
    def refresh(self) -> bool:
        try:
            stat = os.stat(self.pointer)
        except FileNotFoundError:
            return False
        marker = (stat.st_mtime_ns, stat.st_ino)
        if marker == self._seen:
            return False
        self._seen = marker
        try:
            self.model = self._load()
        except (OSError, ValueError, KeyError):
            self.reload_errors += 1
            return False
        return True
