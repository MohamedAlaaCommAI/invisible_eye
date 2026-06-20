"""
calibration.py
---------------
Implements the "establishing dynamic calibration thresholds" step
described in the paper's abstract: the system observes an assumed-empty
room for a fixed number of frames, then sets the entropy and Doppler
alert thresholds to (mean + k * std) of that baseline, so thresholds
adapt to the specific room/hardware instead of using fixed constants.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .config import RadarConfig

logger = logging.getLogger(__name__)


@dataclass
class Thresholds:
    entropy: float
    doppler: float


class Calibrator:
    """Collects a baseline of (entropy, doppler) samples and derives thresholds."""

    def __init__(self, config: RadarConfig):
        self.config = config
        self._entropy_samples: List[float] = []
        self._doppler_samples: List[float] = []
        self._is_calibrated = False
        self.thresholds = Thresholds(
            entropy=config.default_entropy_threshold,
            doppler=config.default_doppler_threshold,
        )

    @property
    def is_calibrated(self) -> bool:
        return self._is_calibrated

    @property
    def progress(self) -> Tuple[int, int]:
        """Return (frames_collected, frames_required)."""
        return len(self._entropy_samples), self.config.calibration_frames

    def update(self, entropy_value: float, doppler_value: float) -> bool:
        """Feed one (S, D) sample during the calibration phase.

        Returns:
            True if calibration just completed on this call.
        """
        if self._is_calibrated:
            return False

        self._entropy_samples.append(entropy_value)
        self._doppler_samples.append(doppler_value)

        if len(self._entropy_samples) >= self.config.calibration_frames:
            self._finalize()
            return True
        return False

    def _finalize(self) -> None:
        k = self.config.calibration_std_multiplier
        entropy_arr = np.array(self._entropy_samples)
        doppler_arr = np.array(self._doppler_samples)

        self.thresholds = Thresholds(
            entropy=float(entropy_arr.mean() + k * entropy_arr.std()),
            doppler=float(doppler_arr.mean() + k * doppler_arr.std()),
        )
        self._is_calibrated = True
        logger.info(
            "Calibration complete: entropy_threshold=%.4f doppler_threshold=%.4f",
            self.thresholds.entropy, self.thresholds.doppler,
        )

    def reset(self) -> None:
        """Discard the current baseline and start calibrating again."""
        self._entropy_samples.clear()
        self._doppler_samples.clear()
        self._is_calibrated = False
