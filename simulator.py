import simpy
from peer import *

# mean interarrival time of transactions
EXPO_MEAN = 500

# class to simulate the blockchain
class Simulator:
    def __init__(self, args, graph, env=simpy.Environment(), name="htg", debug=False, add_malicious=False, malicious_power=0.3):
        # initialize the simulator with the required parameters
        self.env = env
        self.name = name
        self.simtime = args.simtime
        self.graph = graph
        self.args = args
        self.debug = debug
        self.delay = Delays(args.n+1 if add_malicious else args.n, graph.fast_nodes)
        self.genesis_block = Block("0", self.env)
        self.add_malicious = add_malicious
        self.malicious_power = malicious_power
        # adjust the peer list for the malicious node
        self.peer_list = [Peer(i, EXPO_MEAN, args.n+1 if add_malicious else args.n, env, self.delay, self.genesis_block) for i in range(args.n)]
        # check for what type of malicious node to add
        if add_malicious:
            if MALICIOUS_TYPE == 0:
                self.peer_list.append(SelfishMiner(args.n, EXPO_MEAN, args.n+1, env, self.delay, self.genesis_block))
            elif MALICIOUS_TYPE == 1:
                self.peer_list.append(StubMiner(args.n, EXPO_MEAN, args.n+1, env, self.delay, self.genesis_block))

        self.set_all_peer_list()
        self.set_all_fhp()

    # call this function to start the simulation
    def start_simulation(self):
        for elem in self.peer_list:
            self.env.process(elem.run())
        self.env.run(until=self.simtime)
        
    #function to set neighbour edge list in graph
    def set_all_peer_list(self):
        edge_list = self.graph.edgelist
        peer_dict = {k : [] for k in range(self.args.n+1 if self.add_malicious else self.args.n)}
        
        # print(peer_dict)
        # print(self.add_malicious)
        for elem in edge_list:
            peer_dict[elem[0]].append(self.peer_list[elem[1]])
            peer_dict[elem[1]].append(self.peer_list[elem[0]])
        
        for elem in self.peer_list:
            elem.set_peer_list(list(set(peer_dict[elem.node])))
    
    # set the fractional hashing power of node depending on high or low CPU
    def set_all_fhp(self):
        unit_hp = (1-(self.malicious_power if self.add_malicious else 0))/(10*len(self.graph.highcpu_nodes) + len(self.graph.lowcpu_nodes))
        for elem in self.peer_list:
            if elem.node in self.graph.highcpu_nodes:
                elem.set_fraction_hashing_power(10*unit_hp)
            else:
                elem.set_fraction_hashing_power(unit_hp)
        if self.add_malicious:
            self.peer_list[-1].set_fraction_hashing_power(self.malicious_power)
    
    # print the output of all the peers
    def print_all_peer_output(self):
        for elem in self.peer_list:
            elem.print_tree(f"./peer_outputs/peer_{elem.node}.txt")
    
    # print the graph of all the peers
    def print_all_peer_graphs(self):
        for elem in self.peer_list:
            elem.graph_print(f"./peer_graphs/peer_{elem.node}.txt")
