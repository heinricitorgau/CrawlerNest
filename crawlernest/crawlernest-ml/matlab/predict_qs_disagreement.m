function results = predict_qs_disagreement(options)
%PREDICT_QS_DISAGREEMENT Batch inference for cross-source disagreement.
%
%   Loads the QS snapshot, separates the universities THE has not ranked,
%   fits the production model on everything THE has, and predicts the
%   probability that THE would disagree about each of the rest.
%
%   This is the use the model card claims for the one-sided task: flag contested
%   institutions from QS's view alone, before THE data arrives. For a university
%   THE already ranks, the disagreement is observed rather than predicted, so
%   those rows are the training set and never the output.
%
%   The join, the percentile gap and the label all come from
%   BUILD_CROSS_SOURCE_DATA rather than being re-derived here. An earlier version
%   of this file carried its own copy, which had drifted: it matched on names
%   alone and so trained on 820 universities instead of 1082, and 262 of the
%   institutions it then "predicted" were ones THE had already ranked under a
%   reviewed alias. Calling the shared builder means this file inherits whatever
%   that one is fixed to, and it is the one the parity check covers.
%
%   See also BUILD_CROSS_SOURCE_DATA, TRAIN_DISAGREEMENT_CLASSIFIER.

    arguments
        options.OutputCSV (1,1) string = ""
    end

    % A relative default resolves against pwd, so running this from matlab/ wrote
    % to crawlernest-ml/matlab/artifacts/ rather than the artifacts directory
    % every other port uses. Derive it from this file's own location instead.
    if strlength(options.OutputCSV) == 0
        options.OutputCSV = default_output_csv();
    end

    fprintf('Loading QS snapshot and cross-source metadata...\n');
    qs = load_qs_snapshot();
    [X_train, y, info] = build_cross_source_data(Verbose=false, SaveOutput=false);

    % 1. 分出 THE 已排名（訓練集）與從未涵蓋（推論批次）的大學
    covered = false(numel(qs.name), 1);
    covered(info.qsIndex) = true;

    % QS 有幾列帶著名次卻沒有機構名（name 是 "N/A"）。倉儲的寫入端直接拒收它們
    % （"skip invalid university placeholder row"），這裡也不該替它們預測——
    % 對一個不存在的機構輸出爭議機率，那個數字沒有指涉對象。
    placeholder = ismember(lower(strtrim(string(qs.name))), ["", "n/a", "na", "-", "--"]);

    uncovered = ~covered & ~placeholder;

    X_uncovered = qs.X(uncovered, :);
    uncovered_names = qs.name(uncovered);
    uncovered_ranks = qs.rank(uncovered);
    uncovered_countries = qs.country(uncovered);

    fprintf('Total QS population: %d\n', numel(qs.name));
    fprintf('THE-ranked (training set): %d  (%d via the reviewed pairing)\n', ...
        sum(covered), info.pairedCount);
    fprintf('THE-unranked (inference batch): %d  (%d placeholder rows dropped)\n', ...
        sum(uncovered), sum(placeholder & ~covered));
    fprintf('Label: percentile gap > %.4f (%d positives, %.1f%%)\n', ...
        info.threshold, sum(y), 100 * mean(y));

    % --- 2. 訓練最終的生產模型 (Gradient Boosting) ---
    % 交叉驗證的用途是估計誤差，這裡要的是拿去預測的模型，所以用全部訓練資料重擬合一次。
    fprintf('Fitting final Gradient Boosting model on all training data...\n');

    % 中位數插補：中位數只能來自訓練集，推論列不得參與計算
    train_medians = median(X_train, 1, 'omitnan');
    X_train_imp = X_train;
    X_uncovered_imp = X_uncovered;
    for j = 1:size(X_train, 2)
        X_train_imp(isnan(X_train(:, j)), j) = train_medians(j);
        X_uncovered_imp(isnan(X_uncovered(:, j)), j) = train_medians(j);
    end

    final_model = fitcensemble(X_train_imp, y, ...
        Method="LogitBoost", ...
        NumLearningCycles=300, ...
        LearnRate=0.05, ...
        Learners=templateTree(MaxNumSplits=7), ...
        ClassNames=[0; 1]);

    % predict 回傳的是原始集成分數，不是機率：未轉換時範圍大約 [-8, +2]，把它寫進
    % 一個叫 DisagreementProbability 的欄位會直接誤導讀者。LogitBoost 的模型是
    % F(x) = 0.5 * log(p / (1-p))，所以 p = 1 / (1 + exp(-2F))，即 doublelogit。
    % 排序不受影響（單調變換），但數值的意義完全不同。
    final_model.ScoreTransform = "doublelogit";

    % --- 3. 批次預測未涵蓋大學的分歧機率 ---
    fprintf('Running batch inference on uncovered universities...\n');
    [~, score_uncovered] = predict(final_model, X_uncovered_imp);
    probabilities = score_uncovered(:, 2);   % 類別 1 (Disagreement) 的後驗機率

    % --- 4. 整理並輸出結果 ---
    result_table = table( ...
        uncovered_names, ...
        uncovered_countries, ...
        uncovered_ranks, ...
        probabilities, ...
        VariableNames={'University', 'Country', 'QSRank', 'DisagreementProbability'});

    % 依照預測機率由大到小排序（最容易發生分歧的排在前面）
    result_table = sortrows(result_table, 'DisagreementProbability', 'descend');

    outDir = fileparts(options.OutputCSV);
    if strlength(outDir) > 0 && ~isfolder(outDir)
        mkdir(outDir);
    end
    writetable(result_table, options.OutputCSV);

    fprintf('Predicted probability range [%.4f, %.4f]\n', ...
        min(probabilities), max(probabilities));
    fprintf('Inference results successfully saved to: %s\n', options.OutputCSV);

    results = result_table;
end


function path = default_output_csv()
    % .../crawlernest-ml/matlab/predict_qs_disagreement.m -> .../crawlernest-ml
    mlRoot = fileparts(fileparts(mfilename('fullpath')));
    path = string(fullfile(mlRoot, 'artifacts', 'cross_source_matlab', ...
        'predicted_disagreements.csv'));
end
