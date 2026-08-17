function results = qs_support_flagger(options)
%QS_SUPPORT_FLAGGER MATLAB port of ranking_ml.models.support.SupportFlagger.
%
%   Identifies which unlabelled universities are too far from the training
%   distribution to safely predict. It calculates the mean Euclidean distance
%   in standardised indicator space to the 10 nearest training rows.
%   If this distance is <= the 95th percentile of the training set's own
%   distances, it is flagged as "supported".

arguments
    options.Snapshot (1,1) string = ""
end

matrix = load_qs_snapshot(options.Snapshot);
indicators = matrix.indicators;
labelled = matrix.labelledMask;

X_train_raw = matrix.X(labelled, :);
X_infer_raw = matrix.X(~labelled, :);
n_train = size(X_train_raw, 1);
n_infer = size(X_infer_raw, 1);

% --- 1. Imputation (Fit on Train) ---
% 中位數必須由訓練集 (labelled) 產生，避免資料外洩 (Data Leakage)
train_medians = median(X_train_raw, 1, "omitnan");

X_train_imp = X_train_raw;
X_infer_imp = X_infer_raw;
for j = 1:numel(indicators)
    X_train_imp(isnan(X_train_raw(:, j)), j) = train_medians(j);
    X_infer_imp(isnan(X_infer_raw(:, j)), j) = train_medians(j);
end

% --- 2. Scaling (Fit on Train) ---
% StandardScaler 預設使用母體標準差 (ddof=0)，MATLAB std 的第二個參數設為 1 即可對齊
train_mu = mean(X_train_imp, 1);
train_sigma = std(X_train_imp, 1, 1);

X_train_scaled = (X_train_imp - train_mu) ./ train_sigma;
X_infer_scaled = (X_infer_imp - train_mu) ./ train_sigma;

% --- 3. KNN & Threshold (Fit on Train) ---
n_neighbours = 10;
percentile = 95.0;

% 對訓練集自身尋找最近鄰 (K 設為 11，因為第一個必定是自己，距離為 0)
[~, D_train] = knnsearch(X_train_scaled, X_train_scaled, K=(n_neighbours + 1));

% 捨棄第一欄 (自己與自己的距離)，計算對剩下的 10 個鄰居的平均距離
train_distances = mean(D_train(:, 2:end), 2);

% 計算 95 百分位數作為閥值 (Threshold)
threshold = prctile(train_distances, percentile);

% --- 4. Inference (Predict on Unlabelled) ---
% 對未標記的資料，尋找訓練集中的最近鄰 (K=10)
[~, D_infer] = knnsearch(X_train_scaled, X_infer_scaled, K=n_neighbours);
infer_distances = mean(D_infer, 2);

% 判斷是否受到支援
is_supported = infer_distances <= threshold;

% --- 5. 輸出報告 ---
fprintf("\n=== Support Flagger Report ===\n");
fprintf("Threshold (P95 of train): %.4f\n\n", threshold);

% 輸出 Inference 報告
fprintf("[Inference Set: rank 601-1503]\n");
fprintf("  Total (n):          %d\n", n_infer);
fprintf("  Supported:          %d\n", sum(is_supported));
fprintf("  Supported Pct:      %.2f%%\n", 100 * mean(is_supported));
fprintf("  Distance Median:    %.4f\n", median(infer_distances));
fprintf("  Distance P95:       %.4f\n", prctile(infer_distances, 95));

results = struct( ...
    "train_distances", train_distances, ...
    "threshold", threshold, ...
    "infer_distances", infer_distances, ...
    "is_supported", is_supported);
end
