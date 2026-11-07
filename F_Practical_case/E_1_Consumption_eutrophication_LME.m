%% E_1_Consumption_eutrophication_LME.m
% -------------------------------------------------------------------------
% WHICH CONSUMPTION GENERATES WHICH MARINE EUTROPHICATION?
%
% Traces the eutrophication placed in each LME sub-segment (the Python-built
% GLORIA satellites, folder E) back to the FINAL DEMAND that ultimately caused
% it, with a Leontief demand-pull model - and, for the 7 coral-reef LME
% sub-segments of Niclas Pannier's thesis (Table 1), down to the individual
% product x supplying region x consuming region.
%
% METHOD (thesis eq.: B = q_hat * L ; footprint = B * Y)
%   S      305 x 39360   satellite: kg O2-eq placed by each (region x sector)
%                        industry column into each LME sub-segment row
%   x      39360 x 1     GLORIA gross output (kUSD)  ->  E = S ./ x'  (intensity)
%   x_cty  39360 x 164   L * Y_cty, production embodied in each region's demand
%   FP  = E * x_cty      305 x 164   eutrophication in LME r caused by the
%                        final consumption of region c  (THE headline matrix)
%   For a focus LME r:  B_r = E(r,:) * L   (1 x 39360, impact per kUSD of final
%   demand of each product);  D = B_r' .* Y_cty  (39360 x 164) resolves region
%   c's footprint on r into the exact final products bought and who supplies
%   them. Column-sums of D reproduce FP(r,:) - checked at run time.
%
% STYLE: LINEAR ON PURPOSE - no local functions; blocks guarded by RUN_*
%   switches; every intermediate (S, E, FP, B_r, D) stays in the workspace.
%
% INPUTS
%   <SI>\E_MRIO_GLORIA_Satellites\1. GLORIAv60_Eutrophication_Satellites\satellite_<flow>_<year>.mat
%        (+ satellite_column_labels.csv for region/sector names)  <- Python step [5]
%   <wd.hd>\matrix calc\{L,x,x_cty,Y_cty}_<year>.mat   <- A_1_GLORIA_prepALx_v3_1.m
%        run for GLORIA v60, years 2015-2022 (same files D_2 already uses)
%
% OUTPUTS (in '1. results\')
%   CBA\FP_<flow>_<year>.csv             305 LME-ss x 164 consuming regions (CBA)
%   CBA\FP_all_years_long.csv            tidy master: year,flow,LME_ss,consumer,kgO2
%   CBA\focus\<flow>_<year>_<LME>_consumption_top.csv   product-level CBA detail
%   PBA\<flow>_<year>_<LME>_production_full.csv   PBA = the satellite row itself:
%                                        every producing (region x sector) whose
%                                        emissions hit this LME (no L needed)
%   PBA\<flow>_<year>_<LME>_production_top20.csv  same, top 20 for quick reading
%   CBA_vs_PBA\<flow>_<year>_<LME>.csv   region-level PBA vs CBA side by side
%                                        (+ net_import = CBA - PBA) -> the
%                                        production-vs-consumption contrast figure
% Units: kg O2-eq per year; monetary flows in kUSD (GLORIA basic prices).
% Memory: needs L in RAM (~12 GB dense, as in D_2). Aggregate part alone
% (RUN_FOCUS=false) needs only x and x_cty - a laptop handles it.
% -------------------------------------------------------------------------

%% 0) switches + configuration
clc, clear

RUN_AGG    = true;      % write the 305 x 164 FP matrices + tidy master (CBA)
RUN_FOCUS  = true;      % product-level CBA detail for FOCUS_LME (needs L + Y_cty)
RUN_PBA    = true;      % PBA extraction + CBA-vs-PBA tables (satellite only, no L)

gloria_vrs = 60;
startYear  = 2015;
endYear    = 2022;
BATCH      = 'anchored';                        % 'original' (territorial) or 'anchored'
                                                % (GLORIA-anchored satellites from
                                                %  E/2_make_anchored_satellites.py)
GLORIA_ROOT = 'D:';                             % drive/folder holding GLORIA_MRIOS_<vrs>
flows      = {'Nleach', 'NH3', 'NOx'};          % satellite file names, folder E
TOPN       = 5000;                              % rows kept in each focus detail csv

% GLORIA 'matrix calc' location (same drive layout as D_2)
wd.hd    = fullfile(GLORIA_ROOT, ['GLORIA_MRIOS_' num2str(gloria_vrs)]);
wd.hd_ma = fullfile(wd.hd, 'matrix calc');

% this script lives in F_Practical_case -> satellites are one level up in E
here = fileparts(mfilename('fullpath'));
if isempty(here); here = pwd; end
switch BATCH
    case 'original'
        SAT_DIR = fullfile(here, '..', 'E_MRIO_GLORIA_Satellites', '1. GLORIAv60_Eutrophication_Satellites');
        OUT_DIR = fullfile(here, '1. results');           % CBA / PBA / CBA_vs_PBA live here
    case 'anchored'
        SAT_DIR = fullfile(here, '..', 'E_MRIO_GLORIA_Satellites', '1b. GLORIAv60_Eutrophication_Satellites_anchored');
        OUT_DIR = fullfile(here, '1. results_anchored');  % never overwrites the original batch
    otherwise
        error('BATCH must be original or anchored');
end
fprintf('E_1: batch %s, years %d-%d\n', BATCH, startYear, endYear);
CBA_DIR = fullfile(OUT_DIR, 'CBA');
PBA_DIR = fullfile(OUT_DIR, 'PBA');
CMP_DIR = fullfile(OUT_DIR, 'CBA_vs_PBA');
for d_ = {OUT_DIR, CBA_DIR, fullfile(CBA_DIR, 'focus'), PBA_DIR, CMP_DIR}
    if ~exist(d_{1}, 'dir'); mkdir(d_{1}); end
end

% the 7 coral-reef LME sub-segments (Pannier thesis, Table 1)
FOCUS_LME = { ...
    '12_1',  'Bocas del Toro (Caribbean Sea)'        ; ...
    '12_2',  'Crocker Reef (Caribbean Sea)'          ; ...
    '10',    'Kane''ohe Bay (Insular Pacific-Hawaiian)'; ...
    '40_4',  'Heron Island (NE Australian Shelf)'    ; ...
    '36_18', 'Dongsha (South China Sea)'             ; ...
    '49',    'Okinawa (Kuroshio Current)'            ; ...
    '36_13', 'Taiping (South China Sea)'             };

%% 1) labels - region codes and sector names, straight from the satellite folder
%    (no dependency on GLORIA_indices_v3.mat: the column-label file written by
%    the Python builder IS the sequential order the satellites use)
labfile = fullfile(SAT_DIR, 'satellite_column_labels.csv');
if ~exist(labfile, 'file')
    error(['%s not found.\nRun the Python step first: ' ...
           'E_MRIO_GLORIA_Satellites\\0_build_MRIO_satellites.py'], labfile);
end
labs = readtable(labfile);                       % col_index_1based, label, region, type
assert(height(labs) == 39360, 'expected 39,360 column labels');
reg_codes = unique(labs.region, 'stable');       % 164 region acronyms, GLORIA order
assert(numel(reg_codes) == 164, 'expected 164 GLORIA regions');
% 'France (FRA) Growing wheat industry' -> 'Growing wheat'
sec_name = regexprep(labs.label, '^.*?\([A-Za-z]{2,5}\)\s*', '');
sec_name = regexprep(sec_name, '\s+(industry|product)$', '');
[~, col_region_ix] = ismember(labs.region, reg_codes);   % column -> region 1..164 (for PBA sums)
% NOTE the consuming columns of Y_cty / x_cty follow this same 164-region
% GLORIA order (meta.con_y aggregates the 6 demand categories per region).


%% 2) year loop - load GLORIA matrices once per year, then run the three flows
for year = startYear:endYear
    fprintf('\n===== %d =====\n', year);

    % ---- GLORIA pieces from A_1 (clear error if 'not all the files are here')
    fx  = fullfile(wd.hd_ma, ['x_'     num2str(year) '.mat']);
    fxc = fullfile(wd.hd_ma, ['x_cty_' num2str(year) '.mat']);
    if ~exist(fx, 'file') || ~exist(fxc, 'file')
        warning(['%d: x / x_cty missing in %s -> year skipped.\n' ...
                 'Run A_1_GLORIA_prepALx_v3_1.m for GLORIA v%d, year %d ' ...
                 '(or point wd.hd to the right drive).'], year, wd.hd_ma, gloria_vrs, year);
        continue
    end
    tmp = load(fx,  'x');      x     = tmp.x;      % 39360 x 1, kUSD
    tmp = load(fxc, 'x_cty');  x_cty = tmp.x_cty;  % 39360 x 164 = L * Y_cty
    assert(numel(x) == 39360, 'x has %d elements (expected 39,360)', numel(x));
    x_div = x.'; x_div(x_div == 0) = 1;            % guard: 0-output sectors

    if RUN_FOCUS
        fL = fullfile(wd.hd_ma, ['L_'     num2str(year) '.mat']);
        fY = fullfile(wd.hd_ma, ['Y_cty_' num2str(year) '.mat']);
        if ~exist(fL, 'file') || ~exist(fY, 'file')
            warning('%d: L / Y_cty missing -> focus detail skipped this year.', year);
            haveL = false;
        else
            fprintf('  loading L (be patient, ~12 GB) ...\n'); tic
            clear L tmp                                % L needs ONE free ~12 GB block: drop any old copy first
            for attempt = 1:2                          % one retry: a 12 GB read from an external drive can hiccup
                try
                    tmp = load(fL, 'L');  L = tmp.L;  clear tmp
                    break
                catch err
                    clear tmp L
                    if attempt == 2
                        error(['%d: cannot read %s (%s).\nClose other programs, restart MATLAB and rerun ' ...
                               'with startYear = %d: finished years are kept, and the master table is ' ...
                               'rebuilt from all years at the end.'], year, fL, err.message, year);
                    end
                    warning('%d: reading L failed (%s) - retrying in 30 s', year, err.message);
                    pause(30);
                end
            end
            toc
            tmp = load(fY, 'Y_cty');  Y_cty = tmp.Y_cty;
            haveL = true;
        end
    else
        haveL = false;
    end

    % ---- flow loop
    for f = 1:numel(flows)
        flow = flows{f};
        satf = fullfile(SAT_DIR, ['satellite_' flow '_' num2str(year) '.mat']);
        if ~exist(satf, 'file')
            warning('%s not found -> skipped (rerun Python step [5]).', satf);
            continue
        end
        Sm = load(satf);                    % S (sparse 305 x 39360), LME_rows
        S  = Sm.S;
        if iscell(Sm.LME_rows)              % robust: cell array or char matrix
            rows_sat = string(Sm.LME_rows(:));
        else
            rows_sat = string(cellstr(Sm.LME_rows));
        end
        assert(size(S, 2) == 39360, 'satellite has %d columns', size(S, 2));

        % intensity and THE consumption matrix
        E  = S .* (1 ./ x_div);             % kg O2-eq per kUSD of gross output
        FP = full(E * x_cty);               % 305 LME-ss x 164 consuming regions

        % conservation: consumption view must redistribute the production view
        prod_tot = full(sum(S, 2));         % what the satellite places per LME
        cons_tot = sum(FP, 2);              % what consumption accounts for
        dev = max(abs(cons_tot - prod_tot) ./ max(prod_tot, 1));
        if dev < 1e-3, okmsg = 'OK'; else, okmsg = '<< CHECK (L accuracy / x mismatch)'; end
        fprintf('  %-6s : production %.4e | consumption %.4e kg O2 | max LME rel dev %.1e %s\n', ...
                flow, sum(prod_tot), sum(cons_tot), dev, okmsg);

        % ---- aggregate outputs
        if RUN_AGG
            T = [table(cellstr(rows_sat), 'VariableNames', {'LME_ss'}), ...
                 array2table(FP, 'VariableNames', reg_codes')];
            writetable(T, fullfile(CBA_DIR, sprintf('FP_%s_%d.csv', flow, year)));
        end

        % ---- PBA + CBA-vs-PBA per focus LME. The PBA is simply the satellite
        %      row of that LME (which producing region x sector emits what lands
        %      there) - no L, no Y_cty needed, so this runs even without RUN_FOCUS.
        if RUN_PBA
            for k = 1:size(FOCUS_LME, 1)
                lab = string(FOCUS_LME{k, 1});
                ridx = find(rows_sat == lab | rows_sat == lab + "_0" ...
                            | regexprep(rows_sat, '_0$', '') == lab, 1);
                if isempty(ridx)
                    warning('focus LME %s not found among satellite rows', lab); continue
                end
                if prod_tot(ridx) <= 0, continue, end   % nothing lands there for this flow

                % PBA full vector: every producing (region, sector) > 0, sorted
                p = full(S(ridx, :));
                nz = find(p > 0);
                [pv, ord] = sort(p(nz), 'descend');
                nz = nz(ord)';  pv = pv';
                Tf = table(labs.region(nz), sec_name(nz), pv, pv / prod_tot(ridx), ...
                           'VariableNames', {'producer_region', 'sector', 'kgO2', 'share_of_LME'});
                writetable(Tf, fullfile(PBA_DIR, ...
                    sprintf('%s_%d_%s_production_full.csv', flow, year, char(lab))));
                writetable(Tf(1:min(20, height(Tf)), :), fullfile(PBA_DIR, ...
                    sprintf('%s_%d_%s_production_top20.csv', flow, year, char(lab))));

                % CBA vs PBA at region level: who PRODUCES the impact in this LME
                % vs whose CONSUMPTION drives it. net_import > 0 = the region's
                % consumption causes more here than its own territory emits.
                pba_reg = accumarray(col_region_ix, p.', [164 1]);
                cba_reg = FP(ridx, :).';
                Tc = table(reg_codes, pba_reg, cba_reg, cba_reg - pba_reg, ...
                           pba_reg / max(prod_tot(ridx), eps), ...
                           cba_reg / max(cons_tot(ridx), eps), ...
                           'VariableNames', {'region', 'PBA_kgO2', 'CBA_kgO2', ...
                           'net_import_kgO2', 'PBA_share', 'CBA_share'});
                Tc = sortrows(Tc, 'CBA_kgO2', 'descend');
                writetable(Tc, fullfile(CMP_DIR, ...
                    sprintf('%s_%d_%s.csv', flow, year, char(lab))));
            end
        end

        % ---- CBA focus detail: down to the product and the supplying region
        if RUN_FOCUS && haveL
            for k = 1:size(FOCUS_LME, 1)
                lab = string(FOCUS_LME{k, 1});
                ridx = find(rows_sat == lab | rows_sat == lab + "_0" ...
                            | regexprep(rows_sat, '_0$', '') == lab, 1);
                if isempty(ridx) || prod_tot(ridx) <= 0, continue, end

                % B_r: impact on THIS LME per kUSD of final demand of each product
                B_r = full(E(ridx, :)) * L;             % 1 x 39360  (~1 s)
                D   = (B_r.') .* Y_cty;                 % 39360 x 164 product x consumer

                chk = abs(sum(D(:)) - cons_tot(ridx)) / max(cons_tot(ridx), 1);
                if chk > 1e-6
                    warning('%s %d LME %s: detail total deviates rel %.1e', flow, year, lab, chk);
                end

                % keep the TOPN largest (product, consumer) cells
                [v, ord] = maxk(D(:), TOPN);
                keep = v > 0; v = v(keep); ord = ord(keep);
                [ri, ci] = ind2sub(size(D), ord);
                Td = table(reg_codes(ci), labs.region(ri), sec_name(ri), labs.type(ri), ...
                           v, v / sum(D(:)), ...
                           'VariableNames', {'consumer_region', 'supply_region', ...
                           'product', 'column_type', 'kgO2', 'share_of_LME'});
                writetable(Td, fullfile(CBA_DIR, 'focus', ...
                    sprintf('%s_%d_%s_consumption_top.csv', flow, year, char(lab))));

                % console: who consumes this LME's eutrophication (top 5)
                [cv, co] = maxk(FP(ridx, :), 5);
                fprintf('    %-6s %-5s (%s): top consumers ', flow, char(lab), FOCUS_LME{k, 2});
                for t = 1:numel(co)
                    fprintf('%s %.2e | ', reg_codes{co(t)}, cv(t));
                end
                fprintf('kg O2 (coverage top%d cells: %.1f%%)\n', TOPN, 100 * sum(v) / max(sum(D(:)), eps));
            end
        end
    end
    clear L Y_cty                                  % free ~12 GB before next year
end

%% 3) tidy master + done
%   The master is rebuilt from ALL per-year FP_<flow>_<year>.csv files in CBA_DIR, so a run
%   restarted at a later year, or split over several MATLAB sessions, still gives 2015-2022.
if RUN_AGG
  try                                        % never lose a finished run on this summary step
    ff = dir(fullfile(CBA_DIR, 'FP_*.csv'));
    parts = {}; n_long = 0;
    for k = 1:numel(ff)
        tok = regexp(ff(k).name, '^FP_(Nleach|NH3|NOx)_(\d{4})\.csv$', 'tokens', 'once');
        if isempty(tok), continue, end
        C    = readcell(fullfile(ff(k).folder, ff(k).name), 'Delimiter', ',');
        regs = string(cellfun(@num2str, C(1, 2:end), 'UniformOutput', false));   % consumer region codes
        labs = string(cellfun(@num2str, C(2:end, 1), 'UniformOutput', false));   % LME labels ('10' may load as a number)
        V    = cell2mat(C(2:end, 2:end));      % 305 x 164 kg O2
        [nr, nc] = size(V);
        parts{end+1} = table(repmat(str2double(tok{2}), nr*nc, 1), repmat(string(tok{1}), nr*nc, 1), ...
                             repmat(labs, nc, 1), repelem(regs(:), nr), V(:), ...
                             'VariableNames', {'year', 'flow', 'LME_ss', 'consumer_region', 'kgO2'}); %#ok<AGROW>
        n_long = n_long + nr*nc;
    end
    if ~isempty(parts)
        M = sortrows(vertcat(parts{:}), {'year', 'flow'});
        writetable(M, fullfile(CBA_DIR, 'FP_all_years_long.csv'));
        fprintf('\nlong master written: %d rows, years %s -> %s\n', n_long, ...
                mat2str(unique(M.year)'), fullfile(CBA_DIR, 'FP_all_years_long.csv'));
    end
  catch err
    warning('master table not written (%s) - the per-year FP_*.csv files are complete.', err.message);
  end
end
disp('DONE.  CBA matrices in ''1. results\CBA'', PBA vectors in ''1. results\PBA'',');
disp('       region-level comparison tables in ''1. results\CBA_vs_PBA''.');
