### in this we use the python igraph library for creating the network topology of the nodes

import igraph as ig
import matplotlib.pyplot as plt
import random 

# initialize all the seeds and configs
MAX_TRY = 100
random.seed(73)

ig.config["plotting.backend"] = "matplotlib"
ig.config["plotting.layout"] = "fruchterman_reingold"
ig.config["plotting.palette"] = "rainbow"

# class to generate the network graph
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

    def create_graph(self, add_malicious=False, zeta=0):
        connected = False
        curr_try = 0
        valid = False
        # resolve self loops and ensure each node has 4 to 8 neighbours
        while not connected and curr_try < MAX_TRY and not valid:
            degree_list = [random.randint(5, 9) for _ in range(self.n)] # list of degrees of each node randomly initialized
            try:
                # use the ig function to generate a graph with the degree list
                self.graph = ig.GraphBase.Degree_Sequence(degree_list,method="simple")
                connected = self.graph.is_connected()
            except:
                # try again if the graph does not satisfy required properties
                curr_try += 1
                continue
            # To check if each node has 4 to 8 neighbours
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
        # save the edgelist of the graph to be used in our peer file
        self.edgelist = list(set([elem for elem in self.graph.get_edgelist() if elem[0]!=elem[1]]))
        #print(self.edgelist)
        # initialize slow and fast nodes and low and high CPU nodes randomly wrt the given parameters
        for i in range(self.n):
            if random.random() < self.z1:
                self.lowcpu_nodes.append(i)
            else:
                self.highcpu_nodes.append(i)

            if random.random() < self.z0:
                self.slow_nodes.append(i)
            else:
                self.fast_nodes.append(i)


        if add_malicious:
            self.fast_nodes.append(self.n)
            self.highcpu_nodes.append(self.n)
            neigh_m = random.sample(self.fast_nodes[:-1], zeta)
            print("Malicious neigh: ", neigh_m)
            for elem in neigh_m:
                self.edgelist.append([self.n, elem])

        # set all the parameters of the graph to display
        p_graph = ig.Graph(self.n + 1 if add_malicious else self.n, self.edgelist)
        p_graph.vs["label"] = range(self.n + 1 if add_malicious else self.n)
        p_graph.vs["color"] = "blue" if not add_malicious else ["blue" if i < self.n else "red" for i in range(self.n+1)]
        p_graph.vs["size"] = 0.6
        p_graph.es["color"] = "black"
        p_graph.es["width"] = 1

        return p_graph


class Dict2Class(object):
    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])

# if __name__ == "__main__":
#     test_args = {"z0": 0.5, "z1": 0.5, "n": 50}
#     test_args = Dict2Class(test_args)
#     graph = Graph(test_args)
#     out_graph = graph.create_graph()
#     #print(len(out_graph.get_edgelist()))
#     ig.plot(out_graph, "test")