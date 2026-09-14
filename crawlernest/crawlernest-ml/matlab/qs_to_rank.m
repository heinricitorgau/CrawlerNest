function value = qs_to_rank(raw)
%QS_TO_RANK Parse a published QS rank. Ranges such as "901-950" take their midpoint.
%
%   Mirrors ranking_ml.features.build_features._to_rank. The 2026 snapshot
%   carries plain integer positions on all 1,504 rows (the published label,
%   e.g. "=17" or "1401+", sits in rank_display, which is not read), but earlier and future
%   crawls carry banded ranks ("901-950") and tie markers ("=12"), so the
%   parsing rules are kept identical to the Python side rather than simplified.

value = NaN;

if isempty(raw)
    return
end

if isnumeric(raw)
    value = double(raw(1));
    return
end

text = strtrim(string(raw));
text = replace(text, ",", "");
text = regexprep(text, '^[=+]+', '');
if strlength(text) == 0
    return
end

separators = ["-", char(8211), "~"];   % hyphen, en dash, tilde
for k = 1:numel(separators)
    sep = string(separators(k));
    if contains(text, sep)
        parts = strtrim(split(text, sep));
        parts = parts(strlength(parts) > 0);
        if numel(parts) == 2 && all(~cellfun(@isempty, ...
                regexp(cellstr(parts), '^\d+(\.\d+)?$', 'once')))
            value = (str2double(parts(1)) + str2double(parts(2))) / 2;
        end
        return
    end
end

if ~isempty(regexp(text, '^\d+(\.\d+)?$', 'once'))
    value = str2double(text);
end
end
