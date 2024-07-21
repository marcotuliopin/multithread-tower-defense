import socket
import threading
import json
from sys import argv
from time import time

"""
Constant Definitions
"""
NUM_RIVERS = 4
NUM_BRIDGES = 8
NUM_CANNONS = NUM_BRIDGES * NUM_RIVERS
TIMEOUT = .3
MAX_RETRIES = float('inf')

barrier = threading.Barrier(NUM_RIVERS)
lock = threading.Lock()
flag = False
cannon_shot = [False] * NUM_CANNONS

def play(auth, server_adress):
    """
    Play the game with the given authentication and server address.

    Args:
        auth (str): The authentication string.
        server_address (tuple): The server address as a tuple of (host, port).
    Raises:
        AuthenticationFailedException: If authentication fails.
        CommunicationErrorException: If there is an error communicating with the server.
    """
    global flag
    global cannon_shot
    try:
        sock = create_socket(server_adress)
        barrier.wait()

        river, status = authenticate(sock, auth)
        if status:
            raise AuthenticationFailedException
        barrier.wait()

        cannons = place_cannons(sock, auth) 
        barrier.wait()

        turn = 0
        while True:
            ships, gameover, score = pass_turn(sock, auth, turn)
            if gameover:
                break
            barrier.wait()

            lock.acquire()
            if not flag:
                cannon_shot = [False for _ in range(NUM_CANNONS)]
            flag = True
            shots = shoot(river, ships, cannons)
            lock.release()

            for shot in shots:
                send_shot(shot[0], shot[1], auth, sock) 
            barrier.wait()

            turn += 1
            flag = False
        barrier.wait()

        if (river == 1):
            print(score)
            quit(sock, auth)
    finally:
        sock.close()

def create_socket(server_adress):
    """
    Create a socket and connect to the given server address.

    Args:
        server_address (tuple): The server address as a tuple of (host, port).
    Returns:
        socket.socket: The created socket object.
    Raises:
        socket.error: If there is an error creating or connecting the socket.
    """
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.connect(server_adress)
    except socket.error as e:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(server_adress)
    sock.settimeout(TIMEOUT)
    return sock

def authenticate(sock, auth):
    """
    Authenticate with the server using the given socket and authentication string.

    Args:
        sock (socket.socket): The socket object to use for communication.
        auth (str): The authentication string.
    Returns:
        tuple: A tuple of (river, status) where river is the player's river number and status is 0 if authentication succeeds, 1 otherwise.
    Raises:
        CommunicationErrorException: If there is an error communicating with the server.
    """
    data = {
        'type': 'authreq', 
        'auth': auth
    }

    retries = 0
    while retries <= MAX_RETRIES:
        try:
            send(sock, data)
            response = receive(sock)
            while response['type'] != 'authresp':
                response = receive(sock)
            break
        except (socket.error, socket.timeout) as e:
            retries += 1
        except InvalidMessageException as e:
            quit(sock, auth)

    if retries > MAX_RETRIES:
        raise CommunicationErrorException

    return response['river'], response['status'] 

def place_cannons(sock, auth):
    """
    Get the player's cannons from the server using the given socket and authentication string.

    Args:
        sock (socket.socket): The socket object to use for communication.
        auth (str): The authentication string.
    Returns:
        list: A list of dictionaries representing the player's cannons, where each dictionary has keys 'bridge' and 'river'.
    Raises:
        CommunicationErrorException: If there is an error communicating with the server.
    """
    data = {
        'type': 'getcannons', 
        'auth': auth
    }
    
    retries = 0
    while retries <= MAX_RETRIES:
        try:
            send(sock, data)
            response = receive(sock)
            while response['type'] != 'cannons':
                response = receive(sock)
            break
        except (socket.error, socket.timeout) as e:
            retries += 1
    if retries > MAX_RETRIES:
        raise CommunicationErrorException
    
    cannons = []
    for cannon in response['cannons']:
        cannons.append({
            'bridge': cannon[0],
            'river': cannon[1]
        })
    return cannons

def pass_turn(sock, auth, turn):
    """
    Pass the turn to the server using the given socket, authentication string, and turn number.

    Args:
        sock (socket.socket): The socket object to use for communication.
        auth (str): The authentication string.
        turn (int): The current turn number.
    Returns:
        tuple: A tuple of (ships, gameover, score) where ships is a dictionary of ships for each 
        bridge, gameover is True if the game is over, and score is the player's score if the game is over.
    Raises:
        CommunicationErrorException: If there is an error communicating with the server.
    """
    data = {
        'type' : 'getturn', 
        'auth': auth, 
        'turn': turn 
    }

    ships = {}
    retries = 0
    while retries <= MAX_RETRIES:
        try:
            responses = []
            send(sock, data)
            for _ in range(NUM_BRIDGES):
                response = receive(sock)
                if response['type'] == "gameover":
                    return {}, True, response['score']
                if response['type'] == 'state':
                    responses.append(response)
            if len(responses) == NUM_BRIDGES:
                for i in range(NUM_BRIDGES):
                    ships[responses[i]['bridge']] = responses[i]['ships']
                break
        except (socket.error, socket.timeout) as e:
            retries += 1
    return ships, False, None
        
def quit(sock, auth):
    """
    Quit the game by sending a message to the server using the given socket and authentication string.

    Args:
        sock (socket.socket): The socket object to use for communication.
        auth (str): The authentication string.
    Raises:
        CommunicationErrorException: If there is an error communicating with the server.
    """
    data = {
        'type' : 'quit', 
        'auth': auth
    }

    retries = 0
    while retries <= MAX_RETRIES:
        try:
            send(sock, data)
            place_cannons(sock, auth) 
        except (socket.error, socket.timeout) as e:
            retries += 1
        except InvalidMessageException as e:
            break 

def shoot(river, ships, cannons):
    """
    Shoot at enemy ships using the given river, ships, and cannons.

    Args:
        river (int): The player's river number.
        ships (dict): A dictionary of ships for each bridge.
        cannons (list): A list of dictionaries representing the player's cannons, where each dictionary has keys 'bridge' and 'river'.
    Returns:
        list: A list of tuples representing shots fired, where each tuple has the cannon and ship IDs.
    """
    global cannon_shot
    shots = []
    for bridge in ships:
        for i in range(len(cannons)):
            for ship in ships[bridge]:
                if not is_alive(ship):
                    continue
                if cannon_shot[i]:
                    continue
                if validate_shot(cannons[i], bridge, river):
                    cannon_shot[i] = True
                    ship['hits'] += 1
                    shots.append((cannons[i], ship['id']))
    return shots

def is_alive(ship):
    """
    Check if the given ship is still alive based on its hull type and number of hits.

    Args:
        ship (dict): A dictionary representing the ship, with keys 'id', 'hull', and 'hits'.
    Returns:
        bool: True if the ship is still alive, False otherwise.
    """
    match ship['hull']:
        case 'frigate':
            return ship['hits'] < 1
        case 'destroyer':
            return ship['hits'] < 2 
        case 'battleship':
            return ship['hits'] < 3 

def validate_shot(cannon, bridge, river):
    """
    Validate whether the given cannon can shoot at the given bridge and river.

    Args:
        cannon (dict): A dictionary representing the cannon, with keys 'bridge' and 'river'.
        bridge (int): The bridge number to shoot at.
        river (int): The river number to shoot at.
    Returns:
        bool: True if the cannon can shoot at the given bridge and river, False otherwise.
    """
    if cannon['bridge'] != bridge:
        return False
    if cannon['river'] != river:
        if cannon['river'] == 4:
            return False
        if cannon['river'] != river - 1:
            return False
    return True

def send_shot(cannon, ship, auth, sock):
    """
    Send a shot message to the server using the given cannon, ship ID, authentication string, and socket.

    Args:
        cannon (dict): A dictionary representing the cannon, with keys 'bridge' and 'river'.
        ship (int): The ID of the ship being targeted.
        auth (str): The authentication string.
        sock (socket.socket): The socket object to use for communication.
    Raises:
        CommunicationErrorException: If there is an error communicating with the server.
    """
    data = {
        'type': 'shot',
        'auth': auth,
        'cannon': (cannon['bridge'], cannon['river']), 
        'id': ship
    }

    retries = 0
    while retries <= MAX_RETRIES:
        try:
            send(sock, data)
            response = receive(sock)
            while response['type'] != 'shotresp':
                response = receive(sock)
            break
        except (socket.error, socket.timeout) as e:
            retries += 1

def send(sock, data):
    """
    Send a message to the server using the given socket and data.

    Args:
        sock (socket.socket): The socket object
    Raises:
        socket.error: If there is an error sending the message.
    """
    message = json.dumps(data).encode('utf-8')
    sock.sendall(message)

def receive(sock):
    """ Receive a message from the server using the given socket.

    Args:
        sock (socket.socket): The socket object to use for communication.
    Returns:
        dict: The received message data as a dictionary.
    Raises:
        CommunicationErrorException: If there is an error communicating with the server.
        InvalidMessageException: If the received message is invalid.
    """
    response = sock.recv(2048)
    response = json.loads(response)
    if response['type'] == 'gameover'and response['status'] == 1:
        raise InvalidMessageException(response['description'])
    return response

def main():

    _, host, port1, auth = argv

    port1 = int(port1) 
    ports = range(port1, port1 + NUM_RIVERS)
    adresses = [(host, port) for port in ports]

    threads = []
    for i in range(NUM_RIVERS):
        t = threading.Thread(target=play, args=(auth, adresses[i]))
        threads.append(t)
    
    try:
        for t in threads:
            t.start()    
    finally:
        for t in threads:
            t.join()

"""
Exceptions Definitions.
"""
class AuthenticationFailedException(Exception):
    pass

class CommunicationErrorException(Exception):
    pass

class InvalidMessageException(Exception):
    def __init__(self, message):
        super().__init__(message)

if __name__ == '__main__':
    start = time()
    main()
    minutes, seconds = divmod(int(time() - start), 60)
    print(f'Runtime: {minutes:02d}:{seconds:02d}')
