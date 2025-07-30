import java.net.*;
import java.nio.charset.StandardCharsets;

public class LSDatagramReceiver {
    private static final int PORT = 50999;
    private static final int BUFFER_SIZE = 8192;

    public static void startListening() throws Exception {
        DatagramSocket socket = new DatagramSocket(PORT);
        socket.setBroadcast(true);
        byte[] buffer = new byte[BUFFER_SIZE];

        LSLogger.info("Listening for LSNP messages on port " + PORT + "...");

        boolean isFirstMessage = true;

        while (true) {
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            socket.receive(packet);

            String msg = new String(packet.getData(), 0, packet.getLength(), StandardCharsets.UTF_8);
            
            if (isFirstMessage) {
                isFirstMessage = false;
                continue; // Skip first broadcasted ping
            }

            String actualSenderIP = packet.getAddress().getHostAddress();
            String type = extractField(msg, "TYPE");

            if (!"POST".equalsIgnoreCase(type)) {
                String declaredFrom = extractField(msg, "FROM");
                if (declaredFrom == null || !declaredFrom.contains(actualSenderIP)) {
                    LSLogger.warn("Spoof detected: FROM field says " + declaredFrom + ", but IP is " + actualSenderIP);
                    continue;
                }
            }

            LSLogger.recv(type, actualSenderIP, msg);

            // === Token & TTL Validation ===
            String ttlStr = extractField(msg, "TTL");
            String token = extractField(msg, "TOKEN");

            if ("[MISSING]".equals(ttlStr) || "[MISSING]".equals(token)) {
                LSLogger.warn("Dropped message: Missing TTL or TOKEN.");
                continue;
            }

            long now = System.currentTimeMillis() / 1000;
            long ttl;
            try {
                ttl = Long.parseLong(ttlStr);
                if (now > ttl) {
                    LSLogger.warn("Dropped message: TTL expired.");
                    continue;
                }
            } catch (Exception e) {
                LSLogger.warn("Dropped message: Invalid TTL format.");
                continue;
            }

            LSTokenUtils.TokenInfo tokenInfo = LSTokenUtils.parseToken(token);
            if (tokenInfo == null) {
                LSLogger.warn("Dropped message: Invalid token format.");
                continue;
            }

            if (now > tokenInfo.expiry) {
                LSLogger.warn("Dropped message: Token expired.");
                continue;
            }

            if (TokenRevocationManager.isRevoked(token)) {
                LSLogger.warn("Dropped message: Token has been revoked.");
                continue;
            }

            String expectedScope =
                type.equalsIgnoreCase("POST") || type.equalsIgnoreCase("LIKE") ? "broadcast" :
                type.equalsIgnoreCase("DM") || type.equalsIgnoreCase("REVOKE") ? "chat" :
                type.startsWith("FILE_") ? "file" :
                type.startsWith("GROUP_") ? "group" :
                type.startsWith("TICTACTOE_") ? "game" :
                null;

            if (expectedScope != null && !tokenInfo.scope.equals(expectedScope)) {
                LSLogger.warn("Dropped message: Token scope mismatch. Expected " + expectedScope + " but got " + tokenInfo.scope);
                continue;
            }

            // === Valid message: Dispatch by TYPE ===
            switch (type.toUpperCase()) {
                case "POST":
                    String postUser = extractField(msg, "USER_ID");
                    String postContent = extractField(msg, "CONTENT");
                    System.out.println("\n[POST] " + postUser + ": " + postContent);
                    break;

                case "DM":
                    String dmFrom = extractField(msg, "FROM");
                    String dmTo = extractField(msg, "TO");
                    String dmContent = extractField(msg, "CONTENT");
                    System.out.println("\n[DM] " + dmFrom + " → " + dmTo + ": " + dmContent);
                    break;

                case "TICTACTOE_INVITE":
                    String from = extractField(msg, "FROM");
                    String to = extractField(msg, "TO");
                    String gameId = extractField(msg, "GAMEID");
                    String symbol = extractField(msg, "SYMBOL");
                    TicTacToeManager.handleInvite(gameId, from, symbol, to);
                    break;

                case "TICTACTOE_MOVE":
                    String moveGameId = extractField(msg, "GAMEID");
                    String moveSymbol = extractField(msg, "SYMBOL");
                    int pos = Integer.parseInt(extractField(msg, "POSITION"));
                    int turn = Integer.parseInt(extractField(msg, "TURN"));
                    TicTacToeManager.handleMove(moveGameId, moveSymbol, pos, turn);
                    break;

                case "TICTACTOE_RESULT":
                    String resGameId = extractField(msg, "GAMEID");
                    String result = extractField(msg, "RESULT");
                    String winningLine = extractField(msg, "WINNING_LINE");
                    String winSymbol = extractField(msg, "SYMBOL");
                    TicTacToeManager.handleResult(resGameId, result, winningLine, winSymbol);
                    break;

                default:
                    LSLogger.info("Unhandled TYPE: " + type);
            }
        }
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
