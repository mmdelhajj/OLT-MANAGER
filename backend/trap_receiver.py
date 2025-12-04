"""SNMP Trap Receiver for OLT Manager - Instant ONU status notifications"""
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Common VSOL/GPON ONU-related OIDs for traps
# These may vary by OLT vendor - VSOL uses proprietary OIDs
TRAP_OID_PATTERNS = {
    # Generic SNMP traps
    'linkDown': '1.3.6.1.6.3.1.1.5.3',
    'linkUp': '1.3.6.1.6.3.1.1.5.4',
    # VSOL specific (may need adjustment based on your OLT)
    'onuOffline': '1.3.6.1.4.1.37950',  # VSOL enterprise OID prefix
    'onuOnline': '1.3.6.1.4.1.37950',
}


@dataclass
class TrapEvent:
    """Represents a parsed SNMP trap event"""
    timestamp: datetime
    source_ip: str
    event_type: str  # 'online', 'offline', 'unknown'
    pon_port: Optional[int] = None
    onu_id: Optional[int] = None
    mac_address: Optional[str] = None
    description: Optional[str] = None
    raw_oid: Optional[str] = None
    raw_value: Optional[str] = None


class SNMPTrapReceiver:
    """
    Async SNMP Trap receiver that listens for ONU status changes.
    Uses pysnmp for trap reception.
    """

    def __init__(self,
                 bind_address: str = '0.0.0.0',
                 port: int = 162,
                 community: str = 'public'):
        self.bind_address = bind_address
        self.port = port
        self.community = community
        self.running = False
        self.callback: Optional[Callable[[TrapEvent], None]] = None
        self._transport = None
        self._protocol = None

    def set_callback(self, callback: Callable[[TrapEvent], None]):
        """Set callback function to be called when trap is received"""
        self.callback = callback

    def parse_trap(self, source_ip: str, var_binds: list) -> TrapEvent:
        """Parse SNMP trap variable bindings into TrapEvent"""
        event = TrapEvent(
            timestamp=datetime.utcnow(),
            source_ip=source_ip,
            event_type='unknown'
        )

        for oid, value in var_binds:
            oid_str = str(oid)
            value_str = str(value)

            logger.debug(f"Trap OID: {oid_str} = {value_str}")

            # Store raw values for debugging
            if event.raw_oid is None:
                event.raw_oid = oid_str
                event.raw_value = value_str

            # Check for linkUp/linkDown (generic SNMP)
            if '1.3.6.1.6.3.1.1.5.3' in oid_str:
                event.event_type = 'offline'
            elif '1.3.6.1.6.3.1.1.5.4' in oid_str:
                event.event_type = 'online'

            # VSOL specific OIDs - look for ONU status changes
            # OID pattern: 1.3.6.1.4.1.37950.1.1.5.12.2.1.1.2.X.Y where X=PON, Y=ONU
            if '37950' in oid_str:
                # Try to extract PON port and ONU ID from OID
                # Pattern varies by VSOL firmware version
                match = re.search(r'\.(\d+)\.(\d+)$', oid_str)
                if match:
                    event.pon_port = int(match.group(1))
                    event.onu_id = int(match.group(2))

                # Check value for status
                value_lower = value_str.lower()
                if 'offline' in value_lower or 'down' in value_lower or value_str == '0':
                    event.event_type = 'offline'
                elif 'online' in value_lower or 'up' in value_lower or value_str == '1':
                    event.event_type = 'online'

            # Try to extract MAC address if present
            mac_match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}', value_str)
            if mac_match:
                event.mac_address = mac_match.group(0).upper().replace('-', ':')

        return event

    async def start(self):
        """Start the SNMP trap receiver"""
        try:
            from pysnmp.carrier.asyncio.dgram import udp
            from pysnmp.entity import engine, config
            from pysnmp.entity.rfc3413 import ntfrcv
            from pysnmp.proto.api import v2c

            # Create SNMP engine
            snmp_engine = engine.SnmpEngine()

            # Transport setup - listen on UDP port 162
            config.addTransport(
                snmp_engine,
                udp.domainName,
                udp.UdpTransport().openServerMode((self.bind_address, self.port))
            )

            # SNMPv1/v2c community setup
            config.addV1System(snmp_engine, 'my-area', self.community)

            # Callback for trap reception
            def trap_callback(snmp_engine, state_reference, context_engine_id,
                            context_name, var_binds, cb_ctx):
                try:
                    # Get source address from transport
                    transport_dispatcher = snmp_engine.transportDispatcher
                    transport_domain, transport_address = transport_dispatcher.getTransportInfo(state_reference)
                    source_ip = transport_address[0] if transport_address else 'unknown'

                    logger.info(f"SNMP Trap received from {source_ip}")

                    # Parse the trap
                    event = self.parse_trap(source_ip, var_binds)

                    logger.info(f"Trap event: {event.event_type} from {source_ip}, "
                               f"PON:{event.pon_port}, ONU:{event.onu_id}, MAC:{event.mac_address}")

                    # Call the callback if set
                    if self.callback:
                        # Run callback in asyncio context
                        asyncio.create_task(self._async_callback(event))

                except Exception as e:
                    logger.error(f"Error processing trap: {e}")

            # Register trap receiver
            ntfrcv.NotificationReceiver(snmp_engine, trap_callback)

            self.running = True
            logger.info(f"SNMP Trap receiver started on {self.bind_address}:{self.port}")

            # Run the dispatcher
            snmp_engine.transportDispatcher.jobStarted(1)

            try:
                while self.running:
                    snmp_engine.transportDispatcher.runDispatcher(timeout=1.0)
            except Exception:
                snmp_engine.transportDispatcher.closeDispatcher()
                raise

        except ImportError as e:
            logger.error(f"pysnmp not properly installed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to start trap receiver: {e}")
            raise

    async def _async_callback(self, event: TrapEvent):
        """Wrapper to call callback asynchronously"""
        if self.callback:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(event)
            else:
                self.callback(event)

    def stop(self):
        """Stop the trap receiver"""
        self.running = False
        logger.info("SNMP Trap receiver stopped")


# Alternative simpler trap receiver using raw UDP socket
class SimpleTrapReceiver:
    """
    Simple UDP-based trap receiver that captures raw trap packets.
    More reliable than pysnmp for basic trap detection.
    """

    def __init__(self,
                 bind_address: str = '0.0.0.0',
                 port: int = 162):
        self.bind_address = bind_address
        self.port = port
        self.running = False
        self.callback: Optional[Callable[[TrapEvent], None]] = None
        self._transport = None
        self._protocol = None

    def set_callback(self, callback: Callable[[TrapEvent], None]):
        """Set callback function to be called when trap is received"""
        self.callback = callback

    async def start(self):
        """Start listening for traps"""

        class TrapProtocol(asyncio.DatagramProtocol):
            def __init__(self, receiver):
                self.receiver = receiver

            def datagram_received(self, data, addr):
                source_ip = addr[0]
                logger.info(f"Trap packet received from {source_ip}, {len(data)} bytes")

                # Parse basic SNMP trap
                event = self.receiver._parse_raw_trap(data, source_ip)

                if self.receiver.callback and event:
                    asyncio.create_task(self.receiver._async_callback(event))

        loop = asyncio.get_event_loop()

        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: TrapProtocol(self),
            local_addr=(self.bind_address, self.port)
        )

        self.running = True
        logger.info(f"Simple SNMP Trap receiver started on {self.bind_address}:{self.port}")

    def _parse_raw_trap(self, data: bytes, source_ip: str) -> Optional[TrapEvent]:
        """Parse raw SNMP trap packet"""
        try:
            from pysnmp.proto import api
            from pyasn1.codec.ber import decoder

            # Try to decode as SNMPv2c
            msg_version = int(api.decodeMessageVersion(data))

            if msg_version in (api.protoModules[api.protoVersion1].apiMessage.version,
                              api.protoModules[api.protoVersion2c].apiMessage.version):

                proto_module = api.protoModules[msg_version]
                req_msg, _ = decoder.decode(data, asn1Spec=proto_module.Message())

                # Get PDU
                pdu = proto_module.apiMessage.getPDU(req_msg)

                # Extract var binds
                var_binds = []
                for oid, val in proto_module.apiPDU.getVarBinds(pdu):
                    var_binds.append((str(oid), str(val)))

                # Create event
                event = TrapEvent(
                    timestamp=datetime.utcnow(),
                    source_ip=source_ip,
                    event_type='unknown'
                )

                # Parse var binds
                for oid_str, value_str in var_binds:
                    logger.debug(f"Trap OID: {oid_str} = {value_str}")

                    if event.raw_oid is None:
                        event.raw_oid = oid_str
                        event.raw_value = value_str

                    # Check for standard link traps
                    if '1.3.6.1.6.3.1.1.5.3' in oid_str or 'linkDown' in oid_str:
                        event.event_type = 'offline'
                    elif '1.3.6.1.6.3.1.1.5.4' in oid_str or 'linkUp' in oid_str:
                        event.event_type = 'online'

                    # VSOL enterprise OID
                    if '37950' in oid_str:
                        match = re.search(r'\.(\d+)\.(\d+)$', oid_str)
                        if match:
                            event.pon_port = int(match.group(1))
                            event.onu_id = int(match.group(2))

                    # MAC address extraction
                    mac_match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}', value_str)
                    if mac_match:
                        event.mac_address = mac_match.group(0).upper().replace('-', ':')

                return event

        except Exception as e:
            logger.error(f"Failed to parse trap: {e}")
            return TrapEvent(
                timestamp=datetime.utcnow(),
                source_ip=source_ip,
                event_type='unknown',
                description=f"Parse error: {e}"
            )

    async def _async_callback(self, event: TrapEvent):
        """Wrapper to call callback asynchronously"""
        if self.callback:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(event)
            else:
                self.callback(event)

    async def stop(self):
        """Stop the trap receiver"""
        self.running = False
        if self._transport:
            self._transport.close()
        logger.info("Simple SNMP Trap receiver stopped")


# Test function
async def test_trap_receiver():
    """Test the trap receiver"""
    def on_trap(event: TrapEvent):
        print(f"TRAP: {event.event_type} from {event.source_ip}")
        print(f"  PON: {event.pon_port}, ONU: {event.onu_id}, MAC: {event.mac_address}")
        print(f"  Raw: {event.raw_oid} = {event.raw_value}")

    receiver = SimpleTrapReceiver(port=1620)  # Use non-privileged port for testing
    receiver.set_callback(on_trap)

    print("Starting trap receiver on port 1620...")
    await receiver.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await receiver.stop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(test_trap_receiver())
