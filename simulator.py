import simpy
from peer import *

class Simulator:
    def __init__(self, args, env=simpy.Environment(), name="htg", simtime=100, debug=False):
        self.env = env
        self.name = name
        self.simtime = simtime
        self.debug = debug
        self.peer_list = [Peer(i, 5, args.n, env) for i in range(args.n)]
    
    def start_simulation(self):
        for elem in self.peer_list:
            self.env.process(elem.run())
        self.env.run(until=self.simtime)
    
