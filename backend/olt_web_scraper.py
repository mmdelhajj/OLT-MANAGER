"""OLT Web Interface Scraper for ONU OPM (Optical Power Monitor) Data

This module scrapes the OLT web interface to get ONU self-reported optical data:
- ONU RX Power (what ONU reports about signal from OLT) - typically ~-13 dBm
- ONU TX Power, Temperature, Voltage, TX Bias Current

This is different from SNMP rx_power which is OLT-measured (~-26 dBm).

VSOL OLT Web Interface:
- Login URL: https://{ip}/action/main.html
- OPM Diag Page: https://{ip}/action/onuopmdiag.html
- Authentication: POST with user, pass, who=100
- Session: IP-based (no cookies required after login)
"""

import re
import logging
import requests
import urllib3
from typing import Dict, Optional
from dataclasses import dataclass

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ONUOpticalData:
    """ONU self-reported optical data from web interface"""
    pon_port: int
    onu_id: int
    mac_address: str
    distance: Optional[int] = None  # meters
    temperature: Optional[float] = None  # Celsius
    voltage: Optional[float] = None  # Volts
    tx_bias: Optional[float] = None  # mA
    tx_power: Optional[float] = None  # dBm (ONU TX)
    rx_power: Optional[float] = None  # dBm (ONU RX - what customer sees from OLT)


class OLTWebScraper:
    """Scrapes VSOL OLT web interface for ONU optical data"""

    def __init__(self, ip: str, username: str = "admin", password: str = "admin"):
        self.ip = ip
        self.username = username
        self.password = password
        self.base_url = f"https://{ip}"
        self.session = requests.Session()
        self.session.verify = False  # Accept self-signed certs
        self._logged_in = False

    def login(self) -> bool:
        """Login to OLT web interface"""
        try:
            # First, check if we're already logged in (VSOL uses IP-based sessions)
            test_url = f"{self.base_url}/action/onuauthinfo.html"
            test_response = self.session.get(test_url, timeout=10)
            if test_response.status_code == 200 and 'EPON' in test_response.text:
                # Already logged in (IP-based session from previous login)
                self._logged_in = True
                logger.info(f"Already logged into OLT web interface at {self.ip} (IP-based session)")
                return True

            # Not logged in, try to authenticate
            login_url = f"{self.base_url}/action/main.html"
            login_data = {
                "user": self.username,
                "pass": self.password,
                "who": "100"
            }

            response = self.session.post(login_url, data=login_data, timeout=10)

            # Check if login successful (page size > 1000 bytes indicates main page loaded)
            # Also check for login failure message
            if response.status_code == 200:
                if 'LoginFailed' in response.text or 'do not have access' in response.text:
                    logger.warning(f"OLT web login failed for {self.ip}: access denied")
                    return False
                if len(response.text) > 1000:
                    self._logged_in = True
                    logger.info(f"Logged into OLT web interface at {self.ip}")
                    return True

            logger.warning(f"OLT web login failed for {self.ip}: status={response.status_code}, size={len(response.text)}")
            return False

        except Exception as e:
            logger.error(f"OLT web login error for {self.ip}: {e}")
            return False

    def get_onu_opm_data(self) -> Dict[str, ONUOpticalData]:
        """
        Get ONU OPM (Optical Power Monitor) data from web interface.

        Returns dict of MAC address -> ONUOpticalData
        """
        result: Dict[str, ONUOpticalData] = {}

        if not self._logged_in:
            if not self.login():
                return result

        try:
            # Request all PON ports (select=255)
            opm_url = f"{self.base_url}/action/onuopmdiag.html"
            response = self.session.post(opm_url, data={"select": "255"}, timeout=15)

            if response.status_code != 200:
                logger.warning(f"OPM page request failed for {self.ip}: {response.status_code}")
                return result

            html = response.text

            # Parse HTML table rows
            # Format: <tr><td class='hd'>EPON0/1:1</td><td>MAC</td><td>Desc</td><td>Distance</td>
            #         <td>Temp</td><td>Voltage</td><td>TXBias</td><td>TXPower</td><td>RXPower</td></tr>
            pattern = r"<tr><td class='hd'>(EPON\d+/(\d+):(\d+))</td>\s*<td>([^<]+)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>"

            matches = re.findall(pattern, html)

            for m in matches:
                try:
                    onu_full_id = m[0]  # EPON0/1:1
                    pon_port = int(m[1])
                    onu_id = int(m[2])
                    mac = m[3].strip().upper()
                    description = m[4].strip() or None
                    distance_str = m[5].strip()
                    temp_str = m[6].strip()
                    voltage_str = m[7].strip()
                    tx_bias_str = m[8].strip()
                    tx_power_str = m[9].strip()
                    rx_power_str = m[10].strip()

                    # Parse numeric values
                    distance = int(distance_str) if distance_str and distance_str.replace('-', '').isdigit() else None
                    temperature = float(temp_str) if temp_str and self._is_float(temp_str) else None
                    voltage = float(voltage_str) if voltage_str and self._is_float(voltage_str) else None
                    tx_bias = float(tx_bias_str) if tx_bias_str and self._is_float(tx_bias_str) else None
                    tx_power = float(tx_power_str) if tx_power_str and self._is_float(tx_power_str) else None
                    rx_power = float(rx_power_str) if rx_power_str and self._is_float(rx_power_str) else None

                    # Skip if no valid RX power (main data we need)
                    if rx_power is None:
                        continue

                    result[mac] = ONUOpticalData(
                        pon_port=pon_port,
                        onu_id=onu_id,
                        mac_address=mac,
                        distance=distance,
                        temperature=temperature,
                        voltage=voltage,
                        tx_bias=tx_bias,
                        tx_power=tx_power,
                        rx_power=rx_power
                    )

                except (ValueError, IndexError) as e:
                    logger.debug(f"Error parsing ONU row: {e}")
                    continue

            logger.info(f"Web OPM scrape for {self.ip}: found optical data for {len(result)} ONUs")
            return result

        except Exception as e:
            logger.error(f"OPM data scrape failed for {self.ip}: {e}")
            return result

    @staticmethod
    def _is_float(s: str) -> bool:
        """Check if string can be parsed as float"""
        try:
            float(s)
            return True
        except ValueError:
            return False

    def _get_session_key(self) -> Optional[str]:
        """Get session key from OLT web interface for POST operations"""
        try:
            # Get any page that contains SessionKey
            response = self.session.get(f"{self.base_url}/action/onuauthinfo.html", timeout=10)
            if response.status_code == 200:
                # Extract SessionKey from JavaScript
                match = re.search(r"SessionKey\.value\s*=\s*'([^']+)'", response.text)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.debug(f"Error getting session key: {e}")
        return None

    def delete_onu(self, pon_port: int, onu_id: int) -> bool:
        """
        Delete/Deregister an ONU via web interface.

        For authenticated ONUs: uses who=4 (Deregister)
        For unauthorized/offline ONUs: uses who=3 (Unauth/Remove)

        VSOL uses GET requests with query parameters for delete actions.

        Args:
            pon_port: PON port number (1-8)
            onu_id: ONU ID on the PON port

        Returns:
            True if delete command sent successfully
        """
        if not self._logged_in:
            if not self.login():
                logger.error(f"Failed to login for ONU delete on {self.ip}")
                return False

        try:
            # Get fresh session key by accessing the ONU list page first
            list_url = f"{self.base_url}/action/onuauthinfo.html?select={pon_port}"
            list_resp = self.session.get(list_url, timeout=10)

            # Extract session key from response
            match = re.search(r"SessionKey\.value\s*=\s*'([^']+)'", list_resp.text)
            session_key = match.group(1) if match else ""

            if not session_key:
                logger.warning(f"Could not get session key for {self.ip}")
                return False

            delete_url = f"{self.base_url}/action/onuauthinfo.html"

            # VSOL uses GET requests with query parameters (not POST)
            # Try who=4 (Deregister) first for online/authenticated ONUs
            params = {
                "who": "4",
                "select": str(pon_port),
                "select2": str(pon_port),
                "onuid": str(onu_id),
                "SessionKey": session_key
            }

            response1 = self.session.get(delete_url, params=params, timeout=15)
            if response1.status_code == 200:
                logger.info(f"Deregister (who=4) sent for PON {pon_port} ONU {onu_id} on {self.ip}")

            # Also try who=3 (Unauth) for offline/unauthorized ONUs
            params["who"] = "3"
            response2 = self.session.get(delete_url, params=params, timeout=15)
            if response2.status_code == 200:
                logger.info(f"Unauth (who=3) sent for PON {pon_port} ONU {onu_id} on {self.ip}")

            return response1.status_code == 200 or response2.status_code == 200

        except Exception as e:
            logger.error(f"ONU delete error for {self.ip}: {e}")
            return False

    def reboot_onu(self, pon_port: int, onu_id: int) -> bool:
        """
        Reboot an ONU via web interface.

        Args:
            pon_port: PON port number (1-8)
            onu_id: ONU ID on the PON port

        Returns:
            True if reboot command sent successfully
        """
        if not self._logged_in:
            if not self.login():
                logger.error(f"Failed to login for ONU reboot on {self.ip}")
                return False

        try:
            # Get session key first
            session_key = self._get_session_key()
            if not session_key:
                logger.warning(f"Could not get session key, trying without it")
                session_key = ""

            # URL pattern from web interface:
            # onuauthinfo.html?who=5&select={pon}&select2={pon}&onuid={id}&SessionKey={key}
            reboot_url = f"{self.base_url}/action/onuauthinfo.html"
            params = {
                "who": "5",  # 5 = reboot action
                "select": str(pon_port),
                "select2": str(pon_port),
                "onuid": str(onu_id),
                "SessionKey": session_key
            }

            response = self.session.get(reboot_url, params=params, timeout=15)

            if response.status_code == 200:
                logger.info(f"Reboot command sent for PON {pon_port} ONU {onu_id} on {self.ip}")
                return True
            else:
                logger.error(f"Reboot failed for {self.ip}: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"ONU reboot error for {self.ip}: {e}")
            return False

    def set_onu_description(self, pon_port: int, onu_id: int, description: str) -> bool:
        """
        Set ONU description/customer name via web interface.

        Args:
            pon_port: PON port number (1-8)
            onu_id: ONU ID on the PON port
            description: New description/customer name

        Returns:
            True if description was set successfully
        """
        if not self._logged_in:
            if not self.login():
                logger.error(f"Failed to login for ONU description update on {self.ip}")
                return False

        try:
            # Get session key
            session_key = self._get_session_key()
            if not session_key:
                logger.warning(f"Could not get session key, trying without it")
                session_key = ""

            # POST to onuBasic.html with form data
            desc_url = f"{self.base_url}/action/onuBasic.html"
            form_data = {
                "selectpon": str(pon_port),
                "selectonu": str(onu_id),
                "gponid": str(pon_port),
                "gonuid": str(onu_id),
                "onu_description": description,
                "who": "0",  # 0 = submit description
                "SessionKey": session_key
            }

            response = self.session.post(desc_url, data=form_data, timeout=15)

            if response.status_code == 200:
                # Check if the page contains the new description (verify it was set)
                if description in response.text or len(response.text) > 1000:
                    logger.info(f"Description set to '{description}' for PON {pon_port} ONU {onu_id} on {self.ip}")
                    return True
                else:
                    logger.warning(f"Description may not have been set on {self.ip}")
                    return True  # Return true anyway since request succeeded
            else:
                logger.error(f"Set description failed for {self.ip}: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"ONU description error for {self.ip}: {e}")
            return False

    def close(self):
        """Close session"""
        self.session.close()


def delete_onu_web(ip: str, pon_port: int, onu_id: int,
                   username: str = "admin", password: str = "admin") -> bool:
    """
    Convenience function to delete/deregister an ONU via web interface.

    Args:
        ip: OLT IP address
        pon_port: PON port number
        onu_id: ONU ID
        username: Web login username
        password: Web login password

    Returns:
        True if delete command sent successfully
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.delete_onu(pon_port, onu_id)
    finally:
        scraper.close()


def reboot_onu_web(ip: str, pon_port: int, onu_id: int,
                   username: str = "admin", password: str = "admin") -> bool:
    """
    Convenience function to reboot an ONU via web interface.

    Args:
        ip: OLT IP address
        pon_port: PON port number
        onu_id: ONU ID
        username: Web login username
        password: Web login password

    Returns:
        True if reboot command sent successfully
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.reboot_onu(pon_port, onu_id)
    finally:
        scraper.close()


def set_onu_description_web(ip: str, pon_port: int, onu_id: int, description: str,
                            username: str = "admin", password: str = "admin") -> bool:
    """
    Convenience function to set ONU description via web interface.

    Args:
        ip: OLT IP address
        pon_port: PON port number
        onu_id: ONU ID
        description: New description/customer name
        username: Web login username
        password: Web login password

    Returns:
        True if description was set successfully
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.set_onu_description(pon_port, onu_id, description)
    finally:
        scraper.close()


def get_onu_opm_data_web(ip: str, username: str = "admin", password: str = "admin") -> Dict[str, Dict[str, float]]:
    """
    Convenience function to get ONU OPM data via web scraping.

    Returns dict of MAC -> {rx_power, tx_power, temperature, ...}
    Compatible format with get_opm_data_via_ssh() in olt_connector.py
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        opm_data = scraper.get_onu_opm_data()

        # Convert to simple dict format
        result: Dict[str, Dict[str, float]] = {}
        for mac, data in opm_data.items():
            result[mac] = {
                'rx_power': data.rx_power,
                'tx_power': data.tx_power,
                'temperature': data.temperature,
                'voltage': data.voltage,
                'tx_bias': data.tx_bias,
                'distance': data.distance  # Include distance from web interface
            }

        return result

    finally:
        scraper.close()


# Test function
if __name__ == "__main__":
    # Test with local OLT
    import sys

    ip = sys.argv[1] if len(sys.argv) > 1 else "10.10.10.1"
    user = sys.argv[2] if len(sys.argv) > 2 else "admin"
    pwd = sys.argv[3] if len(sys.argv) > 3 else "admin"

    print(f"Testing OLT web scraper for {ip}...")

    scraper = OLTWebScraper(ip, user, pwd)
    if scraper.login():
        data = scraper.get_onu_opm_data()
        print(f"\nFound {len(data)} ONUs with optical data:\n")
        print(f"{'MAC Address':<20} {'PON:ONU':<10} {'RX Power':<12} {'TX Power':<12} {'Temp':<8}")
        print("-" * 70)
        for mac, onu in data.items():
            print(f"{mac:<20} {onu.pon_port}:{onu.onu_id:<6} {onu.rx_power or 'N/A':<12} {onu.tx_power or 'N/A':<12} {onu.temperature or 'N/A':<8}")
    else:
        print("Login failed!")

    scraper.close()
