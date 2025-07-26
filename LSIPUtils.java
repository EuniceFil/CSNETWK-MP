import java.net.*;
import java.util.Collections;
import java.util.UUID;

public class LSIPUtils {

    public static InetAddress getLocalIPAddress() throws SocketException {
        for (NetworkInterface iface : Collections.list(NetworkInterface.getNetworkInterfaces())) {
            if (iface.isLoopback() || !iface.isUp()) continue;

            for (InterfaceAddress addr : iface.getInterfaceAddresses()) {
                InetAddress inetAddr = addr.getAddress();
                if (inetAddr instanceof Inet4Address) {
                    return inetAddr;
                }
            }
        }
        return null;
    }

    public static InetAddress getBroadcastAddress() throws SocketException {
        for (NetworkInterface iface : Collections.list(NetworkInterface.getNetworkInterfaces())) {
            if (iface.isLoopback() || !iface.isUp()) continue;

            for (InterfaceAddress addr : iface.getInterfaceAddresses()) {
                InetAddress broadcast = addr.getBroadcast();
                if (broadcast != null) {
                    return broadcast;
                }
            }
        }
        try {
            return InetAddress.getByName("255.255.255.255"); // fallback
        } catch (UnknownHostException e) {
            return null;
        }
    }

    public static String generateMessageId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }

}