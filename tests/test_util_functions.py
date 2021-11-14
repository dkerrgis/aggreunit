from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest
import rasterio

from aggreunit import raster_to_polygon, join_population_to_shp, get_pop_density, get_labels, aggr_table, sort_by_density, aggr_constrained_shp, rasterize, save_shapefile, dissolve_admin_units

BASE = Path(__file__).resolve().parent.joinpath('data')

#----------------INPUT------------------
L1 = BASE.joinpath('abw_subnational_admin_2000_2020.tif')
L1_CONSTR = BASE.joinpath('abw_L1_constrained.tif')
TABLE = BASE.joinpath('abw_population_2000_2020.csv')
PIXEL = BASE.joinpath('abw_px_area_100m.tif')
#----------------INPUT------------------

#---------------OUTPUT--------------------
L1_SHP = L1.parent.joinpath(f'{L1.stem}.shp')
L1_CONSTR_SHP = L1.parent.joinpath(f'{L1_CONSTR.stem}.shp')
TABLE_AGGR = TABLE.parent.joinpath(f'{TABLE.stem}_A.csv')
L1_SHP_AGGR = L1.parent.joinpath(f'{L1_SHP.stem}_A.shp')
L1_A = L1.parent.joinpath(f'{L1.stem}_A.tif')

#---------------OUTPUT--------------------

#############FIXTURES###################
@pytest.fixture
def poly():
    gdf = raster_to_polygon(L1)
    yield gdf
#############FIXTURES##################

def test_files_exist():
    assert L1.exists()
    assert L1_CONSTR.exists()
    assert TABLE.exists()
    assert PIXEL.exists()

def test_raster_to_polygon(poly):
    gdf = poly
    src = rasterio.open(L1)
    data = src.read()
    data = data != src.nodata
    units_expected = sorted(list(np.unique(data)))
    units_got = sorted(gdf.adm_id.to_list())
    assert isinstance(gdf, gpd.GeoDataFrame)

def test_raster_to_polygon_save_shp():
    if L1_SHP.exists():
        [x.unlink() for x in BASE.iterdir() if x.stem == L1.stem if not x == L1]
    gdf = raster_to_polygon(L1, L1_SHP)
    gdf_saved = gpd.read_file(L1_SHP)
    gdf_adm = sorted(gdf.adm_id.to_list())
    shp_adm = sorted(gdf_saved.adm_id.to_list())
    assert gdf_adm == shp_adm

def test_join_population_to_shp_with_shp():
    gdf_pop = join_population_to_shp(L1_SHP, TABLE)
    assert isinstance(gdf_pop, gpd.GeoDataFrame)
    assert 'P_2020' in gdf_pop.columns

def test_join_population_to_shp_with_gdf():
    if L1_SHP.exists():
        [x.unlink() for x in BASE.iterdir() if x.stem == L1.stem if not x == L1]
    gdf = raster_to_polygon(L1, L1_SHP)
    gdf_pop = join_population_to_shp(gdf, TABLE, pop_col='P_2019')
    assert isinstance(gdf_pop, gpd.GeoDataFrame)
    assert 'P_2019' in gdf_pop.columns

def test_get_pop_density(poly):
    gdf_pop = join_population_to_shp(poly, TABLE)
    gdf_density = get_pop_density(gdf_pop, PIXEL, out_shp=L1_SHP)
    assert 'area' in gdf_density.columns
    assert 'density' in gdf_density.columns

def test_sort_by_density(poly):
    gdf_pop = join_population_to_shp(poly, TABLE)
    gdf_density = get_pop_density(gdf_pop, PIXEL, out_shp=L1_SHP)
    gdf_sorted = sort_by_density(gdf_density)
    gdf_sorted.to_file(L1_SHP.parent.joinpath('test.shp'))
    expected = sorted(gdf_density.density.to_list(), reverse=True)
    expected = [x for x in expected if not str(x) == 'nan']
    got = gdf_sorted.density.to_list()
    got = [x for x in got if not str(x) == 'nan'] #remove water polygon values (nan)
    assert expected[1] == got[1]
    assert expected[5] == got[5]
    assert expected[-1] == got[-1]
    

def test_get_labels(poly):
    gdf_pop = join_population_to_shp(poly, TABLE)
    gdf_density = get_pop_density(gdf_pop, PIXEL, out_shp=L1_SHP)
    gdf_sorted = sort_by_density(gdf_density)
    gdf_labelled = get_labels(gdf_sorted)
    parent_poly_expected = 53351 #Most dense ID (manually checked)
    child_poly_expected = 53354 #Most dense neighbour to 53351 (manually checked)
    assert gdf_labelled.at[child_poly_expected, 'labels'] == parent_poly_expected

def test_aggr_table(poly):
    gdf_pop = join_population_to_shp(poly, TABLE)
    gdf_density = get_pop_density(gdf_pop, PIXEL, out_shp=L1_SHP)
    gdf_sorted = sort_by_density(gdf_density)
    gdf_labelled = get_labels(gdf_sorted)
    aggr_table(TABLE, gdf_labelled, TABLE_AGGR)
    aggr_df = pd.read_csv(TABLE_AGGR)
    assert pytest.approx(abs(gdf_labelled.P_2020.sum() - aggr_df.P_2020.sum()), 0)
    assert len(aggr_df) == len(gdf_labelled.labels.unique()) -1 #remove water rows


def test_aggr_constrained_shp(poly):
    if L1_CONSTR_SHP.exists():
        [x.unlink() for x in BASE.iterdir() if x.stem == L1_CONSTR.stem if not x == L1_CONSTR]
    gdf_pop = join_population_to_shp(poly, TABLE)
    gdf_density = get_pop_density(gdf_pop, PIXEL, out_shp=L1_SHP)
    gdf_sorted = sort_by_density(gdf_density)
    unconstr_gdf = get_labels(gdf_sorted)
    const_gdf = raster_to_polygon(L1_CONSTR, L1_CONSTR_SHP)
    aggr_constr_gdf = aggr_constrained_shp(unconstr_gdf, const_gdf)
    labels = unconstr_gdf.labels.unique()
    #labels = labels[labels != 0]
    assert len(aggr_constr_gdf) == len(labels) -1

def test_dissolve_admin_units(poly):
    if L1_CONSTR_SHP.exists():
        [x.unlink() for x in BASE.iterdir() if x.stem == L1_CONSTR.stem if not x == L1_CONSTR]
    gdf_pop = join_population_to_shp(poly, TABLE)
    gdf_density = get_pop_density(gdf_pop, PIXEL, out_shp=L1_SHP)
    gdf_sorted = sort_by_density(gdf_density)
    unconstr_gdf = get_labels(gdf_sorted)
    gdf_diss = dissolve_admin_units(unconstr_gdf)
    assert len(gdf_diss) < len(unconstr_gdf)



def test_save_shapefile(poly):
    if L1_CONSTR_SHP.exists():
        [x.unlink() for x in BASE.iterdir() if x.stem == L1_CONSTR.stem if not x == L1_CONSTR]
    gdf_pop = join_population_to_shp(poly, TABLE)
    gdf_density = get_pop_density(gdf_pop, PIXEL, L1_SHP)
    gdf_sorted = sort_by_density(gdf_density)
    unconstr_gdf = get_labels(gdf_sorted)
    gdf_diss = dissolve_admin_units(unconstr_gdf)
    save_shapefile(gdf_diss, L1_SHP_AGGR)
    gdf = gpd.read_file(L1_SHP_AGGR)
    assert len(gdf) == len(gdf_diss)


def test_rasterize():
    gdf = gpd.read_file(L1_SHP_AGGR)
    src = rasterio.open(L1)
    profile = src.profile
    rasterize(gdf, L1, L1_A)
    src = rasterio.open(L1_A)
    profile_ = src.profile
    assert profile_['height'] == profile['height']
    assert profile_['width'] == profile['width']
    data = src.read()
    src.close()
    units = list(np.unique(data[data != profile['nodata']]))
    assert len(gdf) == len(units)
    assert 0 in units



