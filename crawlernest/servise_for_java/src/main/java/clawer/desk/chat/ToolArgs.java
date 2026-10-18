package clawer.desk.chat;

import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Set;
import java.util.function.Supplier;

/**
 * A tool call's arguments, read with the desk forms' rules but reporting every
 * problem at once.
 *
 * <p>A form submit can stop at the first bad field: the person fixes it and sees
 * the next. A model given only the first problem fixes that one and trips on the
 * second, a round later or not at all -- in testing, qwen3 was told "reason is
 * required" and never learned that "regular decision" was not a round. So the
 * readers here return null on a bad value, record why, and {@link #throwIfAny}
 * reports the lot.
 */
final class ToolArgs {

    private final List<String> problems = new ArrayList<>();
    private final DeskInput in;

    ToolArgs(JsonNode args, Set<String> allowed) {
        ObjectNode known = args.deepCopy();
        for (Iterator<String> names = args.fieldNames(); names.hasNext(); ) {
            String name = names.next();
            if (!allowed.contains(name)) {
                problems.add("Unknown field \"" + name + "\"; the fields are " + String.join(", ", allowed.stream().sorted().toList()) + ".");
                known.remove(name);
            }
        }
        this.in = new DeskInput(known, allowed);
    }

    private <T> T read(Supplier<T> reader) {
        try {
            return reader.get();
        } catch (DeskException e) {
            problems.add(e.getMessage());
            return null;
        }
    }

    boolean has(String field) {
        return in.has(field);
    }

    String text(String field, int max, boolean required) {
        return read(() -> in.text(field, max, required));
    }

    String oneOf(String field, Set<String> allowed, boolean required) {
        return read(() -> in.oneOf(field, allowed, required));
    }

    LocalDate date(String field) {
        return read(() -> in.date(field, false));
    }

    Long id(String field, boolean required) {
        return read(() -> in.id(field, required));
    }

    void problem(String message) {
        problems.add(message);
    }

    boolean ok() {
        return problems.isEmpty();
    }

    void throwIfAny() {
        if (!problems.isEmpty()) {
            throw DeskException.badRequest(String.join(" ", problems));
        }
    }
}
