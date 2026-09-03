%Script to make surface area cover by ocean, land and freshwater 

%imported landcover fractions from Excel using import tool (surfacecover.mat)
Surfacecover=readtable('C:\Users\ebve\Documents\Nmodel_data\Complete_N_LCIA\Atmospheric CFs\Model input\Surfacecover\Surface_cover.xlsx');
surface_cover=Surfacecover;

clear A
%Testing with OID first..
OID_v=surface_cover(:,1);
OID_v=table2array(OID_v);
A=reshape(OID_v,144,91);
B=A';
OID_fishnet=flip(B);

%Calculating land fractions (%)
land_v=surface_cover(:,6);
land_v=table2array(land_v);
A=reshape(land_v,144,91);
B=A';
land_frac=flip(B)./100; %from % to fraction (input in %)

land_frac(1,:)=0; %assigning the first row and first colum 0, as these airgrid cells overlapped with areas outside the map, assigning half og hte cell with ocean. When caculating the land fraciton in Excel (substracting 1 form ocena nd fw surface), the rest of the gridells where faultly assigne land cover values
land_frac(:,1)=0; 
save("land_frac",'land_frac')

%Calculating oceanfractions (%)
clear A;
ocean_v=surface_cover(:,3);
ocean_v=table2array(ocean_v);
A=reshape(ocean_v,144,91);
B=A';
ocean_frac=flip(B)./100; %from % to fraction (input in %)
save("ocean_frac",'ocean_frac')  

%Calculating freshwater fractions 
clear A;
fw_v=surface_cover(:,4);
fw_v=table2array(fw_v);
A=reshape(fw_v,144,91);
B=A';
fw_frac=flip(B)./100; %from % to fraction (input in %)
save("fw_frac",'fw_frac')

%CHeck that is add up to 100%..
tot_m=land_frac+ocean_frac+fw_frac;

%Check if it make sense by plotting...
contourlines=0:0.01:1;   %  
  figure;contourf(land_frac,contourlines); %%is upsidedown, as it is plotted by x,y axix.
  cb=colorbar;

  contourlines=0:100:10000;   %  
  figure;contourf(OID_fishnet,contourlines); %is upsidedown, as it is plotted by x,y axix..
  cb=colorbar;  
  
  
  
  %% 

    %make 91x144 matrix identical to OIDs from arcGIS fishnet (OID 1 starting
%from south-west corner). TEst..
clear all
OID_v=[1:13104];
A=reshape(OID_v,144,91);
B=A';
OID_fishnet=flip(B);
