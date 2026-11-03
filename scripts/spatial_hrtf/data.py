"""Download and prepare the measured head data (FABIAN HRTF set, TU Berlin, CC BY 4.0, doi 10.14279/depositonce-5718.5).

    python -m spatial_hrtf.data          (from scripts/; setup_project.py runs this once)

Creates data/HRIRs/HRIRs_default_{44100,48000,96000}.mat from the download. Safe to run again: it does nothing when they exist.
Offline or blocked: the mixer falls back to the analytic spatial.py and says so; run this again when the network is back.
"""
import os

from . import io

HRIR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'HRIRs')


def ready(fs=44100):
    return os.path.exists(os.path.join(HRIR_DIR, f'HRIRs_default_{fs}.mat'))


def ensure():
    """True when the default HRIR files exist (downloading and building them when they do not)."""
    if all(ready(fs) for fs in (44100, 48000, 96000)):
        return True
    io.get_default_hrirs()
    return ready()


if __name__ == '__main__':
    print('HRTF data ready' if ensure() else 'HRTF data missing')
