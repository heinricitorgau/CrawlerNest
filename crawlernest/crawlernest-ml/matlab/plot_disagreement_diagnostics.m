function outPath = plot_disagreement_diagnostics(y, proba, outPath)
%PLOT_DISAGREEMENT_DIAGNOSTICS The 3-panel Phase 3 diagnostics, as Python draws them.
%
%   plot_disagreement_diagnostics(y, results.probaBoosted)
%   plot_disagreement_diagnostics(y, proba, "somewhere/else.png")
%
%   Panels:
%     1. ROC curve, with AUC and the chance diagonal
%     2. Precision-recall curve, with average precision and the base rate
%     3. Reliability diagram, with the Brier score
%
%   Mirrors plot_diagnostics in ranking_ml/training/train_disagreement.py.
%
%   PROBA must be a probability. The boosted model's raw ensemble score is not
%   one -- untransformed it spans roughly [-8, +2] -- which leaves the Brier
%   score and the whole third panel meaningless. TRAIN_DISAGREEMENT_CLASSIFIER
%   applies LogitBoost's doublelogit transform, so `results.probaBoosted` is
%   safe to pass here; a raw score is rejected below rather than plotted.
%
%   Panels 1 and 2 are rank-based and would survive an uncalibrated score. Only
%   panel 3 depends on the values themselves, which is exactly why it is the one
%   that exposes a miscalibrated model.
%
%   See also TRAIN_DISAGREEMENT_CLASSIFIER, BUILD_CROSS_SOURCE_DATA.

arguments
    y (:,1) double
    proba (:,1) double
    outPath (1,1) string = default_out_path()
end

if any(proba < 0 | proba > 1)
    outside = sum(proba < 0 | proba > 1);
    error("plot_disagreement_diagnostics:notAProbability", ...
        "proba must lie in [0,1]; %d of %d values do not (range [%.4f, %.4f]). " + ...
        "A raw LogitBoost score needs its doublelogit transform first.", ...
        outside, numel(proba), min(proba), max(proba));
end

outDir = fileparts(outPath);
if strlength(outDir) > 0 && ~isfolder(outDir)
    mkdir(outDir);
end

positiveRate = mean(y);
fig = figure(Name="disagreement_diagnostics", Position=[100 100 1350 420], Color="w");

% --- 1. ROC ------------------------------------------------------------------
subplot(1, 3, 1);
[falsePositiveRate, truePositiveRate, ~, auc] = perfcurve(y, proba, 1);
plot(falsePositiveRate, truePositiveRate, Color="#4c72b0", LineWidth=2, ...
    DisplayName=sprintf("AUC = %.3f", auc));
hold on;
plot([0 1], [0 1], "--", Color="#999999", LineWidth=1, DisplayName="chance (0.500)");
hold off;
xlabel("false positive rate");
ylabel("true positive rate");
title("ROC");
legend(Location="southeast", FontSize=8);
grid on;
box on;

% --- 2. Precision-recall -----------------------------------------------------
subplot(1, 3, 2);
[recall, precision, ap] = precision_recall_curve(y, proba);

plot(recall, precision, Color="#dd8452", LineWidth=2, ...
    DisplayName=sprintf("AP = %.3f", ap));
hold on;
yline(positiveRate, "--", Color="#999999", LineWidth=1, ...
    DisplayName=sprintf("chance (%.3f)", positiveRate));
hold off;
xlabel("recall");
ylabel("precision");
title("Precision-recall");
legend(Location="northeast", FontSize=8);
xlim([0 1]);
ylim([0 1.05]);
grid on;
box on;

% --- 3. Calibration ----------------------------------------------------------
subplot(1, 3, 3);
[predictedFraction, observedFraction] = calibration_curve(y, proba, 10);
brier = mean((proba - y) .^ 2);

plot(predictedFraction, observedFraction, "o-", Color="#55a868", LineWidth=2, ...
    MarkerFaceColor="#55a868", DisplayName="model");
hold on;
plot([0 1], [0 1], "--", Color="#999999", LineWidth=1, ...
    DisplayName="perfectly calibrated");
hold off;
xlabel("mean predicted probability");
ylabel("observed frequency");
title(sprintf("Calibration (Brier = %.3f)", brier));
legend(Location="northwest", FontSize=8);
xlim([0 1]);
ylim([0 1]);
grid on;
box on;

sgtitle("Cross-source disagreement, predicted from QS indicators alone (out-of-fold)", ...
    FontSize=11);

exportgraphics(fig, outPath, Resolution=150);
fprintf("ROC-AUC %.4f   AP %.4f   Brier %.4f\n", auc, ap, brier);
fprintf("Diagnostic plot saved to: %s\n", outPath);
end


% =============================================================================
% helpers
% =============================================================================

function path = default_out_path()
% .../crawlernest-ml/matlab/plot_disagreement_diagnostics.m -> .../crawlernest-ml
mlRoot = fileparts(fileparts(mfilename("fullpath")));
path = string(fullfile(mlRoot, "artifacts", "cross_source_matlab", ...
    "disagreement_diagnostics.png"));
end


function [recall, precision, ap] = precision_recall_curve(y, score)
%PRECISION_RECALL_CURVE sklearn precision_recall_curve and average_precision_score.
%
%   Average precision is sum over thresholds of the recall increment times the
%   precision *at that threshold*: sum((R_n - R_{n-1}) * P_n). Pairing the
%   increment with the preceding precision instead understates it -- by 0.008 on
%   this data -- and is not what sklearn reports.
%
%   Rows sharing a score collapse into a single threshold, so a block of equal
%   probabilities cannot be counted more than once.
[sorted, order] = sort(score(:), "descend");
positive = y(order) > 0;

truePositives = cumsum(positive);
falsePositives = cumsum(~positive);

lastOfRun = [sorted(1:end-1) ~= sorted(2:end); true];
truePositives = truePositives(lastOfRun);
falsePositives = falsePositives(lastOfRun);

precision = truePositives ./ (truePositives + falsePositives);
recall = truePositives / truePositives(end);
ap = sum(diff([0; recall]) .* precision);

% Close the curve at recall 0 for drawing, as sklearn's curve does.
recall = [0; recall];
precision = [1; precision];
end


function [predictedFraction, observedFraction] = calibration_curve(y, proba, nBins)
%CALIBRATION_CURVE sklearn calibration_curve(strategy="quantile").
%
%   Bin edges are quantiles of the predicted probability. MATLAB's `quantile`
%   places order statistics at (i-0.5)/n where numpy uses (i-1)/(n-1); on this
%   data that moves the edges by 3.0e-3, so the edges are interpolated
%   explicitly instead.
%
%   Empty bins are dropped rather than emitted as NaN, again matching sklearn: a
%   NaN would break the line where sklearn simply has one point fewer.
sortedProba = sort(proba);
n = numel(sortedProba);
edges = interp1((0:n-1)' / (n - 1), sortedProba, linspace(0, 1, nBins + 1))';

predictedFraction = NaN(nBins, 1);
observedFraction = NaN(nBins, 1);
for b = 1:nBins
    if b == nBins
        inBin = proba >= edges(b) & proba <= edges(b + 1);
    else
        inBin = proba >= edges(b) & proba < edges(b + 1);
    end
    if any(inBin)
        predictedFraction(b) = mean(proba(inBin));
        observedFraction(b) = mean(y(inBin));
    end
end

populated = ~isnan(predictedFraction);
predictedFraction = predictedFraction(populated);
observedFraction = observedFraction(populated);
end
