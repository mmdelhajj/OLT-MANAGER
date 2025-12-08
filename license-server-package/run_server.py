#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()

import os
import sys
import json
import pty
import select
import struct
import fcntl
import termios
import subprocess
import socket as sock_lib
from gevent import spawn, sleep as gsleep
import signal
import re
from urllib.parse import unquote

from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketError
from geventwebsocket.handler import WebSocketHandler

# Import the Flask app
sys.path.insert(0, '/opt/license-server')
from license_server import app


def handle_terminal(ws, port, user='root', password=''):
    """Handle terminal WebSocket connection"""
    # URL decode the password in case it contains special characters
    password = unquote(password) if password else ''
    
    print(f'Terminal: port={port}, user={user}, pass_len={len(password)}', file=sys.stderr)
    
    # Check tunnel accessibility
    try:
        sock = sock_lib.socket(sock_lib.AF_INET, sock_lib.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0:
            ws.send(f'\r\n\x1b[31mError: Tunnel port {port} not accessible\x1b[0m\r\n')
            return
    except Exception as e:
        ws.send(f'\r\n\x1b[31mError checking tunnel: {e}\x1b[0m\r\n')
        return
    
    ws.send(f'\r\n\x1b[32mConnecting to SSH on port {port}...\x1b[0m\r\n')
    
    # Build SSH command
    if password:
        cmd = f"sshpass -p '{password}' ssh -tt -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {port} {user}@127.0.0.1"
    else:
        cmd = f"ssh -tt -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {port} {user}@127.0.0.1"
    
    # Create PTY
    master_fd, slave_fd = pty.openpty()
    
    # Set terminal size
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
    
    # Start SSH process
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
        close_fds=True
    )
    os.close(slave_fd)
    
    # Set master to non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    
    running = [True]
    
    def read_pty():
        """Read from PTY and send to WebSocket"""
        while running[0] and proc.poll() is None:
            try:
                rlist, _, _ = select.select([master_fd], [], [], 0.1)
                if master_fd in rlist:
                    try:
                        data = os.read(master_fd, 4096)
                        if data:
                            ws.send(data.decode('utf-8', errors='replace'))
                    except OSError:
                        pass
            except:
                pass
            gsleep(0.01)
    
    def read_ws():
        """Read from WebSocket and send to PTY"""
        while running[0] and proc.poll() is None:
            try:
                msg = ws.receive()
                if msg is None:
                    running[0] = False
                    break
                if msg:
                    try:
                        data = json.loads(msg)
                        if data.get('type') == 'input':
                            os.write(master_fd, data['data'].encode())
                        elif data.get('type') == 'resize':
                            rows = data.get('rows', 24)
                            cols = data.get('cols', 80)
                            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
                    except json.JSONDecodeError:
                        os.write(master_fd, msg.encode())
            except WebSocketError:
                running[0] = False
                break
            except:
                pass
            gsleep(0.01)
    
    # Start greenlets
    pty_reader = spawn(read_pty)
    ws_reader = spawn(read_ws)
    
    try:
        # Wait for either to finish
        while running[0] and proc.poll() is None:
            gsleep(0.1)
    except:
        pass
    finally:
        running[0] = False
        try:
            pty_reader.kill()
        except:
            pass
        try:
            ws_reader.kill()
        except:
            pass
        try:
            os.close(master_fd)
        except:
            pass
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            pass


class TerminalWebSocketHandler(WebSocketHandler):
    """Custom WebSocket handler that routes WebSocket requests"""
    
    def run_websocket(self):
        """Called when WebSocket has been created successfully"""
        path = self.environ.get('PATH_INFO', '')
        
        # Check if this is a terminal WebSocket request
        match = re.match(r'/ws/terminal/(\d+)', path)
        if match:
            port = int(match.group(1))
            
            # Parse query params
            query_string = self.environ.get('QUERY_STRING', '')
            params = {}
            for part in query_string.split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    params[k] = v
            
            user = params.get('user', 'root')
            password = params.get('pass', '')
            
            # URL decode the password
            password = unquote(password)
            
            print(f'DEBUG: user={user}, pass_len={len(password)}', file=sys.stderr)
            
            try:
                handle_terminal(self.websocket, port, user, password)
            except Exception as e:
                print(f'Error handling terminal: {e}', file=sys.stderr)
            
            # Cleanup
            if not self.websocket.closed:
                self.websocket.close()
            return
        
        # For non-terminal WebSocket requests, use default handling
        super().run_websocket()


if __name__ == '__main__':
    print('Starting License Server on port 5000...', file=sys.stderr)
    server = WSGIServer(('127.0.0.1', 5000), app, handler_class=TerminalWebSocketHandler)
    server.serve_forever()
