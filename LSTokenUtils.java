public class LSTokenUtils {
    public static class TokenInfo {
        public final String userId;
        public final long expiry;
        public final String scope;

        public TokenInfo(String userId, long expiry, String scope) {
            this.userId = userId;
            this.expiry = expiry;
            this.scope = scope;
        }
    }

    public static TokenInfo parseToken(String token) {
        try {
            String[] parts = token.split("\\|");
            if (parts.length != 3) return null;
            String userId = parts[0];
            long expiry = Long.parseLong(parts[1]);
            String scope = parts[2];
            return new TokenInfo(userId, expiry, scope);
        } catch (Exception e) {
            return null;
        }
    }

    public static boolean isTokenExpired(TokenInfo tokenInfo) {
        if (tokenInfo == null) return true;
        long currentTime = System.currentTimeMillis() / 1000;
        return currentTime > tokenInfo.expiry;
    }

    public static String generateBroadcastToken(String userId, int ttlSeconds) {
        long currentTimestamp = System.currentTimeMillis() / 1000; // Convert to Unix time (seconds)
        long expiryTimestamp = currentTimestamp + ttlSeconds;
        String scope = "broadcast";
        return userId + "|" + expiryTimestamp + "|" + scope;
    }

}