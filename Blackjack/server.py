import random
import socket
import threading
import time
import struct
import protocol

class BlackjackServer:
    def __init__(self):
        self.team_name = "Team "  
        self.tcp_port = 0  #0 is for random free port - changes later after os gives us one
        self.running = True

    def broadcast_offers(self):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        #creating the offer packet
        packet = struct.pack(
            protocol.FORMAT_OFFER,
            protocol.MAGIC_COOKIE,
            protocol.MSG_TYPE_OFFER,
            self.tcp_port,
            protocol.pad_string(self.team_name)
        )

        print(f"Server started, listening on IP address {self.get_local_ip()}")
        
        while self.running:
            try:
                #send broadcast with offer packet to anyone listening on the UDP port 13122
                udp_socket.sendto(packet, ('<broadcast>', protocol.UDP_PORT))
                time.sleep(1)  #broadcast every second
            except Exception as e:
                print(f"Broadcast error: {e}")

    def handle_client(self, client_sock, client_addr): #client thread
        print(f"New connection from {client_addr}")
        
        try:
            client_sock.settimeout(60)
            data = client_sock.recv(1024)
            #if data is wrong size
            if len(data) < 38:
                print("Invalid request size")
                return
            
            #unpack the request packet
            cookie, msg_type, rounds, team_name_bytes = struct.unpack(protocol.FORMAT_REQUEST, data[:38])
            
            if cookie != protocol.MAGIC_COOKIE or msg_type != protocol.MSG_TYPE_REQUEST:
                print("Invalid protocol message")
                return
            
            client_name = team_name_bytes.decode('utf-8').strip()
            print(f"Player {client_name} requested {rounds} rounds.")

            #Game Loop
            for i in range(int(rounds)):
                print(f"Round {i+1} starting with {client_name}")
                self.play_round(client_sock)
            print(f"Finished sending {rounds} rounds to {client_name}.")

        except Exception as e:
            print(f"Error handling client {client_addr}: {e}")
        finally:
            client_sock.close()
    
    def play_round(self, conn):
        deck = [(rank, suit) for rank in range(1, 14) for suit in range(4)]
        random.shuffle(deck)
        
        player_cards = []
        dealer_cards = []

        # Helper to send a card packet
        def send_card(rank, suit, result=protocol.RESULT_PLAYING):
            packet = struct.pack(
                protocol.FORMAT_PAYLOAD_SERVER, # !IBBHB
                protocol.MAGIC_COOKIE,
                protocol.MSG_TYPE_PAYLOAD,
                result,
                rank,
                suit
            )
            conn.sendall(packet)

        
        def calc_score(cards):
            total = 0
            aces = 0
            for r, s in cards:
                if r == 1: #ace (11)
                    total += 11
                    aces += 1
                elif r >= 11: #face
                    total += 10
                else:
                    total += r

            while total > 21 and aces > 0:#getting the highest score under 21 by converting aces from 11 to 1
                total -= 10
                aces -= 1
            return total

        # 2. Initial Deal [cite: 34]
        # Player Card 1
        c = deck.pop()
        player_cards.append(c)
        send_card(c[0], c[1])

        # Player Card 2
        c = deck.pop()
        player_cards.append(c)
        send_card(c[0], c[1])

        # Dealer Card 1 (Visible)
        c = deck.pop()
        dealer_cards.append(c)
        send_card(c[0], c[1])

        # Dealer Card 2 (Hidden) [cite: 39]
        hidden_card = deck.pop()
        dealer_cards.append(hidden_card)
        # We do NOT send this yet.

        # 3. Player Turn
        player_bust = False
        while True:
            # Receive decision
            try:
                data = conn.recv(1024)
                if len(data) < 10: continue 
                cookie, msg_type, decision_bytes = struct.unpack(protocol.FORMAT_PAYLOAD_CLIENT, data[:10])
                decision = decision_bytes.decode('utf-8').strip('\x00')
                
                if cookie != protocol.MAGIC_COOKIE:
                    print(f"Error: Invalid magic cookie: {hex(cookie)}")
                    continue
                
                if msg_type != protocol.MSG_TYPE_PAYLOAD:
                    print(f"Error: Invalid message type: {hex(msg_type)}")
                    continue

                if decision == "Hittt":
                    new_card = deck.pop()
                    player_cards.append(new_card)
                    
                    if calc_score(player_cards) > 21: 
                        send_card(new_card[0], new_card[1], protocol.RESULT_LOSS) #send new card with game end
                        player_bust = True
                        break
                    else:
                        send_card(new_card[0], new_card[1]) #send new card normally
                elif decision == "Stand": 
                    break

            except Exception as e:
                print(f"Connection error during player turn: {e}")
                return # Stop the round if connection dies
        
        #dealer loop
        winner = protocol.RESULT_TIE
        
        if player_bust:
            return #player already busted and got loss sent
        else:
            #send hidden dealer card now
            send_card(hidden_card[0], hidden_card[1])
            
            #delear hits until 17 or more
            while calc_score(dealer_cards) < 17:
                new_card = deck.pop()
                dealer_cards.append(new_card)
                send_card(new_card[0], new_card[1])
            
            d_score = calc_score(dealer_cards)
            p_score = calc_score(player_cards)

            if d_score > 21:
                winner = protocol.RESULT_WIN #dealer busts
            elif p_score > d_score:
                winner = protocol.RESULT_WIN #player > dealer
            elif d_score > p_score:
                winner = protocol.RESULT_LOSS #dealer > player
            else:
                winner = protocol.RESULT_TIE #tie

        #send winner result with no real card
        send_card(0, 0, winner)

    def start(self):
        #create tcp socket
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.bind(("", 0)) #get a free port from OS
        tcp_socket.listen()
        
        #store the assigned port
        self.tcp_port = tcp_socket.getsockname()[1]
        
        #brodcast thread over udp with offer packet
        broadcast_thread = threading.Thread(target=self.broadcast_offers, daemon=True)
        broadcast_thread.start()

        #main server loop to accept clients
        while self.running:
            try:
                client_sock, client_addr = tcp_socket.accept()
                
                #create a new thread for each client game
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_sock, client_addr), 
                    daemon=True
                )
                client_thread.start()
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"Server error: {e}")

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

if __name__ == "__main__":
    server = BlackjackServer()
    server.start()