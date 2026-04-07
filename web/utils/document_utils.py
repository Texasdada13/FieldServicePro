"""
Document management utilities — upload, versioning, search, delete.
All functions that take a db parameter expect an open SQLAlchemy session.
Functions without db use their own session and commit internally.
"""

import os
import uuid
import mimetypes
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from models.document import Document
from sqlalchemy import or_


ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp',
                      'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt'}

MAX_FILE_SIZE_DEFAULT = 25 * 1024 * 1024  # 25MB


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_upload_directory(entity_type, entity_id):
    """Returns absolute path to upload directory for an entity."""
    base = current_app.config.get('UPLOAD_FOLDER',
                                  os.path.join(current_app.root_path, '..', 'uploads'))
    path = os.path.join(base, str(entity_type or 'general'), str(entity_id or 'misc'))
    os.makedirs(path, exist_ok=True)
    return path


def save_uploaded_file(file_obj, entity_type, entity_id):
    """
    Save a werkzeug FileStorage object to disk.
    Returns (stored_filename, relative_path, mime_type, file_size).
    Raises ValueError on validation failure.
    """
    if not file_obj or file_obj.filename == '':
        raise ValueError("No file provided.")

    original_filename = secure_filename(file_obj.filename)
    if not allowed_file(original_filename):
        raise ValueError(f"File type not allowed: {original_filename}")

    # Check size
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)

    max_size = current_app.config.get('MAX_FILE_SIZE', MAX_FILE_SIZE_DEFAULT)
    if size > max_size:
        raise ValueError(f"File too large: {size} bytes (max {max_size} bytes)")

    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    stored_filename = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

    upload_dir = get_upload_directory(entity_type, entity_id)
    full_path = os.path.join(upload_dir, stored_filename)
    file_obj.save(full_path)

    rel_path = os.path.join(str(entity_type or 'general'), str(entity_id or 'misc'), stored_filename)
    mime_type = mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'

    return stored_filename, rel_path, mime_type, size


def create_document_record(db, file_obj, entity_type, entity_id, category,
                           uploaded_by_id, display_name=None, description=None,
                           expiry_date=None, is_confidential=False, tags=None,
                           notes=None, replaces_document_id=None):
    """
    Full pipeline: save file to disk + create Document db record.
    Caller must commit. Returns Document.
    """
    stored_filename, rel_path, mime_type, size = save_uploaded_file(
        file_obj, entity_type, entity_id
    )

    version = 1
    if replaces_document_id:
        prev = db.query(Document).filter_by(id=int(replaces_document_id)).first()
        if prev:
            version = prev.version + 1

    doc = Document(
        filename=stored_filename,
        original_filename=secure_filename(file_obj.filename),
        file_path=rel_path,
        file_type=mime_type,
        file_size=size,
        display_name=display_name or secure_filename(file_obj.filename),
        description=description,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=uploaded_by_id,
        expiry_date=expiry_date,
        is_confidential=is_confidential,
        notes=notes,
        version=version,
        replaces_document_id=replaces_document_id,
    )
    if tags:
        doc.tags = tags if isinstance(tags, list) else [t.strip() for t in tags.split(',') if t.strip()]

    db.add(doc)
    db.flush()
    return doc


def get_documents_for_entity(db, entity_type, entity_id, include_confidential=False):
    """Fetch all documents for a polymorphic entity."""
    q = db.query(Document).filter_by(entity_type=entity_type, entity_id=entity_id)
    if not include_confidential:
        q = q.filter(Document.is_confidential == False)
    return q.order_by(Document.uploaded_at.desc()).all()


def delete_document_file(db, document_id, user_role):
    """Delete document record and file from disk. Only admin/owner."""
    if user_role not in ('owner', 'admin'):
        raise PermissionError("Only admin/owner can delete documents.")
    doc = db.query(Document).filter_by(id=document_id).first()
    if not doc:
        raise ValueError("Document not found.")
    base = current_app.config.get('UPLOAD_FOLDER',
                                  os.path.join(current_app.root_path, '..', 'uploads'))
    full_path = os.path.join(base, doc.file_path)
    if os.path.exists(full_path):
        os.remove(full_path)
    db.delete(doc)


def search_documents(db, query=None, category=None, entity_type=None,
                     date_from=None, date_to=None, tags=None,
                     include_confidential=False, expiring_days=None):
    """Search documents with filters. Returns query object."""
    q = db.query(Document)
    if not include_confidential:
        q = q.filter(Document.is_confidential == False)
    if query:
        q = q.filter(or_(
            Document.display_name.ilike(f'%{query}%'),
            Document.original_filename.ilike(f'%{query}%'),
            Document.description.ilike(f'%{query}%'),
            Document._tags.ilike(f'%{query}%'),
        ))
    if category:
        q = q.filter_by(category=category)
    if entity_type:
        q = q.filter_by(entity_type=entity_type)
    if date_from:
        q = q.filter(Document.uploaded_at >= date_from)
    if date_to:
        q = q.filter(Document.uploaded_at <= date_to)
    if tags:
        for tag in tags:
            q = q.filter(Document._tags.ilike(f'%{tag}%'))
    if expiring_days is not None:
        from datetime import date, timedelta
        cutoff = date.today() + timedelta(days=expiring_days)
        q = q.filter(
            Document.expiry_date.isnot(None),
            Document.expiry_date <= cutoff,
            Document.expiry_date >= date.today(),
        )
    return q.order_by(Document.uploaded_at.desc())


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except ValueError:
        return None
