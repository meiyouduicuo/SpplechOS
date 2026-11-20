"""Check the compiled forced-HLE registry before exporting a test framework."""
import argparse
from collections import Counter
from pathlib import Path
import struct


def verify_forced_hle(binary):
    data = Path(binary).read_bytes()
    if len(data) < 32 or struct.unpack_from('<I', data)[0] != 0xfeedfacf:
        raise ValueError('Expected a 64-bit little-endian Mach-O framework')
    segments, registry, chained = [], None, None
    position = 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, position)
        if size < 8 or position + size > len(data):
            raise ValueError('Invalid Mach-O load command')
        if command == 0x19:
            vm, virtual_size, offset, file_size = struct.unpack_from('<QQQQ', data, position + 24)
            segments.append((vm, offset, file_size))
            count = struct.unpack_from('<I', data, position + 64)[0]
            for i in range(count):
                section = position + 72 + i * 80
                if section + 80 > position + size:
                    raise ValueError('Invalid Mach-O section')
                name = data[section:section + 16].split(b'\0')[0]
                if name == b'swforce':
                    if registry is not None:
                        raise ValueError('Multiple forced-HLE sections')
                    length = struct.unpack_from('<Q', data, section + 40)[0]
                    start = struct.unpack_from('<I', data, section + 48)[0]
                    registry = start, length
        elif command == 0x80000034:
            chained = struct.unpack_from('<I', data, position + 8)[0]
        position += size
    formats = {}
    if chained is not None:
        starts = chained + struct.unpack_from('<I', data, chained + 4)[0]
        count = struct.unpack_from('<I', data, starts)[0]
        for i in range(count):
            relative = struct.unpack_from('<I', data, starts + 4 + i * 4)[0]
            if relative:
                formats[i] = struct.unpack_from('<H', data, starts + relative + 6)[0]
    if registry is None:
        raise ValueError('Framework has no forced-HLE registry')
    start, length = registry
    if length % 24 or start + length > len(data):
        raise ValueError('Invalid forced-HLE registry bounds')
    names = []
    for at in range(start, start + length, 24):
        pointer = struct.unpack_from('<Q', data, at)[0]
        for i, (vm, offset, file_size) in enumerate(segments):
            if offset <= at < offset + file_size and i in formats:
                if formats[i] not in (2, 6) or pointer >> 63:
                    raise ValueError('Unsupported chained pointer in forced-HLE registry')
                pointer = (pointer & ((1 << 36) - 1)) | (((pointer >> 36) & 0xff) << 56)
                if formats[i] == 6:
                    pointer += segments[0][0]
                break
        for vm, offset, file_size in segments:
            if vm <= pointer < vm + file_size:
                address = offset + pointer - vm
                end = data.find(b'\0', address, min(address + 4096, len(data)))
                if end < 0:
                    raise ValueError('Unterminated forced-HLE name')
                names.append(data[address:end].decode('ascii'))
                break
        else:
            raise ValueError('Forced-HLE name points outside the file-backed segments')
    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        raise ValueError('Duplicate forced-HLE registrations: ' + ', '.join(duplicates))
    return len(names)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    print(f'Validated {verify_forced_hle(args.binary)} unique forced-HLE registrations')
