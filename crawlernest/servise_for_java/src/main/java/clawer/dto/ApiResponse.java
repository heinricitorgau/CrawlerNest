package clawer.dto;

import java.time.Instant;
import java.util.Map;

public class ApiResponse<T> {
    private boolean success;
    private T data;
    private Map<String, Object> metadata;

    public ApiResponse() {}

    public ApiResponse(T data) {
        this.success = true;
        this.data = data;
        this.metadata = Map.of("timestamp", Instant.now().toString());
    }

    public ApiResponse(T data, Map<String, Object> metadata) {
        this.success = true;
        this.data = data;
        this.metadata = metadata;
    }

    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(data);
    }

    public static <T> ApiResponse<T> success(T data, Map<String, Object> metadata) {
        return new ApiResponse<>(data, metadata);
    }

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }

    public void setMetadata(Map<String, Object> metadata) {
        this.metadata = metadata;
    }
}
