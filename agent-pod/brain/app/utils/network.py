"""
Network discovery utilities for Kuberbolt agents.
Automatically discovers the local LAN IP address on the current WiFi/network interface.
"""
from __future__ import annotations

import os
import socket


def get_local_ip() -> str:
    """Get this machine's LAN IP (works on same WiFi network).
    
    Can be overridden by SELLER_HOST, AGENT_HOST, or PUBLIC_HOST environment variables.
    """
    env_override = os.getenv("SELLER_HOST") or os.getenv("AGENT_HOST") or os.getenv("PUBLIC_HOST")
    if env_override:
        return env_override

    # Create a UDP socket to determine outbound route without sending actual packets
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        s.close()
