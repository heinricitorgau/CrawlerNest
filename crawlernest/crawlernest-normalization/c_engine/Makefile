CC = gcc
CFLAGS = -Wall -Wextra -std=c11 -Iinclude
SRC_DIR = src
BUILD_DIR = build

SRCS = \
	$(SRC_DIR)/main.c \
	$(SRC_DIR)/normalizer.c \
	$(SRC_DIR)/csv_reader.c \
	$(SRC_DIR)/csv_writer.c \
	$(SRC_DIR)/name_normalizer.c \
	$(SRC_DIR)/country_normalizer.c \
	$(SRC_DIR)/rank_parser.c \
	$(SRC_DIR)/score_parser.c \
	$(SRC_DIR)/requirement_parser.c \
	$(SRC_DIR)/utils.c

OBJS = $(SRCS:$(SRC_DIR)/%.c=$(BUILD_DIR)/%.o)
TARGET = $(BUILD_DIR)/clawer_normalizer
OUTPUT_CSV = data/samples/normalized_universities.csv

TEST_TARGET      = $(BUILD_DIR)/test_normalizer
TEST_SRC         = src/tests/test_normalizer.c
TEST_OBJS        = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_normalizer.o

TEST_EXTREME_TARGET = $(BUILD_DIR)/test_extreme
TEST_EXTREME_SRC    = src/tests/test_extreme.c
TEST_EXTREME_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_extreme.o

TEST_SCALE_TARGET = $(BUILD_DIR)/test_scale
TEST_SCALE_SRC    = src/tests/test_scale.c
TEST_SCALE_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_scale.o

TEST_WEAKNESS_TARGET = $(BUILD_DIR)/test_weakness
TEST_WEAKNESS_SRC    = src/tests/test_weakness.c
TEST_WEAKNESS_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_weakness.o

TEST_REGRESSION2_TARGET = $(BUILD_DIR)/test_regression2
TEST_REGRESSION2_SRC    = src/tests/test_regression2.c
TEST_REGRESSION2_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_regression2.o

TEST_REGRESSION3_TARGET = $(BUILD_DIR)/test_regression3
TEST_REGRESSION3_SRC    = src/tests/test_regression3.c
TEST_REGRESSION3_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_regression3.o

TEST_REGRESSION4_TARGET = $(BUILD_DIR)/test_regression4
TEST_REGRESSION4_SRC    = src/tests/test_regression4.c
TEST_REGRESSION4_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_regression4.o

TEST_REGRESSION5_TARGET = $(BUILD_DIR)/test_regression5
TEST_REGRESSION5_SRC    = src/tests/test_regression5.c
TEST_REGRESSION5_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_regression5.o

TEST_REGRESSION6_TARGET = $(BUILD_DIR)/test_regression6
TEST_REGRESSION6_SRC    = src/tests/test_regression6.c
TEST_REGRESSION6_OBJS   = $(filter-out $(BUILD_DIR)/main.o,$(OBJS)) $(BUILD_DIR)/test_regression6.o

.PHONY: all run test test_extreme test_scale test_weakness test_regression2 test_regression3 test_regression4 test_regression5 test_regression6 test_all clean rebuild clean_output

all: $(TARGET) clean_output

# 編譯時一併清空上一次的正規化輸出，避免拿到舊結果
clean_output:
	@printf '' > $(OUTPUT_CSV)
	@echo "已清空 $(OUTPUT_CSV)"

$(TARGET): $(OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

$(TEST_TARGET): $(TEST_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_OBJS) -o $(TEST_TARGET)

$(TEST_EXTREME_TARGET): $(TEST_EXTREME_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_EXTREME_OBJS) -o $(TEST_EXTREME_TARGET)

$(TEST_SCALE_TARGET): $(TEST_SCALE_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_SCALE_OBJS) -o $(TEST_SCALE_TARGET)

$(BUILD_DIR)/test_normalizer.o: $(TEST_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_SRC) -o $(BUILD_DIR)/test_normalizer.o

$(BUILD_DIR)/test_extreme.o: $(TEST_EXTREME_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_EXTREME_SRC) -o $(BUILD_DIR)/test_extreme.o

$(BUILD_DIR)/test_scale.o: $(TEST_SCALE_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_SCALE_SRC) -o $(BUILD_DIR)/test_scale.o

$(TEST_WEAKNESS_TARGET): $(TEST_WEAKNESS_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_WEAKNESS_OBJS) -o $(TEST_WEAKNESS_TARGET)

$(BUILD_DIR)/test_weakness.o: $(TEST_WEAKNESS_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_WEAKNESS_SRC) -o $(BUILD_DIR)/test_weakness.o

$(TEST_REGRESSION2_TARGET): $(TEST_REGRESSION2_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_REGRESSION2_OBJS) -o $(TEST_REGRESSION2_TARGET)

$(BUILD_DIR)/test_regression2.o: $(TEST_REGRESSION2_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_REGRESSION2_SRC) -o $(BUILD_DIR)/test_regression2.o

$(TEST_REGRESSION3_TARGET): $(TEST_REGRESSION3_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_REGRESSION3_OBJS) -o $(TEST_REGRESSION3_TARGET)

$(BUILD_DIR)/test_regression3.o: $(TEST_REGRESSION3_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_REGRESSION3_SRC) -o $(BUILD_DIR)/test_regression3.o

$(TEST_REGRESSION4_TARGET): $(TEST_REGRESSION4_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_REGRESSION4_OBJS) -o $(TEST_REGRESSION4_TARGET)

$(BUILD_DIR)/test_regression4.o: $(TEST_REGRESSION4_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_REGRESSION4_SRC) -o $(BUILD_DIR)/test_regression4.o

$(TEST_REGRESSION5_TARGET): $(TEST_REGRESSION5_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_REGRESSION5_OBJS) -o $(TEST_REGRESSION5_TARGET)

$(BUILD_DIR)/test_regression5.o: $(TEST_REGRESSION5_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_REGRESSION5_SRC) -o $(BUILD_DIR)/test_regression5.o

$(TEST_REGRESSION6_TARGET): $(TEST_REGRESSION6_OBJS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(TEST_REGRESSION6_OBJS) -o $(TEST_REGRESSION6_TARGET) -lm

$(BUILD_DIR)/test_regression6.o: $(TEST_REGRESSION6_SRC)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $(TEST_REGRESSION6_SRC) -o $(BUILD_DIR)/test_regression6.o

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

run: $(TARGET)
	./$(TARGET)

test: $(TEST_TARGET)
	./$(TEST_TARGET)

test_extreme: $(TEST_EXTREME_TARGET)
	./$(TEST_EXTREME_TARGET)

test_scale: $(TEST_SCALE_TARGET)
	./$(TEST_SCALE_TARGET)

test_weakness: $(TEST_WEAKNESS_TARGET)
	./$(TEST_WEAKNESS_TARGET)

test_regression2: $(TEST_REGRESSION2_TARGET)
	./$(TEST_REGRESSION2_TARGET)

test_regression3: $(TEST_REGRESSION3_TARGET)
	./$(TEST_REGRESSION3_TARGET)

test_regression4: $(TEST_REGRESSION4_TARGET)
	./$(TEST_REGRESSION4_TARGET)

test_regression5: $(TEST_REGRESSION5_TARGET)
	./$(TEST_REGRESSION5_TARGET)

test_regression6: $(TEST_REGRESSION6_TARGET)
	./$(TEST_REGRESSION6_TARGET)

test_all: test test_extreme test_scale test_weakness test_regression2 test_regression3 test_regression4 test_regression5 test_regression6

clean:
	rm -rf $(BUILD_DIR)

rebuild: clean all
