function results = train_disagreement_classifier(X, y, options)
%TRAIN_DISAGREEMENT_CLASSIFIER MATLAB port of ranking_ml.training.train_disagreement.
%
%   results = train_disagreement_classifier(X, y)
%   results = train_disagreement_classifier(X, y, Name="both_sources")
%
%   Stratified k-fold cross-validation producing out-of-fold probabilities, then
%   ROC-AUC and PR-AUC computed from them.
%
%   ## What this asks, and what it deliberately does not
%
%   The label is built from how far apart QS and THE place the same university.
%   Both ranks are close to deterministic functions of their own published
%   component scores, so a classifier given *both* sources' scores is not
%   predicting anything -- it is recomputing a quantity it was handed the inputs
%   to. Such a model scores well and means nothing.
%
%   The task modelled is therefore one-sided: given only what QS published, can
%   we anticipate that THE will disagree? Pass X = the nine QS indicators for
%   that. Passing [X info.theFeatures] fits the two-sided ceiling, which is
%   worth reporting only because it is labelled as a ceiling.
%
%   ## Leakage
%
%   Median imputation and standardisation are fitted inside each training fold
%   and applied to the held-out fold. Fitting either on the full matrix would
%   leak the test rows into the preprocessing and inflate every number below.
%
%   PR-AUC is the honest headline on this problem: the positive rate is 0.20, so
%   ROC-AUC flatters an imbalanced label while precision-recall does not.
%
%   Both models return calibrated probabilities, so `results.probaBoosted` can be
%   scored with Brier and drawn on a reliability diagram -- see
%   PLOT_DISAGREEMENT_DIAGNOSTICS.
%
%   See also BUILD_CROSS_SOURCE_DATA, PLOT_DISAGREEMENT_DIAGNOSTICS.

arguments
    X double
    y double
    options.Folds (1,1) double = 5
    options.Seed (1,1) double = 0
    options.Name (1,1) string = "qs_only"
    options.Verbose (1,1) logical = true
end

y = y(:);
n = numel(y);
if size(X, 1) ~= n
    error("train_disagreement_classifier:shapeMismatch", ...
        "X has %d rows but y has %d", size(X, 1), n);
end

% cvpartition stratifies on the grouping vector it is given, so the class
% balance of every fold matches the whole. Seeded because the fold split is the
% only stochastic part of this run.
rng(options.Seed);
cv = cvpartition(y, KFold=options.Folds);

probaLogistic = NaN(n, 1);
probaBoosted = NaN(n, 1);

for fold = 1:options.Folds
    trainMask = training(cv, fold);
    testMask = test(cv, fold);

    XTrainRaw = X(trainMask, :);
    XTestRaw = X(testMask, :);
    yTrain = y(trainMask);

    % --- median imputation, fitted on the training fold only -----------------
    [XTrain, XTest] = impute_median(XTrainRaw, XTestRaw);

    % --- standardisation, fitted on the training fold only -------------------
    % StandardScaler uses the population standard deviation (ddof=0), which is
    % std(.,1). A zero-variance column is left alone rather than dividing by
    % zero, matching sklearn.
    [XTrainScaled, XTestScaled] = standardise(XTrain, XTest);

    % --- logistic regression, L2 ---------------------------------------------
    % sklearn LogisticRegression(C=1) minimises mean log-loss + ||w||^2/(2*C*n),
    % so the equivalent fitclinear ridge strength is Lambda = 1/(C*n) with n the
    % training-fold size. The bias is unpenalised on both sides.
    logisticModel = fitclinear(XTrainScaled, yTrain, ...
        Learner="logistic", Regularization="ridge", ...
        Lambda=1 / numel(yTrain), Solver="lbfgs", ...
        ClassNames=[0; 1]);
    probaLogistic(testMask) = logistic_probability(logisticModel, XTestScaled);

    % --- gradient boosting ----------------------------------------------------
    % Trees are invariant to a monotone rescale of each feature, so this is
    % fitted on the imputed-but-unscaled matrix, matching the Python pipeline
    % which scales only for the linear model. max_depth=3 has no direct
    % equivalent in templateTree; MaxNumSplits=7 is the standard proxy.
    boostedModel = fitcensemble(XTrain, yTrain, ...
        Method="LogitBoost", ...
        NumLearningCycles=300, ...
        LearnRate=0.05, ...
        Learners=templateTree(MaxNumSplits=7), ...
        ClassNames=[0; 1]);

    % predict returns a raw ensemble score, not a probability: untransformed it
    % spans roughly [-8, +2] here, and treating that as a probability makes the
    % Brier score and the calibration curve meaningless. LogitBoost models
    % F(x) = 0.5 * log(p / (1-p)), so p = 1 / (1 + exp(-2F)) -- which MATLAB
    % exposes as the "doublelogit" transform. Chosen from the algorithm's own
    % formulation, not by which number came closest to the Python run.
    % Rank-based metrics are unaffected: the transform is monotone.
    boostedModel.ScoreTransform = "doublelogit";
    [~, boostedScore] = predict(boostedModel, XTest);
    probaBoosted(testMask) = boostedScore(:, 2);
end

positiveRate = mean(y);
models = ["logistic", "gradient_boosting"];
scores = [probaLogistic, probaBoosted];

rocAuc = zeros(2, 1);
prAuc = zeros(2, 1);
brier = zeros(2, 1);
for k = 1:2
    [~, ~, ~, rocAuc(k)] = perfcurve(y, scores(:, k), 1);
    prAuc(k) = average_precision(y, scores(:, k));
    brier(k) = mean((scores(:, k) - y) .^ 2);
end

metrics = table(models', rocAuc, prAuc, brier, ...
    VariableNames=["model", "roc_auc", "pr_auc", "brier"]);

if options.Verbose
    fprintf("\n%s  (n=%d, %d features, positive rate %.4f, %d-fold stratified)\n", ...
        options.Name, n, size(X, 2), positiveRate, options.Folds);
    for k = 1:2
        fprintf("  %-18s ROC-AUC %.4f   PR-AUC %.4f   Brier %.4f\n", ...
            models(k), rocAuc(k), prAuc(k), brier(k));
    end
end

results = struct( ...
    "name", options.Name, ...
    "metrics", metrics, ...
    "probaLogistic", probaLogistic, ...
    "probaBoosted", probaBoosted, ...
    "positiveRate", positiveRate, ...
    "folds", options.Folds, ...
    "seed", options.Seed, ...
    "partition", cv);
end


% =============================================================================
% preprocessing, fitted on the training fold only
% =============================================================================

function [XTrain, XTest] = impute_median(XTrain, XTest)
medians = median(XTrain, 1, "omitnan");
for j = 1:size(XTrain, 2)
    if isnan(medians(j))
        medians(j) = 0;   % a column missing throughout the fold
    end
    XTrain(isnan(XTrain(:, j)), j) = medians(j);
    XTest(isnan(XTest(:, j)), j) = medians(j);
end
end


function [XTrainScaled, XTestScaled] = standardise(XTrain, XTest)
mu = mean(XTrain, 1);
sigma = std(XTrain, 1, 1);
sigma(sigma == 0) = 1;
XTrainScaled = (XTrain - mu) ./ sigma;
XTestScaled = (XTest - mu) ./ sigma;
end


% =============================================================================
% metrics
% =============================================================================

function probability = logistic_probability(model, XTest)
%LOGISTIC_PROBABILITY Posterior for the positive class, computed explicitly.
%   ClassificationLinear reports a raw linear score whose meaning depends on the
%   learner, so the sigmoid is applied here rather than assumed. The score is
%   oriented towards the second entry of ClassNames.
if model.ClassNames(2) ~= 1
    error("train_disagreement_classifier:classOrder", ...
        "expected ClassNames(2) == 1, got %g", model.ClassNames(2));
end
z = XTest * model.Beta + model.Bias;
probability = 1 ./ (1 + exp(-z));
end


function ap = average_precision(y, score)
%AVERAGE_PRECISION sklearn average_precision_score: sum over thresholds of the
%   recall increment times the precision there. A step-wise sum, not the
%   trapezoid perfcurve would integrate, and tied scores collapse into one
%   threshold so a block of equal probabilities cannot be counted twice.
[sorted, order] = sort(score(:), "descend");
positive = y(order) > 0;

truePositives = cumsum(positive);
falsePositives = cumsum(~positive);

% Keep only the last row of each run of equal scores: one threshold per value.
lastOfRun = [sorted(1:end-1) ~= sorted(2:end); true];
truePositives = truePositives(lastOfRun);
falsePositives = falsePositives(lastOfRun);

if truePositives(end) == 0
    ap = NaN;
    return
end
precision = truePositives ./ (truePositives + falsePositives);
recall = truePositives / truePositives(end);
ap = sum(diff([0; recall]) .* precision);
end
