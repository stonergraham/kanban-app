from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

# Association table for board members
board_members = db.Table('board_members',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('board_id', db.Integer, db.ForeignKey('boards.id'), primary_key=True),
    db.Column('role', db.String(20), default='member'),  # 'owner' or 'member'
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    dark_mode = db.Column(db.Boolean, default=False)
    
    # Relationships
    owned_boards = db.relationship('Board', backref='owner', lazy=True, 
                                   foreign_keys='Board.owner_id')
    cards = db.relationship('Card', backref='creator', lazy=True, 
                           foreign_keys='Card.creator_id')
    comments = db.relationship('Comment', backref='author', lazy=True,
                              foreign_keys='Comment.author_id')
    
    def set_password(self, password, method='pbkdf2:sha256'):
        self.password_hash = generate_password_hash(password, method=method)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Board(db.Model):
    __tablename__ = 'boards'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_parking_lot = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    archived = db.Column(db.Boolean, default=False)
    
    # Relationships
    cards = db.relationship('Card', backref='board', lazy=True, 
                           cascade='all, delete-orphan')
    members = db.relationship('User', secondary=board_members, 
                             backref=db.backref('boards', lazy='dynamic'))
    activity_logs = db.relationship('ActivityLog', backref='board', lazy=True,
                                   cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Board {self.name}>'

class Card(db.Model):
    __tablename__ = 'cards'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    board_id = db.Column(db.Integer, db.ForeignKey('boards.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Column status
    column = db.Column(db.String(20), default='assigned')  # assigned, in_progress, complete, parking_lot
    position = db.Column(db.Integer, default=0)  # For ordering within column
    
    # Time tracking
    time_estimate = db.Column(db.Float, default=0)  # Hours
    time_actual = db.Column(db.Float, default=0)  # Hours
    
    # Metadata
    tags = db.Column(db.String(500))  # Comma-separated tags
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    due_date = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    in_progress_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_moved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Archive
    archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    checklist_items = db.relationship('ChecklistItem', backref='card', lazy=True,
                                     cascade='all, delete-orphan',
                                     order_by='ChecklistItem.position')
    comments = db.relationship('Comment', backref='card', lazy=True,
                              cascade='all, delete-orphan',
                              order_by='Comment.created_at')
    history = db.relationship('CardHistory', backref='card', lazy=True,
                             cascade='all, delete-orphan',
                             order_by='CardHistory.timestamp.desc()')
    
    def get_tags_list(self):
        return [tag.strip() for tag in (self.tags or '').split(',') if tag.strip()]
    
    def set_tags_list(self, tags_list):
        self.tags = ','.join(tags_list) if tags_list else ''
    
    def __repr__(self):
        return f'<Card {self.title}>'

class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('checklist_items.id'), nullable=True)
    text = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    position = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=0)  # 0-4 (5 levels deep)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    children = db.relationship('ChecklistItem', backref=db.backref('parent', remote_side=[id]),
                              cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ChecklistItem {self.text[:30]}>'

class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    edited_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Comment by {self.author_id} on Card {self.card_id}>'

class CardHistory(db.Model):
    __tablename__ = 'card_history'
    
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 'moved', 'created', 'edited', 'archived'
    from_column = db.Column(db.String(20), nullable=True)
    to_column = db.Column(db.String(20), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)  # JSON string for additional data
    
    user = db.relationship('User', backref='actions')
    
    def __repr__(self):
        return f'<CardHistory {self.action} at {self.timestamp}>'

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('boards.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='activity_logs')
    
    def __repr__(self):
        return f'<ActivityLog {self.action} at {self.timestamp}>'