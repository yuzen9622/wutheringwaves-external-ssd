#!/usr/bin/env python3
"""Small fail-closed guards shared by the standalone macOS wrappers."""
import hashlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path

GAME_PATTERN = '/Contents/MacOS/Client-Mac-Shipping'
BUNDLE_ID = 'com.kurogame.wutheringwaves.global'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def no_root():
    require(os.geteuid() != 0 and not os.environ.get('SUDO_USER'), 'Do not use root/sudo')


def no_symlink_ancestors(path, include_leaf=True):
    parts = [path, *path.parents] if include_leaf else list(path.parents)
    require(all(not p.is_symlink() for p in parts), 'Symlink path/ancestor rejected: ' + str(path))


def absolute(value):
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts, 'Required absolute path without ..: ' + value)
    return p


def inside(path, parent):
    return path != parent and parent in path.parents


def existing_parent(path):
    while not path.exists():
        path = path.parent
    return path


def require_closed():
    r = subprocess.run(['pgrep', '-f', GAME_PATTERN], capture_output=True, check=False)
    require(r.returncode == 1, 'Game running (pgrep=0), or process check failed (pgrep!=1); stop')


def config():
    no_root()
    require(sys.platform == 'darwin', 'macOS required')
    values = []
    for key in ('VOLUME', 'ORIGINAL', 'WORK', 'TEST_APP'):
        require(bool(os.environ.get(key)), 'Missing config: ' + key)
        p = absolute(os.environ[key])
        no_symlink_ancestors(p)
        values.append(p)
    volume, original, work, app = values
    require(os.path.ismount(volume), 'Selected drive is not mounted')
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(volume)]))
    require(info.get('MountPoint') == str(volume), 'diskutil mount point mismatch')
    require(str(info.get('FilesystemType', '')).lower() == 'apfs', 'Actual APFS volume required')
    require(inside(original.resolve(), volume.resolve()) and inside(work.resolve(), volume.resolve()),
            'Original/work must resolve inside selected volume')
    require(inside(app.resolve(), work.resolve()), 'Test app must be inside work')
    require(not inside(work.resolve(), original.resolve()) and not inside(original.resolve(), work.resolve())
            and work.resolve() != original.resolve(), 'Work and original must be separate')
    require(original.is_dir(), 'Original app missing')
    with (original / 'Contents/Info.plist').open('rb') as f:
        require(plistlib.load(f).get('CFBundleIdentifier') == BUNDLE_ID, 'Wrong original bundle ID')
    dev = volume.stat().st_dev
    require(all(existing_parent(p).stat().st_dev == dev for p in (original, work, app)),
            'Clone paths must be on the same APFS volume')
    return volume, original, work, app


def manifest(root):
    require(root.is_dir() and not root.is_symlink(), 'Manifest root must be a real directory')
    result = {}

    def walk(parent):
        for p in sorted(parent.iterdir()):
            key = str(p.relative_to(root))
            require(not p.is_symlink(), 'Symlink in Saved: ' + key)
            if p.is_dir():
                result[key] = ['dir']
                walk(p)
            elif p.is_file():
                h = hashlib.sha256()
                with p.open('rb') as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b''):
                        h.update(chunk)
                result[key] = ['file', p.stat().st_size, h.hexdigest()]
            else:
                require(False, 'Unsupported file type: ' + key)
    walk(root)
    return result


def check_pid(pid, app):
    require(pid.isascii() and pid.isdigit() and int(pid) > 0, 'Positive numeric PID required')
    expected = str(app / 'Contents/MacOS/Client-Mac-Shipping')
    command = subprocess.check_output(['ps', '-p', pid, '-o', 'comm='], text=True).strip()
    require(command == expected, 'PID is not the exact configured test app executable')


def main():
    command = sys.argv[1]
    no_root()
    if command == 'closed':
        require_closed()
    elif command == 'preflight':
        volume, original, work, app = config()
        print('Validated APFS paths:', volume, original, work, app, sep='\n')
    elif command == 'pid':
        _, _, _, app = config()
        check_pid(sys.argv[2], app)
    elif command == 'clone':
        _, original, work, app = config()
        require_closed()
        require(not os.path.lexists(work), 'Clone requires a NEW work directory; never overwrite')
        require(not os.path.lexists(app), 'Test app already exists')
        work.parent.mkdir(parents=True, exist_ok=True)
        work.mkdir()  # Exclusive reservation: a concurrent clone cannot use this work directory.
        subprocess.run(['cp', '-cR', str(original), str(app)], check=True)
        entitlements = work / 'test-entitlements.plist'
        with entitlements.open('xb') as f:
            f.write(plistlib.dumps({}))
        require_closed()
        subprocess.run(['codesign', '--force', '--sign', '-', '--entitlements', str(entitlements), str(app)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        subprocess.run(['codesign', '-d', '--entitlements', ':-', str(app)], check=True)
        subprocess.run(['codesign', '-dvv', str(original)], check=True)
        print('Clone signed. Original not modified. This does not prove official acceptance.')
    else:
        require(False, 'Unknown command')


if __name__ == '__main__':
    main()
