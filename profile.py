import socket
import threading
import time
import uuid
import sys

# === Configuration ===
PORT = 50999
BROADCAST_ADDR = '255.255.255.255'
USERNAME = sys.argv[1] if len(sys.argv) >= 2 else "Anonymous"
# --- ADDED: Constant for the broadcast interval ---
PROFILE_BROADCAST_INTERVAL = 300 # 5 mins

try:
    MY_IP = socket.gethostbyname(socket.gethostname())
except socket.gaierror:
    MY_IP = "127.0.0.1"
MY_ID = f"{USERNAME}@{MY_IP}"

# === State ===
peers = {}
followers = set()
known_profiles = {}
# --- MODIFIED: Renamed 'status' to 'bio' for consistency with your commands ---
my_profile_data = {
    "name": USERNAME,
    "bio": "Just another peer on LSNP."
}

# === Tokens ===
def generate_token(user_id, ttl=3600, scope="broadcast"):
    timestamp = int(time.time())
    return f"{user_id}|{timestamp + ttl}|{scope}"

# === Functions ===
def send_message(data, addr):
    msg = '\n'.join(f"{k.upper()}: {v}" for k, v in data.items()) + "\n\n"
    # Using a 'with' statement is safer for sockets in threads
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        if addr[0].endswith('.255') or addr[0] == '255.255.255.255':
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(msg.encode('utf-8'), addr)

def parse_message(raw_msg):
    data = {}
    for line in raw_msg.strip().split('\n'):
        if ': ' in line:
            key, value = line.split(': ', 1)
            data[key.lower()] = value
    return data

# --- MODIFIED: Rewritten for consistency ---
def broadcast_follow(target_id):
    msg = {
        "type": "FOLLOW",
        "user_id": MY_ID, # Use full ID
        "target_id": target_id,
        "message_id": str(uuid.uuid4().hex),
        "token": generate_token(MY_ID, scope="follow") # Use full ID
    }
    send_message(msg, (BROADCAST_ADDR, PORT))
    print(f"[FOLLOW] Sent follow request for {target_id}.")

def broadcast_profile():
    profile_msg = {
        "type": "PROFILE",
        "user_id": MY_ID,
        "name": my_profile_data["name"],
        "bio": my_profile_data["bio"],
        "timestamp": str(int(time.time()))
    }
    send_message(profile_msg, (BROADCAST_ADDR, PORT))

# --- MODIFIED: Corrected to use MY_ID for token ---
def broadcast_post(content):
    post_msg = {
        "type": "POST",
        "user_id": MY_ID,
        "message_id": str(uuid.uuid4().hex),
        "token": generate_token(MY_ID, scope="post"), # Use full ID
        "ttl": "3600",
        "content": content
    }
    send_message(post_msg, (BROADCAST_ADDR, PORT))
    print("[POST] Broadcasted message.")

# --- "ignore self" logic ---
def handle_message(data, addr):
    sender_id = data.get("user_id")

    # This check is critical to prevent processing your own messages
    if sender_id == MY_ID:
        return

    mtype = data.get("type", "").upper()

    if mtype == "FOLLOW":
        target_id = data.get("target_id")
        if target_id == MY_ID and sender_id:
            followers.add(sender_id)
            peers[sender_id] = (addr[0], PORT)
            print(f"\n[FOLLOW] {sender_id} is now following you.")
            notify = { "type": "FOLLOW_NOTIFY", "user_id": MY_ID, "target_id": sender_id }
            send_message(notify, (addr[0], PORT))

    elif mtype == "FOLLOW_NOTIFY":
        target_id = data.get("target_id")
        if target_id == MY_ID:
            print(f"\n[NOTIFY] {sender_id} acknowledged your follow.")

    elif mtype == "PROFILE":
        name = data.get("name", "")
        bio = data.get("bio", "") 
        timestamp = data.get("timestamp", "")
        if sender_id:
            known_profiles[sender_id] = (name, bio, timestamp)
            peers[sender_id] = (addr[0], PORT)
            print(f"\n[PROFILE] {sender_id}: {name} | {bio}")

    elif mtype == "POST":
        content = data.get("content", "")
        if sender_id in peers:
            name = known_profiles.get(sender_id, [sender_id])[0]
            print(f"\n[POST from {name}]: {content}")

    # Reprint the prompt cleanly after handling a message
    print(f"> ", end="", flush=True)

# === Listener Thread ===
def listen():
    while True:
        try:
            # Main listening socket is now only used here
            raw, addr = sock.recvfrom(65535)
            message = raw.decode('utf-8')
            data = parse_message(message)
            handle_message(data, addr)
        except Exception as e:
            print(f"\nError handling message: {e}")

# --- The periodic broadcaster function ---
def periodic_broadcaster():
    """This function runs in a separate thread to send profile updates."""
    while True:
        # Wait for the interval THEN broadcast, so we don't spam on startup
        time.sleep(PROFILE_BROADCAST_INTERVAL)
        print("\n[Auto-Profile] Broadcasting profile...")
        broadcast_profile()
        print(f"> ", end="", flush=True)
# ---------------------------------------------

# === Start UDP Socket ===
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except AttributeError:
    pass
sock.bind(('', PORT))

# === Start Threads ===
threading.Thread(target=listen, daemon=True).start()
# --- Starting the new periodic broadcaster thread ---
threading.Thread(target=periodic_broadcaster, daemon=True).start()

# Announce our presence once on startup immediately
print("Broadcasting initial profile...")
time.sleep(0.5)
broadcast_profile()

# === CLI Loop ===
print(f"Welcome to LSNP! Your ID is {MY_ID}. Type 'help' for commands.")
while True:
    cmd = input("> ").strip()
    
    if cmd == "help":
        print("Available commands:")
        print("  profile set <name|bio> <value> - Update your profile name or bio")
        print("  follow <user_id>          - Follow a user")
        print("  post <message>            - Broadcast a post")
        print("  peers                     - List known peers")
        print("  followers                 - List your followers")
        print("  exit                      - Quit")

    elif cmd.startswith("follow "):
        _, user = cmd.split(" ", 1)
        broadcast_follow(user.strip())

    elif cmd.startswith("profile set "):
    # We split by space into exactly 4 parts for a valid command
        parts = cmd.split(" ", 3)
        if len(parts) < 4:
            print("Usage: profile set <name|bio> <new value>")
        else:
            # parts[0] is "profile", parts[1] is "set"
            field = parts[2].lower()
            value = parts[3]
            if field == "name":
                my_profile_data["name"] = value
                print(f"Display name updated to: {value}")
                broadcast_profile() # Immediately announce the change
            elif field == "bio":
                my_profile_data["bio"] = value
                print(f"Bio updated to: {value}")
                broadcast_profile() # Immediately announce the change
            else:
                print("Invalid field. Can only set 'name' or 'bio'.")

    elif cmd.startswith("post "):
        _, content = cmd.split(" ", 1)
        broadcast_post(content.strip())

    # --- MODIFIED: Improved output to show full profile ---
    elif cmd == "peers":
        if not peers:
            print("No peers known.")
        else:
            print("--- Known Peers ---")
            for uid, (ip, port) in peers.items():
                name, bio, _ = known_profiles.get(uid, (uid, "N/A", 0))
                print(f"- {name} ({uid}) | Bio: {bio}")

    elif cmd == "followers":
        if not followers:
            print("You have no followers yet.")
        else:
            print("--- Your Followers ---")
            for f_id in followers:
                print(f"- {f_id}")

    elif cmd == "exit":
        print("Goodbye!")
        break
    
    elif cmd == "":
        continue

    else:
        print("Unknown command. Type 'help' for list.")