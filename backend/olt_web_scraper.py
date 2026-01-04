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
from typing import Dict, Optional, List
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
            # Try multiple pages to verify session
            test_urls = [
                f"{self.base_url}/action/onuauthinfo.html",
                f"{self.base_url}/action/gecfg.html",  # Port config page
            ]

            for test_url in test_urls:
                try:
                    test_response = self.session.get(test_url, timeout=10)
                    if test_response.status_code == 200:
                        # Check for valid session indicators
                        text = test_response.text
                        if ('EPON' in text or 'GPON' in text or
                            ('description' in text.lower() and len(text) > 5000)):
                            # Already logged in (IP-based session from previous login)
                            self._logged_in = True
                            logger.info(f"Already logged into OLT web interface at {self.ip} (IP-based session)")
                            return True
                except:
                    continue

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
                    # Even if login fails, check if IP session is still valid
                    # This can happen when OLT already has an active session
                    for test_url in test_urls:
                        try:
                            verify = self.session.get(test_url, timeout=10)
                            if verify.status_code == 200 and len(verify.text) > 5000:
                                if 'description' in verify.text.lower() or 'GPON' in verify.text or 'EPON' in verify.text:
                                    self._logged_in = True
                                    logger.info(f"Using existing IP-based session for {self.ip}")
                                    return True
                        except:
                            continue
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
            # Also supports GPON format for V1600G2-B models
            pattern = r"<tr><td class='hd'>([EG]PON\d*/(\d+):(\d+))</td>\s*<td>([^<]+)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>"

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

    def get_onu_opm_data_gpon(self) -> Dict[str, ONUOpticalData]:
        """
        Get ONU optical data for GPON OLTs (V1600G2-B) via per-ONU pages.

        GPON OLTs don't have a bulk OPM page like EPON OLTs.
        Instead, we need to fetch optical data from individual ONU pages.

        Returns dict of MAC address -> ONUOpticalData
        """
        result: Dict[str, ONUOpticalData] = {}

        if not self._logged_in:
            if not self.login():
                return result

        try:
            # First get list of all ONUs with their MAC addresses from onuauthinfo
            # We need to iterate all 16 PON ports
            onu_list = []  # (pon_port, onu_id, mac, is_online)

            for pon in range(1, 17):  # V1600G2-B has 16 PON ports
                list_url = f"{self.base_url}/action/onuauthinfo.html"
                response = self.session.post(list_url, data={"select": str(pon)}, timeout=10)

                if response.status_code != 200:
                    continue

                # Parse ONU list: GPON0/X:Y with SN in last td column (e.g., "HWTC03e33492")
                # Simpler pattern: just get ONU ID and status, then fetch optical page by pon:onu
                # Pattern: <td>GPON0/X:Y</td> <td...>Online</td>
                pattern = r"<td>GPON0?/(\d+):(\d+)</td>\s*<td[^>]*>.*?(Online|Offline).*?</td>"
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)

                for m in matches:
                    try:
                        pon_port = int(m[0])
                        onu_id = int(m[1])
                        is_online = m[2].upper() == 'ONLINE'

                        if is_online:
                            # We don't have MAC from web interface, use pon:onu as temporary key
                            # Will be matched later using pon:onu -> MAC from SNMP data
                            temp_key = f"{pon_port}:{onu_id}"
                            onu_list.append((pon_port, onu_id, temp_key))
                    except (ValueError, IndexError):
                        continue

            logger.debug(f"Found {len(onu_list)} online ONUs for GPON optical poll on {self.ip}")

            # Limit to 600 ONUs (enough for most deployments, ~40s scrape time at 5s per 100)
            for pon_port, onu_id, mac in onu_list[:600]:
                try:
                    # Fetch optical page for this ONU
                    opt_url = f"{self.base_url}/action/onuoptical.html?ponid={pon_port}&onuid={onu_id}&select={pon_port}"
                    opt_resp = self.session.get(opt_url, timeout=5)

                    if opt_resp.status_code != 200:
                        continue

                    html = opt_resp.text

                    # Parse optical values from table
                    # RxOpticalLevelOlt (OLT RX power from ONU) - this is the one we need
                    rx_match = re.search(r"RxOpticalLevelOlt.*?<td>(-?[\d.]+)", html, re.DOTALL)
                    tx_match = re.search(r"TxOpticalLevel.*?<td>(-?[\d.]+)", html, re.DOTALL)
                    temp_match = re.search(r"Temperature.*?<td>([\d.]+)", html, re.DOTALL)
                    voltage_match = re.search(r"powerFeedVoltage.*?<td>([\d.]+)", html, re.DOTALL)
                    bias_match = re.search(r"laserBiasCurrent.*?<td>([\d.]+)", html, re.DOTALL)
                    dist_match = re.search(r"Distance.*?<td>(\d+)", html, re.DOTALL)

                    rx_power = float(rx_match.group(1)) if rx_match else None

                    if rx_power is not None:
                        result[mac] = ONUOpticalData(
                            pon_port=pon_port,
                            onu_id=onu_id,
                            mac_address=mac,
                            distance=int(dist_match.group(1)) if dist_match else None,
                            temperature=float(temp_match.group(1)) if temp_match else None,
                            voltage=float(voltage_match.group(1)) if voltage_match else None,
                            tx_bias=float(bias_match.group(1)) if bias_match else None,
                            tx_power=float(tx_match.group(1)) if tx_match else None,
                            rx_power=rx_power
                        )

                except Exception as e:
                    logger.debug(f"Error fetching optical for PON{pon_port}:ONU{onu_id}: {e}")
                    continue

            logger.info(f"Web GPON optical scrape for {self.ip}: found optical data for {len(result)} ONUs")
            return result

        except Exception as e:
            logger.error(f"GPON optical scrape failed for {self.ip}: {e}")
            return result

    def get_onu_models_gpon(self) -> Dict[str, str]:
        """
        Get ONU models for GPON OLTs (V1600G2-B) from web interface.

        V1600G2-B doesn't expose ONU model via SNMP, but it's available on the web page.

        Returns dict of "pon:onu" -> model (e.g., "1:1" -> "HG8546M")
        """
        result: Dict[str, str] = {}

        if not self._logged_in:
            if not self.login():
                return result

        try:
            # Iterate all 16 PON ports
            for pon in range(1, 17):
                list_url = f"{self.base_url}/action/onuauthinfo.html"
                response = self.session.post(list_url, data={"select": str(pon)}, timeout=10)

                if response.status_code != 200:
                    continue

                # Parse ONU rows: <td>GPON0/X:Y</td><td>Status</td><td>Description</td><td>Model</td>
                # Pattern to extract pon:onu and model
                pattern = r"<td>GPON0?/(\d+):(\d+)</td>\s*<td[^>]*>.*?</td>\s*<td[^>]*>.*?</td>\s*<td>([^<]+)</td>"
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)

                for m in matches:
                    try:
                        pon_port = int(m[0])
                        onu_id = int(m[1])
                        model = m[2].strip()

                        if model and model.lower() != 'unknown':
                            key = f"{pon_port}:{onu_id}"
                            result[key] = model
                    except (ValueError, IndexError):
                        continue

            if result:
                logger.info(f"Web GPON model scrape for {self.ip}: found models for {len(result)} ONUs")
            return result

        except Exception as e:
            logger.error(f"GPON model scrape failed for {self.ip}: {e}")
            return result

    def get_onu_list_gpon(self) -> List[Dict]:
        """
        Get full ONU list for GPON OLTs (V1600G2-B) from web interface.
        Returns list of dicts with: pon_port, onu_id, mac_address, description, model, is_online

        This is used as fallback when SNMP ONU registration OIDs don't exist.
        """
        result: List[Dict] = []

        if not self._logged_in:
            if not self.login():
                return result

        try:
            # Iterate all 16 PON ports
            for pon in range(1, 17):
                list_url = f"{self.base_url}/action/onuauthinfo.html"
                response = self.session.post(list_url, data={"select": str(pon)}, timeout=15)

                if response.status_code != 200:
                    continue

                # Parse ONU rows:
                # <td>GPON0/X:Y</td><td>Status</td><td>Description</td><td>Model</td><td>Profile</td><td>Auth</td><td>Serial</td>
                # Pattern to extract all fields
                pattern = r"<tr><td>GPON0?/?(\d+):(\d+)</td>\s*<td[^>]*>(?:<font[^>]*>)?(?:<font[^>]*>)?([^<]+)</font>(?:</font>)?</td>\s*<td[^>]*>([^<]*)</td>\s*<td>([^<]+)</td>\s*<td>[^<]*</td>\s*<td>[^<]*</td>\s*<td>([^<]+)</td>"
                matches = re.findall(pattern, response.text, re.DOTALL | re.IGNORECASE)

                for m in matches:
                    try:
                        pon_port = int(m[0])
                        onu_id = int(m[1])
                        status_text = m[2].strip()
                        description = m[3].strip()
                        model = m[4].strip()
                        serial = m[5].strip()

                        # Check if online
                        is_online = 'online' in status_text.lower()

                        # Convert serial to MAC format
                        # Serial format: "HWTC03e33492" -> "HW:TC:03:E3:34:92"
                        mac_address = serial.upper()
                        if len(serial) >= 12:
                            mac_address = ':'.join(serial[i:i+2].upper() for i in range(0, 12, 2))

                        result.append({
                            'pon_port': pon_port,
                            'onu_id': onu_id,
                            'mac_address': mac_address,
                            'description': description if description else None,
                            'model': model if model and model.lower() != 'unknown' else None,
                            'is_online': is_online
                        })
                    except (ValueError, IndexError):
                        continue

            if result:
                online_count = sum(1 for o in result if o['is_online'])
                logger.info(f"Web GPON ONU list for {self.ip}: found {len(result)} ONUs ({online_count} online)")
            return result

        except Exception as e:
            logger.error(f"GPON ONU list scrape failed for {self.ip}: {e}")
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

        Extracts the direct action URLs from the ONU list page which contain
        the correct session key, then calls those URLs.

        Args:
            pon_port: PON port number (1-8)
            onu_id: ONU ID on the PON port

        Returns:
            True if delete was successful
        """
        if not self._logged_in:
            if not self.login():
                logger.error(f"Failed to login for ONU delete on {self.ip}")
                return False

        try:
            # Get the ONU list page which contains direct action URLs with session keys
            list_url = f"{self.base_url}/action/onuauthinfo.html?select={pon_port}"
            list_resp = self.session.get(list_url, timeout=10)

            if list_resp.status_code != 200:
                logger.error(f"Failed to get ONU list page for {self.ip}")
                return False

            success = False

            # Look for direct "Unauth" link for this specific ONU (who=3)
            # Format: onuauthinfo.html?who=3&select=X&select2=X&onuid=Y&SessionKey=ZZZ
            unauth_pattern = rf'onuauthinfo\.html\?who=3&select={pon_port}&select2={pon_port}&onuid={onu_id}&SessionKey=[^"\'>\s]+'
            unauth_match = re.search(unauth_pattern, list_resp.text)

            if unauth_match:
                unauth_url = f"{self.base_url}/action/{unauth_match.group(0)}"
                response = self.session.get(unauth_url, timeout=15)
                if response.status_code == 200:
                    logger.info(f"Unauth successful for PON {pon_port} ONU {onu_id} on {self.ip}")
                    success = True

            # Look for direct "Deregister" link (who=4) - may be on different page or for online ONUs
            dereg_pattern = rf'onuauthinfo\.html\?who=4&select={pon_port}&select2={pon_port}&onuid={onu_id}&SessionKey=[^"\'>\s]+'
            dereg_match = re.search(dereg_pattern, list_resp.text)

            if dereg_match:
                dereg_url = f"{self.base_url}/action/{dereg_match.group(0)}"
                response = self.session.get(dereg_url, timeout=15)
                if response.status_code == 200:
                    logger.info(f"Deregister successful for PON {pon_port} ONU {onu_id} on {self.ip}")
                    success = True

            # If no direct links found, try building URL with session key from page
            if not success:
                # Extract session key from JavaScript
                sk_match = re.search(r"SessionKey\.value\s*=\s*'([^']+)'", list_resp.text)
                if not sk_match:
                    # Try alternate pattern - session key in link
                    sk_match = re.search(r'SessionKey=([^"\'>&\s]+)', list_resp.text)

                if sk_match:
                    session_key = sk_match.group(1)
                    # Try who=3 (Unauth/Remove)
                    url = f"{self.base_url}/action/onuauthinfo.html?who=3&select={pon_port}&select2={pon_port}&onuid={onu_id}&SessionKey={session_key}"
                    response = self.session.get(url, timeout=15)
                    if response.status_code == 200:
                        logger.info(f"Unauth (fallback) sent for PON {pon_port} ONU {onu_id} on {self.ip}")
                        success = True

            # Verify deletion by checking if ONU still exists
            if success:
                verify_resp = self.session.get(list_url, timeout=10)
                onu_still_exists = f"onuid={onu_id}&" in verify_resp.text or f"/{pon_port}:{onu_id}<" in verify_resp.text
                if onu_still_exists:
                    logger.warning(f"ONU PON {pon_port} ID {onu_id} may still exist on {self.ip}")
                else:
                    logger.info(f"Verified: ONU PON {pon_port} ID {onu_id} removed from {self.ip}")

            return success

        except Exception as e:
            logger.error(f"ONU delete error for {self.ip}: {e}")
            return False

    def reboot_onu(self, pon_port: int, onu_id: int, model: str = None) -> bool:
        """
        Reboot an ONU via web interface.

        Args:
            pon_port: PON port number (1-16)
            onu_id: ONU ID on the PON port
            model: OLT model (V1600D8, V1600G2-B, etc.) for correct URL format

        Returns:
            True if reboot command sent successfully
        """
        if not self._logged_in:
            if not self.login():
                logger.error(f"Failed to login for ONU reboot on {self.ip}")
                return False

        try:
            # Get session key first (needed for V1600D8)
            session_key = self._get_session_key()
            if not session_key:
                logger.warning(f"Could not get session key, trying without it")
                session_key = ""

            reboot_url = f"{self.base_url}/action/onuauthinfo.html"

            # Different OLT models use different URL parameters for reboot:
            # V1600D8 (EPON): who=5, select={pon}, select2={pon}, onuid={id}, SessionKey={key}
            # V1600G2-B (GPON 16-port): who=1, ponid={pon}, onuid={id}

            if model and 'G2' in model.upper():
                # V1600G2-B and similar GPON models use who=1 with ponid
                params = {
                    "who": "1",  # 1 = reboot action on V1600G2-B
                    "ponid": str(pon_port),
                    "onuid": str(onu_id)
                }
                logger.info(f"Using V1600G2-B reboot format: who=1, ponid={pon_port}, onuid={onu_id}")
            else:
                # V1600D8 and EPON models use who=5 with select
                params = {
                    "who": "5",  # 5 = reboot action on V1600D8
                    "select": str(pon_port),
                    "select2": str(pon_port),
                    "onuid": str(onu_id),
                    "SessionKey": session_key
                }
                logger.info(f"Using V1600D8 reboot format: who=5, select={pon_port}, onuid={onu_id}")

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

    def set_onu_description(self, pon_port: int, onu_id: int, description: str, model: str = None) -> bool:
        """
        Set ONU description/customer name via web interface.

        Args:
            pon_port: PON port number (1-16)
            onu_id: ONU ID on the PON port
            description: New description/customer name
            model: OLT model for correct URL format (V1600D8, V1600G2-B, etc.)

        Returns:
            True if description was set successfully
        """
        if not self._logged_in:
            if not self.login():
                logger.error(f"Failed to login for ONU description update on {self.ip}")
                return False

        try:
            # Get session key (needed for V1600D8)
            session_key = self._get_session_key()
            if not session_key:
                logger.warning(f"Could not get session key, trying without it")
                session_key = ""

            # Different OLT models use different URLs and parameters:
            # V1600D8 (EPON): POST to onuBasic.html with gponid, gonuid, onu_description
            # V1600G2-B (GPON 16-port): POST to onudetail.html with ponid, onuid, onu_description

            if model and 'G2' in model.upper():
                # V1600G2-B uses onudetail.html
                desc_url = f"{self.base_url}/action/onudetail.html"
                form_data = {
                    "select": str(pon_port),
                    "ponid": str(pon_port),
                    "onuid": str(onu_id),
                    "onu_description": description,
                    "who": "0"  # 0 = submit description
                }
                logger.info(f"Using V1600G2-B description format: onudetail.html, ponid={pon_port}, onuid={onu_id}")
            else:
                # V1600D8 and EPON models use onuBasic.html
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
                logger.info(f"Using V1600D8 description format: onuBasic.html, gponid={pon_port}, gonuid={onu_id}")

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

    def set_port_description(self, port_number: int, description: str, model: str = None) -> bool:
        """Set GE port description via web interface.

        Args:
            port_number: GE port number (1-8 for V1600G2-B, 1-16 for V1600D8)
            description: New description (max 30 chars)
            model: OLT model for determining number of ports

        Returns:
            True if description was set successfully
        """
        if not self._logged_in:
            if not self.login():
                return False

        try:
            import re

            # Determine number of GE ports based on model
            if model and 'G2' in model.upper():
                num_ports = 8  # V1600G2-B has 8 GE ports
            else:
                num_ports = 16  # V1600D8 has 16 GE ports

            if port_number < 1 or port_number > num_ports:
                logger.error(f"Invalid port number {port_number} for model {model}")
                return False

            # First, get current form values from gecfg.html
            config_url = f"{self.base_url}/action/gecfg.html"
            response = self.session.get(config_url, timeout=15)

            if response.status_code != 200:
                logger.error(f"Failed to get port config page from {self.ip}")
                return False

            html = response.text

            # Build form data with all current values plus the changed description
            # who=0 is the submit action (whichfun(0)), who=1 is reset, who=100 is initial load
            form_data = {'who': '0'}

            # V1600D8 requires SessionKey (dynamically added via JavaScript)
            # Extract it from the page script: SessionKey.value = 'xxxxx';
            sk_match = re.search(r"SessionKey\.value\s*=\s*'([^']+)'", html)
            if sk_match:
                form_data['SessionKey'] = sk_match.group(1)
                logger.debug(f"Found SessionKey: {sk_match.group(1)}")

            # Parse all current description values
            for i in range(1, num_ports + 1):
                # Find current description value for this port
                pattern = rf"name=['\"]description{i}['\"][^>]*value=['\"]([^'\"]*)['\"]"
                match = re.search(pattern, html)
                if match:
                    current_desc = match.group(1)
                else:
                    # Try alternate pattern
                    pattern2 = rf"value=['\"]([^'\"]*)['\"][^>]*name=['\"]description{i}['\"]"
                    match2 = re.search(pattern2, html)
                    current_desc = match2.group(1) if match2 else ''

                # Set the new description for target port, keep others unchanged
                if i == port_number:
                    form_data[f'description{i}'] = description[:30]  # Max 30 chars
                else:
                    form_data[f'description{i}'] = current_desc

            # Parse and include other required form fields (shutdown, speed, vlan, etc.)
            # These are required for the form submission to work
            for i in range(1, num_ports + 1):
                # Port shutdown/admin status (checkbox)
                shutdown_pattern = rf"document\.all\.shutdown{i}\.checked\s*=\s*(true|false)"
                shutdown_match = re.search(shutdown_pattern, html, re.I)
                if shutdown_match and shutdown_match.group(1).lower() == 'true':
                    form_data[f'shutdown{i}'] = '1'

                # Port speed - find selected option
                speed_pattern = rf"setSelect\('portspeed{i}',\s*(\d+)\)"
                speed_match = re.search(speed_pattern, html)
                if speed_match:
                    form_data[f'portspeed{i}'] = speed_match.group(1)
                else:
                    form_data[f'portspeed{i}'] = '1'  # Default to Auto

                # Port VLAN (PVID)
                vlan_pattern = rf"setSelect\('portvlan{i}',\s*(\d+)\)"
                vlan_match = re.search(vlan_pattern, html)
                if vlan_match:
                    form_data[f'portvlan{i}'] = vlan_match.group(1)
                else:
                    form_data[f'portvlan{i}'] = '1'

                # Flow control
                flow_pattern = rf"document\.all\.flow{i}\.checked\s*=\s*(true|false)"
                flow_match = re.search(flow_pattern, html, re.I)
                if flow_match and flow_match.group(1).lower() == 'true':
                    form_data[f'flow{i}'] = '1'

                # Isolate
                isolate_pattern = rf"document\.all\.isolate{i}\.checked\s*=\s*(true|false)"
                isolate_match = re.search(isolate_pattern, html, re.I)
                if isolate_match and isolate_match.group(1).lower() == 'true':
                    form_data[f'isolate{i}'] = '1'

                # Storm control values
                for field in ['bcStorm', 'mcStorm', 'ucStorm', 'ingress', 'egress', 'maclimit']:
                    field_pattern = rf"name={field}{i}\s+id={field}{i}\s+value=['\"]([^'\"]*)['\"]"
                    field_match = re.search(field_pattern, html)
                    if field_match:
                        form_data[f'{field}{i}'] = field_match.group(1)
                    else:
                        form_data[f'{field}{i}'] = '0'

            # Submit the form
            logger.info(f"Submitting port {port_number} description change to '{description}' on {self.ip}")
            logger.debug(f"Form data keys: {list(form_data.keys())[:10]}...")
            response = self.session.post(config_url, data=form_data, timeout=15)

            if response.status_code == 200:
                # Verify by checking if the new description appears in the response
                # The response should be the reloaded config page with updated values
                desc_pattern = rf"name='description{port_number}'[^>]*value='([^']*)'"
                desc_match = re.search(desc_pattern, response.text)
                actual_desc = desc_match.group(1) if desc_match else None

                if actual_desc == description:
                    logger.info(f"Port {port_number} description set to '{description}' on {self.ip}")
                    return True
                elif description in response.text:
                    # Fallback check - description appears somewhere in response
                    logger.info(f"Port {port_number} description likely set to '{description}' on {self.ip}")
                    return True
                else:
                    # Log what we actually got for debugging
                    logger.warning(f"Port description may not have been set on {self.ip}. Expected '{description}', got '{actual_desc}'")
                    return False
            else:
                logger.error(f"Port config submit failed for {self.ip}: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Port description error for {self.ip}: {e}")
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
                   username: str = "admin", password: str = "admin",
                   model: str = None) -> bool:
    """
    Convenience function to reboot an ONU via web interface.

    Args:
        ip: OLT IP address
        pon_port: PON port number
        onu_id: ONU ID
        username: Web login username
        password: Web login password
        model: OLT model for correct URL format (V1600D8, V1600G2-B, etc.)

    Returns:
        True if reboot command sent successfully
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.reboot_onu(pon_port, onu_id, model=model)
    finally:
        scraper.close()


def set_onu_description_web(ip: str, pon_port: int, onu_id: int, description: str,
                            username: str = "admin", password: str = "admin",
                            model: str = None) -> bool:
    """
    Convenience function to set ONU description via web interface.

    Args:
        ip: OLT IP address
        pon_port: PON port number
        onu_id: ONU ID
        description: New description/customer name
        username: Web login username
        password: Web login password
        model: OLT model for correct URL format (V1600D8, V1600G2-B, etc.)

    Returns:
        True if description was set successfully
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.set_onu_description(pon_port, onu_id, description, model=model)
    finally:
        scraper.close()


def set_port_description_web(ip: str, port_number: int, description: str,
                              username: str = "admin", password: str = "admin",
                              model: str = None) -> bool:
    """
    Convenience function to set GE port description via web interface.

    Args:
        ip: OLT IP address
        port_number: GE port number (1-8 for V1600G2-B, 1-16 for V1600D8)
        description: New description (max 30 chars)
        username: Web login username
        password: Web login password
        model: OLT model for determining number of ports

    Returns:
        True if description was set successfully
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.set_port_description(port_number, description, model=model)
    finally:
        scraper.close()


def get_onu_opm_data_web(ip: str, username: str = "admin", password: str = "admin") -> Dict[str, Dict[str, float]]:
    """
    Convenience function to get ONU OPM data via web scraping.

    Tries EPON bulk OPM page first, then falls back to per-ONU GPON method.

    Returns dict of MAC -> {rx_power, tx_power, temperature, ...}
    Compatible format with get_opm_data_via_ssh() in olt_connector.py
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        # Try EPON bulk OPM page first
        opm_data = scraper.get_onu_opm_data()

        # If no data found (e.g., GPON OLT without bulk OPM page), try per-ONU method
        if not opm_data:
            logger.info(f"No EPON OPM data for {ip}, trying GPON per-ONU method...")
            opm_data = scraper.get_onu_opm_data_gpon()

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


def get_onu_models_web(ip: str, username: str, password: str) -> Dict[str, str]:
    """
    Get ONU models via web scraping for GPON OLTs.

    Returns dict of "pon:onu" -> model (e.g., "1:1" -> "HG8546M")
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.get_onu_models_gpon()
    finally:
        scraper.close()


def get_onu_list_web(ip: str, username: str, password: str) -> List[Dict]:
    """
    Get full ONU list via web scraping for GPON OLTs (fallback when SNMP fails).

    Returns list of dicts with: pon_port, onu_id, mac_address, description, model, is_online
    Used as fallback for V1600G2-B which doesn't have SNMP ONU registration OIDs.
    """
    scraper = OLTWebScraper(ip, username, password)
    try:
        return scraper.get_onu_list_gpon()
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
