package clawer.auth.dto;

import java.time.Instant;

public class AuthUserResponse {
    private Long id;
    private String email;
    private Instant createdAt;
    private Instant lastLoginAt;

    public AuthUserResponse() {}

    public AuthUserResponse(Long id, String email, Instant createdAt, Instant lastLoginAt) {
        this.id = id;
        this.email = email;
        this.createdAt = createdAt;
        this.lastLoginAt = lastLoginAt;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public Instant getLastLoginAt() { return lastLoginAt; }
    public void setLastLoginAt(Instant lastLoginAt) { this.lastLoginAt = lastLoginAt; }
}
