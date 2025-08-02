import socket
import threading
import time
import uuid
import sys

# === Configuration ===
PORT = 50999
BROADCAST_ADDR = '192.168.68.255'
USERNAME = sys.argv[1] if len(sys.argv) >= 2 else "Anonymous"

# === State ===
peers = {}            # username@ip -> (ip, port)
followers = {}        # who follows me
following = {}        # who I follow
posts_list = []       # (timestamp, sender, message)
received_ids = set()  # to prevent duplicates

# === Sockets ===
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except AttributeError:
    pass
sock.bind(('', PORT))

# === Utilities ===
def create_broadcast_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass
    s.bind(('', 0))
    return s

def get_my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except:
        return "127.0.0.1"
    finally:
        s.close()

MY_IP = get_my_ip()
MY_ID = f"{USERNAME}@{MY_IP}"

def generate_kv_message(fields: dict) -> str:
    return ''.join(f"{k.upper()}: {v}\n" for k, v in fields.items()) + "\n"

def parse_kv_message(data: str) -> dict:
    lines = data.strip().splitlines()
    result = {}
    for line in lines:
        if ": " in line:
            key, val = line.split(": ", 1)
            result[key.strip().lower()] = val.strip()
    return result

def send_message(fields, addr):
    msg = generate_kv_message(fields)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if addr[0] == BROADCAST_ADDR:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    s.sendto(msg.encode("utf-8"), addr)
    s.close()

# === Discovery ===
def broadcast_hello():
    msg = {
        "type": "HELLO",
        "user_id": MY_ID,
    }
    send_message(msg, (BROADCAST_ADDR, PORT))

# === Listener ===
def handle_message(raw, addr):
    try:
        data = parse_kv_message(raw.decode("utf-8"))
        mtype = data.get("type", "").upper()
    except:
        return

    if mtype == "HELLO":
        user = data.get("user_id")
        if user and user != MY_ID:
            peers[user] = (addr[0], PORT)
            print(f"[Discovery] New peer discovered: {user}")

    elif mtype == "FOLLOW":
        follower = data.get("user_id")
        if follower and follower != MY_ID:
            followers[follower] = addr
            print(f"[Follow] {follower} is now following you")

            # Respond with FOLLOW_NOTIFY
            notify_msg = {
                "type": "FOLLOW_NOTIFY",
                "user_id": MY_ID
            }
            send_message(notify_msg, addr)

    elif mtype == "FOLLOW_NOTIFY":
        follower = data.get("user_id")
        if follower and follower != MY_ID:
            followers[follower] = addr  # Add the follower if not already added
            print(f"[Follow] {follower} is now following you")

    elif mtype == "POST":
        sender = data.get("user_id")
        content = data.get("content")
        message_id = data.get("message_id")

        if not sender or not content or not message_id:
            return

        if sender in following:
            if message_id in received_ids:
                return
            received_ids.add(message_id)
            posts_list.append((time.time(), sender, content))
            print(f"[New Post] From {sender}: {content}")

def listener():
    while True:
        msg, addr = sock.recvfrom(4096)
        handle_message(msg, addr)

# === Follow ===
def follow_user(target):
    if target in peers:
        ip, _ = peers[target]
        msg = {
            "type": "FOLLOW",
            "user_id": MY_ID
        }
        send_message(msg, (ip, PORT))
        following[target] = (ip, PORT)
        print(f"You are now following {target}")
    else:
        print("User not found. Run 'hello' first.")

# === Post ===
def send_post(content):
    if not followers:
        print("[Post] No followers to send to.")
        return

    message_id = uuid.uuid4().hex[:16]
    msg = {
        "type": "POST",
        "user_id": MY_ID,
        "content": content,
        "message_id": message_id
    }

    for _, addr in followers.items():
        send_message(msg, addr)
    print("[Post] Message broadcasted to followers.")

# === Posts ===
def show_posts():
    print("\n--- Public Posts (from users you follow) ---")
    for i, (ts, sender, msg) in enumerate(posts_list, 1):
        print(f"{i}. From {sender}: {msg}")
    print("--------------------------------------------")

# === Following List ===
def show_following():
    print("\n--- You are following ---")
    if not following:
        print("Nobody yet.")
    else:
        for user in following:
            print(f"- {user}")
    print("--------------------------")

# === Main Loop ===
def prompt():
    print(f"\n--- LSNP Peer [{MY_ID}] ---")
    print("Commands:")
    print("  hello                     - Discover peers")
    print("  peers                     - List discovered peers")
    print("  follow <user@ip>         - Follow a peer")
    print("  following                - List people you're following")
    print("  post <message>           - Send a public post")
    print("  posts                    - Show received posts")
    print("  exit                     - Quit\n")

    while True:
        try:
            cmd = input("> ").strip()
            if cmd == "":
                continue
            elif cmd == "hello":
                broadcast_hello()
            elif cmd == "peers":
                for p in peers:
                    print("  " + p)
            elif cmd == "following":
                show_following()
            elif cmd.startswith("follow "):
                follow_user(cmd.split(" ", 1)[1])
            elif cmd.startswith("post "):
                send_post(cmd.split(" ", 1)[1])
            elif cmd == "posts":
                show_posts()
            elif cmd == "exit":
                print("Goodbye.")
                break
            else:
                print("Unknown command.")
        except KeyboardInterrupt:
            break

# === Entry Point ===
if __name__ == "__main__":
    threading.Thread(target=listener, daemon=True).start()
    prompt()
