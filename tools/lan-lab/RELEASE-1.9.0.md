# SpplechOS 1.9.0 — complete game packages

iOS build 190 upgrades the original `org.spplechos.shell` app. Install using the
same Sideloadly account without uninstalling. The upgrade retains the Animal
Crossing framework, shader image, artwork and LAN environment from 1.8.1 byte
for byte. No ROMFS, saved game, private key or provisioning profile is bundled.

Windows now builds a reusable framework and exports a signed `.sppgame` containing
the framework, matching image, shaders, DLC and artwork. Connect an unlocked phone
with the installed app to sign the package using the existing Sideloadly identity.
The phone's **+** button imports one package, verifies it and publishes it only when
complete. Reimport replaces game content while retaining saves and other games.
Interrupted publication rolls back on the next launch. Signing renewal and device
authorization requirements still apply.

The build page starts with a collapsed game-folder selector. Expand for individual
base/update/DLC/output choices. `prod.keys` is a persistent global choice under
Settings / Build tools. Shared/one-game IPA and separate data-transfer options are
removed from the Windows build page. First installation can export an empty shell
from Settings, without bundling previously built games.

The tracked Windows packaging spec rejects an incompatible MSYS2 ICU DLL that
otherwise shadows Windows ICU and causes a QtCore import failure. A hidden-window
startup test checks the actual application title and rejects exception dialogs.

Validation: Qt suite 574 tests, 56 environment-dependent skips, plus eight focused
Qt UI/key-memory tests. The Python/Swift package fixture covers complete imports,
corruption, large sizes, interrupted replacement and save preservation. Cloud run
[44772317493](https://github.com/meiyouduicuo/SpplechOS/actions/runs/44772317493)
passed Swift build/tests and three UI tests on iPhone 18 Pro with Xcode 27.2. The
iOS source tested there is `715cd31`; later changes affect Windows export/packaging
and test isolation. Final Windows startup and signing-tool startup pass. Both IPA
identity and unchanged existing framework/shader/artwork hashes were checked.

An app-only export was also verified to contain no game frameworks. Physical-device
package import and game launch still need user verification, as no USB device was
connected during this build. The local output folder holds the verification report
and artifact SHA-256 values. No installed phone data was changed.
