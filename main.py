DEBUG = True
if not DEBUG:
    print = lambda *x : x

# import all the required libraries
import argparse
from graph import Graph
from simulator import Simulator
import peer
import igraph as ig

# constants to initialise the malicious nodes
ZETA = 3 # number of malicious nodes' neighbours
ADD_MALICIOUS = True # add malicious nodes or not
MALICIOUS_POWER = 0.3

# function to get the input arguments 
def fetch_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--z0", type=float, default=0.5) 
    parser.add_argument("--z1", type=float, default=0.5) 
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--simtime", type=int, default=10000)
    
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    # initialize all the declared arguments
    args = fetch_args()
    peer.TOTAL_NODES = args.n

    # create the connected graph of the topology of the nodes
    grph = Graph(args)
    g = grph.create_graph(add_malicious=ADD_MALICIOUS, zeta=ZETA)
    g.write_svg("graph.svg")
    ig.plot(g, "graph.png")

    print("Fast Nodes", grph.fast_nodes)
    print("Slow Nodes", grph.slow_nodes)
    print("HighCPU Nodes", grph.highcpu_nodes)
    print("LowCPU Nodes", grph.lowcpu_nodes)

    # start the simulator and then print the output of all the peers
    sim = Simulator(args, grph, add_malicious=ADD_MALICIOUS, malicious_power=MALICIOUS_POWER)
    sim.start_simulation()
    sim.print_all_peer_output()
    sim.print_all_peer_graphs()

