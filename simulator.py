import simpy
from peer import *

EXPO_MEAN = 100
class Simulator:
    def __init__(self, args, graph, env=simpy.Environment(), name="htg", debug=False):
        self.env = env
        self.name = name
        self.simtime = args.simtime
        self.graph = graph
        self.args = args
        self.debug = debug
        self.delay = Delays(args.n, graph.fast_nodes)
        self.genesis_block = Block("0")
        self.peer_list = [Peer(i, EXPO_MEAN, args.n, env, self.delay, self.genesis_block) for i in range(args.n)]
        self.set_all_peer_list()
        self.set_all_fhp()

    def start_simulation(self):
        for elem in self.peer_list:
            self.env.process(elem.run())
        self.env.run(until=self.simtime)
        
    
    def set_all_peer_list(self):
        edge_list = self.graph.edgelist
        peer_dict = {k : [] for k in range(self.args.n)}
        for elem in edge_list:
            peer_dict[elem[0]].append(self.peer_list[elem[1]])
            peer_dict[elem[1]].append(self.peer_list[elem[0]])
        
        for elem in self.peer_list:
            elem.set_peer_list(list(set(peer_dict[elem.node])))
    
    def set_all_fhp(self):
        unit_hp = 1/(10*len(self.graph.highcpu_nodes) + len(self.graph.lowcpu_nodes))
        for elem in self.peer_list:
            if elem.node in self.graph.highcpu_nodes:
                elem.set_fraction_hashing_power(10*unit_hp)
            else:
                elem.set_fraction_hashing_power(unit_hp)
    
    def print_all_peer_output(self):
        for elem in self.peer_list:
            elem.print_tree(f"./peer_outputs/peer_{elem.node}.txt")
    

