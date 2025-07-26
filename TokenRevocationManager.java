import java.util.HashSet;
import java.util.Set;

public class TokenRevocationManager {
    private static final Set<String> revokedTokens = new HashSet<>();

    public static void revoke(String token) {
        revokedTokens.add(token);
    }

    public static boolean isRevoked(String token) {
        return revokedTokens.contains(token);
    }
}