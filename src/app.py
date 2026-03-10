from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta, timezone

from config import Config
from models import db, User, Board, Card, ActivityLog, ChecklistItem, Comment, board_members

app = Flask(__name__,
            static_folder='static',
            template_folder='templates')
app.config.from_object(Config)

# Security headers
@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if app.config.get('FLASK_ENV') == 'production':
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline';"
        )
    return response

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Create database tables
with app.app_context():
    db.create_all()
    
    # Create default admin user if no users exist
    if User.query.count() == 0:
        admin = User(username='admin', email='admin@kanban.local')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("⚠️  SECURITY WARNING: Default admin user created!")
        print("⚠️  Username: admin | Password: admin123")
        print("⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

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
    
    if User.query.count() >= app.config['MAX_USERS']:
        flash('Maximum number of users reached. Contact administrator.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Assigns user.id before it's used below

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

@app.route('/account/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return render_template('change_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('change_password.html')

        if len(new_password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('change_password.html')

        current_user.set_password(new_password)
        db.session.commit()

        flash('Password changed successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')

# ============================================================================
# DASHBOARD
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    # Ensure user has parking lot (create if missing)
    parking_lot = Board.query.filter_by(owner_id=current_user.id, is_parking_lot=True).first()
    if not parking_lot:
        parking_lot = Board(
            name=f"{current_user.username}'s Parking Lot",
            description="Personal backlog and notes",
            owner_id=current_user.id,
            is_parking_lot=True
        )
        db.session.add(parking_lot)
        db.session.commit()
    
    my_boards = Board.query.filter_by(owner_id=current_user.id, is_parking_lot=False, archived=False).all()
    shared_boards = [board for board in current_user.boards if board.owner_id != current_user.id and not board.archived]
    
    # Calculate stats
    total_cards = Card.query.join(Board).filter(
        (Board.owner_id == current_user.id) | (Board.members.any(id=current_user.id)),
        Card.archived == False
    ).count()
    
    return render_template('dashboard.html', 
                         my_boards=my_boards,
                         shared_boards=shared_boards,
                         parking_lot=parking_lot,
                         total_cards=total_cards)

# ============================================================================
# BOARD ROUTES
# ============================================================================

@app.route('/board/create', methods=['GET', 'POST'])
@login_required
def create_board():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('Board name is required', 'error')
            return redirect(url_for('dashboard'))
        
        board = Board(
            name=name,
            description=description,
            owner_id=current_user.id,
            is_parking_lot=False
        )
        db.session.add(board)
        db.session.commit()
        
        flash(f'Board "{name}" created successfully!', 'success')
        return redirect(url_for('view_board', board_id=board.id))
    
    return render_template('create_board.html')

@app.route('/board/<int:board_id>')
@login_required
def view_board(board_id):
    board = db.session.get(Board, board_id) or abort(404)

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        flash('You do not have access to this board', 'error')
        return redirect(url_for('dashboard'))

    # Get cards by column
    assigned_cards = Card.query.filter_by(board_id=board_id, column='assigned', archived=False).order_by(Card.position).all()
    in_progress_cards = Card.query.filter_by(board_id=board_id, column='in_progress', archived=False).order_by(Card.position).all()
    complete_cards = Card.query.filter_by(board_id=board_id, column='complete', archived=False).order_by(Card.position).all()
    
    # For parking lot, get all cards in single column
    parking_lot_cards = Card.query.filter_by(board_id=board_id, column='parking_lot', archived=False).order_by(Card.position).all() if board.is_parking_lot else []
    
    return render_template('board.html',
                         board=board,
                         assigned_cards=assigned_cards,
                         in_progress_cards=in_progress_cards,
                         complete_cards=complete_cards,
                         parking_lot_cards=parking_lot_cards,
                         is_owner=(board.owner_id == current_user.id))

@app.route('/board/<int:board_id>/delete', methods=['POST'])
@login_required
def delete_board(board_id):
    board = db.session.get(Board, board_id) or abort(404)

    if board.owner_id != current_user.id:
        flash('Only the board owner can delete it', 'error')
        return redirect(url_for('dashboard'))
    
    if board.is_parking_lot:
        flash('Cannot delete parking lot', 'error')
        return redirect(url_for('dashboard'))
    
    board_name = board.name
    db.session.delete(board)
    db.session.commit()
    
    flash(f'Board "{board_name}" deleted successfully', 'success')
    return redirect(url_for('dashboard'))

# ============================================================================
# CARD ROUTES
# ============================================================================

@app.route('/board/<int:board_id>/card/create', methods=['POST'])
@login_required
def create_card(board_id):
    board = db.session.get(Board, board_id) or abort(404)

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        flash('You do not have access to this board', 'error')
        return redirect(url_for('dashboard'))

    title = request.form.get('title')
    column = request.form.get('column', 'assigned')
    
    if not title:
        flash('Card title is required', 'error')
        return redirect(url_for('view_board', board_id=board_id))
    
    # Set column based on board type
    if board.is_parking_lot:
        column = 'parking_lot'
    
    # Get next position in column
    max_position = db.session.query(db.func.max(Card.position)).filter_by(
        board_id=board_id, column=column
    ).scalar() or 0
    
    card = Card(
        title=title,
        board_id=board_id,
        creator_id=current_user.id,
        column=column,
        position=max_position + 1
    )
    db.session.add(card)
    db.session.commit()

    # Log activity
    activity = ActivityLog(
        board_id=board_id,
        user_id=current_user.id,
        action='created_card',
        details=f'Created card "{title}" in {column.replace("_", " ")}'
    )
    db.session.add(activity)
    db.session.commit()

    flash(f'Card "{title}" created successfully!', 'success')
    return redirect(url_for('view_board', board_id=board_id))

@app.route('/card/<int:card_id>')
@login_required
def view_card(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        flash('You do not have access to this card', 'error')
        return redirect(url_for('dashboard'))
    
    # For parking lot cards, find boards user can move to
    accessible_boards = []
    if board.is_parking_lot:
        accessible_boards = Board.query.filter(
            db.or_(
                Board.owner_id == current_user.id,
                Board.members.any(id=current_user.id)
            ),
            Board.is_parking_lot == False,
            Board.archived == False
        ).all()

    return render_template('card_detail.html', card=card, board=board, accessible_boards=accessible_boards)

@app.route('/card/<int:card_id>/edit', methods=['POST'])
@login_required
def edit_card(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    # Update fields
    card.title = request.form.get('title', card.title)
    card.description = request.form.get('description', card.description)
    
    # Time tracking
    time_estimate = request.form.get('time_estimate')
    if time_estimate:
        card.time_estimate = float(time_estimate)
    
    time_actual = request.form.get('time_actual')
    if time_actual:
        card.time_actual = float(time_actual)
    
    # Priority
    card.priority = request.form.get('priority', card.priority)
    
    # Tags
    tags = request.form.get('tags', '')
    card.tags = tags

    # Deadline
    deadline_str = request.form.get('deadline', '')
    if deadline_str:
        card.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
    else:
        card.deadline = None

    db.session.commit()
    
    flash('Card updated successfully!', 'success')
    return redirect(url_for('view_card', card_id=card_id))

@app.route('/card/<int:card_id>/delete', methods=['POST'])
@login_required
def delete_card(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    board_id = card.board_id
    card_title = card.title
    
    db.session.delete(card)
    db.session.commit()
    
    flash(f'Card "{card_title}" deleted successfully', 'success')
    return redirect(url_for('view_board', board_id=board_id))

@app.route('/card/<int:card_id>/move', methods=['POST'])
@login_required
def move_card(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    new_column = request.form.get('column')
    
    if new_column not in ['assigned', 'in_progress', 'complete', 'parking_lot']:
        return jsonify({'error': 'Invalid column'}), 400
    
    old_column = card.column
    card.column = new_column
    card.last_moved_at = datetime.now(timezone.utc)
    
    # Update timestamps based on column
    if new_column == 'in_progress' and not card.in_progress_at:
        card.in_progress_at = datetime.now(timezone.utc)
    elif new_column == 'complete' and not card.completed_at:
        card.completed_at = datetime.now(timezone.utc)
    
    # Get next position in new column
    max_position = db.session.query(db.func.max(Card.position)).filter_by(
        board_id=card.board_id, column=new_column
    ).scalar() or 0
    card.position = max_position + 1
    
    db.session.commit()

    # Log activity
    activity = ActivityLog(
        board_id=board.id,
        user_id=current_user.id,
        action='moved_card',
        details=f'Moved "{card.title}" from {old_column.replace("_", " ")} to {new_column.replace("_", " ")}'
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({
        'success': True,
        'card_id': card.id,
        'old_column': old_column,
        'new_column': new_column
    })

@app.route('/card/<int:card_id>/move-to-board', methods=['POST'])
@login_required
def move_card_to_board(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    source_board = card.board

    if not source_board.is_parking_lot:
        return jsonify({'error': 'Card is not in parking lot'}), 400

    if source_board.owner_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    target_board_id = data.get('board_id')
    target_column = data.get('column', 'assigned')

    if not target_board_id:
        return jsonify({'error': 'Target board is required'}), 400

    target_board = db.session.get(Board, target_board_id)
    if not target_board:
        return jsonify({'error': 'Board not found'}), 404

    if target_board.owner_id != current_user.id and current_user not in target_board.members:
        return jsonify({'error': 'Access denied to target board'}), 403

    if target_board.is_parking_lot:
        return jsonify({'error': 'Cannot move to another parking lot'}), 400

    if target_column not in ['assigned', 'in_progress', 'complete']:
        target_column = 'assigned'

    max_position = db.session.query(db.func.max(Card.position)).filter_by(
        board_id=target_board_id, column=target_column
    ).scalar() or 0

    card.move_to_board(target_board_id, target_column)
    card.position = max_position + 1

    db.session.commit()

    activity = ActivityLog(
        board_id=source_board.id,
        user_id=current_user.id,
        action='moved_to_board',
        details=f'Moved "{card.title}" to board "{target_board.name}"'
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({'success': True, 'redirect': url_for('view_card', card_id=card_id)})

# ============================================================================
# BOARD SHARING & MEMBERS
# ============================================================================

@app.route('/board/<int:board_id>/settings')
@login_required
def board_settings(board_id):
    board = db.session.get(Board, board_id) or abort(404)
    
    # Only owner can access settings
    if board.owner_id != current_user.id:
        flash('Only the board owner can access settings', 'error')
        return redirect(url_for('view_board', board_id=board_id))
    
    if board.is_parking_lot:
        flash('Cannot share parking lot', 'error')
        return redirect(url_for('view_board', board_id=board_id))
    
    # Get all members with their roles
    members_data = []
    for member in board.members:
        # Get role from association table
        member_assoc = db.session.query(board_members).filter_by(
            user_id=member.id,
            board_id=board_id
        ).first()
        
        role = member_assoc.role if member_assoc else 'member'
        members_data.append({
            'user': member,
            'role': role
        })
    
    return render_template('board_settings.html', board=board, members_data=members_data)

@app.route('/board/<int:board_id>/members/add', methods=['POST'])
@login_required
def add_board_member(board_id):
    board = db.session.get(Board, board_id) or abort(404)
    
    # Only owner can add members
    if board.owner_id != current_user.id:
        flash('Only the board owner can add members', 'error')
        return redirect(url_for('board_settings', board_id=board_id))
    
    username = request.form.get('username')
    if not username:
        flash('Username is required', 'error')
        return redirect(url_for('board_settings', board_id=board_id))
    
    # Find user
    user = User.query.filter_by(username=username).first()
    if not user:
        flash(f'User "{username}" not found', 'error')
        return redirect(url_for('board_settings', board_id=board_id))
    
    # Check if already a member
    if user in board.members or user.id == board.owner_id:
        flash(f'{username} is already a member of this board', 'error')
        return redirect(url_for('board_settings', board_id=board_id))
    
    # Add member
    board.members.append(user)
    
    # Log activity
    activity = ActivityLog(
        board_id=board_id,
        user_id=current_user.id,
        action='added_member',
        details=f'Added {username} to the board'
    )
    db.session.add(activity)
    
    db.session.commit()
    
    flash(f'{username} added to board', 'success')
    return redirect(url_for('board_settings', board_id=board_id))

@app.route('/board/<int:board_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_board_member(board_id, user_id):
    board = db.session.get(Board, board_id) or abort(404)

    # Only owner can remove members
    if board.owner_id != current_user.id:
        flash('Only the board owner can remove members', 'error')
        return redirect(url_for('board_settings', board_id=board_id))

    user = db.session.get(User, user_id) or abort(404)
    
    # Can't remove owner
    if user.id == board.owner_id:
        flash('Cannot remove board owner', 'error')
        return redirect(url_for('board_settings', board_id=board_id))
    
    # Remove member
    if user in board.members:
        board.members.remove(user)
        
        # Log activity
        activity = ActivityLog(
            board_id=board_id,
            user_id=current_user.id,
            action='removed_member',
            details=f'Removed {user.username} from the board'
        )
        db.session.add(activity)
        
        db.session.commit()
        
        flash(f'{user.username} removed from board', 'success')
    
    return redirect(url_for('board_settings', board_id=board_id))

# ============================================================================
# CARD ASSIGNMENT
# ============================================================================

@app.route('/card/<int:card_id>/assign', methods=['POST'])
@login_required
def assign_card(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board
    
    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403
    
    assignee_id = request.form.get('assignee_id')
    
    if assignee_id:
        assignee_id = int(assignee_id)
        assignee = db.session.get(User, assignee_id)
        
        # Verify assignee has access to board
        if assignee and (assignee.id == board.owner_id or assignee in board.members):
            card.assignee_id = assignee_id
            
            # Log activity
            activity = ActivityLog(
                board_id=board.id,
                user_id=current_user.id,
                action='assigned_card',
                details=f'Assigned "{card.title}" to {assignee.username}'
            )
            db.session.add(activity)
            
            db.session.commit()
            
            flash(f'Card assigned to {assignee.username}', 'success')
        else:
            flash('User does not have access to this board', 'error')
    else:
        # Unassign
        card.assignee_id = None
        db.session.commit()
        flash('Card unassigned', 'success')
    
    return redirect(url_for('view_card', card_id=card_id))

# ============================================================================
# ACTIVITY LOG
# ============================================================================

@app.route('/board/<int:board_id>/activity')
@login_required
def view_activity(board_id):
    board = db.session.get(Board, board_id) or abort(404)
    
    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        flash('You do not have access to this board', 'error')
        return redirect(url_for('dashboard'))
    
    # Get recent activity (last 50 items)
    activities = ActivityLog.query.filter_by(board_id=board_id).order_by(
        ActivityLog.timestamp.desc()
    ).limit(50).all()
    
    return render_template('activity_log.html', board=board, activities=activities)

# ============================================================================
# USER SEARCH API
# ============================================================================

@app.route('/api/users/search')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'users': []})
    
    # Search users by username (exclude current user)
    users = User.query.filter(
        User.username.ilike(f'%{query}%'),
        User.id != current_user.id
    ).limit(10).all()
    
    return jsonify({
        'users': [{'id': u.id, 'username': u.username} for u in users]
    })

# ============================================================================
# METRICS & ANALYTICS
# ============================================================================

@app.route('/dashboard/metrics')
@login_required
def dashboard_metrics():
    user_boards = Board.query.filter(
        db.or_(
            Board.owner_id == current_user.id,
            Board.members.any(id=current_user.id)
        ),
        Board.is_parking_lot == False,
        Board.archived == False
    ).all()

    board_ids = [b.id for b in user_boards]
    metrics = calculate_user_metrics(current_user.id, board_ids)

    return render_template('metrics.html', metrics=metrics)

@app.route('/board/<int:board_id>/metrics')
@login_required
def board_metrics(board_id):
    board = db.session.get(Board, board_id) or abort(404)

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        flash('You do not have access to this board', 'error')
        return redirect(url_for('dashboard'))

    metrics = calculate_board_metrics(board_id)
    return render_template('board_metrics.html', board=board, metrics=metrics)

def calculate_board_metrics(board_id):
    """Calculate metrics for a specific board"""
    all_cards = Card.query.filter_by(board_id=board_id, archived=False).all()

    # Basic counts
    total_cards = len(all_cards)
    assigned_count = len([c for c in all_cards if c.column == 'assigned'])
    in_progress_count = len([c for c in all_cards if c.column == 'in_progress'])
    complete_count = len([c for c in all_cards if c.column == 'complete'])
    completion_rate = round((complete_count / total_cards * 100) if total_cards > 0 else 0, 1)

    # Cards by assignee
    assignee_distribution = {}
    for card in all_cards:
        name = card.assignee.username if card.assignee else 'Unassigned'
        if name not in assignee_distribution:
            assignee_distribution[name] = {'total': 0, 'complete': 0}
        assignee_distribution[name]['total'] += 1
        if card.column == 'complete':
            assignee_distribution[name]['complete'] += 1

    # Cards by priority
    priority_counts = {
        'high': len([c for c in all_cards if c.priority == 'high']),
        'medium': len([c for c in all_cards if c.priority == 'medium']),
        'low': len([c for c in all_cards if c.priority == 'low'])
    }

    # Time tracking
    total_estimated = sum(c.time_estimate for c in all_cards if c.time_estimate > 0)
    total_actual = sum(c.time_actual for c in all_cards if c.time_actual > 0)

    completed_cards = [c for c in all_cards if c.column == 'complete']
    completed_with_time = [c for c in completed_cards if c.time_actual > 0]
    avg_time_per_card = round(
        sum(c.time_actual for c in completed_with_time) / len(completed_with_time), 1
    ) if completed_with_time else 0

    # Activity by week (last 5 weeks)
    weekly_created = {}
    weekly_completed = {}
    for i in range(4, -1, -1):
        week_start = datetime.now(timezone.utc) - timedelta(weeks=i + 1)
        week_end = datetime.now(timezone.utc) - timedelta(weeks=i)
        # Convert to naive for comparison
        week_start_naive = week_start.replace(tzinfo=None)
        week_end_naive = week_end.replace(tzinfo=None)
        label = week_start.strftime('%b %d')
        weekly_created[label] = len([c for c in all_cards if week_start_naive <= c.created_at < week_end_naive])
        weekly_completed[label] = len([
            c for c in completed_cards if c.completed_at and week_start_naive <= c.completed_at < week_end_naive
        ])

    return {
        'total_cards': total_cards,
        'assigned_count': assigned_count,
        'in_progress_count': in_progress_count,
        'complete_count': complete_count,
        'completion_rate': completion_rate,
        'total_estimated': round(total_estimated, 1),
        'total_actual': round(total_actual, 1),
        'avg_time_per_card': avg_time_per_card,
        'assignee_distribution': assignee_distribution,
        'priority_counts': priority_counts,
        'assignee_chart': {
            'labels': list(assignee_distribution.keys()),
            'data': [v['total'] for v in assignee_distribution.values()]
        },
        'priority_chart': {
            'labels': ['High', 'Medium', 'Low'],
            'data': [priority_counts['high'], priority_counts['medium'], priority_counts['low']]
        },
        'activity_chart': {
            'labels': list(weekly_created.keys()),
            'created': list(weekly_created.values()),
            'completed': list(weekly_completed.values())
        }
    }

def calculate_user_metrics(user_id, board_ids):
    """Calculate comprehensive metrics for user's boards"""
    all_cards = Card.query.filter(
        Card.board_id.in_(board_ids),
        Card.archived == False
    ).all()

    # Basic counts
    total_cards = len(all_cards)
    assigned_count = len([c for c in all_cards if c.column == 'assigned'])
    in_progress_count = len([c for c in all_cards if c.column == 'in_progress'])
    complete_count = len([c for c in all_cards if c.column == 'complete'])

    # Cards assigned to current user
    my_cards = [c for c in all_cards if c.assignee_id == user_id]
    my_cards_count = len(my_cards)
    my_complete = len([c for c in my_cards if c.column == 'complete'])

    # Completion rate
    completion_rate = round((complete_count / total_cards * 100) if total_cards > 0 else 0, 1)

    # Time tracking metrics
    cards_with_estimates = [c for c in all_cards if c.time_estimate > 0]
    cards_with_actuals = [c for c in all_cards if c.time_actual > 0]

    total_estimated = sum(c.time_estimate for c in cards_with_estimates)
    total_actual = sum(c.time_actual for c in cards_with_actuals)

    # Estimate accuracy (for completed cards with both estimate and actual)
    completed_cards = [c for c in all_cards if c.column == 'complete']
    accuracy_cards = [c for c in completed_cards if c.time_estimate > 0 and c.time_actual > 0]

    if accuracy_cards:
        accuracy_scores = []
        for card in accuracy_cards:
            ratio = card.time_actual / card.time_estimate
            accuracy = 100 - abs((ratio - 1.0) * 100)
            accuracy = max(0, min(100, accuracy))
            accuracy_scores.append(accuracy)
        avg_accuracy = round(sum(accuracy_scores) / len(accuracy_scores), 1)
    else:
        avg_accuracy = 0

    # Average completion time
    completion_times = []
    for card in completed_cards:
        if card.assigned_at and card.completed_at:
            duration = card.completed_at - card.assigned_at
            completion_times.append(duration.total_seconds() / 3600)

    avg_completion_time = round(sum(completion_times) / len(completion_times), 1) if completion_times else 0

    # Recent activity (last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    # Make seven_days_ago naive to match database timestamps
    seven_days_ago_naive = seven_days_ago.replace(tzinfo=None)
    cards_this_week = len([c for c in all_cards if c.created_at >= seven_days_ago_naive])
    completed_this_week = len([c for c in completed_cards if c.completed_at and c.completed_at >= seven_days_ago_naive])

    # Chart data: Cards by column
    column_data = {
        'labels': ['Assigned', 'In Progress', 'Complete'],
        'data': [assigned_count, in_progress_count, complete_count]
    }

    # Chart data: Completion trend (last 7 days)
    trend_labels = []
    trend_data = []
    for i in range(6, -1, -1):
        date = datetime.now(timezone.utc) - timedelta(days=i)
        trend_labels.append(date.strftime('%b %d'))
        # Convert to naive datetime for comparison
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        day_end = day_start + timedelta(days=1)
        completed_on_day = len([
            c for c in completed_cards
            if c.completed_at and day_start <= c.completed_at < day_end
        ])
        trend_data.append(completed_on_day)

    completion_trend = {'labels': trend_labels, 'data': trend_data}

    # Chart data: Time estimate vs actual (last 10 completed cards with both)
    estimate_comparison = {'labels': [], 'estimated': [], 'actual': []}
    for card in accuracy_cards[:10]:
        label = (card.title[:20] + '...') if len(card.title) > 20 else card.title
        estimate_comparison['labels'].append(label)
        estimate_comparison['estimated'].append(card.time_estimate)
        estimate_comparison['actual'].append(card.time_actual)

    return {
        'total_cards': total_cards,
        'assigned_count': assigned_count,
        'in_progress_count': in_progress_count,
        'complete_count': complete_count,
        'my_cards_count': my_cards_count,
        'my_complete': my_complete,
        'completion_rate': completion_rate,
        'total_estimated': round(total_estimated, 1),
        'total_actual': round(total_actual, 1),
        'avg_accuracy': avg_accuracy,
        'avg_completion_time': avg_completion_time,
        'cards_this_week': cards_this_week,
        'completed_this_week': completed_this_week,
        'column_data': column_data,
        'completion_trend': completion_trend,
        'estimate_comparison': estimate_comparison
    }

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/health')
def health():
    return {'status': 'ok', 'message': 'Kanban API is running'}

# ============================================================================
# CHECKLIST ROUTES
# ============================================================================

@app.route('/card/<int:card_id>/checklist/add', methods=['POST'])
@login_required
def add_checklist_item(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    text = request.form.get('text')
    parent_id = request.form.get('parent_id')
    level = int(request.form.get('level', 0))
    
    if not text:
        return jsonify({'error': 'Text is required'}), 400
    
    if level > 4:
        return jsonify({'error': 'Maximum nesting level reached'}), 400
    
    # Get next position
    if parent_id:
        max_position = db.session.query(db.func.max(ChecklistItem.position)).filter_by(
            card_id=card_id, parent_id=parent_id
        ).scalar() or 0
    else:
        max_position = db.session.query(db.func.max(ChecklistItem.position)).filter_by(
            card_id=card_id, parent_id=None
        ).scalar() or 0
    
    item = ChecklistItem(
        card_id=card_id,
        parent_id=int(parent_id) if parent_id else None,
        text=text,
        level=level,
        position=max_position + 1
    )
    db.session.add(item)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'item': {
            'id': item.id,
            'text': item.text,
            'completed': item.completed,
            'level': item.level
        }
    })

@app.route('/checklist/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_checklist_item(item_id):
    item = db.session.get(ChecklistItem, item_id) or abort(404)
    card = item.card
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    item.completed = not item.completed
    db.session.commit()
    
    return jsonify({
        'success': True,
        'completed': item.completed
    })

@app.route('/checklist/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_checklist_item(item_id):
    item = db.session.get(ChecklistItem, item_id) or abort(404)
    card = item.card
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    text = request.form.get('text')
    if not text:
        return jsonify({'error': 'Text is required'}), 400

    item.text = text
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/checklist/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_checklist_item(item_id):
    item = db.session.get(ChecklistItem, item_id) or abort(404)
    card = item.card
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/checklist/<int:item_id>/indent', methods=['POST'])
@login_required
def indent_checklist_item(item_id):
    item = db.session.get(ChecklistItem, item_id) or abort(404)
    card = item.card
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    direction = request.form.get('direction')  # 'in' or 'out'
    
    if direction == 'in' and item.level < 4:
        # Find previous sibling to become parent
        siblings = ChecklistItem.query.filter_by(
            card_id=item.card_id,
            parent_id=item.parent_id,
            level=item.level
        ).filter(ChecklistItem.position < item.position).order_by(ChecklistItem.position.desc()).all()
        
        if siblings:
            new_parent = siblings[0]
            item.parent_id = new_parent.id
            item.level += 1
            db.session.commit()
            return jsonify({'success': True, 'level': item.level})
    
    elif direction == 'out' and item.level > 0:
        if item.parent_id:
            parent = db.session.get(ChecklistItem, item.parent_id)
            item.parent_id = parent.parent_id if parent else None
            item.level -= 1
            db.session.commit()
            return jsonify({'success': True, 'level': item.level})
    
    return jsonify({'success': False, 'message': 'Cannot indent'})

# ============================================================================
# COMMENT ROUTES
# ============================================================================

@app.route('/card/<int:card_id>/comment/add', methods=['POST'])
@login_required
def add_comment(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    text = request.form.get('text')
    if not text:
        flash('Comment text is required', 'error')
        return redirect(url_for('view_card', card_id=card_id))
    
    comment = Comment(
        card_id=card_id,
        author_id=current_user.id,
        text=text
    )
    db.session.add(comment)
    db.session.commit()
    
    flash('Comment added', 'success')
    return redirect(url_for('view_card', card_id=card_id))

@app.route('/comment/<int:comment_id>/edit', methods=['POST'])
@login_required
def edit_comment(comment_id):
    comment = db.session.get(Comment, comment_id) or abort(404)

    # Only author can edit
    if comment.author_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    text = request.form.get('text')
    if not text:
        return jsonify({'error': 'Text is required'}), 400
    
    comment.text = text
    comment.edited_at = datetime.now(timezone.utc)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id) or abort(404)
    card_id = comment.card_id
    
    # Only author can delete
    if comment.author_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('view_card', card_id=card_id))
    
    db.session.delete(comment)
    db.session.commit()
    
    flash('Comment deleted', 'success')
    return redirect(url_for('view_card', card_id=card_id))

# ============================================================================
# ARCHIVE ROUTES
# ============================================================================

@app.route('/card/<int:card_id>/archive', methods=['POST'])
@login_required
def archive_card(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    card.archived = True
    card.archived_at = datetime.now(timezone.utc)
    db.session.commit()
    
    flash(f'Card "{card.title}" archived', 'success')
    return redirect(url_for('view_board', board_id=board.id))

@app.route('/card/<int:card_id>/unarchive', methods=['POST'])
@login_required
def unarchive_card(card_id):
    card = db.session.get(Card, card_id) or abort(404)
    board = card.board

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        return jsonify({'error': 'Access denied'}), 403

    card.archived = False
    card.archived_at = None
    db.session.commit()
    
    flash(f'Card "{card.title}" restored', 'success')
    return redirect(url_for('view_board', board_id=board.id))

@app.route('/board/<int:board_id>/archived')
@login_required
def view_archived_cards(board_id):
    board = db.session.get(Board, board_id) or abort(404)

    # Check access
    if board.owner_id != current_user.id and current_user not in board.members:
        flash('You do not have access to this board', 'error')
        return redirect(url_for('dashboard'))

    archived_cards = Card.query.filter_by(board_id=board_id, archived=True).order_by(Card.archived_at.desc()).all()
    
    return render_template('archived_cards.html', board=board, archived_cards=archived_cards)

if __name__ == '__main__':
    port = app.config['PORT']
    app.run(host='0.0.0.0', port=port, debug=True)