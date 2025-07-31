import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

public class LSDatagramReceiver {
    private static final int PORT = 50999;
    private static final int BUFFER_SIZE = 8192;
    private static volatile String selfUserId = null;

    // This Set contains all message types that DO NOT require a token.
    // We will check against this list before attempting token validation.
    private static final Set<String> NO_TOKEN_REQUIRED = new HashSet<>(Arrays.asList(
        "PROFILE", "PING", "ACK", "FILE_RECEIVED", "TICTACTOE_RESULT"
    ));

    // Allows LSMain to tell the receiver who it is
    public static void setSelfUserId(String userId) {
        selfUserId = userId;
    }

    public static void startListening() throws Exception {
        DatagramSocket socket = null; 
        try {
            // 1. Create the socket but DO NOT bind it yet.
            socket = new DatagramSocket(null); 
            
            // 2. Set the "Reuse Address" option. This is the magic line.
            // It allows multiple processes to bind to the same address/port.
            socket.setReuseAddress(true); 
            
            // 3. NOW, bind the socket to the port.
            socket.bind(new java.net.InetSocketAddress(PORT));
            socket.setBroadcast(true);
            LSLogger.info("Listening for LSNP messages on port " + PORT + "...");

            byte[] buffer = new byte[BUFFER_SIZE];

            while (!Thread.currentThread().isInterrupted()) {
                try { 
                    DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                    socket.receive(packet); // Wait for a message

                    String message = new String(packet.getData(), 0, packet.getLength(), StandardCharsets.UTF_8);
                    //String localIP = LSIPUtils.getLocalIPAddress().getHostAddress();

                    // --- Consolidated Validation Pipeline ---

                    // 1. Find the sender's ID (if it exists)
                    String senderId = extractField(message, "USER_ID");
                    if (senderId == null) {
                        senderId = extractField(message, "FROM");
                    }

                    // 2. IGNORE SELF: The most reliable check. If we know who we are
                    //    and the message is from us, drop it immediately.
                    if (selfUserId != null && selfUserId.equals(senderId)) {
                        continue;
                    }

                    // 3. Get packet info
                    String senderIP = packet.getAddress().getHostAddress();
                    String type = extractField(message, "TYPE");

                    if (type == null) {
                        LSLogger.warn("Dropped message: Missing TYPE field from " + senderIP);
                        continue;
                    }

                    // 4. SPOOF CHECK: Perform on all messages that aren't PINGs from localhost
                    // This avoids the warning when testing on one machine.
                    if (!"PING".equalsIgnoreCase(type)) {
                         if (!isSenderAuthentic(message, senderIP)) {
                            continue;
                         }
                    }

                    // 5. TOKEN CHECK: Perform only on messages that require tokens.
                    if (!NO_TOKEN_REQUIRED.contains(type.toUpperCase())) {
                        if (!isTokenValid(message, type)) {
                            continue;
                        }
                    }

                    // --- All Checks Passed ---
                    LSLogger.recv(type, senderIP, message);

                    // --- Message Handling ---

                    switch (type.toUpperCase()) {
                        case "POST":
                            String postUser = extractField(message, "USER_ID");
                            String postContent = extractField(message, "CONTENT");
                            System.out.println("\n[POST from " + postUser + "]: " + postContent);
                            break;

                        case "PROFILE":
                             String profileUser = extractField(message, "USER_ID");
                             String displayName = extractField(message, "DISPLAY_NAME");
                             String status = extractField(message, "STATUS");
                             System.out.println("\n[PROFILE from " + profileUser + "]: " + displayName + " is " + (status != null ? status : "here") + ".");
                             break;

                        // Add this case to silently and correctly handle PING messages.
                        case "PING":
                            // According to the spec, we do nothing for a PING.
                            // It's just a heartbeat to know the peer is alive.
                            break;
                        // case "DM":
                        //     String dmFrom = extractField(message, "FROM");
                        //     String dmTo = extractField(message, "TO");
                        //     String dmContent = extractField(message, "CONTENT");
                        //     System.out.println("\n[DM] " + dmFrom + " → " + dmTo + ": " + dmContent);
                        //     break;

                        // case "TICTACTOE_INVITE":
                        //     String from = extractField(message, "FROM");
                        //     String to = extractField(message, "TO");
                        //     String gameId = extractField(message, "GAMEID");
                        //     String symbol = extractField(message, "SYMBOL");
                        //     TicTacToeManager.handleInvite(gameId, from, symbol, to);
                        //     break;

                        // case "TICTACTOE_MOVE":
                        //     String moveGameId = extractField(message, "GAMEID");
                        //     String moveSymbol = extractField(message, "SYMBOL");
                        //     int pos = Integer.parseInt(extractField(message, "POSITION"));
                        //     int turn = Integer.parseInt(extractField(message, "TURN"));
                        //     TicTacToeManager.handleMove(moveGameId, moveSymbol, pos, turn);
                        //     break;

                        // case "TICTACTOE_RESULT":
                        //     String resGameId = extractField(message, "GAMEID");
                        //     String result = extractField(message, "RESULT");
                        //     String winningLine = extractField(message, "WINNING_LINE");
                        //     String winSymbol = extractField(message, "SYMBOL");
                        //     TicTacToeManager.handleResult(resGameId, result, winningLine, winSymbol);
                        //     break;

                        default:
                            LSLogger.info("Unhandled TYPE: " + type);
                    }
                } catch (Exception e) {
                    LSLogger.warn("Receiver error: " + e.getMessage());
                }
            }
        } catch (Exception e) {
            LSLogger.warn("Receiver failed to start: " + e.getMessage());
        }
    }

    /**
     * Checks if the sender's declared IP matches their actual IP.
     * This prevents spoofing.
     *
     * @param message The raw LSNP message.
     * @param actualSenderIP The actual IP address of the packet sender.
     * @return true if the sender is authentic, false otherwise.
     */
    private static boolean isSenderAuthentic(String message, String actualSenderIP) {
        String declaredSenderId = extractField(message, "USER_ID");
        if (declaredSenderId == null) {
            declaredSenderId = extractField(message, "FROM");
        }
        if (declaredSenderId == null) {
            return true; // No sender to check (e.g., ACK)
        }
        if (!declaredSenderId.contains("@")) {
             return false; // Malformed ID
        }

        // The only time we allow a mismatch is for the localhost case (127.0.0.1)
        String declaredIP = declaredSenderId.split("@", 2)[1];
        if (!declaredIP.equals(actualSenderIP)) {
            // If the IPs don't match, check if it's the specific localhost-to-LAN IP mismatch
            if (actualSenderIP.equals("127.0.0.1")) {
                return true; // It's a localhost reflection, allow it.
            }
            LSLogger.warn("Spoof detected: ID says <" + declaredSenderId + ">, but IP is <" + actualSenderIP + ">");
            return false;
        }
        return true;
    }

    /**
     * Validates the token in a message.
     * Checks for presence, expiration, and revocation.
     *
     * @param message The raw LSNP message.
     * @param type The type of the message, used for logging.
     * @return true if the token is valid, false otherwise.
     */
    private static boolean isTokenValid(String message, String type) {
        String token = extractField(message, "TOKEN");
        if (token == null) {
            LSLogger.warn("Dropped " + type + " message: Missing TOKEN field.");
            return false;
        }

        // Check 1: Revocation. Do this first to quickly reject known bad tokens.
        if (TokenRevocationManager.isRevoked(token)) {
            LSLogger.warn("Dropped " + type + " message: Token has been revoked.");
            return false;
        }

        LSTokenUtils.TokenInfo tokenInfo = LSTokenUtils.parseToken(token);
        if (tokenInfo == null) {
            LSLogger.warn("Dropped " + type + " message: Invalid token format.");
            return false;
        }

        // Check 2: Expiration
        if (LSTokenUtils.isTokenExpired(tokenInfo)) { // This method should now take the TokenInfo object
            LSLogger.warn("Dropped " + type + " message: Token is expired.");
            return false;
        }

        // Check 3: Scope
        String expectedScope = null;
        String upperType = type.toUpperCase();
        if (upperType.equals("POST") || upperType.equals("LIKE")) expectedScope = "broadcast";
        else if (upperType.equals("DM") || upperType.equals("REVOKE")) expectedScope = "chat";
        else if (upperType.startsWith("FILE_")) expectedScope = "file";
        else if (upperType.startsWith("GROUP_")) expectedScope = "group";
        else if (upperType.startsWith("TICTACTOE_")) expectedScope = "game";

        if (expectedScope != null && !tokenInfo.scope.equals(expectedScope)) {
            LSLogger.warn("Dropped " + type + " message: Token scope mismatch. Expected '" + expectedScope + "' but got '" + tokenInfo.scope + "'.");
            return false;
        }

        return true; // Token is valid!
    }

    private static String extractField(String message, String key) {
        for (String line : message.strip().split("\n")) {
            if (line.startsWith(key + ":")) {
                return line.split(":", 2)[1].trim();
            }
        }
        return "[MISSING]";
    }
}