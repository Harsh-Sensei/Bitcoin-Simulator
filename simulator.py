import simpy
from peer import *

class Simulator:
    def __init__(self, args, graph, env=simpy.Environment(), name="htg", simtime=10000, debug=False):
        self.env = env
        self.name = name
        self.simtime = simtime
        self.graph = graph
        self.args = args
        self.debug = debug
        self.delay = Delays(args.n, graph.fast_nodes)
        self.peer_list = [Peer(i, 5, args.n, env, self.delay) for i in range(args.n)]
        self.set_all_peer_list()

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
            elem.set_peer_list(peer_dict[elem.node])
            
