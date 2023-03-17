from geopandas import GeoDataFrame
# street nodes, origin nodes, destination_nodes are the different types of nodes


class Network:
    """
    A road network with nodes `nodes` and edges `edges` weighted with factor `weight_attribute`,
    projected onto the `projected_crs` coordinate system.

    Internal class, meant to represent a network within the Zonal object.
    """

    def __init__(self, nodes: GeoDataFrame, edges: GeoDataFrame, projected_crs: str, weight_attribute=None):

        if not nodes:
            pass

        if not edges:
            pass

        self.nodes = nodes
        self.edges = edges
        self.crs = projected_crs
        self.weight_attribute = weight_attribute
        self.G = None  # G represents a networkx graph. To be deprecated
        return

    def insert_node(self, label: str, layer_name: str, weight: int):
        """
        Adds a node with label `label` to the layer `layer_name` with weight `weight`.
        Maps to insert_nodes_v2 in madina.py
        """
        raise NotImplementedError

    def set_node_value(self, idx, label, new_value):
        """
        Sets the node at (`idx`, `label`) value in the network to `new_value`.
        """
        self.nodes.at[idx, label] = new_value
        return

    def create_graph(self, light_graph: bool, dense_graph: bool, dest_graph: bool):
        """
        Creates
        `light_graph` - contains only network nodes and edges

        `dense_graph` - contains all origin and destination nodes

        `dest_graph` - contains all destination nodes

        Returns:
            A new graph (tentatively)
        """
        raise NotImplementedError

    def visualize_graph(self):
        """
        Creates an HTML map of the `zonal` object.
        """
        raise NotImplementedError

    def get_od_subgraph(self, origin_idx, distance):
        """
        Creates a subgraph of the city network `self` from all nodes <= `distance` from the node at `origin_idx`

        Returns:
            A smaller network graph (?)

        """
        raise NotImplementedError

    def turn_o_scope(self, origin_idx, search_radius, detour_ratio, turn_penalty=True,
                     origin_graph=None, return_paths=True):
        """
        Runs a modified Dijkstra algorithm from the `origin_idx`, with a `turn_penalty` for
        making a turn along the path. Bounds the search by `search_radius`

        Returns:
            A tuple of destination indices, origin scope, and paths from origin to destination

        """
        raise NotImplementedError

    def _get_nodes_at_distance(self, origin_node, distance, method='geometric'):
        """
        Gets all nodes at distance `distance` from the origin `origin_idx` using the method `method`.
        Approximation of functionality from ln 496-592 of b_f.py

        Returns:
            The distance first-class function to be used to find nodes
        """
        # TODO: Copy over remainder of distance methods. What does 'trail_blazer' mean?
        method_dict = {
            'geometric': self._get_nodes_at_geometric_distance,
            'network': self._get_nodes_at_network_distance,
            'trail_blazer': self._get_nodes_at_bf_distance

        }
        return method_dict[method](origin_node, distance)

    def _get_nodes_at_geometric_distance(self, origin_node, distance):
        raise NotImplementedError

    def _get_nodes_at_network_distance(self, origin_node, distance):
        raise NotImplementedError

    def _get_nodes_at_bf_distance(self, origin_node, distance):
        raise NotImplementedError

    def scan_for_intersections(self, node_snapping_tolerance=1):
        '''
        TODO: Fill out function spec
        '''
        raise NotImplementedError

    def fuse_degree_2_nodes(self, tolerance_angle):
        '''
        TODO: Fill out function spec
        '''
        raise NotImplementedError

    def network_to_layer(self):
        return {'gdf': self.nodes, 'show': True}, {'gdf': self.edges, 'show': True}


