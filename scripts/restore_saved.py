#!/usr/bin/env python3
"""Offline restore using an explicitly selected migration JSON; keeps external data."""
import argparse
import json
import os
from pathlib import Path

from migrate_saved import checkpoint, locations, state_lock
from safety import (
    absolute,
    inside,
    manifest,
    no_root,
    no_symlink_ancestors,
    require,
    require_closed,
)


def restore(record):
    no_root()
    require_closed()
    expected_src, state = locations()
    record = absolute(str(record))
    no_symlink_ancestors(record)
    require(record.parent == state and record.name.startswith('migration-') and record.suffix == '.json',
            'Record must be an explicit migration JSON directly in expected state directory')
    with state_lock(state):
        try:
            data = json.loads(record.read_text())
        except (OSError, ValueError) as error:
            raise SystemExit('Cannot read migration record: ' + str(error)) from error
        src, dst, backup = (absolute(data[k]) for k in ('source', 'external', 'backup'))
        volume, work = (absolute(data[k]) for k in ('volume', 'work'))
        require(src == expected_src, 'Source is not exact ~/Library/Client/Saved')
        require(backup.parent == state and backup.name.startswith('Saved-backup-'), 'Invalid backup path')
        require(inside(work, volume) and dst == work / 'Saved', 'Invalid external path')
        no_symlink_ancestors(src, include_leaf=False)
        no_symlink_ancestors(backup)
        no_symlink_ancestors(dst)  # Nonexistent offline paths are OK; existing symlink ancestors are not.
        require(data.get('phase') in ('backup-moved', 'linked-awaiting-game-test', 'restore-pending', 'link-held'),
                'Unexpected record phase; inspect manually')
        require(backup.is_dir(), 'Backup missing')
        require(manifest(backup) == data['manifest'], 'Backup SHA manifest mismatch; stop')
        require(backup.stat().st_dev == src.parent.stat().st_dev, 'Backup is not on source device')
        held = backup.with_name(backup.name + '-external-link')
        # Resume safely if interrupted after holding the link but before putting backup back.
        if os.path.lexists(src):
            require(src.is_symlink() and os.readlink(src) == str(dst), 'Current link differs from record')
            require(not os.path.lexists(held), 'Held-link destination already exists')
            data['phase'] = 'restore-pending'
            checkpoint(record, data)
            src.rename(held)
        else:
            require(data['phase'] in ('restore-pending', 'link-held') and held.is_symlink()
                    and os.readlink(held) == str(dst), 'Source absent without matching held link; inspect manually')
        data['phase'] = 'link-held'
        checkpoint(record, data)
        require_closed()
        require(not os.path.lexists(src), 'Source appeared; keep both copies and inspect manually')
        try:
            backup.rename(src)
        except Exception:
            if not os.path.lexists(src):
                held.rename(src)
                data['phase'] = 'linked-awaiting-game-test'
                checkpoint(record, data)
            raise
        data['phase'] = 'restored'
        checkpoint(record, data)
        print('Pre-migration local Saved restored. External Saved/test app NOT deleted.')
        print('Old external link retained at:', held)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path, help='Explicit absolute migration JSON path (never auto-select latest)')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()
    if not args.yes:
        require(input('Restores PRE-migration data, not newer external saves. Keeps external copy. Type YES: ') == 'YES', 'Cancelled')
    restore(args.record)
