"""Routes for document management."""
import os
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file, abort, jsonify)
from flask_login import login_required, current_user
from models.database import get_session
from models.document import Document
from models.division import Division
from web.utils.file_utils import (save_uploaded_file, delete_document,
                                   allowed_file, get_entity_documents)
from web.auth import role_required

documents_bp = Blueprint('documents', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _tpl_vars(**extra):
    base = dict(active_page='documents', user=current_user, divisions=_get_divisions())
    base.update(extra)
    return base


@documents_bp.route('/documents')
@login_required
def document_list():
    """Document center — global searchable repository."""
    db = get_session()
    try:
        search_q = request.args.get('q', '').strip()
        category = request.args.get('category', '')
        entity_type = request.args.get('entity_type', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        view_mode = request.args.get('view', 'list')

        include_confidential = current_user.role in ('owner', 'admin')

        query = Document.search(
            db,
            query_str=search_q if search_q else None,
            category=category if category else None,
            entity_type=entity_type if entity_type else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            include_confidential=include_confidential,
        )
        documents = query.all()

        total_docs = db.query(Document).count()
        from sqlalchemy import func
        categories_used = dict(
            db.query(Document.category, func.count(Document.id))
            .group_by(Document.category).all()
        )

        return render_template('documents/document_list.html',
                               **_tpl_vars(
                                   documents=documents,
                                   total_docs=total_docs,
                                   categories_used=categories_used,
                                   search_q=search_q,
                                   category=category,
                                   entity_type=entity_type,
                                   date_from=date_from,
                                   date_to=date_to,
                                   view_mode=view_mode,
                                   category_choices=Document.CATEGORY_CHOICES,
                               ))
    finally:
        db.close()


@documents_bp.route('/documents/upload', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher', 'technician')
def document_upload():
    """Upload new documents (supports multi-file)."""
    db = get_session()
    try:
        if request.method == 'POST':
            files = request.files.getlist('files')
            if not files or all(f.filename == '' for f in files):
                flash('No files selected.', 'danger')
                return redirect(request.url)

            f = request.form
            entity_type = f.get('entity_type', '').strip() or None
            entity_id = int(f['entity_id']) if f.get('entity_id') else None
            category = f.get('category', 'other')
            description = f.get('description', '').strip() or None
            is_confidential = f.get('is_confidential') == 'on'
            tags = f.get('tags', '').strip() or None
            notes = f.get('notes', '').strip() or None
            expiry_date = None
            if f.get('expiry_date'):
                from datetime import datetime as dt
                try:
                    expiry_date = dt.strptime(f['expiry_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            if current_user.role == 'technician':
                is_confidential = False

            uploaded_count = 0
            errors = []

            for file in files:
                if file.filename == '':
                    continue
                try:
                    display_name = f.get('display_name', '').strip()
                    if not display_name or len(files) > 1:
                        display_name = file.filename
                    doc = save_uploaded_file(
                        db, file, entity_type=entity_type, entity_id=entity_id,
                        category=category, display_name=display_name,
                        description=description, uploaded_by=current_user.id,
                        is_confidential=is_confidential, tags=tags,
                        notes=notes, expiry_date=expiry_date,
                    )
                    if doc:
                        uploaded_count += 1
                except ValueError as e:
                    errors.append(f"{file.filename}: {str(e)}")
                except Exception as e:
                    errors.append(f"{file.filename}: Upload failed")

            if uploaded_count:
                db.commit()
                flash(f'{uploaded_count} document(s) uploaded.', 'success')
            if errors:
                for err in errors:
                    flash(err, 'danger')

            next_url = f.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('documents.document_list'))

        return render_template('documents/document_upload.html',
                               **_tpl_vars(
                                   entity_type=request.args.get('entity_type', ''),
                                   entity_id=request.args.get('entity_id', ''),
                                   category=request.args.get('category', ''),
                                   next_url=request.args.get('next', ''),
                                   category_choices=Document.CATEGORY_CHOICES,
                               ))
    finally:
        db.close()


@documents_bp.route('/documents/<int:doc_id>')
@login_required
def document_detail(doc_id):
    db = get_session()
    try:
        doc = db.query(Document).filter_by(id=doc_id).first()
        if not doc:
            abort(404)
        if doc.is_confidential and current_user.role not in ('owner', 'admin'):
            abort(403)

        # Version history
        versions = []
        current = doc
        while current.replaces_document_id:
            prev = db.query(Document).filter_by(id=current.replaces_document_id).first()
            if prev:
                versions.append(prev)
                current = prev
            else:
                break
        newer = db.query(Document).filter_by(replaces_document_id=doc.id).all()

        return render_template('documents/document_detail.html',
                               **_tpl_vars(doc=doc, versions=versions, newer=newer))
    finally:
        db.close()


@documents_bp.route('/documents/<int:doc_id>/download')
@login_required
def document_download(doc_id):
    db = get_session()
    try:
        doc = db.query(Document).filter_by(id=doc_id).first()
        if not doc:
            abort(404)
        if doc.is_confidential and current_user.role not in ('owner', 'admin'):
            abort(403)
        if not os.path.exists(doc.file_path):
            abort(404)
        return send_file(doc.file_path, download_name=doc.filename, as_attachment=True)
    finally:
        db.close()


@documents_bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def document_delete(doc_id):
    db = get_session()
    try:
        doc = db.query(Document).filter_by(id=doc_id).first()
        if not doc:
            abort(404)
        name = doc.display_name
        delete_document(db, doc_id)
        db.commit()
        flash(f'Document "{name}" deleted.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()

    next_url = request.form.get('next')
    return redirect(next_url or url_for('documents.document_list'))


@documents_bp.route('/documents/<int:doc_id>/new-version', methods=['POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher', 'technician')
def document_new_version(doc_id):
    db = get_session()
    try:
        original = db.query(Document).filter_by(id=doc_id).first()
        if not original:
            abort(404)
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('documents.document_detail', doc_id=doc_id))

        doc = save_uploaded_file(
            db, file, entity_type=original.entity_type,
            entity_id=original.entity_id, category=original.category,
            display_name=original.display_name,
            description=original.description,
            uploaded_by=current_user.id,
            is_confidential=original.is_confidential,
            tags=original.tags, notes=f"New version of {original.display_name}",
            replaces_document_id=original.id,
        )
        db.commit()
        flash(f'Version {doc.version} uploaded.', 'success')
        return redirect(url_for('documents.document_detail', doc_id=doc.id))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('documents.document_detail', doc_id=doc_id))
    finally:
        db.close()


# -- API Endpoints --

@documents_bp.route('/api/documents/for-entity')
@login_required
def api_documents_for_entity():
    db = get_session()
    try:
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id', type=int)
        if not entity_type or not entity_id:
            return jsonify([])
        include_confidential = current_user.role in ('owner', 'admin')
        docs = get_entity_documents(db, entity_type, entity_id, include_confidential)
        return jsonify([d.to_dict() for d in docs])
    finally:
        db.close()


@documents_bp.route('/api/documents/upload-inline', methods=['POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher', 'technician')
def api_upload_inline():
    db = get_session()
    try:
        file = request.files.get('file')
        if not file or file.filename == '':
            return jsonify({'error': 'No file'}), 400
        doc = save_uploaded_file(
            db, file,
            entity_type=request.form.get('entity_type'),
            entity_id=int(request.form['entity_id']) if request.form.get('entity_id') else None,
            category=request.form.get('category', 'other'),
            display_name=request.form.get('display_name', file.filename),
            uploaded_by=current_user.id,
        )
        db.commit()
        return jsonify(doc.to_dict())
    except ValueError as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


# ── Alias routes (templates reference these alternate endpoint names) ──

@documents_bp.route('/documents/center')
@login_required
def document_center():
    """Alias for document_list — sidebar and templates link here."""
    return redirect(url_for('documents.document_list'))


@documents_bp.route('/documents/upload-doc', methods=['GET', 'POST'])
@login_required
def upload_document():
    """Alias for document_upload."""
    return redirect(url_for('documents.document_upload'))


@documents_bp.route('/documents/<int:doc_id>/dl')
@login_required
def download_document(doc_id):
    """Alias for document_download."""
    return redirect(url_for('documents.document_download', doc_id=doc_id))


@documents_bp.route('/documents/<int:doc_id>/remove', methods=['POST'])
@login_required
def delete_document_view(doc_id):
    """Alias for document_delete."""
    return redirect(url_for('documents.document_delete', doc_id=doc_id), code=307)
