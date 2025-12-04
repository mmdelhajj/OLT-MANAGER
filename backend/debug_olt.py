#!/usr/bin/env python3
"""Debug script to test OLT SSH commands and see raw output"""
import paramiko
import time
import sys

OLT_IP = sys.argv[1] if len(sys.argv) > 1 else "10.10.10.1"
USERNAME = "admin"
PASSWORD = "Julia@aboud$442464"

def test_olt_commands():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"Connecting to {OLT_IP}...")
    client.connect(
        hostname=OLT_IP,
        port=22,
        username=USERNAME,
        password=PASSWORD,
        timeout=30,
        look_for_keys=False,
        allow_agent=False
    )
    print("Connected!")

    channel = client.invoke_shell(width=200, height=1000)
    channel.settimeout(60)

    # Wait for initial prompt
    time.sleep(3)
    output = ""
    while channel.recv_ready():
        output += channel.recv(65535).decode('utf-8', errors='ignore')

    print("=== Initial prompt ===")
    print(repr(output))
    print("=" * 50)

    # First try help/? to see available commands
    commands_to_try = [
        ("?", "List available commands"),
        ("show ?", "Show command options"),
        ("show epon ?", "Show EPON options"),
    ]

    for cmd, desc in commands_to_try:
        print(f"\n=== {desc}: {cmd} ===")
        channel.send(cmd + "\n")
        time.sleep(2)

        result = ""
        max_wait = 10
        start = time.time()
        no_data = 0

        while time.time() - start < max_wait:
            if channel.recv_ready():
                chunk = channel.recv(65535).decode('utf-8', errors='ignore')
                result += chunk
                no_data = 0
            else:
                time.sleep(0.5)
                no_data += 1
                if no_data >= 4 and len(result) > 20:
                    break

        print(f"Received {len(result)} bytes:")
        print(result[:3000])
        print("=" * 50)

    # Now try enable with same password
    print("\n=== Trying enable with same password ===")
    channel.send("enable\n")
    time.sleep(1)

    # Read password prompt
    result = ""
    while channel.recv_ready():
        result += channel.recv(65535).decode('utf-8', errors='ignore')
    print(f"After enable: {repr(result)}")

    # Send password
    channel.send(PASSWORD + "\n")
    time.sleep(2)

    result = ""
    while channel.recv_ready():
        result += channel.recv(65535).decode('utf-8', errors='ignore')
    print(f"After password: {repr(result)}")

    # Check if we're in enable mode now
    channel.send("\n")
    time.sleep(1)
    result = ""
    while channel.recv_ready():
        result += channel.recv(65535).decode('utf-8', errors='ignore')
    print(f"Current prompt: {repr(result)}")

    # If we're in enable mode, try show running-config
    print("\n=== Trying show running-config ===")
    channel.send("show running-config\n")
    time.sleep(3)

    result = ""
    max_wait = 30
    start = time.time()
    no_data = 0

    while time.time() - start < max_wait:
        if channel.recv_ready():
            chunk = channel.recv(65535).decode('utf-8', errors='ignore')
            result += chunk
            no_data = 0
            # Handle More pagination
            if "--More--" in chunk or "-- More --" in chunk or "-More-" in chunk:
                channel.send(" ")
                time.sleep(0.3)
        else:
            time.sleep(0.5)
            no_data += 1
            if no_data >= 6 and len(result) > 100:
                break

    print(f"Received {len(result)} bytes:")
    print(result[:5000])
    print("=" * 50)

    channel.close()
    client.close()
    print("\nDone!")

if __name__ == "__main__":
    test_olt_commands()
