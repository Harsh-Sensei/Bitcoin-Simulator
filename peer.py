import numpy as np
import random
import hashlib
import time

np.random.seed(73)
random.seed(73)

LOW_RHO = 10
HIGH_RHO = 500
QUEUE_DELAY_FACTOR = 96
MAX_BLOCK_SIZE = 1000

class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.time = time.time()
        
    def __str__(self):
        return f"TxnID: ID {self.sender} pays ID {self.receiver} {self.amount:.4f} coins"

    def get_id(self):
        return hashlib.sha256((str(self.__str__()) + str(self.time)).encode()).hexdigest()

class Delays:
    def __init__(self, total_nodes, fast_nodes):
        self.rho = np.random.randint(LOW_RHO, HIGH_RHO, (total_nodes, total_nodes))
        self.link_speed = np.ones(shape=(total_nodes, total_nodes))*5
        self.fast_pair = [(i,j) for i in fast_nodes for j in fast_nodes]
        
        for elem in self.fast_pair:
            self.link_speed[elem] = 100
        self.inv_link_speed = 1/self.link_speed
        self.d_mean = QUEUE_DELAY_FACTOR/self.link_speed

    def get_delay(self, sender, receiver, data_size):
        return (self.rho[sender, receiver] + np.random.exponential(self.d_mean[sender, receiver]) 
        + data_size*self.inv_link_speed[sender, receiver])
    
class Block:
    def __init__(self, prev_hash):
        self.prev_hash = prev_hash
        self.block_size = 1
        self.block_txn_list = []

    
    def add_txn(self, txn):
        if self.block_size <= MAX_BLOCK_SIZE:
            self.block_txn_list.append(txn)
            self.block_size += 1
            return True
        else:
            return False
    
    def get_id(self):
        return hashlib.sha256((str(self.prev_hash)+str(self.block_txn_list)).encode()).hexdigest()

class Peer:
    def __init__(self, node, mean, total_nodes, env, delay):
        self.node = node
        self.mean = mean
        self.total_nodes = total_nodes
        self.env = env
        self.delay = delay
        self.txn_list = []
        self.all_txn_list = []
        self.peer_list = []
        self.amount_list = []
        self.sent_txns = []
        
    def run(self):
        while True:
            coins = random.random()*3
            txn = Transaction(self.node, np.random.randint(0, self.total_nodes), coins)
            self.txn_list.append(txn)
            self.all_txn_list.append(txn)   
            yield self.env.timeout(np.random.exponential(self.mean))
            print(txn)
            yield self.env.process(self.send_txn(self.node, txn))
    
    def set_peer_list(self, peer_list):
        self.peer_list = peer_list

    def receive_txn(self, sender, txn):
        self.all_txn_list.append(txn)
        print(f"Transaction {txn.get_id()} from {sender} received by {self.node}")
        yield self.env.process(self.send_txn(sender, txn))
    
    def send_txn(self, exclude, txn):
        for peer in self.peer_list:
            if peer.node != exclude and (peer.node, txn.get_id()) not in self.sent_txns:
                yield self.env.process(self.send_txn_one(self.node, peer, txn))
                self.sent_txns.append((peer.node, txn.get_id()))
            else:
                print(f"Skipping node {peer.node} by {self.node}")
    
    def send_txn_one(self, s, r, txn):
        yield self.env.timeout(self.delay.get_delay(s, r.node, 1))
        print(f"Sent trasaction {txn.get_id()} to {r.node} by {s}")
        r.receive_txn(s, txn)


