"""Read exported epaper interface names from a local ELF library; never load it."""
from pathlib import Path
import re
import shutil
import struct
import subprocess


def display_symbol_report(path):
    data = Path(path).read_bytes()
    if data[:6] != b'\x7fELF\x02\x01':
        raise RuntimeError('Expected a little-endian ELF64 display library')
    try:
        offset = struct.unpack_from('<Q', data, 40)[0]
        size, count = struct.unpack_from('<HH', data, 58)
        if size < 64 or count == 0:
            raise ValueError('Missing ELF section headers')
        sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset + size * i) for i in range(count)]
        names = []
        for section in sections:
            if section[1] != 11:  # SHT_DYNSYM
                continue
            strings = sections[section[6]]
            table = data[strings[4]:strings[4] + strings[5]]
            step = section[9]
            if step < 24:
                raise ValueError('Invalid symbol record size')
            for symbol_offset in range(section[4], section[4] + section[5], step):
                name, info, other, index, value, length = struct.unpack_from('<IBBHQQ', data, symbol_offset)
                if not name or not index:
                    continue  # Skip undefined imports.
                text = table[name:table.index(b'\0', name)].decode('utf-8', errors='replace')
                if any(token in text for token in ('EPFramebuffer', 'EPContent', 'ScreenMode',
                                                   'Ghost', 'Refresh', 'Acep', 'Swtcon')):
                    names.append(text)
    except (struct.error, ValueError, IndexError) as error:
        raise RuntimeError(f'Cannot parse display library symbols: {error}') from error
    lines = sorted(set(names))
    demangler = shutil.which('c++filt')
    if demangler and lines:
        result = subprocess.run([demangler], input='\n'.join(lines) + '\n', capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            lines = result.stdout.splitlines()
    settings = sorted({token.decode('ascii') for token in re.findall(rb'[ -~]{6,}', data)
                       if re.search(rb'(QSG_|QT_|ghost|refresh|Ghost|Refresh)', token)
                       and not token.startswith(b'_Z')})
    return ('\n=== EXPORTED DISPLAY INTERFACES (names only; not invoked) ===\n'
            + '\n'.join(lines) + '\n=== RELEVANT LIBRARY STRINGS (up to 300) ===\n'
            + '\n'.join(settings[:300]) + '\n')
