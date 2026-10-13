"""Isolated fixtures + mocked macOS commands only. Never reads game/Library/Volumes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import migrate_saved as migration
import restore_saved as restoration
import safety


class DataSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.src = self.home / 'Library/Client/Saved'
        self.state = self.home / '.local/state/wuthering-external-test'
        self.volume = self.root / 'external'
        self.work = self.volume / 'work'
        self.app = self.work / 'Test.app'
        self.src.mkdir(parents=True)
        (self.src / 'data').write_bytes(b'original bytes')
        (self.src / 'empty').mkdir()
        self.work.mkdir(parents=True)
        self.original = safety.manifest(self.src)
        for module in (migration, restoration):
            p = patch.object(module, 'locations', return_value=(self.src, self.state))
            p.start()
            self.addCleanup(p.stop)
            p = patch.object(module, 'no_root')
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(migration, 'config', return_value=(self.volume, self.volume / 'Original.app', self.work, self.app))
        p.start()
        self.addCleanup(p.stop)
        # Fake distinct external device, leaving every stat field besides st_dev intact.
        real_stat = Path.stat
        external = self.volume

        def stat(path, *args, **kwargs):
            value = real_stat(path, *args, **kwargs)
            if path == external or external in path.parents:
                fields = list(value)
                fields[2] = value.st_dev + 100
                return os.stat_result(fields)
            return value
        p = patch.object(Path, 'stat', stat)
        p.start()
        self.addCleanup(p.stop)
        self.stat_patch = p
        self.copy_corrupt = False
        self.pgrep_code = 1
        self.commands = []

        def run(command, **kwargs):
            self.commands.append(command)
            if command[0] == 'pgrep':
                return subprocess.CompletedProcess(command, self.pgrep_code)
            if command[0] == '/usr/bin/ditto':
                shutil.copytree(command[1], command[2], dirs_exist_ok=True)
                if self.copy_corrupt:
                    (Path(command[2]) / 'data').write_bytes(b'corrupt')
                return subprocess.CompletedProcess(command, 0)
            raise RuntimeError('Unmocked command rejected: ' + repr(command))
        p = patch.object(subprocess, 'run', side_effect=run)
        p.start()
        self.addCleanup(p.stop)

    def record(self):
        return next(self.state.glob('migration-*.json'))

    def unchanged(self):
        self.assertFalse(self.src.is_symlink())
        self.assertEqual(safety.manifest(self.src), self.original)

    def test_existing_external_directory_rejected(self):
        (self.work / 'Saved').mkdir()
        with self.assertRaises(SystemExit):
            migration.migrate()
        self.unchanged()

    def test_existing_dangling_external_link_rejected(self):
        (self.work / 'Saved').symlink_to(self.root / 'absent')
        with self.assertRaises(SystemExit):
            migration.migrate()
        self.unchanged()

    def test_running_or_failed_pgrep_rejected(self):
        for code in (0, 2, 127):
            self.pgrep_code = code
            with self.assertRaises(SystemExit):
                migration.migrate()
            self.unchanged()
        self.assertFalse((self.work / 'Saved').exists())

    def test_same_device_rejected_before_copy_or_rename(self):
        self.stat_patch.stop()
        with self.assertRaises(SystemExit):
            migration.migrate()
        self.unchanged()
        self.assertFalse(any(c[0] == '/usr/bin/ditto' for c in self.commands))

    def test_copy_mismatch_retains_both_and_checkpoint(self):
        self.copy_corrupt = True
        with self.assertRaises(SystemExit):
            migration.migrate()
        self.unchanged()
        self.assertEqual(json.loads(self.record().read_text())['phase'], 'copy-pending')
        self.assertTrue((self.work / 'Saved').is_dir())

    def test_matching_link_restore_keeps_external_and_held_link(self):
        migration.migrate()
        record = self.record()
        data = json.loads(record.read_text())
        self.assertTrue(self.src.is_symlink())
        self.assertEqual(safety.manifest(Path(data['backup'])), self.original)
        restoration.restore(record)
        self.unchanged()
        self.assertEqual(safety.manifest(self.work / 'Saved'), self.original)
        self.assertTrue(Path(data['backup'] + '-external-link').is_symlink())
        self.assertEqual(json.loads(record.read_text())['phase'], 'restored')

    def test_dangling_link_offline_restore(self):
        migration.migrate()
        # Fixture-only rename simulates an unmounted external disk; no deletion.
        self.volume.rename(self.root / 'unmounted')
        self.assertTrue(self.src.is_symlink())
        self.assertFalse(self.src.exists())
        restoration.restore(self.record())
        self.unchanged()

    def test_mismatched_link_rejected(self):
        migration.migrate()
        self.src.unlink()  # Test fixture link only.
        self.src.symlink_to(self.root / 'wrong')
        with self.assertRaises(SystemExit):
            restoration.restore(self.record())
        self.assertTrue(self.src.is_symlink())

    def test_tampered_backup_path_rejected(self):
        migration.migrate()
        record = self.record()
        data = json.loads(record.read_text())
        data['backup'] = str(self.root / 'outside')
        record.write_text(json.dumps(data))
        with self.assertRaises(SystemExit):
            restoration.restore(record)
        self.assertTrue(self.src.is_symlink())

    def test_symlink_source_ancestor_rejected(self):
        self.src.parent.rename(self.home / 'real-client')
        self.src.parent.symlink_to(self.home / 'real-client')
        with self.assertRaises(SystemExit):
            migration.migrate()
        self.assertEqual(safety.manifest(self.home / 'real-client/Saved'), self.original)

    def test_backup_manifest_tamper_rejected(self):
        migration.migrate()
        data = json.loads(self.record().read_text())
        (Path(data['backup']) / 'data').write_bytes(b'changed')
        with self.assertRaises(SystemExit):
            restoration.restore(self.record())
        self.assertTrue(self.src.is_symlink())

    def test_acknowledgment_required(self):
        from argparse import Namespace
        with self.assertRaises(SystemExit):
            migration.confirmation(Namespace(yes=True, ack_client_saved=False))

    def test_preflight_actual_apfs_and_bundle(self):
        import plistlib
        original = self.volume / 'Original.app'
        (original / 'Contents').mkdir(parents=True)
        info = original / 'Contents/Info.plist'
        info.write_bytes(plistlib.dumps({'CFBundleIdentifier': safety.BUNDLE_ID}))
        env = {'VOLUME': str(self.volume), 'ORIGINAL': str(original),
               'WORK': str(self.work), 'TEST_APP': str(self.app)}
        disk = {'MountPoint': str(self.volume), 'FilesystemType': 'apfs'}
        with patch.dict(os.environ, env), patch.object(os.path, 'ismount', return_value=True), patch.object(subprocess, 'check_output', return_value=plistlib.dumps(disk)):
            self.assertEqual(safety.config(), (self.volume, original, self.work, self.app))
            info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'wrong.bundle'}))
            with self.assertRaises(SystemExit):
                safety.config()
        disk['FilesystemType'] = 'hfs'
        with patch.dict(os.environ, env), patch.object(os.path, 'ismount', return_value=True), patch.object(subprocess, 'check_output', return_value=plistlib.dumps(disk)), self.assertRaises(SystemExit):
            safety.config()

    def test_pid_exact_and_numeric(self):
        with patch.object(subprocess, 'check_output', return_value=str(self.app / 'Contents/MacOS/Client-Mac-Shipping') + '\n'):
            safety.check_pid('123', self.app)
            with self.assertRaises(SystemExit):
                safety.check_pid('123;open', self.app)
        with patch.object(subprocess, 'check_output', return_value='/wrong/Contents/MacOS/Client-Mac-Shipping\n'), self.assertRaises(SystemExit):
            safety.check_pid('123', self.app)


if __name__ == '__main__':
    unittest.main()
