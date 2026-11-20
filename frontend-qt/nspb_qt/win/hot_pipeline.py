"""Experimental Windows-to-iOS incremental game delivery."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .device_probe import probe_shell
from .hot_install import HotInstallError, check_host, inspect_framework, upload_aoc, upload_romfs, upload_signed_framework
from .hot_sign import sign_framework_copy


async def deliver_game(framework: Path, title_id: str, image: Path | None,
                       zsign: Path, credential_dir: Path, progress=None, *, romfs_tool: Path | None = None,
                       shader_dir: Path | None = None, package_path: Path | None = None) -> None:
    """Sign and stage an FH framework, optionally copying its matching image first.

    A device-side restart is required to promote the framework. The installed app
    and the game's saved files are not replaced by this operation.
    """
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService

    if progress:
        progress('device', 0, 0)
    manifest = inspect_framework(framework, title_id)
    try:
        shell = await asyncio.wait_for(probe_shell(), timeout=20)
        device = await asyncio.wait_for(create_using_usbmux(), timeout=20)
    except (asyncio.TimeoutError, OSError) as exc:
        raise HotInstallError('设备连接超时或不可用，请解锁手机、检查数据线和“信任此电脑”设置。') from exc
    except Exception as exc:
        from pymobiledevice3.exceptions import NoDeviceConnectedError
        if isinstance(exc, NoDeviceConnectedError):
            raise HotInstallError('未检测到苹果设备，请解锁手机并重新连接数据线。') from exc
        raise
    try:
        async with await HouseArrestService.create(device, shell.bundle_id, documents_only=True) as afc:
            beacon = await afc.get_file_contents('/Documents/.shell-host.json')
            check_host(beacon, expected_bundle_id=shell.bundle_id, expected_team_id=shell.identity.team_id)
            with tempfile.TemporaryDirectory(prefix='spplechos-hot-') as temp:
                if progress:
                    progress('sign', 0, 0)
                signed = await sign_framework_copy(framework, Path(temp) / Path(framework).name,
                                                   title_id, shell.identity, device, zsign, credential_dir)
                if package_path is not None:
                    from .game_package import export_game_package
                    if image is None:
                        raise HotInstallError('Game data is required to export a complete package')
                    # No files are written to the phone in package-export mode.
                    export_game_package(signed, image, package_path, shell.identity,
                                        romfs_tool=romfs_tool, shader_dir=shader_dir, progress=progress)
                    return
                if image is not None:
                    if progress:
                        progress('prepare', 0, 0)
                    chain = str(manifest.get('chain', ''))
                    candidate = Path(shader_dir) / (chain + '.img') if shader_dir and chain and '/' not in chain and '\\' not in chain else None
                    await upload_romfs(afc, image, title_id, manifest.get('romfs_identity', ''),
                                       None if progress is None else lambda a, b: progress('data', a, b),
                                       romfs_tool=romfs_tool, expected_chain=chain,
                                       stage_progress=progress, shader_image=candidate)
                    await upload_aoc(afc, Path(image).parent / 'aoc', title_id,
                                     None if progress is None else lambda a, b: progress('aoc', a, b))
                await upload_signed_framework(afc, signed, title_id,
                                              None if progress is None else lambda a, b: progress('framework', a, b))
    finally:
        await device.close()
