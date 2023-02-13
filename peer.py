import numpy as np
import random
import hashlib
import time
import simpy

np.random.seed(73)
random.seed(73)

LOW_RHO = 10
HIGH_RHO = 500
QUEUE_DELAY_FACTOR = 96
MAX_BLOCK_SIZE = 1000
MAX_COIN = 30
AVG_INTER_ARRIVAL = 10
MAX_TRANSACTION = 998

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
    def __init__(self, node, mean, total_nodes, env, delay, genesis_block):
        self.node = node
        self.mean = mean
        self.total_nodes = total_nodes
        self.env = env
        self.delay = delay
        self.fraction_hashing_power = None # to be set later in code
        self.txn_list = []
        self.all_txn_list = []
        self.peer_list = []
        self.sent_txns = []
        self.amount_list = np.zeros(total_nodes)
        self.id_to_txn_dict = {}
        self.sent_blks = []
        self.hash_to_block_dict = {genesis_block.get_id() : genesis_block}
        self.hash_to_time_dict = {genesis_block.get_id() : self.env.now}
        self.blockchain_edgelist = []
        self.hash_to_height_dict = {genesis_block.get_id() : 0}
        self.chain_head = genesis_block.get_id()
        self.chain_height = 0
        self.prev_mining_block_hash = None
        self.mining_process = self.env.process(self.mine())

    def run(self):
        while True:
            coins = random.random()*MAX_COIN
            receiver = self.node
            while receiver == self.node:
                receiver = random.randint(0, self.total_nodes-1)
            txn = Transaction(self.node, receiver, coins)
            self.txn_list.append(txn)
            self.id_to_txn_dict[txn.get_id()] = txn   
            yield self.env.timeout(np.random.exponential(self.mean))
            print(txn)
            yield self.env.process(self.send_txn(self.node, txn))
    
    def set_peer_list(self, peer_list):
        self.peer_list = peer_list
    
    def set_fraction_hashing_power(self, h):
        self.fraction_hashing_power = h

    def receive_txn(self, sender, txn):
        self.id_to_txn_dict[txn.get_id()] = txn   
        print(f"Transaction {txn.get_id()} from {sender} received by {self.node}")
        yield self.env.process(self.send_txn(sender, txn))

    def receive_blk(self, sender, blk):
        ### Verification of the block left
        for txn in blk.block_txn_list:
            if self.amount_list[txn.sender] < txn.amount:
                print("Invalid transaction")
                return

        ### Fork resolution
        rewire = False
        if blk.prev_hash in self.hash_to_height_dict:
            height = self.hash_to_height_dict[blk.prev_hash] + 1
            if height > self.chain_height:
                rewire = True
            self.hash_to_height_dict[blk.get_id()] = height
            self.hash_to_block_dict[blk.get_id()] = blk
            self.hash_to_time_dict[blk.get_id()] = self.env.now
            self.blockchain_edgelist.append((blk.prev_hash, blk.get_id()))
        else:
            return
        if not rewire:
            for txn in blk.block_txn_list:
                if txn.sender is None:
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                    continue
                self.amount_list[txn.sender] -= txn.amount
                self.amount_list[txn.receiver] += txn.amount
                self.id_to_txn_dict.pop(txn.get_id(), None)
        else:
            parent_hash = None
            curr_blk_id = self.chain_head
            hash1 = blk.prev_hash
            hash2 = self.chain_head
            self.chain_head = blk.get_id()
            self.chain_height = self.hash_to_height_dict[blk.get_id()]
            while parent_hash is None:
                if hash1 == hash2:
                    parent_hash = hash1
                else:
                    hash1 = self.hash_to_block_dict[hash1].prev_hash
                    hash2 = self.hash_to_block_dict[hash2].prev_hash
            
            lagging_hash = None
            while curr_blk_id != parent_hash:
                curr_blk = self.hash_to_block_dict[curr_blk_id]
                for txn in curr_blk.block_txn_list:
                    if txn.sender is None:
                        self.amount_list[txn.receiver] -= txn.amount
                        self.id_to_txn_dict[txn.get_id()] = txn
                        continue
                    self.amount_list[txn.sender] += txn.amount
                    self.amount_list[txn.receiver] -= txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                lagging_hash = curr_blk_id
                curr_blk_id = curr_blk.prev_hash

            while lagging_hash != blk.get_id():
                curr_blk = self.hash_to_block_dict[lagging_hash]
                for txn in curr_blk.block_txn_list:
                    if txn.sender is None:
                        self.amount_list[txn.receiver] += txn.amount
                        self.id_to_txn_dict.pop(txn.get_id(), None)
                        continue
                    self.amount_list[txn.sender] -= txn.amount
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                lagging_hash = curr_blk.prev_hash

        ### Mining for new block 
        self.mining_process.interrupt()
        yield self.env.process(self.send_block(sender, blk))
        print(f"Block {blk.get_id()} from {sender} received by {self.node}")
        yield self.env.process(self.send_blk(sender, txn))
    
    def send_txn(self, exclude, txn):
        for peer in self.peer_list:
            if peer.node != exclude and (peer.node, txn.get_id()) not in self.sent_txns:
                yield self.env.process(self.send_txn_one(self.node, peer, txn))
                self.sent_txns.append((peer.node, txn.get_id()))
            else:
                print(f"Skipping txn to node {peer.node} by {self.node}")
    
    def send_txn_one(self, s, r, txn):
        yield self.env.timeout(self.delay.get_delay(s, r.node, 1))
        print(f"Sent trasaction {txn.get_id()} to {r.node} by {s}")
        r.receive_txn(s, txn)

    def send_block(self, exclude, blk):
        for peer in self.peer_list:
            if peer.node != exclude and (peer.node, blk.get_id()) not in self.sent_blks:
                yield self.env.process(self.send_block_one(self.node, peer, blk))
                self.sent_blks.append((peer.node, blk.get_id()))
            else:
                print(f"Skipping block to node {peer.node} by {self.node}")
    
    def send_block_one(self, s, r, blk):
        yield self.env.timeout(self.delay.get_delay(s, r.node, blk.block_size))
        print(f"Sent block {blk.get_id()} to {r.node} by {s}")
        r.receive_blk(s, blk)

    def mine(self):
        mean = AVG_INTER_ARRIVAL/self.fraction_hashing_power
        while True:
            next_block = Block(self.chain_head)
            curr_num_txns = 0
            max_txn = random.randint(1, MAX_TRANSACTION)
            for key, val in self.id_to_txn_dict.items():
                if curr_num_txns == max_txn:
                    break
                next_block.add_txn(val)
                curr_num_txns += 1
            next_block.add_txn(Transaction(None, self.node, 50))
            try:
                yield self.env.timeout(np.random.exponential(mean))
            except simpy.Interrupt:
                print("Interrupted")
                continue
            self.chain_head = next_block.get_id()
            self.chain_height += 1

            for txn in next_block.block_txn_list:
                if txn.sender is None:
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                    continue
                self.amount_list[txn.sender] -= txn.amount
                self.amount_list[txn.receiver] += txn.amount
                self.id_to_txn_dict.pop(txn.get_id(), None)
            print(f"Block mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}")
            yield self.env.process(self.send_block(self.node, next_block))
        
