from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import os

from config import Config
from models import db, User, Board

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    db.create_all()
    
    # Create default admin user if no users exist
    if User.query.count() == 0:
        admin = User(username='admin', email='admin@kanban.local')
        admin.set_password('admin123')  # Change this!
        db.session.add(admin)
        db.session.commit()
        print("✓ Created default admin user (username: admin, password: admin123)")

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Check if max users reached
    if User.query.count() >= app.config['MAX_USERS']:
        flash('Maximum number of users reached. Contact administrator.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        
        # Create personal parking lot
        parking_lot = Board(
            name=f"{username}'s Parking Lot",
            description="Personal backlog and notes",
            owner_id=user.id,
            is_parking_lot=True
        )
        db.session.add(parking_lot)
        
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's boards (owned and shared)
    my_boards = Board.query.filter_by(owner_id=current_user.id, is_parking_lot=False, archived=False).all()
    shared_boards = [board for board in current_user.boards if board.owner_id != current_user.id and not board.archived]
    parking_lot = Board.query.filter_by(owner_id=current_user.id, is_parking_lot=True).first()
    
    return render_template('dashboard.html', 
                         my_boards=my_boards,
                         shared_boards=shared_boards,
                         parking_lot=parking_lot)

@app.route('/api/health')
def health():
    return {'status': 'ok', 'message': 'Kanban API is running'}

if __name__ == '__main__':
    port = app.config['PORT']
    app.run(host='0.0.0.0', port=port, debug=True)