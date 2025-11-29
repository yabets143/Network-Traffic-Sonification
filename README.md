# Network-Traffic-Sonification

Network Traffic Sonification
A system that converts real-time network traffic data into an audible soundscape. Different types of traffic (HTTP, SSH, ICMP) and traffic attributes (source/destination IP, packet size) are mapped to distinct sonic elements (pitch, instrument, rhythm).

## 🎯 Project Overview

This project transforms network activity into an immersive audio experience, allowing you to "hear" your network traffic. By mapping packet characteristics to sound parameters, you can monitor network behavior through audio cues rather than visual interfaces.

## Core Features

- Real-time packet capture from your network interface
- Customizable sound mappings for different protocols and packet attributes
- Stereo panning based on source IP addresses
- Dynamic volume control based on traffic intensity
- Aggregate sonification modes to prevent audio clutter
- Configurable parameters via command-line interface
- **Auto-detection of network interfaces** (new!)

## 🚀 Quick Start

Clone the repository

```bash
git clone <repository-url>
cd Network-Traffic-Sonification
```

Create a virtual environment (Recommended)

```bash
# Windows
python -m venv env
env\Scripts\activate

# Linux/Mac
python -m venv env
source env/bin/activate
```

Prerequisites

### Install required packages

```bash
pip install -r requirements.txt
```

### Basic Usage

The tool now **auto-detects** your network interface. For Windows users, if auto-detection fails, you can manually specify your interface GUID.

To find your specific Wi-Fi interface GUID on Windows:
```powershell
netsh wlan show interfaces
```

Basic Usage:
```bash
# Start monitoring with default settings (requires Admin/root privileges)
python sonify.py

# Specify a network interface manually
python sonify.py -i "eth0"  # Linux
python sonify.py -i "{YOUR-INTERFACE-GUID}"  # Windows
```

```bash
# Monitor only specific traffic
python sonify.py -f "tcp port 80"      # HTTP only
python sonify.py -f "icmp"             # Ping traffic only
python sonify.py -f "udp port 53"      # DNS queries only

# Limit capture to specific number of packets
python sonify.py -c 100                # Capture 100 packets

# Quiet mode (sound only, minimal output)
python sonify.py -v quiet
```

## 📖 Documentation

For a comprehensive analysis of the project including identified issues, scalability concerns, and product-readiness assessment, see [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md).


