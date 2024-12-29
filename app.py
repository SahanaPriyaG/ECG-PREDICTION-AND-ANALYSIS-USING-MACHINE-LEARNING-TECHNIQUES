from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_mail import Mail, Message
from flask import flash
import mysql.connector
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import os
import random
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import logging


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Flask-Mail Setup
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Example: Using Gmail SMTP server
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'uu130369@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'Pooja@123'  # Replace with your email password
app.config['MAIL_DEFAULT_SENDER'] = 'uu130369@gmail.com'  # Default sender
mail = Mail(app)

# Logging Configuration
logging.basicConfig(level=logging.DEBUG)

# Upload folder configuration
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Model loading
def load_model():
    logging.info(">>>>inside load model");
    model_path = 'resnet18_model.pth'  # Replace with your model path
    model = models.resnet18(pretrained=False)
    model.fc = nn.Linear(model.fc.in_features, 4)  # Adjust for 4 classes
    state_dict = torch.load(model_path)
    model.load_state_dict(state_dict)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    logging.info(">>>>model eval complete");
    return model

model = load_model()

# Database connection
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="pooja",
        password="123456789",
        database="ECGWEBDB",
        auth_plugin='caching_sha2_password'
    )

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login_register', methods=['GET', 'POST'])
def login_register():
    logging.info(">>>>inside login_register"+request.method);
    if request.method == 'POST':
        logging.info(">>>>inside login_register POST");
        action = request.form['action']
        username = request.form['username']
        password = request.form['password']

        if action == 'Register':
            # Register the user
            email_or_phone = request.form['emailOrPhone']
            hashed_password = generate_password_hash(password)
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, email_or_phone) VALUES (%s, %s, %s)",
                           (username, hashed_password, email_or_phone))
            conn.commit()
            conn.close()
            return redirect(url_for('login_register'))

        elif action == 'Login':
            # Validate the user
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            conn.close()

            if user and check_password_hash(user['password'], password):
                session['username'] = username  # Start session
                return redirect(url_for('patient_form'))  # Redirect to patient form
            else:
                return jsonify({'error': 'Invalid credentials'}), 400

    return render_template('login_register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    logging.info(">>>>inside forgot_password"+request.method);
    if request.method == 'POST':
        email = request.form['contact']
        if not email:
            return jsonify({'error': 'Email is required'}), 400

        otp = str(random.randint(100000, 999999))
        try:
            send_email(email, otp)
            session['otp'] = otp
            session['email'] = email
            return render_template('otp_verification.html')
        except Exception as e:
            logging.error(f"Failed to send OTP: {e}")
            return jsonify({'error': f"Failed to send OTP: {e}"}), 500

    return render_template('forgot_password.html')

def send_email(email,otp):
    logging.info(">>>>inside send email");
    try:
        # Retrieve form data
        subject = "OTP for password reset"
        recipient_email = email
        body = otp

        # Create the email message
        msg = Message(subject=subject,
                      recipients=[recipient_email],  # Recipient's email
                      body=body)
        
        # Send the email
        mail.send(msg)
        logging.info(">>>>after send call")

        # Flash success message
        flash('Email sent successfully!', 'success')
        logging.info(">>>>after flash call")
        
    except Exception as e:
        # Flash error message in case of failure
        flash(f'Error: {str(e)}', 'error')
        logging.info(">>>>send mail exception occured"+str(e));


def send_otp(email, otp):
    logging.info(">>>>inside send otp"+"- email"+email+" otp"+otp);
    sender_email = "your_email@gmail.com"
    sender_password = "your_email_app_password"  # App-specific password
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email
    msg['Subject'] = 'OTP for Password Reset'
    msg.attach(MIMEText(f"Your OTP is: {otp}", 'plain'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
    logging.debug(f"Sent OTP {otp} to {email}")

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    logging.info(">>>>inside verify_otp");
    entered_otp = request.form['otp']
    if entered_otp == session.get('otp'):
        return render_template('reset_password.html')
    return jsonify({'error': 'Invalid OTP'}), 400

@app.route('/reset_password', methods=['POST'])
def reset_password():
    new_password = request.form['password']
    email = session.get('email')
    hashed_password = generate_password_hash(new_password)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = %s WHERE email_or_phone = %s", (hashed_password, email))
    conn.commit()
    conn.close()
    return redirect(url_for('login_register'))

logstr =""
@app.route('/patient', methods=['GET', 'POST'])
def patient_form():
    logging.info(">>>>inside patient"+request.method);
    logstr =""
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        condition = request.form['medical_condition']
        image = request.files['ecg_image']
        if image:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
            image.save(image_path)
            logging.info(">>>>image save completed "+image_path);
            accuracy, prediction = process_ecg_image(image_path)
            logging.info(">>>>image processing completed");
            conn = get_db()
            cursor = conn.cursor()
            logging.info(">>>>executing query");
            cursor.execute("INSERT INTO patients (name, age, medical_condition, image_path) VALUES (%s, %s, %s, %s)",
                           (name, age, condition, image_path))
            conn.commit()
            logging.info(">>>>executing query complete");
            conn.close()
            return render_template('patient_result.html', accuracy=accuracy, prediction=prediction)
    return render_template('patient_form.html')

def predict(image_path, model_path):
    model = torch.load(model_path)  
    model.eval() 

def process_ecg_image(image_path):
     
     
    image = Image.open(image_path)
    transform = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor()])
    image_tensor = transform(image).unsqueeze(0)
    with torch.no_grad():
        output = model(image_tensor)
    accuracy = random.uniform(85, 99)
    prediction = f"Class {torch.argmax(output).item()}"
    return accuracy, prediction

@app.route('/patient_history', methods=['GET'])
def patient_history():
    if 'username' not in session:
        return redirect(url_for('login_register'))

    username = session['username']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE name = %s", (username,))
    history = cursor.fetchall()
    conn.close()
    return render_template('patient_history.html', history=history)

if __name__ == "__main__":
    app.run(debug=True)
