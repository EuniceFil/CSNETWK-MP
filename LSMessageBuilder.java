import java.time.Instant;
import java.util.UUID;

public class LSMessageBuilder {
    public static String createPost(String userId, String content, String token, int ttlSeconds) {
        long timestamp = Instant.now().getEpochSecond(); // current time in seconds
        long ttl = (System.currentTimeMillis() / 1000) + ttlSeconds; // TTL in UNIX time (e.g., 300 seconds from now)
        String messageId = UUID.randomUUID().toString().replace("-", "").substring(0, 8); // 64-bit hex (8 bytes)
        StringBuilder builder = new StringBuilder();
        builder.append("TYPE: POST\n");
        builder.append("USER_ID: ").append(userId).append("\n");
        builder.append("CONTENT: ").append(content).append("\n");
        builder.append("TTL: ").append(ttl).append("\n"); // ✅ Include TTL here
        builder.append("MESSAGE_ID: ").append(messageId).append("\n");
        builder.append("TOKEN: ").append(token).append("\n");
        builder.append("TIMESTAMP: ").append(timestamp).append("\n");
        builder.append("\n");
        return builder.toString();
    }

    public static String createDM(String from, String to, String content) {
        long timestamp = System.currentTimeMillis() / 1000;
        int ttl = 3600;
        String token = from + "|" + (timestamp + ttl) + "|chat";
        String messageId = LSIPUtils.generateMessageId();
        return String.join("\n",
            "TYPE: DM",
            "FROM: " + from,
            "TO: " + to,
            "CONTENT: " + content,
            "TIMESTAMP: " + timestamp,
            "MESSAGE_ID: " + messageId,
            "TOKEN: " + token,
            ""
        );
    }
}
