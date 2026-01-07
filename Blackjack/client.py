import socket
import struct
import protocol

class BlackjackClient:
    def __init__(self):
        self.team_name = "Team Joker"
        self.udp_port = protocol.UDP_PORT
        self.buffer_size = 1024

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
                print("Invalid input. Please enter a number between 1 and 9.")
            
            packet = struct.pack(
                protocol.FORMAT_REQUEST,
                protocol.MAGIC_COOKIE,
                protocol.MSG_TYPE_REQUEST,
                int(rounds_input),
                protocol.pad_string(self.team_name)
            )
            
            tcp_socket.sendall(packet) 
            print(f"Sent request for {rounds_input} round(s). Waiting for game to start...")

            # Just for this test: Try to receive one thing (or just hang here)
            # In the real game, you'd enter a loop here to handle cards.
            data = tcp_socket.recv(1024)
            print(f"Server sent {len(data)} bytes back (Game loop would start here).")

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