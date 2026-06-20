# Audit Report — CSI_NOTEBOOK.ipynb → `invisible_eye` package

This document records what the original notebook contained, what issues
were found during the refactor, and how each was addressed. It is meant
as an engineering changelog, not a judgment of the original exploratory
work — notebooks like this are normal and useful for prototyping on a
lab bench; this audit exists to make the logic safe to package, reuse,
and extend.

## 1. Summary of the original notebook

`CSI_NOTEBOOK.ipynb` contained 8 cells, each runnable independently in
Jupyter with `%matplotlib qt`:

| Cell | Purpose |
|------|---------|
| 0 | Connects to serial, builds a sliding `H` matrix, plots raw amplitude + H-matrix heatmap |
| 1 | Helper function to plot an H matrix (unused by other cells) |
| 2 | Live covariance matrix `C = Hᴴ H / T` heatmap (depends on global `H` from cell 0) |
| 3 | Live eigenvalue bar chart from `C` (depends on global `C` from cell 2) |
| 4 | "Radar Decision Console": calibration + entropy/Doppler thresholding (depends on globals `H`, `lambdas` from earlier cells) |
| 5 | A second, self-contained "all-in-one" version using a blocking `while True` loop instead of `FuncAnimation` |
| 6 | A third, self-contained "all-in-one" version using `FuncAnimation`, labeled "Super-Fast Dashboard" |
| 7 | Empty |

Cells 0/2/3/4 only work together, in order, in the same Jupyter kernel
(they share state through notebook globals `H`, `C`, `lambdas`). Cells 5
and 6 each independently re-implement the entire pipeline (serial read →
H matrix → covariance → eigenvalues → entropy → Doppler) from scratch,
with cell 6 additionally re-implementing the live plotting from cells 0
and 2/3 but **without** cell 4's calibration/decision logic.

## 2. Issues identified

### 2.1 Logic duplication and drift
The core math (`build H`, `C = Hᴴ H / T`, `eigvalsh`, Shannon entropy,
Doppler spread) was copy-pasted across cells 4, 5, and 6 with minor,
unintentional differences (e.g. cell 6's "final" dashboard drops the
calibration/decision/status logic that cell 4 had built). Any bug fix or
tuning change would need to be applied in three places by hand.

**Fix:** the math now lives once, in `csi_math.py`, and the
calibration/decision logic lives once each in `calibration.py` /
`decision_engine.py`. `dashboard.py` is the single live-view
implementation and is the only place plotting code exists.

### 2.2 Notebook global-variable coupling
Cells 2, 3, and 4 read `H`, `C`, and `lambdas` from the notebook's global
namespace (`if 'H' in globals(): ...`), set by other cells. Running them
out of order, or restarting the kernel, silently breaks the pipeline with
no error.

**Fix:** state (`packet_buffer`, `entropy_history`, `doppler_history`,
calibration progress) is held as instance attributes on `LiveDashboard`,
`Calibrator`, and `CSIReader`, with explicit data flow through function
arguments and return values — no implicit globals.

### 2.3 Bare `except: pass` clauses
Cells 0, 5, and 6 all used bare `except:` (or `except: pass`) around
serial reads and packet parsing. This silently swallows *any* exception,
including bugs unrelated to malformed packets (e.g. a typo would also be
silently ignored).

**Fix:** `serial_interface.py` only catches the specific exceptions that
can legitimately occur while parsing an external data stream
(`UnicodeDecodeError`, `OSError`, `ValueError`), logs them at `DEBUG`
level, and lets anything else propagate normally.

### 2.4 Hardcoded hardware configuration
`SERIAL_PORT = 'COM9'` and `BAUD_RATE = 921600` were hardcoded at the top
of five different cells. Anyone using a different port (or running on
Linux/macOS, where `COM9` doesn't exist) had to find and edit every
occurrence.

**Fix:** all tunables live in one `RadarConfig` dataclass
(`config.py`), with CLI overrides in `main.py` (`--port`, `--baud`,
`--subcarriers`, `--window`, etc.).

### 2.5 No error handling around the serial connection
If `serial.Serial(...)` failed (wrong port, port already in use), the
original notebook printed an Arabic-language error string and then
**continued executing**, leaving `ser` undefined and causing a confusing
`NameError` later inside the animation callback.

**Fix:** `main.py` explicitly catches `serial.SerialException` at
startup, logs a clear actionable message, and exits with a non-zero
status code instead of continuing into a broken animation loop.

### 2.6 Mixed-language comments
Comments alternated between Arabic and English (e.g. `# --- الإعدادات
---`, `# حساب S و D`). This is fine for a personal notebook but is a
barrier for open-source collaboration.

**Fix:** all comments and docstrings in the package are in English. (No
functionality changed — this is a readability-only fix.)

### 2.7 Three different "live loop" strategies
Cell 0/2/3/4 used `matplotlib.animation.FuncAnimation`. Cell 5 used a
manual `while True: ... fig.canvas.draw(); plt.pause(0.001)` loop, which
is harder to interrupt cleanly and busy-waits on the CPU. Cell 6 went
back to `FuncAnimation`.

**Fix:** standardized on `FuncAnimation` (`dashboard.py`), matching the
better-performing approach used in cells 0/2/3/4/6, with a single,
documented update callback.

### 2.8 Decision logic missing from the "final" dashboard
The most polished, fastest dashboard (cell 6, "Super-Fast Dashboard")
plots raw amplitude, entropy, and Doppler — but never actually computes
calibrated thresholds or reports a `PERSON DETECTED` / `MOTION DETECTED`
status. That logic only existed in the earlier, separate cell 4.

**Fix:** `LiveDashboard` merges cell 6's plotting performance
improvements (backlog-dropping, single combined figure) with cell 4's
calibration and decision console, so the shipped dashboard both looks
right *and* makes a decision.

### 2.9 Backlog-dropping only in one branch
Cell 6 added `if ser.in_waiting > 2000: ser.reset_input_buffer()` to
avoid rendering a stale backlog, but cells 0/5 did not have this guard.

**Fix:** centralized in `CSIReader.drop_stale_backlog()` and called once
per frame from `dashboard.py`, configurable via
`RadarConfig.max_input_backlog_bytes`.

### 2.10 No package/CLI structure
The notebook could only be run cell-by-cell inside Jupyter with a GUI
backend (`%matplotlib qt`); it could not be imported, unit-tested, or
invoked from a script or CI pipeline.

**Fix:** restructured into an installable package (`invisible_eye/`)
with a `main.py` CLI entry point and `argparse`-based configuration. The
math functions in `csi_math.py` are pure and have no I/O or plotting
dependency, so they can be unit-tested or reused for offline analysis
(see verification below).

## 3. Known behavioral note (not a bug, documented for transparency)

The paper defines Doppler Spread as:

```
D = (1 / (T - 1)) * sum_{t=1}^{T-1} |h_t - h_{t+1}|^2
```

The original notebook instead computes:

```python
D = np.mean(np.abs(np.diff(H, axis=0))**2)
```

For a fixed window size `T`, `np.mean` over `(T-1)` row-wise differences
is identical to the paper's normalized sum — both divide by the same
`(T-1)` count, just spelled differently (`mean` vs `sum / (T-1)`).
**These two formulations are equivalent**, so this is a documentation
note rather than a functional discrepancy. It's recorded here, and in a
comment in `csi_math.doppler_spread`, so a future contributor comparing
the code against the paper isn't confused.

## 4. Verification performed during refactor

Because no physical CSI hardware was available in this environment, the
refactor was verified with synthetic data rather than a live device:

- **Syntax check** — every module parses cleanly (`ast.parse`).
- **Pipeline smoke test** — `build_h_matrix` → `process_window`
  (covariance → eigen-decomposition → entropy → Doppler) was run on:
  - a synthetic "static" window (small random jitter around a fixed
    base vector), and
  - a synthetic "dynamic" window (independent random vectors per
    packet),

  confirming the dynamic case produces materially higher Spectral
  Entropy and Doppler Spread than the static case, and that
  `DecisionEngine` correctly classifies the static baseline as `EMPTY`
  and the dynamic case as `MOTION DETECTED` once calibrated against the
  static baseline.
- **CLI behavior** — `main.py --help` prints correctly, and pointing
  `--port` at a non-existent device fails fast with a clear error
  message and exit code `1`, instead of crashing later inside the
  animation loop.
- **Dashboard construction** — `LiveDashboard` builds its figure and all
  three subplot axes correctly under a headless (`Agg`) Matplotlib
  backend, without requiring a real serial connection.

**Not verified (requires physical hardware):** end-to-end behavior
against a real ESP32 CSI stream, the exact `CSI_DATA[...]` line format
emitted by your specific firmware, and real-world calibration threshold
quality in an actual room. Validate these against your device before
relying on the alerting for anything safety-critical.

## 5. Files added

```
main.py
requirements.txt
invisible_eye/__init__.py
invisible_eye/config.py
invisible_eye/serial_interface.py
invisible_eye/csi_math.py
invisible_eye/calibration.py
invisible_eye/decision_engine.py
invisible_eye/dashboard.py
README.md
AUDIT_REPORT.md (this file)
```
