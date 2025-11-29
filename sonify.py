import argparse
import logging
import sys
import threading
import time
import os
import numpy as np
import pygame
from collections import defaultdict, deque
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.layers.l2 import Ether
from scapy.packet import Raw
from scapy.sendrecv import sniff
from scapy.utils import wrpcap
from scapy.arch import get_if_list

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_default_interface():
    """Auto-detect the default network interface."""
    try:
        interfaces = get_if_list()
        if interfaces:
            # Filter out loopback interfaces
            non_loopback = [iface for iface in interfaces
                            if 'lo' not in iface.lower()
                            and 'loopback' not in iface.lower()]
            return non_loopback[0] if non_loopback else interfaces[0]
    except Exception as e:
        logger.warning(f"Could not auto-detect interface: {e}")
    return None


# Auto-detect default interface or use placeholder for manual configuration
DEFAULT_IFACE = get_default_interface() or r"{YOUR-INTERFACE-GUID-HERE}"


class TrafficStatistics:
    def __init__(self, window_size=10):
        self.window_size = window_size
        self.packet_count = 0
        self.protocol_stats = defaultdict(int)
        self.size_stats = defaultdict(int)
        self.recent_packets = deque(maxlen=100)
        self.start_time = time.time()

    def update(self, packet, protocol):
        self.packet_count += 1
        self.protocol_stats[protocol] += 1

        if IP in packet:
            size = len(packet[IP])
            self.size_stats[protocol] += size

        self.recent_packets.append((time.time(), protocol))

    def get_stats(self):
        current_time = time.time()
        elapsed = current_time - self.start_time

        # Calculate packets per second (last 5 seconds)
        recent_packets = [ts for ts, proto in self.recent_packets
                          if current_time - ts <= 5]
        pps = len(recent_packets) / 5 if recent_packets else 0

        return {
            'total_packets': self.packet_count,
            'protocols': dict(self.protocol_stats),
            'pps': pps,
            'elapsed_time': elapsed
        }


class ProtocolIdentifier:
    def __init__(self):
        self.port_protocol_map = {
            # TCP ports
            20: "FTP_DATA", 21: "FTP", 22: "SSH", 23: "TELNET",
            25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3",
            143: "IMAP", 443: "HTTPS", 993: "IMAPS", 995: "POP3S",
            3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
            # UDP ports
            67: "DHCP", 68: "DHCP", 69: "TFTP",
            123: "NTP", 161: "SNMP", 162: "SNMP", 514: "SYSLOG",
            1900: "SSDP", 5353: "mDNS"
        }

    def identify(self, packet):
        """Enhanced protocol identification."""
        if packet.haslayer(Ether):
            if packet[Ether].type == 0x0806:
                return "ARP"
            elif packet[Ether].type == 0x86DD:
                return "IPv6"

        if packet.haslayer(IP):
            ip = packet[IP]

            if packet.haslayer(TCP):
                return self._identify_tcp_protocol(packet)
            elif packet.haslayer(UDP):
                return self._identify_udp_protocol(packet)
            elif packet.haslayer(ICMP):
                return "ICMP"
            elif ip.proto == 2:
                return "IGMP"
            elif ip.proto == 41:
                return "IPv6"
            elif ip.proto == 89:
                return "OSPF"

        return "OTHER"

    def _identify_tcp_protocol(self, packet):
        tcp = packet[TCP]

        # Check common ports first
        if tcp.dport in self.port_protocol_map:
            return self.port_protocol_map[tcp.dport]
        if tcp.sport in self.port_protocol_map:
            return self.port_protocol_map[tcp.sport]

        # HTTP detection by payload
        if packet.haslayer(Raw):
            try:
                payload = packet[Raw].load.decode('utf-8', errors='ignore').upper()
                if any(method in payload for method in
                       ['GET', 'POST', 'PUT', 'DELETE', 'HTTP/']):
                    return "HTTP"
                if 'SSH-' in payload:  # SSH identification
                    return "SSH"
            except (UnicodeDecodeError, AttributeError) as e:
                logger.debug(f"Payload decode error: {e}")

        return "TCP"

    def _identify_udp_protocol(self, packet):
        udp = packet[UDP]

        if udp.dport in self.port_protocol_map:
            return self.port_protocol_map[udp.dport]
        if udp.sport in self.port_protocol_map:
            return self.port_protocol_map[udp.sport]

        return "UDP"


class SoundManager:
    def __init__(self, volume=0.5, max_pps=20):
        # Initialize pygame mixer with better settings
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        self.sample_rate = 44100

        self.volume = volume
        self.max_pps = max_pps
        self.last_sound_time = 0
        self.sound_enabled = True
        self._lock = threading.Lock()  # Thread safety for shared state

        # Protocol to musical note mapping (pleasant frequencies)
        self.protocol_notes = {
            "HTTP": 523.25,    # C5 - Pleasant middle tone
            "HTTPS": 659.25,   # E5 - Higher, brighter tone
            "SSH": 392.00,     # G4 - Warm, lower tone
            "DNS": 783.99,     # G5 - High, attention-grabbing
            "ICMP": 261.63,    # C4 - Low, bass-like tone
            "TCP": 440.00,     # A4 - Standard tuning reference
            "UDP": 587.33,     # D5 - Bright, clear tone
            "ARP": 329.63,     # E4 - Mid-range, mellow tone
            "OTHER": 349.23    # F4 - Fallback tone
        }

        # Different waveform types for variety
        self.waveforms = {
            "HTTP": "sine",       # Smooth, pure tone
            "HTTPS": "sine",      # Smooth, pure tone
            "SSH": "triangle",    # Softer than square
            "DNS": "sine",        # Clean bell-like
            "ICMP": "square",     # Percussive, drum-like
            "TCP": "sine",        # Smooth flow
            "UDP": "sawtooth",    # Buzzing, energetic
            "ARP": "sine",        # Clean, short
            "OTHER": "sine"       # Default
        }

    def generate_wave(self, wave_type, frequency, duration, volume=0.3):
        """Generate different types of waveforms."""
        samples = int(duration * self.sample_rate)
        t = np.linspace(0, duration, samples, False)

        if wave_type == "sine":
            wave = np.sin(2 * np.pi * frequency * t)
        elif wave_type == "square":
            wave = np.sign(np.sin(2 * np.pi * frequency * t)) * 0.7
        elif wave_type == "sawtooth":
            wave = 2 * (t * frequency - np.floor(t * frequency + 0.5))
        elif wave_type == "triangle":
            wave = 2 * np.abs(2 * (t * frequency - np.floor(t * frequency + 0.5))) - 1
        else:
            wave = np.sin(2 * np.pi * frequency * t)  # Default to sine

        return wave

    def apply_envelope(self, wave, duration):
        """Apply ADSR envelope to make sounds more natural."""
        samples = len(wave)

        # ADSR parameters (Attack, Decay, Sustain, Release)
        attack = int(0.1 * samples)   # 10% attack
        decay = int(0.2 * samples)    # 20% decay
        release = int(0.3 * samples)  # 30% release
        sustain = samples - attack - decay - release

        envelope = np.ones(samples)

        # Attack (fade in)
        if attack > 0:
            envelope[:attack] = np.linspace(0, 1, attack)

        # Decay to sustain level
        if decay > 0:
            envelope[attack:attack+decay] = np.linspace(1, 0.7, decay)

        # Sustain (hold)
        if sustain > 0:
            envelope[attack+decay:attack+decay+sustain] = 0.7

        # Release (fade out)
        if release > 0:
            envelope[-release:] = np.linspace(0.7, 0, release)

        return wave * envelope

    def play_protocol_sound(self, protocol, packet_size=None):
        with self._lock:
            if not self.sound_enabled:
                return

            # Rate limiting
            current_time = time.time()
            if current_time - self.last_sound_time < (1.0 / self.max_pps):
                return

            if protocol not in self.protocol_notes:
                protocol = "OTHER"

            frequency = self.protocol_notes[protocol]
            wave_type = self.waveforms[protocol]

            # Modify frequency based on packet size
            if packet_size:
                frequency = frequency + (packet_size / 200)

            # Generate the wave
            duration = 0.3  # Pleasant duration
            wave = self.generate_wave(wave_type, frequency, duration, self.volume)

            # Apply envelope for natural sound
            wave = self.apply_envelope(wave, duration)

            # Convert to audio buffer
            audio = (wave * self.volume * 32767).astype(np.int16)

            # Create stereo sound (2 channels)
            stereo_audio = np.column_stack((audio, audio))

            # Update last sound time before spawning thread
            self.last_sound_time = current_time

        # Play the sound in a separate thread (outside lock to avoid blocking)
        def play_sound():
            try:
                sound = pygame.sndarray.make_sound(stereo_audio)
                sound.play()
            except Exception as e:
                logger.debug(f"Sound error: {e}")

        threading.Thread(target=play_sound, daemon=True).start()

    def toggle_sound(self):
        with self._lock:
            self.sound_enabled = not self.sound_enabled
            return self.sound_enabled


def display_banner():
    print("=" * 60)
    print("           NETWORK TRAFFIC SONIFICATION TOOL")
    print("=" * 60)


def user_input_handler(sound_manager, stats):
    """Handle user input in a separate thread."""
    while True:
        try:
            key = input().lower().strip()
            if key == 'q':
                print("Shutting down...")
                os._exit(0)
            elif key == 's':
                state = sound_manager.toggle_sound()
                status = "ON" if state else "OFF"
                print(f"Sound {status}")
            elif key == 'p':
                current_stats = stats.get_stats()
                print("\n--- Current Statistics ---")
                print(f"Total packets: {current_stats['total_packets']}")
                print(f"Packets/sec: {current_stats['pps']:.1f}")
                print("Protocol distribution:")
                for proto, count in current_stats['protocols'].items():
                    total = current_stats['total_packets']
                    percentage = (count / total * 100) if total > 0 else 0
                    print(f"  {proto:8}: {count:6} ({percentage:5.1f}%)")
                print("---------------------------\n")
        except (EOFError, KeyboardInterrupt):
            break


def packet_handler(pkt, protocol_identifier, sound_manager, stats, verbose=True):
    """Enhanced packet handler with better organization."""
    # Identify protocol
    protocol = protocol_identifier.identify(pkt)

    # Update statistics
    stats.update(pkt, protocol)

    # Get packet size for sound modulation
    packet_size = len(pkt) if hasattr(pkt, '__len__') else 0

    if verbose:
        # Enhanced output formatting
        if IP in pkt:
            ip_src = pkt[IP].src
            ip_dst = pkt[IP].dst
            print(f"{protocol:8} {ip_src:15} -> {ip_dst:15} Size: {packet_size:4} bytes")
        else:
            print(f"{protocol:8} {pkt.summary()}")

    # Play sound based on protocol
    sound_manager.play_protocol_sound(protocol, packet_size)


def main():
    parser = argparse.ArgumentParser(
        description="Network Traffic Sonification Tool - Convert network traffic to sound",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f "tcp"                    # Only sniff TCP traffic on default interface
  %(prog)s -c 100                      # Capture 100 packets
  %(prog)s -l                          # List available interfaces
  %(prog)s -v quiet                    # Quiet mode (no packet output)
  %(prog)s -i "Ethernet"               # Use specific interface name
        """
    )

    parser.add_argument("-i", "--iface", default=DEFAULT_IFACE,
                        help=f"Interface to sniff (default: {DEFAULT_IFACE})")
    parser.add_argument("-c", "--count", type=int, default=0,
                        help="Number of packets to capture (0 = unlimited)")
    parser.add_argument("-w", "--write", help="Path to write pcap file")
    parser.add_argument("-l", "--list", action="store_true",
                        help="List available interfaces and exit")
    parser.add_argument("-f", "--filter", default="",
                        help="BPF filter (tcp, port 80, host 1.2.3.4, etc.)")
    parser.add_argument("-v", "--verbose", choices=['verbose', 'quiet', 'stats'],
                        default='verbose', help="Output verbosity level")
    parser.add_argument("--max-pps", type=int, default=20,
                        help="Maximum packets per second to sonify")
    parser.add_argument("--volume", type=float, default=0.5,
                        help="Sound volume (0.0 to 1.0)")

    args = parser.parse_args()

    if args.list:
        print(f"\nDefault interface: {DEFAULT_IFACE}")
        sys.exit(0)

    # Initialize components
    protocol_identifier = ProtocolIdentifier()
    sound_manager = SoundManager(volume=args.volume, max_pps=args.max_pps)
    stats = TrafficStatistics()

    # Display startup information
    display_banner()
    print(f"Starting sniff on interface: {args.iface}")
    if args.iface == DEFAULT_IFACE:
        print("Using your predefined Wi-Fi interface")
    print(f"Filter: '{args.filter}' | Max PPS: {args.max_pps}")
    print("Press 's' to toggle sound, 'p' for stats, 'q' to quit\n")

    # Start user input handler in separate thread
    input_thread = threading.Thread(target=user_input_handler,
                                    args=(sound_manager, stats),
                                    daemon=True)
    input_thread.start()

    # Configure packet handler based on verbosity
    verbose = args.verbose in ['verbose', 'stats']

    def handle_packet(pkt):
        """Wrapper function for packet handling."""
        packet_handler(pkt, protocol_identifier, sound_manager, stats, verbose)

    try:
        # Start sniffing
        print("Capturing packets... (Ctrl+C to stop)")
        packets = sniff(
            iface=args.iface,
            prn=handle_packet,
            count=args.count or 0,
            filter=args.filter,
            store=bool(args.write)
        )

        # Save packets if requested
        if args.write and packets:
            wrpcap(args.write, packets)
            print(f"\nCaptured {len(packets)} packets to {args.write}")

    except PermissionError:
        logger.error("Permission denied. Run as Administrator/root.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCapture interrupted by user.")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    # Final statistics
    if stats.packet_count > 0:
        final_stats = stats.get_stats()
        print("\n" + "=" * 50)
        print("CAPTURE SUMMARY")
        print("=" * 50)
        print(f"Duration: {final_stats['elapsed_time']:.1f} seconds")
        print(f"Total packets: {final_stats['total_packets']}")
        if final_stats['elapsed_time'] > 0:
            avg_pps = final_stats['total_packets'] / final_stats['elapsed_time']
            print(f"Average PPS: {avg_pps:.1f}")
        print("\nProtocol breakdown:")
        sorted_protos = sorted(final_stats['protocols'].items(),
                               key=lambda x: x[1], reverse=True)
        for proto, count in sorted_protos:
            percentage = (count / final_stats['total_packets']) * 100
            print(f"  {proto:8}: {count:6} ({percentage:5.1f}%)")
    else:
        print("\nNo packets captured. Check your interface and filter settings.")


if __name__ == "__main__":
    main()
