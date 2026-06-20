"""
csi_math.py
-----------
Implements the mathematical framework described in "Invisible Eye:
Subspace Analysis of Wi-Fi CSI for Human Sensing":

  1. Sample covariance matrix of the CSI window:      C = (1/T) H^H H
  2. Eigen-decomposition of C:                          C = V Lambda V^H
  3. Spectral (Shannon) entropy of the normalized
     eigenvalue distribution:                           S = -sum(p_i * ln p_i)
  4. Doppler Spread / motion index as the mean squared
     distance between consecutive CSI vectors.

These are pure functions operating on NumPy arrays -- no I/O, no
plotting -- so they can be unit-tested and reused independently of the
live dashboard.
"""

from __future__ import annotations

from collections import deque
from typing import Deque

import numpy as np

# Smallest eigenvalue allowed before clipping, to avoid log(0) / div-by-0
# when the channel is (near) perfectly static.
_EPSILON = 1e-10


def build_h_matrix(packet_buffer: Deque[np.ndarray]) -> np.ndarray:
    """Stack a sliding window of CSI packet vectors into the H matrix.

    Args:
        packet_buffer: deque of complex CSI vectors, each of shape (N,).

    Returns:
        Complex array of shape (T, N), rows = time samples, columns = subcarriers.
    """
    return np.array(packet_buffer)


def compute_covariance(h_matrix: np.ndarray) -> np.ndarray:
    """Sample covariance matrix across subcarriers: C = (1/T) H^H H.

    Args:
        h_matrix: complex array of shape (T, N).

    Returns:
        Hermitian, positive semi-definite complex array of shape (N, N).
    """
    t_samples = h_matrix.shape[0]
    return np.dot(h_matrix.conj().T, h_matrix) / t_samples


def eigen_spectrum(covariance: np.ndarray) -> np.ndarray:
    """Eigenvalues of the (Hermitian) covariance matrix, sorted descending.

    Uses `eigvalsh`, which is the appropriate (and faster, more stable)
    solver for Hermitian/symmetric matrices such as a covariance matrix.

    Args:
        covariance: Hermitian array of shape (N, N).

    Returns:
        Real array of length N, eigenvalues sorted from largest to
        smallest and clipped to a small positive epsilon.
    """
    lambdas = np.sort(np.linalg.eigvalsh(covariance))[::-1]
    return np.maximum(lambdas, _EPSILON)


def spectral_entropy(lambdas: np.ndarray) -> float:
    """Shannon entropy of the normalized eigenvalue (power) distribution.

    p_i = lambda_i / sum(lambda)
    S = -sum(p_i * ln(p_i))

    Low S -> energy concentrated in one eigen-channel (static, ordered
    environment). High S -> energy spread across many eigen-channels
    (dynamic, disordered environment / human presence).
    """
    p = lambdas / np.sum(lambdas)
    return float(-np.sum(p * np.log(p + _EPSILON)))


def doppler_spread(h_matrix: np.ndarray) -> float:
    """Motion index: mean squared Euclidean distance between consecutive
    CSI vectors (rows) in the time window.

    Note this matches the live, frame-by-frame metric used in the
    original notebook ``mean(|h_t - h_{t+1}|^2)`` rather than the
    paper's normalized sum ``(1/(T-1)) * sum(|h_t - h_{t+1}|^2)`` --
    for a fixed window size T the two are proportional (off by a
    constant), so thresholds calibrated against this implementation
    remain valid. See AUDIT_REPORT.md for details.
    """
    diffs = np.diff(h_matrix, axis=0)
    return float(np.mean(np.abs(diffs) ** 2))


def process_window(h_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Convenience wrapper running the full pipeline on one CSI window.

    Returns:
        (covariance, eigenvalues, spectral_entropy, doppler_spread)
    """
    covariance = compute_covariance(h_matrix)
    lambdas = eigen_spectrum(covariance)
    s_value = spectral_entropy(lambdas)
    d_value = doppler_spread(h_matrix)
    return covariance, lambdas, s_value, d_value
