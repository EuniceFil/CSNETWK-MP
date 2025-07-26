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
                continue; // skip processing the very first incoming message
            }
            
            String actualSenderIP = packet.getAddress().getHostAddress();
            String type = extractField(msg, "TYPE");

            if (!"POST".equals(type)) {
                String declaredFrom = extractField(msg, "FROM");
                if (declaredFrom == null || !declaredFrom.contains(actualSenderIP)) {
                    LSLogger.warn("Spoof detected: FROM field says " + declaredFrom + ", but packet came from " + actualSenderIP);
                    continue;
                }
            }

            LSLogger.recv(type, actualSenderIP, msg); // log full message in verbose mode
            
            // === Begin TTL and Token Validation ===
            String ttlStr = extractField(msg, "TTL");
            String token = extractField(msg, "TOKEN"); 
            
            if ("[MISSING]".equals(ttlStr)) {
                LSLogger.warn("Dropped message: Missing TTL.");
                continue;
            }

            if ("[MISSING]".equals(token)) {
                LSLogger.warn("Dropped message: Missing TOKEN.");
                continue;
            }

            // Validate TTL
            long now = System.currentTimeMillis() / 1000;
            try {
                long ttl = Long.parseLong(ttlStr);
                if (now > ttl) {
                    LSLogger.warn("Dropped message: TTL expired.");
                    continue;
                }
            } catch (Exception e) {
                LSLogger.warn("Dropped message: Invalid TTL format.");
                continue;
            }

            // Validate token
            LSTokenUtils.TokenInfo info = LSTokenUtils.parseToken(token);
            if (info == null) {
                LSLogger.warn("Dropped message: Invalid token format.");
                continue;
            }

            if (TokenRevocationManager.isRevoked(token)) {
                LSLogger.warn("Dropped message: Token is revoked.");
                continue;
            }

            String expectedScope =
                type.equalsIgnoreCase("POST") || type.equalsIgnoreCase("LIKE") ? "broadcast" :
                type.equalsIgnoreCase("DM") || type.equalsIgnoreCase("REVOKE") ? "chat" :
                type.startsWith("FILE_") ? "file" :
                type.startsWith("GROUP_") ? "group" :
                type.startsWith("TICTACTOE_") ? "game" :
                null; // No expected scope for unknown types

            if (expectedScope != null && !info.scope.equals(expectedScope)) {
                LSLogger.warn("Dropped message: Token scope mismatch (expected " + expectedScope + ").");
                continue;
            }

            if (now > info.expiry) {
                LSLogger.warn("Dropped message: Token expired.");
                continue;
            }

            // === End TTL and Token Validation ===

            if (type.equalsIgnoreCase("POST")) {
                String userId = extractField(msg, "USER_ID");
                String content = extractField(msg, "CONTENT");
                System.out.println("\n [POST] " + userId + ": " + content);
            } else if (type.equalsIgnoreCase("DM")) {
                String from = extractField(msg, "FROM");
                String to = extractField(msg, "TO");
                String content = extractField(msg, "CONTENT");
                System.out.println("\n [DM] " + from + ": " + content);
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