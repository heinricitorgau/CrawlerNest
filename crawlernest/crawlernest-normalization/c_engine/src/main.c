#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "record.h"
#include "normalizer.h"
#include "csv_reader.h"
#include "csv_writer.h"

#define MAX_RECORDS 100
#define SAMPLE_CSV_PATH "data/samples/raw_universities.csv"
#define OUTPUT_CSV_PATH "data/samples/normalized_universities.csv"

static void print_raw_records(const UniversityRecord records[], int count) {
    int i;

    printf("\n==== Raw University Data ====\n");
    for (i = 0; i < count; i++) {
        printf("[%d]\n", i + 1);
        printf("  Name    : %s\n", records[i].raw_name);
        printf("  Country : %s\n", records[i].raw_country);
        printf("  Rank    : %s\n", records[i].raw_rank);
        printf("  Score   : %s\n", records[i].raw_score);
        printf("\n");
    }
}

static void print_normalized_records(const UniversityRecord records[], int count) {
    int i;

    printf("\n==== Normalized University Data ====\n");
    for (i = 0; i < count; i++) {
        printf("[%d]\n", i + 1);
        printf("  Name         : %s\n", records[i].normalized_name);
        printf("  Country      : %s\n", records[i].normalized_country);
        printf("  Rank Min     : %d\n", records[i].rank_min);
        printf("  Rank Max     : %d\n", records[i].rank_max);
        printf("  Score        : %.2f\n", records[i].score);
        printf("\n");
    }
}

static void show_menu(void) {
    printf("\n==== Clawer C Data Normalization Engine ====\n");
    printf("1. 載入 CSV 資料\n");
    printf("2. 顯示原始資料\n");
    printf("3. 執行完整正規化流程\n");
    printf("4. 顯示正規化後資料\n");
    printf("5. 匯出正規化結果到 CSV\n");
    printf("0. 離開程式\n");
    printf("請輸入選項: ");
}

/*
 * run_pipe_name
 *
 * Reads university name strings line-by-line from stdin,
 * outputs normalized names to stdout, one per line.
 * Used by the Python bridge for subprocess-based normalization.
 */
static void run_pipe_name(void) {
    char line[NAME_LEN];
    char output[NAME_LEN];

    while (fgets(line, (int)sizeof(line), stdin) != NULL) {
        /* Strip trailing newline */
        size_t len = strlen(line);
        if (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[--len] = '\0';
        }
        if (len > 0 && (line[len - 1] == '\r')) {
            line[--len] = '\0';
        }

        normalize_name(line, output, (int)sizeof(output));
        printf("%s\n", output);
        fflush(stdout);
    }
}

/*
 * run_pipe_country
 *
 * Reads country strings line-by-line from stdin,
 * outputs normalized canonical country names to stdout, one per line.
 */
static void run_pipe_country(void) {
    char line[COUNTRY_LEN];
    char output[COUNTRY_LEN];

    while (fgets(line, (int)sizeof(line), stdin) != NULL) {
        size_t len = strlen(line);
        if (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[--len] = '\0';
        }
        if (len > 0 && (line[len - 1] == '\r')) {
            line[--len] = '\0';
        }

        normalize_country(line, output, (int)sizeof(output));
        printf("%s\n", output);
        fflush(stdout);
    }
}

/*
 * run_pipe_batch
 *
 * Reads CSV records line-by-line from stdin in the format:
 *   name,country
 * Outputs normalized CSV to stdout:
 *   normalized_name,normalized_country
 *
 * A comma inside a quoted field is not supported; use simple CSV.
 */
static void run_pipe_batch(void) {
    char line[NAME_LEN + COUNTRY_LEN + 4];
    char name_buf[NAME_LEN];
    char country_buf[COUNTRY_LEN];
    char norm_name[NAME_LEN];
    char norm_country[COUNTRY_LEN];
    char *comma;

    /* Print header */
    printf("normalized_name,normalized_country\n");
    fflush(stdout);

    while (fgets(line, (int)sizeof(line), stdin) != NULL) {
        /* Strip trailing newline */
        size_t len = strlen(line);
        if (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[--len] = '\0';
        }
        if (len > 0 && (line[len - 1] == '\r')) {
            line[--len] = '\0';
        }

        /* Skip empty lines and header */
        if (len == 0) continue;
        if (strncmp(line, "name,", 5) == 0 || strncmp(line, "Name,", 5) == 0) continue;

        comma = strchr(line, ',');
        if (comma == NULL) {
            /* No comma: treat entire line as name, empty country */
            strncpy(name_buf, line, sizeof(name_buf) - 1);
            name_buf[sizeof(name_buf) - 1] = '\0';
            country_buf[0] = '\0';
        } else {
            size_t name_len = (size_t)(comma - line);
            if (name_len >= sizeof(name_buf)) name_len = sizeof(name_buf) - 1;
            strncpy(name_buf, line, name_len);
            name_buf[name_len] = '\0';

            strncpy(country_buf, comma + 1, sizeof(country_buf) - 1);
            country_buf[sizeof(country_buf) - 1] = '\0';
        }

        normalize_name(name_buf, norm_name, (int)sizeof(norm_name));
        normalize_country(country_buf, norm_country, (int)sizeof(norm_country));

        printf("%s,%s\n", norm_name, norm_country);
        fflush(stdout);
    }
}

int main(int argc, char *argv[]) {
    UniversityRecord records[MAX_RECORDS];
    int record_count = 0;
    int is_loaded = 0;
    int is_normalized = 0;
    int choice;

    /* --pipe-name: normalize names from stdin, one per line */
    if (argc >= 2 && strcmp(argv[1], "--pipe-name") == 0) {
        run_pipe_name();
        return 0;
    }

    /* --pipe-country: normalize countries from stdin, one per line */
    if (argc >= 2 && strcmp(argv[1], "--pipe-country") == 0) {
        run_pipe_country();
        return 0;
    }

    /* --pipe-batch: normalize CSV (name,country) from stdin */
    if (argc >= 2 && strcmp(argv[1], "--pipe-batch") == 0) {
        run_pipe_batch();
        return 0;
    }

    /* Interactive menu mode */
    printf("Clawer C Data Normalization Engine 啟動中...\n");

    while (1) {
        show_menu();

        if (scanf("%d", &choice) != 1) {
            printf("\n輸入錯誤，程式即將結束。\n");
            break;
        }

        switch (choice) {
            case 1:
                record_count = load_csv_data(SAMPLE_CSV_PATH, records, MAX_RECORDS);
                if (record_count > 0) {
                    is_loaded = 1;
                    is_normalized = 0;
                    printf("\n成功載入 %d 筆資料。\n", record_count);
                } else {
                    printf("\n載入失敗，請確認 CSV 檔案是否存在。\n");
                }
                break;

            case 2:
                if (!is_loaded) {
                    printf("\n尚未載入資料，請先執行選項 1。\n");
                } else {
                    print_raw_records(records, record_count);
                }
                break;

            case 3:
                if (!is_loaded) {
                    printf("\n尚未載入資料，請先執行選項 1。\n");
                } else {
                    normalize_dataset(records, record_count);
                    is_normalized = 1;
                    printf("\n資料正規化完成。\n");
                }
                break;

            case 4:
                if (!is_loaded) {
                    printf("\n尚未載入資料，請先執行選項 1。\n");
                } else if (!is_normalized) {
                    printf("\n資料尚未正規化，請先執行選項 3。\n");
                } else {
                    print_normalized_records(records, record_count);
                }
                break;

            case 5:
                if (!is_loaded) {
                    printf("\n尚未載入資料，請先執行選項 1。\n");
                } else if (!is_normalized) {
                    printf("\n資料尚未正規化，請先執行選項 3。\n");
                } else {
                    if (write_normalized_csv(OUTPUT_CSV_PATH, records, record_count)) {
                        printf("\n已成功輸出到：%s\n", OUTPUT_CSV_PATH);
                    } else {
                        printf("\n輸出 CSV 失敗。\n");
                    }
                }
                break;

            case 0:
                printf("\n程式已結束。\n");
                return 0;

            default:
                printf("\n無效選項，請重新輸入。\n");
                break;
        }
    }

    return 0;
}
