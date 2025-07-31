import java.time.Instant;
import java.util.UUID;

public class LSMessageBuilder {

    /**
     * Creates a PROFILE message to announce a user's identity.
     *
     * @param userId The unique user ID in username@ipaddress format.
     * @param displayName The user's public display name.
     * @param status The user's current status or mood message. Can be null.
     * @param avatarData The Base64-encoded string of the avatar image. Can be null.
     * @param avatarType The MIME type of the avatar (e.g., "image/png"). Can be null.
     * @return A formatted LSNP PROFILE message string.
     */
    public static String createProfile(String userId, String displayName, String status, String avatarData, String avatarType) {
        StringBuilder builder = new StringBuilder();
        builder.append("TYPE: PROFILE\n");
        builder.append("USER_ID: ").append(userId).append("\n");
        builder.append("DISPLAY_NAME: ").append(displayName).append("\n");

        // Add optional fields only if they are provided
        if (status != null && !status.isEmpty()) {
            builder.append("STATUS: ").append(status).append("\n");
        }

        if (avatarData != null && !avatarData.isEmpty() && avatarType != null && !avatarType.isEmpty()) {
            builder.append("AVATAR_TYPE: ").append(avatarType).append("\n");
            builder.append("AVATAR_ENCODING: base64\n");
            builder.append("AVATAR_DATA: ").append(avatarData).append("\n");
        }

        builder.append("\n"); // Message terminator
        return builder.toString();
    }
    
    /**
     * Overloaded method for creating a PROFILE message without an avatar.
     */
    public static String createProfile(String userId, String displayName, String status) {
        return createProfile(userId, displayName, status, null, null);
    }

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

    // public static String createDM(String from, String to, String content) {
    //     long timestamp = System.currentTimeMillis() / 1000;
    //     int ttl = 3600;
    //     String token = from + "|" + (timestamp + ttl) + "|chat";
    //     String messageId = LSIPUtils.generateMessageId();
    //     return String.join("\n",
    //         "TYPE: DM",
    //         "FROM: " + from,
    //         "TO: " + to,
    //         "CONTENT: " + content,
    //         "TIMESTAMP: " + timestamp,
    //         "MESSAGE_ID: " + messageId,
    //         "TOKEN: " + token,
    //         ""
    //     );
    // }
}
