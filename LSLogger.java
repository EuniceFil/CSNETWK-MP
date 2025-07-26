import java.text.SimpleDateFormat;
import java.util.Date;

public class LSLogger {
    private static boolean verboseEnabled = false;

    // ANSI color codes (optional)
    private static final String RESET = "\u001B[0m";
    private static final String GRAY = "\u001B[90m";
    private static final String GREEN = "\u001B[32m";
    private static final String BLUE = "\u001B[34m";
    private static final String RED = "\u001B[31m";
    private static final String YELLOW = "\u001B[33m";

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
        System.out.println(timestamp() + " " + YELLOW + "WARN !" + RESET + " " + message);
    }

    public static void error(String message) {
        System.err.println(timestamp() + " " + RED + "ERROR !" + RESET + " " + message);
    }

    // Scoped logging methods
    public static void send(String messageType, String ip, String fullMessage) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + GREEN + "SEND >" + RESET + " [" + messageType + "] " + ip);
            System.out.println(indent(fullMessage));
        }
    }

    public static void recv(String messageType, String ip, String fullMessage) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + BLUE + "RECV <" + RESET + " [" + messageType + "] " + ip);
            System.out.println(indent(fullMessage));
        }
    }

    public static void drop(String reason, String ip) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + RED + "DROP !" + RESET + " from " + ip + " (" + reason + ")");
        }
    }

    public static void token(String status, String details) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + GRAY + "[TOKEN] " + status + RESET + " - " + details);
        }
    }

    public static void retry(String action, int attempt) {
        if (verboseEnabled) {
            System.out.println(timestamp() + " " + YELLOW + "[RETRY]" + RESET + " " + action + " attempt #" + attempt);
        }
    }

    // Utility to indent multiline messages
    private static String indent(String text) {
        return "    " + text.trim().replaceAll("\n", "\n    ");
    }
}
