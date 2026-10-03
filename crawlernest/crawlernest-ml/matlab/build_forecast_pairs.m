function P = build_forecast_pairs(T)
%BUILD_FORECAST_PAIRS One row per university and source that is ranked in two consecutive editions.
%
%   P = build_forecast_pairs(R.table)
%
%   A row is (university U, source S, edition T): everything known about U at T,
%   and what S printed for U at T+1. Only editions T and earlier feed the
%   features; the target is the following edition. Nothing from T+1 is in a
%   feature.
%
%   ## What a rank is
%
%   A source prints an interval ("201-210", "=196", "1401+"), not a number. The
%   features keep the lower bound, the geometric midpoint of the band, and
%   whether the band was open-ended, and the target is kept as an interval, so a
%   prediction is scored against what the source published rather than against a
%   precision it never claimed. The midpoint of an open-ended band is taken as
%   OPEN_FACTOR times its lower bound; that is a convention, stated here, not a
%   measurement.
%
%   ## What may be a feature: publication timing
%
%   "Edition T" does not mean the same moment for every source. QS edition T
%   appears in June of year T-1 (from 2018; earlier editions in September), THE
%   edition T in October of year T-1, ARWU edition T in August of year T. A feature
%   is information, and information published after the thing being predicted is not
%   a forecast input however it is labelled. For a QS target (edition T+1, June of
%   year T) ARWU edition T (August of year T) is therefore excluded: its column is NaN,
%   as if ARWU had not ranked the university. For THE and ARWU targets every other
%   source's edition T predates the target, and newer editions that would also have been
%   available are deliberately not used, which keeps the comparison conservative.
%   AVAILABLE below is that table.
%
%   ## Who is in it
%
%   Only universities ranked by the source in both editions. A university that
%   drops off the list, or enters it, has no pair, so this describes movement
%   among universities that stay listed. The lists also grow (ARWU 500 -> 1000
%   places, THE 401 -> 2,191, QS 889 -> 1,503 here) and entries arrive at the
%   bottom, which the persistence baseline cannot know.
%
%   ## Columns
%
%   source, yearT, yearTarget, uid
%   ownLo, ownHi (NaN if open-ended), ownMid, ownOpen
%   prevLo        the same source one edition earlier, NaN if not ranked
%   other1Lo, other2Lo, other1, other2   the other two sources at T, in the
%                 fixed order QS, THE, ARWU with S removed; NaN if not ranked
%   tgtLo, tgtHi (NaN if open-ended), tgtMid, tgtOpen

arguments
    T table
end

OPEN_FACTOR = 1.25;
sources = ["QS", "THE", "ARWU"];
% AVAILABLE(s, k): may source k's edition T be a feature for a source-s target at T+1?
AVAILABLE = logical([0 1 0; ...    % QS target:   THE yes, ARWU no (published after it)
                     1 0 1; ...    % THE target:  QS yes, ARWU yes
                     1 1 0]);      % ARWU target: QS yes, THE yes

[uids, ~, ui] = unique(T.canonical_university_id);
years = (min(T.year):max(T.year))';
nU = numel(uids);
nY = numel(years);
nS = numel(sources);
[~, si] = ismember(T.source, sources);
if any(si == 0)
    error("build_forecast_pairs:source", "Unknown source in the export.");
end
yi = T.year - years(1) + 1;

lo = nan(nU, nY, nS);
hi = nan(nU, nY, nS);
idx = sub2ind(size(lo), ui, yi, si);
lo(idx) = T.rank_lo;
hi(idx) = T.rank_hi;

blocks = cell(0, 1);
for s = 1:nS
    others = setdiff(1:nS, s, "stable");
    for t = 1:nY - 1
        here = isfinite(lo(:, t, s)) & isfinite(lo(:, t + 1, s));
        u = find(here);
        if isempty(u)
            continue
        end
        n = numel(u);
        ownLo = lo(u, t, s);
        ownHi = hi(u, t, s);
        tgtLo = lo(u, t + 1, s);
        tgtHi = hi(u, t + 1, s);
        if t > 1
            prevLo = lo(u, t - 1, s);
        else
            prevLo = nan(n, 1);
        end
        blk = table();
        blk.source = repmat(sources(s), n, 1);
        blk.yearT = repmat(years(t), n, 1);
        blk.yearTarget = repmat(years(t + 1), n, 1);
        blk.uid = uids(u);
        blk.ownLo = ownLo;
        blk.ownHi = ownHi;
        blk.ownOpen = isnan(ownHi);
        blk.ownMid = band_midpoint(ownLo, ownHi, OPEN_FACTOR);
        blk.prevLo = prevLo;
        blk.other1 = repmat(sources(others(1)), n, 1);
        blk.other2 = repmat(sources(others(2)), n, 1);
        blk.other1Lo = lo(u, t, others(1));
        blk.other2Lo = lo(u, t, others(2));
        if ~AVAILABLE(s, others(1))
            blk.other1Lo(:) = NaN;
        end
        if ~AVAILABLE(s, others(2))
            blk.other2Lo(:) = NaN;
        end
        blk.tgtLo = tgtLo;
        blk.tgtHi = tgtHi;
        blk.tgtOpen = isnan(tgtHi);
        blk.tgtMid = band_midpoint(tgtLo, tgtHi, OPEN_FACTOR);
        blocks{end + 1, 1} = blk; %#ok<AGROW>
    end
end
P = vertcat(blocks{:});

assert(all(P.yearTarget == P.yearT + 1), "pairs must be consecutive editions");
end

function m = band_midpoint(lo, hi, openFactor)
%BAND_MIDPOINT Geometric midpoint of [lo, hi]; open-ended bands use openFactor * lo.
m = sqrt(lo .* hi);
open = isnan(hi);
m(open) = lo(open) * openFactor;
end
