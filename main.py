import argparse
from graph import Graph
from simulator import Simulator
import peer
import igraph as ig

def fetch_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--z0", type=float, default=0.5)
    parser.add_argument("--z1", type=float, default=0.5) 
    parser.add_argument("--n", type=int, default=20) 
    parser.add_argument("--simtime", type=int, default=25000)
    
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = fetch_args()
    peer.TOTAL_NODES = args.n
    grph = Graph(args)
    g = grph.create_graph()
    g.write_svg("graph.svg")
    ig.plot(g, "graph.png")

    print("Fast Nodes", grph.fast_nodes)
    print("Slow Nodes", grph.slow_nodes)
    print("HighCPU Nodes", grph.highcpu_nodes)
    print("LowCPU Nodes", grph.lowcpu_nodes)

    sim = Simulator(args, grph)
    sim.start_simulation()
    sim.print_all_peer_output()
    sim.print_all_peer_graphs()

