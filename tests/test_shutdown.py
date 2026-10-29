import os
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import yaml


def test_ctrl_c_with_live_event_stream(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    config = {'server':{'host':'127.0.0.1','port':port},
              'database':{'path':str(tmp_path/'shutdown.db')},
              'monitoring':{'interval_seconds':1},
              'batteries':[{'id':'b','name':'Mock','connection':'mock'}]}
    path = tmp_path/'config.yaml'
    path.write_text(yaml.safe_dump(config))
    process = subprocess.Popen([sys.executable,'-m','power_monitor','serve','--config',str(path)],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    stream = None
    try:
        for _ in range(100):
            try:
                stream = urlopen(f'http://127.0.0.1:{port}/api/events', timeout=2)
                break
            except OSError:
                time.sleep(.05)
        assert stream is not None
        assert stream.readline().startswith(b'data: ')
        start = time.monotonic()
        process.send_signal(signal.SIGINT)
        process.wait(timeout=10)
        assert time.monotonic()-start < 8
    finally:
        if stream:
            stream.close()
        if process.poll() is None:
            process.kill()
        process.wait()
