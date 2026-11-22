# Device-to-device game transfer

Implementation status: source is saved, but the final revision has **not** passed iOS validation and no release IPA has been produced for this feature.

## User flow

- Receiver: App settings → Receive a game.
- Sender: select a playable game → Game settings → Send to another device.
- Select the receiving device, compare the six-digit code on both screens, and confirm on both.
- The receiver sees the game title and size and explicitly accepts the import.
- Keep both apps in the foreground. Cancelling, backgrounding or losing the connection aborts the transfer; retry starts from the beginning.

Both apps must have compatible signing teams and matching installed bundle identifiers. Do not confuse the independent airport test app with the original SpplechOS app. Matching metadata alone does not replace the operating system's signature checks when launching the received framework.

## Storage and integrity

The sender reads existing framework files, artwork, the selected RomFS image, external shaders and add-on data. It hashes files in bounded chunks and never builds another full `.sppgame` archive. Directory trees and symbolic links are not accepted as a substitute for the RomFS image.

The receiver checks the manifest and free space before asking to import. It writes directly into one staged resource tree and requires the new payload size plus 256 MiB free. Existing resources remain in place until verification completes, so updating a game still needs room for its replacement.

The source includes no saves, cloud backups or account credentials. Commit uses `GamePackage`'s existing ownership list and journal, preserving saves, settings and other games. The live framework signature is checked before large game data is allowed across the connection. Incomplete stages are cleaned on cancellation or at startup after a process kill.

Bonjour discovery uses `_spp-game._tcp` with Network framework peer-to-peer discovery enabled. An ephemeral Curve25519 exchange derives an AES-GCM key. The user-visible code binds the key exchange; directional sequence authentication rejects replay and reflection. At most one 1 MiB payload chunk awaits acknowledgment. Files are also checked against their SHA-256 digests.

## Validation and resumption

Run the manual GitHub workflow `build-spplechos-ios.yml` on `spplechos/cloud-build`. The workflow includes:

- Swift package build and the peer-transfer suite (encryption, compatible loopback, incompatible teams, interruption and staging cleanup, no archive or save export).
- Isolated 5 GiB file-import and encrypted loopback memory checks.
- Full Swift package tests.
- The peer suite and USB suite on an iOS simulator.
- UI tests for both transfer entry points and the existing import, settings, save confirmation and landscape safety behavior.
- An empty app template build, followed by local packaging and identity/content checks.

The independent source-path check reproduced a missing-executable failure. It was fixed using canonical URL components instead of dropping characters from directory strings. After the repository was made public, run 44997650836 passed all seven peer-transfer tests, a 5 GiB encrypted loopback transfer with 8,011,776 bytes resident-memory growth, and the host package tests. The full UI package gate identified untranslated text and a missing Close entry. These have been corrected across all supported catalogs and await the next complete run.

After cloud checks pass, build version 1.11.0 with original bundle ID `org.spplechos.shell`, no embedded games, and retain the import-memory and landscape fixes. Install through the user's existing signing tool and account, covering the original app without uninstalling it. A real transfer between two signed iPhones, game launch, and preservation of both phones' saves remain required physical checks.

### Local checks while macOS builds are unavailable

The Windows front-end suite completed: 591 tests, 57 skipped, no failures. `python tools/l10n_shell_catalogs.py --check` and `git diff --check` passed. No Qt executable behavior or engine patch changed.

The general build-tool and automation suites were also attempted on Windows, but did not pass there: 269 tests (48 failures, 20 errors, 35 skips) and 177 tests (5 failures, 15 errors). Their logs include missing Unix utilities, shell/shebang and symbolic-link assumptions, and platform-specific extracted-file expectations. These results are not a replacement for the required macOS gates. Local diagnostic logs are in the workspace's `Work/peer-local-*-tests.log`; the Windows front-end result is in `Work/peer-final-windows-tests.log`.

The final source also blocks concurrent package imports, game launch, game deletion, save clearing and save restoration while a peer-transfer sheet is active. The host mutual-exclusion test passed on macOS. The final text changes and transfer-close lifecycle still require the complete macOS/iOS run. Closing the sheet also resumes queued USB imports. The disconnection test asserts it reached payload transfer, preventing an earlier signature failure from counting as successful interruption coverage.
