# CS 765 Project Part 1
# P2P CryptoCurrency Network Simulation
## Team Members: 
Harsh Shah - 200050049;  Shubham Bakare - 200050133;  Sahil Mahajan - 200050124; 

## Instructions for Compiling and Running 
1. Run the file main.py present in the root directory using the command : ```python3 main.py > output.txt```
2. This will generate a file output.txt in the root directory which contains the output of the simulation, a graph.png file containing the figure for the topology of the network and the blockchain trees of all the peers in the folder /peer_graphs and /peer_outputs. 
3. The outputs in /peer_graphs are of the form peer_{x}.txt containing the graph structure of the blockchain trees of node x and the outputs in /peer_outputs are of the form peer_{x}.txt containing the blockchain trees of node x in the form of hashes of the blocks along with timestamps.
4. The file main.py contains the parameters for the simulation which can be changed to run the simulation with different parameters, the default values for the parameters z0, z1, n are set in the main.py file but they can be changed by either passing them as command line arguments or by changing the values in the main.py file. [--z0 z0] [--z1 z1] [--n n] are the command line arguments for z0, z1 and n respectively.
5. We use xdot to visualise the graphs generated. Incase you wish to see the graphs, you can generate them by running the bash script using the command: ```./graph.sh```. The graphs will be generated in the /peer_graphs folder.
6. 
