# SpplechOS 1.8.0 — Animal Crossing local multiplayer

The release uses the same game executable as the build verified on two iOS
devices: one opened the Animal Crossing airport, and the other discovered
the island and successfully joined. The game build is 3.0.3, v2228224.

## Package and upgrade

- Display name: SpplechOS; version: 1.8.0; build: 180.
- Bundle ID: `org.spplechos.acnh.airporttest`, retained for an in-place upgrade
  of the verified test app. Use the same sideloading account and do not uninstall
  it first. The earlier `org.spplechos.shell` app remains a separate application.
- Game framework and matching shaders are embedded; ROMFS, user saves and keys
  are not bundled. Existing game-folder selections and saves remain in Documents.
- LAN is enabled by default. The release does not enable diagnostic tracing by
  default; an explicit pre-existing user configuration still takes priority.
- The existing shell includes per-game clear-save confirmation and global versus
  per-game settings. Clearing saves is unrelated to installing this update.

## Reproduce

Sync the pinned engine, then run `python tools/lan-lab/stage_engine_sources.py`
before rebuilding the game framework. Build the iOS shell template using the
manual `build-spplechos-ios.yml` workflow, or with Xcode locally.

Run `tools/lan-lab/export_acnh_airport_test.py` with `--release --version 1.8.0
--build-number 180`, an empty `--root`, the completed `--framework`, its matching
`--shader-meta`, an existing `--romfs-image` for identity validation, and the
compiled `--template`. Input game data stays local. Use a sideloader to sign
the resulting IPA; the repository contains source, not a signing identity.

## Validation and limits

- 108 Windows LAN tests pass, including publication-pending room settings,
  two-process discovery, joining, bidirectional UDP, reconnect and rejection.
- The exact admission failure was captured on-device as policy 0 returning 674;
  the regression reproduced it before the local-room snapshot fix.
- Compiled forced-HLE registrations are checked for uniqueness before packaging.
- Earlier cloud Swift package builds/tests and two affected iPhone Simulator UI
  tests passed (run 44555680056); release packaging changes no Swift source.
- Device validation: 16PM hosts and Air discovers/joins. Both retained their
  progression. The Air test copy received a different island/player identity:
  cloned saves initially yielded a room at the transport layer but no island in
  the game; after changing the test identity, joining succeeded.
- Save modification and all private save data stay local and are not part of
  the application or repository.
- Verified scope is two SpplechOS devices on one local network. The transport
  currently has one guest connection; larger parties and Nintendo online
  services are not supported by this release. Other games require separate
  compatibility verification, even though the backend is shared.
