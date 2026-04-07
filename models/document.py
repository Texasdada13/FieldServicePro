"""Document management model for centralized file storage."""
from datetime import datetime, date
import json
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, or_
from sqlalchemy.orm import relationship
from .database import Base


class Document(Base):
    __tablename__ = 'documents'

    id                    = Column(Integer, primary_key=True)
    filename              = Column(String(500), nullable=False)
    file_path             = Column(String(1000), nullable=False)
    file_type             = Column(String(100), nullable=False)
    file_size             = Column(Integer, nullable=False)  # bytes
    display_name          = Column(String(500), nullable=False)
    description           = Column(Text, nullable=True)

    category              = Column(String(50), nullable=False, default='other')
    # Categories: permit, insurance, certification, checklist, lien_waiver,
    # contract, quote, invoice, photo, drawing, specification, report,
    # correspondence, other

    entity_type           = Column(String(50), nullable=True)
    # Polymorphic: job, permit, insurance_policy, certification,
    # checklist, lien_waiver, contract, quote, invoice
    entity_id             = Column(Integer, nullable=True)

    uploaded_by           = Column(Integer, ForeignKey('users.id'), nullable=True)
    uploaded_by_portal_user_id = Column(Integer, ForeignKey('portal_users.id'), nullable=True)
    uploaded_at           = Column(DateTime, default=datetime.utcnow)
    expiry_date           = Column(Date, nullable=True)
    is_confidential       = Column(Boolean, default=False)
    tags                  = Column(Text, nullable=True)  # JSON array of strings
    version               = Column(Integer, default=1)
    replaces_document_id  = Column(Integer, ForeignKey('documents.id'), nullable=True)
    notes                 = Column(Text, nullable=True)

    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    uploader              = relationship('User', foreign_keys=[uploaded_by])
    previous_version      = relationship('Document', remote_side=[id], backref='newer_versions')

    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv'}
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

    CATEGORY_CHOICES = [
        ('permit', 'Permit'), ('insurance', 'Insurance'),
        ('certification', 'Certification'), ('checklist', 'Checklist'),
        ('lien_waiver', 'Lien Waiver'), ('contract', 'Contract'),
        ('quote', 'Quote'), ('invoice', 'Invoice'),
        ('photo', 'Photo'), ('drawing', 'Drawing'),
        ('specification', 'Specification'), ('report', 'Report'),
        ('correspondence', 'Correspondence'), ('other', 'Other'),
    ]

    CATEGORY_LABELS = dict(CATEGORY_CHOICES)

    @property
    def category_label(self):
        return self.CATEGORY_LABELS.get(self.category, self.category)

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"

    @property
    def is_image(self):
        return self.file_type and self.file_type.startswith('image/')

    @property
    def is_pdf(self):
        return self.file_type == 'application/pdf'

    @property
    def icon_class(self):
        if self.is_image:
            return 'bi-file-image text-success'
        elif self.is_pdf:
            return 'bi-file-pdf text-danger'
        elif 'word' in (self.file_type or ''):
            return 'bi-file-word text-primary'
        elif 'excel' in (self.file_type or '') or 'spreadsheet' in (self.file_type or ''):
            return 'bi-file-excel text-success'
        else:
            return 'bi-file-earmark text-secondary'

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()

    @property
    def days_until_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    @property
    def tags_list(self):
        """Parse tags JSON to list."""
        if not self.tags:
            return []
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return [t.strip() for t in self.tags.split(',') if t.strip()]

    @tags_list.setter
    def tags_list(self, value):
        if isinstance(value, list):
            self.tags = json.dumps(value)
        elif isinstance(value, str):
            self.tags = json.dumps([t.strip() for t in value.split(',') if t.strip()])

    @staticmethod
    def get_for_entity(db, entity_type, entity_id, include_confidential=False):
        """Get all documents for a given entity."""
        q = db.query(Document).filter_by(entity_type=entity_type, entity_id=entity_id)
        if not include_confidential:
            q = q.filter(Document.is_confidential == False)
        return q.order_by(Document.uploaded_at.desc()).all()

    @staticmethod
    def search(db, query_str=None, category=None, entity_type=None,
               date_from=None, date_to=None, tags=None, include_confidential=False):
        """Search documents with filters. Returns query object."""
        q = db.query(Document)
        if not include_confidential:
            q = q.filter(Document.is_confidential == False)
        if query_str:
            like_str = f"%{query_str}%"
            q = q.filter(or_(
                Document.display_name.ilike(like_str),
                Document.description.ilike(like_str),
                Document.filename.ilike(like_str),
                Document.tags.ilike(like_str),
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
                q = q.filter(Document.tags.ilike(f'%{tag}%'))
        return q.order_by(Document.uploaded_at.desc())

    def to_dict(self):
        return {
            'id': self.id,
            'display_name': self.display_name,
            'filename': self.filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'file_size_display': self.file_size_display,
            'category': self.category,
            'category_label': self.category_label,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'is_confidential': self.is_confidential,
            'tags': self.tags_list,
            'version': self.version,
            'is_image': self.is_image,
            'is_pdf': self.is_pdf,
            'icon_class': self.icon_class,
            'is_expired': self.is_expired,
            'days_until_expiry': self.days_until_expiry,
            'notes': self.notes,
        }

    def __repr__(self):
        return f'<Document {self.id}: {self.display_name}>'
