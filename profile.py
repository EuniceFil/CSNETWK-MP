import socket
import threading
import time
import uuid
import sys

# === Configuration ===
PORT = 50999
BROADCAST_ADDR = '255.255.255.255'  # Change if needed
USERNAME = sys.argv[1] if len(sys.argv) >= 2 else "Anonymous"
MY_ID = f"{USERNAME}@{socket.gethostbyname(socket.gethostname())}"

# === State ===
peers = {}           # user_id -> (ip, port)
followers = set()    # user_id
known_profiles = {}  # user_id -> (name, bio, timestamp)

# === Tokens ===
def generate_token(user_id, ttl=3600, scope="broadcast"):
    timestamp = int(time.time())
    return f"{user_id}|{timestamp + ttl}|{scope}"

# === Functions ===

def send_message(data, addr):
    msg = '\n'.join(f"{k.upper()}: {v}" for k, v in data.items()) + "\n\n"
    if addr[0].endswith('.255') or addr[0] == '255.255.255.255':
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(msg.encode('utf-8'), addr)

def parse_message(raw_msg):
    data = {}
    for line in raw_msg.strip().split('\n'):
        if ': ' in line:
            key, value = line.split(': ', 1)
            data[key.lower()] = value
    return data

def broadcast_hello():
    msg = {
        "type": "HELLO",
        "user_id": MY_ID,
    }
    send_message(msg, (BROADCAST_ADDR, PORT))

def broadcast_follow(target_id):
    message_id = str(uuid.uuid4().hex)
    token = generate_token(MY_ID, ttl=3600, scope="follow")

    message = (
        f"TYPE: FOLLOW\n"
        f"USER_ID: {USERNAME}\n"
        f"TARGET_ID: {target_id}\n"
        f"MESSAGE_ID: {message_id}\n"
        f"TOKEN: {token}\n\n"
    )
    sock.sendto(message.encode(), (BROADCAST_ADDR, PORT))
    print(f"[FOLLOW] You are now following {target_id}.")

def broadcast_profile():
    profile_msg = {
        "type": "PROFILE",
        "user_id": MY_ID,
        "name": USERNAME,
        "bio": "Just another peer on LSNP.",
        "timestamp": str(int(time.time()))
    }
    send_message(profile_msg, (BROADCAST_ADDR, PORT))

def broadcast_post(content):
    message_id = str(uuid.uuid4().hex)
    ttl = 3600  # Default TTL
    token = generate_token(USERNAME, ttl=ttl, scope="post")
    post_msg = {
        "type": "POST",
        "user_id": MY_ID,
        "message_id": message_id,
        "token": token,
        "ttl": str(ttl),
        "content": content
    }
    send_message(post_msg, (BROADCAST_ADDR, PORT))
    print("[POST] Broadcasted message.")

def handle_message(data, addr):
    mtype = data.get("type", "").upper()
    
    if mtype == "HELLO":
        user = data.get("user_id")
        if user and user != MY_ID:
            peers[user] = (addr[0], PORT)
            print(f"[Discovery] New peer discovered: {user}")
    
    elif mtype == "FOLLOW":
        source_id = data.get("user_id")
        target_id = data.get("target_id")
        if target_id == MY_ID and source_id:
            followers.add(source_id)
            peers[source_id] = (addr[0], PORT)
            print(f"[FOLLOW] {source_id} is now following you.")
            notify = {
                "type": "FOLLOW_NOTIFY",
                "user_id": MY_ID,
                "target_id": source_id
            }
            send_message(notify, (addr[0], PORT))
    
    elif mtype == "FOLLOW_NOTIFY":
        user = data.get("user_id")
        target_id = data.get("target_id")
        if target_id == MY_ID:
            print(f"[NOTIFY] {user} acknowledged your follow.")

    elif mtype == "PROFILE":
        user = data.get("user_id")
        name = data.get("name", "")
        bio = data.get("bio", "")
        timestamp = data.get("timestamp", "")
        
        if user and user != MY_ID:
            known_profiles[user] = (name, bio, timestamp)
            peers[user] = (addr[0], PORT)
            print(f"[PROFILE] {user} - {name} | {bio}")

    elif mtype == "POST":
        user = data.get("user_id")
        content = data.get("content", "")
        if user and user != MY_ID:
            if user in peers:
                print(f"[POST from {user}]: {content}")

# === Listener Thread ===

def listen():
    while True:
        try:
            raw, addr = sock.recvfrom(65535)
            message = raw.decode('utf-8')
            data = parse_message(message)
            handle_message(data, addr)
        except Exception as e:
            print("Error handling message:", e)

# === Start UDP Socket ===
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except AttributeError:
    pass
sock.bind(('', PORT))

# === Start Listener Thread ===

threading.Thread(target=listen, daemon=True).start()

# === CLI Loop ===

print("Welcome to LSNP! Type 'help' to see commands.")
while True:
    cmd = input("> ").strip()
    
    if cmd == "help":
        print("Available commands:")
        print("  hello                     - Send HELLO broadcast")
        print("  follow <user_id>          - Follow a user")
        print("  profile                   - Broadcast your profile")
        print("  post <message>            - Broadcast a post")
        print("  peers                     - List known peers")
        print("  followers                 - List your followers")
        print("  exit                      - Quit")
    
    elif cmd == "hello":
        broadcast_hello()
    
    elif cmd.startswith("follow "):
        _, user = cmd.split(" ", 1)
        broadcast_follow(user.strip())
    
    elif cmd == "profile":
        broadcast_profile()
    
    elif cmd.startswith("post "):
        _, content = cmd.split(" ", 1)
        broadcast_post(content.strip())

    elif cmd == "peers":
        if not peers:
            print("No peers known.")
        for uid, (ip, port) in peers.items():
            print(f"{uid} @ {ip}:{port}")
    
    elif cmd == "followers":
        if not followers:
            print("No followers yet.")
        for f in followers:
            print(f)
    
    elif cmd == "exit":
        print("Goodbye!")
        break

    else:
        print("Unknown command. Type 'help' for list.")
