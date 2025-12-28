"""FastAPI Main Application for OLT Manager"""
import asyncio
import logging
import requests
import bcrypt
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

import os
import sys
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Set
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel

from models import init_db, get_db, OLT, ONU, PollLog, Region, User, user_olts, Settings, TrafficSnapshot, TrafficHistory, Diagram, OLTPort, EventLog, ScheduledTask, ConfigBackup, AlertRule, SentAlert, SystemBackup, BackupSettings
from schemas import (
    OLTCreate, OLTUpdate, OLTResponse, OLTListResponse,
    ONUResponse, ONUListResponse, DashboardStats, PollResult,
    RegionCreate, RegionUpdate, RegionResponse, RegionListResponse,
    UserLogin, UserCreate, UserUpdate, UserResponse, UserListResponse, LoginResponse,
    DiagramCreate, DiagramUpdate, DiagramResponse, DiagramListResponse
)
from olt_connector import poll_olt_snmp, get_traffic_counters_snmp, get_olt_health_snmp, ONUData, OLTConnector
from olt_web_scraper import get_onu_opm_data_web
from trap_receiver import SimpleTrapReceiver, TrapEvent
from config import POLL_INTERVAL, encrypt_sensitive, decrypt_sensitive
from auth import (
    authenticate_user, create_access_token, get_password_hash,
    require_auth, require_admin, get_current_user, create_default_admin
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for blocking I/O operations (SNMP, web scraping, etc.)
thread_executor = ThreadPoolExecutor(max_workers=5)

# Cleanup counter - run cleanup every N poll cycles
cleanup_counter = 0
CLEANUP_INTERVAL_CYCLES = 60  # Run cleanup every 60 poll cycles (once per hour if polling every minute)

# Background polling task handle
polling_task: Optional[asyncio.Task] = None

# SNMP Trap receiver
trap_receiver: Optional[SimpleTrapReceiver] = None
trap_task: Optional[asyncio.Task] = None

# Weak signal alert tracking to prevent notification spam
# Format: {onu_id: datetime_of_last_alert}
# Alerts are suppressed for 1 hour after being sent
weak_signal_alert_cache: Dict[int, datetime] = {}
WEAK_SIGNAL_ALERT_COOLDOWN_HOURS = 1  # Don't re-alert for the same ONU within this time

# WebSocket connection manager for live traffic
class TrafficConnectionManager:
    """Manages WebSocket connections for live traffic updates"""
    def __init__(self):
        # olt_id -> set of websocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.traffic_tasks: Dict[int, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, olt_id: int):
        await websocket.accept()
        if olt_id not in self.active_connections:
            self.active_connections[olt_id] = set()
        self.active_connections[olt_id].add(websocket)
        logger.info(f"WebSocket connected for OLT {olt_id}. Total connections: {len(self.active_connections[olt_id])}")

    def disconnect(self, websocket: WebSocket, olt_id: int):
        if olt_id in self.active_connections:
            self.active_connections[olt_id].discard(websocket)
            if not self.active_connections[olt_id]:
                del self.active_connections[olt_id]
                # Stop traffic polling task if no connections
                if olt_id in self.traffic_tasks:
                    self.traffic_tasks[olt_id].cancel()
                    del self.traffic_tasks[olt_id]
        logger.info(f"WebSocket disconnected for OLT {olt_id}")

    async def broadcast(self, olt_id: int, message: dict):
        if olt_id in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[olt_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)
            # Clean up dead connections
            for conn in dead_connections:
                self.active_connections[olt_id].discard(conn)

traffic_manager = TrafficConnectionManager()


def parse_image_urls(image_urls_json: str) -> Optional[List[str]]:
    """Parse JSON image_urls field to list"""
    if not image_urls_json:
        return None
    try:
        return json.loads(image_urls_json)
    except:
        return None


def get_whatsapp_settings(db: Session) -> dict:
    """Get WhatsApp notification settings from database"""
    settings = {}
    for key in ['whatsapp_enabled', 'whatsapp_api_url', 'whatsapp_secret',
                'whatsapp_account', 'whatsapp_recipients']:
        setting = db.query(Settings).filter(Settings.key == key).first()
        if setting:
            settings[key] = setting.value
    return settings


def parse_whatsapp_recipients(recipients_json: str) -> list:
    """Parse JSON recipients field to list of {name, phone}"""
    if not recipients_json:
        return []
    try:
        recipients = json.loads(recipients_json)
        if isinstance(recipients, list):
            return recipients
        return []
    except:
        return []


def send_whatsapp_notification_batch(db: Session, online_onus: list, offline_onus: list, olt_name: str):
    """Send a single WhatsApp notification for all ONU status changes in a poll cycle"""
    try:
        # Log entry for debugging
        logger.info(f"send_whatsapp_notification_batch called: {len(online_onus)} online, {len(offline_onus)} offline for {olt_name}")

        # Skip if no changes
        if not online_onus and not offline_onus:
            logger.debug("No ONUs to notify about (both lists empty)")
            return

        # Check alarm settings
        alarm_settings = get_alarm_settings(db)

        # Check quiet hours
        if is_in_quiet_hours(alarm_settings):
            logger.info("Skipping ONU status notifications - quiet hours")
            return

        # Filter based on alarm settings
        online_alarm_enabled = is_alarm_enabled(alarm_settings, "onu_back_online")
        offline_alarm_enabled = is_alarm_enabled(alarm_settings, "onu_offline")
        logger.info(f"Alarm settings - onu_back_online: {online_alarm_enabled}, onu_offline: {offline_alarm_enabled}")

        filtered_online = online_onus if online_alarm_enabled else []
        filtered_offline = offline_onus if offline_alarm_enabled else []

        # Apply ONU/Region filtering based on alarm settings
        filtered_online = filter_onus_by_selection(filtered_online, alarm_settings)
        filtered_offline = filter_onus_by_selection(filtered_offline, alarm_settings)

        logger.info(f"After filtering - online: {len(filtered_online)}, offline: {len(filtered_offline)}")

        # Skip if nothing to notify after filtering
        if not filtered_online and not filtered_offline:
            logger.info("Skipping ONU status notifications - alarms disabled for these types or no ONUs to notify")
            return

        settings = get_whatsapp_settings(db)

        # Check if WhatsApp notifications are enabled (case-insensitive)
        if str(settings.get('whatsapp_enabled', '')).lower() != 'true':
            return

        api_url = settings.get('whatsapp_api_url', '').strip()
        secret = decrypt_sensitive(settings.get('whatsapp_secret', '')).strip()
        account = settings.get('whatsapp_account', '').strip()

        # Parse recipients (supports both old single recipient and new multiple format)
        recipients = parse_whatsapp_recipients(settings.get('whatsapp_recipients', ''))

        if not recipients:
            logger.warning("No WhatsApp recipients configured, skipping notification")
            return

        if not all([api_url, secret, account]):
            logger.warning("WhatsApp settings incomplete, skipping notification")
            return

        # Build consolidated message with detailed format
        message_parts = []

        # Add offline ONUs section
        for onu in filtered_offline:
            onu_name = onu.description if onu.description and onu.description.upper() != "NULL" else "No Name"
            region_name = onu.region.name if onu.region else "No Region"

            message_parts.append("🔴 *ONU OFFLINE*")
            message_parts.append("")
            message_parts.append(f"Description: {onu_name}")
            message_parts.append(f"OLT: {olt_name}")
            message_parts.append(f"Region: {region_name}")
            message_parts.append(f"MAC: {onu.mac_address}")
            message_parts.append(f"Port: {onu.pon_port}/{onu.onu_id}")
            # Add last signal before disconnect (prefer onu_rx_power from ONU, fallback to rx_power from OLT)
            last_signal = onu.onu_rx_power if onu.onu_rx_power is not None else onu.rx_power
            if last_signal is not None:
                message_parts.append(f"Last Signal: {last_signal} dBm")
            # Add last distance before disconnect
            if onu.distance is not None:
                distance_km = onu.distance / 1000 if onu.distance >= 1000 else None
                if distance_km:
                    message_parts.append(f"Last Distance: {distance_km:.2f} km ({onu.distance} m)")
                else:
                    message_parts.append(f"Last Distance: {onu.distance} m")
            if onu.latitude and onu.longitude:
                message_parts.append(f"Location: https://maps.google.com/?q={onu.latitude},{onu.longitude}")
            if onu.address:
                message_parts.append(f"Address: {onu.address}")
            message_parts.append("")
            message_parts.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("")
            message_parts.append("─" * 20)
            message_parts.append("")

        # Add online ONUs section
        for onu in filtered_online:
            onu_name = onu.description if onu.description and onu.description.upper() != "NULL" else "No Name"
            region_name = onu.region.name if onu.region else "No Region"

            message_parts.append("🟢 *ONU ONLINE*")
            message_parts.append("")
            message_parts.append(f"Description: {onu_name}")
            message_parts.append(f"OLT: {olt_name}")
            message_parts.append(f"Region: {region_name}")
            message_parts.append(f"MAC: {onu.mac_address}")
            message_parts.append(f"Port: {onu.pon_port}/{onu.onu_id}")
            if onu.latitude and onu.longitude:
                message_parts.append(f"Location: https://maps.google.com/?q={onu.latitude},{onu.longitude}")
            if onu.address:
                message_parts.append(f"Address: {onu.address}")
            message_parts.append("")
            message_parts.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("")
            message_parts.append("─" * 20)
            message_parts.append("")

        # Remove trailing separator
        if message_parts and message_parts[-1] == "":
            message_parts.pop()
        if message_parts and message_parts[-1] == "─" * 20:
            message_parts.pop()
        if message_parts and message_parts[-1] == "":
            message_parts.pop()

        message = "\n".join(message_parts)

        # Send WhatsApp message to all recipients
        success_count = 0
        for recipient in recipients:
            phone = recipient.get('phone', '').strip()
            name = recipient.get('name', 'Unknown')

            if not phone:
                continue

            try:
                response = requests.post(
                    api_url,
                    data={
                        'secret': secret,
                        'account': account,
                        'recipient': phone,
                        'type': 'text',
                        'message': message,
                        'priority': 1
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    success_count += 1
                    logger.info(f"WhatsApp notification sent to {name} ({phone})")
                else:
                    logger.error(f"WhatsApp notification failed for {name} ({phone}): {response.text}")
            except Exception as e:
                logger.error(f"Failed to send to {name} ({phone}): {e}")

        logger.info(f"WhatsApp batch notification: {success_count}/{len(recipients)} recipients, {len(filtered_offline)} offline, {len(filtered_online)} online")

    except Exception as e:
        logger.error(f"Failed to send WhatsApp notification: {e}")


def get_alarm_settings(db: Session) -> dict:
    """Get alarm settings from database"""
    settings = db.query(Settings).filter(Settings.key.like('alarm_%')).all()
    result = {}
    for s in settings:
        key = s.key.replace('alarm_', '')
        result[key] = s.value

    # Apply defaults
    defaults = {
        "new_onu_registration": "true",
        "onu_offline": "true",
        "onu_back_online": "true",
        "olt_offline": "true",
        "olt_back_online": "true",
        "weak_signal": "false",
        "weak_signal_threshold": "-25",
        "weak_signal_lower_threshold": "-30",
        "high_temperature": "false",
        "high_temperature_threshold": "60",
        "selected_onus": "[]",
        "selected_regions": "[]",
        "quiet_hours_enabled": "false",
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00"
    }
    for key, value in defaults.items():
        if key not in result:
            result[key] = value

    return result


def is_alarm_enabled(alarm_settings: dict, alarm_type: str) -> bool:
    """Check if a specific alarm type is enabled"""
    value = alarm_settings.get(alarm_type, "false")
    return str(value).lower() == "true"


def is_in_quiet_hours(alarm_settings: dict) -> bool:
    """Check if current time is within quiet hours"""
    if not is_alarm_enabled(alarm_settings, "quiet_hours_enabled"):
        return False

    try:
        now = datetime.now().time()
        start_str = alarm_settings.get("quiet_hours_start", "22:00")
        end_str = alarm_settings.get("quiet_hours_end", "07:00")

        start_parts = start_str.split(":")
        end_parts = end_str.split(":")

        start_time = datetime.strptime(f"{start_parts[0]}:{start_parts[1]}", "%H:%M").time()
        end_time = datetime.strptime(f"{end_parts[0]}:{end_parts[1]}", "%H:%M").time()

        # Handle overnight quiet hours (e.g., 22:00 to 07:00)
        if start_time > end_time:
            return now >= start_time or now <= end_time
        else:
            return start_time <= now <= end_time
    except Exception as e:
        logger.error(f"Error checking quiet hours: {e}")
        return False


def filter_onus_by_selection(onus: list, alarm_settings: dict) -> list:
    """Filter ONUs based on selected_onus and selected_regions in alarm settings.

    If no ONUs or regions are selected, returns all ONUs (no filtering).
    If specific ONUs are selected, only those ONUs will pass the filter.
    If specific regions are selected, only ONUs in those regions will pass the filter.
    If both are selected, ONUs matching either criterion will pass.
    """
    selected_onus_raw = alarm_settings.get("selected_onus", "[]")
    selected_regions_raw = alarm_settings.get("selected_regions", "[]")

    logger.info(f"filter_onus_by_selection - raw selected_onus: {repr(selected_onus_raw)}, raw selected_regions: {repr(selected_regions_raw)}")

    # Handle selected_onus - could be a list (already parsed) or a JSON string
    if isinstance(selected_onus_raw, list):
        selected_onus = selected_onus_raw
    elif isinstance(selected_onus_raw, str) and selected_onus_raw:
        try:
            selected_onus = json.loads(selected_onus_raw)
        except Exception as e:
            logger.error(f"Failed to parse selected_onus: {e}")
            selected_onus = []
    else:
        selected_onus = []

    # Handle selected_regions - could be a list (already parsed) or a JSON string
    if isinstance(selected_regions_raw, list):
        selected_regions = selected_regions_raw
    elif isinstance(selected_regions_raw, str) and selected_regions_raw:
        try:
            selected_regions = json.loads(selected_regions_raw)
        except Exception as e:
            logger.error(f"Failed to parse selected_regions: {e}")
            selected_regions = []
    else:
        selected_regions = []

    logger.info(f"filter_onus_by_selection - parsed selected_onus: {selected_onus}, parsed selected_regions: {selected_regions}")

    # If no specific ONUs or regions are selected, return all ONUs
    if not selected_onus and not selected_regions:
        logger.info("No ONU/Region filtering configured - returning all ONUs")
        return onus

    logger.info(f"Applying ONU/Region filter - selected_onus: {selected_onus}, selected_regions: {selected_regions}")

    def onu_matches_filter(onu):
        # Check if ONU ID is in selected_onus list
        if selected_onus and onu.id in selected_onus:
            return True
        # Check if ONU's region is in selected_regions list
        if selected_regions and onu.region_id and onu.region_id in selected_regions:
            return True
        # Didn't match any selection
        return False

    filtered = [onu for onu in onus if onu_matches_filter(onu)]
    logger.info(f"After ONU/Region filter: {len(filtered)} of {len(onus)} ONUs passed")
    return filtered


def send_new_onu_notification(db: Session, onu, olt_name: str):
    """Send WhatsApp notification for new ONU registration"""
    try:
        alarm_settings = get_alarm_settings(db)

        # Check if new ONU registration alarm is enabled
        if not is_alarm_enabled(alarm_settings, "new_onu_registration"):
            logger.debug("New ONU registration alarm is disabled")
            return

        # Check quiet hours
        if is_in_quiet_hours(alarm_settings):
            logger.debug("Skipping new ONU notification - quiet hours")
            return

        settings = get_whatsapp_settings(db)

        # Check if WhatsApp notifications are enabled
        if str(settings.get('whatsapp_enabled', '')).lower() != 'true':
            return

        api_url = settings.get('whatsapp_api_url', '').strip()
        secret = decrypt_sensitive(settings.get('whatsapp_secret', '')).strip()
        account = settings.get('whatsapp_account', '').strip()
        recipients = parse_whatsapp_recipients(settings.get('whatsapp_recipients', ''))

        if not recipients or not all([api_url, secret, account]):
            return

        # Build message with signal info
        message_parts = [
            "🆕 *NEW ONU REGISTERED*",
            "",
            f"MAC: {onu.mac_address}",
            f"OLT: {olt_name}",
            f"Port: {onu.pon_port}/{onu.onu_id}",
        ]

        # Add model if available
        if onu.model:
            message_parts.append(f"Model: {onu.model}")

        # Add signal information section
        signal_info = []
        if onu.distance is not None:
            signal_info.append(f"Distance: {onu.distance}m")
        if onu.onu_rx_power is not None:
            signal_info.append(f"RX Power: {onu.onu_rx_power} dBm")
        if onu.onu_tx_power is not None:
            signal_info.append(f"TX Power: {onu.onu_tx_power} dBm")
        if onu.onu_temperature is not None:
            signal_info.append(f"Temperature: {onu.onu_temperature}°C")
        if onu.onu_voltage is not None:
            signal_info.append(f"Voltage: {onu.onu_voltage}V")

        if signal_info:
            message_parts.append("")
            message_parts.append("📊 *Signal Info:*")
            message_parts.extend(signal_info)

        message_parts.append("")
        message_parts.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        message = "\n".join(message_parts)

        # Send to all recipients
        for recipient in recipients:
            phone = recipient.get('phone', '').strip()
            if not phone:
                continue

            try:
                response = requests.post(
                    api_url,
                    data={
                        'secret': secret,
                        'account': account,
                        'recipient': phone,
                        'type': 'text',
                        'message': message
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"New ONU notification sent to {phone}")
                else:
                    logger.warning(f"Failed to send new ONU notification to {phone}: {response.text}")
            except Exception as e:
                logger.error(f"Error sending new ONU notification to {phone}: {e}")

    except Exception as e:
        logger.error(f"Failed to send new ONU notification: {e}")


def send_olt_status_notification(db: Session, olt, is_online: bool):
    """Send WhatsApp notification for OLT status change"""
    try:
        alarm_settings = get_alarm_settings(db)

        # Check if appropriate alarm is enabled
        alarm_type = "olt_back_online" if is_online else "olt_offline"
        if not is_alarm_enabled(alarm_settings, alarm_type):
            logger.debug(f"OLT {alarm_type} alarm is disabled")
            return

        # Check quiet hours
        if is_in_quiet_hours(alarm_settings):
            logger.debug("Skipping OLT status notification - quiet hours")
            return

        settings = get_whatsapp_settings(db)

        # Check if WhatsApp notifications are enabled
        if str(settings.get('whatsapp_enabled', '')).lower() != 'true':
            return

        api_url = settings.get('whatsapp_api_url', '').strip()
        secret = decrypt_sensitive(settings.get('whatsapp_secret', '')).strip()
        account = settings.get('whatsapp_account', '').strip()
        recipients = parse_whatsapp_recipients(settings.get('whatsapp_recipients', ''))

        if not recipients or not all([api_url, secret, account]):
            return

        # Build message
        if is_online:
            emoji = "✅"
            status = "BACK ONLINE"
        else:
            emoji = "🔴"
            status = "OFFLINE"

        message_parts = [
            f"{emoji} *OLT {status}*",
            "",
            f"Name: {olt.name}",
            f"IP: {olt.ip_address}",
            "",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ]

        message = "\n".join(message_parts)

        # Send to all recipients
        for recipient in recipients:
            phone = recipient.get('phone', '').strip()
            if not phone:
                continue

            try:
                response = requests.post(
                    api_url,
                    data={
                        'secret': secret,
                        'account': account,
                        'recipient': phone,
                        'type': 'text',
                        'message': message
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"OLT status notification sent to {phone}")
                else:
                    logger.warning(f"Failed to send OLT status notification to {phone}: {response.text}")
            except Exception as e:
                logger.error(f"Error sending OLT status notification to {phone}: {e}")

    except Exception as e:
        logger.error(f"Failed to send OLT status notification: {e}")


def send_weak_signal_notification(db: Session, onus_with_weak_signal: list, olt_name: str, upper_threshold: float, lower_threshold: float):
    """Send WhatsApp notification for ONUs in the 'danger zone' (weak signal between thresholds)"""
    global weak_signal_alert_cache

    try:
        if not onus_with_weak_signal:
            return

        alarm_settings = get_alarm_settings(db)

        # Check if weak signal alarm is enabled
        if not is_alarm_enabled(alarm_settings, "weak_signal"):
            logger.debug("Weak signal alarm is disabled")
            return

        # Check quiet hours
        if is_in_quiet_hours(alarm_settings):
            logger.debug("Skipping weak signal notification - quiet hours")
            return

        # Apply ONU/Region filtering
        onus_with_weak_signal = filter_onus_by_selection(onus_with_weak_signal, alarm_settings)
        if not onus_with_weak_signal:
            logger.debug("No weak signal ONUs left after ONU/Region filtering")
            return

        settings = get_whatsapp_settings(db)

        # Check if WhatsApp notifications are enabled
        if str(settings.get('whatsapp_enabled', '')).lower() != 'true':
            return

        api_url = settings.get('whatsapp_api_url', '').strip()
        secret = decrypt_sensitive(settings.get('whatsapp_secret', '')).strip()
        account = settings.get('whatsapp_account', '').strip()
        recipients = parse_whatsapp_recipients(settings.get('whatsapp_recipients', ''))

        if not recipients or not all([api_url, secret, account]):
            return

        # Filter out ONUs that were recently alerted (within cooldown period)
        now = datetime.utcnow()
        cooldown_threshold = now - timedelta(hours=WEAK_SIGNAL_ALERT_COOLDOWN_HOURS)

        # Clean up old entries from cache
        expired_ids = [onu_id for onu_id, alert_time in weak_signal_alert_cache.items()
                       if alert_time < cooldown_threshold]
        for onu_id in expired_ids:
            del weak_signal_alert_cache[onu_id]

        # Filter to only ONUs that haven't been alerted recently
        onus_to_alert = []
        for onu in onus_with_weak_signal:
            if onu.id not in weak_signal_alert_cache:
                onus_to_alert.append(onu)
            else:
                logger.debug(f"Skipping weak signal alert for ONU {onu.mac_address} - already alerted within {WEAK_SIGNAL_ALERT_COOLDOWN_HOURS}h")

        if not onus_to_alert:
            logger.debug("All weak signal ONUs were already alerted recently, skipping")
            return

        # Build detailed message for each ONU
        for onu in onus_to_alert[:5]:  # Limit to 5 ONUs per batch to avoid long messages
            onu_name = onu.description if onu.description and onu.description.upper() != "NULL" else "No Name"
            region_name = onu.region.name if onu.region else "No Region"

            # Get signal value (prefer ONU-reported rx_power, fallback to OLT-measured)
            signal = onu.rx_power

            # Calculate risk level based on proximity to lower threshold
            if signal is not None:
                range_size = upper_threshold - lower_threshold
                position = (signal - lower_threshold) / range_size if range_size != 0 else 0.5
                if position < 0.33:
                    risk_level = "CRITICAL - Disconnect imminent!"
                elif position < 0.66:
                    risk_level = "HIGH - May disconnect soon"
                else:
                    risk_level = "WARNING - Signal degrading"
            else:
                risk_level = "UNKNOWN"

            message_parts = [
                "⚠️ *WEAK SIGNAL ALERT*",
                "",
                f"Description: {onu_name}",
                f"OLT: {olt_name}",
                f"Region: {region_name}",
                f"MAC: {onu.mac_address}",
                f"Port: {onu.pon_port}/{onu.onu_id}",
                "",
                f"📶 Signal: {signal} dBm" if signal else "📶 Signal: Unknown",
                f"🎯 Danger Zone: {upper_threshold} to {lower_threshold} dBm",
                f"⚡ Risk: {risk_level}",
            ]

            # Add location if available
            if onu.latitude and onu.longitude:
                message_parts.append(f"📍 Location: https://maps.google.com/?q={onu.latitude},{onu.longitude}")
            if onu.address:
                message_parts.append(f"🏠 Address: {onu.address}")

            message_parts.append("")
            message_parts.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("")
            message_parts.append("Action: Check fiber connection")

            message = "\n".join(message_parts)

            # Send to all recipients
            for recipient in recipients:
                phone = recipient.get('phone', '').strip()
                if not phone:
                    continue

                try:
                    response = requests.post(
                        api_url,
                        data={
                            'secret': secret,
                            'account': account,
                            'recipient': phone,
                            'type': 'text',
                            'message': message
                        },
                        timeout=10
                    )
                    if response.status_code == 200:
                        logger.info(f"Weak signal notification sent to {phone} for ONU {onu.mac_address}")
                        # Mark this ONU as alerted in the cache to prevent spam
                        weak_signal_alert_cache[onu.id] = now
                    else:
                        logger.warning(f"Failed to send weak signal notification to {phone}: {response.text}")
                except Exception as e:
                    logger.error(f"Error sending weak signal notification to {phone}: {e}")

        if len(onus_to_alert) > 5:
            logger.info(f"Weak signal alert: Sent notifications for 5 ONUs, {len(onus_to_alert) - 5} more have weak signal (not yet alerted)")

    except Exception as e:
        logger.error(f"Failed to send weak signal notification: {e}")


def send_high_temperature_notification(db: Session, olt, temperature: float):
    """Send WhatsApp notification for OLT high temperature"""
    try:
        alarm_settings = get_alarm_settings(db)

        # Check if high temperature alarm is enabled
        if not is_alarm_enabled(alarm_settings, "high_temperature"):
            logger.debug("High temperature alarm is disabled")
            return

        # Check quiet hours
        if is_in_quiet_hours(alarm_settings):
            logger.debug("Skipping high temperature notification - quiet hours")
            return

        settings = get_whatsapp_settings(db)

        # Check if WhatsApp notifications are enabled
        if str(settings.get('whatsapp_enabled', '')).lower() != 'true':
            return

        api_url = settings.get('whatsapp_api_url', '').strip()
        secret = decrypt_sensitive(settings.get('whatsapp_secret', '')).strip()
        account = settings.get('whatsapp_account', '').strip()
        recipients = parse_whatsapp_recipients(settings.get('whatsapp_recipients', ''))

        if not recipients or not all([api_url, secret, account]):
            return

        threshold = alarm_settings.get("high_temperature_threshold", 60)

        # Build message
        message_parts = [
            f"🌡️ *HIGH TEMPERATURE ALERT*",
            "",
            f"OLT: {olt.name}",
            f"IP: {olt.ip_address}",
            f"Temperature: {temperature}°C",
            f"Threshold: {threshold}°C",
            "",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ]

        message = "\n".join(message_parts)

        # Send to all recipients
        for recipient in recipients:
            phone = recipient.get('phone', '').strip()
            if not phone:
                continue

            try:
                response = requests.post(
                    api_url,
                    data={
                        'secret': secret,
                        'account': account,
                        'recipient': phone,
                        'type': 'text',
                        'message': message
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info(f"High temperature notification sent to {phone}")
                else:
                    logger.warning(f"Failed to send high temperature notification to {phone}: {response.text}")
            except Exception as e:
                logger.error(f"Error sending high temperature notification to {phone}: {e}")

    except Exception as e:
        logger.error(f"Failed to send high temperature notification: {e}")


async def collect_traffic_history(olt, db):
    """Collect traffic data and save to history for an OLT."""
    try:
        loop = asyncio.get_event_loop()
        current_counters = await loop.run_in_executor(
            thread_executor,
            get_traffic_counters_snmp,
            olt.ip_address,
            "public"
        )

        if not current_counters:
            return

        current_time = datetime.utcnow()

        # Get previous snapshots for this OLT
        prev_snapshots = {
            s.mac_address: s
            for s in db.query(TrafficSnapshot).filter(TrafficSnapshot.olt_id == olt.id).all()
        }

        traffic_data = []

        for mac, counters in current_counters.items():
            rx_bytes = counters['rx_bytes']
            tx_bytes = counters['tx_bytes']
            pon_port = counters.get('pon_port', 0)

            rx_kbps = 0
            tx_kbps = 0

            if mac in prev_snapshots:
                prev = prev_snapshots[mac]

                # Use the pre-calculated rates from the snapshot (updated by WebSocket polling)
                # This avoids race conditions where WebSocket updates snapshots frequently
                rx_kbps = getattr(prev, 'last_rx_kbps', 0) or 0
                tx_kbps = getattr(prev, 'last_tx_kbps', 0) or 0

                # Only recalculate if no WebSocket is updating (time_diff > 10 seconds)
                time_diff = (current_time - prev.timestamp).total_seconds()
                if time_diff > 10:
                    # No WebSocket active, calculate rate ourselves
                    rx_diff = rx_bytes - prev.rx_bytes
                    tx_diff = tx_bytes - prev.tx_bytes

                    if rx_diff < 0:
                        rx_diff = rx_bytes
                    if tx_diff < 0:
                        tx_diff = tx_bytes

                    rx_kbps = round((rx_diff * 8) / time_diff / 1000, 2)
                    tx_kbps = round((tx_diff * 8) / time_diff / 1000, 2)

                    # Sanity check: cap at 1 Gbps (1,000,000 Kbps) - reject impossible values
                    MAX_VALID_KBPS = 1000000  # 1 Gbps
                    if rx_kbps > MAX_VALID_KBPS or tx_kbps > MAX_VALID_KBPS:
                        logger.warning(f"Traffic value exceeds 1 Gbps, ignoring: RX={rx_kbps}, TX={tx_kbps}")
                        rx_kbps = 0
                        tx_kbps = 0

                    prev.last_rx_kbps = rx_kbps
                    prev.last_tx_kbps = tx_kbps

                # Always update the snapshot with latest counters
                prev.rx_bytes = rx_bytes
                prev.tx_bytes = tx_bytes
                prev.timestamp = current_time
            else:
                snapshot = TrafficSnapshot(
                    olt_id=olt.id,
                    mac_address=mac,
                    rx_bytes=rx_bytes,
                    tx_bytes=tx_bytes,
                    timestamp=current_time,
                    last_rx_kbps=0,
                    last_tx_kbps=0
                )
                db.add(snapshot)

            # Get ONU from database
            onu = db.query(ONU).filter(
                ONU.olt_id == olt.id,
                ONU.mac_address == mac
            ).first()

            traffic_data.append({
                'onu': onu,
                'pon_port': pon_port,
                'rx_kbps': rx_kbps,
                'tx_kbps': tx_kbps
            })

            # Save ONU traffic history
            if onu and (rx_kbps > 0 or tx_kbps > 0 or onu.is_online):
                onu_history = TrafficHistory(
                    entity_type='onu',
                    entity_id=str(onu.id),
                    olt_id=olt.id,
                    pon_port=pon_port,
                    onu_db_id=onu.id,
                    rx_kbps=rx_kbps,
                    tx_kbps=tx_kbps,
                    timestamp=current_time
                )
                db.add(onu_history)

        # Aggregate and save PON port history
        pon_traffic = {}
        for t in traffic_data:
            pon = t['pon_port']
            if pon not in pon_traffic:
                pon_traffic[pon] = {'rx_kbps': 0, 'tx_kbps': 0}
            pon_traffic[pon]['rx_kbps'] += t['rx_kbps']
            pon_traffic[pon]['tx_kbps'] += t['tx_kbps']

        for pon, traffic in pon_traffic.items():
            pon_history = TrafficHistory(
                entity_type='pon',
                entity_id=f"{olt.id}:{pon}",
                olt_id=olt.id,
                pon_port=pon,
                onu_db_id=None,
                rx_kbps=traffic['rx_kbps'],
                tx_kbps=traffic['tx_kbps'],
                timestamp=current_time
            )
            db.add(pon_history)

        # Save OLT total history
        total_rx = sum(t['rx_kbps'] for t in traffic_data)
        total_tx = sum(t['tx_kbps'] for t in traffic_data)
        olt_history = TrafficHistory(
            entity_type='olt',
            entity_id=str(olt.id),
            olt_id=olt.id,
            pon_port=None,
            onu_db_id=None,
            rx_kbps=total_rx,
            tx_kbps=total_tx,
            timestamp=current_time
        )
        db.add(olt_history)

        # Collect uplink port traffic via SNMP
        from models import PortTraffic
        port_counters = await loop.run_in_executor(
            thread_executor,
            poll_port_traffic_snmp,
            olt.ip_address,
            "public"
        )

        if port_counters:
            port_rates = calculate_port_rates(olt.id, olt.ip_address, port_counters)

            # V1600D8 port mapping: SFP=1-4, SFP+=5-8, ETH=9-16
            model = olt.model or ''
            if 'D8' in model:
                port_mapping = {
                    **{i: ('sfp', i) for i in range(1, 5)},      # GE1-4 = SFP
                    **{i: ('xge', i) for i in range(5, 9)},      # GE5-8 = SFP+
                    **{i: ('ge', i) for i in range(9, 17)}       # GE9-16 = ETH
                }
            else:
                # Default: first ports are GE, then SFP, then XGE
                port_mapping = {i: ('ge', i) for i in range(1, 17)}

            for if_idx, rates in port_rates.items():
                if if_idx in port_mapping and (rates['rx_kbps'] > 0 or rates['tx_kbps'] > 0):
                    port_type, port_num = port_mapping[if_idx]
                    port_traffic = PortTraffic(
                        olt_id=olt.id,
                        port_type=port_type,
                        port_number=if_idx,  # Use actual interface index
                        rx_kbps=rates['rx_kbps'],
                        tx_kbps=rates['tx_kbps'],
                        timestamp=current_time
                    )
                    db.add(port_traffic)

            logger.info(f"Port traffic saved for {olt.name}: {len(port_rates)} ports with traffic")

        logger.info(f"Traffic history saved for {olt.name}: {len(traffic_data)} ONUs, total {total_rx:.0f}/{total_tx:.0f} kbps")

    except Exception as e:
        logger.error(f"Failed to collect traffic history for {olt.name}: {e}")


async def poll_all_olts(db_session_factory, use_snmp: bool = True):
    """Poll all OLTs and update database

    Uses SNMP polling for fast ONU data retrieval (~2 seconds).
    Falls back to SSH if SNMP fails.
    """
    logger.info("Starting OLT polling cycle")

    db = db_session_factory()
    try:
        olts = db.query(OLT).all()

        for olt in olts:
            # Track OLT's previous online status for alarm notifications
            olt_was_online = olt.is_online

            try:
                logger.info(f"Polling OLT: {olt.name} ({olt.ip_address})")

                # Get existing ONUs for this OLT
                existing_onus = {
                    o.mac_address: o
                    for o in db.query(ONU).filter(ONU.olt_id == olt.id).all()
                }

                # Try SNMP first for fast polling (~2 seconds vs 30-60 seconds for SSH)
                snmp_onus_data = []
                snmp_status_map = {}
                if use_snmp:
                    logger.info(f"Trying SNMP poll for {olt.name}...")
                    loop = asyncio.get_event_loop()
                    snmp_onus_data, snmp_status_map = await loop.run_in_executor(
                        thread_executor,
                        poll_olt_snmp,
                        olt.ip_address,
                        "public"  # Default community string
                    )

                    if snmp_onus_data:
                        logger.info(f"SNMP poll successful for {olt.name}: {len(snmp_onus_data)} ONUs")

                        # Get ONU self-reported RX power via web scraping
                        # This gives the ~-13 dBm value the customer sees (vs ~-26 dBm SNMP measures)
                        web_opm_data = {}
                        web_user = olt.web_username or olt.username or 'admin'
                        web_pass = decrypt_sensitive(olt.web_password) if olt.web_password else decrypt_sensitive(olt.password) if olt.password else 'admin'
                        if web_user and web_pass:
                            try:
                                web_opm_data = await loop.run_in_executor(
                                    thread_executor,
                                    get_onu_opm_data_web,
                                    olt.ip_address,
                                    web_user,
                                    web_pass
                                )
                                if web_opm_data:
                                    logger.info(f"Web OPM for {olt.name}: got ONU RX power for {len(web_opm_data)} ONUs")
                            except Exception as web_err:
                                logger.warning(f"Web OPM scraping failed for {olt.name}: {web_err}")

                        # Update OLT status
                        olt.is_online = True
                        olt.last_poll = datetime.utcnow()
                        olt.last_error = None

                        # Poll OLT health metrics (CPU, temperature, uptime, PON port transceiver data)
                        try:
                            health_data = await loop.run_in_executor(
                                thread_executor,
                                get_olt_health_snmp,
                                olt.ip_address,
                                "public",
                                olt.pon_ports  # Pass number of PON ports for transceiver polling
                            )
                            if health_data:
                                olt.cpu_usage = health_data.get('cpu_usage')
                                olt.memory_usage = health_data.get('memory_usage')
                                olt.temperature = health_data.get('temperature')
                                olt.uptime_seconds = health_data.get('uptime_seconds')

                                # Check high temperature alarm
                                if olt.temperature is not None:
                                    alarm_settings = get_alarm_settings(db)
                                    temp_threshold = float(alarm_settings.get("high_temperature_threshold", 60))
                                    if olt.temperature > temp_threshold:
                                        send_high_temperature_notification(db, olt, olt.temperature)

                                # Save PON port transceiver diagnostics to OLTPort table
                                pon_ports_data = health_data.get('pon_ports', [])
                                for port_info in pon_ports_data:
                                    port_num = port_info.get('port')
                                    if port_num:
                                        # Find or create OLTPort entry for this PON port
                                        olt_port = db.query(OLTPort).filter(
                                            OLTPort.olt_id == olt.id,
                                            OLTPort.port_type == 'pon',
                                            OLTPort.port_number == port_num
                                        ).first()
                                        if not olt_port:
                                            olt_port = OLTPort(
                                                olt_id=olt.id,
                                                port_type='pon',
                                                port_number=port_num
                                            )
                                            db.add(olt_port)
                                        # Update transceiver data
                                        if port_info.get('temperature') is not None:
                                            olt_port.temperature = port_info['temperature']
                                        if port_info.get('tx_power') is not None:
                                            olt_port.tx_power = port_info['tx_power']
                                        olt_port.last_updated = datetime.utcnow()
                        except Exception as health_err:
                            logger.warning(f"Health poll failed for {olt.name}: {health_err}")

                        # Send OLT back online notification if it was offline
                        if not olt_was_online and olt.is_online:
                            send_olt_status_notification(db, olt, is_online=True)

                        # Re-index existing ONUs by (pon_port, onu_id) for proper matching
                        existing_by_key = {
                            (o.pon_port, o.onu_id): o
                            for o in db.query(ONU).filter(ONU.olt_id == olt.id).all()
                        }

                        # Track which ONUs we've seen
                        seen_keys = set()

                        # Collect status changes for batched notification
                        onus_went_online = []
                        onus_went_offline = []

                        # Check license ONU limit
                        from license_manager import license_manager
                        license_info = license_manager.get_license_info()
                        max_onus = license_info.get('max_onus', 100)
                        current_onu_count = db.query(ONU).count()
                        onu_limit_reached = current_onu_count >= max_onus

                        # Update or create ONUs from SNMP data
                        for onu_data in snmp_onus_data:
                            key = (onu_data.pon_port, onu_data.onu_id)
                            seen_keys.add(key)

                            # Get online status from status_map using pon:onu key
                            # (handles duplicate MACs across PON ports correctly)
                            status_key = f"{onu_data.pon_port}:{onu_data.onu_id}"
                            is_online = snmp_status_map.get(status_key, False)

                            # Get RX power from SNMP
                            rx_power = onu_data.rx_power

                            # Get ONU self-reported optical data from web scraping
                            onu_rx_power = None
                            onu_tx_power = None
                            onu_temperature = None
                            onu_voltage = None
                            onu_tx_bias = None
                            web_distance = None
                            if onu_data.mac_address in web_opm_data:
                                web_data = web_opm_data[onu_data.mac_address]
                                onu_rx_power = web_data.get('rx_power')
                                onu_tx_power = web_data.get('tx_power')
                                onu_temperature = web_data.get('temperature')
                                onu_voltage = web_data.get('voltage')
                                onu_tx_bias = web_data.get('tx_bias')
                                web_distance = web_data.get('distance')  # From OLT web interface

                            # Use ONLY web distance (no SNMP fallback)
                            final_distance = web_distance

                            if key in existing_by_key:
                                # Update existing ONU
                                existing = existing_by_key[key]
                                was_online = existing.is_online
                                existing.mac_address = onu_data.mac_address
                                existing.is_online = is_online
                                # Update optical diagnostics only when online
                                if onu_data.description:
                                    existing.description = onu_data.description
                                # Always update model if available from SNMP
                                if onu_data.model:
                                    existing.model = onu_data.model
                                if is_online:
                                    # Only update distance/rx_power when ONU is online
                                    if final_distance is not None:
                                        existing.distance = final_distance
                                    if rx_power is not None:
                                        existing.rx_power = rx_power
                                    # Update ONU self-reported optical data from web scraping
                                    if onu_rx_power is not None:
                                        existing.onu_rx_power = onu_rx_power
                                    if onu_tx_power is not None:
                                        existing.onu_tx_power = onu_tx_power
                                    if onu_temperature is not None:
                                        existing.onu_temperature = onu_temperature
                                    if onu_voltage is not None:
                                        existing.onu_voltage = onu_voltage
                                    if onu_tx_bias is not None:
                                        existing.onu_tx_bias = onu_tx_bias
                                    existing.last_seen = datetime.utcnow()
                                else:
                                    # Keep last known optical data when ONU goes offline
                                    # This preserves the "last signal" for notifications and troubleshooting
                                    # Only clear if explicitly requested (e.g., ONU removed)
                                    pass
                                existing.updated_at = datetime.utcnow()

                                # Collect status changes for batched notification
                                if was_online and not is_online:
                                    logger.info(f"ONU went OFFLINE: {existing.mac_address} (PON {existing.pon_port}/{existing.onu_id})")
                                    onus_went_offline.append(existing)
                                elif not was_online and is_online:
                                    logger.info(f"ONU came back ONLINE: {existing.mac_address} (PON {existing.pon_port}/{existing.onu_id})")
                                    onus_went_online.append(existing)
                            else:
                                # Check ONU limit before creating new ONU
                                if onu_limit_reached:
                                    logger.warning(f"ONU limit reached ({max_onus}). Skipping new ONU: {onu_data.mac_address}")
                                    continue

                                # Create new ONU from SNMP (now includes pon_port and onu_id)
                                # Only save distance/rx_power if ONU is online
                                new_onu = ONU(
                                    olt_id=olt.id,
                                    pon_port=onu_data.pon_port,
                                    onu_id=onu_data.onu_id,
                                    mac_address=onu_data.mac_address,
                                    description=onu_data.description,
                                    model=onu_data.model,
                                    is_online=is_online,
                                    distance=final_distance if is_online else None,
                                    rx_power=rx_power if is_online else None,
                                    onu_rx_power=onu_rx_power if is_online else None,
                                    onu_tx_power=onu_tx_power if is_online else None,
                                    onu_temperature=onu_temperature if is_online else None,
                                    onu_voltage=onu_voltage if is_online else None,
                                    onu_tx_bias=onu_tx_bias if is_online else None,
                                    last_seen=datetime.utcnow() if is_online else None
                                )
                                db.add(new_onu)
                                current_onu_count += 1  # Track added ONUs
                                onu_limit_reached = current_onu_count >= max_onus
                                # Send new ONU registration notification
                                send_new_onu_notification(db, new_onu, olt.name)

                        # Mark ONUs not seen in SNMP as offline (they may be powered off)
                        for key, onu in existing_by_key.items():
                            if key not in seen_keys:
                                if onu.is_online:
                                    logger.info(f"Marking ONU offline (not in SNMP): PON {onu.pon_port} ONU {onu.onu_id} ({onu.mac_address})")
                                    onu.is_online = False
                                    # Keep last known optical data for notifications and troubleshooting
                                    # (distance, rx_power, onu_rx_power, etc. are preserved)
                                    onu.updated_at = datetime.utcnow()
                                    onus_went_offline.append(onu)

                        # Send batched notification for all status changes
                        send_whatsapp_notification_batch(db, onus_went_online, onus_went_offline, olt.name)

                        # Check for weak signal alarms (Danger Zone detection)
                        alarm_settings = get_alarm_settings(db)
                        if is_alarm_enabled(alarm_settings, "weak_signal"):
                            # Upper threshold: signal weaker than this triggers alert (e.g., -25 dBm)
                            upper_threshold = float(alarm_settings.get("weak_signal_threshold", -25))
                            # Lower threshold: signal weaker than this means ONU is likely to disconnect (e.g., -30 dBm)
                            lower_threshold = float(alarm_settings.get("weak_signal_lower_threshold", -30))

                            # Find ONUs in the DANGER ZONE: signal is weak but not yet disconnected
                            # Signal must be: weaker than upper (rx_power < upper) AND stronger than lower (rx_power >= lower)
                            weak_signal_onus = [
                                o for o in db.query(ONU).filter(
                                    ONU.olt_id == olt.id,
                                    ONU.is_online == True,
                                    ONU.rx_power != None,
                                    ONU.rx_power < upper_threshold,  # Signal weaker than upper threshold
                                    ONU.rx_power >= lower_threshold  # But not yet at disconnection level
                                ).all()
                            ]
                            if weak_signal_onus:
                                send_weak_signal_notification(db, weak_signal_onus, olt.name, upper_threshold, lower_threshold)

                        # Log successful SNMP poll
                        poll_log = PollLog(
                            olt_id=olt.id,
                            status="success",
                            message=f"SNMP: {len(snmp_onus_data)} ONUs",
                            onus_found=len(snmp_onus_data)
                        )
                        db.add(poll_log)
                        db.commit()

                        # Collect traffic history after successful poll
                        await collect_traffic_history(olt, db)
                        db.commit()

            except Exception as e:
                logger.error(f"Failed to poll OLT {olt.name}: {e}")
                olt.is_online = False
                olt.last_poll = datetime.utcnow()
                olt.last_error = str(e)

                # Send OLT offline notification if it was online before
                if olt_was_online:
                    send_olt_status_notification(db, olt, is_online=False)

                # Log failed poll
                poll_log = PollLog(
                    olt_id=olt.id,
                    status="error",
                    message=str(e),
                    onus_found=0
                )
                db.add(poll_log)

            db.commit()

    finally:
        db.close()

    logger.info("Completed OLT polling cycle")


async def cleanup_old_data(db_session_factory, retention_days: int = 7):
    """Clean up old data from traffic_history, poll_logs, and port_traffic tables.

    This runs periodically to prevent database bloat.
    Default retention is 7 days.
    """
    from models import PortTraffic

    db = db_session_factory()
    try:
        cutoff_time = datetime.utcnow() - timedelta(days=retention_days)

        # Clean traffic_history (largest table)
        deleted_traffic = db.query(TrafficHistory).filter(
            TrafficHistory.timestamp < cutoff_time
        ).delete(synchronize_session=False)

        # Clean poll_logs (uses polled_at column)
        deleted_polls = db.query(PollLog).filter(
            PollLog.polled_at < cutoff_time
        ).delete(synchronize_session=False)

        # Clean port_traffic
        deleted_ports = db.query(PortTraffic).filter(
            PortTraffic.timestamp < cutoff_time
        ).delete(synchronize_session=False)

        db.commit()

        total_deleted = deleted_traffic + deleted_polls + deleted_ports
        if total_deleted > 0:
            logger.info(f"Cleanup completed: deleted {deleted_traffic} traffic_history, "
                       f"{deleted_polls} poll_logs, {deleted_ports} port_traffic records "
                       f"older than {retention_days} days")

    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        db.rollback()
    finally:
        db.close()


async def polling_loop(db_session_factory):
    """Background loop to poll OLTs periodically"""
    global cleanup_counter

    logger.info("Background polling loop started")
    while True:
        try:
            logger.info(f"Waiting {POLL_INTERVAL} seconds before next poll cycle...")
            await asyncio.sleep(POLL_INTERVAL)
            logger.info("Starting scheduled poll cycle")
            await poll_all_olts(db_session_factory)

            # Run cleanup periodically (every CLEANUP_INTERVAL_CYCLES polls)
            cleanup_counter += 1
            if cleanup_counter >= CLEANUP_INTERVAL_CYCLES:
                cleanup_counter = 0
                logger.info("Running scheduled database cleanup...")
                await cleanup_old_data(db_session_factory, retention_days=7)

        except asyncio.CancelledError:
            logger.info("Polling loop cancelled")
            break
        except Exception as e:
            logger.error(f"Polling loop error: {e}", exc_info=True)


async def handle_trap_event(event: TrapEvent, db_session_factory):
    """Handle SNMP trap event - update ONU status and send notification"""
    from models import SessionLocal

    logger.info(f"Processing trap: {event.event_type} from {event.source_ip}, "
                f"PON:{event.pon_port}, ONU:{event.onu_id}, MAC:{event.mac_address}")

    db = db_session_factory()
    try:
        # Find the OLT by IP address
        olt = db.query(OLT).filter(OLT.ip_address == event.source_ip).first()
        if not olt:
            logger.warning(f"Trap from unknown OLT: {event.source_ip}")
            return

        # Find the ONU
        onu = None
        if event.mac_address:
            onu = db.query(ONU).filter(
                ONU.olt_id == olt.id,
                ONU.mac_address == event.mac_address
            ).first()
        elif event.pon_port and event.onu_id:
            onu = db.query(ONU).filter(
                ONU.olt_id == olt.id,
                ONU.pon_port == event.pon_port,
                ONU.onu_id == event.onu_id
            ).first()

        if not onu:
            logger.warning(f"Trap for unknown ONU: PON={event.pon_port}, ID={event.onu_id}, MAC={event.mac_address}")
            return

        # Check if status actually changed
        new_status = event.event_type == 'online'
        if onu.is_online == new_status:
            logger.debug(f"ONU {onu.description or onu.mac_address} status unchanged")
            return

        # Update ONU status
        old_status = onu.is_online
        onu.is_online = new_status
        onu.last_seen = datetime.utcnow()
        db.commit()

        logger.info(f"ONU {onu.description or onu.mac_address} status changed: "
                    f"{'online' if old_status else 'offline'} -> {'online' if new_status else 'offline'} (via TRAP)")

        # Send WhatsApp notification for instant alert
        if event.event_type == 'offline':
            send_whatsapp_notification_batch(db, [], [onu], olt.name)
        else:
            send_whatsapp_notification_batch(db, [onu], [], olt.name)

    except Exception as e:
        logger.error(f"Error handling trap event: {e}", exc_info=True)
    finally:
        db.close()


def get_trap_settings(db: Session) -> dict:
    """Get SNMP trap settings from database"""
    settings = {}
    for key in ['trap_enabled', 'trap_port', 'trap_community']:
        setting = db.query(Settings).filter(Settings.key == key).first()
        if setting:
            settings[key] = setting.value
    return settings


async def start_trap_receiver(db_session_factory):
    """Start SNMP trap receiver if enabled"""
    global trap_receiver, trap_task

    db = db_session_factory()
    try:
        settings = get_trap_settings(db)
        trap_enabled = str(settings.get('trap_enabled', 'true')).lower() == 'true'
        trap_port = int(settings.get('trap_port', '162'))

        if not trap_enabled:
            logger.info("SNMP Trap receiver is disabled in settings")
            return

        trap_receiver = SimpleTrapReceiver(port=trap_port)

        async def on_trap(event: TrapEvent):
            await handle_trap_event(event, db_session_factory)

        trap_receiver.set_callback(on_trap)

        try:
            await trap_receiver.start()
            logger.info(f"SNMP Trap receiver started on port {trap_port}")
        except PermissionError:
            logger.warning(f"Cannot bind to port {trap_port} (requires root). "
                          f"Trying port 1620 instead...")
            trap_receiver = SimpleTrapReceiver(port=1620)
            trap_receiver.set_callback(on_trap)
            await trap_receiver.start()
            logger.info("SNMP Trap receiver started on port 1620")

    except Exception as e:
        logger.error(f"Failed to start trap receiver: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global polling_task, trap_task, trap_receiver

    # Validate license first (but don't crash - allow read-only mode)
    from license_manager import validate_license_on_startup, license_manager, LicenseError, license_check_loop
    license_valid = validate_license_on_startup()

    if license_valid:
        license_info = license_manager.get_license_info()
        logger.info(f"License valid: {license_info.get('customer_name')} | Max OLTs: {license_info.get('max_olts')} | Max ONUs: {license_info.get('max_onus')}")
    else:
        logger.warning("=" * 50)
        logger.warning("LICENSE INVALID - Running in READ-ONLY mode")
        logger.warning(f"Reason: {license_manager.error_message}")
        logger.warning("=" * 50)

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Create default admin user if needed
    from models import SessionLocal
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()

    # Start background polling
    polling_task = asyncio.create_task(polling_loop(SessionLocal))
    logger.info(f"Started background polling (interval: {POLL_INTERVAL}s)")

    # Start SNMP trap receiver
    trap_task = asyncio.create_task(start_trap_receiver(SessionLocal))

    # Start periodic license check
    license_task = asyncio.create_task(license_check_loop())
    logger.info("Started periodic license check (every 5 minutes)")

    yield

    # Cleanup
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass

    if trap_receiver:
        await trap_receiver.stop()

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="EPON OLT Manager",
    description="Dashboard for managing VSOL EPON OLTs and ONUs",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - configurable origins from environment
# For production: set CORS_ORIGINS environment variable (comma-separated)
# Example: CORS_ORIGINS=https://olt.example.com,https://admin.example.com
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").strip()
if CORS_ORIGINS:
    allowed_origins = [origin.strip() for origin in CORS_ORIGINS.split(",")]
else:
    # Default: allow local development and same-origin requests
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Create uploads directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Mount frontend static files (for compiled installations without nginx)
# Check multiple possible locations for static directory
def find_static_dir():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "static"),  # Development
        os.path.join(os.getcwd(), "static"),                 # Current working directory
        os.path.join(os.path.dirname(sys.executable), "static"),  # Next to executable
        "/opt/olt-manager/static",                           # Standard install location
    ]
    for path in possible_paths:
        if os.path.exists(path) and os.path.isdir(path):
            return path
    return None

STATIC_DIR = find_static_dir()
if STATIC_DIR:
    logger.info(f"Found static directory at: {STATIC_DIR}")
    # Mount the JS/CSS static folder
    static_assets = os.path.join(STATIC_DIR, "static")
    if os.path.exists(static_assets):
        app.mount("/static", StaticFiles(directory=static_assets), name="static_assets")


# ============ Helper Functions ============

def get_user_allowed_olt_ids(user: User, db: Session) -> Optional[List[int]]:
    """Get list of OLT IDs a user can access. Returns None if user has access to all (admin)."""
    if user.role == "admin":
        return None  # Admin has access to all OLTs

    # Get assigned OLT IDs for this operator
    assigned_ids = db.query(user_olts.c.olt_id).filter(
        user_olts.c.user_id == user.id
    ).all()

    return [row[0] for row in assigned_ids]


def get_user_olt_ids_list(user: User, db: Session) -> List[int]:
    """Get assigned OLT IDs for a user (for response serialization)."""
    assigned_ids = db.query(user_olts.c.olt_id).filter(
        user_olts.c.user_id == user.id
    ).all()
    return [row[0] for row in assigned_ids]


# ============ Dashboard Endpoints ============

@app.get("/api/dashboard", response_model=DashboardStats)
def get_dashboard_stats(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Get dashboard statistics (filtered by user access)"""
    allowed_olt_ids = get_user_allowed_olt_ids(user, db)

    # Build OLT query
    olt_query = db.query(OLT)
    if allowed_olt_ids is not None:
        olt_query = olt_query.filter(OLT.id.in_(allowed_olt_ids))

    total_olts = olt_query.count()
    online_olts = olt_query.filter(OLT.is_online == True).count()

    # Build ONU query
    onu_query = db.query(ONU)
    if allowed_olt_ids is not None:
        onu_query = onu_query.filter(ONU.olt_id.in_(allowed_olt_ids))

    total_onus = onu_query.count()
    online_onus = onu_query.filter(ONU.is_online == True).count()

    return DashboardStats(
        total_olts=total_olts,
        online_olts=online_olts,
        offline_olts=total_olts - online_olts,
        total_onus=total_onus,
        online_onus=online_onus,
        offline_onus=total_onus - online_onus
    )


# ============ OLT Endpoints ============

@app.get("/api/olts", response_model=OLTListResponse)
def list_olts(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """List all OLTs (filtered by user access)"""
    allowed_olt_ids = get_user_allowed_olt_ids(user, db)

    query = db.query(OLT)
    if allowed_olt_ids is not None:
        query = query.filter(OLT.id.in_(allowed_olt_ids))

    olts = query.all()

    # Get ONU counts in a single query (fixes N+1 problem)
    olt_ids = [olt.id for olt in olts]
    counts_map = {}
    if olt_ids:
        # Get total counts per OLT
        total_counts = db.query(
            ONU.olt_id,
            func.count(ONU.id).label('total')
        ).filter(ONU.olt_id.in_(olt_ids)).group_by(ONU.olt_id).all()

        # Get online counts per OLT
        online_counts = db.query(
            ONU.olt_id,
            func.count(ONU.id).label('online')
        ).filter(ONU.olt_id.in_(olt_ids), ONU.is_online == True).group_by(ONU.olt_id).all()

        # Build lookup dictionary
        for row in total_counts:
            counts_map[row.olt_id] = {'total': row.total, 'online': 0}
        for row in online_counts:
            if row.olt_id in counts_map:
                counts_map[row.olt_id]['online'] = row.online

    response_olts = []
    for olt in olts:
        counts = counts_map.get(olt.id, {'total': 0, 'online': 0})

        response_olts.append(OLTResponse(
            id=olt.id,
            name=olt.name,
            ip_address=olt.ip_address,
            model=olt.model,
            pon_ports=olt.pon_ports,
            is_online=olt.is_online,
            last_poll=olt.last_poll,
            last_error=olt.last_error,
            onu_count=counts['total'],
            online_onu_count=counts['online'],
            cpu_usage=olt.cpu_usage,
            memory_usage=olt.memory_usage,
            temperature=olt.temperature,
            uptime_seconds=olt.uptime_seconds,
            created_at=olt.created_at,
            updated_at=olt.updated_at
        ))

    return OLTListResponse(olts=response_olts, total=len(response_olts))


@app.get("/api/olts/{olt_id}", response_model=OLTResponse)
def get_olt(olt_id: int, db: Session = Depends(get_db)):
    """Get specific OLT by ID"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    onu_count = db.query(ONU).filter(ONU.olt_id == olt.id).count()
    online_onu_count = db.query(ONU).filter(
        ONU.olt_id == olt.id,
        ONU.is_online == True
    ).count()

    return OLTResponse(
        id=olt.id,
        name=olt.name,
        ip_address=olt.ip_address,
        model=olt.model,
        pon_ports=olt.pon_ports,
        is_online=olt.is_online,
        last_poll=olt.last_poll,
        last_error=olt.last_error,
        onu_count=onu_count,
        online_onu_count=online_onu_count,
        cpu_usage=olt.cpu_usage,
        memory_usage=olt.memory_usage,
        temperature=olt.temperature,
        uptime_seconds=olt.uptime_seconds,
        created_at=olt.created_at,
        updated_at=olt.updated_at
    )


@app.post("/api/olts", response_model=OLTResponse, status_code=201)
def create_olt(olt_data: OLTCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Create new OLT (admin only)"""
    # Check license OLT limit
    from license_manager import license_manager
    license_info = license_manager.get_license_info()
    max_olts = license_info.get('max_olts', 1)
    current_olt_count = db.query(OLT).count()

    if current_olt_count >= max_olts:
        package = license_info.get('package_type', 'trial')
        raise HTTPException(
            status_code=403,
            detail=f"OLT limit reached ({max_olts}). Upgrade your package to add more OLTs. Current package: {package}"
        )

    # Check for duplicate IP
    existing = db.query(OLT).filter(OLT.ip_address == olt_data.ip_address).first()
    if existing:
        raise HTTPException(status_code=400, detail="OLT with this IP already exists")

    olt = OLT(
        name=olt_data.name,
        ip_address=olt_data.ip_address,
        username=olt_data.username,
        password=encrypt_sensitive(olt_data.password),  # Encrypt password
        model=olt_data.model,
        pon_ports=olt_data.pon_ports
    )
    db.add(olt)
    db.commit()
    db.refresh(olt)

    return OLTResponse(
        id=olt.id,
        name=olt.name,
        ip_address=olt.ip_address,
        model=olt.model,
        pon_ports=olt.pon_ports,
        is_online=olt.is_online,
        last_poll=olt.last_poll,
        last_error=olt.last_error,
        onu_count=0,
        online_onu_count=0,
        created_at=olt.created_at,
        updated_at=olt.updated_at
    )


@app.put("/api/olts/{olt_id}", response_model=OLTResponse)
def update_olt(olt_id: int, olt_data: OLTUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Update OLT (admin only)"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    if olt_data.name is not None:
        olt.name = olt_data.name
    if olt_data.username is not None:
        olt.username = olt_data.username
    if olt_data.password is not None:
        olt.password = encrypt_sensitive(olt_data.password)  # Encrypt password
    if olt_data.model is not None:
        olt.model = olt_data.model
    if olt_data.pon_ports is not None:
        olt.pon_ports = olt_data.pon_ports

    db.commit()
    db.refresh(olt)

    onu_count = db.query(ONU).filter(ONU.olt_id == olt.id).count()
    online_onu_count = db.query(ONU).filter(
        ONU.olt_id == olt.id,
        ONU.is_online == True
    ).count()

    return OLTResponse(
        id=olt.id,
        name=olt.name,
        ip_address=olt.ip_address,
        model=olt.model,
        pon_ports=olt.pon_ports,
        is_online=olt.is_online,
        last_poll=olt.last_poll,
        last_error=olt.last_error,
        onu_count=onu_count,
        online_onu_count=online_onu_count,
        created_at=olt.created_at,
        updated_at=olt.updated_at
    )


@app.delete("/api/olts/{olt_id}", status_code=204)
def delete_olt(olt_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Delete OLT and all its ONUs (admin only)"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    db.delete(olt)
    db.commit()
    return None


@app.post("/api/olts/{olt_id}/poll", response_model=PollResult)
async def poll_single_olt(olt_id: int, db: Session = Depends(get_db)):
    """Manually trigger poll for specific OLT using SNMP (fast ~2 seconds)"""
    from license_manager import license_manager
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        # Use SNMP for fast polling
        loop = asyncio.get_event_loop()
        onus_data, status_map = await loop.run_in_executor(
            thread_executor,
            poll_olt_snmp,
            olt.ip_address,
            "public"  # SNMP community string
        )

        # Update database (same logic as polling loop)
        olt.is_online = True
        olt.last_poll = datetime.utcnow()
        olt.last_error = None

        existing_onus = {
            (o.pon_port, o.onu_id): o
            for o in db.query(ONU).filter(ONU.olt_id == olt.id).all()
        }

        seen_keys = set()

        # Collect status changes for batched notification
        onus_went_online = []
        onus_went_offline = []

        # Check license ONU limit for manual poll
        license_info = license_manager.get_license_info()
        max_onus = license_info.get('max_onus', 100)
        current_onu_count = db.query(ONU).count()
        onu_limit_reached = current_onu_count >= max_onus

        for onu_data in onus_data:
            key = (onu_data.pon_port, onu_data.onu_id)
            seen_keys.add(key)

            # Get online status from status_map using pon:onu key
            # (handles duplicate MACs across PON ports correctly)
            status_key = f"{onu_data.pon_port}:{onu_data.onu_id}"
            is_online = status_map.get(status_key, False)

            # Get RX power from SNMP
            rx_power = onu_data.rx_power

            if key in existing_onus:
                existing = existing_onus[key]
                was_online = existing.is_online
                existing.mac_address = onu_data.mac_address
                existing.is_online = is_online
                existing.missing_polls = 0  # Reset counter - ONU found in SNMP
                # Update description
                if onu_data.description:
                    existing.description = onu_data.description
                # Always update model if available from SNMP
                if onu_data.model:
                    existing.model = onu_data.model
                # Update optical diagnostics only when online
                if is_online:
                    if onu_data.distance is not None:
                        existing.distance = onu_data.distance
                    if rx_power is not None:
                        existing.rx_power = rx_power
                    existing.last_seen = datetime.utcnow()
                else:
                    # Clear optical data when ONU is offline (no live traffic)
                    existing.distance = None
                    existing.rx_power = None
                existing.updated_at = datetime.utcnow()

                # Collect status changes for batched notification
                if was_online and not is_online:
                    onus_went_offline.append(existing)
                elif not was_online and is_online:
                    onus_went_online.append(existing)
            else:
                # Check ONU limit before creating new ONU
                if onu_limit_reached:
                    logger.warning(f"[Manual Poll] ONU limit reached ({max_onus}). Skipping new ONU: {onu_data.mac_address}")
                    continue

                new_onu = ONU(
                    olt_id=olt.id,
                    pon_port=onu_data.pon_port,
                    onu_id=onu_data.onu_id,
                    mac_address=onu_data.mac_address,
                    description=onu_data.description,
                    model=onu_data.model,
                    is_online=is_online,
                    distance=onu_data.distance,
                    rx_power=rx_power,
                    last_seen=datetime.utcnow()
                )
                db.add(new_onu)
                current_onu_count += 1
                onu_limit_reached = current_onu_count >= max_onus

        # Track ONUs not found in SNMP - delete after 3 consecutive missed polls
        # This syncs with OLT when ONUs are deleted from OLT config
        onus_to_delete = []
        for key, onu in existing_onus.items():
            if key not in seen_keys:
                onu.missing_polls += 1
                onu.updated_at = datetime.utcnow()

                if onu.missing_polls >= 3:
                    # ONU not seen for 3 polls - delete it
                    onus_to_delete.append(onu)
                    print(f"Auto-deleting ONU {onu.mac_address} (PON {onu.pon_port}/{onu.onu_id}) - not found in {onu.missing_polls} consecutive polls")
                elif onu.is_online:
                    # Mark offline but keep tracking
                    onu.is_online = False
                    onu.distance = None
                    onu.rx_power = None
                    onus_went_offline.append(onu)

        # Delete ONUs that have been missing for 3+ polls
        for onu in onus_to_delete:
            db.delete(onu)

        # Send batched notification for all status changes
        send_whatsapp_notification_batch(db, onus_went_online, onus_went_offline, olt.name)

        db.commit()

        # Collect traffic history (including port traffic)
        await collect_traffic_history(olt, db)
        db.commit()

        return PollResult(
            olt_id=olt.id,
            olt_name=olt.name,
            success=True,
            message=f"Successfully polled. Found {len(onus_data)} ONUs.",
            onus_found=len(onus_data)
        )

    except Exception as e:
        olt.is_online = False
        olt.last_poll = datetime.utcnow()
        olt.last_error = str(e)
        db.commit()

        return PollResult(
            olt_id=olt.id,
            olt_name=olt.name,
            success=False,
            message=str(e),
            onus_found=0
        )


# ============ OLT Control Panel Endpoints ============

@app.get("/api/olts/{olt_id}/vlans")
async def get_olt_vlans(olt_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Get VLAN configuration from OLT (admin only)"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        loop = asyncio.get_event_loop()
        connector = OLTConnector(olt.ip_address, olt.username, decrypt_sensitive(olt.password))
        vlan_config = await loop.run_in_executor(thread_executor, connector.get_vlan_config)
        return {"success": True, "vlans": vlan_config.get('vlans', []), "raw_config": vlan_config.get('raw_config', '')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SetONUVlanRequest(BaseModel):
    pon_port: int
    onu_id: int
    vlan_id: int
    mode: str = "tag"  # transparent, tag, translate


@app.post("/api/olts/{olt_id}/set-onu-vlan")
async def set_onu_vlan(olt_id: int, request: SetONUVlanRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Set VLAN for a specific ONU (admin only)"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        loop = asyncio.get_event_loop()
        connector = OLTConnector(olt.ip_address, olt.username, decrypt_sensitive(olt.password))
        result = await loop.run_in_executor(
            thread_executor,
            lambda: connector.set_onu_vlan(request.pon_port, request.onu_id, request.vlan_id, request.mode)
        )
        return {"success": result, "message": f"VLAN {request.vlan_id} set for ONU {request.pon_port}:{request.onu_id} in {request.mode} mode"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SetPortStatusRequest(BaseModel):
    port_type: str  # pon, ge, xge
    port_number: int
    enabled: bool


@app.post("/api/olts/{olt_id}/set-port-status")
async def set_port_status(olt_id: int, request: SetPortStatusRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Enable or disable a port on OLT (admin only)"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        loop = asyncio.get_event_loop()
        connector = OLTConnector(olt.ip_address, olt.username, decrypt_sensitive(olt.password))
        result = await loop.run_in_executor(
            thread_executor,
            lambda: connector.set_port_status(request.port_type, request.port_number, request.enabled)
        )
        status = "enabled" if request.enabled else "disabled"
        return {"success": result, "message": f"Port {request.port_type} {request.port_number} {status}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/olts/{olt_id}/reboot")
async def reboot_olt(olt_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Reboot the entire OLT device (admin only)"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        loop = asyncio.get_event_loop()
        connector = OLTConnector(olt.ip_address, olt.username, decrypt_sensitive(olt.password))
        result = await loop.run_in_executor(thread_executor, connector.reboot_olt)

        # Mark OLT as offline since it's rebooting
        olt.is_online = False
        olt.last_error = "Rebooting..."
        db.commit()

        return {"success": result, "message": f"OLT {olt.name} is rebooting. It will take 2-3 minutes to come back online."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/olts/{olt_id}/save-config")
async def save_olt_config(olt_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Save running config to startup config (admin only)"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        loop = asyncio.get_event_loop()
        connector = OLTConnector(olt.ip_address, olt.username, decrypt_sensitive(olt.password))
        result = await loop.run_in_executor(thread_executor, connector.save_config)
        return {"success": result, "message": "Configuration saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExecuteCommandRequest(BaseModel):
    command: str


# Security: Whitelist of allowed commands for OLT execution
ALLOWED_OLT_COMMANDS = [
    'show',           # Read-only show commands
    'display',        # Display commands (some OLTs use this)
    'ping',           # Network diagnostics
    'traceroute',     # Network diagnostics
]

# Security: Blacklist of dangerous commands that are never allowed
BLOCKED_OLT_COMMANDS = [
    'delete', 'erase', 'format', 'reset',      # Destructive
    'no interface', 'no confirm', 'no onu',    # Config deletion
    'system', 'reload', 'reboot',              # System restart
    'copy', 'tftp', 'ftp',                     # File transfer
    'password', 'secret', 'enable',            # Credential access
    'radius', 'tacacs',                        # AAA config
    'crypto', 'key', 'certificate',            # Security config
    'terminal', 'shell', 'bash',               # Shell access
    'rm ', 'wget', 'curl',                     # Linux commands
    ';', '&&', '||', '|', '`', '$(',           # Command injection
]


def validate_olt_command(command: str) -> tuple[bool, str]:
    """Validate OLT command against security rules"""
    cmd_lower = command.lower().strip()

    # Check for command injection patterns
    for blocked in BLOCKED_OLT_COMMANDS:
        if blocked in cmd_lower:
            return False, f"Blocked command or pattern: {blocked}"

    # Check if command starts with allowed prefix
    cmd_starts_valid = False
    for allowed in ALLOWED_OLT_COMMANDS:
        if cmd_lower.startswith(allowed):
            cmd_starts_valid = True
            break

    if not cmd_starts_valid:
        return False, f"Command must start with one of: {', '.join(ALLOWED_OLT_COMMANDS)}"

    # Command length limit
    if len(command) > 500:
        return False, "Command too long (max 500 characters)"

    return True, "OK"


@app.post("/api/olts/{olt_id}/execute-command")
async def execute_olt_command(olt_id: int, request: ExecuteCommandRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Execute a custom CLI command on OLT (admin only) - restricted to safe read-only commands"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    # Validate command against security rules
    is_valid, message = validate_olt_command(request.command)
    if not is_valid:
        logger.warning(f"[SECURITY] Blocked command attempt by {user.username}: {request.command}")
        raise HTTPException(status_code=400, detail=f"Command not allowed: {message}")

    try:
        loop = asyncio.get_event_loop()
        connector = OLTConnector(olt.ip_address, olt.username, decrypt_sensitive(olt.password))
        output = await loop.run_in_executor(
            thread_executor,
            lambda: connector.execute_custom_command(request.command)
        )
        logger.info(f"[AUDIT] Command executed by {user.username} on OLT {olt.name}: {request.command}")
        return {"success": True, "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ ONU Endpoints ============

@app.get("/api/olts/{olt_id}/onus", response_model=ONUListResponse)
def list_onus_by_olt(olt_id: int, db: Session = Depends(get_db)):
    """List ONUs for specific OLT"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    onus = db.query(ONU).filter(ONU.olt_id == olt_id).order_by(
        ONU.pon_port, ONU.onu_id
    ).all()

    response_onus = []
    for onu in onus:
        region_name = None
        region_color = None
        if onu.region_id:
            region = db.query(Region).filter(Region.id == onu.region_id).first()
            if region:
                region_name = region.name
                region_color = region.color
        response_onus.append(ONUResponse(
            id=onu.id,
            olt_id=onu.olt_id,
            olt_name=olt.name,
            region_id=onu.region_id,
            region_name=region_name,
            region_color=region_color,
            pon_port=onu.pon_port,
            onu_id=onu.onu_id,
            mac_address=onu.mac_address,
            description=onu.description,
            is_online=onu.is_online,
            latitude=onu.latitude,
            longitude=onu.longitude,
            address=onu.address,
            google_maps_url=get_google_maps_url(onu.latitude, onu.longitude),
            distance=onu.distance,
            rx_power=onu.rx_power,
            onu_rx_power=onu.onu_rx_power,
            onu_tx_power=onu.onu_tx_power,
            onu_temperature=onu.onu_temperature,
            onu_voltage=onu.onu_voltage,
            onu_tx_bias=onu.onu_tx_bias,
            model=onu.model,
            image_url=onu.image_url,
            image_urls=parse_image_urls(onu.image_urls),
            last_seen=onu.last_seen,
            created_at=onu.created_at
        ))

    return ONUListResponse(onus=response_onus, total=len(response_onus))


@app.get("/api/onus", response_model=ONUListResponse)
def list_all_onus(
    q: Optional[str] = Query(None, description="Search by customer name or MAC"),
    olt_id: Optional[int] = Query(None, description="Filter by OLT ID"),
    pon_port: Optional[int] = Query(None, description="Filter by PON port"),
    region_id: Optional[int] = Query(None, description="Filter by Region ID"),
    online_only: bool = Query(False, description="Show only online ONUs"),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """List all ONUs with optional filters (filtered by user access)"""
    allowed_olt_ids = get_user_allowed_olt_ids(user, db)

    query = db.query(ONU, OLT.name.label("olt_name")).join(OLT)

    # Filter by user's allowed OLTs
    if allowed_olt_ids is not None:
        query = query.filter(ONU.olt_id.in_(allowed_olt_ids))

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                ONU.description.ilike(search),
                ONU.mac_address.ilike(search)
            )
        )

    if olt_id:
        query = query.filter(ONU.olt_id == olt_id)

    if pon_port:
        query = query.filter(ONU.pon_port == pon_port)

    if region_id:
        query = query.filter(ONU.region_id == region_id)

    if online_only:
        query = query.filter(ONU.is_online == True)

    results = query.order_by(OLT.name, ONU.pon_port, ONU.onu_id).all()

    # Build a cache for region names and colors
    region_ids = set(onu.region_id for onu, _ in results if onu.region_id)
    region_names = {}
    region_colors = {}
    if region_ids:
        regions = db.query(Region).filter(Region.id.in_(region_ids)).all()
        region_names = {r.id: r.name for r in regions}
        region_colors = {r.id: r.color for r in regions}

    response_onus = [
        ONUResponse(
            id=onu.id,
            olt_id=onu.olt_id,
            olt_name=olt_name,
            region_id=onu.region_id,
            region_name=region_names.get(onu.region_id),
            region_color=region_colors.get(onu.region_id),
            pon_port=onu.pon_port,
            onu_id=onu.onu_id,
            mac_address=onu.mac_address,
            description=onu.description,
            is_online=onu.is_online,
            latitude=onu.latitude,
            longitude=onu.longitude,
            address=onu.address,
            google_maps_url=get_google_maps_url(onu.latitude, onu.longitude),
            distance=onu.distance,
            rx_power=onu.rx_power,
            onu_rx_power=onu.onu_rx_power,
            onu_tx_power=onu.onu_tx_power,
            onu_temperature=onu.onu_temperature,
            onu_voltage=onu.onu_voltage,
            onu_tx_bias=onu.onu_tx_bias,
            model=onu.model,
            image_url=onu.image_url,
            image_urls=parse_image_urls(onu.image_urls),
            last_seen=onu.last_seen,
            created_at=onu.created_at
        )
        for onu, olt_name in results
    ]

    return ONUListResponse(onus=response_onus, total=len(response_onus))


@app.get("/api/onus/search", response_model=ONUListResponse)
def search_onus(
    q: str = Query(..., min_length=1, description="Search query"),
    db: Session = Depends(get_db)
):
    """Search ONUs by customer name or MAC address"""
    search = f"%{q}%"
    results = db.query(ONU, OLT.name.label("olt_name")).join(OLT).filter(
        or_(
            ONU.description.ilike(search),
            ONU.mac_address.ilike(search)
        )
    ).order_by(OLT.name, ONU.pon_port, ONU.onu_id).all()

    # Build a cache for region names and colors
    region_ids = set(onu.region_id for onu, _ in results if onu.region_id)
    region_names = {}
    region_colors = {}
    if region_ids:
        regions = db.query(Region).filter(Region.id.in_(region_ids)).all()
        region_names = {r.id: r.name for r in regions}
        region_colors = {r.id: r.color for r in regions}

    response_onus = [
        ONUResponse(
            id=onu.id,
            olt_id=onu.olt_id,
            olt_name=olt_name,
            region_id=onu.region_id,
            region_name=region_names.get(onu.region_id),
            region_color=region_colors.get(onu.region_id),
            pon_port=onu.pon_port,
            onu_id=onu.onu_id,
            mac_address=onu.mac_address,
            description=onu.description,
            is_online=onu.is_online,
            latitude=onu.latitude,
            longitude=onu.longitude,
            address=onu.address,
            google_maps_url=get_google_maps_url(onu.latitude, onu.longitude),
            distance=onu.distance,
            rx_power=onu.rx_power,
            onu_rx_power=onu.onu_rx_power,
            onu_tx_power=onu.onu_tx_power,
            onu_temperature=onu.onu_temperature,
            onu_voltage=onu.onu_voltage,
            onu_tx_bias=onu.onu_tx_bias,
            model=onu.model,
            image_url=onu.image_url,
            image_urls=parse_image_urls(onu.image_urls),
            last_seen=onu.last_seen,
            created_at=onu.created_at
        )
        for onu, olt_name in results
    ]

    return ONUListResponse(onus=response_onus, total=len(response_onus))


@app.get("/api/onus/{onu_id}", response_model=ONUResponse)
def get_onu(onu_id: int, db: Session = Depends(get_db)):
    """Get specific ONU by ID"""
    result = db.query(ONU, OLT.name.label("olt_name")).join(OLT).filter(
        ONU.id == onu_id
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="ONU not found")

    onu, olt_name = result

    region_name = None
    region_color = None
    if onu.region_id:
        region = db.query(Region).filter(Region.id == onu.region_id).first()
        if region:
            region_name = region.name
            region_color = region.color

    return ONUResponse(
        id=onu.id,
        olt_id=onu.olt_id,
        olt_name=olt_name,
        region_id=onu.region_id,
        region_name=region_name,
        region_color=region_color,
        pon_port=onu.pon_port,
        onu_id=onu.onu_id,
        mac_address=onu.mac_address,
        description=onu.description,
        is_online=onu.is_online,
        latitude=onu.latitude,
        longitude=onu.longitude,
        address=onu.address,
        google_maps_url=get_google_maps_url(onu.latitude, onu.longitude),
        distance=onu.distance,
        rx_power=onu.rx_power,
        onu_rx_power=onu.onu_rx_power,
        onu_tx_power=onu.onu_tx_power,
        onu_temperature=onu.onu_temperature,
        onu_voltage=onu.onu_voltage,
        onu_tx_bias=onu.onu_tx_bias,
        model=onu.model,
        image_url=onu.image_url,
        image_urls=parse_image_urls(onu.image_urls),
        last_seen=onu.last_seen,
        created_at=onu.created_at
    )


def sync_onu_description_to_olt(olt_ip: str, olt_username: str, olt_password: str,
                                  pon_port: int, onu_id: int, description: str):
    """Background task to sync ONU description to OLT via web interface"""
    from olt_web_scraper import set_onu_description_web
    try:
        success = set_onu_description_web(
            ip=olt_ip,
            pon_port=pon_port,
            onu_id=onu_id,
            description=description or "",
            username=olt_username,
            password=olt_password
        )
        if success:
            logger.info(f"Background sync: ONU 0/{pon_port}:{onu_id} description synced to OLT {olt_ip}")
        else:
            logger.warning(f"Background sync: Failed to sync description for ONU 0/{pon_port}:{onu_id} on {olt_ip}")
    except Exception as e:
        logger.error(f"Background sync failed for ONU 0/{pon_port}:{onu_id} on {olt_ip}: {e}")


@app.put("/api/onus/{onu_id}", response_model=ONUResponse)
async def update_onu(onu_id: int, data: dict, background_tasks: BackgroundTasks,
                     user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Update ONU description and/or region (any logged in user)"""
    result = db.query(ONU, OLT).join(OLT).filter(
        ONU.id == onu_id
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="ONU not found")

    onu, olt = result

    if "description" in data:
        new_desc = data["description"] or None

        # Update local database immediately
        onu.description = new_desc
        onu.updated_at = datetime.utcnow()

        # Sync to OLT in background via web interface (non-blocking)
        web_user = olt.web_username or olt.username or 'admin'
        web_pass = decrypt_sensitive(olt.web_password) if olt.web_password else decrypt_sensitive(olt.password) or 'admin'
        background_tasks.add_task(
            sync_onu_description_to_olt,
            olt.ip_address, web_user, web_pass,
            onu.pon_port, onu.onu_id, new_desc or ""
        )
        logger.info(f"Queued background sync for ONU {onu_id} to OLT {olt.name} via web")

    # Handle region_id update (can be set to null to remove from region)
    if "region_id" in data:
        new_region_id = data["region_id"]
        if new_region_id is not None:
            # Verify region exists
            region = db.query(Region).filter(Region.id == new_region_id).first()
            if not region:
                raise HTTPException(status_code=400, detail="Region not found")
        onu.region_id = new_region_id
        onu.updated_at = datetime.utcnow()

    # Handle location updates
    if "latitude" in data:
        onu.latitude = data["latitude"]
        onu.updated_at = datetime.utcnow()
    if "longitude" in data:
        onu.longitude = data["longitude"]
        onu.updated_at = datetime.utcnow()
    if "address" in data:
        onu.address = data["address"]
        onu.updated_at = datetime.utcnow()
    if "image_url" in data:
        onu.image_url = data["image_url"]
        onu.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(onu)

    region_name = None
    region_color = None
    if onu.region_id:
        region = db.query(Region).filter(Region.id == onu.region_id).first()
        if region:
            region_name = region.name
            region_color = region.color

    # Parse image_urls from JSON if exists
    return ONUResponse(
        id=onu.id,
        olt_id=onu.olt_id,
        olt_name=olt.name,
        region_id=onu.region_id,
        region_name=region_name,
        region_color=region_color,
        pon_port=onu.pon_port,
        onu_id=onu.onu_id,
        mac_address=onu.mac_address,
        description=onu.description,
        is_online=onu.is_online,
        latitude=onu.latitude,
        longitude=onu.longitude,
        address=onu.address,
        google_maps_url=get_google_maps_url(onu.latitude, onu.longitude),
        distance=onu.distance,
        rx_power=onu.rx_power,
        onu_rx_power=onu.onu_rx_power,
        onu_tx_power=onu.onu_tx_power,
        onu_temperature=onu.onu_temperature,
        onu_voltage=onu.onu_voltage,
        onu_tx_bias=onu.onu_tx_bias,
        model=onu.model,
        image_url=onu.image_url,
        image_urls=parse_image_urls(onu.image_urls),
        last_seen=onu.last_seen,
        created_at=onu.created_at
    )


@app.post("/api/onus/{onu_id}/image")
async def upload_onu_image(onu_id: int, file: UploadFile = File(...),
                           user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Upload building/location image for ONU (supports up to 3 images)"""
    onu = db.query(ONU).filter(ONU.id == onu_id).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    # Parse existing images
    existing_images = []
    if onu.image_urls:
        try:
            existing_images = json.loads(onu.image_urls)
        except:
            existing_images = []

    # Check if already at max (3 images)
    if len(existing_images) >= 3:
        raise HTTPException(status_code=400, detail="Maximum 3 images allowed. Delete an existing image first.")

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, GIF, WEBP")

    # Limit file size (5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 5MB")

    # Generate unique filename
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"onu_{onu_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # Save new image
    with open(filepath, 'wb') as f:
        f.write(contents)

    # Add to list and update database
    new_image_url = f"/uploads/{filename}"
    existing_images.append(new_image_url)
    onu.image_urls = json.dumps(existing_images)
    onu.image_url = existing_images[0]  # Keep first image as legacy field
    onu.updated_at = datetime.utcnow()
    db.commit()

    return {"image_url": new_image_url, "image_urls": existing_images, "message": "Image uploaded successfully"}


@app.delete("/api/onus/{onu_id}/image")
def delete_onu_image(onu_id: int, image_index: int = 0, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Delete building/location image for ONU by index (0, 1, or 2)"""
    onu = db.query(ONU).filter(ONU.id == onu_id).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    # Parse existing images
    existing_images = []
    if onu.image_urls:
        try:
            existing_images = json.loads(onu.image_urls)
        except:
            existing_images = []

    if image_index < 0 or image_index >= len(existing_images):
        raise HTTPException(status_code=400, detail=f"Invalid image index. Available: 0-{len(existing_images)-1}")

    # Delete file from disk
    image_url = existing_images[image_index]
    filename = image_url.split('/')[-1]
    filepath = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    # Remove from list and update database
    existing_images.pop(image_index)
    onu.image_urls = json.dumps(existing_images) if existing_images else None
    onu.image_url = existing_images[0] if existing_images else None  # Update legacy field
    onu.updated_at = datetime.utcnow()
    db.commit()

    return {"image_urls": existing_images, "message": "Image deleted successfully"}


@app.delete("/api/onus/{onu_id}", status_code=204)
def delete_onu(onu_id: int, delete_from_olt: bool = True, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Delete ONU record (admin only). Also deletes from OLT if delete_from_olt=true."""
    from olt_web_scraper import delete_onu_web

    onu = db.query(ONU).filter(ONU.id == onu_id).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    # Try to delete from OLT first if requested
    olt_delete_success = False
    olt_delete_error = None

    # Delete from OLT if requested and OLT is online
    if delete_from_olt:
        # Get the OLT
        olt = db.query(OLT).filter(OLT.id == onu.olt_id).first()
        if olt and olt.is_online:
            try:
                # Use web credentials if set, otherwise fall back to standard credentials
                web_user = olt.web_username or olt.username or 'admin'
                web_pass = decrypt_sensitive(olt.web_password) if olt.web_password else decrypt_sensitive(olt.password) or 'admin'

                olt_delete_success = delete_onu_web(
                    ip=olt.ip_address,
                    pon_port=onu.pon_port,
                    onu_id=onu.onu_id,
                    username=web_user,
                    password=web_pass
                )
                if olt_delete_success:
                    logger.info(f"Successfully deleted ONU {onu.mac_address} from OLT {olt.name}")
            except Exception as e:
                olt_delete_error = str(e)
                logger.warning(f"Failed to delete ONU from OLT: {e}")
        elif olt and not olt.is_online:
            logger.warning(f"OLT {olt.name} is offline - cannot delete ONU from OLT")

    # Delete from database only (not from OLT if offline)
    db.delete(onu)
    db.commit()
    return None


@app.post("/api/onus/{onu_id}/reboot")
def reboot_onu(onu_id: int, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Reboot an ONU via OLT web interface"""
    from olt_web_scraper import reboot_onu_web

    # Get the ONU
    onu = db.query(ONU).filter(ONU.id == onu_id).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    # Get the OLT
    olt = db.query(OLT).filter(OLT.id == onu.olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    # Check if OLT is online
    if not olt.is_online:
        raise HTTPException(status_code=503, detail="OLT is offline")

    try:
        # Use web interface to reboot ONU (more reliable than SSH)
        # Use web credentials if set, otherwise fall back to standard credentials
        web_user = olt.web_username or olt.username or 'admin'
        web_pass = decrypt_sensitive(olt.web_password) if olt.web_password else decrypt_sensitive(olt.password) or 'admin'

        success = reboot_onu_web(
            ip=olt.ip_address,
            pon_port=onu.pon_port,
            onu_id=onu.onu_id,
            username=web_user,
            password=web_pass
        )

        if success:
            logger.info(f"User {user.username} rebooted ONU {onu.id} (0/{onu.pon_port}:{onu.onu_id}) on OLT {olt.name}")
            return {"success": True, "message": f"ONU {onu.description or onu.mac_address} reboot command sent"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send reboot command")

    except Exception as e:
        logger.error(f"Failed to reboot ONU {onu_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reboot ONU: {e}")


def get_google_maps_url(lat: float, lng: float) -> str:
    """Generate Google Maps URL from coordinates"""
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps?q={lat},{lng}"
    return None

# ============ Region Endpoints ============

@app.get("/api/regions", response_model=RegionListResponse)
def list_regions(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """List regions visible to user (admin sees all, operator sees only their own)"""
    if user.role == "admin":
        # Admin sees all regions
        regions = db.query(Region).order_by(Region.name).all()
    else:
        # Operator sees only their own regions
        regions = db.query(Region).filter(Region.owner_id == user.id).order_by(Region.name).all()

    response_regions = []
    for region in regions:
        onu_count = db.query(ONU).filter(ONU.region_id == region.id).count()
        owner_name = None
        if region.owner_id:
            owner = db.query(User).filter(User.id == region.owner_id).first()
            if owner:
                owner_name = owner.full_name or owner.username
        response_regions.append(RegionResponse(
            id=region.id,
            name=region.name,
            description=region.description,
            color=region.color,
            owner_id=region.owner_id,
            owner_name=owner_name,
            latitude=region.latitude,
            longitude=region.longitude,
            address=region.address,
            google_maps_url=get_google_maps_url(region.latitude, region.longitude),
            onu_count=onu_count,
            created_at=region.created_at
        ))

    return RegionListResponse(regions=response_regions, total=len(response_regions))


@app.get("/api/regions/{region_id}", response_model=RegionResponse)
def get_region(region_id: int, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Get specific region by ID (access controlled)"""
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Access control: admin sees all, operator sees only their own
    if user.role != "admin" and region.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this region")

    onu_count = db.query(ONU).filter(ONU.region_id == region.id).count()
    owner_name = None
    if region.owner_id:
        owner = db.query(User).filter(User.id == region.owner_id).first()
        if owner:
            owner_name = owner.full_name or owner.username

    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description,
        color=region.color,
        owner_id=region.owner_id,
        owner_name=owner_name,
        latitude=region.latitude,
        longitude=region.longitude,
        address=region.address,
        google_maps_url=get_google_maps_url(region.latitude, region.longitude),
        onu_count=onu_count,
        created_at=region.created_at
    )


@app.post("/api/regions", response_model=RegionResponse, status_code=201)
def create_region(region_data: RegionCreate, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Create new region (operators own their regions, admin creates global regions)"""
    # Check for duplicate name within user's scope
    if user.role == "admin":
        # Admin: check against all regions
        existing = db.query(Region).filter(Region.name == region_data.name).first()
    else:
        # Operator: check only against their own regions
        existing = db.query(Region).filter(
            Region.name == region_data.name,
            Region.owner_id == user.id
        ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Region with this name already exists")

    # Set owner_id: NULL for admin (visible to all), user.id for operators (private)
    owner_id = None if user.role == "admin" else user.id

    region = Region(
        name=region_data.name,
        description=region_data.description,
        color=region_data.color,
        owner_id=owner_id,
        latitude=region_data.latitude,
        longitude=region_data.longitude,
        address=region_data.address
    )
    db.add(region)
    db.commit()
    db.refresh(region)

    owner_name = None
    if owner_id:
        owner_name = user.full_name or user.username

    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description,
        color=region.color,
        owner_id=region.owner_id,
        owner_name=owner_name,
        latitude=region.latitude,
        longitude=region.longitude,
        address=region.address,
        google_maps_url=get_google_maps_url(region.latitude, region.longitude),
        onu_count=0,
        created_at=region.created_at
    )


@app.put("/api/regions/{region_id}", response_model=RegionResponse)
def update_region(region_id: int, region_data: RegionUpdate, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Update region (access controlled - owner or admin)"""
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Access control: admin can edit all, operator can only edit their own
    if user.role != "admin" and region.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this region")

    if region_data.name is not None:
        # Check for duplicate name within scope
        if user.role == "admin":
            existing = db.query(Region).filter(
                Region.name == region_data.name,
                Region.id != region_id
            ).first()
        else:
            existing = db.query(Region).filter(
                Region.name == region_data.name,
                Region.owner_id == user.id,
                Region.id != region_id
            ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Region with this name already exists")
        region.name = region_data.name

    if region_data.description is not None:
        region.description = region_data.description
    if region_data.color is not None:
        region.color = region_data.color
    if region_data.latitude is not None:
        region.latitude = region_data.latitude
    if region_data.longitude is not None:
        region.longitude = region_data.longitude
    if region_data.address is not None:
        region.address = region_data.address

    db.commit()
    db.refresh(region)

    onu_count = db.query(ONU).filter(ONU.region_id == region.id).count()
    owner_name = None
    if region.owner_id:
        owner = db.query(User).filter(User.id == region.owner_id).first()
        if owner:
            owner_name = owner.full_name or owner.username

    return RegionResponse(
        id=region.id,
        name=region.name,
        description=region.description,
        color=region.color,
        owner_id=region.owner_id,
        owner_name=owner_name,
        latitude=region.latitude,
        longitude=region.longitude,
        address=region.address,
        google_maps_url=get_google_maps_url(region.latitude, region.longitude),
        onu_count=onu_count,
        created_at=region.created_at
    )


@app.delete("/api/regions/{region_id}", status_code=204)
def delete_region(region_id: int, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Delete region (admin can delete any, operator can delete their own)"""
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Access control: admin can delete all, operator can only delete their own
    if user.role != "admin" and region.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this region")

    # Clear region_id from ONUs
    db.query(ONU).filter(ONU.region_id == region_id).update({"region_id": None})

    db.delete(region)
    db.commit()
    return None


@app.get("/api/regions/{region_id}/onus", response_model=ONUListResponse)
def list_onus_by_region(region_id: int, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """List ONUs in a specific region (access controlled)"""
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    # Access control: admin sees all, operator sees only their own regions
    if user.role != "admin" and region.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this region")

    results = db.query(ONU, OLT.name.label("olt_name")).join(OLT).filter(
        ONU.region_id == region_id
    ).order_by(OLT.name, ONU.pon_port, ONU.onu_id).all()

    response_onus = [
        ONUResponse(
            id=onu.id,
            olt_id=onu.olt_id,
            olt_name=olt_name,
            region_id=onu.region_id,
            region_name=region.name,
            region_color=region.color,
            pon_port=onu.pon_port,
            onu_id=onu.onu_id,
            mac_address=onu.mac_address,
            description=onu.description,
            is_online=onu.is_online,
            latitude=onu.latitude,
            longitude=onu.longitude,
            address=onu.address,
            google_maps_url=get_google_maps_url(onu.latitude, onu.longitude),
            distance=onu.distance,
            rx_power=onu.rx_power,
            onu_rx_power=onu.onu_rx_power,
            onu_tx_power=onu.onu_tx_power,
            onu_temperature=onu.onu_temperature,
            onu_voltage=onu.onu_voltage,
            onu_tx_bias=onu.onu_tx_bias,
            model=onu.model,
            image_url=onu.image_url,
            image_urls=parse_image_urls(onu.image_urls),
            last_seen=onu.last_seen,
            created_at=onu.created_at
        )
        for onu, olt_name in results
    ]

    return ONUListResponse(onus=response_onus, total=len(response_onus))


# ============ Authentication Endpoints ============

@app.post("/api/auth/login", response_model=LoginResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login and get access token"""
    # Check if account is locked
    user_check = db.query(User).filter(User.username == credentials.username).first()
    if user_check and user_check.locked_until:
        if datetime.utcnow() < user_check.locked_until:
            remaining = (user_check.locked_until - datetime.utcnow()).seconds // 60
            raise HTTPException(
                status_code=423,
                detail=f"Account locked. Try again in {remaining + 1} minutes."
            )
        else:
            # Lockout expired, reset
            user_check.locked_until = None
            user_check.failed_login_attempts = 0
            db.commit()

    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        # Track failed login attempts
        if user_check:
            user_check.failed_login_attempts = (user_check.failed_login_attempts or 0) + 1
            # Lock account after 5 failed attempts for 15 minutes
            if user_check.failed_login_attempts >= 5:
                user_check.locked_until = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    token = create_access_token({"user_id": user.id, "role": user.role})

    assigned_olt_ids = get_user_olt_ids_list(user, db)

    return LoginResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
            assigned_olt_ids=assigned_olt_ids
        ),
        must_change_password=user.must_change_password or False
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_current_user_info(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Get current logged in user info"""
    assigned_olt_ids = get_user_olt_ids_list(user, db)

    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
        assigned_olt_ids=assigned_olt_ids
    )


# ============ User Management Endpoints (Admin Only) ============

@app.get("/api/users", response_model=UserListResponse)
def list_users(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """List all users (admin only)"""
    users = db.query(User).order_by(User.username).all()

    response_users = []
    for u in users:
        assigned_olt_ids = get_user_olt_ids_list(u, db)
        response_users.append(UserResponse(
            id=u.id,
            username=u.username,
            role=u.role,
            full_name=u.full_name,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login=u.last_login,
            assigned_olt_ids=assigned_olt_ids
        ))

    return UserListResponse(users=response_users, total=len(response_users))


@app.post("/api/users", response_model=UserResponse, status_code=201)
def create_user(user_data: UserCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Create new user (admin only)"""
    # Check license user limit
    from license_manager import license_manager
    license_info = license_manager.get_license_info()
    max_users = license_info.get('max_users', 5)
    current_user_count = db.query(User).count()

    if current_user_count >= max_users:
        package = license_info.get('package_type', 'trial')
        raise HTTPException(
            status_code=403,
            detail=f"User limit reached ({max_users}). Upgrade your package to add more users. Current package: {package}"
        )

    # Check for duplicate username
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role,
        full_name=user_data.full_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Handle OLT assignments (for operators)
    assigned_olt_ids = user_data.assigned_olt_ids or []
    if assigned_olt_ids and user_data.role == "operator":
        for olt_id in assigned_olt_ids:
            # Verify OLT exists
            olt = db.query(OLT).filter(OLT.id == olt_id).first()
            if olt:
                db.execute(user_olts.insert().values(user_id=new_user.id, olt_id=olt_id))
        db.commit()

    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role,
        full_name=new_user.full_name,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        last_login=new_user.last_login,
        assigned_olt_ids=assigned_olt_ids if user_data.role == "operator" else []
    )


@app.put("/api/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_data: UserUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Update user (admin only)"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.password is not None:
        target_user.password_hash = get_password_hash(user_data.password)
    if user_data.role is not None:
        target_user.role = user_data.role
    if user_data.full_name is not None:
        target_user.full_name = user_data.full_name
    if user_data.is_active is not None:
        target_user.is_active = user_data.is_active

    # Handle OLT assignments update
    if user_data.assigned_olt_ids is not None:
        # Clear existing assignments
        db.execute(user_olts.delete().where(user_olts.c.user_id == user_id))

        # Add new assignments (only for operators)
        role = user_data.role if user_data.role is not None else target_user.role
        if role == "operator":
            for olt_id in user_data.assigned_olt_ids:
                olt = db.query(OLT).filter(OLT.id == olt_id).first()
                if olt:
                    db.execute(user_olts.insert().values(user_id=user_id, olt_id=olt_id))

    db.commit()
    db.refresh(target_user)

    assigned_olt_ids = get_user_olt_ids_list(target_user, db)

    return UserResponse(
        id=target_user.id,
        username=target_user.username,
        role=target_user.role,
        full_name=target_user.full_name,
        is_active=target_user.is_active,
        created_at=target_user.created_at,
        last_login=target_user.last_login,
        assigned_olt_ids=assigned_olt_ids
    )


@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Delete user (admin only)"""
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(target_user)
    db.commit()
    return None


# ============ Update Check API ============

@app.get("/api/update-check")
def check_for_updates(current_user: dict = Depends(get_current_user)):
    """Check if software update is available"""
    from license_manager import license_manager, SOFTWARE_VERSION

    update_info = license_manager.update_info

    return {
        "current_version": SOFTWARE_VERSION,
        "update_available": update_info is not None,
        "update": update_info
    }


# Update status tracking
update_status = {
    "in_progress": False,
    "stage": "",
    "progress": 0,
    "error": None,
    "completed": False
}


@app.get("/api/update/status")
def get_update_status(current_user: dict = Depends(get_current_user)):
    """Get current update status"""
    return update_status


@app.post("/api/update/download")
async def download_update(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
):
    """Download update from license server"""
    global update_status
    from license_manager import license_manager, LICENSE_SERVER_URL, SOFTWARE_VERSION

    if update_status["in_progress"]:
        raise HTTPException(status_code=400, detail="Update already in progress")

    # Reset status
    update_status = {
        "in_progress": True,
        "stage": "preparing",
        "progress": 0,
        "error": None,
        "completed": False
    }

    try:
        # Get update info
        update_info = license_manager.update_info
        if not update_info:
            update_status["error"] = "No update available"
            update_status["in_progress"] = False
            raise HTTPException(status_code=400, detail="No update available")

        latest_version = update_info.get("latest_version", "1.0.0")

        # Create updates directory
        updates_dir = Path("/tmp/olt-manager-updates")
        updates_dir.mkdir(exist_ok=True)

        update_status["stage"] = "downloading"
        update_status["progress"] = 10

        # Download from license server
        try:
            response = requests.post(
                f"{LICENSE_SERVER_URL}/api/download-update",
                json={
                    "license_key": license_manager.license_key,
                    "hardware_id": license_manager.hardware_id
                },
                timeout=300,  # 5 minute timeout for download
                stream=True
            )

            if response.status_code != 200:
                error_msg = response.json().get("error", "Download failed")
                update_status["error"] = error_msg
                update_status["in_progress"] = False
                raise HTTPException(status_code=400, detail=error_msg)

            # Save the package
            package_path = updates_dir / f"olt-manager-v{latest_version}.tar.gz"
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(package_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            update_status["progress"] = 10 + int((downloaded / total_size) * 40)

            update_status["stage"] = "downloaded"
            update_status["progress"] = 50
            update_status["package_path"] = str(package_path)
            update_status["new_version"] = latest_version  # Save version for install step

            return {
                "success": True,
                "message": f"Update v{latest_version} downloaded successfully",
                "package_path": str(package_path),
                "version": latest_version
            }

        except requests.exceptions.RequestException as e:
            update_status["error"] = f"Download failed: {str(e)}"
            update_status["in_progress"] = False
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        update_status["error"] = str(e)
        update_status["in_progress"] = False
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update/install")
async def install_update(current_user: User = Depends(require_admin)):
    """Install downloaded update"""
    global update_status
    import tarfile
    import subprocess
    from license_manager import license_manager

    if not update_status.get("package_path"):
        raise HTTPException(status_code=400, detail="No update downloaded")

    package_path = Path(update_status["package_path"])
    if not package_path.exists():
        raise HTTPException(status_code=400, detail="Update package not found")

    try:
        update_status["stage"] = "installing"
        update_status["progress"] = 55

        # Extract to temp directory
        extract_dir = Path("/tmp/olt-manager-update-extract")
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir()

        update_status["progress"] = 60

        # Extract the tarball
        with tarfile.open(package_path, 'r:gz') as tar:
            tar.extractall(extract_dir)

        update_status["stage"] = "backing_up"
        update_status["progress"] = 70

        new_version = update_status.get("new_version", "1.1.0")

        # Check if package includes install script (new self-contained updates)
        package_install_script = extract_dir / "install.sh"
        if package_install_script.exists():
            logger.info("Using package's install script for update")
            update_status["stage"] = "applying"
            update_status["progress"] = 75

            # Make script executable and run it
            package_install_script.chmod(0o755)
            result = subprocess.run(
                ["/bin/bash", str(package_install_script), str(extract_dir), new_version],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"Install script failed: {result.stderr}")
                raise Exception(f"Install script failed: {result.stderr}")

            logger.info(f"Install script output: {result.stdout}")
            update_status["progress"] = 85

        else:
            # Fallback: Legacy install logic for old packages without install.sh
            logger.info("Using legacy install logic (no install.sh in package)")

            # Detect installation type: compiled binary or source
            is_compiled = Path("/opt/olt-manager/olt-manager").exists()

            if is_compiled:
                install_dir = Path("/opt/olt-manager")
                backend_dir = None
                logger.info("Detected compiled binary installation")
            elif Path("/opt/olt-manager/backend").exists():
                install_dir = Path("/opt/olt-manager")
                backend_dir = install_dir / "backend"
            else:
                install_dir = Path("/root/olt-manager")
                backend_dir = install_dir / "backend"

            # Create backup
            backup_dir = Path("/tmp/olt-manager-backup")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            backup_dir.mkdir(parents=True)

            if backend_dir and backend_dir.exists():
                shutil.copytree(str(backend_dir), str(backup_dir / "backend"))

            update_status["stage"] = "applying"
            update_status["progress"] = 80

            # Apply update based on installation type
            if is_compiled:
                # Compiled binary installation - update the binary
                new_binary = extract_dir / "olt-manager"
                if new_binary.exists():
                    # Copy new binary to staging location (can't overwrite running binary)
                    staged_binary = install_dir / "olt-manager.new"
                    shutil.copy2(new_binary, staged_binary)
                    staged_binary.chmod(0o755)
                    logger.info("Staged new binary as olt-manager.new")
                else:
                    logger.warning("No olt-manager binary in update package")

                # Update static folder for compiled installation
                new_static = extract_dir / "static"
                if new_static.exists():
                    # Update /opt/olt-manager/static
                    target_static = install_dir / "static"
                    if target_static.exists():
                        shutil.rmtree(target_static)
                    shutil.copytree(new_static, target_static)
                    logger.info("Updated static folder in /opt/olt-manager")

                    # Also update nginx folder if it exists
                    nginx_html = Path("/var/www/html")
                    if nginx_html.exists():
                        # Clear and copy new frontend
                        for item in nginx_html.iterdir():
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                        for item in new_static.iterdir():
                            dest = nginx_html / item.name
                            if item.is_dir():
                                shutil.copytree(item, dest)
                            else:
                                shutil.copy2(item, dest)
                        logger.info("Updated nginx frontend in /var/www/html")

            elif backend_dir and backend_dir.exists():
                # Source installation - update backend files
                extracted_backend = extract_dir / "backend"
                if extracted_backend.exists():
                    for item in extracted_backend.iterdir():
                        if item.name not in ["venv", "__pycache__", "data"]:
                            dest = backend_dir / item.name
                            if item.is_dir():
                                if dest.exists():
                                    shutil.rmtree(dest)
                                shutil.copytree(item, dest)
                            else:
                                shutil.copy2(item, dest)

            # Apply frontend update
            extracted_frontend = extract_dir / "frontend" / "build"
            if extracted_frontend.exists():
                for nginx_dir in [Path("/var/www/olt-manager"), Path("/var/www/html")]:
                    if nginx_dir.exists():
                        for item in extracted_frontend.iterdir():
                            dest = nginx_dir / item.name
                            if item.is_dir():
                                if dest.exists():
                                    shutil.rmtree(dest)
                                shutil.copytree(item, dest)
                            else:
                                shutil.copy2(item, dest)

            # Update version file
            update_status["progress"] = 85
            if is_compiled:
                version_file = install_dir / "VERSION"
            else:
                version_file = backend_dir / "VERSION"
            version_file.write_text(new_version)
            logger.info(f"Updated VERSION file to {new_version}")

        # Create symlink for database path compatibility (fixes backup/restore)
        # This ensures backup/restore works correctly for compiled installations
        symlink_dir = Path("/root/olt-manager/backend")
        symlink_path = symlink_dir / "olt_manager.db"
        db_target = Path("/opt/olt-manager/olt_manager.db")

        if db_target.exists() and not symlink_path.exists():
            symlink_dir.mkdir(parents=True, exist_ok=True)
            try:
                symlink_path.symlink_to(db_target)
                logger.info("Created database symlink for backup compatibility")
            except Exception as sym_err:
                logger.warning(f"Could not create symlink: {sym_err}")

        update_status["stage"] = "restarting"
        update_status["progress"] = 90

        # Create a script to restart the service after response is sent
        restart_script = Path("/tmp/restart-olt-manager.sh")
        restart_script.write_text("""#!/bin/bash
sleep 2

# For compiled installations, swap the binary before restart
if [ -f /opt/olt-manager/olt-manager.new ]; then
    # Stop service first
    systemctl stop olt-manager 2>/dev/null || systemctl stop olt-backend 2>/dev/null
    sleep 1

    # Backup and swap binary
    cd /opt/olt-manager
    if [ -f olt-manager ]; then
        mv olt-manager olt-manager.old
    fi
    mv olt-manager.new olt-manager
    chmod +x olt-manager

    # Start service
    systemctl start olt-manager 2>/dev/null || systemctl start olt-backend 2>/dev/null
    exit 0
fi

# Try different service names used by different install methods
if systemctl is-active --quiet olt-backend; then
    systemctl restart olt-backend
elif systemctl is-active --quiet olt-manager; then
    systemctl restart olt-manager
else
    # Fallback: manual restart
    cd /opt/olt-manager/backend 2>/dev/null || cd /root/olt-manager/backend
    pkill -f "uvicorn main:app" 2>/dev/null
    sleep 1
    source venv/bin/activate
    nohup python -m uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/olt-manager.log 2>&1 &
fi
""")
        restart_script.chmod(0o755)

        # Run restart script in background
        subprocess.Popen(["/bin/bash", str(restart_script)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True)

        update_status["stage"] = "completed"
        update_status["progress"] = 100
        update_status["completed"] = True
        update_status["in_progress"] = False

        # Cleanup
        if extract_dir.exists():
            shutil.rmtree(extract_dir)

        return {
            "success": True,
            "message": "Update installed successfully. Service is restarting...",
            "restart_in_seconds": 3
        }

    except Exception as e:
        update_status["error"] = str(e)
        update_status["in_progress"] = False
        logger.error(f"Update installation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Installation failed: {str(e)}")


@app.post("/api/update/rollback")
async def rollback_update(current_user: User = Depends(require_admin)):
    """Rollback to previous version"""
    import subprocess

    backup_dir = Path("/root/olt-manager-backup")
    if not backup_dir.exists():
        raise HTTPException(status_code=400, detail="No backup available for rollback")

    try:
        # Restore backend
        backend_backup = backup_dir / "backend"
        if backend_backup.exists():
            backend_dest = Path("/root/olt-manager/backend")
            for item in backend_backup.iterdir():
                if item.name != "venv" and item.name != "__pycache__":
                    dest = backend_dest / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

        # Restart service
        restart_script = Path("/tmp/restart-olt-manager.sh")
        subprocess.Popen(["/bin/bash", str(restart_script)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True)

        return {
            "success": True,
            "message": "Rollback completed. Service is restarting..."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


# ============ Dev Server / Publisher API ============

def is_dev_server():
    """Check if this is the development server"""
    dev_marker = Path("/root/olt-manager/backend/.dev_server")
    return dev_marker.exists()

@app.get("/api/dev/status")
async def get_dev_status():
    """Check if this is a development server - for showing publish UI"""
    from license_manager import SOFTWARE_VERSION
    return {
        "is_dev_server": is_dev_server(),
        "current_version": SOFTWARE_VERSION
    }

from pydantic import BaseModel as PydanticBaseModel

class PublishRequest(PydanticBaseModel):
    version: str
    changelog: str

@app.get("/api/dev/build-status")
async def get_build_status(current_user: User = Depends(require_admin)):
    """Check Nuitka build status"""
    if not is_dev_server():
        raise HTTPException(status_code=403, detail="This feature is only available on development server")

    build_dir = Path("/root/olt-manager/nuitka_build")
    binary_path = build_dir / "olt-manager"
    log_path = Path("/tmp/nuitka_build.log")

    # Check if build is running
    import subprocess
    ps_result = subprocess.run(["pgrep", "-f", "nuitka"], capture_output=True)
    is_building = ps_result.returncode == 0

    # Get log tail
    log_tail = ""
    if log_path.exists():
        log_tail = log_path.read_text()[-2000:]

    # Check binary
    binary_exists = binary_path.exists()
    binary_size = 0
    binary_date = None
    if binary_exists:
        stat = binary_path.stat()
        binary_size = stat.st_size / (1024 * 1024)
        from datetime import datetime
        binary_date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

    return {
        "is_building": is_building,
        "binary_ready": binary_exists and not is_building,
        "binary_size_mb": round(binary_size, 1),
        "binary_date": binary_date,
        "log": log_tail
    }

@app.post("/api/dev/build")
async def start_build(current_user: User = Depends(require_admin), background_tasks: BackgroundTasks = None):
    """Start Nuitka build in background"""
    import subprocess

    if not is_dev_server():
        raise HTTPException(status_code=403, detail="This feature is only available on development server")

    # Check if already building
    ps_result = subprocess.run(["pgrep", "-f", "nuitka"], capture_output=True)
    if ps_result.returncode == 0:
        raise HTTPException(status_code=400, detail="Build already in progress")

    # Start build in background
    build_script = '''
source /root/olt-manager/backend/venv/bin/activate
cd /root/olt-manager/backend
echo "Starting Nuitka build at $(date)"
BUILD_DIR="/root/olt-manager/nuitka_build"
rm -rf "$BUILD_DIR" main.build main.dist main.onefile-build 2>/dev/null
mkdir -p "$BUILD_DIR"
python -m nuitka --standalone --onefile --output-dir="$BUILD_DIR" --output-filename=olt-manager --follow-imports --prefer-source-code main.py
echo "Build finished at $(date)"
ls -lh "$BUILD_DIR/olt-manager" 2>/dev/null || echo "Build failed"
'''
    subprocess.Popen(
        ["bash", "-c", build_script],
        stdout=open("/tmp/nuitka_build.log", "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )

    return {"success": True, "message": "Nuitka build started in background. Check /api/dev/build-status for progress."}

@app.post("/api/dev/publish")
async def publish_update(
    request: PublishRequest,
    current_user: User = Depends(require_admin)
):
    """Publish PROTECTED update using pre-built binary to license server (dev server only)"""
    import subprocess
    import tarfile
    import shutil

    version = request.version
    changelog = request.changelog

    if not is_dev_server():
        raise HTTPException(status_code=403, detail="This feature is only available on development server")

    try:
        result_steps = []
        backend_dir = Path("/root/olt-manager/backend")
        build_dir = Path("/root/olt-manager/nuitka_build")
        binary_path = build_dir / "olt-manager"

        # Check if binary exists
        if not binary_path.exists():
            raise HTTPException(
                status_code=400,
                detail="No pre-built binary found. Click 'Build Binary' first and wait for completion."
            )

        # Check if build is still running
        ps_result = subprocess.run(["pgrep", "-f", "nuitka"], capture_output=True)
        if ps_result.returncode == 0:
            raise HTTPException(
                status_code=400,
                detail="Nuitka build still in progress. Please wait for it to complete."
            )

        binary_size = binary_path.stat().st_size / (1024 * 1024)
        result_steps.append(f"Using pre-built binary: {binary_size:.1f} MB")

        # Step 1: Update VERSION file
        version_file = backend_dir / "VERSION"
        version_file.write_text(version)
        result_steps.append(f"Updated VERSION to {version}")

        # Step 2: Create deployment package
        package_dir = build_dir / "package"
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(exist_ok=True)

        shutil.copy(binary_path, package_dir / "olt-manager")
        shutil.copy(version_file, package_dir / "VERSION")
        (package_dir / "data").mkdir(exist_ok=True)
        (package_dir / "uploads").mkdir(exist_ok=True)

        # Create start script
        start_script = package_dir / "start.sh"
        start_script.write_text("#!/bin/bash\ncd \"$(dirname \"$0\")\"\n./olt-manager\n")
        start_script.chmod(0o755)

        # Create tarball
        package_path = Path("/tmp/olt-manager.tar.gz")
        with tarfile.open(package_path, "w:gz") as tar:
            for item in package_dir.iterdir():
                tar.add(item, arcname=item.name)

        package_size = package_path.stat().st_size / (1024 * 1024)
        result_steps.append(f"Package created: {package_size:.1f} MB (protected binary)")

        # Step 3: Upload to license server via SCP
        license_server = os.environ.get("LICENSE_SERVER", "109.110.185.101")
        license_user = os.environ.get("LICENSE_USER", "testuser")
        license_pass = os.environ.get("LICENSE_PASS")
        if not license_pass:
            raise Exception("LICENSE_PASS environment variable not set")

        scp_result = subprocess.run(
            ["sshpass", "-p", license_pass, "scp", "-o", "StrictHostKeyChecking=no",
             str(package_path), f"{license_user}@{license_server}:/tmp/"],
            capture_output=True, text=True, timeout=300
        )
        if scp_result.returncode != 0:
            raise Exception(f"SCP upload failed: {scp_result.stderr}")

        # Copy to web directory and update version
        import json as json_module
        changelog_escaped = json_module.dumps(changelog)

        ssh_commands = f'''
echo '{license_pass}' | sudo -S bash -c '
# Upload to both locations
cp /tmp/olt-manager.tar.gz /var/www/html/downloads/olt-manager.tar.gz
chmod 644 /var/www/html/downloads/olt-manager.tar.gz
cp /tmp/olt-manager.tar.gz /opt/license-server/updates/olt-manager-{version}.tar.gz
chmod 644 /opt/license-server/updates/olt-manager-{version}.tar.gz

python3 << PYEOF
import json
from datetime import datetime
with open("/opt/license-server/updates.json", "r") as f:
    data = json.load(f)

# Update both latest fields
data["latest"] = "{version}"
data["latest_version"] = "{version}"
data["download_url"] = "https://lic.proxpanel.com/downloads/olt-manager.tar.gz"
data["changelog"] = {changelog_escaped}
data["release_date"] = datetime.now().strftime("%Y-%m-%d")

# Add to versions list
new_version = {{
    "version": "{version}",
    "changelog": {changelog_escaped},
    "filename": "olt-manager-{version}.tar.gz",
    "uploaded_at": datetime.now().strftime("%Y-%m-%d")
}}
if "versions" not in data:
    data["versions"] = []
data["versions"] = [v for v in data["versions"] if v.get("version") != "{version}"]
data["versions"].insert(0, new_version)

with open("/opt/license-server/updates.json", "w") as f:
    json.dump(data, f, indent=2)
print("OK")
PYEOF
'
'''
        ssh_result = subprocess.run(
            ["sshpass", "-p", license_pass, "ssh", "-o", "StrictHostKeyChecking=no",
             f"{license_user}@{license_server}", ssh_commands],
            capture_output=True, text=True, timeout=60
        )
        if ssh_result.returncode != 0:
            raise Exception(f"SSH command failed: {ssh_result.stderr}")

        result_steps.append("Uploaded to license server successfully")

        # Cleanup
        package_path.unlink()

        # Step 4: Reload SOFTWARE_VERSION
        import license_manager
        license_manager.SOFTWARE_VERSION = version
        license_manager.license_manager.update_info = None
        result_steps.append(f"Reloaded version to {version}")

        return {
            "success": True,
            "version": version,
            "message": f"Version {version} published successfully!",
            "steps": result_steps
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Publish failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============ Settings API ============

@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    """Get all settings (public - for page name and refresh time)"""
    settings = db.query(Settings).all()
    # Keys that are stored encrypted
    sensitive_keys = ["whatsapp_secret", "trap_community"]
    result = {}
    for s in settings:
        # Decrypt sensitive values when reading
        result[s.key] = decrypt_sensitive(s.value) if s.key in sensitive_keys else s.value
    # Return defaults if not set
    if "system_name" not in result:
        result["system_name"] = "OLT Manager"
    if "page_name" not in result:
        result["page_name"] = "OLT Manager Pro"
    if "refresh_interval" not in result:
        result["refresh_interval"] = "30"
    if "polling_interval" not in result:
        result["polling_interval"] = "60"
    # WhatsApp defaults
    if "whatsapp_enabled" not in result:
        result["whatsapp_enabled"] = "false"
    if "whatsapp_api_url" not in result:
        result["whatsapp_api_url"] = ""
    if "whatsapp_secret" not in result:
        result["whatsapp_secret"] = ""
    if "whatsapp_account" not in result:
        result["whatsapp_account"] = ""
    if "whatsapp_recipients" not in result:
        result["whatsapp_recipients"] = "[]"
    # SNMP Trap defaults
    if "trap_enabled" not in result:
        result["trap_enabled"] = "true"
    if "trap_port" not in result:
        result["trap_port"] = "162"
    return result


@app.put("/api/settings")
def update_settings(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update settings (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    allowed_keys = ["system_name", "page_name", "refresh_interval", "polling_interval", "whatsapp_enabled",
                    "whatsapp_api_url", "whatsapp_secret", "whatsapp_account", "whatsapp_recipients",
                    "trap_enabled", "trap_port", "trap_community"]
    # Keys that should be encrypted when stored
    sensitive_keys = ["whatsapp_secret", "trap_community"]

    for key, value in data.items():
        if key not in allowed_keys:
            continue
        # Encrypt sensitive values before storing
        store_value = encrypt_sensitive(str(value)) if key in sensitive_keys else str(value)
        setting = db.query(Settings).filter(Settings.key == key).first()
        if setting:
            setting.value = store_value
        else:
            setting = Settings(key=key, value=store_value)
            db.add(setting)
    db.commit()
    return {"message": "Settings updated successfully"}


# ============ Alarm Settings API ============

@app.get("/api/alarm-settings")
def get_alarm_settings(db: Session = Depends(get_db)):
    """Get alarm settings (public - for alarm configuration)"""
    settings = db.query(Settings).all()
    result = {}
    for s in settings:
        if s.key.startswith("alarm_"):
            result[s.key.replace("alarm_", "")] = s.value

    # Return defaults if not set
    defaults = {
        "new_onu_registration": "true",
        "onu_offline": "true",
        "onu_back_online": "true",
        "olt_offline": "true",
        "olt_back_online": "true",
        "weak_signal": "false",
        "weak_signal_threshold": "-25",
        "weak_signal_lower_threshold": "-30",
        "high_temperature": "false",
        "high_temperature_threshold": "60",
        "selected_onus": "[]",
        "selected_regions": "[]",
        "quiet_hours_enabled": "false",
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00"
    }

    for key, default_value in defaults.items():
        if key not in result:
            result[key] = default_value

    # Parse JSON arrays
    try:
        result["selected_onus"] = json.loads(result["selected_onus"])
    except:
        result["selected_onus"] = []
    try:
        result["selected_regions"] = json.loads(result["selected_regions"])
    except:
        result["selected_regions"] = []

    # Convert string booleans to actual booleans
    bool_keys = ["new_onu_registration", "onu_offline", "onu_back_online",
                 "olt_offline", "olt_back_online", "weak_signal",
                 "high_temperature", "quiet_hours_enabled"]
    for key in bool_keys:
        if key in result:
            result[key] = result[key].lower() == "true"

    # Convert numeric strings to numbers
    if "weak_signal_threshold" in result:
        try:
            result["weak_signal_threshold"] = int(result["weak_signal_threshold"])
        except:
            result["weak_signal_threshold"] = -25
    if "weak_signal_lower_threshold" in result:
        try:
            result["weak_signal_lower_threshold"] = int(result["weak_signal_lower_threshold"])
        except:
            result["weak_signal_lower_threshold"] = -30
    if "high_temperature_threshold" in result:
        try:
            result["high_temperature_threshold"] = int(result["high_temperature_threshold"])
        except:
            result["high_temperature_threshold"] = 60

    return result


@app.put("/api/alarm-settings")
def update_alarm_settings(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update alarm settings (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    allowed_keys = ["new_onu_registration", "onu_offline", "onu_back_online",
                    "olt_offline", "olt_back_online", "weak_signal",
                    "weak_signal_threshold", "weak_signal_lower_threshold",
                    "high_temperature", "high_temperature_threshold",
                    "selected_onus", "selected_regions", "quiet_hours_enabled",
                    "quiet_hours_start", "quiet_hours_end"]

    for key, value in data.items():
        if key not in allowed_keys:
            continue
        # Convert lists to JSON strings for storage
        if isinstance(value, list):
            store_value = json.dumps(value)
        elif isinstance(value, bool):
            store_value = "true" if value else "false"
        else:
            store_value = str(value)

        db_key = f"alarm_{key}"
        setting = db.query(Settings).filter(Settings.key == db_key).first()
        if setting:
            setting.value = store_value
        else:
            setting = Settings(key=db_key, value=store_value)
            db.add(setting)
    db.commit()
    return {"message": "Alarm settings updated successfully"}


@app.post("/api/auth/change-password")
def change_password(
    data: dict,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Current password and new password are required")

    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")

    # Verify current password
    if not bcrypt.checkpw(current_password.encode('utf-8'), current_user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Update password and reset must_change_password flag
    new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    current_user.password_hash = new_hash
    current_user.must_change_password = False
    db.commit()

    return {"message": "Password changed successfully"}


# ============ WhatsApp Test Endpoint ============

@app.post("/api/whatsapp/test")
def test_whatsapp(
    data: dict,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Test WhatsApp notification (admin only)"""

    api_url = data.get("api_url", "").strip()
    secret = data.get("secret", "").strip()
    account = data.get("account", "").strip()
    recipient = data.get("recipient", "").strip()

    if not all([api_url, secret, account, recipient]):
        raise HTTPException(status_code=400, detail="All WhatsApp settings are required")

    try:
        # Send test message
        test_message = f"🔔 *OLT Manager Test*\n\nThis is a test notification from OLT Manager.\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        response = requests.post(
            api_url,
            data={
                'secret': secret,
                'account': account,
                'recipient': recipient,
                'type': 'text',
                'message': test_message,
                'priority': 1
            },
            timeout=30
        )

        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("status") == 200:
                    return {"success": True, "message": "Test message sent successfully!"}
                else:
                    return {"success": False, "message": f"API returned: {result.get('message', 'Unknown error')}"}
            except:
                return {"success": True, "message": "Message sent (response received)"}
        else:
            return {"success": False, "message": f"HTTP Error {response.status_code}: {response.text[:200]}"}

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request timed out - check API URL")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Connection failed - check API URL")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ============ OLT Port Endpoints ============

# VSOL model to PON port count mapping
VSOL_PON_COUNTS = {
    'V1600GS': 1, 'V1600GS-F': 1, 'V1600GS-ZF': 1,
    'V1600GT': 2,
    'V1600G0': 4, 'V1600G0-B': 4,
    'V1600D-MINI': 4, 'V1601E04': 4, 'V1600D4': 4,
    'V1600G1': 8, 'V1600G1-B': 8, 'V1600G1-R': 8,
    'V1600D8': 8, 'V1601E04-DP': 4,
    'V1600G2': 16, 'V1600G2-B': 16, 'V1600G2-R': 16,
    'V1600D16': 16,
    'V3600G1': 8, 'V3600G1-C': 8,
}


def get_pon_port_count(model: str) -> int:
    """Get PON port count based on OLT model"""
    if not model:
        return 8  # Default
    model_upper = model.upper().strip()
    for key, count in VSOL_PON_COUNTS.items():
        if key.upper() in model_upper:
            return count
    return 8  # Default to 8 if unknown


# Store previous port counters for rate calculation
_port_counters_cache = {}

def poll_port_traffic_snmp(ip: str, community: str = 'public') -> dict:
    """Poll port traffic counters from OLT via SNMP.
    Returns dict with interface index -> {'rx_bytes': int, 'tx_bytes': int}

    Uses OIDs:
    - 1.3.6.1.2.1.2.2.1.10 (ifInOctets) - input bytes
    - 1.3.6.1.2.1.2.2.1.16 (ifOutOctets) - output bytes
    """
    import subprocess
    import time

    port_traffic = {}

    try:
        # Get input octets (ifInOctets)
        result = subprocess.run(
            ['snmpwalk', '-v2c', '-c', community, '-Oqv', ip, '1.3.6.1.2.1.2.2.1.10'],
            capture_output=True, text=True, timeout=10
        )
        in_octets = result.stdout.strip().split('\n') if result.stdout else []

        # Get output octets (ifOutOctets)
        result = subprocess.run(
            ['snmpwalk', '-v2c', '-c', community, '-Oqv', ip, '1.3.6.1.2.1.2.2.1.16'],
            capture_output=True, text=True, timeout=10
        )
        out_octets = result.stdout.strip().split('\n') if result.stdout else []

        timestamp = time.time()

        # Parse results - ifIndex starts at 1
        # For UPLINK ports (like GE7), data flows are from the INTERNET perspective:
        # - ifInOctets = data FROM internet TO OLT = Customer DOWNLOAD (big number)
        # - ifOutOctets = data FROM OLT TO internet = Customer UPLOAD (small number)
        # So we use ifInOctets as rx_bytes (Download) and ifOutOctets as tx_bytes (Upload)
        for i, (in_oct, out_oct) in enumerate(zip(in_octets, out_octets), start=1):
            try:
                in_bytes = int(in_oct.strip().split(':')[-1].strip())
                out_bytes = int(out_oct.strip().split(':')[-1].strip())
                port_traffic[i] = {
                    'rx_bytes': in_bytes,   # Customer Download = ifInOctets (data from internet)
                    'tx_bytes': out_bytes,  # Customer Upload = ifOutOctets (data to internet)
                    'timestamp': timestamp
                }
            except (ValueError, IndexError):
                continue

    except Exception as e:
        logger.warning(f"Failed to poll port traffic from {ip}: {e}")

    return port_traffic


def calculate_port_rates(olt_id: int, ip: str, current_counters: dict) -> dict:
    """Calculate port traffic rates (kbps) from counter differences."""
    global _port_counters_cache

    cache_key = f"{olt_id}_{ip}"
    rates = {}

    if cache_key in _port_counters_cache:
        prev = _port_counters_cache[cache_key]
        prev_time = prev.get('timestamp', 0)
        curr_time = current_counters.get(1, {}).get('timestamp', 0)

        if curr_time > prev_time:
            time_diff = curr_time - prev_time

            for if_idx, curr in current_counters.items():
                if if_idx in prev:
                    prev_rx = prev[if_idx].get('rx_bytes', 0)
                    prev_tx = prev[if_idx].get('tx_bytes', 0)
                    curr_rx = curr.get('rx_bytes', 0)
                    curr_tx = curr.get('tx_bytes', 0)

                    # Handle counter wraparound (32-bit counters)
                    if curr_rx < prev_rx:
                        curr_rx += 2**32
                    if curr_tx < prev_tx:
                        curr_tx += 2**32

                    # Calculate rates in kbps (bytes * 8 / 1000 / seconds)
                    rx_kbps = ((curr_rx - prev_rx) * 8) / (1000 * time_diff)
                    tx_kbps = ((curr_tx - prev_tx) * 8) / (1000 * time_diff)

                    rates[if_idx] = {
                        'rx_kbps': round(rx_kbps, 2),
                        'tx_kbps': round(tx_kbps, 2)
                    }

    # Store current counters for next calculation
    _port_counters_cache[cache_key] = current_counters
    _port_counters_cache[cache_key]['timestamp'] = current_counters.get(1, {}).get('timestamp', 0)

    return rates


def poll_port_status_snmp(ip: str, community: str = 'public') -> dict:
    """Poll port status from OLT via SNMP.
    Returns dict with interface index -> {'status': 'up'/'down', 'descr': '...', 'name': '...'}

    V1600D8 interface mapping (from SNMP):
    - ifIndex 1-16: GE uplink ports (GE0/1 to GE0/16)
    - ifIndex 17-24: PON ports (EPON0/1 to EPON0/8)
    - ifIndex 25: Management interface
    - ifIndex 26+: ONU virtual interfaces
    """
    import subprocess

    port_info = {}

    try:
        # Get interface names (ifName - e.g., "GE0/7 MIKRO")
        result = subprocess.run(
            ['snmpwalk', '-v2c', '-c', community, '-Oqv', ip, '1.3.6.1.2.1.31.1.1.1.1'],
            capture_output=True, text=True, timeout=10
        )
        names = result.stdout.strip().split('\n') if result.stdout else []

        # Get interface operational status (1=up, 2=down)
        result = subprocess.run(
            ['snmpwalk', '-v2c', '-c', community, '-Oqv', ip, '1.3.6.1.2.1.2.2.1.8'],
            capture_output=True, text=True, timeout=10
        )
        statuses = result.stdout.strip().split('\n') if result.stdout else []

        # Parse results - ifIndex starts at 1
        for i, (name, status) in enumerate(zip(names, statuses), start=1):
            name = name.strip().strip('"')
            status_val = status.strip()

            # Parse interface name - format is "GE0/7 MIKRO" or "GE0/1 "
            parts = name.split(' ', 1)
            if_name = parts[0] if parts else f"IF{i}"
            descr = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

            port_info[i] = {
                'status': 'up' if status_val == '1' else 'down',
                'name': if_name,
                'descr': descr
            }
    except Exception as e:
        logger.warning(f"Failed to poll port status from {ip}: {e}")

    return port_info


@app.get("/api/olts/{olt_id}/ports")
def get_olt_ports(olt_id: int, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """
    Get all ports for an OLT with their status.
    Returns PON ports with ONU counts and SFP uplink ports.
    """
    from models import OLTPort

    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    # Poll live port status from OLT via SNMP
    snmp_ports = poll_port_status_snmp(olt.ip_address)

    # Get PON port count based on model
    pon_count = get_pon_port_count(olt.model)

    # Get existing port data from database
    port_data = db.query(OLTPort).filter(OLTPort.olt_id == olt_id).all()
    port_map = {(p.port_type, p.port_number): p for p in port_data}

    # Get ONU counts per PON port from actual ONUs
    onu_counts = {}
    onus = db.query(ONU).filter(ONU.olt_id == olt_id).all()
    for onu in onus:
        if onu.pon_port not in onu_counts:
            onu_counts[onu.pon_port] = {'total': 0, 'online': 0}
        onu_counts[onu.pon_port]['total'] += 1
        if onu.is_online:
            onu_counts[onu.pon_port]['online'] += 1

    # Build PON ports list
    pon_ports = []
    for i in range(1, pon_count + 1):
        port = port_map.get(('pon', i))
        counts = onu_counts.get(i, {'total': 0, 'online': 0})

        # Determine status based on ONUs or port data
        if counts['online'] > 0:
            status = 'up'
        elif port and port.status:
            status = port.status
        else:
            status = 'unknown'

        pon_ports.append({
            "port_number": i,
            "status": status,
            "onu_count": counts['total'],
            "onu_online": counts['online'],
            "tx_power": port.tx_power if port else None,
            "rx_power": port.rx_power if port else None,
            "temperature": port.temperature if port else None  # PON transceiver temperature
        })

    # Determine uplink port configuration based on model
    # VSOL OLT PORT LAYOUTS - Verified from official product images (December 2025)
    # Port order is LEFT to RIGHT as seen from front panel
    model = olt.model or ''
    model_upper = model.upper()

    # Configuration: lists of tuples (if_index, label, speed)
    # ge_config = RJ45 ports, sfp_config = SFP 1G ports, xge_config = SFP+ 10G ports
    # qsfp_config = QSFP28 40G/100G ports (for V3600 series)

    # COMPLETE VSOL OLT MODEL LIST - Updated December 2025

    # ============ EPON OLT (1G) ============

    if 'D-MINI' in model_upper:
        # V1600D-MINI: 1 PON, L2, Compact
        # RJ45(GE1-4) only
        ge_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        sfp_config = []
        xge_config = []
        qsfp_config = []

    elif 'E02' in model_upper:
        # V1601E02-DP: 2 PON, L3, Dual power
        # SFP+(GE1-2), RJ45(GE3-6)
        sfp_config = []
        xge_config = [(1, 'GE1', '1G/10G'), (2, 'GE2', '1G/10G')]
        ge_config = [(i, f'GE{i}', '1G') for i in range(3, 7)]
        qsfp_config = []

    elif 'E04' in model_upper or 'E08' in model_upper:
        # V1601E04-DP/BT: 4 PON, L3, Redundant power
        # SFP+(GE1-4), RJ45(GE5-8)
        sfp_config = []
        xge_config = [(1, 'GE1', '10G'), (2, 'GE2', '10G'), (3, 'GE3', '10G'), (4, 'GE4', '10G')]
        ge_config = [(5, 'GE5', '1G'), (6, 'GE6', '1G'), (7, 'GE7', '1G'), (8, 'GE8', '1G')]
        qsfp_config = []

    elif 'D4-L' in model_upper:
        # V1600D4-L: 4 PON, L2, Efficient switching
        # SFP(GE1-2), RJ45(GE3-6)
        sfp_config = [(1, 'GE1', '1G'), (2, 'GE2', '1G')]
        xge_config = []
        ge_config = [(i, f'GE{i}', '1G') for i in range(3, 7)]
        qsfp_config = []

    elif 'D4' in model_upper:
        # V1600D4: 4 PON, L3
        # SFP(GE1-2), SFP+(GE3-4), RJ45(GE5-8)
        sfp_config = [(1, 'GE1', '1G'), (2, 'GE2', '1G')]
        xge_config = [(3, 'GE3', '10G'), (4, 'GE4', '10G')]
        ge_config = [(i, f'GE{i}', '1G') for i in range(5, 9)]
        qsfp_config = []

    elif 'D8' in model_upper and 'D16' not in model_upper:
        # V1600D8: 8 PON, L3, Hot-swap support
        # SFP(GE1-4), SFP+(GE5-8), RJ45(GE9-16)
        sfp_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        xge_config = [(i, f'GE{i}', '10G') for i in range(5, 9)]
        ge_config = [(i, f'GE{i}', '1G') for i in range(9, 17)]
        qsfp_config = []

    elif 'D16' in model_upper:
        # V1600D16: 16 PON, L3, Triple-play
        # SFP(GE1-4), SFP+(GE5-8), RJ45(GE9-12)
        sfp_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        xge_config = [(i, f'GE{i}', '10G') for i in range(5, 9)]
        ge_config = [(i, f'GE{i}', '1G') for i in range(9, 13)]
        qsfp_config = []

    # ============ GPON OLT (2.5G) ============

    elif 'GS-F' in model_upper or 'GS-ZF' in model_upper or 'GS-O32' in model_upper or 'GS' in model_upper:
        # V1600GS-F/ZF/O32: 1 PON, L2
        # -F: Optional fan, -ZF: Fanless, -O32: Built-in 1:32 splitter
        # RJ45(GE1-2), SFP+(10GE1)
        ge_config = [(1, 'GE1', '1G'), (2, 'GE2', '1G')]
        sfp_config = []
        xge_config = [(3, '10GE1', '10G')]
        qsfp_config = []

    elif 'GT' in model_upper:
        # V1600GT: 2 PON, L3, Simplified design
        # RJ45(GE1-2), SFP+(10GE1)
        ge_config = [(1, 'GE1', '1G'), (2, 'GE2', '1G')]
        sfp_config = []
        xge_config = [(3, '10GE1', '10G')]
        qsfp_config = []

    elif 'G0-B' in model_upper or 'G0' in model_upper:
        # V1600G0-B / V1600G0: 4 PON, L3, Cloud EMS
        # SFP+(GE1-2), RJ45(GE3-4)
        sfp_config = []
        xge_config = [(1, 'GE1', '10G'), (2, 'GE2', '10G')]
        ge_config = [(3, 'GE3', '1G'), (4, 'GE4', '1G')]
        qsfp_config = []

    elif 'G1WEO-B' in model_upper:
        # V1600G1WEO-B: 8 PON, L3, Outdoor + backup
        # SFP(GE1-4), SFP+(GE5-8), RJ45(GE9-12)
        sfp_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        xge_config = [(i, f'GE{i}', '10G') for i in range(5, 9)]
        ge_config = [(i, f'GE{i}', '1G') for i in range(9, 13)]
        qsfp_config = []

    elif 'G1WEO' in model_upper:
        # V1600G1WEO: 8 PON, L3, Outdoor version
        # SFP(GE1-4), SFP+(GE5-8), RJ45(GE9-12)
        sfp_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        xge_config = [(i, f'GE{i}', '10G') for i in range(5, 9)]
        ge_config = [(i, f'GE{i}', '1G') for i in range(9, 13)]
        qsfp_config = []

    elif 'G1-B' in model_upper or 'G1-R' in model_upper:
        # V1600G1-B/R: 8 PON, L3, Cloud EMS / Compact design
        # SFP(GE1-4), SFP+(GE5-8), RJ45(GE9-12)
        sfp_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        xge_config = [(i, f'GE{i}', '10G') for i in range(5, 9)]
        ge_config = [(i, f'GE{i}', '1G') for i in range(9, 13)]
        qsfp_config = []

    elif 'G1' in model_upper and 'G1WEO' not in model_upper:
        # V1600G1: 8 PON, L3, Standard
        # SFP(GE1-4), SFP+(GE5-8), RJ45(GE9-12)
        sfp_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        xge_config = [(i, f'GE{i}', '10G') for i in range(5, 9)]
        ge_config = [(i, f'GE{i}', '1G') for i in range(9, 13)]
        qsfp_config = []

    elif 'G2-B' in model_upper or 'G2-R' in model_upper:
        # V1600G2-B/R: 16 PON, L3, Cloud EMS / Compact design
        # RJ45(GE1-4), SFP+(GE5-6)
        ge_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        sfp_config = []
        xge_config = [(5, 'GE5', '10G'), (6, 'GE6', '10G')]
        qsfp_config = []

    elif 'G2' in model_upper:
        # V1600G2: 16 PON, L3, Standard
        # SFP(GE1-4), SFP+(GE5-8), RJ45(GE9-12)
        sfp_config = [(i, f'GE{i}', '1G') for i in range(1, 5)]
        xge_config = [(i, f'GE{i}', '10G') for i in range(5, 9)]
        ge_config = [(i, f'GE{i}', '1G') for i in range(9, 13)]
        qsfp_config = []

    # ============ XGS-PON / XG-PON OLT (10G) ============

    elif 'XG02-W' in model_upper:
        # V1600XG02-W: 2 PON, L3, WDM1r support
        # SFP+(GE1-2), RJ45(GE3-6)
        sfp_config = []
        xge_config = [(1, 'GE1', '1G/10G'), (2, 'GE2', '1G/10G')]
        ge_config = [(i, f'GE{i}', '1G') for i in range(3, 7)]
        qsfp_config = []

    elif 'XG02' in model_upper or 'V1600XG' in model_upper:
        # V1600XG02: 2 PON, L3, XG/XGS-PON
        # SFP+(GE1-2), RJ45(GE3-6)
        sfp_config = []
        xge_config = [(1, 'GE1', '1G/10G'), (2, 'GE2', '1G/10G')]
        ge_config = [(i, f'GE{i}', '1G') for i in range(3, 7)]
        qsfp_config = []

    # ============ 10G-EPON OLT ============

    elif 'V3600D8' in model_upper:
        # V3600D8: 8 PON, L3, 100G QSFP28 uplink
        # SFP(GE1-4), SFP+(GE5-6), QSFP28(1-2), RJ45(GE7-8)
        sfp_config = [(i, f'GE{i}', '1G/10G') for i in range(1, 5)]
        xge_config = [(5, 'GE5', '10G/25G'), (6, 'GE6', '10G/25G')]
        qsfp_config = [(7, 'QSFP1', '40G/100G'), (8, 'QSFP2', '40G/100G')]
        ge_config = [(9, 'GE7', '1G'), (10, 'GE8', '1G')]

    # ============ XGS-PON/GPON Combo OLT ============

    elif 'V3600G1' in model_upper:
        # V3600G1-C: 8 PON, L3, Combo PON, 100G uplink
        # SFP(GE1-4), SFP+(GE5-6), QSFP28(1-2), RJ45(GE7)
        sfp_config = [(i, f'GE{i}', '1G/10G') for i in range(1, 5)]
        xge_config = [(5, 'GE5', '1G/10G'), (6, 'GE6', '1G/10G')]
        qsfp_config = [(7, 'QSFP1', '40G/100G'), (8, 'QSFP2', '40G/100G')]
        ge_config = [(9, 'GE7', '1G')]

    # ============ Chassis OLT (Modular) ============

    elif 'V5600X26' in model_upper:
        # V5600X26: 32 slots, Max 1700 PON, 700 Gbps backplane
        # Modular - ports depend on line cards installed
        sfp_config = [(i, f'GE{i}', '1G/10G') for i in range(1, 5)]
        xge_config = [(i, f'XGE{i}', '10G/25G') for i in range(5, 9)]
        qsfp_config = [(i, f'QSFP{i-8}', '40G/100G') for i in range(9, 13)]
        ge_config = [(i, f'MGMT{i-12}', '1G') for i in range(13, 15)]

    elif 'V5600X71' in model_upper:
        # V5600X71: 32 slots, Max 2083 PON, 920 Gbps backplane
        # Modular - ports depend on line cards installed
        sfp_config = [(i, f'GE{i}', '1G/10G') for i in range(1, 5)]
        xge_config = [(i, f'XGE{i}', '10G/25G') for i in range(5, 9)]
        qsfp_config = [(i, f'QSFP{i-8}', '40G/100G') for i in range(9, 13)]
        ge_config = [(i, f'MGMT{i-12}', '1G') for i in range(13, 15)]

    # Default fallback
    else:
        ge_config = [(1, 'GE1', '1G'), (2, 'GE2', '1G')]
        sfp_config = [(3, 'SFP1', '1G'), (4, 'SFP2', '1G')]
        xge_config = []
        qsfp_config = []

    # Build GE RJ45 ports with live SNMP status
    ge_ports = []
    for if_idx, default_label, default_speed in ge_config:
        port = port_map.get(('ge', if_idx))
        snmp_info = snmp_ports.get(if_idx, {})
        descr = snmp_info.get('descr')
        snmp_status = snmp_info.get('status', 'down')
        # Port is UP if: SNMP says UP OR has a custom description
        if snmp_status == 'up' or (descr and descr.strip()):
            status = 'up'
        else:
            status = 'down'
        ge_ports.append({
            "port_number": if_idx,
            "type": "ge",
            "status": status,
            "speed": port.speed if port else default_speed,
            "label": descr if descr else default_label
        })

    # Build SFP ports with live SNMP status
    sfp_ports = []
    for if_idx, default_label, default_speed in sfp_config:
        port = port_map.get(('sfp', if_idx))
        snmp_info = snmp_ports.get(if_idx, {})
        descr = snmp_info.get('descr')
        snmp_status = snmp_info.get('status', 'down')
        # Port is UP if: SNMP says UP OR has a custom description
        if snmp_status == 'up' or (descr and descr.strip()):
            status = 'up'
        else:
            status = 'down'
        sfp_ports.append({
            "port_number": if_idx,
            "type": "sfp",
            "status": status,
            "speed": port.speed if port else default_speed,
            "label": descr if descr else default_label
        })

    # Build 10G SFP+ ports with live SNMP status
    xge_ports = []
    for if_idx, default_label, default_speed in xge_config:
        port = port_map.get(('xge', if_idx))
        snmp_info = snmp_ports.get(if_idx, {})
        descr = snmp_info.get('descr')
        snmp_status = snmp_info.get('status', 'down')
        # Port is UP if: SNMP says UP OR has a custom description
        if snmp_status == 'up' or (descr and descr.strip()):
            status = 'up'
        else:
            status = 'down'
        xge_ports.append({
            "port_number": if_idx,
            "type": "xge",
            "status": status,
            "speed": port.speed if port else default_speed,
            "label": descr if descr else default_label
        })

    # Build QSFP28 40G/100G ports with live SNMP status (for V3600 series)
    qsfp_ports = []
    for if_idx, default_label, default_speed in qsfp_config:
        port = port_map.get(('qsfp', if_idx))
        snmp_info = snmp_ports.get(if_idx, {})
        descr = snmp_info.get('descr')
        snmp_status = snmp_info.get('status', 'down')
        if snmp_status == 'up' or (descr and descr.strip()):
            status = 'up'
        else:
            status = 'down'
        qsfp_ports.append({
            "port_number": if_idx,
            "type": "qsfp",
            "status": status,
            "speed": port.speed if port else default_speed,
            "label": descr if descr else default_label
        })

    return {
        "olt_id": olt_id,
        "olt_name": olt.name,
        "model": olt.model,
        "ip_address": olt.ip_address,
        "is_online": olt.is_online,
        "total_pon": pon_count,
        "pon_ports": pon_ports,
        "ge_ports": ge_ports,
        "sfp_ports": sfp_ports,
        "xge_ports": xge_ports,
        "qsfp_ports": qsfp_ports,  # QSFP28 40G/100G ports for V3600 series
        "total_onus": sum(c['total'] for c in onu_counts.values()),
        "online_onus": sum(c['online'] for c in onu_counts.values())
    }


def set_port_description_snmp(ip: str, if_index: int, description: str, community: str = 'private') -> bool:
    """Set interface description on OLT via SNMP.

    Uses OID 1.3.6.1.2.1.31.1.1.1.18 (ifAlias) for interface description.
    """
    import subprocess

    try:
        # ifAlias OID for setting interface description
        oid = f'1.3.6.1.2.1.31.1.1.1.18.{if_index}'

        result = subprocess.run(
            ['snmpset', '-v2c', '-c', community, ip, oid, 's', description],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            logger.info(f"Set interface {if_index} description to '{description}' on {ip}")
            return True
        else:
            logger.error(f"Failed to set interface description: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"SNMP set failed for {ip}: {e}")
        return False


@app.put("/api/olts/{olt_id}/ports/{port_number}/description")
async def set_port_description(
    olt_id: int,
    port_number: int,
    description: str = Query(..., description="New port description"),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Set port description on OLT via SNMP."""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    # Set description via SNMP (port_number is the interface index)
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(
        thread_executor,
        set_port_description_snmp,
        olt.ip_address,
        port_number,
        description,
        'private'  # Write community string
    )

    if success:
        return {"success": True, "message": f"Port {port_number} description set to '{description}'"}
    else:
        raise HTTPException(status_code=500, detail="Failed to set port description via SNMP")


@app.get("/api/olts/{olt_id}/ports/{port_type}/{port_number}/traffic")
def get_port_traffic_history(
    olt_id: int,
    port_type: str,
    port_number: int,
    range: str = Query('1h', description="Time range: 5m, 15m, 30m, 1h, 6h, 24h, 1w, 1M"),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get traffic history for a specific port.
    Used for per-port traffic graphs.
    """
    from models import PortTraffic
    from datetime import timedelta

    # Time range mapping
    time_ranges = {
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '6h': timedelta(hours=6),
        '24h': timedelta(hours=24),
        '1w': timedelta(weeks=1),
        '1M': timedelta(days=30)
    }

    if range not in time_ranges:
        raise HTTPException(status_code=400, detail=f"Invalid range. Use: {', '.join(time_ranges.keys())}")

    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    time_delta = time_ranges[range]
    since = datetime.utcnow() - time_delta

    traffic = db.query(PortTraffic).filter(
        PortTraffic.olt_id == olt_id,
        PortTraffic.port_type == port_type,
        PortTraffic.port_number == port_number,
        PortTraffic.timestamp > since
    ).order_by(PortTraffic.timestamp).all()

    # If no per-port traffic data, fall back to aggregated PON traffic from TrafficHistory
    if not traffic and port_type == 'pon':
        # Get PON port traffic from TrafficHistory
        pon_traffic = db.query(TrafficHistory).filter(
            TrafficHistory.olt_id == olt_id,
            TrafficHistory.entity_type == 'pon',
            TrafficHistory.pon_port == port_number,
            TrafficHistory.timestamp > since
        ).order_by(TrafficHistory.timestamp).all()

        return {
            "olt_id": olt_id,
            "port_type": port_type,
            "port_number": port_number,
            "range": range,
            "data": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "rx_kbps": t.rx_kbps,
                    "tx_kbps": t.tx_kbps
                }
                for t in pon_traffic
            ]
        }

    return {
        "olt_id": olt_id,
        "port_type": port_type,
        "port_number": port_number,
        "range": range,
        "data": [
            {
                "timestamp": t.timestamp.isoformat(),
                "rx_kbps": t.rx_kbps,
                "tx_kbps": t.tx_kbps
            }
            for t in traffic
        ]
    }


# ============ Traffic Monitoring Endpoints ============

@app.get("/api/olts/{olt_id}/traffic")
async def get_olt_traffic(olt_id: int, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """
    Get live traffic data for all ONUs on an OLT.

    Returns current bandwidth in Kbps for each ONU.
    Polls SNMP counters and calculates rate based on previous snapshot.
    OLT updates counters approximately every 30 seconds.
    """
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        # Get current traffic counters from SNMP
        loop = asyncio.get_event_loop()
        current_counters = await loop.run_in_executor(
            thread_executor,
            get_traffic_counters_snmp,
            olt.ip_address,
            "public"
        )

        if not current_counters:
            return {"olt_id": olt_id, "traffic": [], "message": "No traffic data available"}

        current_time = datetime.utcnow()

        # Get previous snapshots for this OLT
        prev_snapshots = {
            s.mac_address: s
            for s in db.query(TrafficSnapshot).filter(TrafficSnapshot.olt_id == olt_id).all()
        }

        traffic_data = []

        for mac, counters in current_counters.items():
            rx_bytes = counters['rx_bytes']
            tx_bytes = counters['tx_bytes']
            pon_port = counters.get('pon_port', 0)
            onu_id = counters.get('onu_id', 0)

            # Calculate rate if we have previous data
            rx_kbps = 0
            tx_kbps = 0

            if mac in prev_snapshots:
                prev = prev_snapshots[mac]
                time_diff = (current_time - prev.timestamp).total_seconds()

                if time_diff > 0:
                    # Handle counter wrap (unlikely with 64-bit but safe)
                    rx_diff = rx_bytes - prev.rx_bytes
                    tx_diff = tx_bytes - prev.tx_bytes

                    if rx_diff < 0:
                        rx_diff = rx_bytes  # Counter wrapped
                    if tx_diff < 0:
                        tx_diff = tx_bytes  # Counter wrapped

                    # Calculate Kbps: (bytes * 8) / seconds / 1000
                    rx_kbps = round((rx_diff * 8) / time_diff / 1000, 2)
                    tx_kbps = round((tx_diff * 8) / time_diff / 1000, 2)

                    # Sanity check: cap at 1 Gbps (1,000,000 Kbps)
                    MAX_VALID_KBPS = 1000000
                    if rx_kbps > MAX_VALID_KBPS or tx_kbps > MAX_VALID_KBPS:
                        rx_kbps = 0
                        tx_kbps = 0

                # Update snapshot
                prev.rx_bytes = rx_bytes
                prev.tx_bytes = tx_bytes
                prev.timestamp = current_time
            else:
                # Create new snapshot
                snapshot = TrafficSnapshot(
                    olt_id=olt_id,
                    mac_address=mac,
                    rx_bytes=rx_bytes,
                    tx_bytes=tx_bytes,
                    timestamp=current_time
                )
                db.add(snapshot)

            # Get ONU description from database
            onu = db.query(ONU).filter(
                ONU.olt_id == olt_id,
                ONU.mac_address == mac
            ).first()

            traffic_data.append({
                "mac_address": mac,
                "pon_port": pon_port,
                "onu_id": onu_id,
                "onu_db_id": onu.id if onu else None,
                "description": onu.description if onu else None,
                "is_online": onu.is_online if onu else False,
                "rx_kbps": rx_kbps,
                "tx_kbps": tx_kbps,
                "rx_mbps": round(rx_kbps / 1000, 2),
                "tx_mbps": round(tx_kbps / 1000, 2)
            })

            # Store traffic history for ONU (only if we have actual traffic data)
            if rx_kbps > 0 or tx_kbps > 0 or (onu and onu.is_online):
                onu_history = TrafficHistory(
                    entity_type='onu',
                    entity_id=str(onu.id) if onu else f"{olt_id}:{mac}",
                    olt_id=olt_id,
                    pon_port=pon_port,
                    onu_db_id=onu.id if onu else None,
                    rx_kbps=rx_kbps,
                    tx_kbps=tx_kbps,
                    timestamp=current_time
                )
                db.add(onu_history)

        # Aggregate and store PON port traffic history
        pon_traffic = {}
        for t in traffic_data:
            pon = t['pon_port']
            if pon not in pon_traffic:
                pon_traffic[pon] = {'rx_kbps': 0, 'tx_kbps': 0}
            pon_traffic[pon]['rx_kbps'] += t['rx_kbps']
            pon_traffic[pon]['tx_kbps'] += t['tx_kbps']

        for pon, traffic in pon_traffic.items():
            pon_history = TrafficHistory(
                entity_type='pon',
                entity_id=f"{olt_id}:{pon}",
                olt_id=olt_id,
                pon_port=pon,
                onu_db_id=None,
                rx_kbps=traffic['rx_kbps'],
                tx_kbps=traffic['tx_kbps'],
                timestamp=current_time
            )
            db.add(pon_history)

        # Store OLT total traffic history
        total_rx = sum(t['rx_kbps'] for t in traffic_data)
        total_tx = sum(t['tx_kbps'] for t in traffic_data)
        olt_history = TrafficHistory(
            entity_type='olt',
            entity_id=str(olt_id),
            olt_id=olt_id,
            pon_port=None,
            onu_db_id=None,
            rx_kbps=total_rx,
            tx_kbps=total_tx,
            timestamp=current_time
        )
        db.add(olt_history)

        db.commit()

        # Sort by traffic (highest first)
        traffic_data.sort(key=lambda x: x['rx_kbps'] + x['tx_kbps'], reverse=True)

        return {
            "olt_id": olt_id,
            "olt_name": olt.name,
            "timestamp": current_time.isoformat(),
            "onu_count": len(traffic_data),
            "traffic": traffic_data
        }

    except Exception as e:
        logger.error(f"Traffic poll failed for OLT {olt_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Traffic poll failed: {str(e)}")


@app.get("/api/traffic/all")
async def get_all_traffic(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """
    Get live traffic for all ONUs across all OLTs the user can access.
    Returns aggregated bandwidth data.
    """
    allowed_olt_ids = get_user_allowed_olt_ids(user, db)

    # Build OLT query
    olt_query = db.query(OLT)
    if allowed_olt_ids is not None:
        olt_query = olt_query.filter(OLT.id.in_(allowed_olt_ids))

    olts = olt_query.filter(OLT.is_online == True).all()

    all_traffic = []
    current_time = datetime.utcnow()

    for olt in olts:
        try:
            # Get current traffic counters from SNMP
            loop = asyncio.get_event_loop()
            current_counters = await loop.run_in_executor(
                thread_executor,
                get_traffic_counters_snmp,
                olt.ip_address,
                "public"
            )

            if not current_counters:
                continue

            # Get previous snapshots for this OLT
            prev_snapshots = {
                s.mac_address: s
                for s in db.query(TrafficSnapshot).filter(TrafficSnapshot.olt_id == olt.id).all()
            }

            for mac, counters in current_counters.items():
                rx_bytes = counters['rx_bytes']
                tx_bytes = counters['tx_bytes']
                pon_port = counters.get('pon_port', 0)
                onu_id = counters.get('onu_id', 0)

                rx_kbps = 0
                tx_kbps = 0

                if mac in prev_snapshots:
                    prev = prev_snapshots[mac]
                    time_diff = (current_time - prev.timestamp).total_seconds()

                    if time_diff > 0:
                        rx_diff = rx_bytes - prev.rx_bytes
                        tx_diff = tx_bytes - prev.tx_bytes

                        if rx_diff < 0:
                            rx_diff = rx_bytes
                        if tx_diff < 0:
                            tx_diff = tx_bytes

                        rx_kbps = round((rx_diff * 8) / time_diff / 1000, 2)
                        tx_kbps = round((tx_diff * 8) / time_diff / 1000, 2)

                        # Sanity check: cap at 1 Gbps (1,000,000 Kbps)
                        MAX_VALID_KBPS = 1000000
                        if rx_kbps > MAX_VALID_KBPS or tx_kbps > MAX_VALID_KBPS:
                            rx_kbps = 0
                            tx_kbps = 0

                    prev.rx_bytes = rx_bytes
                    prev.tx_bytes = tx_bytes
                    prev.timestamp = current_time
                else:
                    snapshot = TrafficSnapshot(
                        olt_id=olt.id,
                        mac_address=mac,
                        rx_bytes=rx_bytes,
                        tx_bytes=tx_bytes,
                        timestamp=current_time
                    )
                    db.add(snapshot)

                onu = db.query(ONU).filter(
                    ONU.olt_id == olt.id,
                    ONU.mac_address == mac
                ).first()

                all_traffic.append({
                    "olt_id": olt.id,
                    "olt_name": olt.name,
                    "mac_address": mac,
                    "pon_port": pon_port,
                    "onu_id": onu_id,
                    "description": onu.description if onu else None,
                    "is_online": onu.is_online if onu else False,
                    "rx_kbps": rx_kbps,
                    "tx_kbps": tx_kbps,
                    "rx_mbps": round(rx_kbps / 1000, 2),
                    "tx_mbps": round(tx_kbps / 1000, 2)
                })

        except Exception as e:
            logger.warning(f"Traffic poll failed for OLT {olt.name}: {e}")
            continue

    db.commit()

    # Sort by traffic (highest first)
    all_traffic.sort(key=lambda x: x['rx_kbps'] + x['tx_kbps'], reverse=True)

    return {
        "timestamp": current_time.isoformat(),
        "onu_count": len(all_traffic),
        "traffic": all_traffic
    }


# ============ WebSocket Live Traffic ============

async def traffic_polling_loop(olt_id: int, olt_ip: str, db_session_factory):
    """Background loop to poll traffic and broadcast to WebSocket clients"""
    logger.info(f"Started traffic polling loop for OLT {olt_id}")

    # Send immediate "loading" message so client knows we're connected and working
    await traffic_manager.broadcast(olt_id, {
        "olt_id": olt_id,
        "timestamp": datetime.now().isoformat(),
        "traffic": [],
        "message": "Polling SNMP..."
    })

    while olt_id in traffic_manager.active_connections and traffic_manager.active_connections[olt_id]:
        try:
            db = db_session_factory()
            try:
                # Get current traffic counters from SNMP
                loop = asyncio.get_event_loop()
                current_counters = await loop.run_in_executor(
                    thread_executor,
                    get_traffic_counters_snmp,
                    olt_ip,
                    "public"
                )

                if not current_counters:
                    await traffic_manager.broadcast(olt_id, {
                        "olt_id": olt_id,
                        "timestamp": datetime.now().isoformat(),
                        "traffic": [],
                        "message": "No traffic data"
                    })
                    await asyncio.sleep(3)
                    continue

                current_time = datetime.now()

                # Get previous snapshots for this OLT
                prev_snapshots = {
                    s.mac_address: s
                    for s in db.query(TrafficSnapshot).filter(TrafficSnapshot.olt_id == olt_id).all()
                }

                # Get OLT name
                olt = db.query(OLT).filter(OLT.id == olt_id).first()
                olt_name = olt.name if olt else f"OLT-{olt_id}"

                traffic_data = []

                # Smoothing factor: 0.3 = 30% new value, 70% old value (smoother)
                SMOOTHING = 0.3

                for mac, counters in current_counters.items():
                    rx_bytes = counters['rx_bytes']
                    tx_bytes = counters['tx_bytes']
                    pon_port = counters.get('pon_port', 0)
                    onu_id = counters.get('onu_id', 0)

                    rx_kbps = 0
                    tx_kbps = 0

                    if mac in prev_snapshots:
                        prev = prev_snapshots[mac]
                        time_diff = (current_time - prev.timestamp).total_seconds()

                        # Get previous smoothed values
                        prev_rx = getattr(prev, 'last_rx_kbps', 0) or 0
                        prev_tx = getattr(prev, 'last_tx_kbps', 0) or 0

                        if time_diff > 0 and time_diff < 60:  # Only calc rate if reasonable time diff
                            rx_diff = rx_bytes - prev.rx_bytes
                            tx_diff = tx_bytes - prev.tx_bytes

                            # Handle counter wraparound
                            if rx_diff < 0:
                                rx_diff = rx_bytes
                            if tx_diff < 0:
                                tx_diff = tx_bytes

                            # Calculate instant rate
                            instant_rx = (rx_diff * 8) / time_diff / 1000
                            instant_tx = (tx_diff * 8) / time_diff / 1000

                            # Sanity check: cap at 1 Gbps (1,000,000 Kbps)
                            MAX_VALID_KBPS = 1000000
                            if instant_rx > MAX_VALID_KBPS or instant_tx > MAX_VALID_KBPS:
                                instant_rx = 0
                                instant_tx = 0

                            # Apply exponential moving average for smooth transition
                            # New value = SMOOTHING * instant + (1 - SMOOTHING) * previous
                            rx_kbps = round(SMOOTHING * instant_rx + (1 - SMOOTHING) * prev_rx, 2)
                            tx_kbps = round(SMOOTHING * instant_tx + (1 - SMOOTHING) * prev_tx, 2)

                            # Store smoothed rates
                            prev.last_rx_kbps = rx_kbps
                            prev.last_tx_kbps = tx_kbps
                        else:
                            # Keep previous rates with slow decay (reduce by 10% each cycle)
                            rx_kbps = round(prev_rx * 0.9, 2)
                            tx_kbps = round(prev_tx * 0.9, 2)
                            prev.last_rx_kbps = rx_kbps
                            prev.last_tx_kbps = tx_kbps

                        prev.rx_bytes = rx_bytes
                        prev.tx_bytes = tx_bytes
                        prev.timestamp = current_time
                    else:
                        snapshot = TrafficSnapshot(
                            olt_id=olt_id,
                            mac_address=mac,
                            rx_bytes=rx_bytes,
                            tx_bytes=tx_bytes,
                            timestamp=current_time,
                            last_rx_kbps=0,
                            last_tx_kbps=0
                        )
                        db.add(snapshot)

                    # Get ONU description from database
                    onu = db.query(ONU).filter(
                        ONU.olt_id == olt_id,
                        ONU.mac_address == mac
                    ).first()

                    traffic_data.append({
                        "mac_address": mac,
                        "pon_port": pon_port,
                        "onu_id": onu_id,
                        "description": onu.description if onu else None,
                        "is_online": onu.is_online if onu else False,
                        "rx_kbps": rx_kbps,
                        "tx_kbps": tx_kbps,
                        "rx_mbps": round(rx_kbps / 1000, 2),
                        "tx_mbps": round(tx_kbps / 1000, 2)
                    })

                db.commit()

                # Sort by traffic (highest first)
                traffic_data.sort(key=lambda x: x['rx_kbps'] + x['tx_kbps'], reverse=True)

                # Broadcast to all connected clients
                await traffic_manager.broadcast(olt_id, {
                    "olt_id": olt_id,
                    "olt_name": olt_name,
                    "timestamp": current_time.isoformat(),
                    "onu_count": len(traffic_data),
                    "traffic": traffic_data
                })

            finally:
                db.close()

            # Wait 3 seconds before next poll
            await asyncio.sleep(3)

        except asyncio.CancelledError:
            logger.info(f"Traffic polling loop cancelled for OLT {olt_id}")
            break
        except Exception as e:
            logger.error(f"Traffic polling error for OLT {olt_id}: {e}")
            await asyncio.sleep(5)  # Wait longer on error

    logger.info(f"Stopped traffic polling loop for OLT {olt_id}")


@app.websocket("/ws/traffic/{olt_id}")
async def websocket_traffic(websocket: WebSocket, olt_id: int):
    """
    WebSocket endpoint for live traffic updates.
    Connects to an OLT and streams traffic data every 3 seconds.
    """
    from models import SessionLocal

    # Verify OLT exists
    db = SessionLocal()
    try:
        olt = db.query(OLT).filter(OLT.id == olt_id).first()
        if not olt:
            await websocket.close(code=4004, reason="OLT not found")
            return
        olt_ip = olt.ip_address
    finally:
        db.close()

    await traffic_manager.connect(websocket, olt_id)

    try:
        # Start traffic polling task if not already running
        if olt_id not in traffic_manager.traffic_tasks or traffic_manager.traffic_tasks[olt_id].done():
            traffic_manager.traffic_tasks[olt_id] = asyncio.create_task(
                traffic_polling_loop(olt_id, olt_ip, SessionLocal)
            )

        # Keep connection alive and wait for client messages
        while True:
            try:
                # Wait for any message from client (ping/pong or disconnect)
                data = await websocket.receive_text()
                # Client can send "ping" to keep alive
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error for OLT {olt_id}: {e}")
    finally:
        traffic_manager.disconnect(websocket, olt_id)


# ============ Traffic History/Graph Endpoints ============

TIME_RANGES = {
    '5m': timedelta(minutes=5),
    '15m': timedelta(minutes=15),
    '30m': timedelta(minutes=30),
    '1h': timedelta(hours=1),
    '6h': timedelta(hours=6),
    '24h': timedelta(hours=24),
    '1w': timedelta(weeks=1),
    '1M': timedelta(days=30)
}


@app.get("/api/traffic/history/onu/{onu_id}")
async def get_onu_traffic_history(
    onu_id: int,
    range: str = Query('1h', description="Time range: 5m, 15m, 30m, 1h, 6h, 24h, 1w, 1M"),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get historical traffic data for a specific ONU.
    Returns time-series data for graphing.
    """
    if range not in TIME_RANGES:
        raise HTTPException(status_code=400, detail=f"Invalid range. Use: {', '.join(TIME_RANGES.keys())}")

    onu = db.query(ONU).filter(ONU.id == onu_id).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    # Check user access to this ONU's OLT
    allowed_olt_ids = get_user_allowed_olt_ids(user, db)
    if allowed_olt_ids is not None and onu.olt_id not in allowed_olt_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    time_delta = TIME_RANGES[range]
    start_time = datetime.utcnow() - time_delta

    history = db.query(TrafficHistory).filter(
        TrafficHistory.entity_type == 'onu',
        TrafficHistory.onu_db_id == onu_id,
        TrafficHistory.timestamp >= start_time
    ).order_by(TrafficHistory.timestamp.asc()).all()

    return {
        "onu_id": onu_id,
        "onu_description": onu.description,
        "olt_id": onu.olt_id,
        "pon_port": onu.pon_port,
        "range": range,
        "start_time": start_time.isoformat(),
        "end_time": datetime.utcnow().isoformat(),
        "data_points": len(history),
        "data": [
            {
                "timestamp": h.timestamp.isoformat(),
                "rx_kbps": h.rx_kbps,
                "tx_kbps": h.tx_kbps,
                "rx_mbps": round(h.rx_kbps / 1000, 2),
                "tx_mbps": round(h.tx_kbps / 1000, 2)
            }
            for h in history
        ]
    }


@app.get("/api/traffic/history/pon/{olt_id}/{pon_port}")
async def get_pon_traffic_history(
    olt_id: int,
    pon_port: int,
    range: str = Query('1h', description="Time range: 5m, 15m, 30m, 1h, 6h, 24h, 1w, 1M"),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get historical traffic data for a specific PON port on an OLT.
    Returns aggregated time-series data for graphing.
    """
    if range not in TIME_RANGES:
        raise HTTPException(status_code=400, detail=f"Invalid range. Use: {', '.join(TIME_RANGES.keys())}")

    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    # Check user access
    allowed_olt_ids = get_user_allowed_olt_ids(user, db)
    if allowed_olt_ids is not None and olt_id not in allowed_olt_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    time_delta = TIME_RANGES[range]
    start_time = datetime.utcnow() - time_delta
    entity_id = f"{olt_id}:{pon_port}"

    history = db.query(TrafficHistory).filter(
        TrafficHistory.entity_type == 'pon',
        TrafficHistory.entity_id == entity_id,
        TrafficHistory.timestamp >= start_time
    ).order_by(TrafficHistory.timestamp.asc()).all()

    return {
        "olt_id": olt_id,
        "olt_name": olt.name,
        "pon_port": pon_port,
        "range": range,
        "start_time": start_time.isoformat(),
        "end_time": datetime.utcnow().isoformat(),
        "data_points": len(history),
        "data": [
            {
                "timestamp": h.timestamp.isoformat(),
                "rx_kbps": h.rx_kbps,
                "tx_kbps": h.tx_kbps,
                "rx_mbps": round(h.rx_kbps / 1000, 2),
                "tx_mbps": round(h.tx_kbps / 1000, 2)
            }
            for h in history
        ]
    }


@app.get("/api/traffic/history/olt/{olt_id}")
async def get_olt_traffic_history(
    olt_id: int,
    range: str = Query('1h', description="Time range: 5m, 15m, 30m, 1h, 6h, 24h, 1w, 1M"),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get historical traffic data for a specific OLT (total traffic).
    Returns aggregated time-series data for graphing.
    """
    if range not in TIME_RANGES:
        raise HTTPException(status_code=400, detail=f"Invalid range. Use: {', '.join(TIME_RANGES.keys())}")

    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    # Check user access
    allowed_olt_ids = get_user_allowed_olt_ids(user, db)
    if allowed_olt_ids is not None and olt_id not in allowed_olt_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    time_delta = TIME_RANGES[range]
    start_time = datetime.utcnow() - time_delta

    history = db.query(TrafficHistory).filter(
        TrafficHistory.entity_type == 'olt',
        TrafficHistory.olt_id == olt_id,
        TrafficHistory.timestamp >= start_time
    ).order_by(TrafficHistory.timestamp.asc()).all()

    return {
        "olt_id": olt_id,
        "olt_name": olt.name,
        "range": range,
        "start_time": start_time.isoformat(),
        "end_time": datetime.utcnow().isoformat(),
        "data_points": len(history),
        "data": [
            {
                "timestamp": h.timestamp.isoformat(),
                "rx_kbps": h.rx_kbps,
                "tx_kbps": h.tx_kbps,
                "rx_mbps": round(h.rx_kbps / 1000, 2),
                "tx_mbps": round(h.tx_kbps / 1000, 2)
            }
            for h in history
        ]
    }


@app.delete("/api/traffic/history/cleanup")
async def cleanup_traffic_history(
    days: int = Query(30, description="Delete history older than X days"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Clean up old traffic history data.
    Admin only. Deletes records older than specified days.
    """
    cutoff_time = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(TrafficHistory).filter(
        TrafficHistory.timestamp < cutoff_time
    ).delete()

    db.commit()

    return {
        "message": f"Deleted {deleted} records older than {days} days",
        "cutoff_time": cutoff_time.isoformat()
    }


# ============ Diagram Endpoints ============

@app.get("/api/diagrams", response_model=DiagramListResponse)
async def list_diagrams(
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    List all diagrams accessible by the current user.
    Returns user's own diagrams plus shared diagrams.
    """
    # Get user's own diagrams and shared diagrams
    diagrams = db.query(Diagram).filter(
        or_(
            Diagram.owner_id == user.id,
            Diagram.is_shared == True
        )
    ).order_by(Diagram.updated_at.desc()).all()

    result = []
    for d in diagrams:
        owner = db.query(User).filter(User.id == d.owner_id).first()
        result.append(DiagramResponse(
            id=d.id,
            owner_id=d.owner_id,
            owner_name=owner.username if owner else None,
            name=d.name,
            nodes=d.nodes,
            connections=d.connections,
            settings=d.settings,
            is_shared=d.is_shared,
            created_at=d.created_at,
            updated_at=d.updated_at
        ))

    return DiagramListResponse(diagrams=result, total=len(result))


@app.post("/api/diagrams", response_model=DiagramResponse)
async def create_diagram(
    diagram: DiagramCreate,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Create a new diagram"""
    db_diagram = Diagram(
        owner_id=user.id,
        name=diagram.name,
        nodes=diagram.nodes,
        connections=diagram.connections,
        settings=diagram.settings,
        is_shared=diagram.is_shared
    )
    db.add(db_diagram)
    db.commit()
    db.refresh(db_diagram)

    return DiagramResponse(
        id=db_diagram.id,
        owner_id=db_diagram.owner_id,
        owner_name=user.username,
        name=db_diagram.name,
        nodes=db_diagram.nodes,
        connections=db_diagram.connections,
        settings=db_diagram.settings,
        is_shared=db_diagram.is_shared,
        created_at=db_diagram.created_at,
        updated_at=db_diagram.updated_at
    )


@app.get("/api/diagrams/{diagram_id}", response_model=DiagramResponse)
async def get_diagram(
    diagram_id: int,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Get a specific diagram by ID"""
    diagram = db.query(Diagram).filter(Diagram.id == diagram_id).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")

    # Check access: owner or shared
    if diagram.owner_id != user.id and not diagram.is_shared:
        raise HTTPException(status_code=403, detail="Access denied")

    owner = db.query(User).filter(User.id == diagram.owner_id).first()

    return DiagramResponse(
        id=diagram.id,
        owner_id=diagram.owner_id,
        owner_name=owner.username if owner else None,
        name=diagram.name,
        nodes=diagram.nodes,
        connections=diagram.connections,
        settings=diagram.settings,
        is_shared=diagram.is_shared,
        created_at=diagram.created_at,
        updated_at=diagram.updated_at
    )


@app.put("/api/diagrams/{diagram_id}", response_model=DiagramResponse)
async def update_diagram(
    diagram_id: int,
    update: DiagramUpdate,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Update a diagram (owner only)"""
    diagram = db.query(Diagram).filter(Diagram.id == diagram_id).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")

    # Only owner can update
    if diagram.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can update this diagram")

    # Update fields if provided
    if update.name is not None:
        diagram.name = update.name
    if update.nodes is not None:
        diagram.nodes = update.nodes
    if update.connections is not None:
        diagram.connections = update.connections
    if update.settings is not None:
        diagram.settings = update.settings
    if update.is_shared is not None:
        diagram.is_shared = update.is_shared

    diagram.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(diagram)

    owner = db.query(User).filter(User.id == diagram.owner_id).first()

    return DiagramResponse(
        id=diagram.id,
        owner_id=diagram.owner_id,
        owner_name=owner.username if owner else None,
        name=diagram.name,
        nodes=diagram.nodes,
        connections=diagram.connections,
        settings=diagram.settings,
        is_shared=diagram.is_shared,
        created_at=diagram.created_at,
        updated_at=diagram.updated_at
    )


@app.delete("/api/diagrams/{diagram_id}")
async def delete_diagram(
    diagram_id: int,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Delete a diagram (owner only)"""
    diagram = db.query(Diagram).filter(Diagram.id == diagram_id).first()
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")

    # Only owner can delete
    if diagram.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this diagram")

    db.delete(diagram)
    db.commit()

    return {"message": "Diagram deleted successfully"}


# ============ License Info ============

@app.get("/api/license")
async def get_license_info(user: User = Depends(require_auth)):
    """Get current license information"""
    from license_manager import license_manager
    info = license_manager.get_license_info()

    # Add license key from file
    license_key = None
    try:
        license_file = Path('/etc/olt-manager/license.key')
        if license_file.exists():
            license_key = license_file.read_text().strip()
    except:
        pass
    info['license_key'] = license_key or os.getenv('OLT_LICENSE_KEY', 'N/A')

    # Calculate days remaining
    expires_at = info.get('expires_at')
    if expires_at:
        try:
            exp_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if exp_date.tzinfo:
                exp_date = exp_date.replace(tzinfo=None)
            days_remaining = (exp_date - datetime.now()).days
            info['days_remaining'] = max(0, days_remaining)
        except:
            info['days_remaining'] = None
    else:
        info['days_remaining'] = None

    # Add status for frontend
    if not info.get('valid'):
        error_msg = info.get('error_message', '').lower()
        if 'suspended' in error_msg:
            info['status'] = 'suspended'
            info['status_message'] = 'License has been suspended. Please contact support.'
        elif 'expired' in error_msg:
            info['status'] = 'expired'
            info['status_message'] = 'License has expired. Please renew your subscription.'
        elif 'revoked' in error_msg:
            info['status'] = 'revoked'
            info['status_message'] = 'License has been revoked. Please contact support.'
        else:
            info['status'] = 'invalid'
            info['status_message'] = info.get('error_message', 'License is invalid')
    else:
        info['status'] = 'active'
        info['status_message'] = None

    # Add current usage counts
    db = next(get_db())
    try:
        info['current_olts'] = db.query(OLT).count()
        info['current_onus'] = db.query(ONU).count()
        info['current_users'] = db.query(User).count()
    except:
        info['current_olts'] = 0
        info['current_onus'] = 0
        info['current_users'] = 0
    finally:
        db.close()

    return info


@app.post("/api/license/refresh")
async def refresh_license(user: User = Depends(require_auth)):
    """Force refresh license from server"""
    from license_manager import license_manager
    try:
        # Force revalidation from server
        license_manager.validate()
        return {"success": True, "message": "License refreshed successfully"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/system/restart-service")
async def restart_service(user: User = Depends(require_auth)):
    """Restart the OLT Manager service"""
    import subprocess
    try:
        # Try different service names
        service_names = ['olt-backend', 'olt-manager', 'oltmanager']
        for name in service_names:
            result = subprocess.run(['systemctl', 'is-active', name], capture_output=True)
            if result.returncode == 0:
                subprocess.Popen(['systemctl', 'restart', name])
                return {"success": True, "message": f"Service {name} is restarting..."}

        # If no systemd service, try to restart the process
        subprocess.Popen(['pkill', '-f', 'uvicorn|main.bin|main.py'])
        return {"success": True, "message": "Service is restarting..."}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/system/reboot")
async def reboot_server(user: User = Depends(require_auth)):
    """Reboot the server"""
    import subprocess
    try:
        # Schedule reboot in 3 seconds to allow response to be sent
        subprocess.Popen(['shutdown', '-r', '+0'])
        return {"success": True, "message": "Server is rebooting..."}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ============ Remote Access Tunnel API ============

try:
    from tunnel_manager import tunnel_manager
    TUNNEL_AVAILABLE = True
except ImportError:
    TUNNEL_AVAILABLE = False
    tunnel_manager = None


@app.get("/api/tunnel/status")
def get_tunnel_status(current_user: User = Depends(get_current_user)):
    """Get remote access tunnel status"""
    if not TUNNEL_AVAILABLE or not tunnel_manager:
        return {"available": False, "error": "Tunnel feature not available"}

    status = tunnel_manager.get_status()
    status["available"] = True
    return status


@app.post("/api/tunnel/enable")
def enable_tunnel(current_user: User = Depends(get_current_user)):
    """Enable remote access tunnel (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not TUNNEL_AVAILABLE or not tunnel_manager:
        raise HTTPException(status_code=503, detail="Tunnel feature not available")

    result = tunnel_manager.enable_tunnel()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to enable tunnel"))

    return result


@app.post("/api/tunnel/disable")
def disable_tunnel(current_user: User = Depends(get_current_user)):
    """Disable remote access tunnel (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not TUNNEL_AVAILABLE or not tunnel_manager:
        raise HTTPException(status_code=503, detail="Tunnel feature not available")

    result = tunnel_manager.disable_tunnel()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to disable tunnel"))

    return result


@app.delete("/api/tunnel")
def delete_tunnel(current_user: User = Depends(get_current_user)):
    """Delete tunnel completely (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if not TUNNEL_AVAILABLE or not tunnel_manager:
        raise HTTPException(status_code=503, detail="Tunnel feature not available")

    result = tunnel_manager.delete_tunnel()
    return result


# ============ Health Check ============

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/trap/status")
def get_trap_status():
    """Get SNMP trap receiver status"""
    global trap_receiver
    return {
        "running": trap_receiver is not None and trap_receiver.running,
        "port": trap_receiver.port if trap_receiver else 162
    }


# ============ FEATURE 1: GPS Map View ============

@app.get("/api/map/onus")
def get_map_onus(
    olt_id: Optional[int] = None,
    region_id: Optional[int] = None,
    online_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get all ONUs with GPS coordinates for map display"""
    query = db.query(ONU).filter(
        ONU.latitude.isnot(None),
        ONU.longitude.isnot(None)
    )

    if olt_id:
        query = query.filter(ONU.olt_id == olt_id)
    if region_id:
        query = query.filter(ONU.region_id == region_id)
    if online_only:
        query = query.filter(ONU.is_online == True)

    onus = query.all()

    return {
        "total": len(onus),
        "onus": [
            {
                "id": onu.id,
                "mac_address": onu.mac_address,
                "description": onu.description,
                "latitude": onu.latitude,
                "longitude": onu.longitude,
                "address": onu.address,
                "is_online": onu.is_online,
                "rx_power": onu.rx_power,
                "olt_id": onu.olt_id,
                "olt_name": onu.olt.name if onu.olt else None,
                "region_id": onu.region_id,
                "region_name": onu.region.name if onu.region else None,
                "region_color": onu.region.color if onu.region else "#3B82F6"
            }
            for onu in onus
        ]
    }


@app.get("/api/map/regions")
def get_map_regions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get all regions with GPS coordinates for map display"""
    regions = db.query(Region).filter(
        Region.latitude.isnot(None),
        Region.longitude.isnot(None)
    ).all()

    return {
        "total": len(regions),
        "regions": [
            {
                "id": region.id,
                "name": region.name,
                "latitude": region.latitude,
                "longitude": region.longitude,
                "address": region.address,
                "color": region.color,
                "onu_count": len(region.onus)
            }
            for region in regions
        ]
    }


# ============ FEATURE 2: Email Alerts ============

@app.post("/api/email/test")
async def test_email(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Test email notification"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    # Get settings
    settings = {s.key: s.value for s in db.query(Settings).all()}

    smtp_server = settings.get('smtp_server', '')
    smtp_port = int(settings.get('smtp_port', 587))
    smtp_user = settings.get('smtp_user', '')
    smtp_password = settings.get('smtp_password', '')
    email_recipient = settings.get('email_recipient', '')

    if not all([smtp_server, smtp_user, smtp_password, email_recipient]):
        raise HTTPException(status_code=400, detail="Email settings not configured")

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email_recipient
        msg['Subject'] = "OLT Manager - Test Email"

        body = f"""
        This is a test email from OLT Manager.

        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Server: {os.uname().nodename}

        If you received this, email notifications are working correctly!
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return {"success": True, "message": f"Test email sent to {email_recipient}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@app.put("/api/email/settings")
async def update_email_settings(
    smtp_server: str = Body(...),
    smtp_port: int = Body(587),
    smtp_user: str = Body(...),
    smtp_password: str = Body(...),
    email_recipient: str = Body(...),
    email_enabled: bool = Body(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update email notification settings"""
    settings_map = {
        'smtp_server': smtp_server,
        'smtp_port': str(smtp_port),
        'smtp_user': smtp_user,
        'smtp_password': smtp_password,
        'email_recipient': email_recipient,
        'email_enabled': str(email_enabled)
    }

    for key, value in settings_map.items():
        setting = db.query(Settings).filter(Settings.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(Settings(key=key, value=value))

    db.commit()
    return {"success": True, "message": "Email settings updated"}


# ============ FEATURE 3: Report Generation ============

@app.get("/api/reports/onus")
async def generate_onu_report(
    format: str = Query("json", regex="^(json|csv|excel)$"),
    olt_id: Optional[int] = None,
    region_id: Optional[int] = None,
    online_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Generate ONU report in various formats"""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    query = db.query(ONU).join(OLT)

    if olt_id:
        query = query.filter(ONU.olt_id == olt_id)
    if region_id:
        query = query.filter(ONU.region_id == region_id)
    if online_only:
        query = query.filter(ONU.is_online == True)

    onus = query.all()

    if format == "json":
        return {
            "generated_at": datetime.now().isoformat(),
            "total": len(onus),
            "onus": [
                {
                    "id": onu.id,
                    "olt_name": onu.olt.name,
                    "pon_port": onu.pon_port,
                    "onu_id": onu.onu_id,
                    "mac_address": onu.mac_address,
                    "description": onu.description,
                    "is_online": onu.is_online,
                    "rx_power": onu.rx_power,
                    "distance": onu.distance,
                    "region": onu.region.name if onu.region else None,
                    "address": onu.address,
                    "last_seen": onu.last_seen.isoformat() if onu.last_seen else None
                }
                for onu in onus
            ]
        }

    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'OLT', 'PON Port', 'ONU ID', 'MAC Address', 'Description',
                        'Online', 'RX Power (dBm)', 'Distance (m)', 'Region', 'Address', 'Last Seen'])

        for onu in onus:
            writer.writerow([
                onu.id, onu.olt.name, onu.pon_port, onu.onu_id, onu.mac_address,
                onu.description or '', onu.is_online, onu.rx_power or '',
                onu.distance or '', onu.region.name if onu.region else '',
                onu.address or '', onu.last_seen.strftime('%Y-%m-%d %H:%M') if onu.last_seen else ''
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=onu_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )

    elif format == "excel":
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "ONU Report"

            # Header
            headers = ['ID', 'OLT', 'PON Port', 'ONU ID', 'MAC Address', 'Description',
                      'Online', 'RX Power (dBm)', 'Distance (m)', 'Region', 'Address', 'Last Seen']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                cell.font = Font(bold=True, color="FFFFFF")

            # Data
            for row, onu in enumerate(onus, 2):
                ws.cell(row=row, column=1, value=onu.id)
                ws.cell(row=row, column=2, value=onu.olt.name)
                ws.cell(row=row, column=3, value=onu.pon_port)
                ws.cell(row=row, column=4, value=onu.onu_id)
                ws.cell(row=row, column=5, value=onu.mac_address)
                ws.cell(row=row, column=6, value=onu.description or '')
                ws.cell(row=row, column=7, value='Online' if onu.is_online else 'Offline')
                ws.cell(row=row, column=8, value=onu.rx_power)
                ws.cell(row=row, column=9, value=onu.distance)
                ws.cell(row=row, column=10, value=onu.region.name if onu.region else '')
                ws.cell(row=row, column=11, value=onu.address or '')
                ws.cell(row=row, column=12, value=onu.last_seen.strftime('%Y-%m-%d %H:%M') if onu.last_seen else '')

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)

            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=onu_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"}
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl not installed. Use CSV format instead.")


@app.get("/api/reports/signal-quality")
async def generate_signal_report(
    threshold: float = Query(-25.0, description="Signal threshold in dBm"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Generate signal quality report - ONUs with low signal"""
    onus = db.query(ONU).filter(
        ONU.rx_power.isnot(None),
        ONU.rx_power < threshold,
        ONU.is_online == True
    ).order_by(ONU.rx_power).all()

    return {
        "generated_at": datetime.now().isoformat(),
        "threshold": threshold,
        "total_low_signal": len(onus),
        "onus": [
            {
                "id": onu.id,
                "olt_name": onu.olt.name,
                "pon_port": onu.pon_port,
                "onu_id": onu.onu_id,
                "mac_address": onu.mac_address,
                "description": onu.description,
                "rx_power": onu.rx_power,
                "distance": onu.distance,
                "severity": "critical" if onu.rx_power < -28 else "warning"
            }
            for onu in onus
        ]
    }


# ============ FEATURE 4: Signal Quality Alerts ============

@app.get("/api/alerts/rules")
def get_alert_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get all alert rules"""
    rules = db.query(AlertRule).all()
    return {
        "total": len(rules),
        "rules": [
            {
                "id": rule.id,
                "name": rule.name,
                "rule_type": rule.rule_type,
                "threshold": rule.threshold,
                "comparison": rule.comparison,
                "notify_email": rule.notify_email,
                "notify_sms": rule.notify_sms,
                "notify_whatsapp": rule.notify_whatsapp,
                "is_enabled": rule.is_enabled,
                "cooldown_minutes": rule.cooldown_minutes
            }
            for rule in rules
        ]
    }


@app.post("/api/alerts/rules")
def create_alert_rule(
    name: str = Body(...),
    rule_type: str = Body(...),
    threshold: Optional[float] = Body(None),
    comparison: Optional[str] = Body("lt"),
    notify_email: bool = Body(False),
    notify_sms: bool = Body(False),
    notify_whatsapp: bool = Body(True),
    cooldown_minutes: int = Body(60),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new alert rule"""
    rule = AlertRule(
        name=name,
        rule_type=rule_type,
        threshold=threshold,
        comparison=comparison,
        notify_email=notify_email,
        notify_sms=notify_sms,
        notify_whatsapp=notify_whatsapp,
        cooldown_minutes=cooldown_minutes
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return {"success": True, "id": rule.id, "message": "Alert rule created"}


@app.delete("/api/alerts/rules/{rule_id}")
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete an alert rule"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    db.delete(rule)
    db.commit()
    return {"success": True, "message": "Alert rule deleted"}


# ============ FEATURE 5: Batch Operations ============

@app.post("/api/batch/onus/update")
async def batch_update_onus(
    onu_ids: List[int] = Body(...),
    region_id: Optional[int] = Body(None),
    description_prefix: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Batch update multiple ONUs"""
    updated = 0
    for onu_id in onu_ids:
        onu = db.query(ONU).filter(ONU.id == onu_id).first()
        if onu:
            if region_id is not None:
                onu.region_id = region_id
            if description_prefix:
                onu.description = f"{description_prefix} - {onu.mac_address[-8:]}"
            updated += 1

    db.commit()
    return {"success": True, "updated": updated, "message": f"Updated {updated} ONUs"}


@app.post("/api/batch/onus/reboot")
async def batch_reboot_onus(
    onu_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Batch reboot multiple ONUs"""
    results = []
    for onu_id in onu_ids:
        onu = db.query(ONU).filter(ONU.id == onu_id).first()
        if onu:
            try:
                connector = OLTConnector(
                    onu.olt.ip_address,
                    onu.olt.username,
                    decrypt_sensitive(onu.olt.password)
                )
                success = connector.reboot_onu(onu.pon_port, onu.onu_id)
                results.append({"onu_id": onu_id, "success": success})
            except Exception as e:
                results.append({"onu_id": onu_id, "success": False, "error": str(e)})

    return {"results": results, "total": len(results)}


@app.post("/api/batch/onus/delete")
async def batch_delete_onus(
    onu_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Batch delete multiple ONUs from database"""
    deleted = db.query(ONU).filter(ONU.id.in_(onu_ids)).delete(synchronize_session=False)
    db.commit()
    return {"success": True, "deleted": deleted, "message": f"Deleted {deleted} ONUs"}


# ============ FEATURE 6: Configuration Backup/Restore ============

@app.get("/api/backups")
def get_backups(
    olt_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get list of configuration backups"""
    query = db.query(ConfigBackup)
    if olt_id:
        query = query.filter(ConfigBackup.olt_id == olt_id)

    backups = query.order_by(ConfigBackup.created_at.desc()).all()

    return {
        "total": len(backups),
        "backups": [
            {
                "id": backup.id,
                "olt_id": backup.olt_id,
                "filename": backup.filename,
                "file_size": backup.file_size,
                "backup_type": backup.backup_type,
                "notes": backup.notes,
                "created_at": backup.created_at.isoformat()
            }
            for backup in backups
        ]
    }


@app.post("/api/backups/{olt_id}")
async def create_backup(
    olt_id: int,
    notes: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a configuration backup for an OLT"""
    olt = db.query(OLT).filter(OLT.id == olt_id).first()
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")

    try:
        connector = OLTConnector(olt.ip_address, olt.username, decrypt_sensitive(olt.password))
        config = connector.get_running_config()

        # Save to file
        backup_dir = Path("/opt/olt-manager/backend/backups")
        backup_dir.mkdir(exist_ok=True)

        filename = f"{olt.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cfg"
        filepath = backup_dir / filename

        with open(filepath, 'w') as f:
            f.write(config)

        # Save to database
        backup = ConfigBackup(
            olt_id=olt_id,
            filename=filename,
            file_size=len(config),
            backup_type='manual',
            notes=notes,
            created_by=current_user.id
        )
        db.add(backup)
        db.commit()

        return {"success": True, "backup_id": backup.id, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@app.get("/api/backups/{backup_id}/download")
async def download_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Download a configuration backup file"""
    from fastapi.responses import FileResponse

    backup = db.query(ConfigBackup).filter(ConfigBackup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    filepath = Path(f"/opt/olt-manager/backend/backups/{backup.filename}")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    return FileResponse(filepath, filename=backup.filename)


@app.delete("/api/backups/{backup_id}")
async def delete_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a configuration backup"""
    backup = db.query(ConfigBackup).filter(ConfigBackup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Delete file
    filepath = Path(f"/opt/olt-manager/backend/backups/{backup.filename}")
    if filepath.exists():
        filepath.unlink()

    db.delete(backup)
    db.commit()
    return {"success": True, "message": "Backup deleted"}


# ============ SYSTEM BACKUP - Full Database Backup/Restore ============

def upload_to_ftp(filepath: Path, settings: BackupSettings) -> tuple:
    """Upload backup file to FTP/SFTP server"""
    import ftplib
    try:
        if settings.ftp_use_sftp:
            # SFTP using paramiko
            import paramiko
            transport = paramiko.Transport((settings.ftp_host, settings.ftp_port or 22))
            transport.connect(username=settings.ftp_username, password=settings.ftp_password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            remote_path = f"{settings.ftp_path}/{filepath.name}"
            sftp.put(str(filepath), remote_path)
            sftp.close()
            transport.close()
            return True, remote_path
        else:
            # FTP
            ftp = ftplib.FTP()
            ftp.connect(settings.ftp_host, settings.ftp_port or 21)
            ftp.login(settings.ftp_username, settings.ftp_password)
            try:
                ftp.cwd(settings.ftp_path)
            except:
                ftp.mkd(settings.ftp_path)
                ftp.cwd(settings.ftp_path)
            with open(filepath, 'rb') as f:
                ftp.storbinary(f'STOR {filepath.name}', f)
            ftp.quit()
            return True, f"{settings.ftp_path}/{filepath.name}"
    except Exception as e:
        return False, str(e)


def upload_to_s3(filepath: Path, settings: BackupSettings) -> tuple:
    """Upload backup file to AWS S3"""
    try:
        import boto3
        s3 = boto3.client(
            's3',
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key
        )
        s3_key = f"{settings.s3_path.strip('/')}/{filepath.name}"
        s3.upload_file(str(filepath), settings.s3_bucket, s3_key)
        return True, f"s3://{settings.s3_bucket}/{s3_key}"
    except Exception as e:
        return False, str(e)


# Backup encryption key (embedded in compiled binary - not visible to customers)
BACKUP_ENCRYPTION_KEY = b'OLT_M@n@g3r_S3cur3_B@ckup_K3y_2024!'  # 32 bytes for AES-256

def encrypt_backup(data: bytes) -> bytes:
    """Encrypt backup data using AES-256"""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import os

    # Generate random IV
    iv = os.urandom(16)

    # Pad data to 16-byte boundary
    pad_len = 16 - (len(data) % 16)
    padded_data = data + bytes([pad_len] * pad_len)

    # Encrypt
    cipher = Cipher(algorithms.AES(BACKUP_ENCRYPTION_KEY[:32]), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()

    # Return IV + encrypted data
    return iv + encrypted

def decrypt_backup(encrypted_data: bytes) -> bytes:
    """Decrypt backup data using AES-256"""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend

    # Extract IV and encrypted data
    iv = encrypted_data[:16]
    encrypted = encrypted_data[16:]

    # Decrypt
    cipher = Cipher(algorithms.AES(BACKUP_ENCRYPTION_KEY[:32]), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()

    # Remove padding
    pad_len = padded_data[-1]
    return padded_data[:-pad_len]


def create_system_backup_file(db: Session, include_uploads: bool = False) -> tuple:
    """Create a full system backup file (encrypted)"""
    import zipfile
    import sqlite3
    import shutil

    backup_dir = Path("/opt/olt-manager/backups")
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"olt_manager_backup_{timestamp}.zip"
    backup_path = backup_dir / backup_filename

    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Backup database - check multiple possible locations
            db_paths = [
                Path("/opt/olt-manager/olt_manager.db"),  # Compiled binary installation
                Path("/opt/olt-manager/data/olt_manager.db"),  # Compiled with data folder
                Path("/root/olt-manager/backend/olt_manager.db"),
                Path("/opt/olt-manager/backend/olt_manager.db"),
                Path("/opt/olt-manager/backend/data/olt_manager.db"),
                Path("./olt_manager.db"),
                Path("./data/olt_manager.db")
            ]
            for db_path in db_paths:
                if db_path.exists():
                    # Create a copy to avoid locking issues
                    temp_db = backup_dir / f"temp_db_{timestamp}.db"
                    shutil.copy2(db_path, temp_db)
                    zipf.write(temp_db, "database/olt_manager.db")
                    temp_db.unlink()
                    break

            # Backup license files
            license_dir = Path("/etc/olt-manager")
            if license_dir.exists():
                for f in license_dir.iterdir():
                    if f.is_file():
                        zipf.write(f, f"config/{f.name}")

            # Backup uploads if requested - check multiple locations
            if include_uploads:
                upload_paths = [
                    Path("/opt/olt-manager/uploads"),  # Compiled binary installation
                    Path("/root/olt-manager/backend/uploads"),
                    Path("/opt/olt-manager/backend/uploads")
                ]
                for uploads_dir in upload_paths:
                    if uploads_dir.exists():
                        for f in uploads_dir.rglob("*"):
                            if f.is_file():
                                arcname = f"uploads/{f.relative_to(uploads_dir)}"
                                zipf.write(f, arcname)
                        break  # Only backup from first found location

            # Add backup metadata
            metadata = {
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
                "includes_uploads": include_uploads
            }
            zipf.writestr("metadata.json", json.dumps(metadata, indent=2))

        # Encrypt the backup file
        with open(backup_path, 'rb') as f:
            zip_data = f.read()

        encrypted_data = encrypt_backup(zip_data)

        # Save encrypted backup with .bak extension (hides that it's a zip)
        encrypted_path = backup_path.with_suffix('.bak')
        with open(encrypted_path, 'wb') as f:
            # Add magic header to identify encrypted backups
            f.write(b'OLTBAK01')  # 8-byte magic header
            f.write(encrypted_data)

        # Remove unencrypted zip
        backup_path.unlink()

        file_size = encrypted_path.stat().st_size
        return True, encrypted_path, file_size
    except Exception as e:
        if backup_path.exists():
            backup_path.unlink()
        return False, None, str(e)


@app.get("/api/system-backups")
def get_system_backups(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get list of system backups"""
    backups = db.query(SystemBackup).order_by(SystemBackup.created_at.desc()).all()

    return {
        "total": len(backups),
        "backups": [
            {
                "id": backup.id,
                "filename": backup.filename,
                "file_size": backup.file_size,
                "file_size_mb": round(backup.file_size / 1024 / 1024, 2) if backup.file_size else 0,
                "backup_type": backup.backup_type,
                "storage_type": backup.storage_type,
                "storage_path": backup.storage_path,
                "includes_db": backup.includes_db,
                "includes_config": backup.includes_config,
                "includes_uploads": backup.includes_uploads,
                "status": backup.status,
                "error_message": backup.error_message,
                "notes": backup.notes,
                "created_at": backup.created_at.isoformat()
            }
            for backup in backups
        ]
    }


@app.post("/api/system-backups")
async def create_system_backup(
    include_uploads: bool = Body(False),
    upload_to: Optional[str] = Body(None),  # 'ftp', 's3', or None for local only
    notes: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a full system backup"""
    # Get backup settings
    settings = db.query(BackupSettings).first()

    # Create backup file
    success, backup_path, file_size = create_system_backup_file(db, include_uploads)
    if not success:
        raise HTTPException(status_code=500, detail=f"Backup failed: {file_size}")

    storage_type = 'local'
    storage_path = str(backup_path)
    status = 'completed'
    error_message = None

    # Upload to remote storage if requested
    if upload_to and settings:
        if upload_to == 'ftp' and settings.ftp_host:
            storage_type = 'sftp' if settings.ftp_use_sftp else 'ftp'
            success, result = upload_to_ftp(backup_path, settings)
            if success:
                storage_path = result
            else:
                status = 'failed'
                error_message = f"FTP upload failed: {result}"
        elif upload_to == 's3' and settings.s3_bucket:
            storage_type = 's3'
            success, result = upload_to_s3(backup_path, settings)
            if success:
                storage_path = result
            else:
                status = 'failed'
                error_message = f"S3 upload failed: {result}"

    # Save backup record
    backup = SystemBackup(
        filename=backup_path.name,
        file_size=file_size if isinstance(file_size, int) else 0,
        backup_type='manual',
        storage_type=storage_type,
        storage_path=storage_path,
        includes_db=True,
        includes_config=True,
        includes_uploads=include_uploads,
        status=status,
        error_message=error_message,
        notes=notes,
        created_by=current_user.id
    )
    db.add(backup)
    db.commit()

    # Update backup settings with last backup info
    if settings:
        settings.last_backup_at = datetime.now()
        settings.last_backup_status = status
        db.commit()

    return {
        "success": status == 'completed',
        "backup_id": backup.id,
        "filename": backup.filename,
        "file_size_mb": round(backup.file_size / 1024 / 1024, 2) if backup.file_size else 0,
        "storage_type": storage_type,
        "storage_path": storage_path,
        "error": error_message
    }


@app.get("/api/system-backups/{backup_id}/download")
async def download_system_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Download a system backup file"""
    from fastapi.responses import FileResponse

    backup = db.query(SystemBackup).filter(SystemBackup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    if backup.storage_type != 'local':
        raise HTTPException(status_code=400, detail="Cannot download remote backups directly. Use the storage path to access.")

    filepath = Path(f"/opt/olt-manager/backups/{backup.filename}")
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found on disk")

    return FileResponse(filepath, filename=backup.filename, media_type='application/zip')


@app.post("/api/system-backups/{backup_id}/restore")
async def restore_system_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Restore from a system backup"""
    import zipfile
    import shutil
    import sqlite3

    backup = db.query(SystemBackup).filter(SystemBackup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    backup_path = Path(f"/opt/olt-manager/backups/{backup.filename}")
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    # Save all current backup records BEFORE restoring (they will be lost when DB is replaced)
    all_backups = db.query(SystemBackup).all()
    backup_records = []
    for b in all_backups:
        backup_records.append({
            'id': b.id,
            'filename': b.filename,
            'file_size': b.file_size,
            'backup_type': b.backup_type,
            'storage_type': b.storage_type,
            'storage_path': b.storage_path,
            'includes_db': b.includes_db,
            'includes_config': b.includes_config,
            'includes_uploads': b.includes_uploads,
            'status': b.status,
            'error_message': b.error_message,
            'notes': b.notes,
            'created_by': b.created_by,
            'created_at': b.created_at.isoformat() if b.created_at else None
        })

    try:
        # Check if backup is encrypted
        with open(backup_path, 'rb') as f:
            header = f.read(8)
            is_encrypted = header == b'OLTBAK01'

        temp_dir = Path("/tmp/olt_restore")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        if is_encrypted:
            # Decrypt the backup first
            with open(backup_path, 'rb') as f:
                f.read(8)  # Skip magic header
                encrypted_data = f.read()

            zip_data = decrypt_backup(encrypted_data)

            # Write decrypted zip to temp file
            temp_zip = temp_dir / "backup.zip"
            with open(temp_zip, 'wb') as f:
                f.write(zip_data)

            # Extract from decrypted zip
            with zipfile.ZipFile(temp_zip, 'r') as zipf:
                zipf.extractall(temp_dir)

            # Remove temp zip
            temp_zip.unlink()
        else:
            # Old unencrypted backup - extract directly
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(temp_dir)

        # Restore database - find the actual database location
        db_backup = temp_dir / "database" / "olt_manager.db"
        if db_backup.exists():
            # Find actual database location
            db_target = None
            db_paths = [
                Path("/opt/olt-manager/olt_manager.db"),  # Compiled binary installation
                Path("/opt/olt-manager/data/olt_manager.db"),  # Compiled with data folder
                Path("/root/olt-manager/backend/olt_manager.db"),
                Path("/opt/olt-manager/backend/olt_manager.db"),
                Path("/opt/olt-manager/backend/data/olt_manager.db")
            ]
            for p in db_paths:
                if p.exists():
                    db_target = p
                    break

            # If no existing db found, use the first path
            if not db_target:
                db_target = db_paths[0]
                db_target.parent.mkdir(parents=True, exist_ok=True)

            # Close current db connections
            db.close()
            # Backup current db just in case
            if db_target.exists():
                shutil.copy2(db_target, db_target.with_suffix('.db.bak'))
            # Restore
            shutil.copy2(db_backup, db_target)

        # Restore config files
        config_dir = temp_dir / "config"
        if config_dir.exists():
            target_config = Path("/etc/olt-manager")
            target_config.mkdir(exist_ok=True)
            for f in config_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, target_config / f.name)

        # Restore uploads if present - find actual uploads location
        uploads_backup = temp_dir / "uploads"
        if uploads_backup.exists():
            # Find actual uploads location
            uploads_target = None
            upload_paths = [
                Path("/opt/olt-manager/uploads"),  # Compiled binary installation
                Path("/root/olt-manager/backend/uploads"),
                Path("/opt/olt-manager/backend/uploads")
            ]
            for p in upload_paths:
                if p.exists():
                    uploads_target = p
                    break

            if not uploads_target:
                uploads_target = upload_paths[0]

            uploads_target.mkdir(parents=True, exist_ok=True)
            for f in uploads_backup.rglob("*"):
                if f.is_file():
                    target = uploads_target / f.relative_to(uploads_backup)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)

        # Cleanup temp directory
        shutil.rmtree(temp_dir)

        # Re-insert all backup records into the restored database
        # This ensures backup history is preserved even after restore
        if db_target and backup_records:
            try:
                conn = sqlite3.connect(str(db_target))
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_backups (
                        id INTEGER PRIMARY KEY,
                        filename VARCHAR(255) NOT NULL,
                        file_size INTEGER,
                        backup_type VARCHAR(20) DEFAULT 'manual',
                        storage_type VARCHAR(20) DEFAULT 'local',
                        storage_path VARCHAR(500),
                        includes_db BOOLEAN DEFAULT 1,
                        includes_config BOOLEAN DEFAULT 1,
                        includes_uploads BOOLEAN DEFAULT 0,
                        status VARCHAR(20) DEFAULT 'completed',
                        error_message VARCHAR(500),
                        notes VARCHAR(500),
                        created_by INTEGER,
                        created_at DATETIME
                    )
                ''')

                # Insert or replace backup records
                for rec in backup_records:
                    cursor.execute('''
                        INSERT OR REPLACE INTO system_backups
                        (id, filename, file_size, backup_type, storage_type, storage_path,
                         includes_db, includes_config, includes_uploads, status,
                         error_message, notes, created_by, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        rec['id'], rec['filename'], rec['file_size'], rec['backup_type'],
                        rec['storage_type'], rec['storage_path'], rec['includes_db'],
                        rec['includes_config'], rec['includes_uploads'], rec['status'],
                        rec['error_message'], rec['notes'], rec['created_by'], rec['created_at']
                    ))

                conn.commit()
                conn.close()
            except Exception as sql_err:
                print(f"Warning: Could not restore backup records: {sql_err}")

        return {
            "success": True,
            "message": "Backup restored successfully. Please restart the service for changes to take effect.",
            "restart_command": "systemctl restart olt-backend"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")


@app.delete("/api/system-backups/{backup_id}")
async def delete_system_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a system backup"""
    backup = db.query(SystemBackup).filter(SystemBackup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    # Delete local file if exists
    if backup.storage_type == 'local':
        filepath = Path(f"/opt/olt-manager/backups/{backup.filename}")
        if filepath.exists():
            filepath.unlink()

    db.delete(backup)
    db.commit()
    return {"success": True, "message": "Backup deleted"}


# ============ BACKUP SETTINGS ============

@app.get("/api/backup-settings")
def get_backup_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get backup settings"""
    settings = db.query(BackupSettings).first()
    if not settings:
        # Create default settings
        settings = BackupSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return {
        "auto_backup_enabled": settings.auto_backup_enabled,
        "backup_frequency": settings.backup_frequency,
        "backup_time": settings.backup_time,
        "backup_day": settings.backup_day,
        "retention_days": settings.retention_days,
        "backup_database": settings.backup_database,
        "backup_config": settings.backup_config,
        "backup_uploads": settings.backup_uploads,
        "storage_type": settings.storage_type,
        "local_path": settings.local_path,
        "ftp_host": settings.ftp_host,
        "ftp_port": settings.ftp_port,
        "ftp_username": settings.ftp_username,
        "ftp_password": "***" if settings.ftp_password else None,
        "ftp_path": settings.ftp_path,
        "ftp_use_sftp": settings.ftp_use_sftp,
        "s3_bucket": settings.s3_bucket,
        "s3_region": settings.s3_region,
        "s3_access_key": settings.s3_access_key[:8] + "***" if settings.s3_access_key else None,
        "s3_secret_key": "***" if settings.s3_secret_key else None,
        "s3_path": settings.s3_path,
        "last_backup_at": settings.last_backup_at.isoformat() if settings.last_backup_at else None,
        "last_backup_status": settings.last_backup_status,
        "next_backup_at": settings.next_backup_at.isoformat() if settings.next_backup_at else None
    }


@app.put("/api/backup-settings")
def update_backup_settings(
    auto_backup_enabled: Optional[bool] = Body(None),
    backup_frequency: Optional[str] = Body(None),
    backup_time: Optional[str] = Body(None),
    backup_day: Optional[int] = Body(None),
    retention_days: Optional[int] = Body(None),
    backup_database: Optional[bool] = Body(None),
    backup_config: Optional[bool] = Body(None),
    backup_uploads: Optional[bool] = Body(None),
    storage_type: Optional[str] = Body(None),
    local_path: Optional[str] = Body(None),
    ftp_host: Optional[str] = Body(None),
    ftp_port: Optional[int] = Body(None),
    ftp_username: Optional[str] = Body(None),
    ftp_password: Optional[str] = Body(None),
    ftp_path: Optional[str] = Body(None),
    ftp_use_sftp: Optional[bool] = Body(None),
    s3_bucket: Optional[str] = Body(None),
    s3_region: Optional[str] = Body(None),
    s3_access_key: Optional[str] = Body(None),
    s3_secret_key: Optional[str] = Body(None),
    s3_path: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update backup settings"""
    settings = db.query(BackupSettings).first()
    if not settings:
        settings = BackupSettings()
        db.add(settings)

    # Update fields if provided
    if auto_backup_enabled is not None:
        settings.auto_backup_enabled = auto_backup_enabled
    if backup_frequency:
        settings.backup_frequency = backup_frequency
    if backup_time:
        settings.backup_time = backup_time
    if backup_day is not None:
        settings.backup_day = backup_day
    if retention_days is not None:
        settings.retention_days = retention_days
    if backup_database is not None:
        settings.backup_database = backup_database
    if backup_config is not None:
        settings.backup_config = backup_config
    if backup_uploads is not None:
        settings.backup_uploads = backup_uploads
    if storage_type:
        settings.storage_type = storage_type
    if local_path:
        settings.local_path = local_path
    if ftp_host is not None:
        settings.ftp_host = ftp_host
    if ftp_port is not None:
        settings.ftp_port = ftp_port
    if ftp_username is not None:
        settings.ftp_username = ftp_username
    if ftp_password and ftp_password != "***":
        settings.ftp_password = ftp_password
    if ftp_path is not None:
        settings.ftp_path = ftp_path
    if ftp_use_sftp is not None:
        settings.ftp_use_sftp = ftp_use_sftp
    if s3_bucket is not None:
        settings.s3_bucket = s3_bucket
    if s3_region is not None:
        settings.s3_region = s3_region
    if s3_access_key and not s3_access_key.endswith("***"):
        settings.s3_access_key = s3_access_key
    if s3_secret_key and s3_secret_key != "***":
        settings.s3_secret_key = s3_secret_key
    if s3_path is not None:
        settings.s3_path = s3_path

    # Calculate next backup time
    if settings.auto_backup_enabled:
        settings.next_backup_at = calculate_next_backup_time(settings)

    db.commit()
    return {"success": True, "message": "Backup settings updated"}


def calculate_next_backup_time(settings: BackupSettings) -> datetime:
    """Calculate the next scheduled backup time"""
    now = datetime.now()
    backup_hour, backup_minute = map(int, settings.backup_time.split(':'))

    if settings.backup_frequency == 'hourly':
        next_time = now.replace(minute=backup_minute, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(hours=1)
    elif settings.backup_frequency == 'daily':
        next_time = now.replace(hour=backup_hour, minute=backup_minute, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(days=1)
    elif settings.backup_frequency == 'weekly':
        next_time = now.replace(hour=backup_hour, minute=backup_minute, second=0, microsecond=0)
        days_ahead = (settings.backup_day or 0) - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_time += timedelta(days=days_ahead)
    elif settings.backup_frequency == 'monthly':
        next_time = now.replace(day=settings.backup_day or 1, hour=backup_hour, minute=backup_minute, second=0, microsecond=0)
        if next_time <= now:
            if now.month == 12:
                next_time = next_time.replace(year=now.year + 1, month=1)
            else:
                next_time = next_time.replace(month=now.month + 1)
    else:
        next_time = now + timedelta(days=1)

    return next_time


@app.post("/api/backup-settings/test-ftp")
async def test_ftp_connection(
    ftp_host: str = Body(...),
    ftp_port: int = Body(21),
    ftp_username: str = Body(...),
    ftp_password: str = Body(...),
    ftp_path: str = Body("/"),
    ftp_use_sftp: bool = Body(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Test FTP/SFTP connection"""
    try:
        if ftp_use_sftp:
            import paramiko
            transport = paramiko.Transport((ftp_host, ftp_port or 22))
            transport.connect(username=ftp_username, password=ftp_password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.listdir(ftp_path)
            sftp.close()
            transport.close()
        else:
            import ftplib
            ftp = ftplib.FTP()
            ftp.connect(ftp_host, ftp_port or 21)
            ftp.login(ftp_username, ftp_password)
            ftp.cwd(ftp_path)
            ftp.quit()
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/backup-settings/test-s3")
async def test_s3_connection(
    s3_bucket: str = Body(...),
    s3_region: str = Body(...),
    s3_access_key: str = Body(...),
    s3_secret_key: str = Body(...),
    s3_path: str = Body("/"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Test AWS S3 connection"""
    try:
        import boto3
        s3 = boto3.client(
            's3',
            region_name=s3_region,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key
        )
        # Test by listing bucket contents
        s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_path.strip('/'), MaxKeys=1)
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/system-backups/upload")
async def upload_backup_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Upload a backup file for restore"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip backup files are supported")

    backup_dir = Path("/opt/olt-manager/backups")
    backup_dir.mkdir(exist_ok=True)

    # Save uploaded file
    filepath = backup_dir / file.filename
    with open(filepath, 'wb') as f:
        content = await file.read()
        f.write(content)

    # Create backup record
    backup = SystemBackup(
        filename=file.filename,
        file_size=len(content),
        backup_type='uploaded',
        storage_type='local',
        storage_path=str(filepath),
        includes_db=True,
        includes_config=True,
        status='completed',
        notes='Uploaded for restore',
        created_by=current_user.id
    )
    db.add(backup)
    db.commit()

    return {
        "success": True,
        "backup_id": backup.id,
        "filename": file.filename,
        "file_size_mb": round(len(content) / 1024 / 1024, 2)
    }


# ============ FEATURE 7: Scheduled Tasks ============

@app.get("/api/scheduled-tasks")
def get_scheduled_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get all scheduled tasks"""
    tasks = db.query(ScheduledTask).all()
    return {
        "total": len(tasks),
        "tasks": [
            {
                "id": task.id,
                "name": task.name,
                "task_type": task.task_type,
                "target_type": task.target_type,
                "target_id": task.target_id,
                "schedule_type": task.schedule_type,
                "schedule_time": task.schedule_time,
                "schedule_day": task.schedule_day,
                "is_enabled": task.is_enabled,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None
            }
            for task in tasks
        ]
    }


@app.post("/api/scheduled-tasks")
def create_scheduled_task(
    name: str = Body(...),
    task_type: str = Body(...),
    target_type: Optional[str] = Body(None),
    target_id: Optional[int] = Body(None),
    schedule_type: str = Body(...),
    schedule_time: str = Body(...),
    schedule_day: Optional[int] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new scheduled task"""
    task = ScheduledTask(
        name=name,
        task_type=task_type,
        target_type=target_type,
        target_id=target_id,
        schedule_type=schedule_type,
        schedule_time=schedule_time,
        schedule_day=schedule_day,
        created_by=current_user.id
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return {"success": True, "id": task.id, "message": "Scheduled task created"}


@app.put("/api/scheduled-tasks/{task_id}/toggle")
def toggle_scheduled_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Enable/disable a scheduled task"""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_enabled = not task.is_enabled
    db.commit()

    return {"success": True, "is_enabled": task.is_enabled}


@app.delete("/api/scheduled-tasks/{task_id}")
def delete_scheduled_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a scheduled task"""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"success": True, "message": "Scheduled task deleted"}


# ============ FEATURE 8: Event History Log ============

def log_event(db: Session, event_type: str, entity_type: str, entity_id: int,
              olt_id: int = None, description: str = None, details: dict = None):
    """Helper function to log events"""
    event = EventLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        olt_id=olt_id,
        description=description,
        details=json.dumps(details) if details else None
    )
    db.add(event)
    db.commit()


@app.get("/api/events")
def get_events(
    event_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    olt_id: Optional[int] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get event history"""
    query = db.query(EventLog)

    if event_type:
        query = query.filter(EventLog.event_type == event_type)
    if entity_type:
        query = query.filter(EventLog.entity_type == entity_type)
    if olt_id:
        query = query.filter(EventLog.olt_id == olt_id)

    total = query.count()
    events = query.order_by(EventLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "olt_id": event.olt_id,
                "description": event.description,
                "details": json.loads(event.details) if event.details else None,
                "created_at": event.created_at.isoformat()
            }
            for event in events
        ]
    }


@app.get("/api/events/onu/{onu_id}")
def get_onu_events(
    onu_id: int,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get event history for a specific ONU"""
    events = db.query(EventLog).filter(
        EventLog.entity_type == 'onu',
        EventLog.entity_id == onu_id
    ).order_by(EventLog.created_at.desc()).limit(limit).all()

    return {
        "onu_id": onu_id,
        "total": len(events),
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "description": event.description,
                "details": json.loads(event.details) if event.details else None,
                "created_at": event.created_at.isoformat()
            }
            for event in events
        ]
    }


@app.delete("/api/events/cleanup")
def cleanup_old_events(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete events older than specified days"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = db.query(EventLog).filter(EventLog.created_at < cutoff).delete()
    db.commit()
    return {"success": True, "deleted": deleted, "message": f"Deleted {deleted} events older than {days} days"}


# ============ FEATURE 9: Customer Self-Portal (API) ============

@app.get("/api/portal/status/{mac_address}")
def get_customer_status(
    mac_address: str,
    db: Session = Depends(get_db)
):
    """Public endpoint for customers to check their ONU status by MAC address"""
    # Normalize MAC address format
    mac = mac_address.upper().replace('-', ':')

    onu = db.query(ONU).filter(ONU.mac_address == mac).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    return {
        "mac_address": onu.mac_address,
        "description": onu.description,
        "is_online": onu.is_online,
        "signal_quality": "good" if onu.rx_power and onu.rx_power > -25 else "fair" if onu.rx_power and onu.rx_power > -28 else "poor",
        "rx_power": onu.rx_power,
        "last_seen": onu.last_seen.isoformat() if onu.last_seen else None,
        "olt_name": onu.olt.name if onu.olt else None,
        "region": onu.region.name if onu.region else None
    }


@app.get("/api/portal/speed-test/{mac_address}")
def get_customer_traffic(
    mac_address: str,
    db: Session = Depends(get_db)
):
    """Get current traffic for customer's ONU"""
    mac = mac_address.upper().replace('-', ':')

    onu = db.query(ONU).filter(ONU.mac_address == mac).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    # Get latest traffic history
    traffic = db.query(TrafficHistory).filter(
        TrafficHistory.entity_type == 'onu',
        TrafficHistory.onu_db_id == onu.id
    ).order_by(TrafficHistory.timestamp.desc()).first()

    return {
        "mac_address": onu.mac_address,
        "download_kbps": traffic.rx_kbps if traffic else 0,
        "upload_kbps": traffic.tx_kbps if traffic else 0,
        "download_mbps": round(traffic.rx_kbps / 1000, 2) if traffic else 0,
        "upload_mbps": round(traffic.tx_kbps / 1000, 2) if traffic else 0,
        "timestamp": traffic.timestamp.isoformat() if traffic else None
    }


# ============ FEATURE 10: Mobile App API Endpoints ============

@app.get("/api/mobile/dashboard")
def mobile_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Optimized dashboard for mobile app"""
    # Get counts
    total_olts = db.query(func.count(OLT.id)).scalar()
    online_olts = db.query(func.count(OLT.id)).filter(OLT.is_online == True).scalar()
    total_onus = db.query(func.count(ONU.id)).scalar()
    online_onus = db.query(func.count(ONU.id)).filter(ONU.is_online == True).scalar()

    # Get OLTs with issues
    olts_with_issues = db.query(OLT).filter(OLT.is_online == False).all()

    # Get recent events
    recent_events = db.query(EventLog).order_by(EventLog.created_at.desc()).limit(10).all()

    return {
        "summary": {
            "olts": {"total": total_olts, "online": online_olts, "offline": total_olts - online_olts},
            "onus": {"total": total_onus, "online": online_onus, "offline": total_onus - online_onus}
        },
        "issues": [
            {"id": olt.id, "name": olt.name, "ip": olt.ip_address, "error": olt.last_error}
            for olt in olts_with_issues
        ],
        "recent_events": [
            {
                "type": event.event_type,
                "description": event.description,
                "time": event.created_at.isoformat()
            }
            for event in recent_events
        ]
    }


@app.get("/api/mobile/onus")
def mobile_onu_list(
    search: Optional[str] = None,
    online_only: bool = False,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Simplified ONU list for mobile app"""
    query = db.query(ONU)

    if search:
        query = query.filter(
            or_(
                ONU.mac_address.ilike(f"%{search}%"),
                ONU.description.ilike(f"%{search}%")
            )
        )
    if online_only:
        query = query.filter(ONU.is_online == True)

    onus = query.limit(limit).all()

    return {
        "total": len(onus),
        "onus": [
            {
                "id": onu.id,
                "mac": onu.mac_address,
                "name": onu.description,
                "online": onu.is_online,
                "signal": onu.rx_power,
                "olt": onu.olt.name if onu.olt else None
            }
            for onu in onus
        ]
    }


@app.post("/api/mobile/onu/{onu_id}/reboot")
async def mobile_reboot_onu(
    onu_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Quick ONU reboot for mobile app"""
    onu = db.query(ONU).filter(ONU.id == onu_id).first()
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")

    try:
        connector = OLTConnector(
            onu.olt.ip_address,
            onu.olt.username,
            decrypt_sensitive(onu.olt.password)
        )
        success = connector.reboot_onu(onu.pon_port, onu.onu_id)

        if success:
            log_event(db, 'onu_reboot', 'onu', onu.id, onu.olt_id,
                     f"ONU {onu.mac_address} rebooted via mobile app")

        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/mobile/notifications")
def mobile_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get recent notifications for mobile app"""
    # Get recent alerts and events
    recent_events = db.query(EventLog).filter(
        EventLog.event_type.in_(['onu_offline', 'olt_offline', 'signal_low', 'signal_critical'])
    ).order_by(EventLog.created_at.desc()).limit(50).all()

    return {
        "notifications": [
            {
                "id": event.id,
                "type": event.event_type,
                "title": event.event_type.replace('_', ' ').title(),
                "message": event.description,
                "time": event.created_at.isoformat(),
                "read": False
            }
            for event in recent_events
        ]
    }


# ============ SERVICES MANAGEMENT ============

@app.get("/api/services/status")
def get_service_status(
    current_user: User = Depends(require_admin)
):
    """Get OLT Manager service status"""
    import subprocess

    try:
        # Check olt-manager service status
        result = subprocess.run(
            ['systemctl', 'is-active', 'olt-manager'],
            capture_output=True, text=True, timeout=10
        )
        service_status = result.stdout.strip()

        # Get uptime
        uptime_result = subprocess.run(
            ['systemctl', 'show', 'olt-manager', '--property=ActiveEnterTimestamp'],
            capture_output=True, text=True, timeout=10
        )
        uptime_line = uptime_result.stdout.strip()
        service_uptime = uptime_line.split('=')[1] if '=' in uptime_line else None

        # Get system uptime
        with open('/proc/uptime', 'r') as f:
            system_uptime_seconds = float(f.read().split()[0])

        # Get memory info
        mem_result = subprocess.run(
            ['free', '-m'],
            capture_output=True, text=True, timeout=10
        )
        mem_lines = mem_result.stdout.strip().split('\n')
        mem_parts = mem_lines[1].split()
        total_mem = int(mem_parts[1])
        used_mem = int(mem_parts[2])

        # Get disk info
        disk_result = subprocess.run(
            ['df', '-h', '/'],
            capture_output=True, text=True, timeout=10
        )
        disk_lines = disk_result.stdout.strip().split('\n')
        disk_parts = disk_lines[1].split()
        disk_total = disk_parts[1]
        disk_used = disk_parts[2]
        disk_percent = disk_parts[4]

        return {
            "service": {
                "name": "olt-manager",
                "status": service_status,
                "uptime": service_uptime
            },
            "system": {
                "uptime_seconds": int(system_uptime_seconds),
                "uptime_days": round(system_uptime_seconds / 86400, 1),
                "memory_total_mb": total_mem,
                "memory_used_mb": used_mem,
                "memory_percent": round(used_mem / total_mem * 100, 1),
                "disk_total": disk_total,
                "disk_used": disk_used,
                "disk_percent": disk_percent
            }
        }
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return {"error": str(e)}


@app.post("/api/services/restart")
def restart_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Restart OLT Manager service"""
    import subprocess

    try:
        # Log the action
        log_event(db, 'service_restart', 'system', None, None,
                 f"Service restart initiated by {current_user.username}")

        # Schedule restart in background (give time for response)
        subprocess.Popen(
            ['bash', '-c', 'sleep 2 && systemctl restart olt-manager'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return {
            "success": True,
            "message": "Service restart initiated. Please wait 10-15 seconds and refresh."
        }
    except Exception as e:
        logger.error(f"Error restarting service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/services/reboot-server")
def reboot_server(
    delay: int = Body(default=5, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Reboot the server"""
    import subprocess

    try:
        # Log the action
        log_event(db, 'server_reboot', 'system', None, None,
                 f"Server reboot initiated by {current_user.username}")

        # Schedule reboot
        subprocess.Popen(
            ['bash', '-c', f'sleep {delay} && reboot'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return {
            "success": True,
            "message": f"Server will reboot in {delay} seconds."
        }
    except Exception as e:
        logger.error(f"Error initiating reboot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/services/stop")
def stop_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Stop OLT Manager service"""
    import subprocess

    try:
        # Log the action
        log_event(db, 'service_stop', 'system', None, None,
                 f"Service stop initiated by {current_user.username}")

        # Schedule stop in background
        subprocess.Popen(
            ['bash', '-c', 'sleep 2 && systemctl stop olt-manager'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return {
            "success": True,
            "message": "Service stop initiated."
        }
    except Exception as e:
        logger.error(f"Error stopping service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Catch-all route to serve React frontend (must be LAST)
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve React frontend for non-API routes"""
    from fastapi.responses import FileResponse, HTMLResponse

    # Skip API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    # Use the global STATIC_DIR found at startup
    if not STATIC_DIR:
        raise HTTPException(status_code=404, detail="Frontend not configured")

    index_file = os.path.join(STATIC_DIR, "index.html")

    # Try to serve the exact file first (for assets like favicon, manifest, etc.)
    if full_path:
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

    # Otherwise serve index.html for SPA routing
    if os.path.exists(index_file):
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
