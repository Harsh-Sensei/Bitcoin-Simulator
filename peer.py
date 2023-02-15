### we have used simpy library to simulate the discrete-event simulator

import numpy as np
import random
import hashlib
import time
import simpy

# set the seed to use
np.random.seed(73)
random.seed(73)

# initialize all the parameters
LOW_RHO = 10     # Lower bound to propagration delay
HIGH_RHO = 500   # Upper bound to propagration delay
QUEUE_DELAY_FACTOR = 96  # queuing delay factor
MAX_BLOCK_SIZE = 1000  # maxiumum size of each block
MAX_COIN = 30    # maximum number of coins in a transaction
AVG_INTER_ARRIVAL = 2000   # average interarrival time for blocks
MAX_TRANSACTION = 2  # max number of transactions in a block
TOTAL_NODES = 20 # will be updated in main.py

# set to convert the hashes into unique ids
GLOBAL_BLOCK_HASHES = set()

# Class storing data of one transaction
class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.time = time.time()
        
    def __str__(self):
        return f"TxnID: ID {self.sender} pays ID {self.receiver} {self.amount:.4f} coins"

    # taking hash of the transaction string + timestamp to get the unique transaction id
    def get_id(self):
        return hashlib.sha256((str(self.__str__()) + str(self.time)).encode()).hexdigest()

# Class for simulating network delays
class Delays:
    def __init__(self, total_nodes, fast_nodes):
        # intialise the network delay paramters as given in doc
        self.rho = np.random.randint(LOW_RHO, HIGH_RHO, (total_nodes, total_nodes))

        # initialise all link speeds to 5 and later increase for fast pairs
        self.link_speed = np.ones(shape=(total_nodes, total_nodes))*5

        # get the pairs who have atleast one fast node
        self.fast_pair = [(i,j) for i in fast_nodes for j in fast_nodes]
        
        # set the fast links to have link speed 100
        for elem in self.fast_pair:
            self.link_speed[elem] = 100
        self.inv_link_speed = 1/self.link_speed

        #calculate the d mean factor
        self.d_mean = QUEUE_DELAY_FACTOR/self.link_speed

    # calculate and return the delay
    def get_delay(self, sender, receiver, data_size):
        return (self.rho[sender, receiver] + np.random.exponential(self.d_mean[sender, receiver]) 
        + data_size*self.inv_link_speed[sender, receiver])
    
# Class for storing block and validating transactions
class Block:
    def __init__(self, prev_hash, env, total_nodes=TOTAL_NODES):
        self.prev_hash = prev_hash # hash of the previous block
        self.block_size = 1
        self.block_txn_list = [] # maintain the transaction list of the block
        self.total_nodes = total_nodes
        self.amount_list = np.zeros(self.total_nodes) # maintain the coin balances of all nodes
        self.tm = env.now
        self.gen_by = None

    # function to add and process the incoming transaction in the block
    def add_txn(self, txn):
        if self.block_size <= MAX_BLOCK_SIZE:
            # deal with coinbase transactions
            if txn.sender is None:
                self.amount_list[txn.receiver] += txn.amount
                self.block_txn_list.append(txn)
                return True
            # discard invalid transactions
            if self.amount_list[txn.sender] < txn.amount:
                return False
            # deal with normal transactions
            self.amount_list[txn.sender] -= txn.amount
            self.amount_list[txn.receiver] += txn.amount
            self.block_txn_list.append(txn)
            self.block_size += 1
            return True
        else:
            return False

    # get the id of the block which is the hash of prevhash + txnlist + timestamp
    def get_id(self):
        return hashlib.sha256((str(self.prev_hash)+str(self.block_txn_list)+str(self.tm)).encode()).hexdigest()

    def set_gen_by(self, g):
        self.gen_by = g

# class to deal with all the functions of the peer
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
        # mining
        self.mining_process = self.env.process(self.mine())
        self.num_self_blocks = 1
        self.total_num_in_main = 1
        self.gen_block_hashes = []
        self.num_blks_mined = 1
        global GLOBAL_BLOCK_HASHES
        GLOBAL_BLOCK_HASHES.add(genesis_block.get_id())

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
            self.send_txn(self.node, txn)
    
    def set_peer_list(self, peer_list):
        self.peer_list = peer_list
        print(f"Node {self.node} has peer list {[elem.node for elem in self.peer_list]}")
    
    def set_fraction_hashing_power(self, h):
        self.fraction_hashing_power = h

    def receive_txn(self, sender, txn):
        self.id_to_txn_dict[txn.get_id()] = txn   
        print(f"Transaction {txn.get_id()} from {sender} received by {self.node}; amount = {txn}; time = {self.env.now};")
        self.send_txn(sender, txn)
        return

    def receive_blk(self, sender, blk):
        print(f"Block {blk.get_id()} from {sender} received by {self.node}; time = {self.env.now};")
        if blk.get_id() in self.hash_to_block_dict:
            return
        ### Verification of the block left
        tmp_amount_list = np.copy(self.amount_list)
        for txn in blk.block_txn_list:
            if txn.sender is None:
                tmp_amount_list[txn.receiver] += txn.amount
                continue
            else:
                tmp_amount_list[txn.sender] -= txn.amount
                tmp_amount_list[txn.receiver] += txn.amount
            
            if tmp_amount_list[txn.sender] < 0:
                print("Invalid transaction")
                return

        ### Fork resolution
        rewire = False
        if blk.prev_hash in self.hash_to_height_dict:
            height = self.hash_to_height_dict[blk.prev_hash] + 1
            if blk.prev_hash == self.chain_head:
                self.chain_head = blk.get_id()
                self.chain_height = height
                rewire = False
            if height > self.chain_height:
                rewire = True
            self.hash_to_height_dict[blk.get_id()] = height
            self.hash_to_block_dict[blk.get_id()] = blk
            self.hash_to_time_dict[blk.get_id()] = self.env.now
            self.blockchain_edgelist.append((blk.prev_hash, blk.get_id()))
        else:
            print("no parent")
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
            print("Resolving fork")
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
            
            curr_blk_id = blk.get_id()
            while curr_blk_id != parent_hash:
                curr_blk = self.hash_to_block_dict[curr_blk_id]
                for txn in curr_blk.block_txn_list:
                    if txn.sender is None:
                        self.amount_list[txn.receiver] += txn.amount
                        self.id_to_txn_dict.pop(txn.get_id(), None)
                        continue
                    self.amount_list[txn.sender] -= txn.amount
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                curr_blk_id = curr_blk.prev_hash

        ### Mining for new block
        print(f"Amount list for node {self.node} is {', '.join([f'{i}:{elem}' for i, elem in enumerate(self.amount_list)])}")
        self.mining_process.interrupt()
        self.send_block(sender, blk)
    
    def send_txn(self, exclude, txn):
        for peer in self.peer_list:
            if peer.node != exclude and (peer.node, txn.get_id()) not in self.sent_txns:
                self.env.process(self.send_txn_one(self.node, peer, txn))
                print("Sent transaction {} to {} by {}".format(txn.get_id(), peer.node, self.node))
                self.sent_txns.append((peer.node, txn.get_id()))
            else:
                print(f"Skipping txn {txn.get_id()} to node {peer.node} by {self.node}")
    
    def send_txn_one(self, s, r, txn):
        # print('Sending transaction')
        yield self.env.timeout(self.delay.get_delay(s, r.node, 1))
        r.receive_txn(s, txn)
        return

    def send_block(self, exclude, blk):
        for peer in self.peer_list:
            if peer.node != exclude and (peer.node, blk.get_id()) not in self.sent_blks:
                self.env.process(self.send_block_one(self.node, peer, blk))
                print("Sent block {} to {} by {}".format(blk.get_id(), peer.node, self.node))
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
            next_block = Block(self.chain_head, self.env)
            curr_num_txns = 0
            max_txn = random.randint(1, MAX_TRANSACTION)

            next_block.amount_list = self.amount_list.copy()
            for key, val in self.id_to_txn_dict.items():
                if curr_num_txns == max_txn:
                    break
                ret_val = next_block.add_txn(val)
                if ret_val:
                    curr_num_txns += 1
            next_block.add_txn(Transaction(None, self.node, 50))
            try:
                yield self.env.timeout(np.random.exponential(mean))
            except simpy.Interrupt:
                print("Interrupted")
                continue
            self.chain_head = next_block.get_id()
            self.chain_height += 1
            next_block.set_gen_by(self.node)
            
            self.hash_to_height_dict[next_block.get_id()] = self.chain_height
            self.hash_to_block_dict[next_block.get_id()] = next_block
            self.hash_to_time_dict[next_block.get_id()] = self.env.now
            
            self.gen_block_hashes.append(next_block.get_id())
            self.num_blks_mined += 1
            global GLOBAL_BLOCK_HASHES
            GLOBAL_BLOCK_HASHES.add(next_block.get_id())
            for txn in next_block.block_txn_list:
                if txn.sender is None:
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                    continue
                self.amount_list[txn.sender] -= txn.amount
                self.amount_list[txn.receiver] += txn.amount
                self.id_to_txn_dict.pop(txn.get_id(), None)
            self.blockchain_edgelist.append((next_block.prev_hash, next_block.get_id()))
            self.send_block(self.node, next_block)
            print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
            print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
    
    def set_number_blocks_in_main(self):
        curr_hash = self.chain_head
        while curr_hash != "0":
            if curr_hash in self.gen_block_hashes:
                self.num_self_blocks += 1
            curr_hash = self.hash_to_block_dict[curr_hash].prev_hash
            self.total_num_in_main += 1

    def print_tree(self, filename):
        self.set_number_blocks_in_main()
        with open(filename, 'w') as f:
            f.write("\n".join([f'"{str(elem[0])}({self.hash_to_time_dict[elem[0]]})" -> "{str(elem[1])}({self.hash_to_time_dict[elem[1]]})";' 
            for elem in self.blockchain_edgelist]))
            f.write("\n")
            f.write(f"{self.num_self_blocks}/{self.chain_height} blocks in main chain(={self.num_self_blocks/self.chain_height})\n")
            f.write(f"{self.num_self_blocks}/{self.num_blks_mined} (blks in main)/(total gen by this peer) (={self.num_self_blocks/self.num_blks_mined})\n")

    
    def graph_print(self, filename):
        hash_to_idx_dict = {}
        global GLOBAL_BLOCK_HASHES
        for i , (hash, _) in enumerate(self.hash_to_block_dict.items()):
            hash_to_idx_dict[hash] = list(GLOBAL_BLOCK_HASHES).index(hash)
        with open(filename, 'w') as f:
            f.write("digraph unix {\nsize=\"7,5\"; \n node [color=goldenrod2, style=filled];\n")
            f.write("\n".join([f'"{str(hash_to_idx_dict[elem[0]])}(Ta={self.hash_to_time_dict[elem[0]]:.3f};By: {self.hash_to_block_dict[elem[0]].gen_by})" -> "{str(hash_to_idx_dict[elem[1]])}(Ta={self.hash_to_time_dict[elem[1]]:.3f};By: {self.hash_to_block_dict[elem[1]].gen_by})";' 
            for elem in self.blockchain_edgelist]))
            f.write("\n}")
