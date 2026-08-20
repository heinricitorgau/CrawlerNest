#include <stdio.h>
#include <stdlib.h>

#ifdef _WIN32
#include <windows.h>
#endif

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
    printf("1. 載入 CSV 資料並顯示原始資料\n");
    printf("2. 執行完整正規化流程並顯示結果\n");
    printf("3. 匯出正規化結果到 CSV 並離開程式\n");
    printf("0. 離開程式\n");
    printf("請輸入選項: ");
}

int main(void) {
    UniversityRecord records[MAX_RECORDS];
    int record_count = 0;
    int is_loaded = 0;
    int is_normalized = 0;
    int choice;

#ifdef _WIN32
    /* Source strings are UTF-8; switch the Windows console from the
       locale codepage (e.g. CP950) to UTF-8 so they display correctly. */
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif

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
                    print_raw_records(records, record_count);
                } else {
                    printf("\n載入失敗，請確認 CSV 檔案是否存在。\n");
                }
                break;

            case 2:
                if (!is_loaded) {
                    printf("\n尚未載入資料，請先執行選項 1。\n");
                } else {
                    normalize_dataset(records, record_count);
                    is_normalized = 1;
                    printf("\n資料正規化完成。\n");
                    print_normalized_records(records, record_count);
                }
                break;

            case 3:
                if (!is_loaded) {
                    printf("\n尚未載入資料，請先執行選項 1。\n");
                } else if (!is_normalized) {
                    printf("\n資料尚未正規化，請先執行選項 2。\n");
                } else {
                    if (write_normalized_csv(OUTPUT_CSV_PATH, records, record_count)) {
                        printf("\n已成功輸出到：%s\n", OUTPUT_CSV_PATH);
                        printf("\n程式已結束。\n");
                        return 0;
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