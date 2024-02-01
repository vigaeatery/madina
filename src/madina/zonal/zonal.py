# this lets geopandas exclusively use shapely (not pygeos) silences a warning about depreciating pygeos out of geopandas. This is not needed when geopandas 1.0 is released in the future
import os
os.environ['USE_PYGEOS'] = '0'      ## This needs to be done before importing geopandas to prevent warnings
import numpy as np
import random
import time
import warnings
import geopandas as gpd
import pandas as pd
import pydeck as pdk

from typing import Union
from pydeck.types import String
from pathlib import Path

from .network import Network
from .network_utils import node_edge_builder, _discard_redundant_edges, _split_redundant_edges, \
    _tag_edges, efficient_node_insertion
from .utils import prepare_geometry, DEFAULT_COLORS
from .layer import Layer, Layers


VERSION = '0.0.11'
RELEASE_DATE = '2023-01-22'


class Zonal:
    """
    A class to manage and organize urban data into layers and networks, acting as a workspace that manages data and facilitate interoperability across tools.
    A Zonal object populated with a veriety of data layeers and network could be used as input toi many urban analysis tools.
    Please look at the examples to see a gallery of use cases.

    Example:
        >>> shaqra = Zonal()
        >>> shaqra.add_layer(layer_name='streets', file_path='streets.geojson')
        >>> shaqra.color_layer(layer_name='streets', color=[125, 125, 125])
        >>> shaqra.create_map(save_as='street_map.html', basemap=False)
    """
    DEFAULT_PROJECTED_CRS = "EPSG:3857"
    DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"
    DEFAULT_COLORS = DEFAULT_COLORS

    def __init__(self):
        self.network = None
        self.geo_center = (None, None)
        self.layers = Layers(None)

    def __getitem__(self, item):
        return self.layers[item]

    def load_layer(
            self,
            name: str,
            source: str | Path | gpd.GeoDataFrame,
            pos: int = None,
            first: bool =False,
            before: str = None,
            after: str = None
        ) -> None:
        """ Loads a new layer from the given source with the specified layer name.
        :param name: A name for the layer the new layer.  
        :type name: str
        :param source: The data source of this layer. Could either be an existing GeoDataFrame, or a path to an acceptable file. Supported types are '.geojson', '.shp', or any file accepted by geopanda's read_file()
        :type source: str | Path | gpd.GeoDataFrame
        :param pos: position of this layer in the list of layers, defaults adding a layer at the end of the list.
        :type pos: int, optional
        :param first: if True, inserts this layer at the top of the list, defaults to False
        :type first: bool, optional
        :param before: insert before the specified layer name if specified
        :type before: str, optional
        :param after: insert after the specified layer name if specified
        :type after: str, optional
        :raises TypeError: _description_
        :raises TypeError: _description_
        :Example:

            >>> shaqra = Zonal()  # Create a Zonal object.
            >>> zonal.load_layer("streets", "path/to/streets.geojson", first=True) # Load a new layer at the beginning of the layers list.
        """
        # input verification
        if not isinstance(name, str):
            raise TypeError(f"Parameter 'layer_name' must be a string. {type(name)} was given.")
        
        if not isinstance(source, (Path, str, gpd.GeoDataFrame)): 
            raise TypeError(f"Parameter 'file_path' must be either {Path, str, gpd.GeoDataFrame}. {type(source)} was given.")
        




        if isinstance(source, (gpd.GeoDataFrame, Path, str)):
            gdf = source.copy(deep=True)
        else:
            gdf = gpd.read_file(
                source,
                engine='pyogrio'
            )

        gdf['id'] = range(gdf.shape[0])
        gdf = gdf.set_index('id')
        original_crs = gdf.crs

        # perform a standard data cleaning process to ensure compatibility with later processes
        gdf = prepare_geometry(gdf)

        layer = Layer(
            name,
            gdf,
            True,
            original_crs,
            'GeoDataFrame' if isinstance(source, gpd.GeoDataFrame) else source, 
            default_color=[round(random.random() * 255), round(random.random() * 255), round(random.random() * 255)]
        )
        self.layers.add(
            layer,
            pos,
            first,
            before,
            after
        )

        if None in self.geo_center:
            with warnings.catch_warnings():
                # This is to ignore a warning issued for doing calculations in a geographic coordinate system, but that's the needed output:
                # a point in a geographic coordinate system to center the visualization
                warnings.simplefilter("ignore", category=UserWarning)
                # centroid_point = gdf.iloc[[0]].to_crs(self.DEFAULT_GEOGRAPHIC_CRS).centroid.iloc[0]
                centroid_point = gdf['geometry'].to_crs("EPSG:4326").unary_union.centroid
            self.geo_center = centroid_point.coords[0]
        return

    def create_street_network(
            self,
            source_layer: str,
            weight_attribute: str = None,
            node_snapping_tolerance: int | float = 0,
            redundant_edge_treatment: str ='split',
            turn_threshold_degree: int | float = 45,
            turn_penalty_amount: int | float = 30,
    ) -> None:
        """Create a topologically connected street network from a specified layer in the Zonal object.

        :param source_layer: The name of the source layer to create the network from. Layer must be loaded using 'load_layer()' first.
        :type source_layer: str
        :param weight_attribute: Name of the attribute to use as percieved diatance. Given name must exist in layer attributes. Default is None, and the network cost would be calculated using geometric distance.
        :type weight_attribute: str, optional
        :param node_snapping_tolerance: Tolerance for snapping nodes. Default is 0.0 assuming that line geometries that are connected share identical common start/end points, defaults to 0.0
        :type node_snapping_tolerance: int, float, optional
        :param redundant_edge_treatment: Due to current limitations, only one edge can exist between a pair of nodes. Three options: "keep": redundant edges will be kept, posing a risk for error in network construction/calculations. "discard": The shortest edge of redundant edges will be kept. others are discarded. is kept if set to True. "split": Split redundant edges by thier centroids into non-redundant segments. Default "split".
        :type redundant_edge_treatment: str, optional
        :param turn_threshold_degree: Degree threshold for considering a turn. Default is 45. This threshold would only be used whem enabling turn penalty in UNA operations. The angle is measured as the deviation from a straight line. Can only be between 0-180. 90 degrees means a right or left turn, a 180 degree means a full U-turn
        :type turn_threshold_degree: int, optional
        :param turn_penalty_amount: Penalty amount for turns. Default is 30. This penalty (in the units of the layers' CRS) would be used as turn cost when enabling turn penalty in UNA operations. Cannot b e negative.  defaults to 30
        :type turn_penalty_amount: int, optional
        :raises ValueError: if the source layer did not exist in the object.
        :Example:
            >>> zonal = Zonal()  # Create a Zonal object.
            >>> zonal.create_street_network(
            ...     source_layer="streets",
            ...     weight_attribute="length",
            ...     node_snapping_tolerance=0.001,
            ... )
            # Create a street network using 'streets' layer and allowing geometries to be atr most 0.001 CRS units apart to form a node.
        """

        # input validation
        if not isinstance(source_layer, str):
            raise TypeError(f"Parameter 'source_layer' must be a string. {type(source_layer)} was given.")

        if source_layer not in self.layers:
            raise ValueError(f"Source layer {source_layer} not in zonal zonal_layers, available layers are: {self.layers.layers}")
        
        
        if weight_attribute is not None:
            if not isinstance(weight_attribute, str): 
                raise TypeError(f"Parameter 'weight_attribute' must be a string. {type(weight_attribute)} was given.")

            if weight_attribute not in self[source_layer].gdf.columns:
                raise ValueError(f"Parameter 'weight_attribute': {weight_attribute} not in layer {source_layer}. Available attributes are: {list(self[source_layer].gdf.columns)}")
            
        if not isinstance(node_snapping_tolerance, (int, float)): 
            raise TypeError(f"Parameter 'node_snapping_tolerance' must be either {int, float}. {type(node_snapping_tolerance)} was given.")

        if node_snapping_tolerance < 0:
            raise ValueError(f"Parameter 'node_snapping_tolerance': Cannot be negative. node_snapping_tolerance={node_snapping_tolerance} was given.")
        

        if redundant_edge_treatment not in ['keep', 'discard', 'split']:
            if not isinstance(redundant_edge_treatment, str):
                raise TypeError(f"Parameter 'redundant_edge_treatment' must be a string. {type(redundant_edge_treatment)} was given.")
            else: 
                raise ValueError(f"Parameter 'redundant_edge_treatment': must be one of ['keep', 'discard', 'split']. node_snapping_tolerance={redundant_edge_treatment} was given.")
            
        if not isinstance(turn_threshold_degree, (int, float)): 
            raise TypeError(f"Parameter 'turn_threshold_degree' must be either {int, float}. {type(turn_threshold_degree)} was given.")

        if (turn_threshold_degree < 0) or (turn_threshold_degree > 180):
            raise ValueError(f"Parameter 'turn_threshold_degree': Must be between 0 and 180. turn_threshold_degree={turn_threshold_degree} was given.")
        

        if not isinstance(turn_penalty_amount, (int, float)): 
            raise TypeError(f"Parameter 'turn_penalty_amount' must be either {int, float}. {type(turn_penalty_amount)} was given.")

        if turn_penalty_amount < 0:
            raise ValueError(f"Parameter 'turn_penalty_amount': Cannot be negative. turn_penalty_amount={turn_penalty_amount} was given.")
        

        

        geometry_gdf = self.layers[source_layer].gdf

        node_gdf, edge_gdf = node_edge_builder(
            geometry_gdf,
            weight_attribute=weight_attribute,
            tolerance=node_snapping_tolerance, 
            source_layer=source_layer
        )

        if redundant_edge_treatment == 'split':
            node_gdf, edge_gdf = _split_redundant_edges(node_gdf, edge_gdf)
        elif redundant_edge_treatment == 'discard':
            edge_gdf = _discard_redundant_edges(edge_gdf)

        edge_gdf = self.color_gdf(
            edge_gdf,
            color=[125, 125, 125],
        )

        node_gdf = self.color_gdf(
            node_gdf,
            color=[125, 125, 125],
        )

        #type is a placeholder for now, for future use when there are multuple network types, like sidewalks, bikepaths, subway links,...
        edge_gdf = edge_gdf.drop(columns=['type'])



        
        self.network = Network(node_gdf, edge_gdf, turn_threshold_degree, turn_penalty_amount, weight_attribute, edge_source_layer=source_layer)
        return

    def insert_node(self, layer_name: str, label: str = "origin", weight_attribute: str = None):
        """
        Insert "origin" and "destination" nodes into the network. This function must be called aftet the 'create_street_network' function is called, and the corresponding layer have already been loaded by calling 'load_layer'

        Args:
            layer_name (str): The name of the layer to insert the nodes from.
            label (str): The label for the new node. Default is "origin", could wither be "origin", or "destination".
            weight_attribute (str, optional): Name of the attribute to use as the node's weight. Default is None. If no weight is given, all nodes are weighted equally (Assigned a weight of 1). The attribute name must exist in the layer

        Returns:
            None: This method updates the `Zonal` object but does not return a value.

        Notes:
            - This method inserts nodes into the network within the `Zonal` object.
            - Label must either be 'origin' or 'destination'. 
            - By defualt, nodes are weighted equally, unless a 'weight_attribute" is specified

        Example:
            >>> shaqra = Zonal()  # Create a Zonal object.
            >>> shaqra.load_layer('streets', 'streets.geojson') # load streets layer
            >>> shaqra.create_street_network("streets")  # Create a street network
            >>> shaqra.load_layer('homes', 'homes.geojson')
            >>> shaqra.insert_node('homes', label="origin", weight_attribute="residents")
            >>> shaqra.load_layer('schools', 'schools.geojson')
            >>> shaqra.insert_node('schools', label="destination", weight_attribute="school_enrollment")
            # Insert a homes as origins, schools as destinations into the 'shgaqra' Zonal object

        """

        source_gdf = self.layers[layer_name].gdf
        inserted_node_gdf = efficient_node_insertion(
            self.network.nodes, 
            self.network.edges, 
            source_gdf, 
            layer_name=layer_name, 
            label=label,
            weight_attribute=weight_attribute
        )


        # these columns are not created during network creation. Adding them now prevent them from being NaN and changing column type to float instead of int. 
        for column in ['nearest_edge_id', 'edge_start_node', 'weight_to_start', 'edge_end_node', 'weight_to_end']:
            if column not in self.network.nodes:
                self.network.nodes[column] = 0

        self.network.nodes = pd.concat([self.network.nodes, inserted_node_gdf])

        self.network.nodes = self.color_gdf(
            self.network.nodes,
            color_by_attribute='type',
            color_method= 'categorical',
            color= {'origin': [86,5,255], 'destination': [239,89,128], 'street_node': [125, 125, 125]}
        )
        return

    def create_graph(self, light_graph=True, d_graph=True, od_graph=False):
        """
        After creating a street network, adding origin nodes, and destination nodes, this function must be called to construct a NetworkX object internally. This is needed to run UNA tools. 

        Args:
            light_graph: (bool) - contains only network nodes and edges
            d_graph: (bool) - contains all destination nodes and network intersectionsa. This is needed to run UNA tools. 
            od_graph: (bool) - contains all origin, destination, network, etc. nodes

        Returns:
            None

        Example: 
            >>> shaqra = Zonal()  # Create a Zonal object.
            >>> shaqra.load_layer('streets', 'streets.geojson') # load streets layer
            >>> shaqra.create_street_network("streets")  # Create a street network
            >>> shaqra.load_layer('homes', 'homes.geojson')
            >>> shaqra.insert_node('homes', label="origin", weight_attribute="residents")
            >>> shaqra.load_layer('schools', 'schools.geojson')
            >>> shaqra.insert_node('schools', label="destination", weight_attribute="school_enrollment")
            >>> shaqra.create_graph()
            # The zonal object now have everything it needs to be used as input in a UNA tool.
        """
        self.network.create_graph(light_graph, d_graph, od_graph)

    def describe(self):
        """
        prints a textual representation of the zonal objecgt, listing and describing layers

        Returns:
            None

        Example:
            >>> zshaqra = Zonal()
            >>> shaqra.describe()
            >>> shaqra.load_layer('homes', 'homes.geojson')
            >>> shaqra.describe()
            a string representation of the `Zonal` object, a list of layers if any exists. 
        """
        if len(self.layers.layers) == 0:
            print("No zonal_layers yet, load a layer using 'load_layer(layer_name, file_path)'")
        else:
            print(f"{'Layer name':20} | {'Visible':7} | {'projection':10} | {'rows':5} | {'File path':20}")
            for key in self.layers:
                print(
                    f"{key:20} | {self.layers[key].show:7} | {str(self.layers[key].gdf.crs):10} | {self.layers[key].gdf.shape[0]:5} | {self.layers[key].file_path:20}")
                # print(f"\tColumn names: {list(self.layers[key].gdf.columns)}")

        geo_center_x, geo_center_y = self.geo_center

        if self.geo_center is None:
            print(f"No center yet, add a layer or set a scope to define a center")
        else:
            print(f"Geographic center: ({geo_center_x}, {geo_center_y})")

        if self.network is None:
            print(
                f"No network graph yet. First, insert a layer that contains network segments (streets, sidewalks, ..) and call create_street_network(layer_name,  weight_attribute=None)")
            print(f"\tThen,  insert origins and destinations using 'insert_nodes(label, layer_name, weight_attribute)'")
            print(f"\tFinally, when done, create a network by calling 'create_street_network()'")

    def create_map(self, layer_list=None, save_as=None, basemap=False):
        """
        Create a map visualization using the specified layers within the `Zonal` object.

        Args:
            layer_list (list, optional): A list of dictionaries, each containing a 'gdf' key with a GeoDataFrame. 
            If None, the method includes all visible layers from the `Zonal` object.
            save_as (str, optional): The filename to save the map visualization. Default is None (not saved).
            basemap (bool, optional): Include a basemap in the map if True. Default is False.

        Returns:
            map: The generated Deck object representing the map visualization.

        Notes:
            - This method creates a map visualization based on the specified layers from the `Zonal` object.
            - You can provide a custom list of layers with GeoDataFrames, or the method includes all visible layers if `layer_list` is None.
            - If a filename is provided in `save_as`, the map will be saved as an interactive HTML file.
            - The map is centered around the geographic center of the Zonal object.
            - You can choose to include a basemap in the map by setting `basemap` to True.

        Example:
            >>> zonal = Zonal()  # Create a Zonal object.
            >>> zonal.load_layer("streets", "streets.geojson")  # load streets layer.
            >>> zonal.load_layer("homes", "homes.geojson")  # load homes layer.
            >>> zonal.create_map(layer_list=[{"gdf": zonal.layers["streets"].gdf}], save_as="map.html", basemap=True)
            # Create a map visualization with a custom layer and a basemap, and save it as an HTML file.

        """

        if layer_list is None:
            layer_list = []
            for layer_name in self.layers.layers:
                if self.layers[layer_name].show:
                    layer_gdf = self.layers[layer_name].gdf.copy(deep=True)
                    layer_gdf = self.color_gdf(layer_gdf, color=self.layers[layer_name].default_color)
                    layer_list.append({"gdf": layer_gdf})
        else:
            for layer_position, layer_dict in enumerate(layer_list):
                if "layer" in layer_dict:
                    # switch from ysung the keyword layer, into using the keyword 'gdf' by supplying layer's gdf
                    # TODO: here;s a good place to impose default stylings from layer attribute. the layer_dict overrides default layer styling.

                    # color by default layer, would be overriden if different parameters are given..
                    layer_gdf = self.layers[layer_dict["layer"]].gdf.copy(deep=True)
                    layer_dict['gdf'] = self.color_gdf(layer_gdf, color=self.layers[layer_dict["layer"]].default_color)
                    layer_list[layer_position] = layer_dict
        map = self.create_deckGL_map(
            gdf_list=layer_list,
            centerX=self.geo_center[0],
            centerY=self.geo_center[1],
            basemap=basemap,
            zoom=17,
            filename=save_as
        )
        return map

    def clear_nodes(self):
        node_gdf = self.network.nodes
        node_gdf = node_gdf[node_gdf["type"] == "street_node"]
        self.network.nodes = node_gdf
        return

    @staticmethod
    def create_deckGL_map(gdf_list=[], centerX=46.6725, centerY=24.7425, basemap=False, zoom=17, filename=None):
        start = time.time()
        pdk_layers = []
        for layer_number, gdf_dict in enumerate(gdf_list):
            local_gdf = gdf_dict["gdf"].copy(deep=True).reset_index()
            local_gdf["geometry"] = local_gdf["geometry"].to_crs("EPSG:4326")
            # print(f"{(time.time()-start)*1000:6.2f}ms\t {layer_number = }, gdf copied")
            start = time.time()

            radius_attribute = 1
            if "radius" in gdf_dict:
                radius_attribute = gdf_dict["radius"]
                local_gdf = local_gdf[~local_gdf[radius_attribute].isna()]
                r_series = local_gdf[radius_attribute]

                radius_min = gdf_dict["radius_min"] if "radius_min" in gdf_dict else 5
                radius_max = gdf_dict["radius_max"] if "radius_max" in gdf_dict else 10
                #r_series = radius_min + (r_series - r_series.mean()) / r_series.std() * radius_max
                r_series = radius_min + (r_series - r_series.min()) / (r_series.max()-r_series.min()) * (radius_max-radius_min)

                # r_series = r_series.apply(lambda x: (x - r_series.mean()) / r_series.std() if not np.isnan(x) else np.nan)

                # r_series = r_series.apply(lambda x: max(1,x) + 3 if not np.isnan(x) else np.nan)
                local_gdf['__radius__'] = r_series

            width_attribute = 1
            width_scale = 1
            if "width" in gdf_dict:
                width_attribute = gdf_dict["width"]
                if "width_scale" in gdf_dict:
                    width_scale = gdf_dict["width_scale"]
                local_gdf['__width__'] = local_gdf[width_attribute] * width_scale

            if "opacity" in gdf_dict:
                opacity = gdf_dict["opacity"]
            else:
                opacity = 1

            if ("color_by_attribute" in gdf_dict) or ("color_method" in gdf_dict) or ("color" in gdf_dict):
                args = {arg: gdf_dict[arg] for arg in ['color_by_attribute', 'color_method', 'color'] if
                        arg in gdf_dict}
                local_gdf = Zonal.color_gdf(local_gdf, **args)
                # print (local_gdf['color'])

            pdk_layer = pdk.Layer(
                'GeoJsonLayer',
                local_gdf.reset_index(),
                opacity=opacity,
                stroked=True,
                filled=True,
                wireframe=True,
                get_line_width='__width__',
                get_radius='__radius__',
                get_line_color='color',
                get_fill_color="color",
                pickable=True,
            )
            pdk_layers.append(pdk_layer)
            # print(f"{(time.time()-start)*1000:6.2f}ms\t {layer_number = }, pdk.Layer created.")
            start = time.time()

            if "text" in gdf_dict:
                # if numerical, round within four decimals, else, do nothing and treat as string
                try:
                    local_gdf["text"] = round(local_gdf[gdf_dict["text"]], 2).astype('string')
                except TypeError:
                    local_gdf["text"] = local_gdf[gdf_dict["text"]].astype('string')

                # formatting a centroid point to be [lat, long]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=UserWarning)
                    local_gdf["coordinates"] = local_gdf["geometry"].centroid
                local_gdf["coordinates"] = [[p.coords[0][0], p.coords[0][1]] for p in local_gdf["coordinates"]]

                layer = pdk.Layer(
                    "TextLayer",
                    local_gdf.reset_index(),
                    pickable=True,
                    get_position="coordinates",
                    get_text="text",
                    get_size=16,
                    get_color='color',
                    get_angle=0,
                    background=True,
                    get_background_color=[0, 0, 0, 125],
                    # Note that string constants in pydeck are explicitly passed as strings
                    # This distinguishes them from columns in a data set
                    get_text_anchor=String("middle"),
                    get_alignment_baseline=String("center"),
                )
                pdk_layers.append(layer)
                # print(f"{(time.time()-start)*1000:6.2f}ms\t {layer_number = }, text layer created and added.")
                start = time.time()

        initial_view_state = pdk.ViewState(
            latitude=centerY,
            longitude=centerX,
            zoom=zoom,
            max_zoom=20,
            pitch=0,
            bearing=0
        )

        if basemap:
            r = pdk.Deck(
                layers=pdk_layers,
                initial_view_state=initial_view_state,
            )
        else:
            r = pdk.Deck(
                layers=pdk_layers,
                initial_view_state=initial_view_state,
                map_provider=None,
                parameters={
                    "clearColor": [0.00, 0.00, 0.00, 1]
                },
            )

        if filename is not None:
            r.to_html(
                filename,
                css_background_color="cornflowerblue"
            )
        # print(f"{(time.time()-start)*1000:6.2f}ms\t {layer_number = }, map rendered.")
        start = time.time()
        return r

    def color_layer(self, layer_name, color_by_attribute=None, color_method="single_color", color=None):
        '''
        This function is used internally to apply default color settings for given layers
        '''
        if layer_name in self.DEFAULT_COLORS.keys() and color_by_attribute is None and color is None:
            # set default colors first. all default layers call without specifying "color_by_attribute"
            # default layer creation always calls self.color_layer(layer_name) without any other parameters
            color = self.DEFAULT_COLORS[layer_name].copy()
            color_method = "single_color"
            if type(color) is dict:
                # the default color is categorical..
                color_by_attribute = color["__attribute_name__"]
                color_method = "categorical"
        self.layers[layer_name]["gdf"] = self.color_gdf(
            self.layers[layer_name]["gdf"],
            color_by_attribute=color_by_attribute,
            color_method=color_method,
            color=color
        )
        return

    @staticmethod
    def color_gdf(gdf, color_by_attribute=None, color_method=None, color=None):
        """Sets geometry color

        :param gdf: GeoDataFrame to be colored.
        :param color_by_attribute: string, attribute name, or column name to visualize geometry by
        :param color_method: string, "single_color" to color all geometry by the same color.
        "categorical" to use distinct color to distinct value, "gradient": to use a gradient of colors for a numeric, scalar attribute.
        :param color: if color method is single color, expects one color. if categorical, expects nothing and would give automatic assignment, or a dict {"val': [0,0,0]}. if color_method is gradient, expects nothing for a default color map, or a color map name

        """
        if color_method is None:
            if color_by_attribute is not None:
                color_method = "categorical"
            else:
                color_method = "single_color"

        if color_by_attribute is None and color is None:
            # if "color_by_attribute" is not given, and its not a default layer, assuming color_method == "single_color"
            # if no color is given, assign random color, else, color=color
            color = [random.random() * 255, random.random() * 255, random.random() * 255]
            color_method = "single_color"
        elif color is None:
            # color by attribute ia given, but no color is given..
            if color_method == "single_color":
                # if color by attribute is given, and color method is single color, this is redundant but just in case:
                color = [random.random() * 255, random.random() * 255, random.random() * 255]
            if color_method == "categorical":
                color = {"__other__": [255, 255, 255]}
                for distinct_value in gdf[color_by_attribute].unique():
                    color[distinct_value] = [random.random() * 255, random.random() * 255, random.random() * 255]

        # create color column
        if color_method == "single_color":
            color_column = [color] * len(gdf)
        elif color_method == "categorical":
            # color = {"__other__": [255, 255, 255]}
            color_column = []
            for value in gdf[color_by_attribute]:
                if value in color.keys():
                    color_column.append(color[value])
                else:
                    color_column.append(color["__other__"])
        elif color_method == "gradient":
            cbc = gdf[color_by_attribute]  # color by column
            nc = 255 * (cbc - cbc.min()) / (cbc.max() - cbc.min())  # normalized column
            color_column = [[255 - v, 0 + v, 0] if not np.isnan(v) else [255, 255, 255] for v in
                            list(nc)]  # convert normalized values to color spectrom.
            # TODO: insert color map options here..
        elif color_method == 'quantile':
            scaled_percentile_rank = 255 * gdf[color_by_attribute].rank(pct=True)
            color_column = [[255.0 - v, 0.0 + v, 0] if not np.isnan(v) else [255, 255, 255] for v in
                            scaled_percentile_rank]  # convert normalized values to color spectrom.

        gdf["color"] = color_column
        return gdf
