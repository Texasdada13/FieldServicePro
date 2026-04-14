"""Job materials logging API and view routes."""
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc

from models.database import get_session
from models.job_material import JobMaterial
from models.inventory import InventoryStock, InventoryLocation
from models.part import Part
from models.job import Job
from models.technician import Technician
from web.auth import role_required
from web.utils.materials_utils import (
    log_material, return_material, get_billable_materials_for_invoice
)

materials_bp = Blueprint('materials', __name__, url_prefix='/materials')


# ─── Add Material to Job ─────────────────────────────────────────────────────

@materials_bp.route('/job/<int:job_id>/add', methods=['POST'])
@login_required
def add_material(job_id):
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            flash('Job not found.', 'error')
            return redirect(request.referrer or '/')

        mode = request.form.get('mode', 'catalog')
        data = {
            'phase_id': request.form.get('phase_id') or None,
            'is_billable': request.form.get('is_billable') != 'false',
            'is_warranty_replacement': request.form.get('is_warranty_replacement') == 'true',
            'notes': request.form.get('notes', ''),
            'quantity': float(request.form.get('quantity', 1)),
        }

        if mode == 'catalog':
            part_id = int(request.form.get('part_id', 0))
            part = db.query(Part).filter_by(id=part_id).first()
            if not part:
                flash('Part not found.', 'error')
                return redirect(request.referrer or f'/jobs/{job_id}')

            src_loc = request.form.get('source_location_id') or None
            data.update({
                'part_id': part_id,
                'unit_of_measure': part.unit_of_measure,
                'unit_cost': float(request.form.get('unit_cost') or part.cost_price or 0),
                'markup_percentage': float(request.form.get('markup_percentage') or part.markup_percentage or 0),
                'sell_price_per_unit': float(request.form.get('sell_price_per_unit') or part.sell_price or 0),
                'source_location_id': int(src_loc) if src_loc else None,
            })
        else:
            data.update({
                'custom_description': request.form.get('custom_description', '').strip(),
                'unit_of_measure': request.form.get('unit_of_measure', 'each'),
                'unit_cost': float(request.form.get('unit_cost', 0)),
                'markup_percentage': float(request.form.get('markup_percentage', 0)),
                'sell_price_per_unit': float(request.form.get('sell_price_per_unit', 0)),
            })

        log_material(db, job_id, current_user.id, data)
        flash('Material logged.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error logging material: {e}', 'error')
    finally:
        db.close()
    return redirect(request.referrer or f'/jobs/{job_id}')


# ─── Return Material ─────────────────────────────────────────────────────────

@materials_bp.route('/<int:material_id>/return', methods=['POST'])
@login_required
def return_material_route(material_id):
    db = get_session()
    try:
        jm = db.query(JobMaterial).filter_by(id=material_id).first()
        if not jm:
            flash('Material not found.', 'error')
            return redirect(request.referrer or '/')

        job_id = jm.job_id
        qty = request.form.get('quantity_returned')
        notes = request.form.get('notes', '')

        return_material(db, material_id, current_user.id,
                        float(qty) if qty else None, notes)
        flash('Material returned and inventory restored.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error returning material: {e}', 'error')
        job_id = request.form.get('job_id', '')
    finally:
        db.close()
    return redirect(request.referrer or f'/jobs/{job_id}')


# ─── Update Status ────────────────────────────────────────────────────────────

@materials_bp.route('/<int:material_id>/status', methods=['POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def update_status(material_id):
    db = get_session()
    try:
        jm = db.query(JobMaterial).filter_by(id=material_id).first()
        if not jm:
            flash('Material not found.', 'error')
        else:
            new_status = request.form.get('status', '')
            valid = {s for s, _ in [('logged', 'Logged'), ('verified', 'Verified'), ('invoiced', 'Invoiced')]}
            if new_status in valid:
                jm.status = new_status
                db.commit()
                flash(f'Status updated to {new_status}.', 'success')
            else:
                flash('Invalid status.', 'error')
    finally:
        db.close()
    return redirect(request.referrer or '/')


# ─── Bulk Verify ──────────────────────────────────────────────────────────────

@materials_bp.route('/job/<int:job_id>/bulk-verify', methods=['POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def bulk_verify(job_id):
    db = get_session()
    try:
        materials = db.query(JobMaterial).filter_by(
            job_id=job_id, status='logged'
        ).all()
        for m in materials:
            m.status = 'verified'
        count = len(materials)
        db.commit()
        flash(f'Verified {count} materials.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(request.referrer or f'/jobs/{job_id}')


# ─── Delete Material ──────────────────────────────────────────────────────────

@materials_bp.route('/<int:material_id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def delete_material(material_id):
    db = get_session()
    try:
        jm = db.query(JobMaterial).filter_by(id=material_id).first()
        if not jm:
            flash('Material not found.', 'error')
            return redirect(request.referrer or '/')
        job_id = jm.job_id
        db.delete(jm)
        db.commit()
        flash('Material entry deleted.', 'success')
        return redirect(request.referrer or f'/jobs/{job_id}')
    finally:
        db.close()


# ─── API: Materials for a job (JSON) ─────────────────────────────────────────

@materials_bp.route('/api/job/<int:job_id>')
@login_required
def api_job_materials(job_id):
    db = get_session()
    try:
        materials = db.query(JobMaterial).filter_by(
            job_id=job_id
        ).order_by(desc(JobMaterial.added_at)).all()
        return jsonify([m.to_dict() for m in materials])
    finally:
        db.close()


# ─── API: Billable materials for invoice ──────────────────────────────────────

@materials_bp.route('/api/job/<int:job_id>/for-invoice')
@login_required
def api_for_invoice(job_id):
    db = get_session()
    try:
        items = get_billable_materials_for_invoice(db, job_id)
        return jsonify(items)
    finally:
        db.close()


# ─── API: Tech's default truck location ──────────────────────────────────────

@materials_bp.route('/api/tech-location/<int:tech_id>')
@login_required
def api_tech_location(tech_id):
    db = get_session()
    try:
        loc = db.query(InventoryLocation).filter_by(
            technician_id=tech_id, location_type='truck', is_active=True
        ).first()
        if not loc:
            return jsonify({'location': None})

        stocks = db.query(InventoryStock).filter_by(
            location_id=loc.id
        ).join(Part).filter(Part.is_active == True).all()

        return jsonify({
            'location': {'id': loc.id, 'name': loc.name},
            'stock': [{
                'part_id': s.part_id,
                'part_number': s.part.part_number,
                'part_name': s.part.name,
                'available': s.available_quantity,
            } for s in stocks],
        })
    finally:
        db.close()
