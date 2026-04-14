"""Truck stock view for technicians."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import desc

from models.database import get_session
from models.inventory import InventoryLocation, InventoryStock
from models.stock_transfer import StockTransfer, StockTransferItem
from models.part import Part
from models.technician import Technician
from models.job import Job
from models.division import Division
from web.utils.materials_utils import log_material
from web.utils.transfer_utils import generate_transfer_number

truck_bp = Blueprint('truck', __name__, url_prefix='/inventory/truck')


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


# ── My Truck (redirect) ──────────────────────────────────────────────────────

@truck_bp.route('/my')
@login_required
def my_truck():
    db = get_session()
    try:
        tech = db.query(Technician).filter_by(user_id=current_user.id).first()
        if not tech:
            flash('No technician profile found for your account.', 'error')
            return redirect(url_for('inventory.dashboard'))
        return redirect(url_for('truck.truck_stock', tech_id=tech.id))
    finally:
        db.close()


# ── Truck Stock View ──────────────────────────────────────────────────────────

@truck_bp.route('/<int:tech_id>')
@login_required
def truck_stock(tech_id):
    db = get_session()
    try:
        org_id = current_user.organization_id
        tech = db.query(Technician).filter_by(id=tech_id).first()
        if not tech:
            flash('Technician not found.', 'error')
            return redirect(url_for('inventory.dashboard'))

        # Permission: techs can only view their own truck
        if current_user.role == 'technician':
            my_tech = db.query(Technician).filter_by(user_id=current_user.id).first()
            if not my_tech or my_tech.id != tech_id:
                flash('You can only view your own truck stock.', 'error')
                return redirect(url_for('inventory.dashboard'))

        # Find truck location
        truck_location = db.query(InventoryLocation).filter_by(
            technician_id=tech_id, location_type='truck', is_active=True
        ).first()

        stocks = []
        if truck_location:
            stocks = db.query(InventoryStock).filter_by(
                location_id=truck_location.id
            ).join(Part).filter(Part.is_active == True).order_by(Part.trade, Part.name).all()

        # Current active job for quick-use
        active_job = db.query(Job).filter(
            Job.assigned_technician_id == tech_id,
            Job.status.in_(['in_progress', 'scheduled']),
        ).order_by(desc(Job.scheduled_date)).first()

        # Warehouses for restock requests
        warehouses = db.query(InventoryLocation).filter_by(
            organization_id=org_id, location_type='warehouse', is_active=True
        ).all()

        # Pending restock transfers
        pending_restocks = []
        if truck_location:
            pending_restocks = db.query(StockTransfer).filter(
                StockTransfer.to_location_id == truck_location.id,
                StockTransfer.status.in_(['requested', 'approved', 'in_transit']),
            ).all()

        return render_template('inventory/truck_stock.html',
            active_page='inventory', user=current_user, divisions=_get_divisions(),
            can_admin=current_user.role in ('owner', 'admin'),
            tech=tech, truck_location=truck_location, stocks=stocks,
            active_job=active_job, warehouses=warehouses,
            pending_restocks=pending_restocks,
        )
    finally:
        db.close()


# ── Quick Use ─────────────────────────────────────────────────────────────────

@truck_bp.route('/<int:tech_id>/quick-use', methods=['POST'])
@login_required
def quick_use(tech_id):
    db = get_session()
    try:
        # Permission check
        if current_user.role == 'technician':
            my_tech = db.query(Technician).filter_by(user_id=current_user.id).first()
            if not my_tech or my_tech.id != tech_id:
                flash('Permission denied.', 'error')
                return redirect(url_for('truck.truck_stock', tech_id=tech_id))

        job_id = int(request.form.get('job_id'))
        part_id = int(request.form.get('part_id'))
        quantity = float(request.form.get('quantity', 1))

        truck_location = db.query(InventoryLocation).filter_by(
            technician_id=tech_id, location_type='truck', is_active=True
        ).first()

        part = db.query(Part).filter_by(id=part_id).first()
        if not part:
            flash('Part not found.', 'error')
            return redirect(url_for('truck.truck_stock', tech_id=tech_id))

        data = {
            'part_id': part_id,
            'quantity': quantity,
            'unit_of_measure': part.unit_of_measure,
            'unit_cost': float(part.cost_price or 0),
            'markup_percentage': float(part.markup_percentage or 0),
            'sell_price_per_unit': float(part.sell_price or 0),
            'source_location_id': truck_location.id if truck_location else None,
            'is_billable': True,
            'notes': 'Logged from truck stock',
        }
        log_material(db, job_id, current_user.id, data)
        flash(f'Logged {quantity} x {part.name} on job.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('truck.truck_stock', tech_id=tech_id))


# ── Request Restock ───────────────────────────────────────────────────────────

@truck_bp.route('/<int:tech_id>/request-restock', methods=['POST'])
@login_required
def request_restock(tech_id):
    db = get_session()
    try:
        org_id = current_user.organization_id

        if current_user.role == 'technician':
            my_tech = db.query(Technician).filter_by(user_id=current_user.id).first()
            if not my_tech or my_tech.id != tech_id:
                flash('Permission denied.', 'error')
                return redirect(url_for('truck.truck_stock', tech_id=tech_id))

        truck_location = db.query(InventoryLocation).filter_by(
            technician_id=tech_id, location_type='truck', is_active=True
        ).first()
        if not truck_location:
            flash('No truck location found.', 'error')
            return redirect(url_for('truck.truck_stock', tech_id=tech_id))

        warehouse_id = int(request.form.get('warehouse_id'))
        part_ids = request.form.getlist('part_id[]')
        quantities = request.form.getlist('quantity[]')
        notes = request.form.get('notes', '')

        items_data = []
        for pid, qty in zip(part_ids, quantities):
            if pid and qty and int(qty) > 0:
                items_data.append({'part_id': int(pid), 'quantity': int(qty)})

        if not items_data:
            flash('Select at least one part.', 'error')
            return redirect(url_for('truck.truck_stock', tech_id=tech_id))

        transfer = StockTransfer(
            organization_id=org_id,
            transfer_number=generate_transfer_number(db),
            status='requested',
            from_location_id=warehouse_id,
            to_location_id=truck_location.id,
            notes=notes or f'Restock request from {truck_location.name}',
            requested_by=current_user.id,
        )
        db.add(transfer)
        db.flush()

        for item_data in items_data:
            part = db.query(Part).filter_by(id=item_data['part_id']).first()
            db.add(StockTransferItem(
                transfer_id=transfer.id,
                part_id=item_data['part_id'],
                quantity_requested=item_data['quantity'],
                unit_cost=float(part.cost_price or 0) if part else 0,
            ))

        db.commit()
        flash(f'Restock request {transfer.transfer_number} submitted.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('truck.truck_stock', tech_id=tech_id))
