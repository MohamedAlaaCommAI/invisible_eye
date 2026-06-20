"""
Invisible Eye -- Subspace Analysis of Wi-Fi CSI for Human Sensing.

A device-free human presence/motion sensing system based on
eigen-decomposition of the Wi-Fi CSI covariance matrix, using
Spectral Entropy and Doppler Spread as detection metrics.

See README.md for usage and AUDIT_REPORT.md for the engineering
notes on how this package relates to the original research notebook.
"""

from .calibration import Calibrator, Thresholds
from .config import RadarConfig
from .csi_math import (
    build_h_matrix,
    compute_covariance,
    doppler_spread,
    eigen_spectrum,
    process_window,
    spectral_entropy,
)
from .dashboard import LiveDashboard
from .decision_engine import DecisionEngine, SystemState
from .serial_interface import CSIReader

__all__ = [
    "RadarConfig",
    "CSIReader",
    "Calibrator",
    "Thresholds",
    "DecisionEngine",
    "SystemState",
    "LiveDashboard",
    "build_h_matrix",
    "compute_covariance",
    "eigen_spectrum",
    "spectral_entropy",
    "doppler_spread",
    "process_window",
]

__version__ = "1.0.0"
