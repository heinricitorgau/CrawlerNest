function matrix = load_qs_snapshot(snapshotPath)
%LOAD_QS_SNAPSHOT Build the QS indicator matrix from the committed crawl snapshot.
%
%   MATRIX = LOAD_QS_SNAPSHOT() reads
%   crawlernest/crawlernest-kb/databases/last_crawl_snapshot.json, which is
%   committed to the repository, so this runs with no database and no network.
%
%   MATRIX = LOAD_QS_SNAPSHOT(PATH) reads an explicit snapshot file.
%
%   Returned struct:
%     .X               1503x9 double, indicators in QS_INDICATORS order, NaN where missing
%     .y               1503x1 double, Overall Score; NaN for ranks 601-1503
%     .rank            1503x1 double, published rank (evaluation only, never a feature)
%     .name            1503x1 string, university name
%     .country         1503x1 string
%     .indicators      1x9 string, column names of X
%     .labelledMask    1503x1 logical, true where QS published an overall score
%
%   `rank` is deliberately kept out of X: QS derives the rank *from* the overall
%   score, so using it as a feature would leak the target.
%
%   MATLAB port of ranking_ml.features.build_features.load_feature_matrix. The
%   region one-hot block is not built here -- none of the EDA figures use it.

arguments
    snapshotPath (1,1) string = ""
end

if strlength(snapshotPath) == 0
    snapshotPath = default_snapshot_path();
end

if ~isfile(snapshotPath)
    error("load_qs_snapshot:missingSnapshot", ...
        "crawl snapshot not found at %s. Run the pipeline first, or pass an explicit path.", ...
        snapshotPath);
end

indicators = qs_indicators();
targetLabel = "Overall Score";

records = jsondecode(fileread(snapshotPath));
if isstruct(records)
    records = num2cell(records);
elseif ~iscell(records)
    error("load_qs_snapshot:badPayload", ...
        "expected a list of records in %s", snapshotPath);
end

n = numel(records);
X = NaN(n, numel(indicators));
y = NaN(n, 1);
ranks = NaN(n, 1);
names = strings(n, 1);
countries = strings(n, 1);

% jsondecode rewrites JSON keys such as "Citations per Faculty" into valid
% MATLAB identifiers. Resolve the mapping once, from the data itself, so a
% change in MATLAB's name-mangling rules fails loudly here instead of quietly
% producing a matrix full of NaN.
fieldFor = resolve_metric_fields(records, [indicators, targetLabel]);

for i = 1:n
    record = records{i};

    if isfield(record, "table_metrics") && isstruct(record.table_metrics)
        metrics = record.table_metrics;
        for j = 1:numel(indicators)
            X(i, j) = qs_to_float(get_metric(metrics, fieldFor(indicators(j))));
        end
        y(i) = qs_to_float(get_metric(metrics, fieldFor(targetLabel)));
    end

    if isfield(record, "rank")
        ranks(i) = qs_to_rank(record.rank);
    end
    if isfield(record, "name")
        names(i) = strtrim(string(record.name));
    end
    if isfield(record, "country")
        countries(i) = strtrim(string(record.country));
    end
end

matrix = struct( ...
    "X", X, ...
    "y", y, ...
    "rank", ranks, ...
    "name", names, ...
    "country", countries, ...
    "indicators", indicators, ...
    "targetLabel", targetLabel, ...
    "labelledMask", ~isnan(y), ...
    "snapshotPath", snapshotPath);
end


function names = qs_indicators()
%QS_INDICATORS Fixed column order, mirroring ranking_ml.features.schema.
names = [ ...
    "Academic Reputation", ...
    "Employer Reputation", ...
    "Faculty Student Ratio", ...
    "Citations per Faculty", ...
    "International Faculty Ratio", ...
    "International Student Ratio", ...
    "International Research Network", ...
    "Employment Outcomes", ...
    "Sustainability Score"];
end


function path = default_snapshot_path()
% .../crawlernest/crawlernest-ml/matlab/load_qs_snapshot.m -> .../crawlernest
crawlernestDir = fileparts(fileparts(fileparts(mfilename("fullpath"))));
path = string(fullfile(crawlernestDir, "crawlernest-kb", "databases", "last_crawl_snapshot.json"));
end


function map = resolve_metric_fields(records, labels)
%RESOLVE_METRIC_FIELDS Map JSON metric labels to the struct fields jsondecode produced.
available = strings(0, 1);
for i = 1:numel(records)
    if isfield(records{i}, "table_metrics") && isstruct(records{i}.table_metrics)
        available = string(fieldnames(records{i}.table_metrics));
        break
    end
end
if isempty(available)
    error("load_qs_snapshot:noMetrics", "no record carries a table_metrics object");
end

map = dictionary(string.empty, string.empty);
for k = 1:numel(labels)
    candidate = string(matlab.lang.makeValidName(labels(k)));
    if ~ismember(candidate, available)
        error("load_qs_snapshot:unmappedMetric", ...
            "metric %s (expected field %s) is not in table_metrics. Fields present: %s", ...
            labels(k), candidate, strjoin(available, ", "));
    end
    map(labels(k)) = candidate;
end
end


function value = get_metric(metrics, field)
if isfield(metrics, field)
    value = metrics.(field);
else
    value = [];
end
end
