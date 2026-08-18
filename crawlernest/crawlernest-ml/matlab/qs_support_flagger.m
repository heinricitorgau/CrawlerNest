function results = qs_support_flagger(options)
%QS_SUPPORT_FLAGGER MATLAB port of ranking_ml.models.support.SupportFlagger.
%
%   results = qs_support_flagger()
%   results = qs_support_flagger(SaveOutput=false)
%
%   Identifies which unlabelled universities are too far from the training
%   distribution to safely predict. It calculates the mean Euclidean distance
%   in standardised indicator space to the 10 nearest training rows. If this
%   distance is <= the 95th percentile of the training set's own distances, it
%   is flagged as "supported".
%
%   The EDA established that the 903 universities whose score QS withholds are
%   not drawn from the same population as the 600 it publishes -- every
%   indicator shifts by 0.67 to 1.91 pooled standard deviations. A model trained
%   on the labelled rows therefore extrapolates when it predicts the unlabelled
%   ones, and a cross-validated error says nothing about how wrong it is out
%   there. This answers the narrower question that can be answered: for one row,
%   how far is it from the training data?
%
%   What it does not do: estimate the error. A supported row can still be
%   predicted badly. It only separates "the model has seen rows like this" from
%   "the model has not".
%
%   ## Two different distances
%
%   The threshold comes from leave-one-out distances -- each training row's mean
%   distance to its 10 nearest *other* training rows. The per-row distance
%   reported for a set is the mean over its 10 nearest training rows including
%   itself where it is one of them, which is why 98.33% of the training set
%   clears a threshold set at its own 95th percentile rather than exactly 95%.
%   Both match the Python side, where `fit` drops the self-match and `distance`
%   does not.
%
%   See also RUN_QS_EDA, LOAD_QS_SNAPSHOT.

arguments
    options.Snapshot (1,1) string = ""
    options.OutDir (1,1) string = ""
    options.SaveOutput (1,1) logical = true
    options.Neighbours (1,1) double = 10
    options.Percentile (1,1) double = 95.0
end

matrix = load_qs_snapshot(options.Snapshot);
indicators = matrix.indicators;
labelled = matrix.labelledMask;

outDir = options.OutDir;
if strlength(outDir) == 0
    outDir = string(fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
        "artifacts", "support_matlab"));
end
if options.SaveOutput && ~isfolder(outDir)
    mkdir(outDir);
end

trainRaw = matrix.X(labelled, :);
inferRaw = matrix.X(~labelled, :);

% --- 1. Imputation (fit on train) --------------------------------------------
% 中位數必須由訓練集 (labelled) 產生，避免資料外洩 (Data Leakage)
trainMedians = median(trainRaw, 1, "omitnan");

trainImputed = trainRaw;
inferImputed = inferRaw;
for j = 1:numel(indicators)
    trainImputed(isnan(trainRaw(:, j)), j) = trainMedians(j);
    inferImputed(isnan(inferRaw(:, j)), j) = trainMedians(j);
end

% --- 2. Scaling (fit on train) -----------------------------------------------
% StandardScaler 預設使用母體標準差 (ddof=0)，MATLAB std 的第二個參數設為 1 即可對齊
trainMu = mean(trainImputed, 1);
trainSigma = std(trainImputed, 1, 1);
trainSigma(trainSigma == 0) = 1;

trainScaled = (trainImputed - trainMu) ./ trainSigma;
inferScaled = (inferImputed - trainMu) ./ trainSigma;

% --- 3. Threshold from leave-one-out distances -------------------------------
% K 設為 neighbours+1，因為第一個命中必定是自己，距離為 0
[~, looNeighbourDistances] = knnsearch(trainScaled, trainScaled, ...
    K=(options.Neighbours + 1));
trainDistances = mean(looNeighbourDistances(:, 2:end), 2);

% np.percentile 的預設慣例是把序位統計量放在 (i-1)/(n-1) 再線性內插；MATLAB
% prctile 放在 (i-0.5)/n。兩者在 n=600 時差 4.8e-3，足以讓 4 所學校跨過門檻，
% 所以這裡不能用 prctile。
threshold = linear_percentile(trainDistances, options.Percentile);

% --- 4. Distance for each set ------------------------------------------------
% 查詢時 K 就是 neighbours，訓練列自己也算在內 —— 與 Python 的 distance() 一致
trainSetDistances = mean_neighbour_distance(trainScaled, trainScaled, options.Neighbours);
inferDistances = mean_neighbour_distance(trainScaled, inferScaled, options.Neighbours);

% --- 5. Report ---------------------------------------------------------------
summary = [ ...
    support_report("labelled", trainSetDistances, threshold); ...
    support_report("unlabelled", inferDistances, threshold)];

fprintf("\n=== Support Flagger Report ===\n");
fprintf("Threshold (P%g of train leave-one-out): %.4f\n\n", options.Percentile, threshold);
disp(summary);
fprintf("%.2f%% of the inference set sits outside the region the model was fitted on.\n", ...
    100 - summary.supported_pct(summary.set == "unlabelled"));

if options.SaveOutput
    writetable(summary, fullfile(outDir, "support_summary.csv"));
    fprintf("\nwritten to %s\n", outDir);
end

results = struct( ...
    "summary", summary, ...
    "threshold", threshold, ...
    "trainDistances", trainDistances, ...
    "trainSetDistances", trainSetDistances, ...
    "inferDistances", inferDistances, ...
    "isSupported", inferDistances <= threshold, ...
    "outDir", outDir);
end


% =============================================================================
% helpers
% =============================================================================

function distances = mean_neighbour_distance(reference, query, k)
%MEAN_NEIGHBOUR_DISTANCE Mean distance from each query row to its k nearest
%   reference rows. A query row that is also a reference row matches itself at
%   distance 0 and that zero is included, matching sklearn's kneighbors.
[~, neighbourDistances] = knnsearch(reference, query, K=k);
distances = mean(neighbourDistances, 2);
end


function row = support_report(label, distances, threshold)
supported = distances <= threshold;
row = table(label, numel(distances), sum(supported), 100 * mean(supported), ...
    median(distances), linear_percentile(distances, 95), threshold, ...
    VariableNames=["set", "n", "supported", "supported_pct", ...
                   "distance_median", "distance_p95", "threshold"]);
end


function q = linear_percentile(x, p)
%LINEAR_PERCENTILE numpy default: order statistics at (i-1)/(n-1), linear interp.
values = sort(x(:));
n = numel(values);
if n == 0
    q = NaN;
elseif n == 1
    q = values;
else
    q = interp1((0:n-1)' / (n - 1) * 100, values, p);
end
end
