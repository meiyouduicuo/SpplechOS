"""Streaming, uncompressed SpplechOS game packages. Never include keys or saves.

Wire format: SPPLPK01, uint64 little-endian JSON length, UTF-8 manifest,
then the listed regular files concatenated in order. Sizes are 64-bit.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import struct
import tempfile
from pathlib import Path

from .hot_install import HotInstallError, inspect_framework, ready_payload

MAGIC = b'SPPLPK01'
MAX_HEADER = 32 * 1024 * 1024
MAX_BYTES = 100 * 1024**3
CHUNK = 4 * 1024 * 1024


def _tree(root: Path, prefix: str):
    if root.is_symlink():
        raise HotInstallError('Package source contains a link')
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise HotInstallError('Package source contains a link or unsupported file')
        if path.is_file():
            yield prefix + '/' + path.relative_to(root).as_posix(), path, path.stat().st_size


def _digest(path: Path, size: int) -> str:
    result = hashlib.sha256()
    with path.open('rb') as source:
        left = size
        while left:
            chunk = source.read(min(left, CHUNK))
            if not chunk:
                raise HotInstallError('Package source is incomplete')
            result.update(chunk)
            left -= len(chunk)
    return result.hexdigest()


def write_package(destination: Path, *, title_id: str, bundle_id: str, team_id: str,
                  files, progress=None) -> Path:
    """Publish only a completely written package, hashing again during the copy."""
    if not re.fullmatch(r'[0-9A-F]{16}', title_id) or not bundle_id or not team_id:
        raise HotInstallError('Invalid package signing identity')
    files = list(files)
    names = [name for name, _, _ in files]
    if len(files) > 200_000 or len(set(n.casefold() for n in names)) != len(names):
        raise HotInstallError('Duplicate package paths')
    for name in names:
        parts = name.split('/')
        allowed = (parts[0] == 'framework' and len(parts) > 1 or
                   name == 'data/romfs.img' or
                   len(parts) > 2 and parts[:2] in (['data', 'msl'], ['data', 'aoc']))
        if not allowed or any(p in ('', '.', '..') or '\\' in p or ':' in p for p in parts):
            raise HotInstallError('Unsafe package path')
    total = sum(size for _, _, size in files)
    if total > MAX_BYTES or any(size < 0 for _, _, size in files):
        raise HotInstallError('Package size exceeds the supported limit')
    entries = []
    for index, (name, path, size) in enumerate(files):
        if progress:
            progress('hash', index, len(files))
        entries.append(dict(path=name, size=size, sha256=_digest(path, size)))
    manifest = dict(schema=1, titleID=title_id, bundleID=bundle_id, teamID=team_id, files=entries)
    header = json.dumps(manifest, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    if len(header) > MAX_HEADER:
        raise HotInstallError('Package manifest is too large')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.sppgame-', suffix='.part', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as target:
            target.write(MAGIC + struct.pack('<Q', len(header)) + header)
            done = 0
            for entry, (_, path, size) in zip(entries, files):
                digest = hashlib.sha256()
                with Path(path).open('rb') as source:
                    left = size
                    while left:
                        chunk = source.read(min(left, CHUNK))
                        if not chunk:
                            raise HotInstallError('Package source changed while exporting')
                        target.write(chunk)
                        digest.update(chunk)
                        left -= len(chunk)
                        done += len(chunk)
                        if progress:
                            progress('package', done, total)
                if digest.hexdigest() != entry['sha256']:
                    raise HotInstallError('Package source changed while exporting')
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def export_game_package(framework: Path, image: Path, destination: Path, identity,
                        *, romfs_tool: Path | None = None, shader_dir: Path | None = None, progress=None) -> Path:
    """Package an already signed framework and its matching data, DLC and shaders."""
    from ..refresh_flow import matches_romfs_identity

    manifest = inspect_framework(framework, framework.name.removeprefix('DmGame').removesuffix('.framework'))
    tid = manifest['title_id'].upper()
    ready_payload(framework, tid)
    if not matches_romfs_identity(image, manifest.get('romfs_identity', '')):
        raise HotInstallError('Game data does not match the framework')
    with image.open('rb') as source:
        header = source.read(32)
    if len(header) != 32:
        raise HotInstallError('Incomplete game image')
    magic, index, length, _ = struct.unpack('<8sQQQ', header)
    size = index + length
    if magic != b'DMROMFS1' or size < 32 or size > image.stat().st_size:
        raise HotInstallError('Invalid game image')
    with tempfile.TemporaryDirectory(prefix='sppgame-shaders-') as temporary:
        files = list(_tree(framework, 'framework'))
        inline_shaders = any(n.startswith('framework/msl/') or
                             re.fullmatch(r'framework/msl-[^/]+\.aar', n) for n, _, _ in files)
        files.append(('data/romfs.img', image, size))
        aoc = image.parent / 'aoc'
        if aoc.exists():
            files.extend(_tree(aoc, 'data/aoc'))
        if not inline_shaders and size != image.stat().st_size:
            if not romfs_tool or not romfs_tool.is_file():
                raise HotInstallError('Shader extraction tool is unavailable')
            spec = importlib.util.spec_from_file_location('_sppgame_romfs', romfs_tool)
            tool = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tool)
            info = tool.inspect_msl(str(image))
            if not info.get('has_trailer') or info.get('chain') != manifest.get('chain'):
                raise HotInstallError('Shaders do not match the framework')
            if progress:
                progress('extract', 0, 0)
            tool.extract_msl(str(image), temporary)
            files.extend(_tree(Path(temporary), 'data/msl'))
        elif not inline_shaders and (image.parent / 'msl').is_dir():
            files.extend(_tree(image.parent / 'msl', 'data/msl'))
        elif not inline_shaders and shader_dir and re.fullmatch(r'b-[A-Za-z0-9._-]+', manifest.get('chain', '')):
            packed = shader_dir / (manifest['chain'] + '.img')
            if packed.is_file() and not packed.is_symlink():
                files.append(('data/msl/' + packed.name, packed, packed.stat().st_size))
        if not any(n.startswith(('framework/msl/', 'data/msl/')) or
                   re.fullmatch(r'framework/msl-[^/]+\.aar', n) for n, _, _ in files):
            raise HotInstallError('Matching game shaders are missing')
        return write_package(destination, title_id=tid, bundle_id=identity.bundle_id,
                             team_id=identity.team_id, files=files, progress=progress)
