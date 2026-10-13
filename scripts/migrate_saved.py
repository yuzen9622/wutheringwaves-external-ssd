#!/usr/bin/env python3
"""Copy/verify first, checkpoint, then move the original and link. Never delete data."""
import argparse
import datetime
import json
import os
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

from safety import (
    config,
    manifest,
    no_root,
    no_symlink_ancestors,
    require,
    require_closed,
)


def locations():
    home = Path.home()
    return home / 'Library/Client/Saved', home / '.local/state/wuthering-external-test'


@contextmanager
def state_lock(state):
    no_symlink_ancestors(state)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = state / '.operation-lock'
    lock.mkdir()  # Exclusive; stale lock after interruption requires manual inspection.
    try:
        yield
    finally:
        lock.rmdir()


def checkpoint(record, data):
    temp = record.with_name(record.name + '.tmp')
    with temp.open('x') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, record)


def migrate():
    no_root()
    volume, _, work, _ = config()
    require_closed()
    src, state = locations()
    dst = work / 'Saved'
    no_symlink_ancestors(src)
    require(src.is_dir(), 'Saved missing or is a link')
    require(work.is_dir(), 'Work directory missing')
    require(not os.path.lexists(dst), 'External Saved already exists; never overwrite')
    with state_lock(state):
        # All device checks happen BEFORE moving the only local original.
        require(src.stat().st_dev == state.stat().st_dev, 'Backup must be on original device')
        require(src.stat().st_dev != work.stat().st_dev, 'External must be a different device')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
        backup = state / ('Saved-backup-' + stamp)
        record = state / ('migration-' + stamp + '.json')
        require(not os.path.lexists(backup) and not os.path.lexists(record), 'Backup/record collision')
        before = manifest(src)
        data = {'source': str(src), 'external': str(dst), 'backup': str(backup),
                'volume': str(volume), 'work': str(work), 'manifest': before, 'phase': 'copy-pending'}
        with record.open('x') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        print('Recovery record:', record, flush=True)
        dst.mkdir()  # Reserve exclusively; ditto merges only into this newly reserved directory.
        subprocess.run(['/usr/bin/ditto', str(src), str(dst)], check=True)
        require(before == manifest(dst) == manifest(src), 'SHA manifest mismatch; original stays put')
        require_closed()
        no_symlink_ancestors(src)
        no_symlink_ancestors(backup)
        require(not os.path.lexists(backup), 'Backup appeared; stop')
        require(src.stat().st_dev == state.stat().st_dev, 'Backup device changed')
        require(src.stat().st_dev != dst.stat().st_dev, 'External device mismatch')
        data['phase'] = 'verified-copy'
        checkpoint(record, data)
        src.rename(backup)
        data['phase'] = 'backup-moved'
        checkpoint(record, data)
        try:
            src.symlink_to(dst, target_is_directory=True)
        except Exception:
            require(not os.path.lexists(src), 'Source appeared; keep backup, inspect record manually')
            backup.rename(src)
            data['phase'] = 'link-failed-original-restored'
            checkpoint(record, data)
            raise
        require(manifest(dst) == before and src.resolve() == dst.resolve(), 'Post-link verification failed')
        data['phase'] = 'linked-awaiting-game-test'
        checkpoint(record, data)
        print('Link:', src, '->', dst)
        print('Local original retained:', backup)
        print('Not yet verified in game.')


def confirmation(args):
    require(args.ack_client_saved, 'Required: --ack-client-saved (you verified generic Client/Saved belongs to this game)')
    if not args.yes:
        require(input('Moves ~/Library/Client/Saved. You confirmed it belongs to the TEST game. Type YES: ') == 'YES', 'Cancelled')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true')
    parser.add_argument('--ack-client-saved', action='store_true')
    arguments = parser.parse_args()
    confirmation(arguments)
    migrate()
