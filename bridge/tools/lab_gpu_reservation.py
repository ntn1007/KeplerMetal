"""Cooperative host reservation for KeplerMetal runners, with inherited lock FD.

This reserves lab launches, not WindowServer or every user of the hardware.
An unresolved/kill-requested session stays blocked; a state file is not proof
that a process is terminal. No process is killed or resumed by this module.
"""
from pathlib import Path
import datetime
import fcntl
import json
import os
import subprocess
import uuid


class ReservationBusy(RuntimeError):
    pass


def process_table():
    result = subprocess.run(['ps', '-axo', 'pid=,lstart=,command='],
                            capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise ReservationBusy('Cannot establish current process identities')
    rows = {}
    for line in result.stdout.splitlines():
        fields = line.split(None, 6)
        if len(fields) != 7 or not fields[0].isdigit():
            raise ReservationBusy('Unexpected ps identity format; inspect before launching')
        rows[int(fields[0])] = {'start': ' '.join(fields[1:6]), 'command': fields[6]}
    return rows


class GPUReservation:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.folder = self.root / 'results'
        assert self.folder.is_dir()
        self.state_path = self.folder / 'kepler-gpu-reservation.json'
        self.fd = os.open(self.folder / 'kepler-gpu-reservation.lock',
                          os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            self.fd = None
            raise ReservationBusy('Another lab process holds the GPU reservation')
        try:
            previous = json.loads(self.state_path.read_text()) if self.state_path.exists() else None
            if previous and previous.get('state') == 'unresolved':
                raise ReservationBusy('Earlier session unresolved; terminal/session evidence required')
            table = process_table()
            paths = set()
            registry = self.folder / 'signed-native-jobs.json'
            if registry.exists():
                for job in json.loads(registry.read_text()):
                    paths.add(job['signed_executable'])
            if previous:
                if previous.get('signed_executable'):
                    paths.add(previous['signed_executable'])
                owner = table.get(previous['owner_PID'])
                if previous.get('state') != 'terminal' and owner and owner['start'] == previous['owner_start']:
                    raise ReservationBusy('Earlier owner still live despite a free lock; inspect session')
                if previous.get('state') in ('running', 'spawning'):
                    raise ReservationBusy('Earlier launcher outcome unattested; session evidence required')
            live = [{'pid': pid, **row} for pid, row in table.items()
                    if any(row['command'] == p or row['command'].startswith(p + ' ') for p in paths)]
            if live:
                raise ReservationBusy('Known signed lab executable still present: ' + json.dumps(live))
            owner = table.get(os.getpid())
            if not owner:
                raise ReservationBusy('Cannot establish launcher birth identity')
            self.data = {
                'schema': 1, 'reservation_id': uuid.uuid4().hex, 'state': 'reserved',
                'owner_PID': os.getpid(), 'owner_start': owner['start'],
                'known_signed_processes_live': [], 'bootstrap_process_table_checked': True,
                'legacy_registry_entries': len(json.loads(registry.read_text())) if registry.exists() else 0,
                'known_signed_executable_paths': len(paths),
                'lock_inherited_by_child': True,
                'scope': 'Cooperative lab runners; not exclusive hardware access',
            }
            self.save()
        except BaseException:
            self.close()
            raise

    def save(self):
        self.data['observed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        temporary = self.state_path.with_name(self.state_path.name + '.' + self.data['reservation_id'])
        with temporary.open('x') as stream:
            json.dump(self.data, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, self.state_path)

    def spawning(self, signed_executable, signed_sha256):
        self.data.update(state='spawning', signed_executable=str(signed_executable),
                         signed_binary_sha256=signed_sha256)
        self.save()

    def bind_child(self, pid):
        row = process_table().get(pid)
        self.data.update(state='running', child_PID=pid,
                         child_start=row['start'] if row else None,
                         child_birth_observed=row is not None)
        self.save()

    def finish(self, exit_code, kill_requested, ps_status):
        assert self.fd is not None, 'Finish must retain the reservation until outcome is saved'
        terminal = exit_code is not None and not kill_requested and not ps_status
        self.data.update(state='terminal' if terminal else 'unresolved',
                         exit_code=exit_code, SIGKILL_requested=kill_requested,
                         authoritative_ps_status=ps_status)
        self.save()

    def close(self):
        if self.fd is not None:
            # Do not LOCK_UN: the child inherits the same open file description.
            # Closing only our FD keeps a live child's reservation after parent exit.
            os.close(self.fd)
            self.fd = None
