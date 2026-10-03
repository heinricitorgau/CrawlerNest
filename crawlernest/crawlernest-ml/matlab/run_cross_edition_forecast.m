function results = run_cross_edition_forecast(options)
%RUN_CROSS_EDITION_FORECAST Can the next edition's rank be predicted better than "no change"?
%
%   results = run_cross_edition_forecast()
%   results = run_cross_edition_forecast(SaveOutput=false, Boot=200)
%
%   For every university a source ranks in two consecutive editions, predict the
%   rank it prints in the later one from what was known in the earlier one:
%   its own band, the edition before, and what the other two sources printed.
%   Models are fitted only on editions that precede the one being predicted
%   (an expanding window), so each test year is genuinely out of time.
%
%   ## The question, and what would count as an answer
%
%   The baseline is persistence: predict the geometric midpoint of the band the
%   source printed last time (persist_mid). A model is only interesting if it beats that
%   out of time, by more than resampling the universities would produce. The
%   paired bootstrap interval on the difference in error says whether it does;
%   a point estimate alone does not. The bootstrap resamples universities, not rows:
%   a university appears once in each test year, so in the pooled rows its errors
%   are correlated, and resampling rows would make the interval too narrow. If neither learned model beats persistence,
%   that is the result, not a failure of the experiment.
%
%   ## Two controls, because "beats persistence" is a weak claim
%
%   persist_drift is persistence shifted by the mean movement of the training pairs. Lists
%   grow and bands renumber, so the whole table drifts down a little each edition; a model
%   that only learned that has learned nothing about universities. linear_own is the same
%   regression restricted to the university's own band at T, with no earlier edition and no
%   other source. A model has to beat persist_drift to say anything beyond drift, and
%   linear has to beat linear_own to say that other editions or other sources carry
%   information.
%
%   ## How a prediction is scored
%
%   A source prints an interval, so a prediction is scored against the interval:
%   the error is the distance, in log10 rank, from the prediction to the printed
%   band, and zero if it falls inside. HitRate is the share with zero error. An
%   open-ended band ("1401+") is hit by any prediction at or beyond its lower
%   bound, which flatters every method equally on those rows. Errors are in log
%   rank because a rank error is multiplicative: 20 places is large at 40 and
%   nothing at 800.
%
%   ## Three strata
%
%   "all", "exact_at_t" (the university had an exact rank at T, i.e. in the top
%   ranks where bands are width zero) and "banded_at_t". They behave differently
%   and averaging them hides it.
%
%   ## What this does not show
%
%   - Only universities ranked in both editions are in it, so it says nothing
%     about who enters or leaves a list, and the lists grow.
%   - QS has no 2015, 2017 or 2021, so its pairs are 2018-19, 2019-20 and 2022-26.
%   - The hyperparameters were fixed before looking at any test year and not tuned.
%   - A university the warehouse still holds on the wrong canonical is one series
%     here, as it is in the export.
%   - Predicting a rank is not explaining one. Nothing here is causal.
%
%   ## Output
%
%   <crawlernest-ml>/artifacts/cross_edition_matlab/
%       forecast_metrics.csv    one row per source, test year, model and stratum
%       forecast_splits.csv     training and test sizes per source and test year
%       forecast_drift.csv      how far the printed band moved, per source and edition
%       forecast_run.json       seed, hyperparameters, data hash
%       forecast_error_by_year.png

arguments
    options.Csv (1,1) string = ""
    options.OutDir (1,1) string = ""
    options.SaveOutput (1,1) logical = true
    options.Seed (1,1) double = 20261003
    options.Boot (1,1) double = 2000
    options.TestFrom (1,1) double = 2020
    options.MinTrain (1,1) double = 200
end

R = load_cross_edition_ranks(Csv=options.Csv);
P = build_forecast_pairs(R.table);
sources = ["QS", "THE", "ARWU"];
models = ["persist_mid", "persist_lo", "persist_drift", "linear_own", "linear", "gbt"];
strata = ["all", "exact_at_t", "banded_at_t"];

OWN_COLUMNS = 1:3;   % feature_matrix: own lower bound, own midpoint, open-ended flag
hyper = struct("NumLearningCycles", 150, "LearnRate", 0.05, "MaxNumSplits", 6, "MinLeafSize", 20);
rng(options.Seed, "twister");

rows = table();
splits = table();
pooled = struct();   % source_model -> vectors, for the pooled rows

for src = sources
    Ps = P(P.source == src, :);
    testYears = sort(unique(Ps.yearTarget(Ps.yearTarget >= options.TestFrom)))';
    for Y = testYears
        trainMask = Ps.yearTarget < Y;
        testMask = Ps.yearTarget == Y;
        Ptr = Ps(trainMask, :);
        Pte = Ps(testMask, :);
        assert(all(Ptr.yearTarget < Y) && all(Pte.yearTarget == Y), "train and test must not overlap in time");
        assert(all(Ptr.yearT < Y), "a training row may not use an edition at or after the test year");
        if height(Ptr) < options.MinTrain || height(Pte) == 0
            continue
        end
        splits = [splits; table(src, Y, height(Ptr), height(Pte), ...
            'VariableNames', {'source', 'testYear', 'nTrain', 'nTest'})]; %#ok<AGROW>

        pred = struct();
        pred.persist_mid = log10(Pte.ownMid);
        pred.persist_lo = log10(Pte.ownLo);
        drift = mean(log10(Ptr.tgtMid) - log10(Ptr.ownMid));
        pred.persist_drift = log10(Pte.ownMid) + drift;
        Xtr = feature_matrix(Ptr);
        Xte = feature_matrix(Pte);
        ytr = log10(Ptr.tgtMid);

        pred.linear = ols_fit_predict(Xtr, ytr, Xte);
        pred.linear_own = ols_fit_predict(Xtr(:, OWN_COLUMNS), ytr, Xte(:, OWN_COLUMNS));

        tree = templateTree(MaxNumSplits=hyper.MaxNumSplits, MinLeafSize=hyper.MinLeafSize);
        gbt = fitrensemble(Xtr, ytr, Method="LSBoost", NumLearningCycles=hyper.NumLearningCycles, ...
            LearnRate=hyper.LearnRate, Learners=tree);
        pred.gbt = predict(gbt, Xte);

        exactMask = ~Pte.ownOpen & Pte.ownLo == Pte.ownHi;
        masks = struct("all", true(height(Pte), 1), "exact_at_t", exactMask, "banded_at_t", ~exactMask);

        err = struct();
        for m = models
            err.(m) = interval_error(pred.(m), Pte.tgtLo, Pte.tgtHi);
        end
        for m = models
            for st = strata
                k = masks.(st);
                if ~any(k)
                    continue
                end
                [d, lo, hi] = paired_difference(err.persist_mid(k), err.(m)(k), Pte.uid(k), options.Boot, m == "persist_mid");
                [dd, dlo, dhi] = paired_difference(err.persist_drift(k), err.(m)(k), Pte.uid(k), options.Boot, m == "persist_drift");
                rows = [rows; metric_row(src, string(Y), m, st, err.(m)(k), pred.(m)(k), ...
                    Pte.tgtMid(k), [d lo hi], [dd dlo dhi])]; %#ok<AGROW>
            end
            % kept for the pooled rows below
            key = src + "_" + m;
            if ~isfield(pooled, key)
                pooled.(key) = struct("err", [], "pred", [], "mid", [], "base", [], "drift", [], "exact", [], "uid", []);
            end
            pooled.(key).err = [pooled.(key).err; err.(m)];
            pooled.(key).pred = [pooled.(key).pred; pred.(m)];
            pooled.(key).mid = [pooled.(key).mid; Pte.tgtMid];
            pooled.(key).base = [pooled.(key).base; err.persist_mid];
            pooled.(key).drift = [pooled.(key).drift; err.persist_drift];
            pooled.(key).exact = [pooled.(key).exact; exactMask];
            pooled.(key).uid = [pooled.(key).uid; Pte.uid];
        end
    end

    for m = models
        key = src + "_" + m;
        if ~isfield(pooled, key)
            continue
        end
        pk = pooled.(key);
        pooledExact = logical(pk.exact);   % [] (double) concatenated with a logical is a double
        pmasks = struct("all", true(numel(pk.err), 1), "exact_at_t", pooledExact, "banded_at_t", ~pooledExact);
        for st = strata
            k = pmasks.(st);
            if ~any(k)
                continue
            end
            [d, lo, hi] = paired_difference(pk.base(k), pk.err(k), pk.uid(k), options.Boot, m == "persist_mid");
            [dd, dlo, dhi] = paired_difference(pk.drift(k), pk.err(k), pk.uid(k), options.Boot, m == "persist_drift");
            rows = [rows; metric_row(src, "pooled", m, st, pk.err(k), pk.pred(k), pk.mid(k), [d lo hi], [dd dlo dhi])]; %#ok<AGROW>
        end
    end
end

results = struct("metrics", rows, "splits", splits, "pairs", P, "hyper", hyper, ...
    "seed", options.Seed, "sha256", R.sha256);

print_summary(rows, splits);

if options.SaveOutput
    outDir = options.OutDir;
    if outDir == ""
        outDir = string(fullfile(fileparts(fileparts(mfilename("fullpath"))), "artifacts", "cross_edition_matlab"));
    end
    if ~isfolder(outDir)
        mkdir(outDir);
    end
    writetable(rows, fullfile(outDir, "forecast_metrics.csv"));
    writetable(splits, fullfile(outDir, "forecast_splits.csv"));
    writetable(drift_table(P, options.TestFrom), fullfile(outDir, "forecast_drift.csv"));
    info = struct("matlab", version, "seed", options.Seed, "bootstrap_resamples", options.Boot, ...
        "test_from", options.TestFrom, "min_train", options.MinTrain, "hyperparameters", hyper, ...
        "data_sha256", R.sha256, "pairs_per_source", count_pairs(P, sources), ...
        "open_ended_midpoint_factor", 1.25);
    fid = fopen(fullfile(outDir, "forecast_run.json"), "w");
    fwrite(fid, jsonencode(info, PrettyPrint=true));
    fclose(fid);
    plot_forecast(rows, fullfile(outDir, "forecast_error_by_year.png"));
    fprintf("wrote %s\n", outDir);
end
end

function X = feature_matrix(P)
%FEATURE_MATRIX Log-rank features known at edition T, missing values imputed and flagged.
lOwnLo = log10(P.ownLo);
lOwnMid = log10(P.ownMid);
hasPrev = isfinite(P.prevLo);
lPrev = lOwnLo;
lPrev(hasPrev) = log10(P.prevLo(hasPrev));
has1 = isfinite(P.other1Lo);
l1 = lOwnMid;
l1(has1) = log10(P.other1Lo(has1));
has2 = isfinite(P.other2Lo);
l2 = lOwnMid;
l2(has2) = log10(P.other2Lo(has2));
X = [lOwnLo, lOwnMid, double(P.ownOpen), lPrev, double(hasPrev), l1, double(has1), l2, double(has2)];
end

function yhat = ols_fit_predict(Xtr, ytr, Xte)
%OLS_FIT_PREDICT Ordinary least squares with an intercept, dropping columns the training data cannot identify.
%   A column is kept only if it adds something to the intercept and the columns kept before it. Some
%   columns are constant or collinear in a small training window -- for QS in 2020, no training pair has an
%   earlier edition, so the imputed "previous rank" column equals the own-rank column exactly -- and which
%   of two collinear columns a library drops is its own choice, so the rule is stated here and in the
%   Python check rather than left to fitlm, whose pivoting is not documented to be stable across releases.
n = size(Xtr, 1);
basis = ones(n, 1) / sqrt(n);
keep = false(1, size(Xtr, 2));
for j = 1:size(Xtr, 2)
    v = Xtr(:, j);
    r = v - basis * (basis' * v);
    if norm(r) > 1e-9 * max(1, norm(v))
        keep(j) = true;
        basis = [basis, r / norm(r)]; %#ok<AGROW>
    end
end
beta = [ones(n, 1), Xtr(:, keep)] \ ytr;
yhat = [ones(size(Xte, 1), 1), Xte(:, keep)] * beta;
end

function e = interval_error(p, tgtLo, tgtHi)
%INTERVAL_ERROR Distance in log10 rank from p to the printed band; zero inside it.
lo = log10(tgtLo);
hi = log10(tgtHi);
hi(isnan(hi)) = inf;
e = max(0, max(lo - p, p - hi));
end

function [d, lo, hi] = paired_difference(baseErr, modelErr, uid, B, isBaseline)
%PAIRED_DIFFERENCE Mean of baseErr - modelErr (positive: better than the baseline), bootstrapped over universities.
diffs = baseErr - modelErr;
d = mean(diffs);
if isBaseline || numel(diffs) < 2
    lo = NaN;
    hi = NaN;
    return
end
[~, ~, g] = unique(uid);
clusterSum = accumarray(g, diffs);
clusterN = accumarray(g, 1);
nc = numel(clusterSum);
draw = randi(nc, nc, B);
means = sort(sum(clusterSum(draw), 1) ./ sum(clusterN(draw), 1));
lo = means(max(1, floor(0.025 * B)));
hi = means(min(B, ceil(0.975 * B)));
end

function r = metric_row(src, test, model, stratum, err, pred, tgtMid, vsMid, vsDrift)
r = table(src, test, model, stratum, numel(err), mean(err), mean(err < 1e-12), ...
    mean(abs(pred - log10(tgtMid))), vsMid(1), vsMid(2), vsMid(3), vsDrift(1), vsDrift(2), vsDrift(3), ...
    'VariableNames', {'source', 'test', 'model', 'stratum', 'n', 'meanIntervalErr', 'hitRate', ...
    'meanAbsLogErrMid', 'diffVsPersistMid', 'ciLo', 'ciHi', 'diffVsDrift', 'driftCiLo', 'driftCiHi'});
end

function D = drift_table(P, testFrom)
%DRIFT_TABLE How far the printed band moved between editions, per source and target edition.
%   drift = log10(target midpoint / own midpoint). A list that grows pushes the bottom of the
%   table further down, so a positive median is the list, not the universities.
keys = unique(P(P.yearTarget >= testFrom, {'source', 'yearTarget'}), "rows");
D = table();
for i = 1:height(keys)
    k = P.source == keys.source(i) & P.yearTarget == keys.yearTarget(i);
    drift = log10(P.tgtMid(k) ./ P.ownMid(k));
    D = [D; table(keys.source(i), keys.yearTarget(i), sum(k), median(drift), mean(drift), ...
        mean(P.tgtOpen(k)), mean(P.ownOpen(k)), ...
        'VariableNames', {'source', 'yearTarget', 'n', 'medianDrift', 'meanDrift', ...
        'shareTargetOpenEnded', 'shareOwnOpenEnded'})]; %#ok<AGROW>
end
end

function c = count_pairs(P, sources)
c = struct();
for s = sources
    c.(s) = sum(P.source == s);
end
end

function print_summary(rows, splits)
fprintf("\n--- pairs per test year ---\n");
disp(splits);
pooledAll = rows(rows.test == "pooled" & rows.stratum == "all", :);
fprintf("--- pooled over test years, all strata (diff > 0: better than the baseline named) ---\n");
disp(pooledAll(:, {'source', 'model', 'n', 'meanIntervalErr', 'hitRate', 'diffVsPersistMid', 'ciLo', 'ciHi', ...
    'diffVsDrift', 'driftCiLo', 'driftCiHi'}));
end

function plot_forecast(rows, path)
f = figure(Visible="off", Position=[100 100 1400 700]);
sources = ["QS", "THE", "ARWU"];
models = ["persist_mid", "persist_drift", "linear_own", "linear", "gbt"];
colours = lines(numel(models));
t = tiledlayout(f, 2, 3, TileSpacing="compact");
title(t, "Next-edition rank forecast, expanding window (all strata)");
for i = 1:numel(sources)
    sub = rows(rows.source == sources(i) & rows.stratum == "all" & rows.test ~= "pooled", :);
    years = unique(double(sub.test))';
    ax = nexttile(t, i);
    hold(ax, "on");
    for j = 1:numel(models)
        s = sub(sub.model == models(j), :);
        [~, ord] = sort(double(s.test));
        plot(ax, double(s.test(ord)), s.meanIntervalErr(ord), "-o", Color=colours(j, :), DisplayName=models(j));
    end
    title(ax, sources(i));
    xlabel(ax, "test edition");
    ylabel(ax, "mean interval error (log10 rank)");
    xticks(ax, years);
    grid(ax, "on");
    if i == 1
        lgd = legend(ax, Interpreter="none", Orientation="horizontal");
        lgd.Layout.Tile = "south";
    end
    ax2 = nexttile(t, 3 + i);
    hold(ax2, "on");
    for j = 3:5
        s = sub(sub.model == models(j), :);
        [~, ord] = sort(double(s.test));
        x = double(s.test(ord));
        y = s.diffVsDrift(ord);
        errorbar(ax2, x + 0.08 * (j - 4), y, y - s.driftCiLo(ord), s.driftCiHi(ord) - y, "o", ...
            Color=colours(j, :), DisplayName=models(j));
    end
    yline(ax2, 0, "k-");
    xlabel(ax2, "test edition");
    ylabel(ax2, "error saved vs persist\_drift");
    xticks(ax2, years);
    grid(ax2, "on");
end
exportgraphics(f, path, Resolution=150);
close(f);
end
