"""
config.py
---------
Central configuration for the Invisible Eye CSI sensing system.

All "magic numbers" that were hardcoded throughout the original notebook
(serial port, baud rate, matrix dimensions, thresholds, history lengths)
live here as a single dataclass so they can be changed in one place or
overridden from the command line (see main.py).
"""

from dataclasses import dataclass


@dataclass
class RadarConfig:
    # --- Serial link to the CSI-emitting device (e.g. an ESP32 CSI firmware) ---
    serial_port: str = "COM9"
    baud_rate: int = 921600
    serial_timeout: float = 0.01  # seconds

    # --- CSI matrix dimensions ---
    num_subcarriers: int = 64   # N: number of OFDM subcarriers per packet
    window_size: int = 50       # T: number of packets kept in the sliding window

    # --- History buffers for the live plots ---
    history_len: int = 100

    # --- Calibration ---
    calibration_frames: int = 50   # number of stable frames used to learn thresholds
    calibration_std_multiplier: float = 3.0  # mean + k * std

    # --- Fallback thresholds, used only until calibration completes ---
    default_entropy_threshold: float = 0.5
    default_doppler_threshold: float = 50.0

    # --- Plot axis limits (cosmetic, safe to tune per environment) ---
    amplitude_ylim: tuple = (0, 150)
    entropy_ylim: tuple = (0, 4)
    doppler_ylim: tuple = (0, 500)

    # --- Serial buffer overflow guard ---
    # If more than this many bytes pile up in the OS input buffer, the
    # reader drops them to avoid rendering a stale, lagging signal.
    max_input_backlog_bytes: int = 2000
