function R = load_cross_edition_ranks(options)
%LOAD_CROSS_EDITION_RANKS Read the committed cross-edition rank export.
%
%   R = load_cross_edition_ranks()
%   R = load_cross_edition_ranks(Csv="...", CheckHash=false)
%
%   One row per university, source and edition, with the interval the source
%   printed: RANK_LO and RANK_HI, where RANK_HI is NaN for an open-ended band
%   such as "1401+". The file is written by
%   crawlernest/scripts/export_cross_edition_ranks.py from the warehouse; the
%   metadata beside it records its SHA-256.
%
%   By default the file's hash is compared with that metadata and a mismatch is an
%   error. The experiment is only reproducible against the export it was run on,
%   so a CSV edited by hand, or re-exported without its metadata, stops here
%   rather than producing a plausible number.
%
%   R.table   the rows, string columns as strings
%   R.csv     the path read
%   R.sha256  hash of the bytes read
%   R.meta    the decoded metadata file

arguments
    options.Csv (1,1) string = ""
    options.CheckHash (1,1) logical = true
end

mlDir = fileparts(fileparts(mfilename("fullpath")));
kbDir = fullfile(fileparts(mlDir), "crawlernest-kb", "databases");
csv = options.Csv;
if csv == ""
    csv = string(fullfile(kbDir, "cross_edition_ranks.csv"));
end
if ~isfile(csv)
    error("load_cross_edition_ranks:missing", ...
        "No export at %s. Run crawlernest/scripts/export_cross_edition_ranks.py --commit.", csv);
end

fid = fopen(csv, "r");
bytes = fread(fid, Inf, "*uint8");
fclose(fid);
digest = java.security.MessageDigest.getInstance("SHA-256");
raw = typecast(int8(digest.digest(bytes)), "uint8");
sha = lower(string(reshape(dec2hex(raw, 2)', 1, [])));

metaPath = replace(csv, ".csv", ".meta.json");
meta = struct();
if isfile(metaPath)
    meta = jsondecode(fileread(metaPath));
end
if options.CheckHash
    if ~isfield(meta, "csv_sha256")
        error("load_cross_edition_ranks:nometa", "No metadata with a hash beside %s.", csv);
    end
    if ~strcmp(sha, string(meta.csv_sha256))
        error("load_cross_edition_ranks:stale", ...
            "%s hashes to %s, its metadata says %s. Re-export it.", csv, sha, meta.csv_sha256);
    end
end

opts = detectImportOptions(csv, TextType="string");
opts = setvartype(opts, ["canonical_university_id", "year"], "double");
opts = setvartype(opts, ["rank_lo", "rank_hi"], "double");
T = readtable(csv, opts);

required = ["canonical_university_id", "year", "source", "rank_lo", "rank_hi", "printed", "source_kind"];
missingCols = setdiff(required, string(T.Properties.VariableNames));
if ~isempty(missingCols)
    error("load_cross_edition_ranks:columns", "Missing columns: %s", strjoin(missingCols, ", "));
end
if any(isnan(T.rank_lo)) || any(T.rank_lo < 1)
    error("load_cross_edition_ranks:rank", "rank_lo must be a positive number in every row.");
end
bounded = ~isnan(T.rank_hi);
if any(T.rank_hi(bounded) < T.rank_lo(bounded))
    error("load_cross_edition_ranks:interval", "A row has rank_hi below rank_lo.");
end
key = T.canonical_university_id * 1e6 + T.year * 10 + double(categorical(T.source));
if numel(unique(key)) ~= height(T)
    error("load_cross_edition_ranks:duplicate", "More than one row for a university, source and edition.");
end

R = struct("table", T, "csv", csv, "sha256", sha, "meta", meta);
end
