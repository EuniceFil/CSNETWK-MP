import socket
import threading
import time
import uuid
import sys

# === Configuration ===
PORT = 50999
BROADCAST_ADDR = '255.255.255.255'
USERNAME = sys.argv[1] if len(sys.argv) >= 2 else "Anonymous"
# --- Constant for the broadcast interval ---
PROFILE_BROADCAST_INTERVAL = 30 # 1 min

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
# --- MODIFIED: Renamed 'status' to 'bio' for consistency with your commands ---
my_profile_data = {
    "name": USERNAME,
    "bio": "Just another peer on LSNP."
}
# === Tic-Tac-Toe State ===
active_games = {} # Stores game instances by GAMEID
game_id_counter = 0
dm_history = {}
pending_acks = {}
revoked_tokens = set()

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
        winning_lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
                         (0, 3, 6), (1, 4, 7), (2, 5, 8),
                         (0, 4, 8), (2, 4, 6)]
        for line in winning_lines:
            if self.board[line[0]] == self.board[line[1]] == self.board[line[2]] != ' ':
                return self.board[line[0]], line
        if ' ' not in self.board:
            return 'DRAW', None
        return None, None

    def make_move(self, position, symbol):
        if self.board[position] == ' ':
            self.board[position] = symbol
            self.turn += 1
            return True
        return False

# === Tokens ===
def generate_token(user_id, ttl=3600, scope="broadcast"):
    timestamp = int(time.time())
    return f"{user_id}|{timestamp + ttl}|{scope}"

def validate_token(token, expected_scope, sender_id):
    """
    Validates a token based on the LSNP RFC rules.
    Checks format, scope, expiration, and revocation list.
    """
    try:
        # 1. Check the token's structure: user_id|expiration_timestamp|scope
        token_user, token_exp, token_scope = token.split('|')
        
        # 2. Check if the sender matches the token's owner
        if token_user != sender_id:
            print(f"[AUTH-FAIL] Token owner ({token_user}) does not match sender ({sender_id}).")
            return False
            
        # 3. Check if the token has the correct scope for the action
        if token_scope != expected_scope:
            print(f"[AUTH-FAIL] Invalid token scope. Expected '{expected_scope}', got '{token_scope}'.")
            return False
            
        # 4. Check for expiration
        if int(token_exp) < time.time():
            print(f"[AUTH-FAIL] Expired token from {sender_id}.")
            return False
            
        # 5. Check against the revocation list
        if token in revoked_tokens:
            print(f"[AUTH-FAIL] Revoked token received from {sender_id}.")
            return False
            
        # If all checks pass, the token is valid
        return True

    except (ValueError, IndexError):
        # Catches errors from a malformed token string (e.g., wrong number of '|')
        print(f"[AUTH-FAIL] Malformed token received from {sender_id}.")
        return False

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

def broadcast_profile():
    profile_msg = {
        "type": "PROFILE",
        "user_id": MY_ID,
        "name": my_profile_data["name"],
        "bio": my_profile_data["bio"]
    }
    send_message(profile_msg, (BROADCAST_ADDR, PORT))

def send_post_to_followers(content):

    # Sends a post individually to each known follower.

    if not followers:
        return print("[POST] You have no followers to post to.")

    print(f"[POST] Sending post to {len(followers)} follower(s)...")
    
    # Create the base message once
    post_msg = {
        "type": "POST",
        "user_id": MY_ID,
        "content": content,
        "ttl": "3600",
        "message_id": str(uuid.uuid4().hex), #random
        "token": generate_token(MY_ID, scope="post")
    }

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
        "symbol": opponent_symbol,
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
        if not (0 <= position <= 8):
            print("Error: Position must be an integer between 0 and 8.")
            return
        
        if not game.make_move(position, game.my_symbol):
            print("Error: That position is already taken.")
            return

    except ValueError:
        print("Error: Position must be a number.")
        return

    # Check for a winner or draw
    winner, winning_line = game.check_winner()
    
    # Send the move
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
    
    target_addr = peers.get(game.opponent_id)
    if target_addr:
        send_message(move_msg, target_addr)
        game.is_my_turn = False
        game.display_board()

    # If the game is over, send a result message
    if winner:
        send_result(game_id, winner, winning_line)
        del active_games[game_id] # Game is finished, remove it

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

    target_addr = peers.get(game.opponent_id)
    if target_addr:
        send_message(result_msg, target_addr)
        
    print(f"\n[TICTACTOE] Game {game_id} finished. Result: {result}.")
    print(f"> ", end="", flush=True)

# --- "ignore self" logic ---
def handle_message(data, addr):
    sender_id = data.get("user_id") or data.get("from")

    # This check is critical to prevent processing your own messages
    if sender_id == MY_ID:
        return
    
    packet_sender_addr = addr

    mtype = data.get("type", "").upper()
    message_id = data.get("message_id")

    if mtype in ["FOLLOW", "UNFOLLOW"] and message_id:
        # These are critical requests, so we ACK them.
        ack_msg = {"type": "ACK", "message_id": message_id, "status": "RECEIVED"}
        send_message(ack_msg, addr)

    if mtype == "FOLLOW":
        from_id = data.get("from")
        to_id = data.get("to")
        if to_id == MY_ID and from_id and message_id:
            followers.add(from_id)
            peers[from_id] = (addr[0], PORT)
            print(f"\n[FOLLOW] {from_id} is now following you.")
            ack_msg = {"type": "ACK", "message_id": message_id, "status": "RECEIVED"}
            send_message(ack_msg, (addr[0], PORT))

    elif mtype == "UNFOLLOW":
        from_id = data.get("from")
        to_id = data.get("to")
        if to_id == MY_ID and from_id in followers and message_id:
            followers.remove(from_id)
            print(f"\n[UNFOLLOW] {from_id} has unfollowed you.")
            ack_msg = {"type": "ACK", "message_id": message_id, "status": "RECEIVED"}
            send_message(ack_msg, (addr[0], PORT))

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

    elif mtype == "PROFILE":
        name = data.get("name", "")
        bio = data.get("bio", "")
        if sender_id:
            known_profiles[sender_id] = (name, bio)
            peers[sender_id] = (addr[0], PORT)
            print(f"\n[PROFILE] {sender_id}: {name} | {bio}")

    elif mtype == "POST":
        content = data.get("content", "")
        # CORRECT LOGIC: Display the post ONLY if you are following the sender.
        if sender_id:
            name = known_profiles.get(sender_id, [sender_id])[0]
            print(f"\n[POST from {name}]: {content}")
    
    # === Tic-Tac-Toe Message Handlers ===
    elif mtype == "TICTACTOE_INVITE":
        from_id = data.get("from")
        to_id = data.get("to")
        game_id = data.get("gameid")
        symbol = data.get("symbol")
        
        if to_id == MY_ID:
            print(f"\n{from_id.split('@')[0]} is inviting you to play tic-tac-toe.") # e.g. alice is inviting you to play tic-tac-toe.
            print(f"SYMBOL: '{symbol}'. Use 'ttaccept {game_id} <position>' to accept and make your first move.")
            
            opponent_symbol = 'X' if symbol == 'O' else 'O'
            is_my_turn = (symbol == 'X')
            
            # Create a game instance for the inviter
            active_games[game_id] = TicTacToeGame(game_id, from_id, symbol, opponent_symbol, is_my_turn)

    elif mtype == "TICTACTOE_MOVE":
        from_id = data.get("from")
        to_id = data.get("to")
        game_id = data.get("gameid")
        position = int(data.get("position"))
        symbol = data.get("symbol")
        turn = int(data.get("turn"))

        if to_id == MY_ID:
            game = active_games.get(game_id)
            if not game:
                print(f"\n[TICTACTOE] Received move for unknown game {game_id}. Ignoring.")
                return

            game.make_move(position, symbol)
            game.is_my_turn = True
            
            winner, winning_line = game.check_winner()
            
            game.display_board()
            
            if winner:
                # The game is over, we send the result back
                send_result(game_id, winner, winning_line)
                del active_games[game_id]
                
    elif mtype == "TICTACTOE_RESULT":
        from_id = data.get("from")
        to_id = data.get("to")
        game_id = data.get("gameid")
        result = data.get("result")
        winning_line = data.get("winning_line")
        
        if to_id == MY_ID:
            game = active_games.get(game_id)
            if not game:
                print(f"\n[TICTACTOE] Received result for unknown game {game_id}. Ignoring.")
                return
            
            if result == "WIN":
                print("\nYou won.")
            elif result == "LOSE":
                print("\nYou lost.")
            elif result == "DRAW":
                print("\nDraw.")
            del active_games[game_id]

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
            # This is a safe way to handle potential errors without crashing the thread
            sys.stderr.write(f"\nError handling message: {e}\n")
            sys.stderr.flush()

# --- The periodic broadcaster function ---
def periodic_broadcaster():
    """This function runs in a separate thread to send profile updates."""
    last_profile_time = 0  # Track the last time a PROFILE was sent

    while True:
        # Wait for the interval THEN broadcast, so we don't spam on startup
        time.sleep(PROFILE_BROADCAST_INTERVAL)

        now = time.time()
        if now - last_profile_time >= 300:
            print("\n[Auto-Profile] Broadcasting profile...")
            broadcast_profile()
            last_profile_time = now
        else:
            print("\n[Auto-Discovery] Broadcasting PING...")
            ping_msg = {
                "type": "PING",
                "user_id": MY_ID
            }
            send_message(ping_msg, (BROADCAST_ADDR, PORT))

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
        print("  peers                     - List known peers")
        print("  profile set <name|bio> <value> - Update your profile name or bio")
        print("  post <message>            - Send a post to followers")
        print("  follow <user_id>          - Follow a user")
        print("  unfollow <user_id>        - Unfollow a user")
        print("  following                 - List users you are following")
        print("  followers                 - List your followers")
        print("  dm <user_id> <message>    - Send a private message")
        print("  dms [user_id]             - View DM history")
        print("  ttinvite <user_id> <X|O>  - Invite a user to a tic-tac-toe game")
        print("  ttmove <gameid> <position>- Make a move in an active game")
        print("  ttaccept <gameid> <pos>   - Accept an invite and make your first move")
        print("  ttgames                   - List active games")
        print("  exit                      - Quit")

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
        try:
            _, content = cmd.split(" ", 1)
            send_post_to_followers(content.strip()) 
        except ValueError:
            print("Usage: post <message>")

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

    # --- MODIFIED: Improved output to show full profile ---
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

    elif cmd == "exit":
        print("Goodbye!")
        break
    
    elif cmd == "":
        continue

    else:
        print("Unknown command. Type 'help' for list.")