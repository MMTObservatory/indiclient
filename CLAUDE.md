# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**indiclient** is a Python package providing a Pythonic interface to the INDI (Instrument Neutral Distributed Interface) protocol for astronomical observatory control. It is used at MMTO (Multiple Mirror Telescope Observatory) and SAAO (South African Astronomical Observatory).

## Common Commands

```bash
# Install in development mode
pip install -e .[test]       # With test dependencies
pip install -e .[docs]       # With documentation dependencies

# Run tests (requires a running INDI server at localhost:7624)
pytest indiclient/tests

# Run via tox (starts Docker INDI server container automatically)
tox -e py313-test-cov

# Run a single test
pytest indiclient/tests/test_ccdcam.py::test_ccdtemp

# Code style check (max line length 135)
flake8 indiclient --count --max-line-length=135

# Build documentation
tox -e build_docs
```

## Architecture

The codebase is organized as a layered stack from raw protocol to instrument-specific APIs:

```
bigindiclient          # Low-level: TCP socket, XML parser, background thread, event queue
    └── indiclient     # Mid-level: convenience methods (get_float, set_and_send_bool, etc.)
        └── CCDCam     # High-level: generic CCD camera (temperature, cooling, exposure, filters)
            ├── ASICam         # ZWO ASI cameras (localhost:7624, adds gain control)
            ├── RATCam         # SBIG ST-I at ratcam.mmto.arizona.edu
            ├── MATCam         # MatCam at matcam.mmto.arizona.edu (has filter wheel)
            ├── F9WFSCam       # F/9 WFS SBIG at f9indi.mmto.arizona.edu
            └── SimCam         # INDI simulator
```

### Key Modules

- **indiclient/indiclient.py**: Core INDI protocol implementation (~2668 lines). `bigindiclient` handles the raw TCP/XML/threading layer; `indiclient` wraps it with typed property access methods. The INDI data model is `Device → Vector (named group) → Element (typed value: Text/Number/Switch/BLOB/Light)`.

- **indiclient/indicam.py**: Camera-specific wrappers. `CCDCam` exposes Python properties (`cam.temperature`, `cam.filters`, `cam.binning`, etc.) that internally call `get_float()`/`set_and_send_float()`. Exposures return `astropy.io.fits.HDUList` objects. Subclasses override defaults (host, port, supported features) and add instrument-specific properties.

- **indiclient/tests/test_ccdcam.py**: Integration tests. These test against a live INDI simulator, so they need either the Docker container (via tox) or a running INDI server.

### Event Model

The INDI client is event-driven and threaded:
1. A background receiver thread continuously reads from the TCP socket into `receive_event_queue`.
2. The user calls `process_events()` to dispatch queued messages to registered handlers.
3. Handlers can be custom callables or blocking operations for synchronous value retrieval.

### INDI Protocol Basics

INDI communicates via XML over TCP. Properties have three components: device name, vector name, and element name (e.g., `"CCD Simulator"` / `"CCD_TEMPERATURE"` / `"CCD_TEMPERATURE_VALUE"`). The protocol uses `getProperties`, `defXXXVector`, `setXXXVector`, and `newXXXVector` message types.

## Code Style

- Max line length: **135** characters (not the usual 79 or 88)
- Python 3.11+ required
- `astropy` is used throughout for FITS I/O and physical units

## Testing Notes

Tests in `test_ccdcam.py` connect to a real (or simulated) INDI server. Running `tox` handles the Docker INDI server setup automatically via `mmtobservatory/indilib_server:latest`. Direct `pytest` runs need the server already running on `localhost:7624`.
