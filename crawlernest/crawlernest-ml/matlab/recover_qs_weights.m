function results = recover_qs_weights(options)
%RECOVER_QS_WEIGHTS Recover QS's published indicator weighting from the data.
%
%   recover_qs_weights()                    % tables, figures, CSVs
%   recover_qs_weights(Snapshot="...json")  % a different crawl snapshot
%   recover_qs_weights(SaveOutput=false)    % on-screen only, writes nothing
%
%   MATLAB port of the Phase 2 weight recovery in
%   ranking_ml/models/overall_score.py and ranking_ml/evaluation/baselines.py.
%
%   QS combines nine indicators into the overall score as a weighted average and
%   publishes the weighting it uses. Fitting ordinary least squares to the 600
%   rows where the score is published and normalising the coefficients to sum to
%   1 recovers that weighting to a mean absolute error of 0.0006.
%
%   That result reframes what the model is. The overall score is a deterministic
%   weighted sum, so this is **system identification, not forecasting** -- an R2
%   of 0.9997 means the formula was recovered, and must never be read as
%   predictive accuracy on a university whose score QS withheld.
%
%   Keeping QS's published weighting in the comparison is what makes the claim
%   falsifiable. It is not a strawman baseline like "predict the mean"; it is
%   the actual documented mechanism. If the fit did not land on it, something
%   upstream would be wrong, and the discrepancy would show here rather than
%   being absorbed into a slightly better R2.
%
%   Two fits, differing only in how missing indicators are handled:
%
%     linear_raw      median-impute, then OLS on all 600 rows. This is the one
%                     the model card quotes.
%     linear_renorm   OLS on the 593 rows with no missing indicator, then score
%                     a row by renormalising the weights over whatever it does
%                     have. Recovers the weighting an order of magnitude more
%                     closely, because it never borrows a median from the
%                     training distribution.
%
%   See also RUN_QS_EDA, LOAD_QS_SNAPSHOT.

arguments
    options.Snapshot (1,1) string = ""
    options.OutDir (1,1) string = ""
    options.SaveOutput (1,1) logical = true
end

matrix = load_qs_snapshot(options.Snapshot);
outDir = options.OutDir;
if strlength(outDir) == 0
    outDir = string(fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
        "artifacts", "weights_matlab"));
end
if options.SaveOutput && ~isfolder(outDir)
    mkdir(outDir);
end

indicators = matrix.indicators;
published = qs_published_weights();

labelled = matrix.labelledMask;
V = matrix.X(labelled, :);      % raw indicators, NaN preserved
y = matrix.y(labelled);
n = numel(y);

available = isfinite(V);
complete = all(available, 2);

fprintf("labelled rows          %d\n", n);
fprintf("  complete             %d\n", sum(complete));
fprintf("  >=1 missing          %d\n", sum(~complete));

% --- linear_raw --------------------------------------------------------------
% Median imputation first, then OLS with an intercept on the raw 0-100 values.
% No scaling: the coefficients are only comparable to QS's published weights
% because the indicators share a scale, so standardising would destroy exactly
% the interpretation this fit exists for.
Vi = V;
columnMedians = median(V, 1, "omitnan");
for j = 1:size(Vi, 2)
    gaps = isnan(Vi(:, j));
    Vi(gaps, j) = columnMedians(j);
end

rawFit = [ones(n, 1), Vi] \ y;
rawCoefficients = rawFit(2:end);
rawWeights = rawCoefficients / sum(rawCoefficients);
rawPrediction = [ones(n, 1), Vi] * rawFit;

recovery = weight_recovery_table(indicators, published, rawWeights);
fprintf("\n--- linear_raw: recovered weighting vs QS published ---\n");
disp(recovery);
fprintf("weight MAE %.6f   worst %.6f\n", ...
    mean(recovery.abs_error), max(recovery.abs_error));

% --- linear_renorm -----------------------------------------------------------
% Fitted on complete rows only, so no imputed value ever enters the weighting.
% Prediction renormalises the weights over the indicators a row actually has: a
% university missing its international-faculty score is scored on what QS did
% publish for it, not on a median borrowed from institutions it does not
% resemble.
renormFit = [ones(sum(complete), 1), V(complete, :)] \ y(complete);
renormWeights = renormFit(2:end) / sum(renormFit(2:end));

completeAverage = renormalised_average(V(complete, :), renormWeights);
rescale = [ones(sum(complete), 1), completeAverage] \ y(complete);
renormOffset = rescale(1);
renormScale = rescale(2);
renormPrediction = renormalised_average(V, renormWeights) * renormScale + renormOffset;

renormRecovery = weight_recovery_table(indicators, published, renormWeights);
fprintf("\n--- linear_renorm: recovered weighting vs QS published ---\n");
disp(renormRecovery);
fprintf("weight MAE %.6f   worst %.6f   (scale %.4f, offset %.4f)\n", ...
    mean(renormRecovery.abs_error), max(renormRecovery.abs_error), ...
    renormScale, renormOffset);

% --- the non-learned baseline ------------------------------------------------
baselinePrediction = renormalised_average(V, published);

fits = ["QS published weighting (no fit)"; "linear_raw"; "linear_renorm"];
predictions = [baselinePrediction, rawPrediction, renormPrediction];
rmse = zeros(3, 1); mae = zeros(3, 1); r2 = zeros(3, 1);
for k = 1:3
    [rmse(k), mae(k), r2(k)] = regression_metrics(y, predictions(:, k));
end
fit = table(fits, rmse, mae, r2, repmat(n, 3, 1), ...
    VariableNames=["fit", "rmse", "mae", "r2", "n"]);
fprintf("\n--- in-sample fit on the 600 labelled rows ---\n");
disp(fit);
fprintf("Read these as recovery, not accuracy. The target is a deterministic\n" + ...
        "function of the features, so a near-perfect R2 is the expected result\n" + ...
        "and says nothing about the 903 rows whose score QS withheld.\n");

% --- correlation is not importance -------------------------------------------
% The recovered weight beside the Pearson correlation with the target. Citations
% per Faculty carries 20% of the score and correlates at 0.476, below three
% indicators weighted at 5%: a weight cannot be read off a correlation.
pearson = corr(Vi, y);
importance = table(indicators', published, rawWeights, pearson, ...
    VariableNames=["indicator", "qs_published", "recovered", "pearson_r"]);
importance = sortrows(importance, "qs_published", "descend");
fprintf("\n--- weight vs correlation ---\n");
disp(importance);

% --- figures -----------------------------------------------------------------
figures = struct();
figures.recovery = plot_weight_recovery(recovery);
figures.importance = plot_weight_vs_correlation(importance);

if options.SaveOutput
    exportgraphics(figures.recovery, fullfile(outDir, "weight_recovery.png"), Resolution=150);
    exportgraphics(figures.importance, fullfile(outDir, "weight_vs_correlation.png"), Resolution=150);
    writetable(recovery, fullfile(outDir, "weight_recovery_linear_raw.csv"));
    writetable(renormRecovery, fullfile(outDir, "weight_recovery_linear_renorm.csv"));
    writetable(fit, fullfile(outDir, "in_sample_fit.csv"));
    writetable(importance, fullfile(outDir, "weight_vs_correlation.csv"));
    fprintf("\nwritten to %s\n", outDir);
end

% --- parity with the Python run ----------------------------------------------
parity = parity_check(rawWeights, renormWeights, [renormScale; renormOffset], ...
    rmse, mae, r2);

results = struct( ...
    "matrix", matrix, ...
    "recovery", recovery, ...
    "renormRecovery", renormRecovery, ...
    "fit", fit, ...
    "importance", importance, ...
    "rawWeights", rawWeights, ...
    "rawIntercept", rawFit(1), ...
    "renormWeights", renormWeights, ...
    "renormScale", renormScale, ...
    "renormOffset", renormOffset, ...
    "figures", figures, ...
    "parity", parity, ...
    "outDir", outDir);
end


% =============================================================================
% analysis helpers
% =============================================================================

function weights = qs_published_weights()
%QS_PUBLISHED_WEIGHTS QS World University Rankings 2026 methodology, in
%   QS_INDICATORS column order. Mirrors ranking_ml.features.schema. Sums to 1.
weights = [0.30; 0.15; 0.10; 0.20; 0.05; 0.05; 0.05; 0.05; 0.05];
end


function average = renormalised_average(V, weights)
%RENORMALISED_AVERAGE Weighted average over the indicators a row actually has.
%   Missing indicators drop out of both the numerator and the weight mass, so
%   the weights are rescaled to sum to 1 across whatever is present. Rows with
%   no indicator at all return NaN rather than 0.
available = isfinite(V);
values = V;
values(~available) = 0;
mass = available * weights;
average = NaN(size(V, 1), 1);
usable = mass > 0;
average(usable) = (values(usable, :) * weights) ./ mass(usable);
end


function recovery = weight_recovery_table(indicators, published, recovered)
recovery = table(indicators', published, recovered, abs(recovered - published), ...
    VariableNames=["indicator", "qs_published", "recovered", "abs_error"]);
recovery = sortrows(recovery, "qs_published", "descend");
end


function [rmse, mae, r2] = regression_metrics(yTrue, yPred)
residual = yTrue - yPred;
rmse = sqrt(mean(residual .^ 2));
mae = mean(abs(residual));
r2 = 1 - sum(residual .^ 2) / sum((yTrue - mean(yTrue)) .^ 2);
end


function parity = parity_check(rawWeights, renormWeights, renormRescale, rmse, mae, r2)
%PARITY_CHECK Compare against ranking_ml.models.overall_score on this snapshot.
%   Reference values are hard-coded on purpose: a silent divergence between the
%   two ports is exactly the failure this check exists to catch.

referenceRaw = [0.2995729900; 0.1504254700; 0.0993226800; 0.1992050400; ...
                0.0493494600; 0.0507926100; 0.0499196600; 0.0505950400; 0.0508170500];
referenceRenorm = [0.2999033359; 0.1500915213; 0.1000148317; 0.2000156829; ...
                   0.0500331921; 0.0499667104; 0.0500394654; 0.0499315319; 0.0500037283];
referenceRescale = [1.0263566439; -1.6630437711];

% rows: published baseline, linear_raw, linear_renorm
referenceRmse = [0.7829365527; 0.3128385694; 0.2140776054];
referenceMae  = [0.6785285088; 0.0882161259; 0.0459819738];
referenceR2   = [0.9982676862; 0.9997234243; 0.9998704862];

parity = table( ...
    ["linear_raw recovered weights"; "linear_renorm recovered weights"; ...
     "linear_renorm scale / offset"; "RMSE, all three fits"; ...
     "MAE, all three fits"; "R2, all three fits"], ...
    [max(abs(rawWeights - referenceRaw)); ...
     max(abs(renormWeights - referenceRenorm)); ...
     max(abs(renormRescale - referenceRescale)); ...
     max(abs(rmse - referenceRmse)); ...
     max(abs(mae - referenceMae)); ...
     max(abs(r2 - referenceR2))], ...
    VariableNames=["quantity", "max_abs_deviation_from_python"]);

fprintf("\n--- parity with ranking_ml.models.overall_score ---\n");
disp(parity);
if max(parity.max_abs_deviation_from_python) > 1e-6
    warning("recover_qs_weights:parityDrift", ...
        "MATLAB output has drifted from the Python fit by more than 1e-6. " + ...
        "Do not trust the recovered weighting until this is explained.");
end
end


% =============================================================================
% figures
% =============================================================================

function fig = plot_weight_recovery(recovery)
fig = figure(Name="weight_recovery", Position=[100 100 900 500], Color="w");
ax = axes(fig);
bars = bar(ax, [recovery.qs_published, recovery.recovered]);
bars(1).FaceColor = "#b0b7c3";
bars(2).FaceColor = "#4c72b0";

set(ax, XTick=1:height(recovery), XTickLabel=recovery.indicator, ...
    XTickLabelRotation=30, FontSize=9, TickLabelInterpreter="none");
ylabel(ax, "weight");
legend(ax, ["QS published", "recovered by OLS"], Location="northeast");
title(ax, sprintf("QS weighting recovered from 600 labelled rows (MAE %.4f, worst %.4f)", ...
    mean(recovery.abs_error), max(recovery.abs_error)), FontSize=11);
grid(ax, "on");
ax.GridAlpha = 0.15;
ax.XGrid = "off";
end


function fig = plot_weight_vs_correlation(importance)
fig = figure(Name="weight_vs_correlation", Position=[100 100 800 620], Color="w");
ax = axes(fig);
hold(ax, "on");

scatter(ax, importance.pearson_r, importance.recovered, 60, "filled", ...
    MarkerFaceColor="#4c72b0", MarkerFaceAlpha=0.8);

% Five indicators sit at weight 0.05, so labels placed beside the marker
% collide. Label above instead, cycling through three heights in x order so
% neighbouring labels never share a line.
[~, xOrder] = sort(importance.pearson_r);
offsets = [0.011, 0.023, 0.035];
labels = short_labels(importance.indicator);
for k = 1:numel(xOrder)
    i = xOrder(k);
    text(ax, importance.pearson_r(i), ...
        importance.recovered(i) + offsets(mod(k - 1, 3) + 1), labels(i), ...
        FontSize=8, HorizontalAlignment="center", VerticalAlignment="middle", ...
        Interpreter="none");
end

% Citations per Faculty is the point that makes the argument: high weight, low
% correlation. Ring it rather than relying on the reader to find it.
outlier = importance.indicator == "Citations per Faculty";
if any(outlier)
    scatter(ax, importance.pearson_r(outlier), importance.recovered(outlier), 200, ...
        MarkerEdgeColor="#c0392b", LineWidth=1.5);
end

xlabel(ax, "Pearson r with Overall Score");
ylabel(ax, "recovered weight");
title(ax, "A weight cannot be read off a correlation", FontSize=11);
xlim(ax, [0.25 1.0]);
ylim(ax, [0 0.35]);
grid(ax, "on");
ax.GridAlpha = 0.15;
hold(ax, "off");
end


function short = short_labels(names)
%SHORT_LABELS Abbreviated indicator names, so nine labels fit without collision.
%   The printed tables keep the full names; this is presentation only.
short = names;
short = replace(short, "International ", "Intl ");
short = replace(short, " Reputation", " Rep.");
short = replace(short, "Employment Outcomes", "Employment Out.");
short = replace(short, "Faculty Student Ratio", "Faculty/Student");
short = replace(short, "Citations per Faculty", "Citations/Faculty");
short = replace(short, "Sustainability Score", "Sustainability");
end
