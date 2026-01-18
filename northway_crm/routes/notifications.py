from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from models import db, Notification
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    # Fetch unread first, then recent read ones (limit 20 total)
    unread = Notification.query.filter_by(user_id=current_user.id, read=False)\
        .order_by(Notification.created_at.desc()).all()
    
    read_limit = 20 - len(unread)
    read = []
    if read_limit > 0:
        read = Notification.query.filter_by(user_id=current_user.id, read=True)\
            .order_by(Notification.created_at.desc()).limit(read_limit).all()
            
    notifications = unread + read
    # Sort again by date desc just in case
    notifications.sort(key=lambda x: x.created_at, reverse=True)
    
    return jsonify({
        'unread_count': len(unread),
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.type,
            'read': n.read,
            'created_at': n.created_at.strftime('%d/%m %H:%M')
        } for n in notifications]
    })

@notifications_bp.route('/api/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id != current_user.id:
        abort(403)
        
    notification.read = True
    db.session.commit()
    return jsonify({'success': True})

@notifications_bp.route('/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    return jsonify({'success': True})
