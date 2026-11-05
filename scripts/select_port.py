"""Select an available loopback port without touching existing processes."""
import socket
import sys
import errno


def select_port(first, attempts=20):
    if not 1024 <= first <= 65535:
        raise ValueError('端口应在1024至65535之间。')
    for port in range(first, min(65536, first + attempts)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
            try:
                candidate.bind(('127.0.0.1', port))
            except OSError as exc:
                if exc.errno == errno.EADDRINUSE:
                    continue
                raise
            return port
    raise RuntimeError('候选端口均已占用，请设置另一个PORT。')


if __name__ == '__main__':
    try:
        print(select_port(int(sys.argv[1]) if len(sys.argv) > 1 else 8765))
    except (OSError, ValueError, RuntimeError) as exc:
        print('无法准备本地监听端口：%s' % exc, file=sys.stderr)
        raise SystemExit(1)
