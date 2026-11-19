"""Read-only discovery of an installed SpplechOS shell over USB.

The optional pymobiledevice3 dependency is loaded on demand. No keys are read,
no device data is modified, and discovery fails closed if multiple shells match.
"""
from __future__ import annotations

from dataclasses import dataclass
from .hot_install import HotInstallError, HostIdentity, check_host

ORIGINAL_BUNDLE_ID = 'org.spplechos.shell'


@dataclass(frozen=True)
class DeviceShell:
    bundle_id: str
    identity: HostIdentity


async def probe_shell() -> DeviceShell:
    """Find one paired USB device's compatible shell and validate its beacon."""
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.house_arrest import HouseArrestService
        from pymobiledevice3.services.installation_proxy import InstallationProxyService
    except ImportError as exc:
        raise HotInstallError('USB device communication component is not installed') from exc

    lockdown = await create_using_usbmux()
    try:
        apps = await InstallationProxyService(lockdown=lockdown).get_apps(application_type='User')
        matches = [(key, value) for key, value in apps.items()
                   if key == ORIGINAL_BUNDLE_ID or value.get('ALTBundleIdentifier') == ORIGINAL_BUNDLE_ID]
        if len(matches) != 1:
            raise HotInstallError('Expected exactly one installed SpplechOS app on the connected device')
        bundle_id, app = matches[0]
        entitlements = app.get('Entitlements') or {}
        team = entitlements.get('com.apple.developer.team-identifier', '')
        if not isinstance(team, str) or not team:
            raise HotInstallError('Installed app does not report its signing team')
        async with await HouseArrestService.create(lockdown, bundle_id, documents_only=True) as service:
            data = await service.get_file_contents('/Documents/.shell-host.json')
        identity = check_host(data, expected_bundle_id=bundle_id, expected_team_id=team)
        return DeviceShell(bundle_id, identity)
    finally:
        await lockdown.close()
