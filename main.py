#!/usr/bin/env python3
"""
main.py
-------
Command-line entry point for the Invisible Eye CSI radar.

Usage:
    python main.py --port COM9 --baud 921600
    python main.py --port /dev/ttyUSB0          # Linux / macOS
    python main.py --port COM9 --window 50 --subcarriers 64

Run `python main.py --help` for the full list of options.
"""

from __future__ import annotations

import argparse
import logging
import sys

import serial

from invisible_eye import CSIReader, LiveDashboard, RadarConfig


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Invisible Eye: Wi-Fi CSI subspace-entropy human sensing radar."
    )
    parser.add_argument("--port", default="COM9", help="Serial port the CSI device is connected to (default: COM9)")
    parser.add_argument("--baud", type=int, default=921600, help="Serial baud rate (default: 921600)")
    parser.add_argument("--subcarriers", type=int, default=64, help="Number of OFDM subcarriers, N (default: 64)")
    parser.add_argument("--window", type=int, default=50, help="Sliding window size in packets, T (default: 50)")
    parser.add_argument(
        "--calibration-frames", type=int, default=50,
        help="Number of baseline frames used to learn alert thresholds (default: 50)",
    )
    parser.add_argument(
        "--std-multiplier", type=float, default=3.0,
        help="Threshold = mean + k * std of the calibration baseline (default: 3.0)",
    )
    parser.add_argument("--interval", type=int, default=30, help="Plot refresh interval in ms (default: 30)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> RadarConfig:
    return RadarConfig(
        serial_port=args.port,
        baud_rate=args.baud,
        num_subcarriers=args.subcarriers,
        window_size=args.window,
        calibration_frames=args.calibration_frames,
        calibration_std_multiplier=args.std_multiplier,
    )


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("invisible_eye.main")

    config = build_config(args)
    reader = CSIReader(config)

    try:
        reader.connect()
    except serial.SerialException as exc:
        logger.error("Could not open serial port %s: %s", config.serial_port, exc)
        logger.error("Check that the port name is correct and not in use by another program.")
        return 1

    dashboard = LiveDashboard(config, reader)

    try:
        logger.info("Starting live dashboard. Close the plot window or press Ctrl+C to stop.")
        dashboard.run(interval_ms=args.interval)
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    finally:
        reader.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
