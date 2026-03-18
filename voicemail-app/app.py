from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///voicemail.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ─── Models ───────────────────────────────────────────────────────────────────

class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created  = db.Column(db.DateTime, default=datetime.utcnow)

    sent_emails     = db.relationship('Email', foreign_keys='Email.sender_id',   backref='sender',   lazy=True)
    received_emails = db.relationship('Email', foreign_keys='Email.receiver_id', backref='receiver', lazy=True)

class Email(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject     = db.Column(db.String(200), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    is_read     = db.Column(db.Boolean, default=False)
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)

# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('inbox'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        password   = request.form['password']

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id']  = user.id
            session['username'] = user.username
            return redirect(url_for('inbox'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── Email Routes ─────────────────────────────────────────────────────────────

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/inbox')
@login_required
def inbox():
    emails = Email.query.filter_by(receiver_id=session['user_id'])\
                        .order_by(Email.timestamp.desc()).all()
    unread = sum(1 for e in emails if not e.is_read)
    return render_template('inbox.html', emails=emails, unread=unread)

@app.route('/sent')
@login_required
def sent():
    emails = Email.query.filter_by(sender_id=session['user_id'])\
                        .order_by(Email.timestamp.desc()).all()
    return render_template('sent.html', emails=emails)

@app.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    if request.method == 'POST':
        to_user  = request.form['to'].strip()
        subject  = request.form['subject'].strip()
        body     = request.form['body'].strip()

        receiver = User.query.filter(
            (User.username == to_user) | (User.email == to_user)
        ).first()

        if not receiver:
            flash('Recipient not found.', 'danger')
            return render_template('compose.html', to=to_user, subject=subject, body=body)

        email = Email(
            sender_id=session['user_id'],
            receiver_id=receiver.id,
            subject=subject,
            body=body
        )
        db.session.add(email)
        db.session.commit()
        flash('Email sent!', 'success')
        return redirect(url_for('sent'))
    return render_template('compose.html')

@app.route('/email/<int:email_id>')
@login_required
def view_email(email_id):
    email = Email.query.get_or_404(email_id)
    if email.receiver_id != session['user_id'] and email.sender_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('inbox'))
    if email.receiver_id == session['user_id'] and not email.is_read:
        email.is_read = True
        db.session.commit()
    return render_template('view_email.html', email=email)

@app.route('/delete/<int:email_id>', methods=['POST'])
@login_required
def delete_email(email_id):
    email = Email.query.get_or_404(email_id)
    if email.receiver_id != session['user_id'] and email.sender_id != session['user_id']:
        flash('Access denied.', 'danger')
    else:
        db.session.delete(email)
        db.session.commit()
        flash('Email deleted.', 'success')
    return redirect(url_for('inbox'))

@app.route('/users')
@login_required
def list_users():
    users = User.query.filter(User.id != session['user_id']).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])

# ─── WebRTC Signaling (Socket.IO) ─────────────────────────────────────────────

online_users = {}   # username → sid

@socketio.on('connect')
def on_connect():
    if 'username' in session:
        online_users[session['username']] = request.sid
        emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    user = session.get('username')
    if user and user in online_users:
        del online_users[user]
    emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('call_user')
def call_user(data):
    target = data.get('target')
    if target in online_users:
        emit('incoming_call', {
            'from': session['username'],
            'offer': data['offer']
        }, to=online_users[target])
    else:
        emit('call_failed', {'reason': 'User is offline'})

@socketio.on('call_answer')
def call_answer(data):
    target = data.get('target')
    if target in online_users:
        emit('call_answered', {
            'from': session['username'],
            'answer': data['answer']
        }, to=online_users[target])

@socketio.on('ice_candidate')
def ice_candidate(data):
    target = data.get('target')
    if target in online_users:
        emit('ice_candidate', {
            'from': session['username'],
            'candidate': data['candidate']
        }, to=online_users[target])

@socketio.on('end_call')
def end_call(data):
    target = data.get('target')
    if target in online_users:
        emit('call_ended', {'from': session['username']}, to=online_users[target])

@socketio.on('get_online_users')
def get_online_users():
    emit('online_users', list(online_users.keys()))

# ─── Entry Point ──────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
