# Wuthering Waves on Mac: Store Additional Game Resources on an External SSD

[繁體中文](README.md) | English

**Installing the app on an external drive is not enough. In this test, re-signing a separate test copy and linking its Saved directory to an external SSD allowed additional resources to download externally. The user also reported being able to play. SIP was not disabled.**

## Read the Risks First

- This removes the **test copy's** original entitlements, including App Sandbox, and replaces its signature with a local ad-hoc signature. **It does more than change the download location: it reduces isolation for that copy.**
- This procedure does not disable SIP, Gatekeeper, or system-wide sandbox protections. It does not modify gameplay logic or bypass anti-cheat or account authentication.
- The re-signed copy no longer has its original Apple/developer signing identity. Sign in with Apple, Keychain access, App Store receipt/integrity checks, and updates may stop working.
- **Compliance with the game's terms of service and account safety are not guaranteed.** Ask the publisher first if account risk is a concern. Do not proceed if you are unwilling to accept these risks.
- Crashes occurred during testing; the user subsequently reported being able to play. **Long-term stability, all login methods, future updates, and other computers have not been verified.**
- Obtain the original game only from the App Store. Do not download someone else's re-signed copy. Share this guide, not game files, receipts, or personal data.
- **Keep the original app and back up existing data. Never modify your only copy.**

## Tested Environment

| Item                      | Environment                                  |
| ------------------------- | -------------------------------------------- |
| Operating system          | macOS 27.0.1                                 |
| Game                      | Wuthering Waves 3.7.0, Mac App Store edition |
| Executable architecture   | arm64                                        |
| External drive            | APFS SSD                                     |
| App installation location | External SSD                                 |

## Why the App Store's External Installation Setting Is Not Enough

The App Store can install large apps on an external drive, but resources downloaded by the game itself may still go into a user directory on the internal drive.

Paths observed in this test:

| Version                | Data location                                                                       |
| ---------------------- | ----------------------------------------------------------------------------------- |
| Original sandboxed app | `~/Library/Containers/com.kurogame.wutheringwaves.global/Data/Library/Client/Saved` |
| Re-signed test copy    | `~/Library/Client/Saved`                                                            |

**Verify the actual path on your own machine.** `Client` is a generic name that other Unreal Engine games may also use. If you cannot confirm that the directory belongs to this test copy, stop—do not move it blindly.

## Before You Start

- Install the original game from the App Store on an external APFS volume.
- Leave enough external space for the app, additional resources, backups, and future updates. APFS clones initially share blocks, but later changes consume more space.
- Leave internal space for macOS, swap, and caches. This method **does not eliminate internal storage usage**.
- Quit both the original app and the test copy completely. Never move data while the game is running, downloading, or updating.
- The commands require macOS Terminal, `codesign`, `ditto`, and Python 3. If Python 3 is missing, install it yourself from a trusted source. Nothing is installed automatically.
- Do not use `sudo`, `chmod -R 777`, or disable security protections to work around errors.

## Package and Dependencies

You can share this package as a whole. The scripts package the manual procedure, but **these packaged scripts have not been run against the real game. Do not rerun them on an already working installation.** The original single-machine success does not establish that these scripts, a new computer, or a new game version will work.

Requirements: macOS, Python 3, and the system tools `diskutil`, `cp`, `ditto`, `codesign`, `pgrep`, `ps`, `open`, and `lsof`. No automatic installation or sudo is used. There is no run-everything, update, or delete command.

```text
wutheringwaves-external-ssd/
├── README.md
├── README.en.md
├── config.env.example
├── scripts/
│   ├── common.sh
│   ├── safety.py
│   ├── preflight.sh
│   ├── create-test-app.sh
│   ├── launch.sh
│   ├── inspect.sh
│   ├── migrate-saved.sh
│   ├── verify.sh
│   ├── restore-saved.sh
│   ├── migrate_saved.py
│   └── restore_saved.py
└── tests/test_safety.py
```

## 1. Configure Your Paths

In Terminal, change to **the package directory** (for example, `cd "$HOME/Documents/wutheringwaves-external-ssd"`; use the actual folder name on your machine). Copy the template, edit `config.env`, and save it before running preflight:

```bash
cp -n config.env.example config.env
open -e config.env
bash scripts/preflight.sh
```

`config.env` is a trusted shell configuration file: do not source untrusted code. The template defines quoted paths for `VOLUME`, `ORIGINAL`, `WORK`, and `TEST_APP`. Replace the Chinese drive-name placeholder with your actual external volume name. Spaces in names are supported. Do not share your personal configuration file.

Each script loads configuration relative to the package, without relying on exports from a previous shell. Except for offline restoration, the scripts check the mount point, APFS information from `diskutil`, resolved paths within the selected volume, clone source and destination on the same volume, the original bundle ID, and separation between the work directory and the original app. Symlink paths and ancestors are rejected.

Still read the device and capacity information yourself to confirm that you selected the correct SSD. Adjust `ORIGINAL` if the app's name or location differs. **Never point `TEST_APP` at the original app.** Stop on errors; do not skip checks.

## 2. Create and Re-sign a Separate Copy

Quit the original app and test copy completely, then run:

```bash
bash scripts/create-test-app.sh
```

You will be prompted to type `YES`. Commands that create, launch, migrate, or restore data require confirmation. You may add `--yes` if you explicitly accept the risks; this does not bypass safety checks.

**WORK must not exist yet.** The script reserves a new work directory exclusively to prevent concurrent creation or overwriting an existing copy. It uses macOS `cp -cR` for an APFS copy-on-write clone, re-signs the copy ad hoc with empty entitlements, runs `codesign --verify --deep --strict`, and displays the original app's signature. The original should still show Apple Mac OS Application Signing, not an ad-hoc signature.

If a step fails, the copy/work directory is retained for inspection. The original is not deleted, and there is no automatic cleanup. Do not blindly rerun or overwrite it; inspect the failure and use another new WORK directory when appropriate. Signature verification may take more than a minute—wait for it to finish.

Passing `codesign --verify` does not mean the publisher accepts the copy or that Gatekeeper, login, anti-cheat, or updates will work. Stop if the system or game rejects it. This guide does not provide instructions to bypass those checks.

## 3. Launch the Copy and Identify Its Data Directory

```bash
bash scripts/launch.sh
pgrep -fl '/Contents/MacOS/Client-Mac-Shipping'
# Replace 12345 with the PID of the test copy shown above.
bash scripts/inspect.sh 12345
```

The inspection script requires a positive numeric PID. It uses `ps` to check that the executable exactly matches the configured test app, then displays open files with `lsof`. It rejects the original app's PID and does not treat this output as proof of success.

In this test, the copy reached the storage check before resource downloads. **Do not start a large download or enter account credentials just to test this stage.**

Observed files included `~/Library/Client/Saved/DeviceSaved/DeviceStorage.db`. If you see a different location, the original app's process, or a pre-existing `~/Library/Client` directory of unknown ownership, **stop before proceeding**.

After confirming ownership, cancel and **quit the game completely**. Do not move an open database.

## 4. Back Up Saved, Copy It Externally, and Create the Symlink

This operation is only for `~/Library/Client/Saved` after you have confirmed that it belongs to the test game. It does not modify the original app's container. Because `Client` is generic, an explicit ownership acknowledgment is required:

```bash
bash scripts/migrate-saved.sh --ack-client-saved
# Non-interactive execution still requires the ownership acknowledgment:
# bash scripts/migrate-saved.sh --ack-client-saved --yes
```

The script compares SHA-256 hashes for every file, retains the local original, and refuses to overwrite an existing external Saved directory, including a dangling symlink. **Before moving the original**, it checks that the external destination is on a different filesystem device and the backup is on the source device. It checks again that the game is closed: `pgrep` exit code 0 means running, 1 means no process, and other codes are errors. Symlinks in the source path or its ancestors also cause it to stop.

Backups and checkpoint JSON files live under `~/.local/state/wuthering-external-test/`, with unique names and an exclusive lock. The external destination is reserved exclusively. Only after copying and verification does the script rename the local original and create the symlink. It records progress and does not delete backups. **Do not rerun a successful migration.**

Backups contain personal game data. Keep them private and save the printed **absolute path to the recovery record**. If any stage fails, inspect the JSON `phase` and the source, backup, and external directory states first. Do not delete apparently redundant directories or blindly rerun.

An interrupted operation may leave `.operation-lock` or `.tmp` files. Confirm that no script/game is running and preserve all copies before handling them manually. For intermediate states without a matching symlink, the restore script refuses to guess; manual recovery using the record is required. There is no automatic deletion or force-continue command.

## 5. Verify That Downloads Really Go to the External Drive

```bash
bash scripts/launch.sh
pgrep -fl '/Contents/MacOS/Client-Mac-Shipping'
# Replace 12345 with the current test copy's PID.
bash scripts/verify.sh 12345
```

If the storage warning disappears, let the download run for about 20–30 seconds, then pause and inspect it. `verify.sh` only shows snapshots from `readlink`, `df`, `du`, and external open files reported by `lsof`. Run it again to compare sizes. **It does not automatically declare success.**

Verify each of these separately:

1. The running app is the external `WutheringWaves-Test.app`, not the original.
2. The free-space check passes.
3. The external `Saved/Resources` directory actually grows.
4. During downloading, `lsof` shows external `.pak.download` or other resource files open. A paused or completed download may no longer have an open `.download` file; its absence alone is not proof of failure.
5. Subsequently verify download completion, login, and gameplay.

**A successfully created symlink or a “downloading” screen alone is not sufficient evidence.**

## Everyday Use, Crashes, and Updates

- Find `WutheringWaves-Test.app` in Finder and drag it to the Dock. Connect the SSD first, and make sure its mount name has not changed.
- Use the `TEST_APP` path from `config.env` to find the copy. Do not use the App Store's Open button, which may launch the original.
- Do not unplug or eject the drive while playing or downloading. Use a stable connection.
- Internal caches, logs, and swap may still grow. Check internal free space when investigating crashes, but do not assume it is the cause without evidence.
- A crash does not mean your data disappeared. Check the copy, symlink, and which app you launched before deleting large resource directories or reinstalling.
- **Updates remain unverified.** The App Store normally manages the original app, not necessarily this copy. In-game updates may also change executables, signatures, or data formats.
- Quit and back up before updating. If a new copy is needed, build it from the new legitimate original in **another new test directory** and recheck compatibility. Do not overwrite your only working version or let two versions write to the same Saved directory simultaneously.
- No automatic security-disabling, anti-cheat bypass, or re-sign-on-every-launch tool is provided.

## Restore the Previous Setup

Quit all Wuthering Waves processes first.

### Return to the Official App

This guide does not modify the original app or its container. Launch it from the App Store or its original location. It may still require internal space and **will not automatically use the test copy's external resources**.

### Restore the Test Copy's Local Saved Directory

Restoration preserves the symlink under a different name and puts the pre-migration local original back. **New external data remains intact, but the game returns to the older local data.** If new local saves/settings were created after migration, back up external Saved first and determine how to preserve them. Do not assume everything is stored in the cloud.

Pass the **absolute JSON path** printed in step 4. The script does not select the “latest backup” for you. Replace the placeholder below with the actual record filename:

```bash
bash scripts/restore-saved.sh "$HOME/.local/state/wuthering-external-test/migration-REPLACE-WITH-ACTUAL-RECORD.json"
# Append --yes only if you explicitly accept restoring pre-migration data.
```

Restoration does not load `config.env`, require the SSD to be mounted, or require the original app to exist. It can restore a dangling symlink. It still requires the game to be closed, the source to be exactly `~/Library/Client/Saved`, the record and backup to be directly within the expected state directory, no symlink ancestors, matching backup hashes, and a current link that exactly matches the record.

The link is retained under a new name; external Saved and the test app are not deleted. The final phase is `restored`. If the state does not match the record, restoration stops rather than overwriting a different source or guessing paths.

No automatic deletion command is provided. Clean up copies and backups manually only after confirming that they are no longer needed and no game is using them.

## Moving to Another Mac

1. Keep this README, information about the legitimate original, external `Saved`, and necessary personal backups. **Copying only the app is not enough.**
2. Confirm hardware, macOS, and game compatibility on the new Mac. Obtain the original through the App Store using your own account. Do not assume an old copy's receipt/signature will work there.
3. Create a separate test copy on the new Mac. First verify startup and its actual data location.
4. If external Saved already exists, **step 4 intentionally stops**. Back up that data separately before deciding how to test a new version. Do not delete it just to pass the check.
5. Recreate the new Mac's `~/Library/Client/Saved` link. Absolute paths do not repair themselves if the SSD's mount name changes.
6. Resource reuse or re-download requirements depend on the game version. You may need to log in again; Keychain items are not guaranteed to migrate with Saved.

This guide documents the tested procedure. **It is not a one-click migration tool that eliminates verification on a new Mac or game version.**

## Isolated Tests (No Game Operations)

```bash
for script in scripts/*.sh; do bash -n "$script" || break; done
python3 -m unittest discover -s tests -v
python3 -O -m unittest discover -s tests -v
```

Tests use small fixtures in temporary directories and mock macOS commands and cross-device checks. They cover existing destinations, running games/process-check failures, copy mismatches, matching/dangling restore links, and altered paths/backups. The `-O` run also checks that Python optimization does not disable guards. These tests do not validate actual APFS cloning, signing, downloads, login, or a new Mac.

## References and Sharing

- [Apple: Change App Store settings](https://support.apple.com/guide/app-store/change-settings-mchlp2257/mac): external APFS installation for large apps—not a guarantee that in-game resource locations are configurable.
- [Apple: Accessing files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox): file-access authorization principles, not an endorsement of this workaround.
- [Wuthering Waves official website](https://wutheringwaves.kurogames.com/en/main)
- Local command documentation: `man codesign`, `man cp`, `man ditto`, and `man lsof`.

When sharing, retain the risks, tested versions, and unverified limitations. Do not claim “official support,” “no account-ban risk,” “zero internal storage usage,” or “works forever.”
