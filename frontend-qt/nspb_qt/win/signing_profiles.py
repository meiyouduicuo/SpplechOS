"""Choose an installed provisioning profile without accessing any private key."""
from datetime import datetime, timezone
from .hot_install import HotInstallError


def _utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def select_signing_profile(profiles, host, certificate_der: bytes, *, device_udid=None, now=None):
    """Renewals may leave several profiles. Keep app/cert/device binding exact."""
    now = _utc(now) or datetime.now(timezone.utc)
    matches = [p for p in profiles
               if p.plist.get('Entitlements', {}).get('application-identifier') == host.team_id + '.' + host.bundle_id
               and (not p.plist.get('TeamIdentifier') or host.team_id in p.plist['TeamIdentifier'])
               and p.plist.get('Entitlements', {}).get('com.apple.developer.team-identifier', host.team_id) == host.team_id]
    if not matches:
        raise HotInstallError('sign.profile.missing')
    matches = [p for p in matches if certificate_der in p.plist.get('DeveloperCertificates', [])]
    if not matches:
        raise HotInstallError('sign.profile.certificate')
    if isinstance(device_udid, str) and device_udid:
        matches = [p for p in matches if p.plist.get('ProvisionsAllDevices') is True
                   or device_udid in p.plist.get('ProvisionedDevices', [])]
        if not matches:
            raise HotInstallError('sign.profile.device')
    dated = [p for p in matches if _utc(p.plist.get('ExpirationDate')) is not None]
    if not dated:
        raise HotInstallError('sign.profile.undated')
    valid = [p for p in dated if _utc(p.plist['ExpirationDate']) > now
             and (_utc(p.plist.get('CreationDate')) or now) <= now]
    if not valid:
        raise HotInstallError('sign.profile.expired')
    # Ordering does not depend on the order returned by misagent. Duplicate
    # entries and old renewals do not make the valid profile ambiguous.
    return max(valid, key=lambda p: (_utc(p.plist['ExpirationDate']),
                                    _utc(p.plist.get('CreationDate')) or datetime.min.replace(tzinfo=timezone.utc),
                                    str(p.plist.get('UUID', ''))))


def profile_error_text(message: str, t) -> str:
    texts = {
        'sign.profile.missing': t('sign.profile.missing'),
        'sign.profile.certificate': t('sign.profile.certificate'),
        'sign.profile.device': t('sign.profile.device'),
        'sign.profile.undated': t('sign.profile.undated'),
        'sign.profile.expired': t('sign.profile.expired'),
    }
    return texts.get(message, message)
