# chat_client.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import socket
import threading
import json
import base64
from datetime import datetime
from cryptography.fernet import Fernet
from PIL import Image, ImageTk
import io
import os

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Chat Application")
        self.root.geometry("900x700")
        self.root.configure(bg='#2c3e50')
        
        self.socket = None
        self.cipher = None
        self.username = None
        self.current_room = None
        self.unread_messages = 0
        
        # Emoji dictionary
        self.emojis = {
            ':)': '😊', ':(': '😢', ':D': '😃', ':P': '😛',
            '<3': '❤️', ':*': '😘', ';)': '😉', ':O': '😮',
            ':thumbsup:': '👍', ':fire:': '🔥', ':star:': '⭐',
            ':heart:': '❤️', ':laugh:': '😂', ':cool:': '😎'
        }
        
        self.show_login_screen()
        
    def show_login_screen(self):
        """Display login/registration screen"""
        self.clear_window()
        
        # Login Frame
        login_frame = tk.Frame(self.root, bg='#34495e', padx=40, pady=40)
        login_frame.place(relx=0.5, rely=0.5, anchor='center')
        
        # Title
        title = tk.Label(login_frame, text="💬 Chat Application", 
                        font=('Arial', 24, 'bold'), bg='#34495e', fg='white')
        title.grid(row=0, column=0, columnspan=2, pady=20)
        
        # Username
        tk.Label(login_frame, text="Username:", font=('Arial', 12), 
                bg='#34495e', fg='white').grid(row=1, column=0, sticky='w', pady=5)
        self.username_entry = tk.Entry(login_frame, font=('Arial', 12), width=25)
        self.username_entry.grid(row=1, column=1, pady=5)
        
        # Password
        tk.Label(login_frame, text="Password:", font=('Arial', 12), 
                bg='#34495e', fg='white').grid(row=2, column=0, sticky='w', pady=5)
        self.password_entry = tk.Entry(login_frame, font=('Arial', 12), 
                                      width=25, show='*')
        self.password_entry.grid(row=2, column=1, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(login_frame, bg='#34495e')
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        login_btn = tk.Button(btn_frame, text="Login", font=('Arial', 12, 'bold'),
                             bg='#27ae60', fg='white', padx=20, pady=5,
                             command=self.login)
        login_btn.pack(side='left', padx=5)
        
        register_btn = tk.Button(btn_frame, text="Register", font=('Arial', 12),
                                bg='#3498db', fg='white', padx=20, pady=5,
                                command=self.register)
        register_btn.pack(side='left', padx=5)
        
        # Bind Enter key
        self.password_entry.bind('<Return>', lambda e: self.login())
        
    def connect_to_server(self):
        """Connect to chat server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(('127.0.0.1', 5555))
            
            # Receive encryption key
            key = self.socket.recv(1024)
            self.cipher = Fernet(key)
            return True
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
            return False
    
    def send_data(self, data):
        """Send encrypted data to server"""
        encrypted = self.cipher.encrypt(json.dumps(data).encode())
        self.socket.send(encrypted)
    
    def receive_data(self):
        """Receive and decrypt data from server"""
        while True:
            try:
                encrypted_data = self.socket.recv(4096)
                if not encrypted_data:
                    break
                
                data = json.loads(self.cipher.decrypt(encrypted_data).decode())
                self.handle_server_response(data)
            except Exception as e:
                print(f"Error receiving data: {e}")
                break
    
    def handle_server_response(self, data):
        """Handle different server responses"""
        action = data.get('action')
        
        if action == 'register_response':
            if data['success']:
                messagebox.showinfo("Success", data['message'])
            else:
                messagebox.showerror("Error", data['message'])
        
        elif action == 'login_response':
            if data['success']:
                self.rooms = data['rooms']
                self.show_chat_screen()
            else:
                messagebox.showerror("Error", data['message'])
        
        elif action == 'room_joined':
            self.current_room = data['room']
            self.room_label.config(text=f"Room: {self.current_room}")
            self.chat_display.config(state='normal')
            self.chat_display.delete(1.0, tk.END)
            
            # Display history
            for msg in data['history']:
                self.display_message(msg[0], msg[1], msg[2], msg[3])
            
            self.chat_display.config(state='disabled')
            self.update_user_list(data['users'])
        
        elif action == 'new_message':
            self.display_message(data['username'], data['message'], 
                               data['timestamp'], data['type'])
            self.show_notification(data['username'], data['message'])
        
        elif action == 'new_file':
            self.display_file(data['username'], data['filename'], 
                            data['filedata'], data['timestamp'])
        
        elif action == 'user_joined':
            self.chat_display.config(state='normal')
            self.chat_display.insert(tk.END, f"\n[{data['username']} joined the room]\n", 'system')
            self.chat_display.config(state='disabled')
            self.update_user_list(data['users'])
        
        elif action == 'user_left':
            self.chat_display.config(state='normal')
            self.chat_display.insert(tk.END, f"\n[{data['username']} left the room]\n", 'system')
            self.chat_display.config(state='disabled')
            self.update_user_list(data['users'])
    
    def register(self):
        """Register new user"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please fill all fields!")
            return
        
        if not self.connect_to_server():
            return
        
        self.send_data({
            'action': 'register',
            'username': username,
            'password': password
        })
    
    def login(self):
        """Login user"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please fill all fields!")
            return
        
        if not self.connect_to_server():
            return
        
        self.username = username
        self.send_data({
            'action': 'login',
            'username': username,
            'password': password
        })
        
        # Start receiving thread
        receive_thread = threading.Thread(target=self.receive_data)
        receive_thread.daemon = True
        receive_thread.start()
    
    def show_chat_screen(self):
        """Display main chat interface"""
        self.clear_window()
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Top bar
        top_bar = tk.Frame(main_frame, bg='#34495e', height=60)
        top_bar.pack(fill='x', pady=(0, 5))
        
        self.room_label = tk.Label(top_bar, text="Select a room", 
                                   font=('Arial', 14, 'bold'), bg='#34495e', fg='white')
        self.room_label.pack(side='left', padx=15, pady=15)
        
        user_label = tk.Label(top_bar, text=f"👤 {self.username}", 
                             font=('Arial', 12), bg='#34495e', fg='white')
        user_label.pack(side='right', padx=15, pady=15)
        
        # Middle section
        middle_frame = tk.Frame(main_frame, bg='#2c3e50')
        middle_frame.pack(fill='both', expand=True)
        
        # Left sidebar - Rooms
        left_panel = tk.Frame(middle_frame, bg='#34495e', width=200)
        left_panel.pack(side='left', fill='y', padx=(0, 5))
        
        tk.Label(left_panel, text="Chat Rooms", font=('Arial', 12, 'bold'),
                bg='#34495e', fg='white').pack(pady=10)
        
        for room in self.rooms:
            btn = tk.Button(left_panel, text=f"# {room}", font=('Arial', 11),
                          bg='#2c3e50', fg='white', activebackground='#1abc9c',
                          width=18, pady=8, command=lambda r=room: self.join_room(r))
            btn.pack(pady=2, padx=10)
        
        # Center - Chat area
        center_panel = tk.Frame(middle_frame, bg='#ecf0f1')
        center_panel.pack(side='left', fill='both', expand=True)
        
        # Chat display
        self.chat_display = scrolledtext.ScrolledText(
            center_panel, wrap=tk.WORD, font=('Arial', 11),
            bg='#ecf0f1', fg='#2c3e50', state='disabled'
        )
        self.chat_display.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Configure tags
        self.chat_display.tag_config('username', foreground='#3498db', font=('Arial', 11, 'bold'))
        self.chat_display.tag_config('timestamp', foreground='#7f8c8d', font=('Arial', 9))
        self.chat_display.tag_config('system', foreground='#95a5a6', font=('Arial', 10, 'italic'))
        
        # Message input area
        input_frame = tk.Frame(center_panel, bg='#ecf0f1')
        input_frame.pack(fill='x', padx=5, pady=(0, 5))
        
        self.message_entry = tk.Text(input_frame, height=3, font=('Arial', 11),
                                     wrap=tk.WORD)
        self.message_entry.pack(side='left', fill='both', expand=True, padx=(0, 5))
        self.message_entry.bind('<Return>', self.send_message)
        
        # Buttons frame
        btn_frame = tk.Frame(input_frame, bg='#ecf0f1')
        btn_frame.pack(side='right', fill='y')
        
        send_btn = tk.Button(btn_frame, text="Send", font=('Arial', 10, 'bold'),
                           bg='#27ae60', fg='white', padx=15, pady=5,
                           command=self.send_message)
        send_btn.pack(pady=2)
        
        file_btn = tk.Button(btn_frame, text="📎 File", font=('Arial', 9),
                           bg='#3498db', fg='white', padx=15, pady=3,
                           command=self.send_file)
        file_btn.pack(pady=2)
        
        emoji_btn = tk.Button(btn_frame, text="😊", font=('Arial', 10),
                            bg='#f39c12', fg='white', padx=15, pady=3,
                            command=self.show_emoji_picker)
        emoji_btn.pack(pady=2)
        
        # Right sidebar - Users
        right_panel = tk.Frame(middle_frame, bg='#34495e', width=180)
        right_panel.pack(side='right', fill='y', padx=(5, 0))
        
        tk.Label(right_panel, text="Online Users", font=('Arial', 11, 'bold'),
                bg='#34495e', fg='white').pack(pady=10)
        
        self.user_listbox = tk.Listbox(right_panel, font=('Arial', 10),
                                       bg='#2c3e50', fg='white', 
                                       selectbackground='#1abc9c')
        self.user_listbox.pack(fill='both', expand=True, padx=10, pady=5)
    
    def join_room(self, room):
        """Join a chat room"""
        self.send_data({
            'action': 'join_room',
            'room': room
        })
    
    def send_message(self, event=None):
        """Send text message"""
        if event and event.keysym == 'Return' and event.state & 1:  # Shift+Enter
            return
        
        message = self.message_entry.get(1.0, tk.END).strip()
        
        if message and self.current_room:
            # Replace emoji codes
            for code, emoji in self.emojis.items():
                message = message.replace(code, emoji)
            
            self.send_data({
                'action': 'send_message',
                'room': self.current_room,
                'message': message,
                'type': 'text'
            })
            
            # Display own message
            self.display_message(self.username, message, 
                               datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text')
            
            self.message_entry.delete(1.0, tk.END)
        
        return 'break' if event else None
    
    def send_file(self):
        """Send file/image"""
        if not self.current_room:
            messagebox.showwarning("Warning", "Please join a room first!")
            return
        
        filename = filedialog.askopenfilename(
            title="Select file",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif"), 
                      ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'rb') as f:
                    filedata = base64.b64encode(f.read()).decode()
                
                basename = os.path.basename(filename)
                
                self.send_data({
                    'action': 'send_file',
                    'room': self.current_room,
                    'filename': basename,
                    'filedata': filedata
                })
                
                # Display own file
                self.display_file(self.username, basename, filedata,
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send file: {e}")
    
    def display_message(self, username, message, timestamp, msg_type):
        """Display message in chat"""
        self.chat_display.config(state='normal')
        
        # Timestamp
        self.chat_display.insert(tk.END, f"\n{timestamp} ", 'timestamp')
        
        # Username
        self.chat_display.insert(tk.END, f"{username}: ", 'username')
        
        # Message
        self.chat_display.insert(tk.END, f"{message}\n")
        
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')
    
    def display_file(self, username, filename, filedata, timestamp):
        """Display file in chat"""
        self.chat_display.config(state='normal')
        
        self.chat_display.insert(tk.END, f"\n{timestamp} ", 'timestamp')
        self.chat_display.insert(tk.END, f"{username}: ", 'username')
        self.chat_display.insert(tk.END, f"📎 {filename}\n")
        
        # Try to display image
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            try:
                image_data = base64.b64decode(filedata)
                image = Image.open(io.BytesIO(image_data))
                image.thumbnail((300, 300))
                photo = ImageTk.PhotoImage(image)
                
                self.chat_display.image_create(tk.END, image=photo)
                self.chat_display.image = photo  # Keep reference
                self.chat_display.insert(tk.END, "\n")
            except:
                pass
        
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')
    
    def show_emoji_picker(self):
        """Show emoji picker window"""
        emoji_window = tk.Toplevel(self.root)
        emoji_window.title("Emoji Picker")
        emoji_window.geometry("300x200")
        emoji_window.configure(bg='#34495e')
        
        emojis_list = ['😊', '😂', '😍', '😢', '😎', '🔥', '❤️', '👍', 
                      '👏', '🎉', '⭐', '💯', '🤔', '😴', '🤗', '😘']
        
        row, col = 0, 0
        for emoji in emojis_list:
            btn = tk.Button(emoji_window, text=emoji, font=('Arial', 20),
                          width=3, command=lambda e=emoji: self.insert_emoji(e, emoji_window))
            btn.grid(row=row, column=col, padx=5, pady=5)
            col += 1
            if col > 3:
                col = 0
                row += 1
    
    def insert_emoji(self, emoji, window):
        """Insert emoji into message"""
        self.message_entry.insert(tk.INSERT, emoji)
        window.destroy()
    
    def update_user_list(self, users):
        """Update online users list"""
        self.user_listbox.delete(0, tk.END)
        for user in users:
            self.user_listbox.insert(tk.END, f"👤 {user}")
    
    def show_notification(self, username, message):
        """Show notification for new message"""
        if not self.root.focus_get():
            self.unread_messages += 1
            self.root.title(f"Advanced Chat ({self.unread_messages} new)")
            self.root.bell()
        else:
            self.root.title("Advanced Chat Application")
            self.unread_messages = 0
    
    def clear_window(self):
        """Clear all widgets from window"""
        for widget in self.root.winfo_children():
            widget.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()