"""File upload and management utilities."""
import os
import uuid
import mimetypes
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from models.document import Document


ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx',
                      'xls', 'xlsx', 'txt', 'csv'}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_upload_dir(entity_type=None, entity_id=None):
    """Get the upload directory, creating it if needed."""
    base = current_app.config.get('UPLOAD_FOLDER', os.path.join(
        current_app.instance_path, 'uploads'))
    if entity_type and entity_id:
        path = os.path.join(base, entity_type, str(entity_id))
    else:
        path = os.path.join(base, 'general')
    os.makedirs(path, exist_ok=True)
    return path


def save_uploaded_file(db, file, entity_type=None, entity_id=None,
                       category='other', display_name=None,
                       description=None, uploaded_by=None,
                       is_confidential=False, tags=None, notes=None,
                       expiry_date=None, replaces_document_id=None):
    """
    Save an uploaded file and create a Document record.
    Caller must commit. Returns Document instance.
    """
    if not file or file.filename == '':
        return None

    if not allowed_file(file.filename):
        raise ValueError(f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    max_size = current_app.config.get('MAX_FILE_SIZE', MAX_FILE_SIZE)
    if file_size > max_size:
        raise ValueError(f"File too large. Maximum: {max_size // (1024*1024)}MB")

    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"

    upload_dir = get_upload_dir(entity_type, entity_id)
    file_path = os.path.join(upload_dir, unique_filename)
    file.save(file_path)

    mime_type = mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'

    version = 1
    if replaces_document_id:
        prev = db.query(Document).filter_by(id=int(replaces_document_id)).first()
        if prev:
            version = prev.version + 1

    doc = Document(
        filename=original_filename,
        file_path=file_path,
        file_type=mime_type,
        file_size=file_size,
        display_name=display_name or original_filename,
        description=description,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=uploaded_by,
        is_confidential=is_confidential,
        notes=notes,
        expiry_date=expiry_date,
        version=version,
        replaces_document_id=replaces_document_id,
    )

    if tags:
        doc.tags_list = tags

    db.add(doc)
    db.flush()
    return doc


def delete_document(db, document_id):
    """Delete a document record and its file."""
    doc = db.query(Document).filter_by(id=document_id).first()
    if not doc:
        return False
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass
    db.delete(doc)
    return True


def get_entity_documents(db, entity_type, entity_id, include_confidential=False):
    """Get all documents for an entity."""
    return Document.get_for_entity(db, entity_type, entity_id, include_confidential)
