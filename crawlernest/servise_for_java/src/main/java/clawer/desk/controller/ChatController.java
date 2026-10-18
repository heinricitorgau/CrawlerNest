package clawer.desk.controller;

import clawer.desk.chat.ChatActionService;
import clawer.desk.chat.TasselChatService;
import clawer.desk.support.DeskAuth;
import clawer.dto.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/**
 * Tassel: one conversation turn, and what the user does with its actions.
 *
 * <p>Under /api/v1/user/ like the rest of the desk. The model's tool calls write
 * only desk.* rows of the session user, through the same services the desk
 * forms use; no warehouse, analytics or pipeline table is reachable from here.
 */
@RestController
@RequestMapping("/api/v1/user/desk/chat")
public class ChatController {

    private final TasselChatService chat;
    private final ChatActionService actions;

    public ChatController(TasselChatService chat, ChatActionService actions) {
        this.chat = chat;
        this.actions = actions;
    }

    /** Body: {"sessionId", "message", "history"?: [{"role", "content"}], "mode"?: general|brainstorming|review}. */
    @PostMapping("/message")
    public ResponseEntity<?> message(@RequestBody JsonNode body) {
        return ResponseEntity.ok(ApiResponse.success(chat.message(DeskAuth.currentUserId(), body)));
    }

    @GetMapping("/actions")
    public ResponseEntity<?> list(@RequestParam String sessionId) {
        return ResponseEntity.ok(ApiResponse.success(actions.list(DeskAuth.currentUserId(), sessionId)));
    }

    @PostMapping("/actions/{id}/confirm")
    public ResponseEntity<?> confirm(@PathVariable UUID id) {
        return ResponseEntity.ok(ApiResponse.success(actions.confirm(DeskAuth.currentUserId(), id)));
    }

    @PostMapping("/actions/{id}/reject")
    public ResponseEntity<?> reject(@PathVariable UUID id) {
        return ResponseEntity.ok(ApiResponse.success(actions.reject(DeskAuth.currentUserId(), id)));
    }

    @PostMapping("/actions/{id}/undo")
    public ResponseEntity<?> undo(@PathVariable UUID id) {
        return ResponseEntity.ok(ApiResponse.success(actions.undo(DeskAuth.currentUserId(), id)));
    }
}
