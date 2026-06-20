"""
serial_interface.py
--------------------
Handles the low-level serial connection to the CSI-emitting device and
parses the ASCII "CSI_DATA[...]" lines it emits into complex-valued
NumPy vectors.

This isolates all I/O and string-parsing concerns away from the math
and the plotting code, and replaces the original notebook's bare
`except: pass` blocks with explicit, logged exception handling so
malformed packets are skipped without hiding real bugs.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import serial

from .config import RadarConfig

logger = logging.getLogger(__name__)


class CSIReader:
    """Reads and parses CSI packets from a serial device.

    Expected line format (as emitted by the firmware)::

        ... CSI_DATA ... [i0,q0,i1,q1,...,iN-1,qN-1] ...

    Each packet contains 2 * num_subcarriers integers, interleaved as
    (I, Q) pairs, which are combined into a complex amplitude/phase
    vector of length num_subcarriers.
    """

    def __init__(self, config: RadarConfig):
        self.config = config
        self._serial: Optional[serial.Serial] = None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> None:
        """Open the serial port. Raises serial.SerialException on failure."""
        self._serial = serial.Serial(
            self.config.serial_port,
            self.config.baud_rate,
            timeout=self.config.serial_timeout,
        )
        self._serial.reset_input_buffer()
        logger.info("Connected to %s @ %d baud", self.config.serial_port, self.config.baud_rate)

    def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
            logger.info("Serial port closed")

    def drop_stale_backlog(self) -> None:
        """Discard buffered bytes if the OS input buffer is growing too large.

        This keeps the live view close to real time instead of slowly
        rendering a backlog of old packets.
        """
        if self._serial and self._serial.in_waiting > self.config.max_input_backlog_bytes:
            self._serial.reset_input_buffer()

    def read_packet(self) -> Optional[np.ndarray]:
        """Read one line from the serial port and parse it into a complex vector.

        Returns:
            A complex-valued NumPy array of length ``num_subcarriers``,
            or ``None`` if no valid CSI packet was available this call.
        """
        if not self._serial or self._serial.in_waiting <= 0:
            return None

        try:
            raw_line = self._serial.readline().decode("utf-8", errors="ignore").strip()
        except (UnicodeDecodeError, OSError) as exc:
            logger.debug("Failed to read line from serial port: %s", exc)
            return None

        if "CSI_DATA" not in raw_line:
            return None

        return self._parse_csi_line(raw_line)

    def _parse_csi_line(self, raw_line: str) -> Optional[np.ndarray]:
        start, end = raw_line.find("["), raw_line.find("]")
        if start == -1 or end == -1 or end <= start:
            logger.debug("Malformed CSI line (no bracketed payload): %r", raw_line)
            return None

        try:
            raw_values = np.fromstring(raw_line[start + 1:end], sep=",", dtype=int)
        except ValueError as exc:
            logger.debug("Could not parse CSI payload as integers: %s", exc)
            return None

        expected_len = 2 * self.config.num_subcarriers
        if raw_values.size < expected_len:
            logger.debug(
                "CSI packet too short: got %d values, expected >= %d",
                raw_values.size, expected_len,
            )
            return None

        raw_values = raw_values[:expected_len]
        i_samples = raw_values[0::2]
        q_samples = raw_values[1::2]
        return i_samples + 1j * q_samples
