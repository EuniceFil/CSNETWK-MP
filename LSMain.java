import java.net.InetAddress;
import java.util.Scanner;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class LSMain {

    public static boolean VERBOSE = false;

    public static void main(String[] args) throws Exception {
        for (String arg : args) {
            if ("--verbose".equals(arg)) {
                VERBOSE = true;
                System.out.println("[INFO] Verbose mode enabled.");
            }
        }

        // Start listener thread
        Thread listener = new Thread(() -> {
            try {
                LSDatagramReceiver.startListening();
            } catch (Exception e) {
                LSLogger.warn("Receiver crashed: " + e.getMessage());
            }
        });
        listener.start();

        // Delay then ping
        Thread.sleep(2000);
        //String localIP = LSIPUtils.getLocalIPAddress().getHostAddress();
        // String pingMessage = "TYPE: PING\nUSER_ID: system@" + localIP + "\n\n";
        // LSDatagramSender.sendBroadcast(pingMessage);

        Scanner scanner = new Scanner(System.in);
        System.out.print("Enter your USER_ID (e.g., dave@192.168.1.10): ");
        String userId = scanner.nextLine();

        String localIP = userId.split("@")[1]; // This gets "127.0.0.1" from your input
        String pingMessage = "TYPE: PING\nUSER_ID: system@" + localIP + "\n\n";
        LSDatagramSender.sendBroadcast(pingMessage);
        
        System.out.print("Enter your display name: ");
        String displayName = scanner.nextLine();
        
        System.out.print("Enter your status: ");
        String status = scanner.nextLine();

        // Set up a scheduled task to broadcast the profile periodically
        ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();

        Runnable broadcastProfileTask = () -> {
            String profileMessage = LSMessageBuilder.createProfile(userId, displayName, status);
            LSDatagramSender.sendBroadcast(profileMessage);
        };
        
        // Schedule the task to run immediately, and then every 300 seconds (5 minutes)
        executor.scheduleAtFixedRate(broadcastProfileTask, 0, 60, TimeUnit.SECONDS);
        System.out.println("Profile has been broadcast. It will be rebroadcast every 5 minutes.");

        while (true) {
            System.out.println("Choose an action: [post] [dm] [raw] [invite] [move] [exit]");
            String command = scanner.nextLine().trim();

            if (command.equalsIgnoreCase("post")) {
                System.out.print("Enter message content: ");
                String content = scanner.nextLine();

                System.out.print("Enter TTL in seconds (or press Enter for default 3600): ");
                String ttlInput = scanner.nextLine();
                int ttl = ttlInput.isEmpty() ? 3600 : Integer.parseInt(ttlInput);
                String token = LSTokenUtils.generateBroadcastToken(userId, ttl);

                String msg = LSMessageBuilder.createPost(userId, content, token, ttl);
                LSDatagramSender.sendBroadcast(msg);
            }

            // else if (command.equalsIgnoreCase("dm")) {
            //     System.out.print("Enter recipient (e.g., bob@192.168.1.20): ");
            //     String to = scanner.nextLine();
            //     System.out.print("Enter message content: ");
            //     String content = scanner.nextLine();
            //     System.out.print("Enter recipient IP (e.g., 192.168.1.20): ");
            //     InetAddress ip = InetAddress.getByName(scanner.nextLine());

            //     String msg = LSMessageBuilder.createDM(userId, to, content);
            //     LSDatagramSender.sendCustomMessage(msg, ip);
            // }

            else if (command.equalsIgnoreCase("raw")) {
                System.out.println("Enter raw message. End with empty line:");
                StringBuilder sb = new StringBuilder();
                while (true) {
                    String line = scanner.nextLine();
                    if (line.isEmpty()) break;
                    sb.append(line).append("\n");
                }
                LSDatagramSender.sendBroadcast(sb.toString());
            }

            else if (command.equalsIgnoreCase("invite")) {
                System.out.print("Enter recipient (e.g., bob@192.168.1.12): ");
                String to = scanner.nextLine();
                System.out.print("Enter recipient IP: ");
                InetAddress ip = InetAddress.getByName(scanner.nextLine());
                System.out.print("Enter Game ID (e.g., g123): ");
                String gameId = scanner.nextLine();
                System.out.print("Your symbol (X or O): ");
                String symbol = scanner.nextLine().toUpperCase();

                long now = System.currentTimeMillis() / 1000;
                int ttl = 3600;
                String token = userId + "|" + (now + ttl) + "|game";

                String msg = String.join("\n",
                        "TYPE: TICTACTOE_INVITE",
                        "FROM: " + userId,
                        "TO: " + to,
                        "GAMEID: " + gameId,
                        "SYMBOL: " + symbol,
                        "TIMESTAMP: " + now,
                        "TOKEN: " + token,
                        ""
                );
                LSDatagramSender.sendCustomMessage(msg, ip);
            }

            else if (command.equalsIgnoreCase("move")) {
                System.out.print("Game ID: ");
                String gameId = scanner.nextLine();
                System.out.print("Opponent ID (e.g., bob@192.168.1.12): ");
                String to = scanner.nextLine();
                System.out.print("Opponent IP: ");
                InetAddress ip = InetAddress.getByName(scanner.nextLine());
                System.out.print("Your symbol (X or O): ");
                String symbol = scanner.nextLine().toUpperCase();
                System.out.print("Board position (0–8): ");
                int pos = Integer.parseInt(scanner.nextLine());
                System.out.print("Turn number: ");
                int turn = Integer.parseInt(scanner.nextLine());

                long now = System.currentTimeMillis() / 1000;
                int ttl = 3600;
                String token = userId + "|" + (now + ttl) + "|game";

                String msg = String.join("\n",
                        "TYPE: TICTACTOE_MOVE",
                        "FROM: " + userId,
                        "TO: " + to,
                        "GAMEID: " + gameId,
                        "POSITION: " + pos,
                        "SYMBOL: " + symbol,
                        "TURN: " + turn,
                        "TOKEN: " + token,
                        ""
                );
                LSDatagramSender.sendCustomMessage(msg, ip);
            }

            else if (command.equalsIgnoreCase("exit")) {
                System.out.println("Exiting LSNP...");
                break;
            }

            else {
                System.out.println("Unknown command.");
            }
        }
        scanner.close();
        listener.interrupt();
    }
}