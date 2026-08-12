%% NOx "to air" (EDGAR) extraction from GLORIA 60 -- CORRECTED
% Verified against GLORIA_ReadMe_060.xlsx, sheet 'Satellites':
%   col 1 = Lfd_Nr | col 2 = Sat_head_indicator | col 3 = Sat_indicator | col 4 = Sat_unit
%   6130 data rows; Lfd_Nr == row position (1..6130).
%
% KEY FACT: every nox_* label appears TWICE in the sheet -- once under head
% 'Emissions (EDGAR)' and once under 'NOx to air (EDGAR)'. So matching the
% label ALONE is wrong (it can grab the 'Emissions' duplicate). The head
% filter is REQUIRED. The exact head string below was verified in the file.
clc; clear;

%% ---- Paths
%wd.mrio_pa = 'D:\GLORIA_MRIOS_60\';
wd.mrio_pa = 'C:\Users\etber\OneDrive\Nitrogen_Paper\SI_1\0_External_data\7_data_GLORIA\';
wd.hd_pa   = 'C:\Users\etber\OneDrive\Nitrogen_Paper\SI_1\0_External_data\7_data_GLORIA\';
outDir   = fullfile(wd.hd_pa, 'NOx');
if ~exist(outDir, 'dir'), mkdir(outDir); end

HEAD = 'Emissions (EDGAR)';   % satellite head indicator (col 2 of 'Satellites')

%% ---- Read & clean the index sheet
raw = readcell(fullfile(wd.hd_pa, 'GLORIA_ReadMe_060.xlsx'), 'Sheet', 'Satellites');
raw = raw(2:end, :);                                   % drop header row
% The cells carry literal single-quotes (e.g. 'NOx to air (EDGAR)'); strip + trim them.
% Using string arrays so any empty/missing cell stays <missing> instead of crashing.
head_index = strtrim(erase(string(raw(:,2)), "'"));    % e.g. "NOx to air (EDGAR)"
lab_index  = strtrim(erase(string(raw(:,3)), "'"));    % e.g. "nox_1A3c_EDGAR_consistent"
nRowsIndex = numel(lab_index);                         % expected: 6130

%% ---- Master NOx list
allNOx = { ...
    'nox_1A1a_EDGAR_consistent'; ...
    'nox_1A1b_EDGAR_consistent'; 'nox_1A1ci_EDGAR_consistent'; 'nox_1A1cii_EDGAR_consistent'; 'nox_1B1_EDGAR_consistent'; 'nox_1B2_EDGAR_consistent'; ...
    'nox_1A2_EDGAR_consistent'; ...
    'nox_1A3a_EDGAR_consistent'; ...
    'nox_1A3b_noRES_EDGAR_consistent'; ...
    'nox_1A3c_EDGAR_consistent'; 'nox_1A3e_EDGAR_consistent'; ...
    'nox_1A3d_EDGAR_consistent'; ...
    'nox_1A4_EDGAR_consistent'; 'nox_1A5_EDGAR_consistent'; ...
    'nox_1B1_EDGAR_consistent'; 'nox_1B2_EDGAR_consistent'; 'nox_5B_EDGAR_consistent' ; ...
    'nox_2A1_EDGAR_consistent'; 'nox_2A2_EDGAR_consistent'; 'nox_2A3_EDGAR_consistent'; 'nox_2A4_EDGAR_consistent'; ...
    'nox_2B_EDGAR_consistent'; ...
    'nox_2C_EDGAR_consistent'; ...
    'nox_2H_EDGAR_consistent'; ...
    'nox_3A2_EDGAR_consistent'; ...
    'nox_3C1b_EDGAR_consistent'; ...
    'nox_3C2_EDGAR_consistent'; 'nox_3C3_EDGAR_consistent'; 'nox_3C4_EDGAR_consistent'; 'nox_3C7_EDGAR_consistent'; ...
    'nox_4C_EDGAR_consistent'};

%% ---- Groups (summed) and the rest (saved individually)
G1 = {'nox_1A1b_EDGAR_consistent', 'nox_1A1ci_EDGAR_consistent', 'nox_1A1cii_EDGAR_consistent', 'nox_1B1_EDGAR_consistent', 'nox_1B2_EDGAR_consistent'};
G2 = {'nox_1A3c_EDGAR_consistent', 'nox_1A3e_EDGAR_consistent'};
G3 = {'nox_1A4_EDGAR_consistent', 'nox_1A5_EDGAR_consistent'}; 
G4 = {'nox_1B1_EDGAR_consistent', 'nox_1B2_EDGAR_consistent', 'nox_5B_EDGAR_consistent'};
G5 = {'nox_2A1_EDGAR_consistent', 'nox_2A2_EDGAR_consistent', 'nox_2A3_EDGAR_consistent', 'nox_2A4_EDGAR_consistent'};
G6 = {'nox_3C2_EDGAR_consistent', 'nox_3C3_EDGAR_consistent', 'nox_3C4_EDGAR_consistent', 'nox_3C7_EDGAR_consistent'};
grouped           = [G1, G2, G3, G4, G5, G6];
save_individually = setdiff(allNOx, grouped, 'stable');     % column cell of the remaining 14

mk_slug = @(s) regexprep(regexprep(s, '^nox_', ''), '_EDGAR_consistent$', '');

%% ---- Resolve row indices (NaN where not found, so a typo can't crash the run)
idxG1      = find_rows(G1,                head_index, lab_index, HEAD);
idxG2      = find_rows(G2,                head_index, lab_index, HEAD);
idxG3      = find_rows(G3,                head_index, lab_index, HEAD);
idxG4      = find_rows(G4,                head_index, lab_index, HEAD);
idxG5      = find_rows(G5,                head_index, lab_index, HEAD);
idxG6      = find_rows(G6,                head_index, lab_index, HEAD);
idxSingles = find_rows(save_individually, head_index, lab_index, HEAD);

report_missing(G1,                idxG1,      HEAD);
report_missing(G2,                idxG2,      HEAD);
report_missing(G3,                idxG3,      HEAD);
report_missing(G4,                idxG4,      HEAD);
report_missing(G5,                idxG5,      HEAD);
report_missing(G6,                idxG5,      HEAD);
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

    % ---- CRITICAL alignment guard: the find() row index is only valid if
    %      Q_T's rows line up 1:1 with the Satellites sheet.
    if size(Q_T,1) ~= nRowsIndex
        warning(['Row mismatch for %d: Q_T has %d rows but the index has %d. ', ...
                 'Row indices may point to the wrong series -- check the CSV.'], ...
                 year, size(Q_T,1), nRowsIndex);
    end

    % ---- Groups: sum member rows, write as a column vector
    write_group(Q_T, idxG1, fullfile(outDir, sprintf('GLORIA_%d_60_NOx_G1#1A1b_1A1c_1B1_1B2.csv',    year)));
    write_group(Q_T, idxG2, fullfile(outDir, sprintf('GLORIA_%d_60_NOx_G2#1A3c_1A3e.csv',            year)));
    write_group(Q_T, idxG3, fullfile(outDir, sprintf('GLORIA_%d_60_NOx_G3#1A4_1A5.csv',              year)));
    write_group(Q_T, idxG4, fullfile(outDir, sprintf('GLORIA_%d_60_NOx_G4#1B1_1B2_5B.csv',           year)));
    write_group(Q_T, idxG5, fullfile(outDir, sprintf('GLORIA_%d_60_NOx_G5#2A.csv',                   year)));
    write_group(Q_T, idxG6, fullfile(outDir, sprintf('GLORIA_%d_60_NOx_G6#3C.csv',                   year)));

    % ---- Individuals
    for k = 1:numel(save_individually)
        ix = idxSingles(k);
        if isnan(ix), continue; end
        outname = fullfile(outDir, sprintf('GLORIA_%d_60_NOx#%s.csv', year, mk_slug(save_individually{k})));
        writematrix(Q_T(ix, :).', outname);
    end

    fprintf('Done %d.\n', year);
end

%% ===================== local helper functions =====================
function idx = find_rows(names, head_index, lab_index, HEAD)
% Returns a numeric row index per name; NaN if not found.
% Matches on BOTH head and label (label alone is ambiguous -- see header note).
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