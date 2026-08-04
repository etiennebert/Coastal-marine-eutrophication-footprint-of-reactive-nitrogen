%% create FFs matrices based on the SRM matrices from Roy et al 2012
% This script calculates a 13104x13104 matrix collecting the CF for each
% emission cell to each deposition cell. 

haut=30;
keep_N=zeros(91,144); %entire deposition at every grid location 

%% open the emission files and sum over the first 30 emission heights (haut)
    em=load('Z:\Sections\QSA\BACKUP\Eldbjoerg_Vea\Marine N model\From Andrew H\NOXemission\NOxemission');
    emi = getfield(em,'emission');
    emission_nox(1:91,1:144)=sum(emi(1:haut,:,:));
    clear em
    clear emi
     
 %% load ocean, land and fw fractions
    of=flip(getfield(load('Model input\surfacecover\ocean_frac'),'ocean_frac'));
    lf=flip(getfield(load('Model input\surfacecover\land_frac'),'land_frac'));
    fwf=flip(getfield(load('Model input\surfacecover\fw_frac'),'fw_frac'));
    
    %load components for deposition on land gridcells (soil and fw fractions exported (FE), FF ocean
    %(1/removal_c), XF and plant updake
    FE_s_table=readtable('Model input\FE_all_soils_airgrid.xlsx');
    FE_fw_table=readtable('Model input\FE_fw_airgrid.xls');
    FF_mar_inland_table=readtable('Model input\FF_mar_inland_airgrid.xls');
    XF_c_table=readtable('Model input\XF_airgrid_final.xls');%THis is calculated as average withint the ai gridcell overlaying different riverbasins, hence that one gridcell can export to various riverbasins with different XFs is considered
    plantuptake_table=readtable('Model input\plantuptake_airgrid_fin.xls');%This is a fraction of N in that is taken up by vegetation (crops and intensivly managed grassland, i.e. removed from the system)
 
    %This is the removal rates for direct deposition on ocean.
    FF_mar_o_table=readtable('Model input\FF_mar_ocean_airgrid.xls');
    XF_o_table=readtable('Model input\XF_SOS_coast_ocean_airgrid_final.xlsx');
    
       
    %rearrange the tables into 91x144 matrices based on their objecID (like
    %I did with the surface covers:
    FE_s_v=table2array(FE_s_table(:,5)); %converting table to vector, and only selecting FE, which is in column number 5..
    A=reshape(FE_s_v,144,91);
    FE_s=A';
    X=isnan(FE_s); %turning NaN to 0
    FE_s(X)=0;
    
    clear A B X
    FE_fw_v=table2array(FE_fw_table(:,5)); %coverting table to vector, and only selecting FE, which is in column number 5..
    A=reshape(FE_fw_v,144,91);
    FE_fw=A';
    X=isnan(FE_fw); %turning NaN to 0
    FE_fw(X)=0;
    
    clear A B X
    FF_mar_c_v=table2array(FF_mar_inland_table(:,24)); %coverting table to vector, and only selecting FE, which is in column number 5.
    A=reshape(FF_mar_c_v,144,91);
    FF_mar_c=A';
    X=isnan(FF_mar_c); %turning NaN to 0
    FF_mar_c(X)=0; %marine FFs associated with inland riverbasin gridcell 
    
    clear A B X
    FF_mar_o_v=table2array(FF_mar_o_table(:,6)); %coverting table to vector, and only selecting FE, which is in column number 11.
    A=reshape(FF_mar_o_v,144,91);
    FF_mar_o=A';
    X=isnan(FF_mar_o); %turning NaN to 0
    FF_mar_o(X)=0; %marine FFs associated with ocean and coastal gridcells

    clear A B X
    terminal_v=table2array(FF_mar_inland_table(:,21)); %to exclude export from terminal riverbasins
    A=reshape(terminal_v,144,91);
    terminal=A';
    X=isnan(terminal); %turning NaN to 0
    terminal(X)=0; %marine FFs associated with inland riverbasin gridcells
    
    X=terminal==0; %switching terminal mask indicaiton to 0 for terminal basins, 1 for non terminal
    Y=terminal==1;
    terminal(X)=1;
    terminal(Y)=0;
    
    clear A B X
    XF_c_v=table2array(XF_c_table(:,20)); %coverting table to vector, and oly selecting FE, which is in column number 11.
    A=reshape(XF_c_v,144,91);
    XF_c=A';
    X=isnan(XF_c); %turning NaN to 0
    XF_c(X)=0;
    
    clear A B X
    XF_o_v=table2array(XF_o_table(:,7)); %coverting table to vector, and oly selecting FE, which is in column number 11.
    A=reshape(XF_o_v,144,91);
    XF_o=A';
    X=isnan(XF_o); %turning NaN to 0
    XF_o(X)=0;
    
    clear A B X
    plantuptake_v=table2array(plantuptake_table(:,5)); %coverting table to vector, and only selecting the plant uptake parameter which is in column 5
    A=reshape(plantuptake_v,144,91);
    plant_uptake=A';
    X=isnan(plant_uptake); %turning NaN to 0
    plant_uptake(X)=0;    
    
    plant=ones(91,144);
    
%% Calculate air deposition CFs
a=1
while a<=91
    b=1; 
         srm=strcat('Z:\Sections\QSA\BACKUP\Eldbjoerg_Vea\Marine N model\From Andrew H\sent_NOX\SRMNOx',int2str(a),'original_1e-7.mat'); % Open the SRM for the (a,b) horizontal grid
         dep=load(srm);
         dep_NOx= getfield(dep,'srm');%saves the 3D SRM for location latitute a
         clear dep
    
        %FF_atm_NHx_cell=dep_NHX(b,:,:)/emission_nhx(a,b);
        %save(strcat('FF_atm_NHx_',num2str(a)),'FF_atm_NHx_cell')
        
        while b<=144

    depnox(1:91,1:144)=dep_NOx(b,:,:);  % Give the worldwide deposition related to that particular horizontal grid emission in (a,b)   
    FF_atm_NOx=depnox/emission_nox(a,b); %provide the  fate factor to that particular horizontal grid(a,b)emission as a 91x144 matrix
    
    %% Create mega matrix (13104 x 1304) contatining all data, if this is wanted...
    
    temporary= depnox/emission_nox(a,b);   %used for the mega matrix; The fate factor for the emission location as a 91x144 matrix
    e=1;
    ff_line=[];
       
    while e<=91
        ff_line=[ff_line,temporary(e,:)];       % This should give you at e=92 a 1x13104 matrix. If it gives you a 13104x1 matrix, simply add after the "end", ff_line=ff_line'; which will give you the inverse.                                                                     %Also if you get an error here, try "," instead of ";" after "[ff_line". I often get mixed up between the two but they are simply spacers that tell you how you                                                    %   want to create your matrix
        e=e+1;
    end 
   
    FF_nox_all((a-1)*144+b,:)=ff_line;     % this tells you to replace the zeros with the values of the fate factor for a given grid. You just went from a 2D system to a 1D system                                                                                                  

    b=b+1;
    end

a=a+1

end

FF_nox_all(isnan(FF_nox_all))=0;
% writematrix(FF_nox_all, 'FF_NOx_all.csv')

CF_nox_all=zeros(13104,13104);

i=0
while i<=13103
    b = rem(i, 144) + 1;
    a = int32((i-b)/144) + 1;
    if b == 0
        b = 144;
    end
    j=0;
    while j<=13103
        d = rem(j, 144) + 1;
        c = int32((j-d)/144) + 1;
        if d == 0
            d = 144;
        end

        CF_o_ij = FF_nox_all(i+1,j+1)*of(c,d)*FF_mar_o(c,d)*XF_o(c,d);
        CF_fw_ij = FF_nox_all(i+1,j+1)*fwf(c,d)*FE_fw(c,d)*FF_mar_c(c,d)*XF_c(c,d)*terminal(c,d);
        CF_s_ij = FF_nox_all(i+1,j+1)*lf(c,d)*(plant(c,d)-plant_uptake(c,d))*FE_s(c,d)*FF_mar_c(c,d)*XF_c(c,d)*terminal(c,d);
        
        CF_ij = CF_o_ij + CF_fw_ij + CF_s_ij;

        CF_nox_all(i+1,j+1) = CF_ij;

        j = j+1;
    end

    i = i+1
end


CF_nox_all(isnan(CF_nox_all))=0;
writematrix(CF_nox_all, 'CF_NOx_all.csv')

 %% Exporting CFs
   
    %  export as tiff
%     clear A
%     A=CF_NOX; 
%     latlim = [-90 90];
%     lonlim = [-180 180];
%     rasterSize = size(A);
%     R = georefcells(latlim,lonlim,rasterSize,"ColumnsStartFrom","north","RowsStartFrom","west");
% 
%     geotiffwrite('CF_NOx.tif',A,R) 

   
    % to export as asci see "CFs_inland.m" script.. 
    
   % Export as Excel talbe as a vector to be joined with emissions and
   % countries for aggregation...--> not used in the end, as I need to
   % export to ArcGIS to be able to aggregate according to Hendeson
   % formula..
%     clear A B X
%     A=flip(CF_NH3);
%     B=A';
%     CF_NH3_v=reshape(B,13104,1);
    
    %validating the above with OID
%     clear A B X
%     OID_table=readtable('C:\Users\ebve\Documents\Nmodel_data\Complete_N_LCIA\AtmosphericFFs\FE_all_soils_airgrid.xlsx');
%     OID_v=table2array(OID_table(:,1)); %coverting table to vector, and oly selecting FE, which is in column number 11.
%     A=reshape(OID_v,144,91);
%     B=A';
%     OID=flip(B); 
%     %turn OID matrix back to vector
%     clear A B X
%     A=flip(OID);
%     B=A';
%     OID_v_test=reshape(B,13104,1);
% 

% % Plot CFs...
%     latlim = [-90 90];
%     lonlim = [-180 180];
%     rasterSize = size(CF);
%     R = georefcells(latlim,lonlim,rasterSize,"ColumnsStartFrom","north","RowsStartFrom","west");
%     figure
%     worldmap(CF,R)
%     geoshow(CF,R,'DisplayType','texturemap')
%     colormap colorcube %see help GRAPH3D for different types of colormaps to use.. 
%     colorbar
% 
% 
    %Check if it make sense by plotting...
 
%     contourlines=0:0.00001:0.001;   %  
%     c=flip(CF_NH3); %have to flip as it is orginially is upsidedown, as it is plotted by x,y axix.
%     figure;contourf(c,contourlines); 
%     cb=colorbar;
% %    
%     A=FF_o;
%     contourlines=0:0.00001:0.001;   %  
%     c=flip(A); %have to flip as it is orginially is upsidedown, as it is plotted by x,y axix.
%     figure;contourf(c,contourlines); 
%     cb=colorbar;
%     
