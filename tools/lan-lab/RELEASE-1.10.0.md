# SpplechOS 1.10.0 — USB game packages and immersive library

The iPhone library uses a mountain-and-lake wallpaper when a game has no banner.
Games with banners use the original artwork, with a dark overlay for legible text.
The horizontal game shelf works in portrait and landscape. The top gear opens
app settings. The sliders next to Play open the selected game's settings.

The Windows build page can send an already exported `.sppgame` to exactly one
USB-connected iPhone or iPad. The phone must be unlocked and SpplechOS must be
open. This transfer does not sign code or read signing credentials. Packages must
already match the installed app's bundle ID and signing team.

The desktop verifies the uploaded file before publishing a request in
`Documents/.usb-game-import`. The app watches this inbox, validates and imports
the package with the existing transactional importer, refreshes its catalogue,
and writes a receipt. The desktop reports success only after that receipt.
Incomplete transfers are never imported. Existing games, saves and settings are
outside the inbox and outside the importer's replacement scope.

The release IPA uses `org.spplechos.shell` and contains no games, game metadata,
ROM images or saves. Cover-install with the original Sideloadly account, without
uninstalling the original app, to keep its Documents folder.

Validation: Windows regression suite, focused Qt build-page checks, synthetic
USB transfer tests, Swift package tests and iOS simulator UI checks. A physical
USB import requires the updated app to be installed and opened on the phone.
