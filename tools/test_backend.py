#!/usr/bin/env python3
"""Exercise the real compiled backend against an AppLoad-shaped Linux socket."""
import argparse
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile


def send_message(connection, kind, text):
    payload = text.encode('utf-8')
    connection.sendall(struct.pack('<iI', kind, len(payload)))
    connection.sendall(payload)


def receive_message(connection):
    header = connection.recv(8, socket.MSG_TRUNC)
    assert len(header) == 8, f'Invalid header: {header!r}'
    kind, length = struct.unpack('<iI', header)
    payload = connection.recv(max(1, length), socket.MSG_TRUNC)
    assert len(payload) == length
    return kind, payload.decode('utf-8')


def session(binary, callback):
    with tempfile.TemporaryDirectory(prefix='ink-test-', dir='/tmp') as directory:
        path = str(Path(directory) / 'appload.sock')
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as server:
            server.settimeout(10)
            server.bind(path)
            server.listen(1)
            process = subprocess.Popen([binary, path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(5)
                    callback(connection)
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 0, (process.returncode, stdout, stderr)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()


def check_roundtrip(connection):
    send_message(connection, -2, '1')
    kind, description = receive_message(connection)
    assert kind == 101 and 'Kotlin/Native' in description and 'pid=' in description
    assert receive_message(connection) == (102, '0')
    for expected in ('1', '2'):
        send_message(connection, 2, 'increment')
        assert receive_message(connection) == (102, expected)
    send_message(connection, 1, 'Unicode: café ✓')
    kind, description = receive_message(connection)
    assert kind == 101 and 'Unicode: café ✓' in description
    assert receive_message(connection) == (102, '2')
    # No frontends, followed by a new frontend, must retain process state.
    send_message(connection, -3, '0')
    send_message(connection, -2, '1')
    assert receive_message(connection)[0] == 101
    assert receive_message(connection) == (102, '2')
    send_message(connection, 3, 'reset')
    assert receive_message(connection) == (102, '0')
    # Empty payload is a distinct packet, not a stream or missing record.
    send_message(connection, 1, '')
    assert receive_message(connection)[0] == 101
    assert receive_message(connection) == (102, '0')
    send_message(connection, 9, 'stop')
    assert receive_message(connection) == (103, 'stopping')


def check_host_shutdown(connection):
    send_message(connection, -1, 'close')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary')
    args = parser.parse_args()
    if not hasattr(socket, 'SOCK_SEQPACKET') or os.uname().sysname != 'Linux':
        parser.error('Run this protocol test on Linux; macOS Unix sockets do not provide this transport.')
    binary = str(Path(args.binary).resolve())
    subprocess.run([binary, '--self-test'], check=True, timeout=10)
    session(binary, check_roundtrip)
    session(binary, check_host_shutdown)
    session(binary, lambda connection: None)  # EOF also exits cleanly.
    print('PASS: native executable, message framing, UTF-8, counter, reattachment, stop, host shutdown and EOF')


if __name__ == '__main__':
    main()
