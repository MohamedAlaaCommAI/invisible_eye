"""
decision_engine.py
-------------------
Turns the (Spectral Entropy S, Doppler Spread D) pair into one of the
human-readable system states described in the paper: an empty
environment, static human presence, or dynamic motion -- by comparing
against the thresholds learned during calibration.
"""

from __future__ import annotations

from enum import Enum

from .calibration import Thresholds


class SystemState(Enum):
    CALIBRATING = "CALIBRATING"
    EMPTY = "SYSTEM READY: EMPTY"
    PRESENCE = "ALERT: PERSON DETECTED"
    MOTION = "ALERT: MOTION DETECTED"


class DecisionEngine:
    """Classifies room occupancy state from entropy and Doppler metrics.

    Decision logic (matches the original "Radar Decision Console"):
      - S <= entropy_threshold                -> EMPTY
      - S >  entropy_threshold and D < doppler_threshold -> PRESENCE (static human)
      - S >  entropy_threshold and D >= doppler_threshold -> MOTION (moving human)
    """

    def decide(self, entropy_value: float, doppler_value: float, thresholds: Thresholds) -> SystemState:
        if entropy_value <= thresholds.entropy:
            return SystemState.EMPTY
        if doppler_value < thresholds.doppler:
            return SystemState.PRESENCE
        return SystemState.MOTION
