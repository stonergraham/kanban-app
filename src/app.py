from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime
import os

from config import Config
from models import db, User, Board, Card, ActivityLog, ChecklistItem, Comment

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
        print("✓ Created default admin user (username: admin, password: admin123)")

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
    
    return render_template('card_detail.html', card=card, board=board)

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
    card.last_moved_at = datetime.utcnow()
    
    # Update timestamps based on column
    if new_column == 'in_progress' and not card.in_progress_at:
        card.in_progress_at = datetime.utcnow()
    elif new_column == 'complete' and not card.completed_at:
        card.completed_at = datetime.utcnow()
    
    # Get next position in new column
    max_position = db.session.query(db.func.max(Card.position)).filter_by(
        board_id=card.board_id, column=new_column
    ).scalar() or 0
    card.position = max_position + 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'card_id': card.id,
        'old_column': old_column,
        'new_column': new_column
    })

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
    comment.edited_at = datetime.utcnow()
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
    card.archived_at = datetime.utcnow()
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