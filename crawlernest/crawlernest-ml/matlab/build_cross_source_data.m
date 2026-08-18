function [X, y, info] = build_cross_source_data(options)
%BUILD_CROSS_SOURCE_DATA MATLAB port of ranking_ml.features.cross_source.
%
%   [X, y] = build_cross_source_data()
%   [X, y, info] = build_cross_source_data(Quantile=0.80)
%
%   Two ranking bodies score the same universities on different criteria and
%   reach different conclusions. This assembles the rows where both published a
%   verdict, so the disagreement can be modelled instead of asserted.
%
%   X is the nine QS indicators for the matched universities, NaN preserved.
%   y is the binary disagreement label. INFO carries everything else the
%   training run needs, including THE's five pillar scores in INFO.theFeatures
%   -- the two-sided ceiling model is fitted from [X INFO.theFeatures].
%
%   ## The join
%
%   Matching on a normalised name (letters only, lowercased) recovers 820 of the
%   1,503 QS universities. The warehouse reaches 1,080 for the same two
%   snapshots, because its entity resolver is seeded with reviewed aliases and
%   because a human went through the ambiguous cases. That decision is committed
%   to qs_the_pairing_2026.json and is read here rather than re-derived, so
%   there is one answer to "which institution is this" instead of two that agree
%   today and drift tomorrow. Where no reviewed pair exists the normalised name
%   is still used, so a missing pairing file degrades to the smaller overlap
%   rather than failing.
%
%   ## Percentiles
%
%   Computed against each source's full population, not the overlap, so a
%   university's standing means "top x% of what QS ranked" rather than "top x%
%   of the subset that happens to appear in both".
%
%   See also TRAIN_DISAGREEMENT_CLASSIFIER, LOAD_QS_SNAPSHOT.

arguments
    options.Quantile (1,1) double {mustBeInRange(options.Quantile, 0, 1)} = 0.80
    options.QsSnapshot (1,1) string = ""
    options.TheSnapshot (1,1) string = ""
    options.Pairing (1,1) string = ""
    options.Verbose (1,1) logical = true
    options.OutDir (1,1) string = ""
    options.SaveOutput (1,1) logical = true
end

databases = databases_dir();
thePath = options.TheSnapshot;
if strlength(thePath) == 0
    thePath = string(fullfile(databases, "the_rankings_2026.json"));
end
pairingPath = options.Pairing;
if strlength(pairingPath) == 0
    pairingPath = string(fullfile(databases, "qs_the_pairing_2026.json"));
end

% --- load both sources -------------------------------------------------------
qs = load_qs_snapshot(options.QsSnapshot);
[theNames, theRanks, thePillars, pillarNames] = load_the_snapshot(thePath);

% --- the reviewed pairing, as a join key neither side can collide with -------
[qsPaired, thePaired] = load_pairing(pairingPath);

qsKeys = join_keys(qs.name, qsPaired);
theKeys = join_keys(theNames, thePaired);

% --- percentile within each source's own population, 0 = best ----------------
qsPercentile = population_percentile(qs.rank);
thePercentile = population_percentile(theRanks);

qsPopulation = sum(~isnan(qs.rank));
thePopulation = sum(~isnan(theRanks));

% --- inner join --------------------------------------------------------------
% Drop duplicate keys before joining so a name collision cannot fan out. Keep
% the first occurrence on each side, matching pandas drop_duplicates(keep=
% "first"), and do it before the rank filter so both ports discard the same rows
% rather than each keeping a different member of a duplicate pair.
qsIndex = find(first_occurrence(qsKeys));
theIndex = find(first_occurrence(theKeys));

% ismember preserves QS order, which the pandas inner merge also does. Row order
% changes no metric, but it does decide the fold assignment, so matching it
% keeps the two ports comparable run for run.
[matched, location] = ismember(qsKeys(qsIndex), theKeys(theIndex));
qsMatched = qsIndex(matched);
theMatched = theIndex(location(matched));

% Only now drop pairs where either source withheld a rank.
usable = ~isnan(qs.rank(qsMatched)) & ~isnan(theRanks(theMatched));
qsMatched = qsMatched(usable);
theMatched = theMatched(usable);

n = numel(qsMatched);

% --- label -------------------------------------------------------------------
gap = abs(qsPercentile(qsMatched) - thePercentile(theMatched));

% pandas Series.quantile interpolates linearly between order statistics placed
% at (i-1)/(n-1). MATLAB prctile places them at (i-0.5)/n instead, which on this
% data shifts the threshold far enough to move universities across the label
% boundary. The convention has to match or the two ports are not labelling the
% same thing.
threshold = linear_quantile(gap, options.Quantile);
y = double(gap > threshold);

X = qs.X(qsMatched, :);

favouredBy = repmat("THE", n, 1);
favouredBy(qsPercentile(qsMatched) < thePercentile(theMatched)) = "QS";

info = struct( ...
    "qsName", qs.name(qsMatched), ...
    "theName", theNames(theMatched), ...
    "qsRank", qs.rank(qsMatched), ...
    "theRank", theRanks(theMatched), ...
    "qsPercentile", qsPercentile(qsMatched), ...
    "thePercentile", thePercentile(theMatched), ...
    "percentileGap", gap, ...
    "favouredBy", favouredBy, ...
    "threshold", threshold, ...
    "quantile", options.Quantile, ...
    "qsIndicators", qs.indicators, ...
    "theFeatures", thePillars(theMatched, :), ...
    "theFeatureNames", pillarNames, ...
    "qsPopulation", qsPopulation, ...
    "thePopulation", thePopulation, ...
    "pairedCount", sum(startsWith(qsKeys(qsMatched), "pair::")));

if options.Verbose
    fprintf("matched %d universities (QS population %d, THE population %d)\n", ...
        n, qsPopulation, thePopulation);
    fprintf("  %d came from the reviewed pairing, %d from a name match\n", ...
        info.pairedCount, n - info.pairedCount);
    fprintf("label: percentile gap > %.4f (%d positives, %.1f%%)\n", ...
        threshold, sum(y), 100 * mean(y));
    fprintf("among disagreeing pairs, THE ranks higher for %d and QS for %d\n", ...
        sum(favouredBy == "THE" & y == 1), sum(favouredBy == "QS" & y == 1));
end

% The dataset this produces is fully deterministic, so it is written out and
% parity-checked against Python. The classifier metrics downstream are not:
% they depend on a fold split whose RNG cannot be aligned across the two
% languages. Checking what can be checked is the point -- the pairing-file
% regression that this port originally had would have shown up here as a
% matched count of 820 against Python's 1082.
if options.SaveOutput
    outDir = options.OutDir;
    if strlength(outDir) == 0
        outDir = string(fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
            "artifacts", "cross_source_matlab"));
    end
    if ~isfolder(outDir)
        mkdir(outDir);
    end

    summary = table( ...
        ["matched"; "qs_population"; "the_population"; "gap_threshold"; ...
         "positives"; "positive_rate"; "favoured_the"; "favoured_qs"; "paired_count"], ...
        [n; qsPopulation; thePopulation; threshold; ...
         sum(y); mean(y); sum(favouredBy == "THE" & y == 1); ...
         sum(favouredBy == "QS" & y == 1); info.pairedCount], ...
        VariableNames=["quantity", "value"]);
    writetable(summary, fullfile(outDir, "dataset_summary.csv"));
    if options.Verbose
        fprintf("written to %s\n", outDir);
    end
end
end


% =============================================================================
% loading
% =============================================================================

function [names, ranks, pillars, pillarNames] = load_the_snapshot(path)
%LOAD_THE_SNAPSHOT THE's rows, ranks and five pillar scores.
%
%   Unlike the QS snapshot, which is a bare JSON array, this file wraps its
%   records in {"rows": [...]}. jsondecode returns a scalar struct there, and
%   reading .name off that struct is the "Unrecognized field name" this used to
%   fail on.
%
%   The rows themselves decode to a struct array -- all 2,191 share the same
%   nine top-level fields -- but metadata.raw_row does not: it carries 31, 32 or
%   33 fields depending on the record. A struct array element may hold a
%   different struct in a given field, so every nested read is guarded rather
%   than assumed.

if ~isfile(path)
    error("build_cross_source_data:missingTheSnapshot", ...
        "THE snapshot not found at %s", path);
end

pillarNames = ["scores_teaching", "scores_research", "scores_citations", ...
               "scores_industry_income", "scores_international_outlook"];

payload = jsondecode(fileread(path));
if isstruct(payload) && isscalar(payload) && isfield(payload, "rows")
    rows = payload.rows;
else
    rows = payload;
end
if isstruct(rows)
    rows = num2cell(rows);
elseif ~iscell(rows)
    error("build_cross_source_data:badThePayload", ...
        "expected a list of rows in %s, got %s", path, class(rows));
end

n = numel(rows);
names = strings(n, 1);
ranks = NaN(n, 1);
pillars = NaN(n, numel(pillarNames));

for i = 1:n
    record = rows{i};
    if ~isstruct(record)
        continue
    end
    if isfield(record, "name")
        names(i) = strtrim(string(record.name));
    end
    if isfield(record, "rank")
        ranks(i) = qs_to_rank(record.rank);
    end

    if ~isfield(record, "metadata") || ~isstruct(record.metadata) ...
            || ~isfield(record.metadata, "raw_row") || ~isstruct(record.metadata.raw_row)
        continue
    end
    raw = record.metadata.raw_row;
    for j = 1:numel(pillarNames)
        if isfield(raw, pillarNames(j))
            pillars(i, j) = qs_to_float(raw.(pillarNames(j)));
        end
    end
end
end


function [qsPaired, thePaired] = load_pairing(path)
%LOAD_PAIRING The warehouse's reviewed QS/THE pairing, as two lookups.
%   A missing file is not an error -- the name join still works, with the
%   smaller overlap it always had.
qsPaired = dictionary(string.empty, string.empty);
thePaired = dictionary(string.empty, string.empty);
if ~isfile(path)
    return
end

payload = jsondecode(fileread(path));
if isstruct(payload)
    payload = num2cell(payload);
end

qsNames = strings(numel(payload), 1);
theNames = strings(numel(payload), 1);
kept = false(numel(payload), 1);
for i = 1:numel(payload)
    row = payload{i};
    if ~isstruct(row) || ~isfield(row, "qs_name") || ~isfield(row, "the_name")
        continue
    end
    qsName = strtrim(string(row.qs_name));
    theName = strtrim(string(row.the_name));
    if strlength(qsName) == 0 || strlength(theName) == 0
        continue
    end
    qsNames(i) = qsName;
    theNames(i) = theName;
    kept(i) = true;
end
qsNames = qsNames(kept);
theNames = theNames(kept);
if isempty(qsNames)
    return
end

% A key the two sides can meet on that no normalised name can collide with,
% indexed off the sorted QS names so a given pair always gets the same key.
[qsSorted, order] = sort(qsNames);
theSorted = theNames(order);
keys = "pair::" + string((0:numel(qsSorted) - 1)');

qsPaired = dictionary(qsSorted, keys);
thePaired = dictionary(theSorted, keys);
end


function path = databases_dir()
% .../crawlernest/crawlernest-ml/matlab/build_cross_source_data.m -> .../crawlernest
crawlernestDir = fileparts(fileparts(fileparts(mfilename("fullpath"))));
path = fullfile(crawlernestDir, "crawlernest-kb", "databases");
end


% =============================================================================
% join and label helpers
% =============================================================================

function keys = join_keys(names, paired)
%JOIN_KEYS Reviewed pairing key where one exists, normalised name otherwise.
keys = regexprep(lower(names), '[^a-z]', '');
if numEntries(paired) == 0
    return
end
known = isKey(paired, names);
if any(known)
    keys(known) = paired(names(known));
end
end


function keep = first_occurrence(keys)
%FIRST_OCCURRENCE Logical mask marking the first row carrying each key.
keep = false(numel(keys), 1);
[~, firstIndex] = unique(keys, "first");
keep(firstIndex) = true;
end


function percentile = population_percentile(ranks)
%POPULATION_PERCENTILE Fractional rank within the non-missing population.
%   Matches pandas Series.rank(method="average", pct=True): ties share their
%   average rank, and the divisor is the count of non-missing values.
percentile = NaN(size(ranks));
valid = ~isnan(ranks);
percentile(valid) = tiedrank(ranks(valid)) / sum(valid);
end


function q = linear_quantile(x, p)
%LINEAR_QUANTILE numpy/pandas default quantile: order statistics at (i-1)/(n-1).
values = sort(x(:));
n = numel(values);
if n == 0
    q = NaN;
elseif n == 1
    q = values;
else
    q = interp1((0:n-1)' / (n - 1), values, p);
end
end
