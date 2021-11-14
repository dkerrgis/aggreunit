"""
Helper functions
"""
from pathlib import Path 
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from rasterstats import zonal_stats #Deprecation warning for collections.abc import in this module
import rasterio
from rasterio.features import shapes

from .rasterize_geoms import RasterizeAdminUnits

def raster_to_polygon(raster, out_shp=None):
    """
    Returns GeoDataFrame of polygonisation of raster and saves GeoDataFrame to out_shp

    Parameters:
    ------------
    raster: (Path/str)
        Path to input raster to polygonise
    out_shp:    (Path/str) - Optional: Default = None
        Path to output polygone shape

    Returns:
    --------
    gdf :   (gpd.GeoDataFrame)
        Geodataframe of polygonised version of input raster 
    """
    mask = None
    with rasterio.Env():
        with rasterio.open(raster) as src:
            image = src.read().astype(np.int32)# first band
            mask = image != src.nodata
            results = ({'properties': {'adm_id': v}, 'geometry': s}   for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform)))
            geoms = list(results)
    gdf = gpd.GeoDataFrame.from_features(geoms, crs='EPSG:4326').dissolve(by='adm_id')
    gdf = gdf.reset_index()
    if out_shp:
        if not out_shp.exists():
            gdf.to_file(out_shp, index=False)
        else:
            raise FileExistsError(f"{out_shp} exists. Please delete before creating new shapefile")
    return gdf

def join_population_to_shp(shp, csv, shp_id='adm_id', csv_id='GID', pop_col='P_2020'):
    """Joins population csv to shapefile and returns geodataframe -- Overwrites input shp (if it's a file and not a dataframe) with population column from table
    
    Parameters:
    ------------
    shp:    (Path/str/GeoDataframe)
        Path to admin unit shapefile or Geodataframe object of shapefile
    csv :   (Path/str)
        Path to population table
    shp_id  :   (str)
        Column in shapefile used for join (Default -> 'adm_id')
    csv_id  :   (str)
        Column in csv used for join (Default -> 'GID')

    """
    if not isinstance(shp, gpd.GeoDataFrame):
        gdf = gpd.read_file(shp)
    else:
        gdf = shp
    gdf = gdf[[x for x in gdf.columns if not x == pop_col]].set_index(shp_id)
    df = pd.read_csv(csv)
    df[shp_id] = df[csv_id]
    df_cols = [shp_id, pop_col]
    df = df[df_cols].set_index(shp_id)
    gdf_pop = gpd.GeoDataFrame(gdf.join(df))
    if not isinstance(shp, gpd.GeoDataFrame):
        gdf_pop.to_file(shp)
    return gdf_pop

#density to gdf
def get_pop_density(shp, raster, out_shp=None, shp_index_col='adm_id', pop_col='P_2020'):
    """
    Returns Geodataframe of admin units with population density appended

    Parameters:
    -----------
    shp :   (Path/str/gpd.GeoDataFrame)
        Path to/geodataframe of imput geometries
    raster  :   (Path/str)
        Path to pixel area raster
    out_shp :   (Path/str)
        Path to output shapefile
    shp_index_col   :   (str)
        Shape column used in join (Default = 'adm_id')
    pop_col :   (str)
        Population column in shapefile

    Returns:
    --------
    gdf_density :   (gpd.GeoDataFrame)
        Input geodataframe with population density column appended
    """
    if not isinstance(shp, gpd.GeoDataFrame):
        gdf = gpd.read_file(shp)
    else:
        gdf = shp
    gdf = gdf[[x for x in gdf.columns if not x in ['area', 'density', 'sum']]].reset_index()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore') #Collections.abc deprecation warning in below function call
        gdf_sum = zonal_stats(gdf, raster, stats=['sum'], geojson_out=True)
    gdf_sum = gpd.GeoDataFrame.from_features(gdf_sum, crs="EPSG:4326")[['adm_id', 'sum']]
    gdf_sum['area'] = gdf_sum['sum']
    gdf_density = gpd.GeoDataFrame(gdf.set_index(shp_index_col).join(gdf_sum.set_index(shp_index_col)))
    gdf_density['density'] = gdf_density[pop_col] / gdf_density['area']
    cols = [pop_col, 'area', 'density', 'geometry']
    gdf_density = gdf_density[cols]
    gdf_density = gdf_density.fillna(0)
    if out_shp:
        gdf_density.to_file(out_shp)
    return gdf_density

def sort_by_density(gdf):
    """
    Returns gdf sorted by density adds lables and paired (or not) boolean

    Parameters  
    -----------
    gdf :   (gpd.GeoDataFrame)
        Input geodataframe with density value column

    Returns
    --------
    gdf :   (gpd.GeoDataFrame)
        Sorted dataframe (by density) with labels to indicate whether admin unit has been paired yet (all initialised to False)
    """
    gdf = gdf.sort_values(by='density', ascending=False)
    gdf['labels'] = gdf.index
    gdf['paired'] = False
    return gdf

def get_labels(gdf):
    """
    Returns geodataframe with 'labels' and 'columns' set according to most dense neighbours. Will loop through rows will complete once number of units have been reduced by ~50%

    Parameters:
    -----------
    gdf     :   (gpd.GeoDataFrame)
        Dataframe in which units will be matched with dense neighbours 

    Returns:
    ---------
    gdf     :   (gpd.GeoDataFrame)
        Dataframe with units matched with their neighbours.
    """
    required_number_of_units = round(len(gdf.labels.unique()) - (len(gdf.labels.unique()) * 0.5))
    probs = 0
    gdf.loc[gdf.labels == 0, 'labels'] = 0
    gdf.loc[gdf.labels == 0, 'paired'] = True
    for index, row in gdf.iterrows():
        if len(gdf.labels.unique()) <= required_number_of_units:
            print(f'{len(gdf.labels.unique())} admin units made. Finished')
            break
        if not gdf.loc[index, 'labels'] == 0:
            if gdf.loc[index, 'paired'] == False:
                paired = False
                neighbour_df = gdf[gdf.geometry.touches(row['geometry'])]
                #isplay(neighbour_df)
                for i, neighbour in neighbour_df.iterrows():
                    #Join up polygon with neighbour if not paired before
                    if gdf.at[i, 'paired'] == False:
                        gdf.at[index, 'paired'] = True
                        gdf.at[i, 'paired'] = True
                        gdf.at[index, 'labels'] = index
                        gdf.at[i, 'labels'] = index
                        paired = True
                        break
    return gdf

def aggr_table(csv, gdf, out_csv, pop_col='P_2020', index_col='GID'):
    """
    Updates population csv by summing populations based on aggregation

    Parameters:
    -----------
    csv :   (Path/str)
        Path to input pop csv
    gdf :   (gpd.GeoDataFrame)
        Geodataframe of aggregated admin units
    pop_col :   (str)
        Column in population table used for summing (Default = 'P_2020')
    index_col   :   (str)
        Column in pop table used for index to aggregate (Default = 'GID')

    Returns:
    ----------
    None    
    """
    df = pd.read_csv(csv)
    if not 'adm_id' in df.columns:
        df['adm_id'] = df[index_col]
    df = df[['adm_id', pop_col]].set_index('adm_id')
    gdf = gdf[['labels']]
    df_joined = df.join(gdf).reset_index()
    df_joined['adm_id'] = df_joined['labels']
    df_joined = df_joined[['adm_id', pop_col]].groupby('adm_id').sum() #Aggregate admin units and sum populations
    df_joined.to_csv(out_csv)

def aggr_constrained_shp(unconstr_gdf, constr_gdf):
    """
    Returns identical aggregation for unconstrained dataframe to match that of contrained dataframe.

    Parameters:
    -----------
    unconstr_gdf    :   (gpd.GeoDataFrame)
        gdf of admin unit polygons with labels indicating how units will be aggregated BEFORE DISSOLVING (unconstr and constr should have the same number of rows)
    constr_gdf  :   (gpd.GeoDataFrame)
        gdf polygonised from admin units covering ONLY areas that are 'built'.

    Retruns:
    ---------
    constr_gdf    :   (gpd.GeoDataFrame)
        Unconstrained geodataframe aggregated to same level (as indicated by the constrained labels) as constrained geodataframe
    """
    constr_gdf = constr_gdf[['geometry']]
    unconstr_gdf = unconstr_gdf.reset_index()
    constr_gdf['labels'] = unconstr_gdf['labels']
    constr_gdf['adm_id'] = constr_gdf['labels']
    constr_gdf = constr_gdf[['adm_id','geometry']]
    constr_gdf = constr_gdf.dissolve(by='adm_id')
    return constr_gdf

def dissolve_admin_units(gdf):
    """
    Returns input gdf with dissolved geometries based on identical values in 'adm_id'

    Parameters:
    -----------
    gdf :   (gpd.GeoDataFrame)
        Geodataframe to dissolve with field of 'adm_id'

    Returns:
    ---------
    gdf :   (gpd.GeoDataFrame)
        Geodataframe with dissolved geometries based on idential values in 'adm_id'
    """	
    gdf = gdf.reset_index()
    gdf['adm_id'] = gdf['labels']
    gdf = gdf.dissolve(by='adm_id')
    return gdf

def save_shapefile(gdf, outname):
	"""Save shapefile to outname
    
    Parameters:
    -----------
    gdf :   (gpd.GeoDataFrame)
        Dataframe to save
    outname :   (Path/str)
        Path to same outfile
    """
	gdf.to_file(outname)


def rasterize(gdf, raster, out_name):
    """
    Rasterises gdf and saves to outname

    Parameters:
    ------------
    gdf :   (gpd.GeoDataFrame)
        Geodataframe to rasterise
    raster  :   (Path/str)
        Path to raster to be used as snap/extent template
    """
    gdf = gdf.reset_index()
    rasterise = RasterizeAdminUnits(gdf, raster, out_name).rasterize_geometries()

