# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""resources.py - how many workers this machine can run, decided once from what it has.

A fixed worker count is wrong on both sides: four sampler processes ran a 15 GB laptop out of memory, and two left six cores
idle on a workstation. The numbers here come from the cores the process may use (affinity and container limits, not the
machine's total) and the memory it may take (what is free, and the container's cap), and every one can be set by an
environment variable. Nothing here knows a project or a piece.

    cores()              cores this process may run on
    available_gb()       memory this process may still take, in GB
    sfz_workers()        sampler subprocesses at once       MUSICGEN_SFZ_WORKERS
    stem_workers()       stems rendered at once            MUSICGEN_STEM_WORKERS
    gate_workers()       threads for the per-stem gate rows  GATE_WORKERS
    summary()            one line for the render report
    release_memory()     hand freed memory back to the system between renders
"""
import gc
import os

SFZ_WORKER_GB = 2.5        # starting value: one sfizz process with an orchestra patch set, measured as the cause of an out-of-memory at 4 on 15 GB
STEM_WORKER_GB = 0.5       # one stem render's working set: measured 0.43 GB per extra worker on projects/palace_chase
                           # (185 s stems, 31 tracks; 2.7 GB at one worker, 5.7 GB at eight), rounded up for headroom
HEADROOM_GB = 3.0          # left for the mixer, the gate and the system


def cores():
    try:
        n = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        n = os.cpu_count() or 1
    quota = _cgroup_cpus()
    return max(1, min(n, quota) if quota else n)


def _cgroup_cpus():
    try:
        with open('/sys/fs/cgroup/cpu.max', encoding='utf-8') as fh:
            q, p = fh.read().split()[:2]
        if q != 'max':
            return max(1, int(round(float(q) / float(p))))
    except (OSError, ValueError):
        pass
    return None


def _meminfo_gb(key='MemAvailable'):
    try:
        with open('/proc/meminfo', encoding='utf-8') as fh:
            for line in fh:
                if line.startswith(key + ':'):
                    return float(line.split()[1]) / 1048576.0
    except (OSError, ValueError, IndexError):
        pass
    return None


def _cgroup_limit_gb():
    for path in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        try:
            with open(path, encoding='utf-8') as fh:
                v = fh.read().strip()
            if v != 'max' and float(v) < 1 << 50:
                return float(v) / (1 << 30)
        except (OSError, ValueError):
            continue
    return None


def available_gb(meminfo=None, limit=None):
    """Free memory, capped by a container limit when there is one. `meminfo` and `limit` are injectable for tests."""
    free = _meminfo_gb() if meminfo is None else meminfo
    cap = _cgroup_limit_gb() if limit is None else limit
    if free is None:
        free = 8.0
    return min(free, cap) if cap else free


def _env_int(name):
    try:
        v = int(os.environ.get(name, ''))
        return v if v > 0 else None
    except ValueError:
        return None


def sfz_workers(n_jobs=None, n_cores=None, free_gb=None):
    """Sampler subprocesses to run at once: every core while memory allows, one per SFZ_WORKER_GB beyond the headroom."""
    forced = _env_int('MUSICGEN_SFZ_WORKERS')
    if forced:
        return forced if n_jobs is None else max(1, min(forced, n_jobs))
    c = cores() if n_cores is None else n_cores
    mem = available_gb() if free_gb is None else free_gb
    by_mem = int(max(0.0, mem - HEADROOM_GB) // SFZ_WORKER_GB)
    n = max(1, min(c, by_mem))
    return n if n_jobs is None else max(1, min(n, n_jobs))


def stem_workers(n_jobs=None, n_cores=None, free_gb=None):
    """Stems rendered at once: every core while memory allows, one per STEM_WORKER_GB beyond the headroom.

    Stems are independent (each has its own seed and its own sampler), so the count is bounded only by cores and
    memory. A render that asks for more workers than it has tracks gets one worker per track.
    """
    forced = _env_int('MUSICGEN_STEM_WORKERS')
    if forced:
        return forced if n_jobs is None else max(1, min(forced, n_jobs))
    c = cores() if n_cores is None else n_cores
    mem = available_gb() if free_gb is None else free_gb
    by_mem = int(max(0.0, mem - HEADROOM_GB) // STEM_WORKER_GB)
    n = max(1, min(c, by_mem))
    return n if n_jobs is None else max(1, min(n, n_jobs))


def gate_workers(n_cores=None):
    """Threads for the stem gate: most of the cores (numpy and scipy release the GIL), at least two, at most eight."""
    forced = _env_int('GATE_WORKERS')
    if forced:
        return forced
    c = cores() if n_cores is None else n_cores
    return max(2, min(8, c - 1 if c > 2 else c))


def summary():
    return (f'{cores()} core(s), {available_gb():.1f} GB free: {sfz_workers()} sampler worker(s), {gate_workers()} gate thread(s)')


def release_memory():
    """Give freed memory back to the operating system; returns the resident size in GB before and after, or None.

    numpy frees an array to the allocator, and glibc keeps what worker threads freed in per-thread arenas: after a
    mix that peaked at 12 GB the process still held most of it, and the next format's mix started on top and was
    killed by the container's limit. A collection plus `malloc_trim` returns the free pages. Only glibc has it, and
    nothing happens elsewhere."""
    def rss():
        try:
            with open('/proc/self/statm') as fh:
                return int(fh.read().split()[1]) * os.sysconf('SC_PAGE_SIZE') / 1e9
        except (OSError, ValueError, IndexError):
            return None
    before = rss()
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except (OSError, AttributeError):
        pass
    return before, rss()
