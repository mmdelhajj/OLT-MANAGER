#!/usr/bin/env python3
"""Test setting ONU description on OLT"""
import paramiko
import time

OLT_IP = "10.10.10.1"
USERNAME = "admin"
PASSWORD = "Julia@aboud$442464"
PON_PORT = 2
ONU_ID = 2
NEW_DESC = "TEST-CUSTOMER"

def test_set_description():
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
    time.sleep(2)
    while channel.recv_ready():
        channel.recv(65535)

    # Enter enable mode
    print("Entering enable mode...")
    channel.send("enable\n")
    time.sleep(1)
    while channel.recv_ready():
        channel.recv(65535)
    channel.send(PASSWORD + "\n")
    time.sleep(2)
    while channel.recv_ready():
        channel.recv(65535)

    # Enter config mode (correct command)
    print("Entering config mode...")
    channel.send("configure terminal\n")
    time.sleep(1)
    output = ""
    while channel.recv_ready():
        output += channel.recv(65535).decode('utf-8', errors='ignore')
    print(f"Config mode: {output}")

    # Enter interface
    print(f"Entering interface epon 0/{PON_PORT}...")
    channel.send(f"interface epon 0/{PON_PORT}\n")
    time.sleep(1)
    output = ""
    while channel.recv_ready():
        output += channel.recv(65535).decode('utf-8', errors='ignore')
    print(f"Interface: {output}")

    # Set description
    print(f"Setting onu {ONU_ID} description {NEW_DESC}...")
    channel.send(f"onu {ONU_ID} description {NEW_DESC}\n")
    time.sleep(1)
    output = ""
    while channel.recv_ready():
        output += channel.recv(65535).decode('utf-8', errors='ignore')
    print(f"After description: {output}")

    # Exit interface
    channel.send("exit\n")
    time.sleep(0.5)
    while channel.recv_ready():
        channel.recv(65535)

    # Exit config mode
    channel.send("exit\n")
    time.sleep(0.5)
    while channel.recv_ready():
        channel.recv(65535)

    # Save config
    print("Saving config...")
    channel.send("write\n")
    time.sleep(3)
    output = ""
    while channel.recv_ready():
        output += channel.recv(65535).decode('utf-8', errors='ignore')
    print(f"Write result: {output}")

    channel.close()
    client.close()
    print("\nDone! Description set successfully.")

if __name__ == "__main__":
    test_set_description()
