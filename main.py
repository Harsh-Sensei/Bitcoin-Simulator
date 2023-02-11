import argparse
from graph import Graph
from simulator import Simulator

def fetch_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--z0", type=float, default=0.5)
    parser.add_argument("--z1", type=float, default=0.5) 
    parser.add_argument("--n", type=int, default=50) 
    parser.add_argument("--simtime", type=int, default=100)
    
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = fetch_args()
    grph = Graph(args)
    g = grph.create_graph()
    g.write_svg("graph.svg")

    Simulator(args).start_simulation()

