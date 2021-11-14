"""
Class to wrap up functions in utilities to process the aggregation of admin units for validataion
"""
from pathlib import Path 
import aggreunit

class AggregateUnits:
    """
    Class to wrap up functions in utilities to process the aggregation of admin units for validataion
    """
    def __init__(self, admin_raster, population_table, area_raster, out_admin_raster, out_population_table, out_admin_shapefile, save_admin_shape=False):
        """
        Instantiation

        Parameters:
        -----------
        admin_raster    :   (Path/str)
            Path to subnational admin unit raster
        population_table  :   (Path/str)
            Path to csv with populations for each admin unit as defined in admin_raster
        area_raster     :   (Path/str) 
            Path to pixel area raster matching extent of admin_raster
        out_admin_raster    :   (Path/str)
            Path to output raster with aggregated units
        out_population_table    :   (Path/str)
            Path to output csv of aggregated population counts
        out_admin_shapefile     :   (Path/str)
            Path to output shapefile of aggregated admin_units
        save_admin_rastershape   :   (Boolean)
            Indicates whether or not to save shapfile of admin_raster to same folder/name (with different suffix) as admin_raster
        """
        self.admin_raster = admin_raster
        self.population_table = population_table
        self.area_raster = area_raster
        self.out_admin_raster = out_admin_raster
        self.out_population_table = out_population_table
        self.out_admin_shapefile = out_admin_shapefile
        self.save_admin_shape = save_admin_shape

    def _aggregate(self):
        """
        Wrapper function to process aggregation and save output

        Parameters:
        ----------
        None

        Returns:
        --------
        None
        """
        if self.save_admin_shape == True:
            out_shp = self.admin_raster.parent.joinpath(f'{self.admin_raster.stem}.shp')
        else:
            out_shp = None 
        l1_gdf = aggreunit.raster_to_polygon(self.admin_raster, out_shp=out_shp)
        gdf_pop = aggreunit.join_population_to_shp(l1_gdf, self.population_table, pop_col='B_Tot')
        gdf_density = aggreunit.get_pop_density(gdf_pop, self.area_raster, out_shp=out_shp, pop_col='B_Tot')
        gdf_sorted = aggreunit.sort_by_density(gdf_density)
        unconstr_gdf = aggreunit.get_labels(gdf_sorted)
        gdf_diss = aggreunit.dissolve_admin_units(unconstr_gdf)
        aggreunit.aggr_table(self.population_table, unconstr_gdf, self.out_population_table, pop_col='B_Tot')
        aggreunit.save_shapefile(gdf_diss, self.out_admin_shapefile)
        aggreunit.rasterize(gdf_diss,self.admin_raster, self.out_admin_raster)



