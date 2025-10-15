# chat_server.py
import socket
import threading
import json
import sqlite3
import hashlib
import base64
import os
from datetime import datetime
from cryptography.fernet import Fernet

class ChatServer:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = {}  # {username: (socket, cipher)}
        self.rooms = {'General': [], 'Random': [], 'Tech': []}
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for users and messages"""
        self.conn = sqlite3.connect('chat_data.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Users table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Messages table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                room TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT DEFAULT 'text'
            )
        ''')
        
        self.conn.commit()
        
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password):
        """Register a new user"""
        try:
            hashed_pw = self.hash_password(password)
            self.cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                              (username, hashed_pw))
            self.conn.commit()
            return True, "Registration successful!"
        except sqlite3.IntegrityError:
            return False, "Username already exists!"
        except Exception as e:
            return False, f"Registration failed: {str(e)}"
    
    def authenticate_user(self, username, password):
        """Authenticate user login"""
        hashed_pw = self.hash_password(password)
        self.cursor.execute('SELECT * FROM users WHERE username=? AND password=?',
                          (username, hashed_pw))
        return self.cursor.execute('SELECT * FROM users WHERE username=? AND password=?',
                                  (username, hashed_pw)).fetchone() is not None
    
    def save_message(self, username, room, message, msg_type='text'):
        """Save message to database"""
        self.cursor.execute('''
            INSERT INTO messages (username, room, message, message_type) 
            VALUES (?, ?, ?, ?)
        ''', (username, room, message, msg_type))
        self.conn.commit()
    
    def get_message_history(self, room, limit=50):
        """Retrieve message history for a room"""
        self.cursor.execute('''
            SELECT username, message, timestamp, message_type 
            FROM messages 
            WHERE room=? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (room, limit))
        messages = self.cursor.fetchall()
        return list(reversed(messages))
    
    def broadcast(self, message, room, sender=None):
        """Broadcast message to all users in a room"""
        encrypted_msg = self.cipher.encrypt(json.dumps(message).encode())
        
        for username in self.rooms.get(room, []):
            if username != sender and username in self.clients:
                try:
                    client_socket = self.clients[username][0]
                    client_socket.send(encrypted_msg)
                except:
                    self.remove_client(username)
    
    def handle_client(self, client_socket, address):
        """Handle individual client connection"""
        username = None
        current_room = None
        
        try:
            # Send encryption key to client
            client_socket.send(self.encryption_key)
            
            while True:
                encrypted_data = client_socket.recv(4096)
                if not encrypted_data:
                    break
                
                data = json.loads(self.cipher.decrypt(encrypted_data).decode())
                action = data.get('action')
                
                if action == 'register':
                    success, msg = self.register_user(data['username'], data['password'])
                    response = {'action': 'register_response', 'success': success, 'message': msg}
                    client_socket.send(self.cipher.encrypt(json.dumps(response).encode()))
                
                elif action == 'login':
                    if self.authenticate_user(data['username'], data['password']):
                        username = data['username']
                        self.clients[username] = (client_socket, self.cipher)
                        response = {
                            'action': 'login_response', 
                            'success': True, 
                            'message': 'Login successful!',
                            'rooms': list(self.rooms.keys())
                        }
                        client_socket.send(self.cipher.encrypt(json.dumps(response).encode()))
                    else:
                        response = {'action': 'login_response', 'success': False, 
                                  'message': 'Invalid credentials!'}
                        client_socket.send(self.cipher.encrypt(json.dumps(response).encode()))
                
                elif action == 'join_room':
                    room = data['room']
                    if current_room:
                        self.rooms[current_room].remove(username)
                    
                    current_room = room
                    if room not in self.rooms:
                        self.rooms[room] = []
                    self.rooms[room].append(username)
                    
                    # Send message history
                    history = self.get_message_history(room)
                    response = {
                        'action': 'room_joined',
                        'room': room,
                        'history': history,
                        'users': self.rooms[room]
                    }
                    client_socket.send(self.cipher.encrypt(json.dumps(response).encode()))
                    
                    # Notify others
                    self.broadcast({
                        'action': 'user_joined',
                        'username': username,
                        'room': room,
                        'users': self.rooms[room]
                    }, room, username)
                
                elif action == 'send_message':
                    msg = data['message']
                    msg_type = data.get('type', 'text')
                    room = data['room']
                    
                    self.save_message(username, room, msg, msg_type)
                    
                    self.broadcast({
                        'action': 'new_message',
                        'username': username,
                        'message': msg,
                        'type': msg_type,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }, room, username)
                
                elif action == 'send_file':
                    room = data['room']
                    filename = data['filename']
                    filedata = data['filedata']
                    
                    self.save_message(username, room, f"[FILE:{filename}]", 'file')
                    
                    self.broadcast({
                        'action': 'new_file',
                        'username': username,
                        'filename': filename,
                        'filedata': filedata,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }, room, username)
        
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            if username:
                self.remove_client(username, current_room)
            client_socket.close()
    
    def remove_client(self, username, room=None):
        """Remove client from server"""
        if username in self.clients:
            del self.clients[username]
        
        if room and username in self.rooms.get(room, []):
            self.rooms[room].remove(username)
            self.broadcast({
                'action': 'user_left',
                'username': username,
                'users': self.rooms[room]
            }, room)
    
    def start(self):
        """Start the chat server"""
        self.server.bind((self.host, self.port))
        self.server.listen()
        print(f"Server started on {self.host}:{self.port}")
        
        while True:
            client_socket, address = self.server.accept()
            print(f"Connection from {address}")
            thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
            thread.daemon = True
            thread.start()

if __name__ == '__main__':
    server = ChatServer()
    server.start()