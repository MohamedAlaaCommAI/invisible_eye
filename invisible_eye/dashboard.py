"""
dashboard.py
------------
The live visualization layer. Consolidates what used to be six
overlapping, copy-pasted notebook cells (a standalone H-matrix viewer,
a standalone covariance heatmap, a standalone eigenvalue bar chart, a
standalone decision console, and two nearly-identical "final" combined
dashboards) into a single, configurable, reusable dashboard class.

It shows three live panels:
  1. Raw CSI amplitude for the most recent packet.
  2. Spectral Entropy S over time, with the calibrated alert threshold.
  3. Doppler Spread D over time, with the calibrated alert threshold.

A status banner reports CALIBRATING / EMPTY / PERSON DETECTED / MOTION
DETECTED, driven by the DecisionEngine.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Deque, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from . import csi_math
from .calibration import Calibrator
from .config import RadarConfig
from .decision_engine import DecisionEngine, SystemState
from .serial_interface import CSIReader

logger = logging.getLogger(__name__)

_STATUS_COLORS = {
    SystemState.CALIBRATING: "white",
    SystemState.EMPTY: "lime",
    SystemState.PRESENCE: "yellow",
    SystemState.MOTION: "red",
}


class LiveDashboard:
    """Real-time, three-panel CSI sensing dashboard."""

    def __init__(
        self,
        config: RadarConfig,
        reader: CSIReader,
        calibrator: Optional[Calibrator] = None,
        decision_engine: Optional[DecisionEngine] = None,
    ):
        self.config = config
        self.reader = reader
        self.calibrator = calibrator or Calibrator(config)
        self.decision_engine = decision_engine or DecisionEngine()

        self.packet_buffer: Deque[np.ndarray] = deque(maxlen=config.window_size)
        self.entropy_history: Deque[float] = deque([0.0] * config.history_len, maxlen=config.history_len)
        self.doppler_history: Deque[float] = deque([0.0] * config.history_len, maxlen=config.history_len)

        self._animation: Optional[FuncAnimation] = None
        self._build_figure()

    # ------------------------------------------------------------------
    # Figure / artist setup
    # ------------------------------------------------------------------
    def _build_figure(self) -> None:
        plt.style.use("dark_background")
        self.fig, (self.ax_amplitude, self.ax_entropy, self.ax_doppler) = plt.subplots(3, 1, figsize=(10, 12))
        self.fig.canvas.manager.set_window_title("Invisible Eye: CSI Subspace Radar")

        n = self.config.num_subcarriers
        h = self.config.history_len

        (self.line_amplitude,) = self.ax_amplitude.plot(range(n), np.zeros(n), color="red", lw=1)
        self.ax_amplitude.set_ylim(*self.config.amplitude_ylim)
        self.ax_amplitude.set_title("CSI Amplitude (current packet)")
        self.ax_amplitude.set_xlabel("Subcarrier index")

        (self.line_entropy,) = self.ax_entropy.plot(range(h), [0] * h, color="cyan", lw=2)
        self.entropy_threshold_line = self.ax_entropy.axhline(
            y=self.calibrator.thresholds.entropy, color="red", linestyle="--", label="threshold"
        )
        self.ax_entropy.set_ylim(*self.config.entropy_ylim)
        self.ax_entropy.set_title("Spectral Entropy S (presence)")
        self.ax_entropy.legend(loc="upper right")

        (self.line_doppler,) = self.ax_doppler.plot(range(h), [0] * h, color="magenta", lw=2)
        self.doppler_threshold_line = self.ax_doppler.axhline(
            y=self.calibrator.thresholds.doppler, color="yellow", linestyle="--", label="threshold"
        )
        self.ax_doppler.set_ylim(*self.config.doppler_ylim)
        self.ax_doppler.set_title("Doppler Spread D (motion)")
        self.ax_doppler.legend(loc="upper right")

        self.status_text = self.fig.text(
            0.5, 0.01, "CALIBRATING: 0/{}".format(self.config.calibration_frames),
            ha="center", fontsize=13, color="white",
        )

        plt.tight_layout(rect=(0, 0.03, 1, 0.97))

    # ------------------------------------------------------------------
    # Frame update
    # ------------------------------------------------------------------
    def _update(self, _frame):
        self.reader.drop_stale_backlog()
        packet = self.reader.read_packet()
        if packet is None:
            return self.line_amplitude, self.line_entropy, self.line_doppler

        self.packet_buffer.append(packet)
        self.line_amplitude.set_ydata(np.abs(packet))

        if len(self.packet_buffer) < self.config.window_size:
            return self.line_amplitude, self.line_entropy, self.line_doppler

        h_matrix = csi_math.build_h_matrix(self.packet_buffer)
        _covariance, lambdas, s_value, d_value = csi_math.process_window(h_matrix)

        just_calibrated = self.calibrator.update(s_value, d_value)
        if just_calibrated:
            self.entropy_threshold_line.set_ydata(
                [self.calibrator.thresholds.entropy, self.calibrator.thresholds.entropy]
            )
            self.doppler_threshold_line.set_ydata(
                [self.calibrator.thresholds.doppler, self.calibrator.thresholds.doppler]
            )

        if not self.calibrator.is_calibrated:
            done, total = self.calibrator.progress
            self.status_text.set_text(f"CALIBRATING: {done}/{total}")
            self.status_text.set_color(_STATUS_COLORS[SystemState.CALIBRATING])
            return self.line_amplitude, self.line_entropy, self.line_doppler

        self.entropy_history.append(s_value)
        self.doppler_history.append(d_value)
        self.line_entropy.set_ydata(list(self.entropy_history))
        self.line_doppler.set_ydata(list(self.doppler_history))

        state = self.decision_engine.decide(s_value, d_value, self.calibrator.thresholds)
        self.status_text.set_text(state.value)
        self.status_text.set_color(_STATUS_COLORS[state])

        return self.line_amplitude, self.line_entropy, self.line_doppler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, interval_ms: int = 30) -> None:
        """Connect to the serial device and start the live animation loop."""
        if not self.reader.is_connected:
            self.reader.connect()

        self._animation = FuncAnimation(self.fig, self._update, interval=interval_ms, blit=False)
        plt.show()
