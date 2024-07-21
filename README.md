# multithread-tower-defense

The following presents the documentation related to the implementation of the client for the Bridge Defense game. Developed as part of an academic project, the objective of this project was to create a client capable of interacting with servers using the UDP communication protocol, following the specifications provided by the project statement.

The Bridge Defense game is a simplified version of traditional Tower Defense games, where the player controls cannons positioned on bridges over parallel rivers. The challenge lies in the strategic coordination of cannon fire to sink enemy ships crossing the bridges.

Throughout this document, we will detail the implementation of the client, discussing the strategies adopted for communication with the servers, the game logic, and the techniques used to deal with issues such as message loss and retransmissions.

In addition, we will describe the challenges encountered during the implementation process, the solutions adopted, and important considerations for the efficiency and robustness of the client.

Finally, we will present an analysis of the client's performance at different game difficulties, highlighting the results obtained and the lessons learned throughout development.

## Code Overview

The code consists of a Python-implemented client for the Bridge Defense game, which uses the UDP protocol for communication with the game servers. The client is responsible for authenticating on the servers, obtaining information about the disposition of the cannons, advancing the game turns, and firing at enemy ships. The main functions used for this code implementation are defined below:

**Authentication (authenticate)**: The client starts by sending an authentication request (authreq) to the server, using an authentication key provided as a command line argument. The server responds with an authentication message (authresp) indicating whether the authentication was successful or not.

**Cannon Acquisition (place_cannons)**: After successful authentication, the client requests the server for information about the disposition of the cannons (getcannons). The server responds with the location of the player's cannons.

**Turn Advancement (pass_turn)**: The client advances the game turns, requesting the server for information about the enemy ships that are crossing the bridges. The server responds with the ships present on each bridge. The client then decides which ships to attack and sends shot messages (shot) to the server.

**Communication Error Handling**: The code implements a retransmission mechanism to deal with possible communication errors, such as message loss or timeout. If the client does not receive a response from the server within the defined time limit, it tries to retransmit the message.
Game Termination (quit): After the game is completed, the client sends a termination message (quit) to the server, ending the connection.

## Turn Management

During the turn change, we send a message of type getturn to each of the servers and receive the response to this request. We store the responses related to each bridge in a list. If the list is not complete (i.e., part of the response was lost), we resend the requests. With these responses, we first check if they are of the type gameover and, if so, we return the score, otherwise we use the ships field of each response and update the boats present on each of the bridges in our local data structures (not shared between threads), to match the server's response.

## Retransmission and Error Handling

The chosen retransmission strategy was with the use of try and except in Python, we try to send our encoded message and try to receive the server's response, if either method results in an error or a timeout, we will resend the message and wait again for the response. The number of retransmission attempts is defined by MAX_RETRIES, which was set as the maximum value of float.
When we need to receive a response from the server we check the type of the received response and if it does not match the expected type we enter a loop in which we receive everything that is in the reception queue for the socket we are using and then repeat the sending in order to wait for the correct response.

## Simultaneous Communication

To execute communication with multiple servers, we use multithreading from the threading library. We create a different thread to communicate with each server (each thread represents a river), and we perform communication simultaneously. Except for the choice of which cannon will shoot at which river (which could generate a race condition between different rivers), the other processes are performed in parallel by the different threads. In this scenario, all communications with the server are done in parallel.

At key parts of the program, we create a barrier so that all threads wait for the others. These parts are: after the creation and authentication of the servers, after requesting the positioning of the cannons, and at the beginning and end of the turns.

## Target Selection Strategy

For the choice of the target of each of the available cannons during a round we use our shoot function, in it we iterate over the bridges present in a river, on each of these bridges we see the cannons present and the boats that are passing through this bridge, the cannons
