# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""compute.py - where the heavy array work runs: the CPU always, a GPU when one is present.

One decision, made once per process and written into the render report:

    request  "auto" | "cpu" | "cuda" | "mps"      mix preset `render.compute.device`, or the MUSICGEN_DEVICE variable
    backend  "numpy" (SciPy's FFT, every core)  |  "torch" (CUDA or Apple MPS)

"auto" takes a GPU only when torch is installed and reports one. Asking for a device by name that is not there is not
an error: the work runs on the CPU and `info()['fallback']` says why, so a render made on a laptop and one made on a
workstation differ only in the report line and in the last bits of the samples.

What runs here is the work that is the same arithmetic on either device: FFT convolution (reverb returns, air
absorption, head filters) and matrix products (ambisonic encode and decode). Recursive filters, the limiter, the
SoundFont and the Pedalboard plugins are sequential by nature and stay on the CPU.

A GPU result is not bit-identical to a CPU one (float32 and a different FFT), so the gate certifies whichever render
was made and tests/test_immersive_v3.py bounds the difference between the two kernels. On the CPU, `conv` and `oaconv`
call SciPy exactly as the engine always has: a CPU render does not depend on this module. Stems are rendered before
this stage and are the same on every device; `cache_tag()` is for a cache of anything computed here.

Nothing here is tuned for a project: there are no acoustic numbers in this file.
"""
import os

import numpy as np

REQUESTS = ('auto', 'cpu', 'cuda', 'mps')
ENV = 'MUSICGEN_DEVICE'
WORKERS_ENV = 'MUSICGEN_FFT_WORKERS'

_state = None            # the resolved decision: dict(request, backend, device, name, fallback, workers)
_requested = None        # what a preset asked for, before the environment variable is looked at


def configure(request=None, workers=None):
    """Set what the mix preset asks for (`render.compute`). Resets the decision so the next call resolves again."""
    global _requested, _state
    _requested = dict(device=str(request).lower() if request else None, workers=workers)
    _state = None
    return info()


def _torch():
    try:
        import torch
        return torch
    except Exception:           # not installed, or installed and broken: either way the CPU path is the path
        return None


def _resolve():
    asked = (os.environ.get(ENV) or (_requested or {}).get('device') or 'auto').lower()
    fallback = None
    if asked not in REQUESTS:
        fallback = f'unknown device "{asked}" (known: {", ".join(REQUESTS)}); using the CPU'
        asked = 'cpu'
    workers = os.environ.get(WORKERS_ENV) or (_requested or {}).get('workers')
    try:
        workers = int(workers) if workers not in (None, '', 'auto') else -1
    except (TypeError, ValueError):
        workers = -1
    out = dict(request=asked, backend='numpy', device='cpu', name='cpu', fallback=fallback, workers=workers)
    if asked == 'cpu':
        return out
    torch = _torch()
    if torch is None:
        if asked != 'auto':
            out['fallback'] = f'"{asked}" was asked for but torch is not installed; using the CPU'
        return out
    have = {'cuda': bool(torch.cuda.is_available()),
            'mps': bool(getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available())}
    pick = next((d for d in ('cuda', 'mps') if have[d]), None) if asked == 'auto' else (asked if have[asked] else None)
    if pick is None:
        if asked != 'auto':
            out['fallback'] = f'"{asked}" was asked for but this machine has no such device; using the CPU'
        return out
    name = torch.cuda.get_device_name(0) if pick == 'cuda' else 'Apple MPS'
    out.update(backend='torch', device=pick, name=name)
    return out


def info():
    """The decision as a dict (a copy): request, backend, device, name, fallback, workers."""
    global _state
    if _state is None:
        _state = _resolve()
    return dict(_state)


def device():
    return info()['device']


def on_gpu():
    return info()['backend'] == 'torch'


def cache_tag():
    """What a cache key carries so a CPU stem is never served to a GPU render or the other way round."""
    i = info()
    return 'cpu' if i['backend'] == 'numpy' else f'{i["device"]}-f32'


def describe():
    i = info()
    line = f'compute: {i["name"]} ({i["backend"]})'
    if i['fallback']:
        line += f' - {i["fallback"]}'
    return line


def _fail_over(exc):
    """A GPU kernel failed (out of memory, an operator the device lacks): finish on the CPU and say so once."""
    global _state
    _state = dict(info(), backend='numpy', device='cpu', name='cpu',
                  fallback=f'the GPU path failed ({type(exc).__name__}: {str(exc)[:120]}); finished on the CPU')
    import sys
    sys.stderr.write(f'[compute] {_state["fallback"]}\n')


def _torch_conv(xx, hh, n, dev):
    """The GPU kernel: (N, C) with (M, 1 or C) -> the first n samples of the full convolution, float32. `dev` may be
    "cpu", which is how the arithmetic is tested on a machine with no GPU."""
    torch = _torch()
    dev = torch.device(dev)
    size = 1 << int(np.ceil(np.log2(max(n, 2))))
    X = torch.fft.rfft(torch.as_tensor(np.ascontiguousarray(xx.T), dtype=torch.float32, device=dev), n=size)
    H = torch.fft.rfft(torch.as_tensor(np.ascontiguousarray(hh.T), dtype=torch.float32, device=dev), n=size)
    return torch.fft.irfft(X * H, n=size)[:, :n].T.cpu().numpy()


def fftconvolve(x, h, mode='full'):
    """x convolved with h along axis 0. x is (N,) or (N, C); h is (M,) or (M, C) (one kernel per channel, or one
    kernel for all). Returns the dtype of x. `mode` is 'full' or 'same' (the first N samples of the full result,
    which is what a causal filter means here, not SciPy's centred 'same')."""
    if mode not in ('full', 'same'):
        raise ValueError("mode must be 'full' or 'same'")
    x = np.asarray(x)
    h = np.asarray(h)
    one_d = x.ndim == 1
    xx = x[:, None] if one_d else x
    hh = h[:, None] if h.ndim == 1 else h
    if hh.shape[1] not in (1, xx.shape[1]):
        raise ValueError(f'kernel has {hh.shape[1]} channels, the signal {xx.shape[1]}')
    n = len(xx) + len(hh) - 1
    y = None
    if on_gpu():
        try:
            y = _torch_conv(xx, hh, n, device())
        except Exception as exc:
            _fail_over(exc)
    if y is None:
        from scipy import fft as sfft
        size = sfft.next_fast_len(n, real=True)
        w = info()['workers']
        X = sfft.rfft(xx, size, axis=0, workers=w)
        H = sfft.rfft(hh, size, axis=0, workers=w)
        y = sfft.irfft(X * H, size, axis=0, workers=w)[:n]
    if mode == 'same':
        y = y[:len(xx)]
    y = y.astype(x.dtype if np.issubdtype(x.dtype, np.floating) else np.float64, copy=False)
    return y[:, 0] if one_d else y


def conv(x, h):
    """A one-dimensional full convolution: SciPy's own on the CPU (so a CPU render is bit-for-bit what it was before
    this module existed), the GPU kernel when there is one."""
    if on_gpu():
        return fftconvolve(np.asarray(x), np.asarray(h))
    from scipy import signal
    return signal.fftconvolve(x, h)


def oaconv(x, h):
    """As conv, for a long signal and a short kernel (overlap-add on the CPU; one FFT on a GPU, which has the memory)."""
    if on_gpu():
        return fftconvolve(np.asarray(x), np.asarray(h))
    from scipy import signal
    return signal.oaconvolve(x, h)


def matmul(a, b):
    """a @ b. On a GPU for large products, otherwise NumPy (which already uses every core through BLAS)."""
    a = np.asarray(a)
    b = np.asarray(b)
    if on_gpu() and a.size * b.shape[-1] >= (1 << 22):
        try:
            torch = _torch()
            dev = torch.device(device())
            y = torch.as_tensor(a, dtype=torch.float32, device=dev) @ torch.as_tensor(b, dtype=torch.float32, device=dev)
            return y.cpu().numpy().astype(np.result_type(a, b), copy=False)
        except Exception as exc:
            _fail_over(exc)
    return a @ b


if __name__ == '__main__':
    print(describe())
    for k, v in info().items():
        print(f'  {k}: {v}')
