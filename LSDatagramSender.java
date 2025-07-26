import java.net.*;
import java.nio.charset.StandardCharsets;
import java.io.IOException;

public class LSDatagramSender {
    private static final int PORT = 50999;

    public static void sendBroadcast(String message) {
        DatagramSocket socket = null;
        try {
            socket = new DatagramSocket();
            socket.setBroadcast(true);

            byte[] data = message.getBytes(StandardCharsets.UTF_8);
            InetAddress broadcastAddress = LSIPUtils.getBroadcastAddress();

            DatagramPacket packet = new DatagramPacket(data, data.length, broadcastAddress, PORT);
            socket.send(packet);

            String type = extractType(message);
            LSLogger.send(type, broadcastAddress.getHostAddress(), message);

        } catch (Exception e) {
            LSLogger.warn("Broadcast send failed: " + e.getMessage());
        } finally {
            if (socket != null && !socket.isClosed()) {
                socket.close();
            }
        }
    }
    
    public static void sendCustomMessage(String message, InetAddress targetAddress) {
        try (DatagramSocket socket = new DatagramSocket()) {
            socket.setBroadcast(true);

            byte[] buffer = message.getBytes(StandardCharsets.UTF_8);
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length, targetAddress, PORT);
            socket.send(packet);

            String type = extractType(message);
            LSLogger.send(type, targetAddress.getHostAddress(), message);
        } catch (IOException e) {
            LSLogger.warn("Failed to send custom message: " + e.getMessage());
        }
    }
    
    private static String extractType(String message) {
        for (String line : message.strip().split("\n")) {
            if (line.startsWith("TYPE:")) {
                return line.split(":", 2)[1].trim();
            }
        }
        return "[MISSING]";
    }
}
