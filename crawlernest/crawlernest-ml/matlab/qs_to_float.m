function value = qs_to_float(raw)
%QS_TO_FLOAT Parse a QS table cell to double, mapping "n/a" and junk to NaN.
%
%   Mirrors ranking_ml.features.build_features._to_float so the MATLAB port
%   produces the same matrix as the Python pipeline. Two rules matter:
%
%     * "n/a", empty, and anything that is not a plain decimal number -> NaN.
%     * Values outside the published 0-100 scale -> NaN, not trusted. A number
%       off that scale means the scraper picked up the wrong cell, and silently
%       analysing it would be worse than dropping it.

value = NaN;

if isempty(raw)
    return
end

if islogical(raw)
    return
end

if isnumeric(raw)
    value = double(raw(1));
else
    text = strtrim(string(raw));
    if strlength(text) == 0 || lower(text) == "n/a"
        return
    end
    text = replace(text, ",", "");
    if isempty(regexp(text, '^\d+(\.\d+)?$', 'once'))
        return
    end
    value = str2double(text);
end

if ~(value >= 0 && value <= 100)
    value = NaN;
end
end
