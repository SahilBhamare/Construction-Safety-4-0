import os
import json
import hashlib
from dotenv import load_dotenv
import cv2
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from ultralytics import YOLO
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

# Load environment variables
load_dotenv(override=True)
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

CREDENTIALS_FILE = "users.json"

# ----------------------------
# Authentication System
# ----------------------------
class LoginPage:
    def __init__(self, master):
        self.master = master
        self.master.title("PPE Detection - Login")
        self.master.configure(bg="#f7f7f7")  # Light gray background

        # Center the window on the screen
        window_width = 400
        window_height = 300
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.master.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.create_widgets()
        self.load_credentials()

    def create_widgets(self):
        # Create a frame to hold the widgets
        frame = tk.Frame(self.master, bg="#ffffff", bd=2, relief="groove")  # White background with a border
        frame.place(relx=0.5, rely=0.5, anchor='center')  # Center the frame

        title_label = tk.Label(frame, text="PPE Detection System", font=("Arial", 20, "bold"), bg="#ffffff", fg="#333333")
        title_label.grid(row=0, column=0, columnspan=2, pady=(20, 10))  # Center title

        tk.Label(frame, text="Username:", bg="#ffffff", fg="#333333", font=("Arial", 14, "bold")).grid(row=1, column=0, sticky='e', padx=5, pady=5)  # Align to the right
        self.username_entry = tk.Entry(frame, width=30, font=("Arial", 14))
        self.username_entry.grid(row=1, column=1, padx=5, pady=5)  # Align to the left

        tk.Label(frame, text="Password:", bg="#ffffff", fg="#333333", font=("Arial", 14, "bold")).grid(row=2, column=0, sticky='e', padx=5, pady=5)  # Align to the right
        self.password_entry = tk.Entry(frame, show="*", width=30, font=("Arial", 14))
        self.password_entry.grid(row=2, column=1, padx=5, pady=5)  # Align to the left

        login_btn = tk.Button(frame, text="Login", command=self.authenticate, bg="#007BFF", fg="white", font=("Arial", 14, "bold"))
        login_btn.grid(row=3, column=0, columnspan=2, pady=(20, 10))  # Center button

    def load_credentials(self):
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                self.users = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.users = {"admin": self.hash_password("admin123")}

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self):
        username = self.username_entry.get()
        password = self.hash_password(self.password_entry.get())

        if not username or not password:
            messagebox.showerror("Error", "Please fill all fields")
            return

        if username in self.users and self.users[username] == password:
            self.master.destroy()
            root = tk.Tk()
            MainApplication(root)
            root.mainloop()
        else:
            messagebox.showerror("Error", "Invalid credentials")

# ----------------------------
# Email + Beep
# ----------------------------

def send_email_alert(image_path):
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL
    message["Subject"] = "Alert: Hardhat Missing!"

    body = "A person was detected without a hardhat for over 10 seconds."
    message.attach(MIMEText(body, "plain"))

    with open(image_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={image_path}")
        message.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        print("Email sent.")
    except Exception as e:
        print(f"Email failed: {e}")

def send_email_in_background(image_path):
    threading.Thread(target=send_email_alert, args=(image_path,)).start()

def play_beep():
    try:
        import winsound
        winsound.Beep(1000, 3000)
    except:
        for _ in range(3):
            print('\a')
            time.sleep(0.5)

def draw_text_with_background(frame, text, position, font_scale=0.5, color=(255, 255, 255), thickness=1, bg_color=(0, 0, 0), alpha=0.7, padding=5):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    x, y = position

    # Create a background rectangle
    cv2.rectangle(frame, (x - padding, y - padding), (x + text_size[0] + padding, y + text_size[1] + padding), bg_color, -1)
    
    # Put the text on the frame
    cv2.putText(frame, text, (x, y + text_size[1] + padding), font, font_scale, color, thickness)
# ----------------------------
# Main Application
# ----------------------------
# Add this after imports
CLASS_COLORS = {
    "Hardhat": (255, 0, 0),
    "Mask": (0, 255, 0),
    "NO-Hardhat": (0, 0, 255),
    "NO-Mask": (255, 255, 0),
    "NO-Safety Vest": (255, 0, 255),
    "Person": (0, 255, 255),
    "Safety Cone": (128, 0, 128),
    "Safety Vest": (128, 128, 0),
    "Machinery": (0, 128, 128),
    "Vehicle": (128, 128, 128)
}

class MainApplication:
    def __init__(self, master):
        self.master = master
        self.master.title("PPE Detection System")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.master.bind('<q>', lambda event: self.on_close())  # Press 'q' to quit

        self.model = YOLO("Model/ppe.pt")
        self.cap = cv2.VideoCapture(0)
        self.running = True

        self.last_email_time = time.time() - 11
        self.email_sent_flag = False
        self.email_sent_time = 0

        self.setup_gui()
        self.update_video()

    def setup_gui(self):
        # Create a canvas to display the video feed
        self.video_canvas = tk.Canvas(self.master, width=640, height=480, bg="black")
        self.video_canvas.place(relx=0.5, rely=0.5, anchor='center')  # Center the canvas

        self.status_label = tk.Label(self.master, text="System Status: Active", fg="green")
        self.status_label.pack(pady=10)

        stop_btn = tk.Button(self.master, text="Stop", command=self.on_close, bg="red", fg="white")
        stop_btn.pack(pady=10)

    def update_video(self):
        if self.running:
            ret, frame = self.cap.read()
            if ret:
                hardhat_detected = False
                person_detected = False
                hardhat_count = 0
                vest_count = 0
                person_count = 0

                results = self.model(frame)

                for result in results:
                    if result.boxes is not None:
                        for box in result.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            conf = box.conf[0]
                            cls = int(box.cls[0])
                            name = self.model.names[cls]
                            color = CLASS_COLORS.get(name, (255, 255, 255))  # fallback color
                            label = f"{name} ({conf:.2f})"

                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            draw_text_with_background(frame, label, (x1, y1 - 10), color=color)

                            if name == "Hardhat":
                                hardhat_detected = True
                                hardhat_count += 1
                            elif name == "Person":
                                person_detected = True
                                person_count += 1
                            elif name == "Safety Vest":
                                vest_count += 1

                if person_detected and not hardhat_detected and (time.time() - self.last_email_time) >= 10:
                    img_path = "no_hardhat.jpg"
                    cv2.imwrite(img_path, frame)
                    send_email_in_background(img_path)
                    threading.Thread(target=play_beep).start()
                    self.email_sent_flag = True
                    self.email_sent_time = time.time()
                    self.last_email_time = time.time()

                y = 30
                for line in [f"Hardhats: {hardhat_count}", f"Vests: {vest_count}", f"People: {person_count}"]:
                    draw_text_with_background(frame, line, (10, y))
                    y += 30

                if self.email_sent_flag and (time.time() - self.email_sent_time) < 3:
                    draw_text_with_background(frame, "Email Sent", (frame.shape[1] - 160, 30), color=(0, 255, 0))

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)

                self.video_canvas.create_image(0, 0, anchor='nw', image=imgtk)
                self.video_canvas.imgtk = imgtk  # Keep a reference to avoid garbage collection

            self.master.after(10, self.update_video)

    def on_close(self):
        self.running = False
        self.cap.release()
        cv2.destroyAllWindows()
        self.master.destroy()

# ----------------------------
# Start App
# ----------------------------

if __name__ == "__main__":
    if not os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump({"admin": hashlib.sha256("admin123".encode()).hexdigest()}, f)

    root = tk.Tk()
    LoginPage(root)
    root.mainloop()




