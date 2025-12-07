"""OLT SSH Connection and Config Parser"""
import re
import logging
import subprocess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import paramiko
from config import SSH_TIMEOUT, SSH_PORT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ONUData:
    """Parsed ONU data"""
    pon_port: int
    onu_id: int
    mac_address: str
    description: Optional[str] = None
    distance: Optional[int] = None  # Distance in meters
    rx_power: Optional[float] = None  # RX Power in dBm


class OLTConnector:
    """Handles SSH connection to VSOL EPON OLTs"""

    def __init__(self, ip: str, username: str, password: str, port: int = SSH_PORT):
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self.client: Optional[paramiko.SSHClient] = None

    def connect(self) -> bool:
        """Establish SSH connection to OLT"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=SSH_TIMEOUT,
                look_for_keys=False,
                allow_agent=False
            )
            logger.info(f"Connected to OLT at {self.ip}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to OLT at {self.ip}: {e}")
            raise ConnectionError(f"SSH connection failed: {e}")

    def disconnect(self):
        """Close SSH connection"""
        if self.client:
            self.client.close()
            self.client = None
            logger.info(f"Disconnected from OLT at {self.ip}")

    def execute_command(self, command: str, need_enable: bool = True) -> str:
        """Execute command on OLT and return output"""
        import time
        if not self.client:
            raise ConnectionError("Not connected to OLT")

        try:
            # Use invoke_shell for interactive session (VSOL OLTs often need this)
            channel = self.client.invoke_shell(width=200, height=1000)
            channel.settimeout(90)

            # Wait for initial prompt
            time.sleep(2)
            output = ""
            while channel.recv_ready():
                output += channel.recv(65535).decode('utf-8', errors='ignore')

            logger.info(f"Initial prompt received")

            # Enter enable mode if needed (VSOL OLTs require this for show running-config)
            if need_enable:
                logger.info("Entering enable mode...")
                channel.send("enable\n")
                time.sleep(1)

                # Read password prompt
                while channel.recv_ready():
                    output = channel.recv(65535).decode('utf-8', errors='ignore')

                # Send password
                channel.send(self.password + "\n")
                time.sleep(2)

                # Read response and check if we're in enable mode
                while channel.recv_ready():
                    output = channel.recv(65535).decode('utf-8', errors='ignore')

                if "#" in output:
                    logger.info("Successfully entered enable mode")
                else:
                    logger.warning(f"Enable mode response: {output[:100]}")

            logger.info(f"Sending command: {command}")

            # Send command
            channel.send(command + "\n")
            time.sleep(1)

            # Collect output with timeout
            result = ""
            max_wait = 90  # Max 90 seconds for large configs
            start_time = time.time()
            no_data_count = 0

            while time.time() - start_time < max_wait:
                if channel.recv_ready():
                    chunk = channel.recv(65535).decode('utf-8', errors='ignore')
                    result += chunk
                    no_data_count = 0

                    # Handle "More" pagination
                    if "--More--" in chunk or "-- More --" in chunk or "-More-" in chunk:
                        channel.send(" ")
                        time.sleep(0.3)
                else:
                    time.sleep(0.5)
                    no_data_count += 1
                    # If no data for 3 seconds and we have some result, break
                    if no_data_count >= 6 and len(result) > 100:
                        break

            channel.close()
            logger.info(f"Command completed, received {len(result)} bytes")
            return result

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise RuntimeError(f"Command failed: {e}")

    def get_running_config(self) -> str:
        """Get running config from OLT"""
        return self.execute_command("show running-config")

    def get_onu_status(self) -> str:
        """Get ONU status (online/offline)"""
        # Try common VSOL commands for ONU status
        try:
            return self.execute_command("show epon onu-info")
        except Exception:
            try:
                return self.execute_command("show epon active-onu")
            except Exception:
                return ""

    def set_onu_description(self, pon_port: int, onu_id: int, description: str) -> bool:
        """Set ONU description on the OLT (optimized for speed)"""
        import time

        # Create new connection for this operation
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False
            )

            channel = client.invoke_shell(width=200, height=1000)
            channel.settimeout(15)

            # Helper to drain buffer
            def drain():
                time.sleep(0.2)
                while channel.recv_ready():
                    channel.recv(65535)

            # Wait for initial prompt
            drain()

            # Enter enable mode and send password together
            channel.send("enable\n")
            drain()
            channel.send(self.password + "\n")
            drain()

            # Send all config commands rapidly
            safe_desc = description.replace(" ", "-").replace("'", "").replace('"', '')[:32] if description else ""

            # Enter config mode and interface
            channel.send("configure terminal\n")
            drain()
            channel.send(f"interface epon 0/{pon_port}\n")
            drain()

            # Set description
            if safe_desc:
                channel.send(f"onu {onu_id} description {safe_desc}\n")
            else:
                channel.send(f"no onu {onu_id} description\n")
            drain()

            # Exit and save - send all at once
            channel.send("exit\nexit\nwrite\n")
            time.sleep(1)  # Wait for write to complete
            drain()

            channel.close()
            logger.info(f"Set ONU 0/{pon_port}:{onu_id} description to '{safe_desc}'")
            return True

        except Exception as e:
            logger.error(f"Failed to set ONU description: {e}")
            raise RuntimeError(f"Failed to set description: {e}")
        finally:
            client.close()

    def reboot_onu(self, pon_port: int, onu_id: int) -> bool:
        """Reboot an ONU via SSH CLI command"""
        import time

        # Create new connection for this operation
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False
            )

            channel = client.invoke_shell(width=200, height=1000)
            channel.settimeout(15)

            # Helper to drain buffer
            def drain():
                time.sleep(0.3)
                while channel.recv_ready():
                    channel.recv(65535)

            # Wait for initial prompt
            drain()

            # Enter enable mode
            channel.send("enable\n")
            drain()
            channel.send(self.password + "\n")
            drain()

            # Enter config mode
            channel.send("config terminal\n")
            drain()

            # Enter interface epon mode
            channel.send(f"interface epon 0/{pon_port}\n")
            drain()

            # Send reset command - VSOL EPON OLT command
            # Format: reset onu auth onuid <onu-id>
            channel.send(f"reset onu auth onuid {onu_id}\n")
            time.sleep(1)
            drain()

            # Exit interface mode
            channel.send("exit\n")
            drain()

            channel.close()
            logger.info(f"Rebooted ONU 0/{pon_port}:{onu_id} on {self.ip}")
            return True

        except Exception as e:
            logger.error(f"Failed to reboot ONU: {e}")
            raise RuntimeError(f"Failed to reboot ONU: {e}")
        finally:
            client.close()


class ConfigParser:
    """Parser for VSOL OLT configuration output"""

    # Regex patterns for VSOL config
    INTERFACE_PATTERN = re.compile(r'interface epon 0/(\d+)', re.IGNORECASE)
    MAC_BINDING_PATTERN = re.compile(
        r'confirm onu mac ([0-9a-fA-F:]{17})\s+onuid\s+(\d+)',
        re.IGNORECASE
    )
    DESCRIPTION_PATTERN = re.compile(
        r'onu\s+(\d+)\s+description\s+(\S+)',
        re.IGNORECASE
    )
    # Alternative patterns for different VSOL firmware versions
    ALT_MAC_PATTERN = re.compile(
        r'epon\s+onu\s+(\d+)\s+mac\s+([0-9a-fA-F:]{17})',
        re.IGNORECASE
    )
    ONU_INFO_PATTERN = re.compile(
        r'0/(\d+):(\d+)\s+([0-9a-fA-F:]{17})\s+(\w+)',
        re.IGNORECASE
    )

    @classmethod
    def parse_running_config(cls, config: str) -> List[ONUData]:
        """Parse running-config output and extract ONU data"""
        onus: List[ONUData] = []
        current_pon_port: Optional[int] = None

        # First pass: collect MAC bindings per interface
        mac_bindings: Dict[Tuple[int, int], str] = {}  # (pon_port, onu_id) -> mac
        descriptions: Dict[Tuple[int, int], str] = {}  # (pon_port, onu_id) -> description

        lines = config.split('\n')
        for line in lines:
            line = line.strip()

            # Check for interface line
            interface_match = cls.INTERFACE_PATTERN.search(line)
            if interface_match:
                current_pon_port = int(interface_match.group(1))
                continue

            if current_pon_port is None:
                continue

            # Check for MAC binding
            mac_match = cls.MAC_BINDING_PATTERN.search(line)
            if mac_match:
                mac = mac_match.group(1).upper()
                onu_id = int(mac_match.group(2))
                mac_bindings[(current_pon_port, onu_id)] = mac
                continue

            # Alternative MAC pattern
            alt_mac_match = cls.ALT_MAC_PATTERN.search(line)
            if alt_mac_match:
                onu_id = int(alt_mac_match.group(1))
                mac = alt_mac_match.group(2).upper()
                mac_bindings[(current_pon_port, onu_id)] = mac
                continue

            # Check for description
            desc_match = cls.DESCRIPTION_PATTERN.search(line)
            if desc_match:
                onu_id = int(desc_match.group(1))
                description = desc_match.group(2)
                descriptions[(current_pon_port, onu_id)] = description

            # Reset on exit
            if line.lower() == 'exit' or line.startswith('!'):
                current_pon_port = None

        # Combine MAC bindings with descriptions
        for (pon_port, onu_id), mac in mac_bindings.items():
            description = descriptions.get((pon_port, onu_id))
            onus.append(ONUData(
                pon_port=pon_port,
                onu_id=onu_id,
                mac_address=mac,
                description=description
            ))

        logger.info(f"Parsed {len(onus)} ONUs from config")
        return onus

    @classmethod
    def parse_onu_status(cls, status_output: str) -> Dict[str, bool]:
        """Parse ONU status output to get online/offline state
        Returns dict of MAC -> is_online
        """
        online_macs: Dict[str, bool] = {}

        for line in status_output.split('\n'):
            # Pattern: 0/1:2  4C:D7:C8:F9:91:00  online
            match = cls.ONU_INFO_PATTERN.search(line)
            if match:
                mac = match.group(3).upper()
                status = match.group(4).lower()
                online_macs[mac] = status in ('online', 'up', 'active')

        return online_macs


def poll_olt(ip: str, username: str, password: str) -> Tuple[List[ONUData], Dict[str, bool]]:
    """Poll an OLT and return ONU data with status"""
    connector = OLTConnector(ip, username, password)
    try:
        connector.connect()

        # Get running config
        config = connector.get_running_config()
        onus = ConfigParser.parse_running_config(config)

        # Get ONU status
        status_output = connector.get_onu_status()
        status_map = ConfigParser.parse_onu_status(status_output)

        return onus, status_map

    finally:
        connector.disconnect()


# SNMP OIDs for VSOL OLT (Enterprise 37950) - ONU Registration Table
# OID: 1.3.6.1.4.1.37950.1.1.5.12.1.12.1.{column}.{index}
SNMP_ONU_REG_TABLE = "1.3.6.1.4.1.37950.1.1.5.12.1.12.1"
SNMP_ONU_PON_PORT_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.12.1.2"   # PON Port (INTEGER: 1-4)
SNMP_ONU_ID_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.12.1.3"         # ONU ID on port (INTEGER)
SNMP_ONU_STATUS_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.12.1.5"     # Online status (INTEGER: 1=online, 0=offline)
SNMP_ONU_MAC_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.12.1.6"        # MAC Address (STRING: "4c:d7:c8:f9:91:00")
SNMP_ONU_MODEL_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.12.1.7"      # ONU Model (STRING: "V2801S")

# ONU Extended Info Table (subtree 25) - indexed by PON.ONU
# OID: 1.3.6.1.4.1.37950.1.1.5.12.1.25.1.{column}.{pon}.{onu}
SNMP_ONU_INFO_TABLE = "1.3.6.1.4.1.37950.1.1.5.12.1.25.1"
SNMP_ONU_DESC_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.25.1.9"       # Description (STRING)
SNMP_ONU_DISTANCE_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.25.1.12"  # Distance in meters (INTEGER)

# ONU Optical Power Table (subtree 28) - RX Power measured at OLT
# OID: 1.3.6.1.4.1.37950.1.1.5.12.1.28.1.{column}.{index}
SNMP_ONU_OPTICAL_TABLE = "1.3.6.1.4.1.37950.1.1.5.12.1.28.1"
SNMP_ONU_OPTICAL_MAC_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.28.1.2"   # MAC Address (STRING)
SNMP_ONU_RX_POWER_OID = "1.3.6.1.4.1.37950.1.1.5.12.1.28.1.3"      # RX Power in dBm (STRING: "-22.08")


def get_opm_data_via_ssh(ip: str, username: str, password: str, port: int = 22) -> Dict[str, Dict[str, float]]:
    """
    Get OPM (Optical Power Monitor) data via SSH for ALL ONUs.
    Uses 'show onu opm-diag all' command in config mode.

    Returns dict of MAC -> {rx_power, tx_power, temperature, voltage, tx_bias}
    """
    import time

    opm_data: Dict[str, Dict[str, float]] = {}

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=ip,
            port=port,
            username=username,
            password=password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False
        )

        shell = client.invoke_shell(width=200, height=1000)
        shell.settimeout(60)
        time.sleep(2)

        # Clear initial banner
        while shell.recv_ready():
            shell.recv(65535)

        # Enter enable mode
        shell.send("enable\n")
        time.sleep(0.5)
        while shell.recv_ready():
            shell.recv(65535)
        shell.send(password + "\n")
        time.sleep(1)
        while shell.recv_ready():
            shell.recv(65535)

        # Enter config mode
        shell.send("configure terminal\n")
        time.sleep(0.5)
        while shell.recv_ready():
            shell.recv(65535)

        # Get OPM diagnostic data for all ONUs
        shell.send("show onu opm-diag all\n")

        # Collect output with paging support
        output = ""
        start_time = time.time()
        while True:
            time.sleep(0.5)
            if shell.recv_ready():
                chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                output += chunk

                # Handle --More-- paging
                if "--More--" in chunk:
                    shell.send(" ")

            # Timeout after 30 seconds
            if time.time() - start_time > 30:
                break

            # Check if command is done (prompt returned)
            if output.rstrip().endswith("#") and len(output) > 200:
                break

        # Also get ONU status for MAC/distance lookup
        shell.send("show onu status all\n")
        status_output = ""
        start_time = time.time()
        while True:
            time.sleep(0.5)
            if shell.recv_ready():
                chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                status_output += chunk
                if "--More--" in chunk:
                    shell.send(" ")
            if time.time() - start_time > 30:
                break
            if status_output.rstrip().endswith("#") and len(status_output) > 200:
                break

        shell.close()
        client.close()

        # Parse OPM data
        # Format: EPON0/1:1   39.69   3.38   14.75   2.56   -12.51
        # Columns: ONU-ID, Temperature, Voltage, TX Bias, TX Power, RX Power
        pon_onu_data: Dict[str, Dict[str, float]] = {}
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('EPON'):
                # Parse: EPON0/1:1   39.69   3.38   14.75   2.56   -12.51
                match = re.match(
                    r'EPON0/(\d+):(\d+)\s+'         # PON port : ONU ID
                    r'([\d.]+)\s+'                  # Temperature
                    r'([\d.]+)\s+'                  # Voltage
                    r'([\d.]+)\s+'                  # TX Bias
                    r'(-?[\d.]+)\s+'                # TX Power
                    r'(-?[\d.]+)',                  # RX Power
                    line
                )
                if match:
                    pon_port = match.group(1)
                    onu_id = match.group(2)
                    key = f"{pon_port}.{onu_id}"
                    pon_onu_data[key] = {
                        'temperature': float(match.group(3)),
                        'voltage': float(match.group(4)),
                        'tx_bias': float(match.group(5)),
                        'tx_power': float(match.group(6)),
                        'rx_power': float(match.group(7))
                    }

        # Parse status output to get MAC addresses
        # Format: EPON0/1:1   online    4C:D7:C8:F9:91:00    4188
        pon_onu_to_mac: Dict[str, str] = {}
        for line in status_output.split('\n'):
            line = line.strip()
            if line.startswith('EPON'):
                match = re.match(
                    r'EPON0/(\d+):(\d+)\s+\w+\s+'   # PON:ONU and status
                    r'([0-9a-fA-F:]{17})',          # MAC Address
                    line
                )
                if match:
                    pon_port = match.group(1)
                    onu_id = match.group(2)
                    mac = match.group(3).upper()
                    key = f"{pon_port}.{onu_id}"
                    pon_onu_to_mac[key] = mac

        # Convert PON.ONU keys to MAC keys
        for key, data in pon_onu_data.items():
            if key in pon_onu_to_mac:
                mac = pon_onu_to_mac[key]
                opm_data[mac] = data

        logger.info(f"SSH OPM poll for {ip}: found optical data for {len(opm_data)} ONUs")
        return opm_data

    except Exception as e:
        logger.error(f"SSH OPM poll failed for {ip}: {e}")
        return {}


def poll_olt_snmp(ip: str, community: str = "public") -> Tuple[List[ONUData], Dict[str, bool]]:
    """
    Poll OLT via SNMP for ONU data and status. Much faster than SSH (~2 seconds vs 30-60 seconds).

    Returns tuple of (list of ONUData, dict of MAC -> is_online status)

    SNMP OID structure (VSOL OLT Enterprise 37950):
    - 1.3.6.1.4.1.37950.1.1.5.12.1.12.1.2.X = PON Port (INTEGER: 1-4)
    - 1.3.6.1.4.1.37950.1.1.5.12.1.12.1.3.X = ONU ID on port (INTEGER)
    - 1.3.6.1.4.1.37950.1.1.5.12.1.12.1.5.X = Online Status (INTEGER: 1=online, 0=offline)
    - 1.3.6.1.4.1.37950.1.1.5.12.1.12.1.6.X = MAC Address (STRING: "4c:d7:c8:f9:91:00")
    """
    onus: List[ONUData] = []
    status_map: Dict[str, bool] = {}

    try:
        # Get PON ports
        port_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_PON_PORT_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get ONU IDs
        id_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_ID_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get status values
        status_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_STATUS_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get MAC addresses
        mac_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_MAC_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get descriptions from extended info table (subtree 25)
        desc_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_DESC_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get distance from extended info table (subtree 25)
        distance_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_DISTANCE_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get RX power from optical table (subtree 28)
        rx_power_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_RX_POWER_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get MAC addresses from optical table to correlate with RX power
        optical_mac_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_OPTICAL_MAC_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        if mac_result.returncode != 0 or status_result.returncode != 0:
            logger.warning(f"SNMP query failed for {ip}")
            return [], {}

        # Parse PON ports: index -> port number
        port_by_index: Dict[str, int] = {}
        for line in port_result.stdout.split('\n'):
            if 'INTEGER:' in line:
                match = re.search(r'\.2\.(\d+)\s*=\s*INTEGER:\s*(\d+)', line)
                if match:
                    idx = match.group(1)
                    port_by_index[idx] = int(match.group(2))

        # Parse ONU IDs: index -> onu_id
        id_by_index: Dict[str, int] = {}
        for line in id_result.stdout.split('\n'):
            if 'INTEGER:' in line:
                match = re.search(r'\.3\.(\d+)\s*=\s*INTEGER:\s*(\d+)', line)
                if match:
                    idx = match.group(1)
                    id_by_index[idx] = int(match.group(2))

        # Parse status: index -> is_online
        status_by_index: Dict[str, bool] = {}
        for line in status_result.stdout.split('\n'):
            if 'INTEGER:' in line:
                match = re.search(r'\.5\.(\d+)\s*=\s*INTEGER:\s*(\d+)', line)
                if match:
                    idx = match.group(1)
                    status = int(match.group(2))
                    status_by_index[idx] = (status == 1)

        # Parse MAC addresses: index -> MAC (already in correct format)
        mac_by_index: Dict[str, str] = {}
        for line in mac_result.stdout.split('\n'):
            if 'STRING:' in line:
                match = re.search(r'\.6\.(\d+)\s*=\s*STRING:\s*"?([0-9a-fA-F:]+)"?', line)
                if match:
                    idx = match.group(1)
                    mac = match.group(2).upper()
                    mac_by_index[idx] = mac

        # Parse descriptions from subtree 25 (indexed by PON.ONU)
        # OID format: .9.{pon}.{onu} = STRING: "description"
        desc_by_pon_onu: Dict[str, str] = {}
        for line in desc_result.stdout.split('\n'):
            if 'STRING:' in line:
                match = re.search(r'\.9\.(\d+)\.(\d+)\s*=\s*STRING:\s*"?([^"]*)"?', line)
                if match:
                    pon = match.group(1)
                    onu = match.group(2)
                    desc = match.group(3).strip()
                    if desc:  # Only store non-empty descriptions
                        desc_by_pon_onu[f"{pon}.{onu}"] = desc

        # Parse distance from subtree 25 (indexed by PON.ONU)
        # OID format: .12.{pon}.{onu} = INTEGER: distance
        distance_by_pon_onu: Dict[str, int] = {}
        for line in distance_result.stdout.split('\n'):
            if 'INTEGER:' in line:
                match = re.search(r'\.12\.(\d+)\.(\d+)\s*=\s*INTEGER:\s*(\d+)', line)
                if match:
                    pon = match.group(1)
                    onu = match.group(2)
                    distance = int(match.group(3))
                    distance_by_pon_onu[f"{pon}.{onu}"] = distance

        # Parse RX power from subtree 28 - need to correlate with MAC
        # Build MAC -> RX power map using optical_mac_result and rx_power_result
        optical_mac_by_index: Dict[str, str] = {}
        for line in optical_mac_result.stdout.split('\n'):
            if 'STRING:' in line:
                match = re.search(r'\.2\.(\d+)\s*=\s*STRING:\s*"?([0-9a-fA-F:]+)"?', line)
                if match:
                    idx = match.group(1)
                    mac = match.group(2).upper()
                    optical_mac_by_index[idx] = mac

        rx_power_by_index: Dict[str, float] = {}
        for line in rx_power_result.stdout.split('\n'):
            if 'STRING:' in line:
                match = re.search(r'\.3\.(\d+)\s*=\s*STRING:\s*"?(-?[\d.]+)"?', line)
                if match:
                    idx = match.group(1)
                    try:
                        rx_power = float(match.group(2))
                        rx_power_by_index[idx] = rx_power
                    except ValueError:
                        pass

        # Build MAC -> RX power lookup
        rx_power_by_mac: Dict[str, float] = {}
        for idx, mac in optical_mac_by_index.items():
            if idx in rx_power_by_index:
                rx_power_by_mac[mac] = rx_power_by_index[idx]

        # Combine all data
        for idx, mac in mac_by_index.items():
            pon_port = port_by_index.get(idx, 0)
            onu_id = id_by_index.get(idx, 0)
            is_online = status_by_index.get(idx, False)

            if pon_port > 0 and onu_id > 0:
                # Get description and distance using PON.ONU key
                pon_onu_key = f"{pon_port}.{onu_id}"
                description = desc_by_pon_onu.get(pon_onu_key)
                distance = distance_by_pon_onu.get(pon_onu_key)
                # Get RX power using MAC address
                rx_power = rx_power_by_mac.get(mac)

                onus.append(ONUData(
                    pon_port=pon_port,
                    onu_id=onu_id,
                    mac_address=mac,
                    description=description,
                    distance=distance,
                    rx_power=rx_power
                ))
                # Use (pon_port, onu_id) as key to handle duplicate MACs correctly
                # Each ONU on each PON port gets its own status entry
                status_key = f"{pon_port}:{onu_id}"
                status_map[status_key] = is_online

        logger.info(f"SNMP poll for {ip}: found {len(onus)} ONUs ({sum(1 for s in status_map.values() if s)} online)")
        return onus, status_map

    except subprocess.TimeoutExpired:
        logger.warning(f"SNMP timeout for {ip}")
        return [], {}
    except Exception as e:
        logger.error(f"SNMP poll failed for {ip}: {e}")
        return [], {}


# SNMP OIDs for traffic counters (IF-MIB)
# Uses 64-bit counters (ifHCInOctets/ifHCOutOctets) for accurate high-speed measurements
# NOTE: From OLT perspective, IN = data received FROM customer (upload), OUT = data sent TO customer (download)
# We swap them to show from CUSTOMER perspective: RX = download, TX = upload
SNMP_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"          # Interface description (EPONxxONUyy)
SNMP_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"   # OLT IN = Customer Upload (TX)
SNMP_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10" # OLT OUT = Customer Download (RX)


def get_traffic_counters_snmp(ip: str, community: str = "public") -> Dict[str, Dict[str, int]]:
    """
    Get traffic counters for all ONU interfaces via SNMP.

    Returns dict of MAC -> {rx_bytes, tx_bytes, if_index} where MAC is uppercase.
    The counters are cumulative - caller must calculate rate by comparing two polls.

    Uses IF-MIB 64-bit counters (ifHCInOctets/ifHCOutOctets).
    OLT updates counters approximately every 30 seconds.
    """
    traffic_data: Dict[str, Dict[str, int]] = {}

    try:
        # Get interface descriptions to find ONU interfaces
        # Format: "EPONxxONUyy description" or just "EPONxxONUyy"
        descr_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_IF_DESCR, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        if descr_result.returncode != 0:
            logger.warning(f"SNMP traffic poll failed for {ip}: interface descriptions unavailable")
            return {}

        # Parse interface descriptions to find ONU interfaces
        # Build ifIndex -> (pon_port, onu_id) mapping
        onu_interfaces: Dict[str, Tuple[int, int]] = {}  # ifIndex -> (pon, onu)
        for line in descr_result.stdout.split('\n'):
            if 'STRING:' in line and 'EPON' in line.upper():
                # Format 1: "EPON01ONU1 soloo12233" or "EPON0/1ONU1" (V1600D8 style)
                match = re.search(r'\.2\.(\d+)\s*=\s*STRING:\s*"?EPON0?/?(\d+)ONU(\d+)', line, re.IGNORECASE)
                if match:
                    if_index = match.group(1)
                    pon_port = int(match.group(2))
                    onu_id = int(match.group(3))
                    onu_interfaces[if_index] = (pon_port, onu_id)
                else:
                    # Format 2: "EPON0/3:1" (V1600G/V1601E style - colon separator)
                    match = re.search(r'\.2\.(\d+)\s*=\s*STRING:\s*"?EPON0/(\d+):(\d+)', line, re.IGNORECASE)
                    if match:
                        if_index = match.group(1)
                        pon_port = int(match.group(2))
                        onu_id = int(match.group(3))
                        onu_interfaces[if_index] = (pon_port, onu_id)

        if not onu_interfaces:
            logger.info(f"No ONU interfaces found for {ip}")
            return {}

        # Get RX bytes (64-bit counter)
        rx_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_IF_HC_IN_OCTETS, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get TX bytes (64-bit counter)
        tx_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_IF_HC_OUT_OCTETS, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Parse RX counters
        rx_by_index: Dict[str, int] = {}
        for line in rx_result.stdout.split('\n'):
            if 'Counter64:' in line:
                match = re.search(r'\.6\.(\d+)\s*=\s*Counter64:\s*(\d+)', line)
                if match:
                    if_index = match.group(1)
                    rx_bytes = int(match.group(2))
                    rx_by_index[if_index] = rx_bytes

        # Parse TX counters
        tx_by_index: Dict[str, int] = {}
        for line in tx_result.stdout.split('\n'):
            if 'Counter64:' in line:
                match = re.search(r'\.10\.(\d+)\s*=\s*Counter64:\s*(\d+)', line)
                if match:
                    if_index = match.group(1)
                    tx_bytes = int(match.group(2))
                    tx_by_index[if_index] = tx_bytes

        # Now we need to map PON.ONU to MAC address
        # Get MAC addresses from ONU registration table
        mac_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_MAC_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get PON ports from ONU registration table
        port_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_PON_PORT_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Get ONU IDs from ONU registration table
        id_result = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, ip, SNMP_ONU_ID_OID, "-t", "5"],
            capture_output=True, text=True, timeout=30
        )

        # Parse to build (pon, onu) -> MAC mapping
        mac_by_index: Dict[str, str] = {}
        port_by_index: Dict[str, int] = {}
        id_by_index: Dict[str, int] = {}

        for line in mac_result.stdout.split('\n'):
            if 'STRING:' in line:
                match = re.search(r'\.6\.(\d+)\s*=\s*STRING:\s*"?([0-9a-fA-F:]+)"?', line)
                if match:
                    idx = match.group(1)
                    mac = match.group(2).upper()
                    mac_by_index[idx] = mac

        for line in port_result.stdout.split('\n'):
            if 'INTEGER:' in line:
                match = re.search(r'\.2\.(\d+)\s*=\s*INTEGER:\s*(\d+)', line)
                if match:
                    idx = match.group(1)
                    port_by_index[idx] = int(match.group(2))

        for line in id_result.stdout.split('\n'):
            if 'INTEGER:' in line:
                match = re.search(r'\.3\.(\d+)\s*=\s*INTEGER:\s*(\d+)', line)
                if match:
                    idx = match.group(1)
                    id_by_index[idx] = int(match.group(2))

        # Build (pon, onu) -> MAC lookup
        pon_onu_to_mac: Dict[Tuple[int, int], str] = {}
        for idx, mac in mac_by_index.items():
            pon = port_by_index.get(idx)
            onu = id_by_index.get(idx)
            if pon and onu:
                pon_onu_to_mac[(pon, onu)] = mac

        # Combine: ifIndex -> (pon, onu) -> MAC -> traffic data
        # Handle duplicate MACs: prefer entry with actual traffic over zero traffic
        # IMPORTANT: Swap RX/TX to show from CUSTOMER perspective
        # - OLT ifHCInOctets (rx_by_index) = data received BY OLT = Customer UPLOAD
        # - OLT ifHCOutOctets (tx_by_index) = data sent BY OLT = Customer DOWNLOAD
        for if_index, (pon_port, onu_id) in onu_interfaces.items():
            mac = pon_onu_to_mac.get((pon_port, onu_id))
            if mac:
                # Swap: OLT's IN becomes customer's TX (upload), OLT's OUT becomes customer's RX (download)
                customer_tx_bytes = rx_by_index.get(if_index, 0)  # OLT IN = Customer Upload
                customer_rx_bytes = tx_by_index.get(if_index, 0)  # OLT OUT = Customer Download

                # If MAC already exists, only overwrite if new entry has more traffic
                # This handles cases where same MAC is registered at multiple (pon, onu) locations
                if mac in traffic_data:
                    existing = traffic_data[mac]
                    existing_total = existing['rx_bytes'] + existing['tx_bytes']
                    new_total = customer_rx_bytes + customer_tx_bytes
                    if new_total <= existing_total:
                        # Keep existing entry with more traffic
                        continue

                traffic_data[mac] = {
                    'rx_bytes': customer_rx_bytes,  # Customer Download
                    'tx_bytes': customer_tx_bytes,  # Customer Upload
                    'if_index': int(if_index),
                    'pon_port': pon_port,
                    'onu_id': onu_id
                }

        logger.info(f"SNMP traffic poll for {ip}: got counters for {len(traffic_data)} ONUs")
        return traffic_data

    except subprocess.TimeoutExpired:
        logger.warning(f"SNMP traffic timeout for {ip}")
        return {}
    except Exception as e:
        logger.error(f"SNMP traffic poll failed for {ip}: {e}")
        return {}


# Test function
if __name__ == "__main__":
    # Test config parsing with sample data
    sample_config = """
interface epon 0/1
confirm onu mac 4c:d7:c8:f9:91:00 onuid 1
confirm onu mac 4c:d7:c8:f9:86:94 onuid 3
onu 1 description CUSTOMER-ONE
onu 3 description CUSTOMER-THREE
exit

interface epon 0/2
confirm onu mac 4c:d7:c8:f9:92:11 onuid 2
confirm onu mac 4c:d7:c8:f9:93:22 onuid 5
onu 2 description NAJI-CENTER-AZZMI
onu 5 description MES-OFFICE
exit
"""
    onus = ConfigParser.parse_running_config(sample_config)
    for onu in onus:
        print(f"PON {onu.pon_port} ONU {onu.onu_id}: {onu.mac_address} - {onu.description}")
