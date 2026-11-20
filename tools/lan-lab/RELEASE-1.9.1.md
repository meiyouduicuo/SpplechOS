# SpplechOS 1.9.1 — empty shell and signing-profile selection

The iOS IPA is now an empty shell: no game frameworks, manifests, launchers, images,
artwork or saved data are included. It retains `org.spplechos.shell`, so installing
with the original Sideloadly account updates the existing application. Existing
games imported into Documents and their saved data are not removed. Those games
may still appear after an upgrade because they already reside on the phone.

Windows previously rejected any profile match count other than one, showing
`No unique installed signing profile matches this app` both when no matching
profile existed and when several renewals coexisted. The selector now requires
the same exact app identity, team, certificate and current device authorization,
rejects expired or undated profiles, and deterministically picks the valid profile
with the latest expiration. Specific localized messages distinguish missing
profiles, certificate mismatches, device authorization and expiry.

Eight synthetic-public-metadata tests cover renewed profiles in either order,
duplicates, expiry, wrong certificates/apps/teams/devices, naive plist dates,
stable ties and language-specific errors. The original multiple-match failure was
reproduced before the fix. No real private key was accessed during diagnosis.
The user deferred USB access, so the exact profile state on that phone and actual
signed-package export still need device verification.

The build result also clears the driver's obsolete IPA-path announcement in game
package mode, so it does not imply that building a framework generated a game IPA.
The iOS executable and import UI are the same cloud-tested build as 1.9.0, with
bundle metadata updated to version 1.9.1 / build 191 and all embedded games omitted.
