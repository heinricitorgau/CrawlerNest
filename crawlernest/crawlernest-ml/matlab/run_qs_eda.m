function results = run_qs_eda(options)
%RUN_QS_EDA MATLAB port of the QS indicator EDA (ranking_ml.eda.run_eda).
%
%   run_qs_eda()                       % figures + tables into artifacts/eda_matlab/
%   run_qs_eda(Snapshot="...json")     % analyse a different crawl snapshot
%   run_qs_eda(OutDir="...")           % write elsewhere
%   run_qs_eda(SaveFigures=false)      % on-screen only, write nothing
%
%   Reproduces the three figures and the four numeric tables that the Phase 2
%   modelling decisions rest on:
%
%     1. correlation_heatmap  indicator correlation on the 600 labelled rows
%     2. target_distribution  the published Overall Score, ranks 1-600
%     3. pca_scatter          all 1,503 rows, training set vs inference set
%
%   The question the analysis exists to answer is not "are the indicators
%   correlated" -- of course they are -- but *how far the 903 unlabelled rows
%   sit from the 600 labelled ones*. Training on ranks 1-600 and predicting
%   601-1503 is extrapolation, not interpolation.
%
%   Output goes to artifacts/eda_matlab/, deliberately separate from the
%   Python-committed artifacts/eda/ so neither run clobbers the other.
%
%   A parity check against the committed Python numbers runs at the end and
%   prints the largest absolute deviation per table. If a deviation is not
%   ~1e-4 the port has drifted and the figures should not be trusted.

arguments
    options.Snapshot (1,1) string = ""
    options.OutDir (1,1) string = ""
    options.SaveFigures (1,1) logical = true
end

matrix = load_qs_snapshot(options.Snapshot);
outDir = options.OutDir;
if strlength(outDir) == 0
    outDir = string(fullfile(fileparts(fileparts(mfilename("fullpath"))), ...
        "artifacts", "eda_matlab"));
end
if options.SaveFigures && ~isfolder(outDir)
    mkdir(outDir);
end

indicators = matrix.indicators;
labelled = matrix.labelledMask;
nLab = sum(labelled);

fprintf("rows              %d\n", size(matrix.X, 1));
fprintf("indicators        %d\n", numel(indicators));
fprintf("labelled (train)  %d   rank range %g-%g\n", nLab, ...
    min(matrix.rank(labelled)), max(matrix.rank(labelled)));
fprintf("unlabelled (infer)%d   rank range %g-%g\n", sum(~labelled), ...
    min(matrix.rank(~labelled)), max(matrix.rank(~labelled)));
fprintf("snapshot          %s\n", matrix.snapshotPath);

% --- missingness -------------------------------------------------------------
% Every indicator is present on every record, but some carry "n/a". Median
% imputation is the current strategy; this table exists so that stays a visible
% decision rather than a silent default.
missingCount = sum(isnan(matrix.X), 1)';
missingness = table(indicators', missingCount, ...
    round(100 * missingCount / size(matrix.X, 1), 2), ...
    VariableNames=["indicator", "missing", "missing_pct"]);
missingness = sortrows(missingness, "missing", "descend");
fprintf("\n--- missingness ---\n");
disp(missingness);

% --- correlation with the target --------------------------------------------
% Imputed over the labelled rows only, matching the Python side: the heatmap
% describes the training set, so the medians come from the training set.
labelledImputed = median_impute(matrix.X(labelled, :));
yLab = matrix.y(labelled);

corrToTarget = corr(labelledImputed, yLab);
[sortedCorr, order] = sort(corrToTarget, "descend");
correlationTable = table(indicators(order)', sortedCorr, ...
    VariableNames=["indicator", "pearson_r"]);
fprintf("\n--- indicator correlation with %s (labelled rows) ---\n", matrix.targetLabel);
disp(correlationTable);

% --- covariate shift ---------------------------------------------------------
% Cohen's d between the 600 labelled and 903 unlabelled rows. Anything past
% roughly 0.8 is a large shift, and means a cross-validated error on the
% labelled rows understates the error a model makes on the unlabelled ones.
allImputed = median_impute(matrix.X);
shift = covariate_shift(allImputed, labelled, indicators);
fprintf("\n--- covariate shift, labelled vs unlabelled (Cohen's d) ---\n");
disp(shift);

% --- PCA ---------------------------------------------------------------------
% StandardScaler uses the population standard deviation (ddof=0); std(X,1)
% matches it. Using std(X) here would put PC1 off by ~0.03% of variance.
scaled = (allImputed - mean(allImputed, 1)) ./ std(allImputed, 1, 1);
[coeff, score, ~, ~, explained] = pca(scaled, Algorithm="svd", NumComponents=2);

% PCA component signs are arbitrary. Fix them so a rerun -- and the Python
% figure -- orient the same way.
for k = 1:size(coeff, 2)
    if sum(coeff(:, k)) < 0
        coeff(:, k) = -coeff(:, k);
        score(:, k) = -score(:, k);
    end
end

fprintf("\n--- PCA ---\n");
fprintf("PC1 %.1f%%, PC2 %.1f%%, cumulative %.1f%%\n", ...
    explained(1), explained(2), explained(1) + explained(2));

% --- figures -----------------------------------------------------------------
figures = struct();
figures.correlation = plot_correlation(labelledImputed, yLab, indicators, ...
    matrix.targetLabel, nLab);
figures.target = plot_target_distribution(yLab, matrix.targetLabel);
figures.pca = plot_pca(score, explained, matrix.rank, labelled);

if options.SaveFigures
    written = strings(0, 1);
    written(end+1) = save_figure(figures.correlation, outDir, "correlation_heatmap.png");
    written(end+1) = save_figure(figures.target, outDir, "target_distribution.png");
    written(end+1) = save_figure(figures.pca, outDir, "pca_scatter.png");

    writetable(missingness, fullfile(outDir, "missingness.csv"));
    writetable(correlationTable, fullfile(outDir, "correlation_with_target.csv"));
    writetable(shift, fullfile(outDir, "covariate_shift.csv"));

    fprintf("\nwritten:\n");
    for k = 1:numel(written)
        fprintf("  %s\n", written(k));
    end
    fprintf("  %s\n", fullfile(outDir, "missingness.csv"));
    fprintf("  %s\n", fullfile(outDir, "correlation_with_target.csv"));
    fprintf("  %s\n", fullfile(outDir, "covariate_shift.csv"));
end

% --- parity with the Python run ----------------------------------------------
parity = parity_check(correlationTable, shift, explained, yLab);

results = struct( ...
    "matrix", matrix, ...
    "missingness", missingness, ...
    "correlation", correlationTable, ...
    "covariateShift", shift, ...
    "explained", explained(1:2), ...
    "pcaScore", score, ...
    "pcaLoadings", coeff, ...
    "figures", figures, ...
    "parity", parity, ...
    "outDir", outDir);
end


% =============================================================================
% analysis helpers
% =============================================================================

function imputed = median_impute(X)
%MEDIAN_IMPUTE Column-wise median imputation, ignoring NaN when taking the median.
%   Matches sklearn SimpleImputer(strategy="median").
imputed = X;
columnMedians = median(X, 1, "omitnan");
for j = 1:size(X, 2)
    gaps = isnan(imputed(:, j));
    imputed(gaps, j) = columnMedians(j);
end
end


function shift = covariate_shift(imputed, labelled, indicators)
%COVARIATE_SHIFT Per-indicator difference in means, in pooled standard deviations.
n = numel(indicators);
labelledMean = zeros(n, 1);
unlabelledMean = zeros(n, 1);
gap = zeros(n, 1);

for j = 1:n
    a = imputed(labelled, j);
    b = imputed(~labelled, j);
    pooled = sqrt(((var(a) * (numel(a) - 1)) + (var(b) * (numel(b) - 1))) ...
        / (numel(a) + numel(b) - 2));
    labelledMean(j) = mean(a);
    unlabelledMean(j) = mean(b);
    if pooled > 0
        gap(j) = (mean(a) - mean(b)) / pooled;
    else
        gap(j) = NaN;
    end
end

shift = table(indicators', labelledMean, unlabelledMean, gap, ...
    VariableNames=["indicator", "labelled_mean", "unlabelled_mean", "standardised_gap"]);
[~, order] = sort(abs(shift.standardised_gap), "descend");
shift = shift(order, :);
end


function parity = parity_check(correlationTable, shift, explained, yLab)
%PARITY_CHECK Compare against the numbers the Python EDA produced on this snapshot.
%   Reference values come from ranking_ml.eda.run_eda on
%   last_crawl_snapshot.json (QS 2026, 1,504 rows). They are hard-coded on
%   purpose: a silent divergence between the two ports is exactly the failure
%   this check exists to catch.
%
%   They are therefore tied to one snapshot. Refreshing the snapshot moves
%   every number below, and this check fires on the refresh itself -- which is
%   correct, and is not the same thing as the ports disagreeing. Re-derive them
%   from a fresh Python run before deciding a divergence is real.

referenceCorr = dictionary( ...
    ["Academic Reputation", "Employer Reputation", "Employment Outcomes", ...
     "Sustainability Score", "International Research Network", ...
     "Citations per Faculty", "International Student Ratio", ...
     "International Faculty Ratio", "Faculty Student Ratio"], ...
    [0.899483, 0.800391, 0.613249, 0.618268, 0.494912, ...
     0.483992, 0.397889, 0.375336, 0.321830]);

referenceGap = dictionary( ...
    ["Sustainability Score", "Academic Reputation", "Citations per Faculty", ...
     "International Research Network", "Employer Reputation", ...
     "International Faculty Ratio", "Employment Outcomes", ...
     "International Student Ratio", "Faculty Student Ratio"], ...
    [1.7729, 1.6343, 1.4204, 1.2858, 1.5265, 1.0409, 1.0784, 0.9067, 0.5016]);

corrDelta = max(abs(correlationTable.pearson_r ...
    - reshape(referenceCorr(correlationTable.indicator), [], 1)));
gapDelta = max(abs(shift.standardised_gap ...
    - reshape(referenceGap(shift.indicator), [], 1)));
pcaDelta = max(abs(explained(1:2) - [47.5977; 13.4346]));
targetDelta = max(abs([mean(yLab); std(yLab)] - [46.967714; 18.673447]));

parity = table( ...
    ["correlation with target"; "covariate shift (Cohen's d)"; ...
     "PCA explained variance %"; "target mean / std"], ...
    [corrDelta; gapDelta; pcaDelta; targetDelta], ...
    VariableNames=["table", "max_abs_deviation_from_python"]);

fprintf("\n--- parity with ranking_ml.eda.run_eda ---\n");
disp(parity);
if max(parity.max_abs_deviation_from_python) > 1e-3
    warning("run_qs_eda:parityDrift", ...
        "MATLAB output has drifted from the Python EDA by more than 1e-3. " + ...
        "Do not trust the figures until this is explained.");
end
end


% =============================================================================
% figures
% =============================================================================

function fig = plot_correlation(labelledImputed, yLab, indicators, targetLabel, nLab)
frame = [labelledImputed, yLab];
labels = [indicators, targetLabel];
correlation = corr(frame);

fig = figure(Name="correlation_heatmap", Position=[100 100 900 750], Color="w");
ax = axes(fig);
imagesc(ax, correlation, [-1 1]);
colormap(ax, diverging_colormap());
axis(ax, "equal", "tight");

n = numel(labels);
set(ax, XTick=1:n, XTickLabel=labels, YTick=1:n, YTickLabel=labels, ...
    XTickLabelRotation=45, FontSize=8, TickLabelInterpreter="none");

for i = 1:n
    for j = 1:n
        value = correlation(i, j);
        if abs(value) > 0.55
            textColour = "w";
        else
            textColour = "k";
        end
        text(ax, j, i, sprintf("%.2f", value), HorizontalAlignment="center", ...
            VerticalAlignment="middle", FontSize=6.5, Color=textColour);
    end
end

title(ax, sprintf("QS indicator correlation, labelled rows only (n=%d)", nLab), ...
    FontSize=11, Interpreter="none");
bar = colorbar(ax);
bar.Label.String = "Pearson r";
end


function fig = plot_target_distribution(yLab, targetLabel)
fig = figure(Name="target_distribution", Position=[100 100 750 450], Color="w");
ax = axes(fig);
histogram(ax, yLab, 40, FaceColor="#4c72b0", FaceAlpha=0.85, EdgeColor="w");
xlabel(ax, sprintf("%s (published, top of the table)", targetLabel), Interpreter="none");
ylabel(ax, "universities");
title(ax, sprintf("Target distribution: n=%d, mean=%.1f, std=%.1f, " + ...
    "right-skewed toward the top of the table", ...
    numel(yLab), mean(yLab), std(yLab)), FontSize=10, Interpreter="none");
grid(ax, "on");
ax.GridAlpha = 0.15;
ax.XGrid = "off";
end


function fig = plot_pca(score, explained, ranks, labelled)
fig = figure(Name="pca_scatter", Position=[100 100 850 650], Color="w");
ax = axes(fig);
hold(ax, "on");

scatter(ax, score(~labelled, 1), score(~labelled, 2), 9, ...
    MarkerFaceColor="#b0b7c3", MarkerEdgeColor="none", MarkerFaceAlpha=0.45, ...
    DisplayName=sprintf("rank %d-%d, score withheld (n=%d)", ...
        min(ranks(~labelled)), max(ranks(~labelled)), sum(~labelled)));
scatter(ax, score(labelled, 1), score(labelled, 2), 14, ranks(labelled), "filled", ...
    MarkerFaceAlpha=0.85, ...
    DisplayName=sprintf("rank %d-%d, score published (n=%d)", ...
        min(ranks(labelled)), max(ranks(labelled)), sum(labelled)));

% MATLAB ships no viridis; parula is the closest perceptually-uniform default.
colormap(ax, parula);
bar = colorbar(ax);
bar.Label.String = "published QS rank";

xlabel(ax, sprintf("PC1 (%.1f%% variance)", explained(1)));
ylabel(ax, sprintf("PC2 (%.1f%% variance)", explained(2)));
title(ax, "QS universities in indicator space: training set vs inference set", ...
    FontSize=11);
legend(ax, Location="best", FontSize=8);
grid(ax, "on");
ax.GridAlpha = 0.15;
hold(ax, "off");
end


function map = diverging_colormap()
%DIVERGING_COLORMAP Blue-white-red, standing in for matplotlib's RdBu_r.
low  = [0.129 0.400 0.674];
mid  = [0.969 0.969 0.969];
high = [0.698 0.094 0.168];
half = 128;
t = linspace(0, 1, half)';
map = [low + t .* (mid - low); mid + t .* (high - mid)];
end


function path = save_figure(fig, outDir, filename)
path = string(fullfile(outDir, filename));
exportgraphics(fig, path, Resolution=150);
end
