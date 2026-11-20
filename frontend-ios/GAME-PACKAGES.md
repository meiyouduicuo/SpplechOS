# SpplechOS game packages

Windows builds the game framework and image once. **Export game package** connects to
an unlocked phone running the installed SpplechOS, signs a disposable framework copy
with its existing Sideloadly identity, then writes one `.sppgame` file. No game or saved
file is written to the phone during export. A compatible signing certificate and the
installed app's profile are required. Private keys and profiles never enter the package.

Copy the package to Files on the phone, open SpplechOS and tap **+**. The importer reads
the selected file in place, streams it to staging, verifies every SHA-256, the app/team,
game manifest, framework signature metadata, image identity and shader presence. It
publishes the complete game and reloads the library without reinstalling the app.
Keep SpplechOS in the foreground during import. iOS remains responsible for enforcing
the actual code signature when loading the framework. Existing signing expiry and
device authorization requirements still apply.

Reimport replaces only that game's framework, image, shaders and DLC. Saved games,
settings, save backups and other games are preserved. A transaction record restores
previous files if an import is interrupted during publication. Import temporarily
requires space for the complete new payload in addition to existing data and the
source package. After success the source package may be removed separately in Files.

## Container version 1

The first eight bytes are ASCII `SPPLPK01`. A little-endian unsigned 64-bit JSON byte
length follows, then UTF-8 JSON and the concatenated file payloads in manifest order.
There is no compression or archive extraction library. Both writers and readers stream
4 MiB chunks. JSON is limited to 32 MiB, 200,000 entries and 100 GiB of payload.

The manifest has `schema: 1`, `titleID` (16 uppercase hexadecimal digits), `bundleID`,
`teamID` and `files`. Each file has `path`, unsigned 64-bit `size` and lowercase hex
`sha256`. No absolute paths, path traversal, symlinks, case collisions or file/parent
collisions are allowed. Only `framework/**`, `data/romfs.img`, `data/msl/**` and
`data/aoc/**` are accepted. `framework/` maps to `DmGame<TITLE_ID>.framework`.

`Tests/ShellHostTests/Fixtures/GamePackage/synthetic.sppgame` is a tiny Python-written
interoperability fixture. Its mock signature metadata, image and shader are synthetic
parser inputs, not executable game code or an Apple-signed program.
