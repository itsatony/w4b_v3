import os
import time
import subprocess
import curses
from datetime import datetime, timedelta

WG_DIR = "/etc/wireguard"
PEER_MAP = os.path.join(WG_DIR, "peer_mapping.txt")

def get_peer_mapping():
    peer_mapping = {}
    if os.path.exists(PEER_MAP):
        with open(PEER_MAP, 'r') as f:
            for line in f:
                public_key, client_name = line.strip().split()
                peer_mapping[public_key] = client_name
    return peer_mapping

def get_wireguard_status():
    result = subprocess.run(['wg', 'show'], capture_output=True, text=True)
    return result.stdout

def parse_wireguard_status(status, peer_mapping):
    peers = []
    current_peer = None
    for line in status.splitlines():
        if line.startswith('peer:'):
            if current_peer:
                peers.append(current_peer)
            current_peer = {'public_key': line.split()[1]}
        elif line.startswith('  endpoint:'):
            current_peer['endpoint'] = line.split()[1]
        elif line.startswith('  allowed ips:'):
            current_peer['allowed_ips'] = line.split()[2]
        elif line.startswith('  latest handshake:'):
            handshake_time = ' '.join(line.split()[2:])
            current_peer['latest_handshake'] = handshake_time
            try:
                current_peer['connected_since'] = datetime.strptime(handshake_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                current_peer['connected_since'] = 'N/A'
        elif line.startswith('  transfer:'):
            current_peer['transfer'] = line.split()[1] + ' ' + line.split()[2]
    if current_peer:
        peers.append(current_peer)
    
    for peer in peers:
        peer['name'] = peer_mapping.get(peer['public_key'], 'Unknown')
        if isinstance(peer.get('connected_since'), datetime):
            peer['connection_duration'] = str(datetime.now() - peer['connected_since']).split('.')[0]
            peer['connected_since'] = peer['connected_since'].strftime('%Y-%m-%d %H:%M:%S')
        else:
            peer['connection_duration'] = 'N/A'
            peer['connected_since'] = 'N/A'
    
    return peers

def format_time_ago(time_str):
    try:
        time_ago = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        delta = datetime.now() - time_ago
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02} ago"
    except ValueError:
        return time_str

def display_status(stdscr, peers, last_refresh, next_refresh):
    stdscr.clear()
    stdscr.addstr(0, 0, "WireGuard Status Monitor", curses.A_BOLD)
    stdscr.addstr(1, 0, "========================")
    stdscr.addstr(2, 0, f"Last Refresh: {last_refresh} | Next Refresh: {next_refresh} | Press 'r' to refresh, 'q' to quit")
    stdscr.addstr(3, 0, "-" * 120)
    stdscr.addstr(4, 0, f"{'Name':<20} | {'Endpoint':<20} | {'Allowed IPs':<20} | {'Latest Handshake':<20} | {'Transfer':<20} | {'Connected Since':<20} | {'Connection Duration':<20}")
    stdscr.addstr(5, 0, "-" * 120)
    
    for idx, peer in enumerate(peers, start=6):
        latest_handshake = format_time_ago(peer['latest_handshake'])
        stdscr.addstr(idx, 0, f"{peer['name']:<20} | {peer['endpoint']:<20} | {peer['allowed_ips']:<20} | {latest_handshake:<20} | {peer['transfer']:<20} | {peer['connected_since']:<20} | {peer['connection_duration']:<20}")
    
    stdscr.refresh()

def main(stdscr):
    if os.geteuid() != 0:
        print("This script must be run as root. Please use sudo.")
        return
    
    curses.curs_set(0)
    peer_mapping = get_peer_mapping()
    refresh_interval = 5
    
    while True:
        last_refresh = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        next_refresh = (datetime.now() + timedelta(seconds=refresh_interval)).strftime('%Y-%m-%d %H:%M:%S')
        
        status = get_wireguard_status()
        peers = parse_wireguard_status(status, peer_mapping)
        display_status(stdscr, peers, last_refresh, next_refresh)
        
        for _ in range(refresh_interval * 10):
            key = stdscr.getch()
            if key == ord('q'):
                return
            elif key == ord('r'):
                break
            time.sleep(0.1)

if __name__ == "__main__":
    curses.wrapper(main)
