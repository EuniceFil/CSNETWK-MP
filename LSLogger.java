import java.text.SimpleDateFormat;
import java.util.Date;

public class LSLogger {
    private static boolean verboseEnabled = false;

    // Enable or disable verbose mode
    public static void enableVerbose() {
        verboseEnabled = true;
    }

    public static void disableVerbose() {
        verboseEnabled = false;
    }

    public static boolean isVerboseEnabled() {
        return verboseEnabled;
    }

    // Timestamp formatter
    private static String timestamp() {
        return "[" + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date()) + "]";
    }

    // General logging methods
    public static void info(String message) {
        System.out.println(timestamp() + " INFO > " + message);
    }

    public static void warn(String message) {
        System.out.println(timestamp() + " " + "WARN !" + " " + message);
    }

    public static void error(String message) {
        System.err.println(timestamp() + " " + "ERROR !" + " " + message);
    }

    // Scoped logging methods
    public static void send(String messageType, String ip, String fullMessage) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + "SEND >" + " [" + messageType + "] " + ip);
            System.out.println(indent(fullMessage));
        }
    }

    public static void recv(String messageType, String ip, String fullMessage) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + "RECV <" + " [" + messageType + "] " + ip);
            System.out.println(indent(fullMessage));
        }
    }

    public static void drop(String reason, String ip) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + "DROP !" + " from " + ip + " (" + reason + ")");
        }
    }

    public static void token(String status, String details) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + "[TOKEN] " + status + " - " + details);
        }
    }

    public static void retry(String action, int attempt) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + "[RETRY]" + " " + action + " attempt #" + attempt);
        }
    }

    // Utility to indent multiline messages
    private static String indent(String text) {
        return "    " + text.trim().replaceAll("\n", "\n    ");
    }
}
