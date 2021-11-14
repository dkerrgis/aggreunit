from pathlib import Path
import geopandas as gpd
import pandas as pd 
from rasterstats import zonal_stats 
import fiona
from rasterio import features

import rasterio
import numpy as np

class RasterizeAdminUnits:
    """Rasterize input gdf, snapping to input raster and saving to output name"""
    def __init__(self, gdf, raster, out_name):
        """
        Initialisation

        Parameters:
        gdf (gpd.GeoDataFrame) : input gdf 
        raster (Path/str) : Raster to snap and match in output
        out_name (Path/str) : Output raster name

        Returns:
        None
        """
        self.gdf = gdf 
        self.raster = raster
        self.out_name = out_name
        if not isinstance(self.gdf, gpd.GeoDataFrame):
            try:
                self.gdf = gpd.read_file(self.gdf)
            except:
                raise Error("There is a problem with the input Shapefile/geodataframe")

    def get_geometries_from_gdf(self):
        """Returns list of geometries and their values in gdf
        
        Parameters:
        None

        Returns:
        None
        """
        self.gdf = self.gdf.reset_index()
        geometries = ((geom,value) for geom, value in zip(self.gdf['geometry'], self.gdf['adm_id']))
        return geometries

    def rasterize_geometries(self):
        """
        Returns raster object along with copy of metadata for use in the output raster

        Parameters:
        gdf_water (gpd.GeoDataFrame) : Water polygons removed when clustering 

        Returns:
        src (rasterio.<Object>) : Opened raster dataset
        meta (dict) : Band meta data
        """
        geometries = self.get_geometries_from_gdf()#########################
        with rasterio.open(str(self.raster)) as src:
            kwargs = src.meta.copy()
            kwargs.update({
                'driver': 'GTiff',
                'compress': 'lzw',
                'dtype': 'int32'
            })
            windows = src.block_windows(1)
            with rasterio.open(str(self.out_name), 'w+', **kwargs) as dst:
                #for idx, window in windows:
                out_arr = dst.read(1)
                out_arr = out_arr.astype(np.int32)
                burned = features.rasterize(shapes=geometries, fill=src.nodata, out=out_arr, out_shape=(kwargs['height'],kwargs['width']), transform=src.transform)
                dst.write(burned, 1)