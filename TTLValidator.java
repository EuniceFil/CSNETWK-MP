import java.util.Map;

public class TTLValidator {
    public static boolean isValid(Map<String, String> msgFields) {
        try {
            long timestamp = Long.parseLong(msgFields.get("TIMESTAMP"));
            int ttl = Integer.parseInt(msgFields.get("TTL"));
            long now = System.currentTimeMillis() / 1000; // current UNIX timestamp in seconds

            return (timestamp + ttl) > now;
        } catch (Exception e) {
            return false;
        }
    }
}
