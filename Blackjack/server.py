import socket
import threading
import time
import struct
import protocol

class BlackjackServer:
    def __init__(self):
        self.team_name = "Team "  # Replace with your cool team name
        self.tcp_port = 0  # 0 let's the OS pick a free port
        self.running = True

    def broadcast_offers(self):
        """
        Runs in a separate thread.
        Broadcasts UDP offers every 1 second so clients can find us.
        """
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Prepare the binary packet once (since the port doesn't change)
        # Packet format: Cookie (4B), Type 0x2 (1B), TCP Port (2B), Name (32B)
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
                # Send to the broadcast address on the specific UDP port (13122)
                udp_socket.sendto(packet, ('<broadcast>', protocol.UDP_PORT))
                time.sleep(1)  # Requirement: Send once every second
            except Exception as e:
                print(f"Broadcast error: {e}")

    def handle_client(self, client_sock, client_addr):
        """
        Runs in a separate thread for EACH client.
        Handles the entire game session (Request -> Game Loop -> Close).
        """
        print(f"New connection from {client_addr}")
        
        try:
            # 1. Receive Request Message (TCP)
            # We expect exactly 38 bytes: Cookie(4) + Type(1) + Rounds(1) + Name(32)
            data = client_sock.recv(1024)
            if len(data) < 38:
                print("Invalid request size")
                return
            
            # Unpack the request
            cookie, msg_type, rounds, team_name_bytes = struct.unpack(protocol.FORMAT_REQUEST, data[:38])
            
            if cookie != protocol.MAGIC_COOKIE or msg_type != protocol.MSG_TYPE_REQUEST:
                print("Invalid protocol message")
                return
            
            client_name = team_name_bytes.decode('utf-8').strip()
            print(f"Player {client_name} requested {rounds} rounds.")

            # 2. Game Loop
            # TODO: Implement the game logic here
            # for i in range(rounds):
            #     play_round(client_sock)
            
            # 3. Game Over
            print(f"Finished sending {rounds} rounds to {client_name}.")

        except Exception as e:
            print(f"Error handling client {client_addr}: {e}")
        finally:
            client_sock.close()

    def start(self):
        """
        Main entry point. Starts TCP listener and UDP broadcast thread.
        """
        # 1. Setup TCP Socket
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.bind(("", 0)) # Bind to wildcard IP and random free port
        tcp_socket.listen()
        
        # Retrieve the actual port the OS assigned us so we can put it in the UDP packet
        self.tcp_port = tcp_socket.getsockname()[1]
        
        # 2. Start UDP Broadcast in a background thread
        broadcast_thread = threading.Thread(target=self.broadcast_offers, daemon=True)
        broadcast_thread.start()

        # 3. Listen for incoming TCP connections
        while self.running:
            try:
                client_sock, client_addr = tcp_socket.accept()
                
                # Spawn a new thread for this client so we can keep accepting others
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
        """Helper to print the server's IP address."""
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