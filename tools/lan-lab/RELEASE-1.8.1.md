# SpplechOS 1.8.1 — bundled Animal Crossing artwork

Build 182 upgrades the original app (`org.spplechos.shell`). The game executable,
shader image, save handling, LAN behavior, and shell UI are unchanged from the
verified 1.8.0 original-app upgrade.

The standalone exporter previously called `export_shell` without artwork arguments.
That path removes stale mirrored banners and writes no replacement, so the
Animal Crossing framework in the IPA had no `banner.*` and the launcher displayed
its title-only placeholder. The desktop UI already passed its artwork selection.

The exporter now selects local artwork before packaging: explicit `--banner`,
current desktop cache/custom artwork, legacy cache, then an existing source
framework banner. It forwards the selection and verifies the exact image bytes
in the finished IPA. No network artwork download or user data is added to source.

Validation: 114 LAN/packaging tests pass; the previous IPA contained no banner,
and the corrected IPA contains the cached JPEG. Original-app identity, executable,
shader identity and ZIP integrity are verified. The missing-game-data badge is
independent of artwork: the game still needs its existing ROMFS folder selected
in this application's settings. Test-app data is not automatically migrated.
