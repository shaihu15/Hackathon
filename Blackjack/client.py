import socket
import struct
import protocol

class BlackjackClient:
    def __init__(self):
        self.team_name = "Team Joker"
        self.udp_port = protocol.UDP_PORT
        self.buffer_size = 1024

    def get_card_name(self, rank, suit):
        suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
        
        if rank == 1:
            rank_str = "Ace"
        elif rank == 11:
            rank_str = "Jack"
        elif rank == 12:
            rank_str = "Queen"
        elif rank == 13:
            rank_str = "King"
        elif rank == 0 and suit == 0:
            return "" #dummy for game end result
        else:
            rank_str = str(rank)
            
        try:
            return f"{rank_str} of {suits[suit]}"
        except IndexError:
            return f"Unknown Card ({rank}, {suit})"
        
    
    def recv_all(self, sock, length):
        data = b'' #empty bytes buffer
        while len(data) < length: #keep receiving until we have enough
            try:
                chunk = sock.recv(length - len(data)) #receive remaining bytes
                if not chunk: 
                    raise ConnectionError("Connection closed by server")#if no data received
                data += chunk
            except socket.error as e:
                raise ConnectionError(f"Socket error: {e}") #handle socket errors
        return data
    
    def parse_server_packet(self, sock):
        #calculate expected packet size
        packet_size = struct.calcsize(protocol.FORMAT_PAYLOAD_SERVER)
        data = self.recv_all(sock, packet_size)
        
        cookie, msg_type, result, rank, suit = struct.unpack(protocol.FORMAT_PAYLOAD_SERVER, data)
        
        if cookie != protocol.MAGIC_COOKIE:
            raise ValueError("Invalid Magic Cookie")
        if msg_type != protocol.MSG_TYPE_PAYLOAD:
            raise ValueError("Invalid Message Type")
            
        return result, rank, suit

    def find_server(self):
        print("Client started, listening for offer requests...")
        
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        #for reusing the port
        try:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            # SO_REUSEPORT might not be available on Windows; on Windows, SO_REUSEADDR usually works for this
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        udp_socket.bind(("", self.udp_port))

        while True:
            try:
                #recieve udp offer packet
                data, addr = udp_socket.recvfrom(self.buffer_size)
                server_ip = addr[0]

                #check proper len
                if len(data) < 39:
                    continue

                #unpack offer packet
                cookie, msg_type, server_port, server_name_bytes = struct.unpack(protocol.FORMAT_OFFER, data[:39])

                #validate cookie and type
                if cookie != protocol.MAGIC_COOKIE:
                    continue
                if msg_type != protocol.MSG_TYPE_OFFER:
                    continue

                server_name = server_name_bytes.decode('utf-8').strip('\x00') #remove pad
                print(f"Received offer from {server_name} at {server_ip}...")

                return server_ip, server_port

            except Exception as e:
                print(f"Error receiving UDP: {e}")

    def play_round(self, tcp_socket, round_num):
        print(f"\n--- Round {round_num} ---")
        
        player_cards = []
        dealer_cards = []
        # Player Card 1
        res, rank, suit = self.parse_server_packet(tcp_socket)
        c1 = self.get_card_name(rank, suit)
        player_cards.append(c1)
        print(f"Player got: {c1}")

        # Player Card 2
        res, rank, suit = self.parse_server_packet(tcp_socket)
        c2 = self.get_card_name(rank, suit)
        player_cards.append(c2)
        print(f"Player got: {c2}")

        # Dealer Card 1 (Visible)
        res, rank, suit = self.parse_server_packet(tcp_socket)
        d1 = self.get_card_name(rank, suit)
        dealer_cards.append(d1)
        print(f"Dealer showing: {d1}")
        
        # --- 2. Player Turn ---
        while True:
            # Ask user for move
            action = ""
            while action not in ["h", "s"]:
                user_input = input("Your move (h)it or (s)tand? ").strip().lower()
                if user_input in ["h", "s"]:
                    action = user_input
            
            if action == 'h':
                # Send Hit
                # Protocol requires "Hittt" (5 bytes) 
                payload = struct.pack(
                    protocol.FORMAT_PAYLOAD_CLIENT,
                    protocol.MAGIC_COOKIE,
                    protocol.MSG_TYPE_PAYLOAD,
                    b"Hittt" 
                )
                tcp_socket.sendall(payload)
                
                # Receive response card
                res, rank, suit = self.parse_server_packet(tcp_socket)
                card_name = self.get_card_name(rank, suit)
                print(f"Player got: {card_name}")
                
                if res != protocol.RESULT_PLAYING:
                    # If result is not playing, it means we busted or won immediately? 
                    # Usually means bust if we just hit.
                    self.handle_result(res)
                    return # Round over
                    
            elif action == 's':
                # Send Stand
                payload = struct.pack(
                    protocol.FORMAT_PAYLOAD_CLIENT,
                    protocol.MAGIC_COOKIE,
                    protocol.MSG_TYPE_PAYLOAD,
                    b"Stand"
                )
                tcp_socket.sendall(payload)
                break # Exit player loop, wait for dealer

        # --- 3. Dealer Turn ---
        # We now listen until the server sends a result that isn't PLAYING.
        # The server will send the hidden card, then any draw cards, then the final result.
        
        print("Dealer's turn...")
        while True:
            res, rank, suit = self.parse_server_packet(tcp_socket)
            
            # If rank is 0, it's likely just a status packet (Game Over), 
            # though the protocol definition technically has a card for every packet.
            if rank != 0:
                card_name = self.get_card_name(rank, suit)
                print(f"Dealer got: {card_name}")
            
            if res != protocol.RESULT_PLAYING:
                self.handle_result(res)
                return

    def handle_result(self, result):
        if result == protocol.RESULT_WIN:
            print(">>> YOU WON! <<<")
            self.wins += 1
        elif result == protocol.RESULT_LOSS:
            print(">>> YOU LOST! <<<")
            self.losses += 1
        elif result == protocol.RESULT_TIE:
            print(">>> IT'S A TIE! <<<")
            self.ties += 1
        else:
            print(f"Unknown result code: {result}")

    def connect_and_play(self, server_ip, server_port):
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            print(f"Connecting to server at {server_ip}:{server_port}...")
            tcp_socket.connect((server_ip, server_port))
            print("Connected successfully!")

            #get num of rounds from user. 255 is max for 1 Byte 
            while True:
                rounds_input = input("Enter number of rounds to play (1-255) and press Enter to continue: ")
                try:
                    rounds_num = int(rounds_input)
                    if 1 <= rounds_num <= 255:
                        break
                except ValueError:
                    continue
                print("Invalid input. Please enter a number between 1 and 255.")
            
            packet = struct.pack(
                protocol.FORMAT_REQUEST,
                protocol.MAGIC_COOKIE,
                protocol.MSG_TYPE_REQUEST,
                int(rounds_input),
                protocol.pad_string(self.team_name)
            )
            
            tcp_socket.sendall(packet) 
            print(f"Sent request for {rounds_input} round(s). Waiting for game to start...")

            for i in range(rounds_num):
                self.play_round(tcp_socket, i+1)

        except Exception as e:
            print(f"TCP Connection Error: {e}")
        finally:
            print("Closing connection.")
            tcp_socket.close()

    def start(self):
        # Main Logic
        server_ip, server_port = self.find_server()
        self.connect_and_play(server_ip, server_port)

if __name__ == "__main__":
    client = BlackjackClient()
    client.start()