import java.net.InetAddress;
import java.util.Scanner;

public class LSMain {

    public static boolean VERBOSE = false;
    public static void main(String[] args) throws Exception {

        for (String arg : args) {
            if ("--verbose".equals(arg)) {
                VERBOSE = true;
                System.out.println("[INFO] Verbose mode enabled.");
            }
        }

        // Start listening thread
        Thread listener = new Thread(() -> {
            try {
                LSDatagramReceiver.startListening();
            } catch (Exception e) {
                LSLogger.warn("Receiver crashed: " + e.getMessage());
            }
        });
        listener.start();

        // Wait briefly then send test PING
        Thread.sleep(2000);

        String localIP = LSIPUtils.getLocalIPAddress().getHostAddress();
        String pingMessage = "TYPE: PING\nFROM: " + localIP + "\n\n";
        LSDatagramSender.sendBroadcast(pingMessage);

        Scanner scanner = new Scanner(System.in);
        System.out.print("Enter your USER_ID (e.g., dave@192.168.1.10): ");
        String userId = scanner.nextLine();

        while (true) {
            System.out.println("Choose an action: [post] [dm] [raw] [exit]");
            String command = scanner.nextLine().trim();

            if (command.equalsIgnoreCase("post")) {
                System.out.print("Enter message content: ");
                String content = scanner.nextLine();

                System.out.print("Enter TTL in seconds (or press Enter for default 3600): ");
                String ttlInput = scanner.nextLine();
                int ttl = ttlInput.isEmpty() ? 3600 : Integer.parseInt(ttlInput);

                String token = LSTokenUtils.generateBroadcastToken(userId, ttl); 
                String postMsg = LSMessageBuilder.createPost(userId, content, token, ttl);
                LSDatagramSender.sendBroadcast(postMsg);
            } 
            else if (command.equalsIgnoreCase("dm")) {
                System.out.print("Enter recipient (e.g., bob@192.168.1.20): ");
                String to = scanner.nextLine();
                System.out.print("Enter message content: ");
                String content = scanner.nextLine();
                System.out.print("Enter recipient IP (e.g., 192.168.1.20): ");
                InetAddress ip = InetAddress.getByName(scanner.nextLine());

                String dm = LSMessageBuilder.createDM(userId, to, content);
                LSDatagramSender.sendCustomMessage(dm, ip);
            } 
            else if (command.equalsIgnoreCase("raw")) {
                System.out.println("Enter raw message, finish with an empty line:");
                StringBuilder sb = new StringBuilder();
                while (true) {
                    String line = scanner.nextLine();
                    if (line.isEmpty()) break;
                    sb.append(line).append("\n");
                }
                LSDatagramSender.sendBroadcast(sb.toString());
            } 
            else if (command.equalsIgnoreCase("exit")) {
                break;
            }
        }

    
    }

}