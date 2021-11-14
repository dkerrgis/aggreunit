# aggreunit

Script to aggregate/merge adiministrative units based on population density


## TODO

### Inputs
1. Seed subnational admin unit raster (Admin unit raster from which to aggregate)
2. PPP raster
3. Population table - ID's should match the subnational raster
4. Pixel area raster
5. Target reduction/aggregation (seed = 100 units -> target = 50 units)


## Workflow
1. Polygonise subnational raster
2. Join population table to 1 shapefile
3. Calculate population density in each admin unit
    a. Zonal stats on area raster
    b. Calculate people per square km (or meters???)
    c. Add density to out table
4. Sort by population density
5. Make labels to indicate whether admin unit has been joined yet or not
6. While len(shp) > target reduction:
    - Iterate non-aggregated units, merge/dissolve with most dense neighbour
7. Rasterize shapefile
8. Calculate new population in merged admin unit
9. Save shapefile