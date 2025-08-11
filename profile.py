import socket
import threading
import time
import uuid
import sys
import os
import base64
import mimetypes

# === Configuration ===
PORT = 50999
BROADCAST_ADDR = '255.255.255.255'
# --- Constant for the broadcast interval ---
PROFILE_BROADCAST_INTERVAL = 300 # 1 min

# --- Check for --verbose flag ---
VERBOSE = "--verbose" in sys.argv
# We need to filter it out so it doesn't become the username
if VERBOSE:
    sys.argv.remove("--verbose")
# ------------------------------------
USERNAME = sys.argv[1] if len(sys.argv) >= 2 else "Anonymous"

try:
    MY_IP = socket.gethostbyname(socket.gethostname())
except socket.gaierror:
    MY_IP = "127.0.0.1"
MY_ID = f"{USERNAME}@{MY_IP}"

# === State ===
peers = {}
followers = set()
following = set()
known_profiles = {}
posts_list = []
my_posts = []
my_profile_data = {
    "name": USERNAME,
    "bio": "Just another peer on LSNP."
}
active_games = {} # Stores game instances by GAMEID
game_id_counter = 0
dm_history = {}
pending_acks = {}
revoked_tokens = set()
my_groups = {}
MY_AVATAR_DATA = None
MY_AVATAR_TYPE = None
peer_avatars = {}
incoming_avatar_chunks = {}

# === File transfer state ===
# Offers received but not yet accepted: fileid -> metadata
pending_file_offers = {}
# Accepted offers we are expecting chunks for: fileid -> {'filename', 'filesize', 'filetype', 'total_chunks', 'chunks': {idx: data}, 'from'}
incoming_transfers = {}
# Outgoing transfer records for bookkeeping if needed: fileid -> metadata
outgoing_transfers = {}

# Max chunk size in bytes (raw bytes before base64). Choose a value that keeps UDP packets reasonably sized.
MAX_CHUNK_SIZE = 4096

class TicTacToeGame:
    def __init__(self, game_id, opponent_id, my_symbol, opponent_symbol, is_my_turn):
        self.game_id = game_id
        self.opponent_id = opponent_id
        self.my_symbol = my_symbol
        self.opponent_symbol = opponent_symbol
        self.board = [' ' for _ in range(9)]
        self.is_my_turn = is_my_turn
        self.turn = 1

    def display_board(self):
        print(f"\n--- Game {self.game_id} against {self.opponent_id} ---")
        print(f" {self.board[0]} | {self.board[1]} | {self.board[2]} ")
        print("---+---+---")
        print(f" {self.board[3]} | {self.board[4]} | {self.board[5]} ")
        print("---+---+---")
        print(f" {self.board[6]} | {self.board[7]} | {self.board[8]} ")
        print(f"Your symbol: {self.my_symbol}")
        print(f"Turn: {self.turn}")
        if self.is_my_turn:
            print("It's your turn.")
        else:
            print(f"Waiting for {self.opponent_id}'s move...")

    def check_winner(self):
        lines = [
            (0,1,2), (3,4,5), (6,7,8),
            (0,3,6), (1,4,7), (2,5,8),
            (0,4,8), (2,4,6)
        ]
        for a, b, c in lines:
            if self.board[a] == self.board[b] == self.board[c] != ' ':
                return self.board[a], (a, b, c)
        if ' ' not in self.board:
            return "DRAW", None
        return None, None

    def make_move(self, pos, symbol):
        if self.board[pos] == ' ':
            self.board[pos] = symbol
            self.turn += 1
            return True
        return False

# === Tokens ===
def generate_token(user_id, ttl=3600, scope="broadcast"):
    timestamp = int(time.time())
    return f"{user_id}|{timestamp + ttl}|{scope}"

def validate_token(token, expected_scope, sender_id):
    """Validates a token with detailed verbose logging."""
    try:
        token_user, token_exp, token_scope = token.split('|')
        
        if token_user != sender_id:
            log("TOKEN !", f"FAIL: Owner ({token_user}) != Sender ({sender_id})")
            return False
            
        if token_scope != expected_scope:
            log("TOKEN !", f"FAIL: Scope mismatch. Expected '{expected_scope}', got '{token_scope}'")
            return False
            
        if int(token_exp) < time.time():
            log("TOKEN !", f"FAIL: Expired token from {sender_id}")
            return False
            
        if token in revoked_tokens:
            log("TOKEN !", f"FAIL: Token is on revocation list")
            return False
        
        log("TOKEN OK", f"SUCCESS: Valid '{token_scope}' token from {sender_id}")
        return True

    except (ValueError, IndexError):
        log("TOKEN !", f"FAIL: Malformed token from {sender_id}")
        return False

# --- Profile Picture Functions ---
CHUNK_SIZE = 1000  # A safe size for UDP payload

def set_profile_picture(file_path):
    global MY_AVATAR_DATA, MY_AVATAR_TYPE
    try:
        with open(file_path, "rb") as image_file:
            image_data = image_file.read()
            
            # Check if the file exceeds the 20 KB limit
            if len(image_data) > 20000:
                print("Error: Image file exceeds the 20 KB limit.")
                return

            MY_AVATAR_DATA = base64.b64encode(image_data).decode('utf-8')
            
            if file_path.lower().endswith(('.png')):
                MY_AVATAR_TYPE = 'image/png'
            elif file_path.lower().endswith(('.jpg', '.jpeg')):
                MY_AVATAR_TYPE = 'image/jpeg'
            else:
                print("Error: Unsupported image type. Please use .png or .jpg.")
                MY_AVATAR_DATA = None
                MY_AVATAR_TYPE = None
                return
            
        print(f"Profile picture '{file_path}' set successfully. Broadcasting new profile...")
        broadcast_profile()
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"Error setting profile picture: {e}")

def broadcast_profile():
    # This function now intelligently sends avatars
    profile_msg = {
        "type": "PROFILE",
        "user_id": MY_ID,
        "name": my_profile_data["name"],
        "bio": my_profile_data["bio"]
    }
    
    # If the encoded avatar data is small enough to fit in a single packet,
    # send it all at once.
    if MY_AVATAR_DATA and len(MY_AVATAR_DATA) <= CHUNK_SIZE:
        profile_msg["AVATAR_TYPE"] = MY_AVATAR_TYPE
        profile_msg["AVATAR_ENCODING"] = "base64"
        profile_msg["AVATAR_DATA"] = MY_AVATAR_DATA
        send_message(profile_msg, (BROADCAST_ADDR, PORT))
    
    # If it's too big, send the profile info first, then send the chunks.
    elif MY_AVATAR_DATA:
        send_message(profile_msg, (BROADCAST_ADDR, PORT))
        send_avatar_in_chunks(MY_AVATAR_DATA, MY_AVATAR_TYPE)
    
    # If there's no avatar, just send the regular profile message.
    else:
        send_message(profile_msg, (BROADCAST_ADDR, PORT))


def send_avatar_in_chunks(avatar_data, avatar_type):
    """Breaks the base64 encoded avatar into chunks and sends them."""
    chunks = [avatar_data[i:i + CHUNK_SIZE] for i in range(0, len(avatar_data), CHUNK_SIZE)]
    total_chunks = len(chunks)
    transfer_id = str(uuid.uuid4().hex)

    for i, chunk_data in enumerate(chunks):
        msg = {
            "type": "PROFILE_CHUNK",
            "from": MY_ID,
            "CHUNK_ID": transfer_id,
            "CHUNK_NUM": str(i + 1),
            "TOTAL_CHUNKS": str(total_chunks),
            "AVATAR_TYPE": avatar_type,
            "AVATAR_CHUNK_DATA": chunk_data
        }
        send_message(msg, (BROADCAST_ADDR, PORT))

def view_profile_picture(user_id):
    if user_id in peer_avatars:
        print(f"Profile picture found for {user_id}. Data is stored locally.")
    else:
        print(f"No profile picture found for {user_id}.")

# === Functions ===
def log(prefix, message):
    """Prints a message only if VERBOSE mode is enabled."""
    if VERBOSE:
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"[{timestamp}] {prefix} {message}")
        
def send_message(data, addr):
    msg = '\n'.join(f"{k.upper()}: {v}" for k, v in data.items()) + "\n\n"
    log(f"SEND > [{data.get('type', 'UNKNOWN')}] to {addr[0]}:{addr[1]}", f"\n------\n{msg.strip()}\n------")
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

def send_follow_request(target_id):
    if target_id not in peers:
        print(f"Error: Peer {target_id} not found. Make sure you have seen their profile.")
        return

    message_id = str(uuid.uuid4().hex)[:8]
    msg = {
        "type": "FOLLOW",
        "message_id": message_id,
        "from": MY_ID,
        "to": target_id,
        "timestamp": str(int(time.time())),
        "token": generate_token(MY_ID, scope="follow")
    }
    
    # Store the fact that we're waiting for an ACK for this follow action
    pending_acks[message_id] = {"type": "FOLLOW", "target": target_id}
    
    target_addr = peers[target_id]
    send_message(msg, target_addr)
    print(f"[FOLLOW] Sent follow request to {target_id}. Waiting for acknowledgement...")

def send_unfollow_request(target_id):
    """Sends a request to unfollow a user and waits for acknowledgement."""
    if target_id not in following:
        print(f"Error: You are not currently following {target_id}.")
        return

    message_id = str(uuid.uuid4().hex)[:8]
    msg = {
        "type": "UNFOLLOW",
        "message_id": message_id,
        "from": MY_ID,
        "to": target_id,
        "timestamp": str(int(time.time())),
        "token": generate_token(MY_ID, scope="follow")
    }

    # Store the action we are waiting on
    pending_acks[message_id] = {"type": "UNFOLLOW", "target": target_id}
    
    target_addr = peers.get(target_id)
    if target_addr:
        send_message(msg, target_addr)
        print(f"[UNFOLLOW] Sent unfollow request to {target_id}. Waiting for acknowledgement...")
    else:
        # If peer is offline, the ACK will never arrive, so we can't unfollow.
        print(f"Error: Peer {target_id} appears to be offline. Cannot send unfollow request.")
        if message_id in pending_acks:
            del pending_acks[message_id]

def send_post_to_followers(content):

    # Sends a post individually to each known follower.

    if not followers:
        return print("[POST] You have no followers to post to.")

    print(f"[POST] Sending post to {len(followers)} follower(s)...")
    
    # Create the base message once
    timestamp = str(int(time.time()))
    post_msg = {
        "type": "POST",
        "user_id": MY_ID,
        "content": content,
        "ttl": "3600",
        "message_id": str(uuid.uuid4().hex), #random
        "timestamp": timestamp,
        "token": generate_token(MY_ID, scope="post")
    }

    # Save the post to our own list before sending
    my_posts.append({"timestamp": timestamp, "content": content})

    # Loop through your followers and send a direct message to each one
    for follower_id in followers:
        if follower_id in peers:
            target_addr = peers[follower_id]
            # Add the 'to' field for clarity, though not strictly required by handler
            post_msg['to'] = follower_id 
            send_message(post_msg, target_addr)
        else:
            print(f"[Warning] Follower {follower_id} is not a known, online peer.")
    
    print("[POST] Finished sending to followers.")

def send_dm(target_id, content):
    """Constructs and sends a reliable DM to a single user."""
    if target_id not in peers:
        return print(f"Error: Peer {target_id} not found.")
    if not content:
        return print("Error: Cannot send an empty message.")

    message_id = str(uuid.uuid4().hex)[:16]
    
    # Create the message exactly as specified in the RFC
    msg = {
        "type": "DM",
        "from": MY_ID,
        "to": target_id,
        "content": content,
        "timestamp": str(int(time.time())),
        "message_id": message_id,
        "token": generate_token(MY_ID, scope="chat")
    }
    
    # Add to our local history immediately
    if target_id not in dm_history:
        dm_history[target_id] = []
    dm_history[target_id].append(('sent', time.time(), content))

    # Set up the ACK waiting mechanism
    pending_acks[message_id] = {"type": "DM", "target": target_id}
    target_addr = peers[target_id]
    
    # Use the reliable send_message function from the ACK implementation
    # (Assuming you have a function that handles retransmissions)
    # For now, we'll just send it once and the ACK handler will do its job.
    send_message(msg, target_addr)
    print(f"DM sent to {target_id}.")

def send_like(post_index, action="LIKE"):
    """Looks up a post by its list index and sends a LIKE or UNLIKE action."""
    try:
        post_index = int(post_index)
        if not (1 <= post_index <= len(posts_list)):
            raise IndexError
    except (ValueError, IndexError):
        return print(f"Error: Invalid post number. Use 'posts' to see the list.")

    # Retrieve the post from our stored list (adjusting for 0-based index)
    post = posts_list[post_index - 1]
    
    target_id = post['sender']
    post_timestamp = post['ts']

    if target_id not in peers:
        return print(f"Error: Cannot send like. Peer {target_id} appears to be offline.")
        
    msg = {
        "type": "LIKE",
        "from": MY_ID,
        "to": target_id,
        "post_timestamp": post_timestamp,
        "action": action, # Will be "LIKE" or "UNLIKE"
        "timestamp": str(int(time.time())),
        "token": generate_token(MY_ID, scope="broadcast")
    }
    
    # Likes are sent directly to the post's author
    send_message(msg, peers[target_id])
    
    action_verb = "liked" if action == "LIKE" else "unliked"
    print(f"[ACTION] You {action_verb} the post: \"{post['content']}\"")

def create_group(group_id, group_name, members_str):
    """Creates a group and sends the invite to all members."""
    if not group_id or not group_name:
        return print("Error: Group ID and name cannot be empty.")
    if group_id in my_groups:
        return print(f"Error: You are already in a group with ID '{group_id}'.")

    member_ids = {m.strip() for m in members_str.split(',') if m.strip()}
    # The creator is always a member
    member_ids.add(MY_ID)
    
    # Check if all intended members are known peers
    for member_id in member_ids:
        if member_id != MY_ID and member_id not in peers:
            print(f"[Warning] Peer {member_id} is not currently known. They might not receive the group creation message.")

    # Create the message
    msg = {
        "type": "GROUP_CREATE",
        "from": MY_ID,
        "group_id": group_id,
        "group_name": group_name,
        "members": ",".join(sorted(list(member_ids))),
        "timestamp": str(int(time.time())),
        "token": generate_token(MY_ID, scope="group")
    }
    
    # Send the message to every member (including yourself, to create the group locally)
    for member_id in member_ids:
        if member_id == MY_ID:
            # Handle locally instead of sending to self over network
            handle_message(msg, (MY_IP, PORT))
        elif member_id in peers:
            send_message(msg, peers[member_id])
        
    print(f"Group '{group_name}' creation messages sent.")


def send_group_message(group_id, content):
    """Sends a message to all members of a specific group."""
    if group_id not in my_groups:
        return print(f"Error: You are not a member of group '{group_id}'.")
    if not content:
        return print("Error: Cannot send an empty message.")
        
    group_info = my_groups[group_id]
    members = group_info["members"]

    msg = {
        "type": "GROUP_MESSAGE",
        "from": MY_ID,
        "group_id": group_id,
        "content": content,
        "timestamp": str(int(time.time())),
        "token": generate_token(MY_ID, scope="group")
    }
    
    print(f"Sending message to {len(members)} members of '{group_info['name']}'...")
    for member_id in members:
        if member_id != MY_ID and member_id in peers:
            send_message(msg, peers[member_id])
    
    # Also display your own message
    print(f"[GROUP {group_info['name']}] You: {content}")

def send_group_update(group_id, members_to_add=None, members_to_remove=None):
    """Constructs and sends a GROUP_UPDATE message to relevant peers."""
    if group_id not in my_groups:
        return print(f"Error: You are not in group '{group_id}'.")
    
    if not members_to_add and not members_to_remove:
        return print("Error: You must specify members to add or remove.")

    current_info = my_groups[group_id]
    current_members = current_info["members"]

    # Any member is authorized to make changes in this implementation.
    if MY_ID not in current_members:
         return print(f"Error: You are no longer a member of '{group_id}' and cannot modify it.")

    msg = {
        "type": "GROUP_UPDATE",
        "from": MY_ID,
        "group_id": group_id,
        "timestamp": str(int(time.time())),
        "token": generate_token(MY_ID, scope="group")
    }

    # Add optional fields if they contain data
    if members_to_add:
        msg["add"] = ",".join(members_to_add)
    if members_to_remove:
        msg["remove"] = ",".join(members_to_remove)

    # Recipients are all current members plus any newly added members.
    recipients = current_members.union(members_to_add or set())

    print(f"Sending update for group '{current_info['name']}' to {len(recipients)} peers...")

    for member_id in recipients:
        if member_id == MY_ID:
             # Handle locally immediately to update own state
             handle_message(msg, (MY_IP, PORT))
        elif member_id in peers:
            send_message(msg, peers[member_id])
        else:
            print(f"[Warning] Peer {member_id} is not currently known. They may not receive the group update.")

# === File transfer helpers ===
def make_fileid():
    return uuid.uuid4().hex[:8]

def chunk_bytes(data, size):
    for i in range(0, len(data), size):
        yield data[i:i+size]

def send_file_offer(target_id, filepath, description=""):
    """Read file metadata and send FILE_OFFER to target peer."""
    if target_id not in peers:
        print(f"Error: Peer {target_id} not known.")
        return
    if not os.path.isfile(filepath):
        print(f"Error: File '{filepath}' not found.")
        return

    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)
    filetype, _ = mimetypes.guess_type(filepath)
    if not filetype:
        filetype = "application/octet-stream"
    fileid = make_fileid()
    timestamp = str(int(time.time()))
    token = generate_token(MY_ID, scope="file")

    msg = {
        "type": "FILE_OFFER",
        "from": MY_ID,
        "to": target_id,
        "filename": filename,
        "filesize": str(filesize),
        "filetype": filetype,
        "fileid": fileid,
        "description": description,
        "timestamp": timestamp,
        "token": token
    }

    # Record outgoing transfer (file path needed when sending chunks)
    outgoing_transfers[fileid] = {
        "filepath": filepath,
        "filename": filename,
        "filesize": filesize,
        "filetype": filetype,
        "target": target_id,
        "token": token,
        "sent": False
    }

    send_message(msg, peers[target_id])
    print(f"[FILE_OFFER] Sent offer for '{filename}' to {target_id}. FileID: {fileid}")
    print("Waiting for recipient to accept (use 'fileaccept <fileid>' on recipient).")

def _send_file_chunks_async(fileid):
    """Sends chunks for an outgoing transfer. Runs in a separate thread."""
    record = outgoing_transfers.get(fileid)
    if not record:
        return
    target = record["target"]
    target_addr = peers.get(target)
    if not target_addr:
        log("DROP !", f"Cannot send chunks for {fileid}: peer {target} unknown.")
        return

    filepath = record["filepath"]
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
    except Exception as e:
        log("DROP !", f"Failed to read file {filepath}: {e}")
        return

    # Break into chunks
    chunk_list = list(chunk_bytes(raw, MAX_CHUNK_SIZE))
    total_chunks = len(chunk_list)
    chunk_size = MAX_CHUNK_SIZE
    token = record["token"]
    fileid_local = fileid

    for idx, chunk in enumerate(chunk_list):
        b64chunk = base64.b64encode(chunk).decode('ascii')
        chunk_msg = {
            "type": "FILE_CHUNK",
            "from": MY_ID,
            "to": target,
            "fileid": fileid_local,
            "chunk_index": str(idx),
            "total_chunks": str(total_chunks),
            "chunk_size": str(len(chunk)),
            "token": token,
            "data": b64chunk
        }
        send_message(chunk_msg, target_addr)
        # Slight pause to avoid flooding the network
        time.sleep(0.02)

    # After sending all chunks, optionally wait for FILE_RECEIVED from receiver.
    record["sent"] = True
    log("SEND >", f"All chunks for {fileid_local} sent to {target} ({total_chunks} chunks).")

def fileaccept_cmd(fileid):
    """Called in CLI on recipient to accept an offer and start receiving."""
    offer = pending_file_offers.get(fileid)
    if not offer:
        print(f"Error: No pending file offer with id {fileid}. Use 'fileoffers' to list offers.")
        return
    # Mark that we accept this file — create incoming_transfers entry
    incoming_transfers[fileid] = {
        "filename": offer["filename"],
        "filesize": int(offer["filesize"]),
        "filetype": offer["filetype"],
        "from": offer["from"],
        "total_chunks": None,  # to be set when the first chunk arrives
        "chunks": {}
    }
    # Remove from pending offers
    del pending_file_offers[fileid]
    print(f"[FILE] Accepted offer {fileid}. Waiting for chunks...")

def send_file_received(target_id, fileid, status="COMPLETE"):
    msg = {
        "type": "FILE_RECEIVED",
        "from": MY_ID,
        "to": target_id,
        "fileid": fileid,
        "status": status,
        "timestamp": str(int(time.time()))
    }
    if target_id in peers:
        send_message(msg, peers[target_id])

def try_assemble_file(fileid):
    """If all chunks for fileid are present, assemble, write to disk and notify sender."""
    info = incoming_transfers.get(fileid)
    if not info:
        return
    chunks = info["chunks"]
    total = info["total_chunks"]
    if total is None:
        return
    if len(chunks) < total:
        return

    # Reassemble chunks in order
    ordered = []
    for i in range(total):
        ordered.append(chunks[str(i)])
    try:
        raw_b64 = "".join(ordered)
        raw = base64.b64decode(raw_b64)
    except Exception as e:
        log("DROP !", f"Failed to decode/reassemble file {fileid}: {e}")
        return

    filename = info["filename"]
    # If filename exists, do not overwrite — create unique name
    outname = filename
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(outname):
        outname = f"{base}_{counter}{ext}"
        counter += 1

    try:
        with open(outname, "wb") as f:
            f.write(raw)
    except Exception as e:
        log("DROP !", f"Failed to write file {outname}: {e}")
        return

    # Inform user per spec (only print when all chunks completed)
    print(f"\nFile transfer of {filename} is complete. Saved as: {outname}")

    # Send FILE_RECEIVED back to sender
    send_file_received(info["from"], fileid, status="COMPLETE")

    # Cleanup
    del incoming_transfers[fileid]

# === Tic-Tac-Toe Functions ===
def send_invite(target_id, symbol):
    global game_id_counter
    game_id = f"g{game_id_counter}"
    game_id_counter = (game_id_counter + 1) % 256

    opponent_symbol = 'O' if symbol == 'X' else 'X'
    is_my_turn = (symbol == 'X')
    
    # Create the game instance and store it
    active_games[game_id] = TicTacToeGame(game_id, target_id, symbol, opponent_symbol, is_my_turn)

    invite_msg = {
        "type": "TICTACTOE_INVITE",
        "from": MY_ID,
        "to": target_id,
        "gameid": game_id,
        "message_id": str(uuid.uuid4().hex),
        "symbol": symbol,
        "timestamp": str(int(time.time())),
        "token": generate_token(MY_ID, scope="game")
    }
    target_addr = peers.get(target_id)
    if target_addr:
        send_message(invite_msg, target_addr)
        print(f"[TICTACTOE] Sent invite for game {game_id} to {target_id}. Waiting for their move...")
        active_games[game_id].display_board()
    else:
        print(f"Error: {target_id} is not a known peer.")
        del active_games[game_id] # Clean up if the peer is unknown

def send_move(game_id, position):
    game = active_games.get(game_id)
    if not game:
        print(f"Error: Game {game_id} not found.")
        return
    if not game.is_my_turn:
        print("Error: It's not your turn.")
        return

    try:
        position = int(position)
    except ValueError:
        print("Error: Position must be a number.")
        return
    if position < 0 or position > 8:
        print("Error: Position must be 0–8.")
        return
    if not game.make_move(position, game.my_symbol):
        print("Error: That spot is already taken.")
        return

    move_msg = {
        "type": "TICTACTOE_MOVE",
        "from": MY_ID,
        "to": game.opponent_id,
        "gameid": game_id,
        "message_id": str(uuid.uuid4().hex),
        "position": str(position),
        "symbol": game.my_symbol,
        "turn": str(game.turn - 1),
        "token": generate_token(MY_ID, scope="game")
    }
    send_message(move_msg, peers[game.opponent_id])
    game.is_my_turn = False
    game.display_board()  # Non-verbose board print

    winner, winning_line = game.check_winner()
    if winner:
        send_result(game_id, winner, winning_line)
        del active_games[game_id]

def send_result(game_id, result_type, winning_line=None):
    game = active_games.get(game_id)
    if not game:
        return

    result = "DRAW"
    if result_type == game.my_symbol:
        result = "WIN"
    elif result_type == game.opponent_symbol:
        result = "LOSE"

    result_msg = {
        "type": "TICTACTOE_RESULT",
        "from": MY_ID,
        "to": game.opponent_id,
        "gameid": game_id,
        "message_id": str(uuid.uuid4().hex),
        "result": result,
        "symbol": game.my_symbol,
        "timestamp": str(int(time.time()))
    }
    if winning_line:
        result_msg["winning_line"] = ",".join(map(str, winning_line))

    send_message(result_msg, peers[game.opponent_id])
    # Non-verbose board print after sending result
    game.display_board()
    print(f"\n[TICTACTOE] Game {game_id} finished. Result: {result}.")
    print("> ", end="", flush=True)

# --- "ignore self" logic ---
def handle_message(data, addr):
    sender_id = data.get("user_id") or data.get("from")

    # Critical check to prevent processing your own broadcast messages, but allow targeted self-messages (like group create)
    if sender_id == MY_ID and data.get('to') != MY_ID and data.get('type') not in ['GROUP_CREATE', 'GROUP_UPDATE']:
        return


    mtype = data.get("type", "").upper()
    message_id = data.get("message_id")
    token = data.get("token", "")

    if mtype in ["FOLLOW", "UNFOLLOW"] and message_id:
        # These are critical requests, so we ACK them.
        ack_msg = {"type": "ACK", "message_id": message_id, "status": "RECEIVED"}
        send_message(ack_msg, addr)
        print("> ", end="", flush=True)

    if mtype == "FOLLOW":
        from_id = data.get("from")
        to_id = data.get("to")
        if to_id == MY_ID and from_id and message_id:
            followers.add(from_id)
            peers[from_id] = (addr[0], PORT)
            print(f"\n[FOLLOW] {from_id} is now following you.")
            ack_msg = {"type": "ACK", "message_id": message_id, "status": "RECEIVED"}
            send_message(ack_msg, (addr[0], PORT))
            print("> ", end="", flush=True)

    elif mtype == "UNFOLLOW":
        from_id = data.get("from")
        to_id = data.get("to")
        if to_id == MY_ID and from_id in followers and message_id:
            followers.remove(from_id)
            print(f"\n[UNFOLLOW] {from_id} has unfollowed you.")
            ack_msg = {"type": "ACK", "message_id": message_id, "status": "RECEIVED"}
            send_message(ack_msg, (addr[0], PORT))
            print("> ", end="", flush=True)

    elif mtype == "ACK":
        if message_id in pending_acks:
            action = pending_acks[message_id]
            target_id = action["target"]
            
            if action["type"] == "FOLLOW":
                following.add(target_id)
                print(f"\n[SUCCESS] You are now following {target_id}.")
            
            elif action["type"] == "UNFOLLOW":
                following.remove(target_id)
                print(f"\n[SUCCESS] Your unfollow request for {target_id} was received.")
            
            del pending_acks[message_id]
            print("> ", end="", flush=True)

    elif mtype == "DM":
        to_id = data.get("to")
        token = data.get("token", "")
        content = data.get("content", "")
        # 1. Validate the message is for me and the token is correct
        if to_id == MY_ID and validate_token(token, "chat", sender_id):
            # 2. Add to local history
            if sender_id not in dm_history:
                dm_history[sender_id] = []
            dm_history[sender_id].append(('recvd', time.time(), content))
            # 3. Print it for the user
            name = known_profiles.get(sender_id, (sender_id,))[0]
            print(f"\n[DM from {name}]: {content}")
            # 4. Send the ACK
            if message_id:
                ack_msg = {"type": "ACK", "message_id": message_id, "status": "RECEIVED"}
                send_message(ack_msg, addr)
            print("> ", end="", flush=True)

    elif mtype == "PROFILE":
        name = data.get("name", "")
        bio = data.get("bio", "")
        if sender_id:
            known_profiles[sender_id] = (name, bio)
            peers[sender_id] = (addr[0], PORT)
            print(f"\n[PROFILE] {sender_id}: {name} | {bio}")

            if 'avatar_data' in data and 'avatar_type' in data:
                peer_avatars[sender_id] = {
                    "data": data['avatar_data'],
                    "type": data['avatar_type']
                }
                print(f"[PROFILE] Avatar received for {sender_id}.")
            print("> ", end="", flush=True)

    elif mtype == "PROFILE_CHUNK":
        sender_id = data.get("from")
        chunk_id = data.get("chunk_id")
        chunk_num = int(data.get("chunk_num", 0))
        total_chunks = int(data.get("total_chunks", 0))
        avatar_type = data.get("avatar_type")
        chunk_data = data.get("avatar_chunk_data")
        
        if sender_id not in incoming_avatar_chunks:
            incoming_avatar_chunks[sender_id] = {}
        if chunk_id not in incoming_avatar_chunks[sender_id]:
            incoming_avatar_chunks[sender_id][chunk_id] = {
                "chunks": [None] * total_chunks,
                "received": 0,
                "total": total_chunks,
                "type": avatar_type
            }

        if chunk_num > 0 and chunk_num <= total_chunks:
            incoming_avatar_chunks[sender_id][chunk_id]["chunks"][chunk_num - 1] = chunk_data
            incoming_avatar_chunks[sender_id][chunk_id]["received"] += 1

            if incoming_avatar_chunks[sender_id][chunk_id]["received"] == total_chunks:
                full_avatar_data = "".join(incoming_avatar_chunks[sender_id][chunk_id]["chunks"])
                
                peer_avatars[sender_id] = {
                    "data": full_avatar_data,
                    "type": avatar_type
                }
                
                print(f"\n[PROFILE] Full avatar received for {sender_id}.")
                del incoming_avatar_chunks[sender_id][chunk_id]
                print("> ", end="", flush=True)
        
    elif mtype == "POST":
        content = data.get("content", "")
        post_timestamp = data.get("timestamp")
        # CORRECT LOGIC: Display the post ONLY if you are following the sender.
        if sender_id and content and message_id and post_timestamp:
            posts_list.append({
                "id": message_id,
                "ts": post_timestamp,
                "sender": sender_id,
                "content": content
            })
            name = known_profiles.get(sender_id, [sender_id])[0]
            print(f"\n[POST from {name}]: {content}")
            print("> ", end="", flush=True)
    
    elif mtype == "LIKE":
        liker_id = data.get("from")
        to_id = data.get("to")
        action = data.get("action", "LIKE").upper()
        post_timestamp = data.get("post_timestamp")
        
        # Validate the message is for me and the token is valid
        token = data.get("token", "")
        if to_id == MY_ID and validate_token(token, "broadcast", sender_id):
            # Find the original post they are talking about
            original_post_content = "a post of yours"
            for post in posts_list:
                if post['ts'] == post_timestamp and post['sender'] == MY_ID:
                    original_post_content = f"your post: \"{post['content']}\""
                    break
            
            liker_name = known_profiles.get(sender_id, (sender_id,))[0]
            action_verb = "likes" if action == "LIKE" else "unlikes"
            print(f"\n[ACTION] {liker_name} {action_verb} {original_post_content}")
            print("> ", end="", flush=True)

    elif mtype == "GROUP_CREATE":
        group_id = data.get("group_id")
        group_name = data.get("group_name")
        members_str = data.get("members", "")
        
        if validate_token(token, "group", sender_id) and group_id and group_name:
            # Add or update the group in our local state
            member_set = set(members_str.split(','))
            my_groups[group_id] = {"name": group_name, "members": member_set}
            
            # Print non-verbose message only if we are not the creator
            if sender_id != MY_ID:
                print(f"\nYou've been added to {group_name}")
                print("> ", end="", flush=True)

    elif mtype == "GROUP_MESSAGE":
        group_id = data.get("group_id")
        content = data.get("content", "")
        
        if validate_token(token, "group", sender_id) and group_id in my_groups:
            # Security check: ensure the sender is actually in the group according to our local state
            if sender_id in my_groups[group_id]["members"]:
                group_name = my_groups[group_id]['name']
                sender_name = known_profiles.get(sender_id, (sender_id,))[0]
                
                # The new, clearer output format
                print(f"\n[GROUP: {group_name}] {sender_name}: {content}")
            else:
                log("DROP !", f"Group message from {sender_id} for group {group_id}, but they are not a member.")
            print("> ", end="", flush=True)

    elif mtype == "GROUP_UPDATE":
        group_id = data.get("group_id")
        
        if not group_id or not sender_id or not validate_token(token, "group", sender_id):
            return # Basic validation failed

        add_list = {m.strip() for m in data.get("add", "").split(',') if m.strip()}
        remove_list = {m.strip() for m in data.get("remove", "").split(',') if m.strip()}

        # Case 1: An invitation for me to a new group via an update.
        if group_id not in my_groups and MY_ID in add_list:
            # Create a placeholder group. Name is unknown until a GROUP_CREATE or other message arrives.
            log("GROUP !", f"Added to new group '{group_id}' via GROUP_UPDATE from {sender_id}.")
            my_groups[group_id] = {"name": group_id, "members": {sender_id, MY_ID}}
            print(f"\nYou have been added to the group '{group_id}'.")

        # Case 2: An update for a group I am already in.
        elif group_id in my_groups:
            # Sender must be a member to authorize a change.
            if sender_id not in my_groups[group_id]["members"]:
                log("DROP !", f"Rejected GROUP_UPDATE from non-member {sender_id} for group {group_id}")
                return
            
            current_members = my_groups[group_id]["members"]
            updated_members = (current_members.union(add_list)) - remove_list
            my_groups[group_id]["members"] = updated_members
            
            group_name = my_groups[group_id]['name']
            if MY_ID in remove_list:
                print(f"\nYou have been removed from the group '{group_name}'.")
                del my_groups[group_id]
            elif sender_id != MY_ID:
                print(f"\nThe group “{group_name}” member list was updated.")
            print("> ", end="", flush=True)
                
    # === File transfer handlers ===
    elif mtype == "FILE_OFFER":
        # Received an offer; store it in pending_file_offers and prompt user per spec
        from_id = data.get("from")
        to_id = data.get("to")
        fileid = data.get("fileid")
        filename = data.get("filename")
        filesize = data.get("filesize")
        filetype = data.get("filetype")
        description = data.get("description", "")

        # Ensure offer is intended for us
        if to_id != MY_ID:
            return

        # Validate token scope before advertising offer to user (optional but sensible)
        if not validate_token(token, "file", from_id):
            log("DROP !", f"FILE_OFFER from {from_id} failed token validation.")
            return

        pending_file_offers[fileid] = {
            "from": from_id,
            "filename": filename,
            "filesize": filesize,
            "filetype": filetype,
            "description": description,
            "timestamp": data.get("timestamp", "")
        }

        # Non-verbose printing (per spec)
        sender_name = known_profiles.get(from_id, (from_id.split('@')[0],))[0]
        print(f"\nUser {sender_name} is sending you a file do you accept? (fileid: {fileid})")
        print("> ", end="", flush=True)

    elif mtype == "FILE_CHUNK":
        # Received chunk — store it only if offer accepted (incoming_transfers contains fileid)
        from_id = data.get("from")
        to_id = data.get("to")
        fileid = data.get("fileid")
        chunk_index = data.get("chunk_index")
        total_chunks = data.get("total_chunks")
        chunk_size = data.get("chunk_size")
        b64data = data.get("data")
        token = data.get("token", "")

        # Only accept chunks if they are for us
        if to_id != MY_ID:
            return

        # Token validation (must be file scope)
        if not validate_token(token, "file", from_id):
            log("DROP !", f"FILE_CHUNK from {from_id} failed token validation.")
            return

        # If this fileid is not in incoming_transfers (i.e., not accepted), ignore chunks
        transfer = incoming_transfers.get(fileid)
        if not transfer:
            log("DROP !", f"Ignoring chunk for {fileid} because offer not accepted or unknown.")
            return

        # Initialize total_chunks if not set
        if transfer["total_chunks"] is None and total_chunks:
            try:
                transfer["total_chunks"] = int(total_chunks)
            except ValueError:
                transfer["total_chunks"] = None

        # Store the chunk (keep as base64 string for easier concatenation/assembly)
        transfer["chunks"][chunk_index] = b64data
        log("RECV <", f"Stored chunk {chunk_index} for {fileid} (from {from_id})")

        # Check if we can assemble
        try_assemble_file(fileid)
        print("> ", end="", flush=True)

    elif mtype == "FILE_RECEIVED":
        # Sender receives notification; we can log it
        from_id = data.get("from")
        to_id = data.get("to")
        fileid = data.get("fileid")
        status = data.get("status", "")
        if to_id == MY_ID:
            log("RECV <", f"FILE_RECEIVED from {from_id} for {fileid}: {status}")
            # Optionally cleanup outgoing_transfers
            if fileid in outgoing_transfers:
                del outgoing_transfers[fileid]

    # === Tic-Tac-Toe Message Handlers ===
    elif mtype == "TICTACTOE_INVITE":
        game_id = data.get("gameid")
        symbol = data.get("symbol", "").upper()
        from_id = data.get("from")
        to_id = data.get("to")
        
        # Verbose log for incoming invite
        log("RECV <", f"TICTACTOE_INVITE from {from_id} for game {game_id}. My symbol will be '{'O' if symbol == 'X' else 'X'}'.")

        # Validation
        if not game_id or not game_id.startswith("g") or not game_id[1:].isdigit() or not (0 <= int(game_id[1:]) <= 255):
            print(f"\n[TICTACTOE] Invalid GAMEID '{game_id}'. Ignoring invite.")
            log("DROP !", f"Invalid GAMEID '{game_id}' in TICTACTOE_INVITE.")
            return
        if symbol not in ("X", "O"):
            print(f"\n[TICTACTOE] Invalid SYMBOL '{symbol}'. Ignoring invite.")
            log("DROP !", f"Invalid SYMBOL '{symbol}' in TICTACTOE_INVITE.")
            return
        if to_id != MY_ID:
            return  # Not for us
        
        # Non-verbose printing
        inviter_name = from_id.split("@")[0]
        print(f"\n{inviter_name} is inviting you to play tic-tac-toe.")
        
        # Create game object: we are invitee, so opponent moves first if symbol != our symbol
        my_symbol = "O" if symbol == "X" else "X"
        active_games[game_id] = TicTacToeGame(
            game_id=game_id,
            opponent_id=from_id,
            my_symbol=my_symbol,
            opponent_symbol=symbol,
            is_my_turn=(my_symbol == "X")
        )
        print("> ", end="", flush=True)
        
    elif mtype == "TICTACTOE_MOVE":
        from_id = data.get("from")
        game_id = data.get("gameid")
        position = data.get("position")
        symbol = data.get("symbol", "").upper()

        # Verbose log for incoming move
        log("RECV <", f"TICTACTOE_MOVE from {from_id} for game {game_id}. Position: {position}, Symbol: {symbol}.")
        
        # Validation
        try:
            position = int(position)
        except (TypeError, ValueError):
            print(f"\n[TICTACTOE] Invalid POSITION '{position}'. Ignoring move.")
            log("DROP !", f"Invalid POSITION '{position}' in TICTACTOE_MOVE.")
            return
        
        if position < 0 or position > 8:
            print(f"\n[TICTACTOE] POSITION out of range: {position}")
            log("DROP !", f"POSITION out of range: {position} in TICTACTOE_MOVE.")
            return
        if symbol not in ("X", "O"):
            print(f"\n[TICTACTOE] Invalid SYMBOL '{symbol}'. Ignoring move.")
            log("DROP !", f"Invalid SYMBOL '{symbol}' in TICTACTOE_MOVE.")
            return

        game = active_games.get(game_id)
        if not game:
            print(f"\n[TICTACTOE] Received move for unknown game {game_id}. Ignoring.")
            log("DROP !", f"Received move for unknown game {game_id}.")
            return
        if symbol != game.opponent_symbol:
            print(f"\n[TICTACTOE] SYMBOL mismatch in move for game {game_id}. Ignoring.")
            log("DROP !", f"SYMBOL mismatch in TICTACTOE_MOVE for game {game_id}. Expected {game.opponent_symbol}, got {symbol}.")
            return
        if not game.make_move(position, symbol):
            print(f"\n[TICTACTOE] Position {position} already taken in game {game_id}.")
            log("DROP !", f"Position {position} already taken in game {game_id}.")
            return

        # Token validation for moves
        if not validate_token(token, "game", from_id):
            print(f"\n[TICTACTOE] Invalid token for move in game {game_id}. Ignoring.")
            log("DROP !", f"Invalid token for TICTACTOE_MOVE from {from_id}.")
            return
        
        game.is_my_turn = True
        game.display_board()  # Non-verbose: just print board

        winner, winning_line = game.check_winner()
        if winner:
            send_result(game_id, winner, winning_line)
            del active_games[game_id]
        print("> ", end="", flush=True)
        
    elif mtype == "TICTACTOE_RESULT":
        game_id = data.get("gameid")
        result = data.get("result", "").upper()
        winning_line = data.get("winning_line")

        # Verbose log for incoming result
        log("RECV <", f"TICTACTOE_RESULT for game {game_id}. Result: {result}.")

        game = active_games.get(game_id)
        if not game:
            log("DROP !", f"Received result for unknown game {game_id}.")
            return

        # Non-verbose printing: only board + whose turn (but since it's final, we print result)
        game.display_board()
        if result == "WIN":
            print("\nYou won.")
        elif result == "LOSE":
            print("\nYou lost.")
        elif result == "DRAW":
            print("\nDraw.")
        elif result == "FORFEIT":
            print("\nOpponent forfeited.")
        else:
            print(f"\nGame over. Result: {result}")

        del active_games[game_id]
        print("> ", end="", flush=True)

# === Listener Thread ===
def listen():
    while True:
        try:
            # Main listening socket is now only used here
            raw, addr = sock.recvfrom(65535)
            message = raw.decode('utf-8')
            data = parse_message(message)
            log(f"RECV < [{data.get('type', 'UNKNOWN')}] from {addr[0]}:{addr[1]}", f"\n------\n{message.strip()}\n------")
            handle_message(data, addr)
        except Exception as e:
            log("DROP !", f"Packet dropped due to error: {e}")
            # This is a safe way to handle potential errors without crashing the thread
            sys.stderr.write(f"\nError handling message: {e}\n")
            sys.stderr.flush()

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
        print("  peers                                  - List known peers")
        print("  profile set <name|bio> <value>         - Update your profile name or bio")
        print("  profile set avatar <path>              - Add your profile picture from a local file")
        print("  profile view [user_id]                 - View your or another user's profile")
        print("  post <message>                         - Send a post to followers")
        print("  posts                                  - List of posts of the users you are following")
        print("  myposts                                - List your own sent posts")
        print("  like <post number>                     - Like a post")  
        print("  unlike <post number>                   - Unlike a post")  
        print("  follow <user_id>                       - Follow a user")
        print("  unfollow <user_id>                     - Unfollow a user")
        print("  following                              - List users you are following")
        print("  followers                              - List your followers")
        print("  dm <user_id> <message>                 - Send a private message")
        print("  dms [user_id]                          - View DM history")
        print("  fileoffer <user_id> <filepath> [desc]  - Offer a file to a peer")
        print("  fileaccept <fileid>                    - Accept a pending file offer")
        print("  fileoffers                             - List pending file offers")
        print("  group create <id> <name> <members>     - Create a group (members are comma-separated IDs)")
        print("  gsend <group_id> <message>             - Send a message to a group")
        print("  groups                                 - List the groups you are in")
        print("  group info <id>                        - List the members of a specific group")
        print("  group add <id> <members>               - Add members to a group")
        print("  group remove <id> <members>            - Remove members from a group")
        print("  ttinvite <user_id> <X|O>               - Invite a user to a tic-tac-toe game")
        print("  ttmove <gameid> <position>             - Make a move in an active game")
        print("  ttaccept <gameid> <pos>                - Accept an invite and make your first move")
        print("  ttgames                                - List active games")
        print("  exit                                   - Quit")

    elif cmd.startswith("follow "):
        try:
            _, user = cmd.split(" ", 1)
            send_follow_request(user.strip())
        except ValueError:
            print("Usage: follow <user_id>")
            
    elif cmd.startswith("unfollow "):
        try:
            _, user = cmd.split(" ", 1)
            send_unfollow_request(user.strip())
        except ValueError:
            print("Usage: unfollow <user_id>")
    
    elif cmd == "following":
        if not following:
            print("You are not following anyone.")
        else:
            print("--- You Are Following ---")
            for f_id in following:
                print(f"- {f_id}")

    elif cmd.startswith("profile set avatar "):
        parts = cmd.split(" ", 3)
        if len(parts) == 4:
            file_path = parts[3]
            set_profile_picture(file_path)
        else:
            print("Usage: profile set avatar <path_to_image>")

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

    elif cmd.startswith("profile view"):
        parts = cmd.split(" ", 2)
        if len(parts) == 3:
            user_id = parts[2]
            
            # Check if the user is trying to view their own profile
            if user_id == MY_ID:
                print("--- Your Profile ---")
                print(f"Name: {my_profile_data['name']}")
                print(f"Bio: {my_profile_data['bio']}")
                if MY_AVATAR_DATA:
                    print(f"Profile picture is set. Type: {MY_AVATAR_TYPE}")
                else:
                    print("No profile picture is currently set.")
            elif user_id in known_profiles:
                name, bio = known_profiles[user_id]
                print(f"--- Profile for {name} ({user_id}) ---")
                print(f"Name: {name}")
                print(f"Bio: {bio}")
                if user_id in peer_avatars:
                    print("Profile picture: Yes")
                else:
                    print("Profile picture: No")
            else:
                print(f"Error: Peer {user_id} not found.")
        elif len(parts) == 2:
            # Displays my own profile by default
            print("--- Your Profile ---")
            print(f"Name: {my_profile_data['name']}")
            print(f"Bio: {my_profile_data['bio']}")
            if MY_AVATAR_DATA:
                print(f"Profile picture is set. Type: {MY_AVATAR_TYPE}")
            else:
                print("No profile picture is currently set.")
        else:
            print("Usage: profile view [user_id]")

    elif cmd.startswith("post "):
        try:
            _, content = cmd.split(" ", 1)
            send_post_to_followers(content.strip()) 
        except ValueError:
            print("Usage: post <message>")

    elif cmd == "posts":
        print("--- Recent Posts from Following ---")
        if not posts_list:
            print("No posts to show. Follow someone and wait for them to post.")
        else:
            for i, post in enumerate(posts_list, 1):
                name = known_profiles.get(post['sender'], (post['sender'],))[0]
                print(f"[{i}] From {name}: {post['content']}")
    
    elif cmd == "myposts":
        print("--- Your Posts ---")
        if not my_posts:
            print("You have not created any posts yet.")
        else:
            # Sort by timestamp, newest first
            sorted_posts = sorted(my_posts, key=lambda p: int(p['timestamp']), reverse=True)
            for i, post in enumerate(sorted_posts, 1):
                ts = int(post['timestamp'])
                print(f"[{i}] [{time.ctime(ts)}] {post['content']}")

    elif cmd.startswith("like "):
        _, post_num = cmd.split(" ", 1)
        send_like(post_num, "LIKE")
        
    elif cmd.startswith("unlike "):
        _, post_num = cmd.split(" ", 1)
        send_like(post_num, "UNLIKE")

    elif cmd.startswith("dm "):
        parts = cmd.split(" ", 2)
        if len(parts) == 3:
            send_dm(parts[1], parts[2])
        else:
            print("Usage: dm <user_id> <message>")

    elif cmd.startswith("dms"):
        parts = cmd.split(" ", 1)
        target_user = parts[1] if len(parts) > 1 else None
        
        if not target_user:
            print("--- DM Conversations ---")
            if not dm_history: print("No messages yet.")
            else: [print(f"- {user}") for user in dm_history]
        elif target_user in dm_history:
            name = known_profiles.get(target_user, (target_user,))[0]
            print(f"--- History with {name} ---")
            for direction, ts, content in dm_history[target_user]:
                sender = "You" if direction == 'sent' else name
                print(f"[{time.ctime(ts)}] {sender}: {content}")
        else:
            print(f"No message history with {target_user}.")

    elif cmd.startswith("group create "):
        parts = cmd.split(" ", 4)
        if len(parts) < 5:
            print("Usage: group create <group_id> <group_name> <member1,member2,...>")
        else:
            group_id = parts[2]
            group_name = parts[3]
            members_str = parts[4]
            create_group(group_id, group_name, members_str)
    
    elif cmd.startswith("group add "):
        parts = cmd.split(" ", 3)
        if len(parts) != 4:
            print("Usage: group add <group_id> <member1,member2,...>")
        else:
            group_id = parts[2]
            members_to_add = {m.strip() for m in parts[3].split(',') if m.strip()}
            send_group_update(group_id, members_to_add=members_to_add)

    elif cmd.startswith("group remove "):
        parts = cmd.split(" ", 3)
        if len(parts) != 4:
            print("Usage: group remove <group_id> <member1,member2,...>")
        else:
            group_id = parts[2]
            members_to_remove = {m.strip() for m in parts[3].split(',') if m.strip()}
            send_group_update(group_id, members_to_remove=members_to_remove)

    elif cmd.startswith("gsend "):
        parts = cmd.split(" ", 2)
        if len(parts) != 3:
            print("Usage: gsend <group_id> <message>")
        else:
            group_id = parts[1]
            content = parts[2]
            send_group_message(group_id, content)

    elif cmd == "groups":
        if not my_groups:
            print("You are not a member of any groups.")
        else:
            print("--- Your Groups ---")
            for group_id, info in my_groups.items():
                print(f"- {info['name']} (ID: {group_id}) | Members: {len(info['members'])}")

    elif cmd.startswith("group info "):
        parts = cmd.split(" ", 2)
        if len(parts) != 3:
            print("Usage: group info <group_id>")
        else:
            group_id = parts[2]
            if group_id in my_groups:
                info = my_groups[group_id]
                print(f"--- Members of {info['name']} (ID: {group_id}) ---")
                for member_id in sorted(list(info['members'])):
                    # Try to get the friendly name, otherwise just show the ID
                    name = known_profiles.get(member_id, (member_id,))[0]
                    if member_id == MY_ID:
                        print(f"- {name} ({member_id}) [You]")
                    else:
                        print(f"- {name} ({member_id})")
            else:
                print(f"Error: You are not in a group with ID '{group_id}'.")

    elif cmd == "peers":
        if not peers:
            print("No peers known.")
        else:
            print("--- Known Peers ---")
            for uid, (ip, port) in peers.items():
                name, bio = known_profiles.get(uid, (uid, "N/A"))
                print(f"- {name} ({uid}) | Bio: {bio}")

    elif cmd == "followers":
        if not followers:
            print("You have no followers yet.")
        else:
            print("--- Your Followers ---")
            for f_id in followers:
                print(f"- {f_id}")
    
    # === Tic-Tac-Toe Commands ===
    elif cmd.startswith("ttinvite "):
        parts = cmd.split(" ", 2)
        if len(parts) != 3:
            print("Usage: ttinvite <user_id> <X|O>")
        else:
            target_id = parts[1]
            symbol = parts[2].upper()
            if symbol not in ['X', 'O']:
                print("Error: Symbol must be 'X' or 'O'.")
            elif target_id not in peers:
                print(f"Error: {target_id} is not a known peer.")
            else:
                send_invite(target_id, symbol)
                
    elif cmd.startswith("ttmove "):
        parts = cmd.split(" ", 2)
        if len(parts) != 3:
            print("Usage: ttmove <gameid> <position>")
        else:
            game_id = parts[1]
            position = parts[2]
            send_move(game_id, position)
    
    elif cmd.startswith("ttaccept "):
        parts = cmd.split(" ", 2)
        if len(parts) != 3:
            print("Usage: ttaccept <gameid> <position>")
        else:
            game_id = parts[1]
            position = parts[2]
            game = active_games.get(game_id)
            if not game:
                print(f"Error: No pending invite for game {game_id}.")
            else:
                # The first move after accepting is handled by the move function
                # The invite receiver plays 'O' and the inviter plays 'X'
                if game.my_symbol == 'X':
                    print("Error: You are 'X', the inviter. You must wait for their move.")
                else:
                    send_move(game_id, position)
    
    elif cmd == "ttgames":
        if not active_games:
            print("No active games.")
        else:
            print("--- Active Games ---")
            for game_id, game in active_games.items():
                status = "Your turn" if game.is_my_turn else "Waiting for opponent"
                print(f"- Game {game_id} against {game.opponent_id} ({game.my_symbol}) - {status}")

    elif cmd.startswith("fileoffer "):
        # Usage: fileoffer <user_id> <filepath> [description]
        parts = cmd.split(" ", 2)
        if len(parts) < 3:
            print("Usage: fileoffer <user_id> <filepath> [description]")
        else:
            # parts[2] may contain filepath and optional description - try to split sensibly
            rest = parts[2].strip()
            # if description provided, we expect: "<filepath> <description...>"
            subparts = rest.split(" ", 1)
            filepath = subparts[0]
            desc = subparts[1] if len(subparts) == 2 else ""
            send_file_offer(parts[1], filepath, desc)

    elif cmd.startswith("fileaccept "):
        try:
            _, fileid = cmd.split(" ", 1)
            fileid = fileid.strip()
            fileaccept_cmd(fileid)
        except ValueError:
            print("Usage: fileaccept <fileid>")

    elif cmd == "fileoffers":
        if not pending_file_offers:
            print("No pending file offers.")
        else:
            print("--- Pending File Offers ---")
            for fid, meta in pending_file_offers.items():
                sender = meta["from"]
                fname = meta["filename"]
                fsize = meta["filesize"]
                desc = meta.get("description", "")
                print(f"- {fid}: {fname} ({fsize} bytes) from {sender} - {desc}")

    elif cmd == "exit":
        print("Goodbye!")
        break
    
    elif cmd == "":
        continue

    else:
        print("Unknown command. Type 'help' for list.")