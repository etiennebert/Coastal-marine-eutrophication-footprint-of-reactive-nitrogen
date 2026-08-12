%% NH3 "to air" (EDGAR) extraction from GLORIA 060 -- CORRECTED
% Index read from GLORIA_ReadMe_060.xlsx, sheet 'Satellites':
%   col 1 = Lfd_Nr | col 2 = Sat_head_indicator | col 3 = Sat_indicator | col 4 = Sat_unit
%   Row count (nRowsIndex) is read from that file, so it adapts if 060 differs from 059a.
%
% NOTE: each nh3_* label appears twice -- once under head 'Emissions (EDGAR)'
% and once under 'NH3 to air (EDGAR)'. The head filter is REQUIRED so we take
% the "to air" copy, not the Emissions one.
clc; clear;

%% ---- Paths
%wd.mrio_pa = 'D:\GLORIA_MRIOS_60\';
wd.mrio_pa = 'C:\Users\etber\OneDrive\Nitrogen_Paper\SI_1\0_External_data\7_data_GLORIA\';
wd.hd_pa   = 'C:\Users\etber\OneDrive\Nitrogen_Paper\SI_1\0_External_data\7_data_GLORIA\';
outDir     = fullfile(wd.hd_pa, 'NH3');
if ~exist(outDir, 'dir'), mkdir(outDir); end

HEAD = 'NH3 to air (EDGAR)';   % satellite head indicator (col 2 of 'Satellites')

%% ---- Read & clean the index sheet
raw = readcell(fullfile(wd.mrio_pa, 'GLORIA_ReadMe_060.xlsx'), 'Sheet', 'Satellites');
raw = raw(2:end, :);                                   % drop header row
head_index = strtrim(erase(string(raw(:,2)), "'"));    % e.g. "NH3 to air (EDGAR)"
lab_index  = strtrim(erase(string(raw(:,3)), "'"));    % e.g. "nh3_1A3c_EDGAR_consistent"
nRowsIndex = numel(lab_index);

%% ---- Master NH3 list  (nh3_1A1bc is intentionally excluded)
allNH3 = { ...
    'nh3_1A1a_EDGAR_consistent'; 'nh3_1A1b_EDGAR_consistent'; 'nh3_1A1ci_EDGAR_consistent'; ...
    'nh3_1A1cii_EDGAR_consistent'; 'nh3_1B1_EDGAR_consistent'; 'nh3_1B2_EDGAR_consistent'; ...
    'nh3_1A2_EDGAR_consistent'; 'nh3_1A3a_EDGAR_consistent'; 'nh3_1A3b_noRES_EDGAR_consistent'; ...
    'nh3_1A3c_EDGAR_consistent'; 'nh3_1A3d_EDGAR_consistent'; 'nh3_1A3e_EDGAR_consistent'; ...
    'nh3_1A4_EDGAR_consistent'; 'nh3_1A5_EDGAR_consistent'; 'nh3_2A1_EDGAR_consistent'; ...
    'nh3_2A2_EDGAR_consistent'; 'nh3_2A3_EDGAR_consistent'; 'nh3_2A4_EDGAR_consistent'; ...
    'nh3_2B_EDGAR_consistent'; ...
    'nh3_2D_EDGAR_consistent'; 'nh3_2E_EDGAR_consistent'; 'nh3_2F_EDGAR_consistent'; 'nh3_2G_EDGAR_consistent'; ...
    'nh3_3A2_EDGAR_consistent'; ...
    'nh3_3C1_EDGAR_consistent'; ...
    'nh3_3C2_EDGAR_consistent'; 'nh3_3C3_EDGAR_consistent'; 'nh3_3C4_EDGAR_consistent'; 'nh3_3C7_EDGAR_consistent'; ...
    'nh3_4A_EDGAR_consistent'; 'nh3_4B_EDGAR_consistent'; ...
    'nh3_4C_EDGAR_consistent'; 'nh3_4D_EDGAR_consistent' };

%% ---- Groups (summed) and the rest (saved individually)
G1 = {'nh3_1A3c_EDGAR_consistent','nh3_1A3e_EDGAR_consistent'};
G2 = {'nh3_1A4_EDGAR_consistent','nh3_1A5_EDGAR_consistent'};
G3 = {'nh3_1A1b_EDGAR_consistent','nh3_1A1ci_EDGAR_consistent','nh3_1A1cii_EDGAR_consistent', ...
      'nh3_1B1_EDGAR_consistent','nh3_1B2_EDGAR_consistent'};
G4 = {'nh3_2A1_EDGAR_consistent','nh3_2A2_EDGAR_consistent','nh3_2A3_EDGAR_consistent', ...
      'nh3_2A4_EDGAR_consistent'};
G5 = {'nh3_2D_EDGAR_consistent', 'nh3_2E_EDGAR_consistent', 'nh3_2F_EDGAR_consistent', 'nh3_2G_EDGAR_consistent'};
G6 = {'nh3_3C2_EDGAR_consistent', 'nh3_3C3_EDGAR_consistent', 'nh3_3C4_EDGAR_consistent', 'nh3_3C7_EDGAR_consistent'};
G7 = {'nh3_4A_EDGAR_consistent', 'nh3_4B_EDGAR_consistent'};

grouped           = [G1, G2, G3, G4, G5, G6, G7];
save_individually = setdiff(allNH3, grouped, 'stable');     % the remaining 13

mk_slug = @(s) regexprep(regexprep(s, '^nh3_', ''), '_EDGAR_consistent$', '');

%% ---- Resolve row indices (NaN where not found, so a typo can't crash the run)
idxG1      = find_rows(G1,                head_index, lab_index, HEAD);
idxG2      = find_rows(G2,                head_index, lab_index, HEAD);
idxG3      = find_rows(G3,                head_index, lab_index, HEAD);
idxG4      = find_rows(G4,                head_index, lab_index, HEAD);
idxG5      = find_rows(G5,                head_index, lab_index, HEAD);
idxG6      = find_rows(G6,                head_index, lab_index, HEAD);
idxG7      = find_rows(G7,                head_index, lab_index, HEAD);
idxSingles = find_rows(save_individually, head_index, lab_index, HEAD);

report_missing(G1,                idxG1,      HEAD);
report_missing(G2,                idxG2,      HEAD);
report_missing(G3,                idxG3,      HEAD);
report_missing(G4,                idxG4,      HEAD);
report_missing(G5,                idxG5,      HEAD);
report_missing(G6,                idxG6,      HEAD);
report_missing(G7,                idxG7,      HEAD);
report_missing(save_individually, idxSingles, HEAD);

%% ---- Loop over years
for year = 2015:2022
    % Build folder and filename SEPARATELY, one %d each, and join with fullfile
    % (fullfile inserts the '\' without escape-processing it like sprintf would).
    subdir = sprintf('GLORIA_SatelliteAccounts_060_%d', year);
    fname  = sprintf('20240417_120secMother_AllCountries_002_TQ-Results_%d_060_Markup001(full).csv', year);
    file_path = fullfile(wd.mrio_pa, subdir, fname);

    if ~isfile(file_path)
        fprintf(2, 'WARNING: file not found, skipping %d:\n  %s\n', year, file_path);
        continue;
    end
    Q_T = readmatrix(file_path);                 % row i must be satellite indicator i (Lfd_Nr i)

    if size(Q_T,1) ~= nRowsIndex                 % CRITICAL alignment guard
        warning(['Row mismatch for %d: Q_T has %d rows but the index has %d. ', ...
                 'Row indices may point to the wrong series -- check the CSV.'], ...
                 year, size(Q_T,1), nRowsIndex);
    end

    % ---- Groups: sum member rows, write as a column vector
    write_group(Q_T, idxG1, fullfile(outDir, sprintf('GLORIA_%d_60_NH3_G1#1A3c_1A3e.csv',                 year)));
    write_group(Q_T, idxG2, fullfile(outDir, sprintf('GLORIA_%d_60_NH3_G2#1A4_1A5.csv',                   year)));
    write_group(Q_T, idxG3, fullfile(outDir, sprintf('GLORIA_%d_60_NH3_G3#1A1b_1A1ci_1A1cii_1B1_1B2.csv', year)));
    write_group(Q_T, idxG4, fullfile(outDir, sprintf('GLORIA_%d_60_NH3_G4#2A.csv',                        year)));
    write_group(Q_T, idxG5, fullfile(outDir, sprintf('GLORIA_%d_60_NH3_G5#2D_2E_2F_2G.csv',               year)));
    write_group(Q_T, idxG6, fullfile(outDir, sprintf('GLORIA_%d_60_NH3_G6#3C2_3C3_3C4_3C7.csv',           year)));
    write_group(Q_T, idxG7, fullfile(outDir, sprintf('GLORIA_%d_60_NH3_G7#4A_4B.csv',                     year)));

    % ---- Individuals
    for k = 1:numel(save_individually)
        ix = idxSingles(k);
        if isnan(ix), continue; end
        outname = fullfile(outDir, sprintf('GLORIA_%d_60_NH3#%s.csv', year, mk_slug(save_individually{k})));
        writematrix(Q_T(ix, :).', outname);
    end

    fprintf('Done %d.\n', year);
end

%% ===================== local helper functions =====================
function idx = find_rows(names, head_index, lab_index, HEAD)
% Returns a numeric row index per name; NaN if not found. Matches head + label.
    idx = nan(1, numel(names));
    for i = 1:numel(names)
        hit = find(strcmp(head_index, HEAD) & strcmp(lab_index, names{i}), 1, 'first');
        if ~isempty(hit), idx(i) = hit; end
    end
end

function report_missing(names, idx, HEAD)
    for i = 1:numel(names)
        if isnan(idx(i))
            fprintf(2, 'WARNING: "%s" not found under %s.\n', names{i}, HEAD);
        end
    end
end

function write_group(Q_T, idx, outfile)
    idx = idx(~isnan(idx));        % drop any missing members
    if isempty(idx), return; end
    writematrix(sum(Q_T(idx, :), 1).', outfile);
end