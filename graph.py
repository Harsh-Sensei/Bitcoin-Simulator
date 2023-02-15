import igraph as ig
import matplotlib.pyplot as plt
import random 

MAX_TRY = 100
random.seed(73)

ig.config["plotting.backend"] = "matplotlib"
ig.config["plotting.layout"] = "fruchterman_reingold"
ig.config["plotting.palette"] = "rainbow"

class Graph:
    def __init__(self, args):
        self.z0 = args.z0
        self.z1 = args.z1
        self.n = args.n
        self.graph = None
        self.edgelist = []
        self.highcpu_nodes = []
        self.lowcpu_nodes = []
        self.slow_nodes= []
        self.fast_nodes = []

    def create_graph(self):
        connected = False
        curr_try = 0
        valid = False
        # resolve self loops 
        while not connected and curr_try < MAX_TRY and not valid:
            degree_list = [random.randint(5, 9) for _ in range(self.n)]
            try:
                self.graph = ig.GraphBase.Degree_Sequence(degree_list,method="simple")
                connected = self.graph.is_connected()
            except:
                curr_try += 1
                continue
            tmp_el = list(set([elem for elem in self.graph.get_edgelist() if elem[0]!=elem[1]]))
            tmp_dict = {i : [] for i in range(self.n)}
            for e in tmp_el:
                tmp_dict[e[0]].append(e[1])
            valid = True
            for elem, val in tmp_dict.items():
                if len(val)>8 or len(val)<4:
                    valid = False
                    break
            
        if curr_try >= MAX_TRY:
            raise Exception("Cannot generate graph in {MAX_TRY} tries")
        self.edgelist = list(set([elem for elem in self.graph.get_edgelist() if elem[0]!=elem[1]]))
        #print(self.edgelist)
        p_graph = ig.Graph(self.n, self.edgelist)
        p_graph.vs["label"] = range(self.n)
        p_graph.vs["color"] = "blue"
        p_graph.vs["size"] = 0.6
        p_graph.es["color"] = "black"
        p_graph.es["width"] = 1

        for i in range(self.n):
            if random.random() < self.z1:
                self.lowcpu_nodes.append(i)
            else:
                self.highcpu_nodes.append(i)

            if random.random() < self.z0:
                self.slow_nodes.append(i)
            else:
                self.fast_nodes.append(i)
        
        return p_graph


class Dict2Class(object):
    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])

if __name__ == "__main__":
    test_args = {"z0": 0.5, "z1": 0.5, "n": 50}
    test_args = Dict2Class(test_args)
    graph = Graph(test_args)
    out_graph = graph.create_graph()
    #print(len(out_graph.get_edgelist()))
    ig.plot(out_graph, "test")