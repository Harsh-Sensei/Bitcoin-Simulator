### we have used simpy library to simulate the discrete-event simulator

import numpy as np
import random
import hashlib
import time
import simpy
import os

MALICIOUS_TYPE = 1 # 0 for selfish miner and 1 for stub miner 

# set the seed to use
np.random.seed(73)
random.seed(73)

# initialize all the parameters
LOW_RHO = 10     # Lower bound to propagration delay
HIGH_RHO = 500   # Upper bound to propagration delay
QUEUE_DELAY_FACTOR = 96  # queuing delay factor
MAX_BLOCK_SIZE = 1000  # maxiumum size of each block
MAX_COIN = 30    # maximum number of coins in a transaction
AVG_INTER_ARRIVAL = 500   # average interarrival time for blocks
MAX_TRANSACTION = 2  # max number of transactions in a block
TOTAL_NODES = None # will be updated in main.py

# set to convert the hashes into unique ids
GLOBAL_BLOCK_HASHES = set()
TOTAL_BLOCKS_MINED = 0

# Class storing data of one transaction
class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender    # sender id
        self.receiver = receiver # receiver id
        self.amount = amount   # amount of coins
        self.time = time.time() # time of transaction
        
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
        self.block_size = 1 # size of the block
        self.block_txn_list = [] # maintain the transaction list of the block
        self.total_nodes = total_nodes # total number of nodes in the network
        self.amount_list = np.zeros(self.total_nodes) # maintain the coin balances of all nodes
        self.tm = env.now # time of creation of the block
        self.gen_by = None # id of the node which generated the block

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

    # get the generation of the block
    def set_gen_by(self, g):
        self.gen_by = g

# class to deal with all the functions of the nodes
class Peer:
    def __init__(self, node, mean, total_nodes, env, delay, genesis_block):
        # initialise all the parameters and variables
        self.node = node # node id
        self.mean = mean # mean interarrival time of txn
        self.total_nodes = total_nodes # total number of nodes
        self.env = env # environment
        self.delay = delay # delay object
        self.fraction_hashing_power = None # to be set later in code 
        self.txn_list = [] # list of transactions in the node 
        self.all_txn_list = [] # list of all transactions in the node
        self.peer_list = [] # list of peers
        self.sent_txns = [] # list of sent transactions
        self.amount_list = np.zeros(total_nodes) # list of coin balances of all nodes
        self.id_to_txn_dict = {} # dictionary to map transaction id to transaction object
        self.sent_blks = [] # list of sent blocks
        self.hash_to_block_dict = {genesis_block.get_id() : genesis_block} # dictionary to map block hash to block object
        self.hash_to_time_dict = {genesis_block.get_id() : self.env.now} # dictionary to map block hash to time of generation
        self.blockchain_edgelist = [] # list of edges in the blockchain
        self.hash_to_height_dict = {genesis_block.get_id() : 0} # dictionary to map block hash to height
        self.chain_head = genesis_block.get_id() # hash of the chain head
        self.chain_height = 0 # height of the chain
        self.prev_mining_block_hash = None # hash of the block mined by the node in the previous round

        # start the mining process
        self.mining_process = self.env.process(self.mine())
        self.num_self_blocks = 1 # number of blocks mined by the node itself
        self.total_num_in_main = 1 # total number of blocks in the main chain
        self.gen_block_hashes = []
        self.num_blks_mined = 1 # number of blocks mined by the node
        global GLOBAL_BLOCK_HASHES # global set of block hashes
        GLOBAL_BLOCK_HASHES.add(genesis_block.get_id()) # add the genesis block hash to the global set

    # function to start the transaction generation process
    def run(self):
        while True:
            coins = random.random()*MAX_COIN # random amount of coins to be sent
            receiver = self.node
            # make sure that the receiver is not the sender
            while receiver == self.node:
                receiver = random.randint(0, self.total_nodes-1)
            txn = Transaction(self.node, receiver, coins) # create the transaction
            self.txn_list.append(txn)
            self.id_to_txn_dict[txn.get_id()] = txn   
            yield self.env.timeout(np.random.exponential(self.mean)) # wait for the next transaction
            print(txn)
            self.send_txn(self.node, txn) # send the transaction to the peers
    
    # function to set the peer list
    def set_peer_list(self, peer_list):
        self.peer_list = peer_list
        print(f"Node {self.node} has peer list {[elem.node for elem in self.peer_list]}")
    
    # function to set the fractional hashing power
    def set_fraction_hashing_power(self, h):
        self.fraction_hashing_power = h

    #function to receive the transactions from the sender
    def receive_txn(self, sender, txn):
        self.id_to_txn_dict[txn.get_id()] = txn   
        print(f"Transaction {txn.get_id()} from {sender} received by {self.node}; amount = {txn}; time = {self.env.now};")
        self.send_txn(sender, txn) # send the transaction to the peers
        return

    # function to receive the block and process all the transactions in the block
    def receive_blk(self, sender, blk):
        print(f"Block {blk.get_id()} from {sender} received by {self.node}; time = {self.env.now};")
        # if already received the block, return
        if blk.get_id() in self.hash_to_block_dict:
            return
        
        # process all the transaction in the block using a temporary amount list
        tmp_amount_list = np.copy(self.amount_list)
        for txn in blk.block_txn_list:
            if txn.sender is None:
                tmp_amount_list[txn.receiver] += txn.amount
                continue
            else:
                tmp_amount_list[txn.sender] -= txn.amount
                tmp_amount_list[txn.receiver] += txn.amount

        # if any of the transactions are invalid, return
        # for txn in blk.block_txn_list:
                if tmp_amount_list[txn.sender] < 0:
                    print("Invalid transaction")
                    return

        rewire = False # flag to check if the blockchain needs to be re-wired

        # if the parent of the block is in the blockchain, add the block to the blockchain
        if blk.prev_hash in self.hash_to_height_dict:
            height = self.hash_to_height_dict[blk.prev_hash] + 1 # calculate height of the block

            # if the parent is the chain head, it means block is getting added to the main chain, no rewire
            if blk.prev_hash == self.chain_head:
                self.chain_head = blk.get_id()
                self.chain_height = height
                rewire = False
            
            # if the parent is not the chain head, it means block is getting added to a side chain, rewire
            if height > self.chain_height:
                rewire = True

            # set the block attributes
            self.hash_to_height_dict[blk.get_id()] = height
            self.hash_to_block_dict[blk.get_id()] = blk
            self.hash_to_time_dict[blk.get_id()] = self.env.now
            self.blockchain_edgelist.append((blk.prev_hash, blk.get_id()))
        
        else:
            print("no parent")
            return
        
        # deal with block getting added to the main chain
        if not rewire:
            for txn in blk.block_txn_list:
                # adjust all the amounts with the transactions and remove the transaction from the transaction pool
                if txn.sender is None:
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                    continue
                self.amount_list[txn.sender] -= txn.amount
                self.amount_list[txn.receiver] += txn.amount
                self.id_to_txn_dict.pop(txn.get_id(), None)
        
        # fork resolution
        else:
            print("Resolving fork")
            parent_hash = None # hash of the block where fork was created 
            curr_blk_id = self.chain_head # current block id
            hash1 = blk.prev_hash # pointers to prev block while crawling up the chain
            hash2 = self.chain_head # pointers to current block while crawling up the chain
            self.chain_head = blk.get_id()
            self.chain_height = self.hash_to_height_dict[blk.get_id()]

            # crawl up the chain to find the block where fork was created
            while parent_hash is None:
                if hash1 == hash2:
                    parent_hash = hash1
                else:
                    hash1 = self.hash_to_block_dict[hash1].prev_hash
                    hash2 = self.hash_to_block_dict[hash2].prev_hash
            
            lagging_hash = None

            # now reverse all the main chain txns upto the forked block
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
            
            # and now add all the txns in the new sub chain that is part of the main chain 
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
    
    # function to send a transaction to all peers excluding the sender and previously sent transactions
    def send_txn(self, exclude, txn):
        for peer in self.peer_list:
            if peer.node != exclude and (peer.node, txn.get_id()) not in self.sent_txns:
                self.env.process(self.send_txn_one(self.node, peer, txn))
                print("Sent transaction {} to {} by {}".format(txn.get_id(), peer.node, self.node))
                self.sent_txns.append((peer.node, txn.get_id()))
            else:
                print(f"Skipping txn {txn.get_id()} to node {peer.node} by {self.node}")
    
    # subfunction to simulate the delay in sending a transaction
    def send_txn_one(self, s, r, txn):
        # print('Sending transaction')
        yield self.env.timeout(self.delay.get_delay(s, r.node, 1))
        r.receive_txn(s, txn)
        return

    # function to send a block to all peers excluding the sender and previously sent blocks
    def send_block(self, exclude, blk):
        for peer in self.peer_list:
            if peer.node != exclude and (peer.node, blk.get_id()) not in self.sent_blks:
                self.env.process(self.send_block_one(self.node, peer, blk))
                print("Sent block {} to {} by {}".format(blk.get_id(), peer.node, self.node))
                self.sent_blks.append((peer.node, blk.get_id()))
            else:
                print(f"Skipping block to node {peer.node} by {self.node}")
    
    # subfunction to simulate the delay in sending a block
    def send_block_one(self, s, r, blk):
        yield self.env.timeout(self.delay.get_delay(s, r.node, blk.block_size))
        print(f"Sent block {blk.get_id()} to {r.node} by {s}")
        r.receive_blk(s, blk)

    # function to simulate the mining process and the PoW
    def mine(self):
        global TOTAL_BLOCKS_MINED
        mean = AVG_INTER_ARRIVAL/self.fraction_hashing_power # mean of the exponential distribution for interarrival of blocks 
        
        while True:
            next_block = Block(self.chain_head, self.env)   # initialize a new block
            curr_num_txns = 0                              # number of txns in the block
            max_txn = random.randint(1, MAX_TRANSACTION)  # maximum number of txns in the block

            # copy the amount list to the new block
            next_block.amount_list = self.amount_list.copy()

            # add txns to the block from the pool of the node
            for key, val in self.id_to_txn_dict.items():
                if curr_num_txns == max_txn:
                    break
                ret_val = next_block.add_txn(val)
                if ret_val:
                    curr_num_txns += 1
            next_block.add_txn(Transaction(None, self.node, 50)) # add a coinbase txn to the block
            try:
                yield self.env.timeout(np.random.exponential(mean)) # wait for the next block to be mined (simulating PoW/Hashing)
            except simpy.Interrupt:
                print("Interrupted")
                continue
            self.chain_head = next_block.get_id() # update the chain head
            self.chain_height += 1 # update the chain height
            next_block.set_gen_by(self.node)
            
            # update the dictionaries
            self.hash_to_height_dict[next_block.get_id()] = self.chain_height
            self.hash_to_block_dict[next_block.get_id()] = next_block
            self.hash_to_time_dict[next_block.get_id()] = self.env.now
            
            self.gen_block_hashes.append(next_block.get_id()) # add the block to the list of blocks mined by the node
            self.num_blks_mined += 1 # update the number of blocks mined
            global GLOBAL_BLOCK_HASHES
            GLOBAL_BLOCK_HASHES.add(next_block.get_id())

            # update the amount list
            for txn in next_block.block_txn_list:
                if txn.sender is None:
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
                    continue
                self.amount_list[txn.sender] -= txn.amount
                self.amount_list[txn.receiver] += txn.amount
                self.id_to_txn_dict.pop(txn.get_id(), None)
            self.blockchain_edgelist.append((next_block.prev_hash, next_block.get_id())) # add the block to the blockchain edgelist
            self.send_block(self.node, next_block) # send the block to all peers
            TOTAL_BLOCKS_MINED += 1
            print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
            print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
    
    # helper function to get the number of blocks in the main chain and the blocks mined by the node itself (for analysis)
    def set_number_blocks_in_main(self):
        curr_hash = self.chain_head
        while curr_hash != "0":
            if curr_hash in self.gen_block_hashes:
                self.num_self_blocks += 1
            curr_hash = self.hash_to_block_dict[curr_hash].prev_hash
            self.total_num_in_main += 1

    # helper function to print the blockchain tree of the nodes into a file 
    def print_tree(self, filename):
        self.set_number_blocks_in_main()
        with open(filename, 'w') as f:
            f.write("\n".join([f'"{str(elem[0])}({self.hash_to_time_dict[elem[0]]})" -> "{str(elem[1])}({self.hash_to_time_dict[elem[1]]})";' 
            for elem in self.blockchain_edgelist]))
            f.write("\n")
            f.write(f"{self.num_self_blocks}/{(self.chain_height+1)} blocks in main chain(={self.num_self_blocks/(self.chain_height+1)})\n")
            f.write(f"{self.num_self_blocks}/{self.num_blks_mined} (blks in main)/(total gen by this peer) (={self.num_self_blocks/self.num_blks_mined})\n")

    # helper function to print the graph structure of the blockchain tree 
    def graph_print(self, filename):
        self.set_number_blocks_in_main()
        hash_to_idx_dict = {}
        global GLOBAL_BLOCK_HASHES
        for i , (hash, _) in enumerate(self.hash_to_block_dict.items()):
            hash_to_idx_dict[hash] = list(GLOBAL_BLOCK_HASHES).index(hash)
        with open(filename, 'w') as f:
            f.write("digraph unix {\nsize=\"7,5\"; \n node [color=goldenrod2, style=filled];\n")
            f.write("\n".join([f'"{str(hash_to_idx_dict[elem[0]])}(Ta={self.hash_to_time_dict[elem[0]]:.3f};By: {self.hash_to_block_dict[elem[0]].gen_by})" -> "{str(hash_to_idx_dict[elem[1]])}(Ta={self.hash_to_time_dict[elem[1]]:.3f};By: {self.hash_to_block_dict[elem[1]].gen_by})";' 
            for elem in self.blockchain_edgelist]))
            f.write("\n}")


class SelfishMiner(Peer):
    def __init__(self, node, mean, total_nodes, env, delay, genesis_block):
        super().__init__(node, mean, total_nodes, env, delay, genesis_block)
        self.private_block_chain = []
        self.chain_length_diff = 0
        self.private_chain_head = self.chain_head
        self.height_increased = False
        self.events = []

    def update_bookkeeping(self, next_block):
        self.hash_to_height_dict[next_block.get_id()] = self.chain_height
        self.hash_to_block_dict[next_block.get_id()] = next_block
        self.hash_to_time_dict[next_block.get_id()] = self.env.now
        # update the amount list
        for txn in next_block.block_txn_list:
            if txn.sender is None:
                self.amount_list[txn.receiver] += txn.amount
                self.id_to_txn_dict.pop(txn.get_id(), None)
                continue
            self.amount_list[txn.sender] -= txn.amount
            self.amount_list[txn.receiver] += txn.amount
            self.id_to_txn_dict.pop(txn.get_id(), None)
        self.blockchain_edgelist.append((next_block.prev_hash, next_block.get_id())) # add the block to the blockchain edgelist
    # function to simulate the selfish-mining process and the PoW
    def mine(self):
        global TOTAL_BLOCKS_MINED
        mean = AVG_INTER_ARRIVAL/self.fraction_hashing_power # mean of the exponential distribution for interarrival of blocks 
        while True:
            print("Malicious node mining")
            self.mark_malicious_event()
            if len(self.private_block_chain)>0:
                if self.height_increased:
                    if self.chain_length_diff == 1:
                        next_block = self.private_block_chain[0]
                        # update the dictionaries
                        self.update_bookkeeping(next_block=next_block)
                        self.send_block(self.node, next_block) # send the block to all peers'
                        print("Releasing private block:", self.chain_length_diff)
                        print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
                        print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
                        self.private_block_chain.pop(0)

                        next_block = self.private_block_chain[0]
                        # update the amount list
                        self.update_bookkeeping(next_block=next_block)
                        self.send_block(self.node, next_block) # send the block to all peers'
                        print("Releasing private block : ", self.chain_length_diff)
                        print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
                        print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
                        self.private_block_chain.pop(0)
                        
                        self.chain_length_diff -= 1
                        print("Decreasing chain length diff :", self.chain_length_diff)
                        assert len(self.private_block_chain) == 0, "Private block chain length is non-empty"
                    
                    else:
                        next_block = self.private_block_chain[0]
                        # update the amount list
                        self.update_bookkeeping(next_block=next_block)
                        self.send_block(self.node, next_block) # send the block to all peers'
                        print("Releasing private block : ", self.chain_length_diff)
                        print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
                        print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
                        self.private_block_chain.pop(0)

            self.height_increased = False

            assert self.chain_length_diff == len(self.private_block_chain), "Inconsistent chain length difference"

            next_block = Block(self.private_chain_head, self.env)   # initialize a new block
            curr_num_txns = 0                             # number of txns in the block
            max_txn = random.randint(1, MAX_TRANSACTION)  # maximum number of txns in the block

            # copy the amount list to the new block
            next_block.amount_list = self.amount_list.copy()

            # add txns to the block from the pool of the node
            for key, val in self.id_to_txn_dict.items():
                if curr_num_txns == max_txn:
                    break
                ret_val = next_block.add_txn(val)
                if ret_val:
                    curr_num_txns += 1
            next_block.add_txn(Transaction(None, self.node, 50)) # add a coinbase txn to the block
            try:
                yield self.env.timeout(np.random.exponential(mean)) # wait for the next block to be mined (simulating PoW/Hashing)
            except simpy.Interrupt:
                print("Malicious Interrupted")
                continue
            self.private_chain_head = next_block.get_id() # update the chain head
            next_block.set_gen_by(self.node)
            
            self.gen_block_hashes.append(next_block.get_id()) # add the block to the list of blocks mined by the node
            self.num_blks_mined += 1 # update the number of blocks mined
            global GLOBAL_BLOCK_HASHES
            GLOBAL_BLOCK_HASHES.add(next_block.get_id())
            
            self.private_block_chain.append(next_block)
            TOTAL_BLOCKS_MINED += 1
            print("Mined private block")
            self.chain_length_diff += 1

            print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
            print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
    
    def receive_blk(self, sender, blk):
        print(f"Block {blk.get_id()} from {sender} received by {self.node}; time = {self.env.now};")
        
        # if already received the block, return
        if blk.get_id() in self.hash_to_block_dict:
            return
        
        # process all the transaction in the block using a temporary amount list
        tmp_amount_list = np.copy(self.amount_list)
        for txn in blk.block_txn_list:
            if txn.sender is None:
                tmp_amount_list[txn.receiver] += txn.amount
                continue
            else:
                tmp_amount_list[txn.sender] -= txn.amount
                tmp_amount_list[txn.receiver] += txn.amount

        # if any of the transactions are invalid, return
        # for txn in blk.block_txn_list:
                if tmp_amount_list[txn.sender] < 0:
                    print("Invalid transaction")
                    return

        rewire = False # flag to check if the blockchain needs to be re-wired

        # if the parent of the block is in the blockchain, add the block to the blockchain
        if blk.prev_hash in self.hash_to_height_dict:
            height = self.hash_to_height_dict[blk.prev_hash] + 1 # calculate height of the block

            # if the parent is the chain head, it means block is getting added to the main chain, no rewire
            if blk.prev_hash == self.chain_head:
                self.chain_head = blk.get_id()
                self.chain_height = height
                rewire = False
                self.height_increased = True

            # if the parent is not the chain head, it means block is getting added to a side chain, rewire
            if height > self.chain_height:
                rewire = True
                self.height_increased = True

            # set the block attributes
            self.hash_to_height_dict[blk.get_id()] = height
            self.hash_to_block_dict[blk.get_id()] = blk
            self.hash_to_time_dict[blk.get_id()] = self.env.now
            self.blockchain_edgelist.append((blk.prev_hash, blk.get_id()))
        
        else:
            print("no parent")
            return
        
        # deal with block getting added to the main chain
        if not rewire:
            if len(self.private_block_chain) == 0:
                for txn in blk.block_txn_list:
                    # adjust all the amounts with the transactions and remove the transaction from the transaction pool
                    if txn.sender is None:
                        self.amount_list[txn.receiver] += txn.amount
                        self.id_to_txn_dict.pop(txn.get_id(), None)
                        continue
                    self.amount_list[txn.sender] -= txn.amount
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
        
        # fork resolution
        else:
            print("Resolving fork")
            parent_hash = None # hash of the block where fork was created 
            curr_blk_id = self.chain_head # current block id
            hash1 = blk.prev_hash # pointers to prev block while crawling up the chain
            hash2 = self.chain_head # pointers to current block while crawling up the chain
            self.chain_head = blk.get_id()
            self.chain_height = self.hash_to_height_dict[blk.get_id()]

            # crawl up the chain to find the block where fork was created
            while parent_hash is None:
                if hash1 == hash2:
                    parent_hash = hash1
                else:
                    hash1 = self.hash_to_block_dict[hash1].prev_hash
                    hash2 = self.hash_to_block_dict[hash2].prev_hash
            
            # now reverse all the main chain txns upto the forked block
            while curr_blk_id != parent_hash:
                curr_blk = self.hash_to_block_dict[curr_blk_id]
                if len(self.private_block_chain) == 0:
                    for txn in curr_blk.block_txn_list:
                        if txn.sender is None:
                            self.amount_list[txn.receiver] -= txn.amount
                            self.id_to_txn_dict[txn.get_id()] = txn
                            continue
                        self.amount_list[txn.sender] += txn.amount
                        self.amount_list[txn.receiver] -= txn.amount
                        self.id_to_txn_dict[txn.get_id()] = txn
                    curr_blk_id = curr_blk.prev_hash
            
            # and now add all the txns in the new sub chain that is part of the main chain 
            curr_blk_id = blk.get_id()
            while curr_blk_id != parent_hash:
                if len(self.private_block_chain) == 0:
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
        
        if self.height_increased:
            if self.chain_length_diff > 0:
                self.chain_length_diff -= 1
                print("Decreasing chain length diff :", self.chain_length_diff)
            else:
                self.private_chain_head = self.chain_head
        self.mining_process.interrupt()
    
    def find_mpu_adv(self):
        self.set_number_blocks_in_main()
        return self.total_num_in_main/self.num_blks_mined
    
    def find_mpu_overall(self):
        self.set_number_blocks_in_main()
        global TOTAL_BLOCKS_MINED
        return self.chain_height/TOTAL_BLOCKS_MINED

    def graph_private_chain(self, filename):
        self.set_number_blocks_in_main()
        hash_to_idx_dict = {}
        global GLOBAL_BLOCK_HASHES
        for i , (hash, _) in enumerate(self.hash_to_block_dict.items()):
            hash_to_idx_dict[hash] = list(GLOBAL_BLOCK_HASHES).index(hash)
        with open(filename, 'w') as f:
            f.write("digraph unix {\nsize=\"7,5\"; \n node [color=goldenrod2, style=filled];\n")
            f.write("\n".join([f'"{hash_to_idx_dict[self.private_block_chain[i]]}" -> "{hash_to_idx_dict[self.private_block_chain[i+1]]}";' 
            for i in range(len(self.private_block_chain)-1)]))
            f.write("\n}")

    def mark_malicious_event(self):
        self.set_number_blocks_in_main()
        path = "malicious_events/"
        isExist = os.path.exists(path)
        if not isExist:
            os.makedirs(path)
        time = str(self.env.now)
        filename = path+ "private_chain" + time
        self.graph_private_chain(filename)
        filename = path+ "global_chain" + time
        self.graph_print(filename)

class StubMiner(Peer):
    def __init__(self, node, mean, total_nodes, env, delay, genesis_block):
        super().__init__(node, mean, total_nodes, env, delay, genesis_block)
        self.private_block_chain = []
        self.chain_length_diff = 0
        self.private_chain_head = self.chain_head
        self.height_increased = False
        self.events = []

    def update_bookkeeping(self, next_block):
        self.hash_to_height_dict[next_block.get_id()] = self.chain_height
        self.hash_to_block_dict[next_block.get_id()] = next_block
        self.hash_to_time_dict[next_block.get_id()] = self.env.now
        # update the amount list
        for txn in next_block.block_txn_list:
            if txn.sender is None:
                self.amount_list[txn.receiver] += txn.amount
                self.id_to_txn_dict.pop(txn.get_id(), None)
                continue
            self.amount_list[txn.sender] -= txn.amount
            self.amount_list[txn.receiver] += txn.amount
            self.id_to_txn_dict.pop(txn.get_id(), None)
        self.blockchain_edgelist.append((next_block.prev_hash, next_block.get_id())) # add the block to the blockchain edgelist
    # function to simulate the selfish-mining process and the PoW
    def mine(self):
        global TOTAL_BLOCKS_MINED
        mean = AVG_INTER_ARRIVAL/self.fraction_hashing_power # mean of the exponential distribution for interarrival of blocks 
        while True:
            print("Malicious node mining")
            self.mark_malicious_event()
            if len(self.private_block_chain)>0:
                if self.height_increased:
                    next_block = self.private_block_chain[0]
                    self.update_bookkeeping(next_block=next_block)
                    self.send_block(self.node, next_block) # send the block to all peers'
                    print("Releasing private block : ", self.chain_length_diff)
                    print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
                    print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
                    self.private_block_chain.pop(0)

            self.height_increased = False

            assert self.chain_length_diff == len(self.private_block_chain), "Inconsistent chain length difference"

            next_block = Block(self.private_chain_head, self.env)   # initialize a new block
            curr_num_txns = 0                             # number of txns in the block
            max_txn = random.randint(1, MAX_TRANSACTION)  # maximum number of txns in the block

            # copy the amount list to the new block
            next_block.amount_list = self.amount_list.copy()

            # add txns to the block from the pool of the node
            for key, val in self.id_to_txn_dict.items():
                if curr_num_txns == max_txn:
                    break
                ret_val = next_block.add_txn(val)
                if ret_val:
                    curr_num_txns += 1
            next_block.add_txn(Transaction(None, self.node, 50)) # add a coinbase txn to the block
            try:
                yield self.env.timeout(np.random.exponential(mean)) # wait for the next block to be mined (simulating PoW/Hashing)
            except simpy.Interrupt:
                print("Malicious Interrupted")
                continue
            self.private_chain_head = next_block.get_id() # update the chain head
            next_block.set_gen_by(self.node)
            
            self.gen_block_hashes.append(next_block.get_id()) # add the block to the list of blocks mined by the node
            self.num_blks_mined += 1 # update the number of blocks mined
            global GLOBAL_BLOCK_HASHES
            GLOBAL_BLOCK_HASHES.add(next_block.get_id())
            
            self.private_block_chain.append(next_block)
            TOTAL_BLOCKS_MINED += 1
            print("Mined private block")
            self.chain_length_diff += 1

            print(f"Block {next_block.get_id()} mined by {self.node} with {len(next_block.block_txn_list)} transactions; money left  {self.amount_list[self.node]}; time {self.env.now}")
            print(f"Txns: {[str(elem) for elem in next_block.block_txn_list]}")
    
    def receive_blk(self, sender, blk):
        print(f"Block {blk.get_id()} from {sender} received by {self.node}; time = {self.env.now};")
        
        # if already received the block, return
        if blk.get_id() in self.hash_to_block_dict:
            return
        
        # process all the transaction in the block using a temporary amount list
        tmp_amount_list = np.copy(self.amount_list)
        for txn in blk.block_txn_list:
            if txn.sender is None:
                tmp_amount_list[txn.receiver] += txn.amount
                continue
            else:
                tmp_amount_list[txn.sender] -= txn.amount
                tmp_amount_list[txn.receiver] += txn.amount

        # if any of the transactions are invalid, return
        # for txn in blk.block_txn_list:
                if tmp_amount_list[txn.sender] < 0:
                    print("Invalid transaction")
                    return

        rewire = False # flag to check if the blockchain needs to be re-wired

        # if the parent of the block is in the blockchain, add the block to the blockchain
        if blk.prev_hash in self.hash_to_height_dict:
            height = self.hash_to_height_dict[blk.prev_hash] + 1 # calculate height of the block

            # if the parent is the chain head, it means block is getting added to the main chain, no rewire
            if blk.prev_hash == self.chain_head:
                self.chain_head = blk.get_id()
                self.chain_height = height
                rewire = False
                self.height_increased = True

            # if the parent is not the chain head, it means block is getting added to a side chain, rewire
            if height > self.chain_height:
                rewire = True
                self.height_increased = True

            # set the block attributes
            self.hash_to_height_dict[blk.get_id()] = height
            self.hash_to_block_dict[blk.get_id()] = blk
            self.hash_to_time_dict[blk.get_id()] = self.env.now
            self.blockchain_edgelist.append((blk.prev_hash, blk.get_id()))
        
        else:
            print("no parent")
            return
        
        # deal with block getting added to the main chain
        if not rewire:
            if len(self.private_block_chain) == 0:
                for txn in blk.block_txn_list:
                    # adjust all the amounts with the transactions and remove the transaction from the transaction pool
                    if txn.sender is None:
                        self.amount_list[txn.receiver] += txn.amount
                        self.id_to_txn_dict.pop(txn.get_id(), None)
                        continue
                    self.amount_list[txn.sender] -= txn.amount
                    self.amount_list[txn.receiver] += txn.amount
                    self.id_to_txn_dict.pop(txn.get_id(), None)
        
        # fork resolution
        else:
            print("Resolving fork")
            parent_hash = None # hash of the block where fork was created 
            curr_blk_id = self.chain_head # current block id
            hash1 = blk.prev_hash # pointers to prev block while crawling up the chain
            hash2 = self.chain_head # pointers to current block while crawling up the chain
            self.chain_head = blk.get_id()
            self.chain_height = self.hash_to_height_dict[blk.get_id()]

            # crawl up the chain to find the block where fork was created
            while parent_hash is None:
                if hash1 == hash2:
                    parent_hash = hash1
                else:
                    hash1 = self.hash_to_block_dict[hash1].prev_hash
                    hash2 = self.hash_to_block_dict[hash2].prev_hash
            
            # now reverse all the main chain txns upto the forked block
            while curr_blk_id != parent_hash:
                curr_blk = self.hash_to_block_dict[curr_blk_id]
                if len(self.private_block_chain) == 0:
                    for txn in curr_blk.block_txn_list:
                        if txn.sender is None:
                            self.amount_list[txn.receiver] -= txn.amount
                            self.id_to_txn_dict[txn.get_id()] = txn
                            continue
                        self.amount_list[txn.sender] += txn.amount
                        self.amount_list[txn.receiver] -= txn.amount
                        self.id_to_txn_dict[txn.get_id()] = txn
                    curr_blk_id = curr_blk.prev_hash
            
            # and now add all the txns in the new sub chain that is part of the main chain 
            curr_blk_id = blk.get_id()
            while curr_blk_id != parent_hash:
                if len(self.private_block_chain) == 0:
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
        
        if self.height_increased:
            if self.chain_length_diff > 0:
                self.chain_length_diff -= 1
                print("Decreasing chain length diff :", self.chain_length_diff)
            else:
                self.private_chain_head = self.chain_head
        self.mining_process.interrupt()
    
    def find_mpu_adv(self):
        self.set_number_blocks_in_main()
        return self.total_num_in_main/self.num_blks_mined
    
    def find_mpu_overall(self):
        global TOTAL_BLOCKS_MINED
        return self.chain_height/TOTAL_BLOCKS_MINED

    def graph_private_chain(self, filename):
        hash_to_idx_dict = {}
        global GLOBAL_BLOCK_HASHES
        for i , (hash, _) in enumerate(self.hash_to_block_dict.items()):
            hash_to_idx_dict[hash] = list(GLOBAL_BLOCK_HASHES).index(hash)
        with open(filename, 'w') as f:
            f.write("digraph unix {\nsize=\"7,5\"; \n node [color=goldenrod2, style=filled];\n")
            f.write("\n".join([f'"{hash_to_idx_dict[self.private_block_chain[i]]}" -> "{hash_to_idx_dict[self.private_block_chain[i+1]]}";' 
            for i in range(len(self.private_block_chain)-1)]))
            f.write("\n}")

    def mark_malicious_event(self):
        path = "malicious_events/"
        isExist = os.path.exists(path)
        if not isExist:
            os.makedirs(path)
        filename = path+str(self.env.now)
        self.graph_print(filename)
