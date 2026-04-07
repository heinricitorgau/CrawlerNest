#ifndef CSV_READER_H
#define CSV_READER_H

#include "record.h"

int load_csv_data(const char *filename, UniversityRecord records[], int max_records);

#endif /* CSV_READER_H */