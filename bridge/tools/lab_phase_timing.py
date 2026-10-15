"""Opt-in diagnostics for a fresh lab run; never a GPU performance benchmark."""
from contextlib import contextmanager
from pathlib import Path
import datetime
import hashlib
import json
import os
import platform
import time


class PhaseLog:
    def __init__(self, path, tools):
        self.path = Path(path)
        assert self.path.parent.is_dir() and not self.path.exists()
        self.origin = time.perf_counter_ns()
        self.data = {
            'schema': 1, 'diagnostic_timings': True, 'performance_benchmark': False,
            'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'host': platform.node(), 'architecture': platform.machine(),
            'launcher_PID': os.getpid(), 'python': platform.python_version(),
            'tool_SHA256': {str(Path(p).resolve()): hashlib.sha256(
                Path(p).read_bytes()).hexdigest() for p in tools},
            'phases': [], 'status': 'running',
        }
        self.save()

    def save(self):
        # Only the fresh run's diagnostic log is updated; qualified evidence
        # and executable files are never touched by this helper.
        self.path.write_text(json.dumps(self.data, indent=2) + '\n')

    @contextmanager
    def phase(self, label, **metadata):
        begin = time.perf_counter_ns()
        entry = {'label': label, 'started_ns': begin - self.origin, **metadata}
        try:
            yield entry
        except BaseException as error:
            entry['status'] = 'error'
            entry['exception_type'] = type(error).__name__
            self.data['status'] = 'error'
            self.data['exception_type'] = type(error).__name__
            raise
        else:
            entry['status'] = 'observed'
        finally:
            end = time.perf_counter_ns()
            entry.update(ended_ns=end-self.origin, duration_ns=end-begin)
            self.data['phases'].append(entry)
            self.save()

    def finish(self, status, **metadata):
        if status == 'PASS':
            assert all(p['status'] != 'error' for p in self.data['phases']), \
                'A diagnostic phase error cannot be silently reported as PASS'
        self.data.update(status=status, elapsed_ns=time.perf_counter_ns()-self.origin,
                         completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         **metadata)
        self.save()
