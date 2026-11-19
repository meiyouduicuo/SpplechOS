# SpplechOS local multiplayer prototype

This directory contains an experimental, opt-in LAN backend for two
SpplechOS instances. `stage_engine_sources.py` stages the source and bootstrap
into the nested engine checkout; set `DM_LAN=1` in a newly built game
framework to enable it. Without that setting the existing offline backend is
unchanged. The installed application and previously built frameworks do not
acquire this feature automatically.

From a fresh launcher checkout, run `python tools/engine.py sync` once to
populate `engine/`. Then run `python tools/lan-lab/stage_engine_sources.py`.
It applies `ldn-engine-integration.patch` to the pinned engine when needed
and copies the current LAN modules from `src/`. The engine checkout is
generated locally. Edit the source in this directory and keep the patch
up to date when changing the engine entry points. `ldn-trace.patch` is an
older diagnostic snapshot and is not applied by the staging script.

The prototype discovers rooms via Bonjour, authenticates the room join with
HMAC and fresh random nonces, and transports virtual UDP datagrams over a TCP
connection. The subsequent data stream is neither encrypted nor individually
authenticated. It is a SpplechOS-specific protocol and is not compatible with
Switch consoles or other emulators. Treat untrusted networks accordingly.

The implementation includes an LDN state/event model, public and private room
operations, room advertisements, a subset of virtual UDP socket operations,
and teardown/reconnection logic. It does not implement every socket operation,
acceptance policy, or game-specific behavior; importing an API does not prove
that a particular game will work. `DM_LDN_TRACE=1` enables diagnostic logging
of selected calls without recording credentials or packet contents.

`run_tests_windows.py` exercises native Windows modules, including two separate
processes communicating over real loopback TCP with a simulated asynchronous
Bonjour service. These tests do not establish real iOS Bonjour or privacy
behavior or Monster Hunter Rise compatibility. The target is a two-device test
using a separately built framework and an iOS shell containing local network
usage and Bonjour metadata. Existing applications and save data should not be
replaced for that test.

The LDN ABI references the public [libnx LDN service header](https://github.com/switchbrew/libnx/blob/master/nx/include/switch/services/ldn.h).
Apple's [local network privacy technote](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)
describes the usage string, Bonjour declaration and multicast restrictions.

## Open device investigation: MHR 3.9.1

The 2026-11-18 device log records ErrorCode 2618-0006 after host creation
and one empty nonblocking receive. The old backend returned BSD EAGAIN=35.
This SDK exposes musl errno (EAGAIN=11) at nn::socket, not raw BSD service
errno. Main build 14a1b6358133a714f994aee6772def48 checks 11 at 0x5357b08.
The typed receive at 0x207711c uses the error mapping at 0x2076bd0:
11 selects 0x2076c14 (retry), 35 selects 0x2076c24 (fatal). Both SDK
GetLastError and GetLastErrno read the same musl errno location.

The empty-receive regression failed with `35 != 11` before correction.
Guest socket errors now use musl numbers, including EAGAIN=11,
ENOPROTOOPT=92, EOPNOTSUPP=95, EAFNOSUPPORT=97 and ENETDOWN=100.
98 lab tests pass; successful lobby creation and joining on iOS remain
unverified until the corrected IPA is installed and tested.

The corrected errno build was tested on-device: 2618-0006 no longer appeared,
and repeated empty receives returned 11. Lobby creation still failed and
the game called DestroyNetwork/CloseAccessPoint. This remains OPEN.
`mhr_391_task_observations.py` contains build-ID/opcode-checked, read-only
observations for the game's asynchronous failure result and completion of
its initial create-network setup. They are temporarily installed in the
external provisional profile as patches.py. Callback output is tagged
[DEBUG-LAN-TASK]; no game behavior or return value is replaced.

The tasktrace device run reports create setup completed, then asynchronous
failure 0x6c65 (variant 1, underlying Result 0), followed by room teardown.
This result is synthesized by CreateMeshJob/JoinMeshJob cancellation paths.
SetupLocalPlayerInfo calls friends::GetPlayHistoryRegistrationKey and returns
an error if that fails; the host currently returns failure unconditionally.
Runtime confirmation is pending. The playertrace build adds a log at that
API and records the failure caller/stage without replacing return values.

The playertrace device run CONFIRMED local=1 GetPlayHistoryRegistrationKey
returns 0x2a2 immediately before CreateMeshJob::CompleteFailure
(main+0x20a24bc). A local-only compatibility implementation now issues an
opaque 64-byte process-lifetime identity, using random bytes and a SpplechOS
marker. It validates the emulated local UID and active LDN network; online
requests remain unsupported. This is NOT Nintendo's registration key format
and does not implement Nintendo play-history synchronization. The regression
failed with "local player setup rejected" before the change; 99 lab tests
pass afterward. On-device lobby creation/joining remains pending.
