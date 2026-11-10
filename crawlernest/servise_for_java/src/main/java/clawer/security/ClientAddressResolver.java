package clawer.security;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.List;

import jakarta.servlet.http.HttpServletRequest;

/**
 * The address a request came from, for rate limiting.
 *
 * <p>{@code X-Forwarded-For} is believed only when the connection itself comes from a configured proxy
 * (by default loopback, where the Next.js server runs in a local setup). Then the answer is the right-most
 * entry that is not itself a trusted proxy: anything left of it was written by the client and proves
 * nothing. A request from a trusted proxy that sends no such header is reported as {@link #INTERNAL}: that
 * is the frontend's own server-side rendering, not a visitor.
 */
public final class ClientAddressResolver {

    public static final String INTERNAL = "internal";

    private final List<Cidr> trusted;

    public ClientAddressResolver(List<String> trustedProxies) {
        List<Cidr> parsed = new ArrayList<>();
        for (String entry : trustedProxies) {
            String value = entry == null ? "" : entry.trim();
            if (!value.isEmpty()) {
                parsed.add(Cidr.parse(value));
            }
        }
        this.trusted = List.copyOf(parsed);
    }

    public String resolve(HttpServletRequest request) {
        String remote = request.getRemoteAddr();
        if (!isTrusted(remote)) {
            return remote;
        }
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded == null || forwarded.isBlank()) {
            return INTERNAL;
        }
        String[] hops = forwarded.split(",");
        for (int i = hops.length - 1; i >= 0; i--) {
            String hop = hops[i].trim();
            if (!hop.isEmpty() && !isTrusted(hop)) {
                return hop;
            }
        }
        return INTERNAL;
    }

    boolean isTrusted(String address) {
        byte[] bytes = literalBytes(address);
        if (bytes == null) {
            return false;
        }
        for (Cidr cidr : trusted) {
            if (cidr.contains(bytes)) {
                return true;
            }
        }
        return false;
    }

    /** The bytes of an IP literal, or null for anything else. Never a DNS lookup. */
    static byte[] literalBytes(String address) {
        if (address == null) {
            return null;
        }
        String value = address.trim();
        if (value.startsWith("[") && value.endsWith("]")) {
            value = value.substring(1, value.length() - 1);
        }
        if (value.isEmpty() || !value.matches("[0-9A-Fa-f:.]+")) {
            return null;
        }
        try {
            return InetAddress.getByName(value).getAddress();
        } catch (UnknownHostException e) {
            return null;
        }
    }

    private record Cidr(byte[] network, int prefix) {

        static Cidr parse(String text) {
            String[] parts = text.split("/", 2);
            byte[] network = literalBytes(parts[0]);
            if (network == null) {
                throw new IllegalArgumentException("not an IP address or CIDR range: " + text);
            }
            int prefix = parts.length == 2 ? Integer.parseInt(parts[1].trim()) : network.length * 8;
            if (prefix < 0 || prefix > network.length * 8) {
                throw new IllegalArgumentException("bad prefix length in " + text);
            }
            return new Cidr(network, prefix);
        }

        boolean contains(byte[] address) {
            if (address.length != network.length) {
                return false;
            }
            int full = prefix / 8;
            for (int i = 0; i < full; i++) {
                if (address[i] != network[i]) {
                    return false;
                }
            }
            int rest = prefix % 8;
            if (rest == 0) {
                return true;
            }
            int mask = (0xFF << (8 - rest)) & 0xFF;
            return (address[full] & mask) == (network[full] & mask);
        }
    }
}
