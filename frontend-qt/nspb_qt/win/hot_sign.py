"""Sign a disposable framework copy with the installed SpplechOS identity.

Private keys remain in Sideloadly's directory. A matching installed provisioning
profile is used only in a temporary directory and is never sent to the device.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .hot_install import HostIdentity, HotInstallError, inspect_framework, ready_payload


async def sign_framework_copy(source: Path, destination: Path, title_id: str,
                              host: HostIdentity, lockdown, zsign: Path,
                              credential_dir: Path) -> Path:
    """Copy and sign a framework; reject ambiguous identities and unverified output."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.x509.oid import NameOID
    from pymobiledevice3.services.misagent import MisagentService

    manifest = inspect_framework(source, title_id)
    source, destination = Path(source), Path(destination)
    ready_payload(source, title_id)  # Reject links and unsupported files before copying.
    if destination.exists() or destination.name != source.name:
        raise HotInstallError('Signing destination must be a new matching framework folder')
    key_path = Path(credential_dir) / 'key.pem'
    try:
        key = serialization.load_pem_private_key(key_path.read_bytes(), None)
        encode = lambda k: k.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        public = encode(key.public_key())
        candidates = []
        for cert_path in Path(credential_dir).glob('cert-*.pem'):
            cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            teams = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
            if encode(cert.public_key()) == public and any(t.value == host.team_id for t in teams):
                candidates.append((cert_path, cert))
        if len(candidates) != 1:
            raise HotInstallError('No unique Sideloadly certificate matches the installed app')
        cert_path, cert = candidates[0]
        async with MisagentService(lockdown) as service:
            profiles = await service.copy_all()
        matches = [p for p in profiles
                   if p.plist.get('Entitlements', {}).get('application-identifier') == host.team_id + '.' + host.bundle_id
                   and cert.public_bytes(serialization.Encoding.DER) in p.plist.get('DeveloperCertificates', [])]
        if len(matches) != 1:
            raise HotInstallError('No unique installed signing profile matches this app')
        shutil.copytree(source, destination, symlinks=False)
        binary = destination / manifest.get('framework_executable', f'DmGame{title_id.upper()}')
        before = hashlib.sha256(binary.read_bytes()).digest()
        with tempfile.TemporaryDirectory(prefix='spplechos-profile-') as tmp:
            profile = Path(tmp) / 'profile.mobileprovision'
            profile.write_bytes(matches[0].buf)
            signed = subprocess.run([str(zsign), '-f', '-k', str(key_path), '-c', str(cert_path),
                                     '-m', str(profile), '-b', host.bundle_id, str(binary)],
                                    capture_output=True, timeout=600)
        if signed.returncode or hashlib.sha256(binary.read_bytes()).digest() == before:
            raise HotInstallError('Framework signing failed')
        checked = subprocess.run([str(zsign), str(binary)], capture_output=True, text=True, errors='replace', timeout=120)
        output = checked.stdout
        identifier = re.search(r'(?m)^\s*identifier:\s*(\S+)\s*$', output)
        team = re.search(r'(?m)^\s*teamid:\s*(\S+)\s*$', output)
        if (checked.returncode or not identifier or identifier.group(1) != host.bundle_id
                or not team or team.group(1) != host.team_id or 'CSSLOT_SIGNATURESLOT' not in output
                or 'CSSLOT_ENTITLEMENTS:' in output or 'CSSLOT_DER_ENTITLEMENTS:' in output):
            raise HotInstallError('Signed framework identity could not be verified')
        return destination
    except HotInstallError:
        raise
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise HotInstallError('Could not prepare a signed game framework') from exc
