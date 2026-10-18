package clawer.auth.reset;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/** The reply to "send me a link" never promises a delivery the server cannot make. */
class PasswordResetMessageTest {

    private static String messageFor(String mode) {
        PasswordResetService service = mock(PasswordResetService.class);
        when(service.ttl()).thenReturn(Duration.ofMinutes(30));
        return new PasswordResetController(service, new PasswordResetDelivery(mode)).requestedMessage();
    }

    @Test
    void withNoDeliveryItSaysNoLinkWasSent() {
        String message = messageFor("none");
        assertTrue(message.contains("not set up on this server yet, so no link was sent"), message);
        assertTrue(!message.contains("we've sent"), message);
    }

    @Test
    void inDevelopmentItSaysTheLinkIsInTheLog() {
        String message = messageFor("log");
        assertTrue(message.contains("written to the server log"), message);
        assertTrue(message.contains("30 minutes"), message);
    }
}
