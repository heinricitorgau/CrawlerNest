package clawer.desk.support;

import clawer.auth.jwt.AuthenticatedUser;

/** The signed-in user for a desk request. */
public final class DeskAuth {

    private DeskAuth() {}

    /**
     * From the verified token, never from the request. The filter chain already
     * refuses an anonymous caller on /api/v1/user/**; this check stays so a
     * routing change cannot quietly open a desk endpoint.
     */
    public static long currentUserId() {
        Long id = AuthenticatedUser.currentId();
        if (id == null) {
            throw DeskException.unauthenticated();
        }
        return id;
    }
}
