"""Business logic for logging materials used on jobs."""
from datetime import datetime
from models.job_material import JobMaterial
from models.part import Part
from models.inventory import InventoryStock, InventoryTransaction, InventoryLocation
from models.job import Job


def get_job_material_summary(db, job_id):
    """Calculate material cost/sell/margin totals for a job."""
    materials = db.query(JobMaterial).filter_by(job_id=job_id).all()
    total_cost = sum(float(m.total_cost or 0) for m in materials)
    total_sell = sum(float(m.total_sell or 0) for m in materials if m.is_billable)
    billable_cost = sum(float(m.total_cost or 0) for m in materials if m.is_billable)
    warranty_cost = sum(float(m.total_cost or 0) for m in materials if m.is_warranty_replacement)
    margin = total_sell - billable_cost
    return {
        'total_cost': round(total_cost, 2),
        'total_sell': round(total_sell, 2),
        'billable_cost': round(billable_cost, 2),
        'warranty_cost': round(warranty_cost, 2),
        'margin': round(margin, 2),
        'margin_pct': round((margin / total_sell * 100) if total_sell > 0 else 0, 1),
        'count': len(materials),
    }


def log_material(db, job_id, added_by, data):
    """
    Log a material used on a job. Decrements inventory if from catalog stock.
    data keys: part_id, custom_description, quantity, unit_of_measure,
               unit_cost, markup_percentage, sell_price_per_unit,
               source_location_id, is_billable, is_warranty_replacement,
               notes, phase_id
    """
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise ValueError(f'Job {job_id} not found')

    qty = float(data.get('quantity', 1))
    unit_cost = float(data.get('unit_cost', 0))
    sell_per = float(data.get('sell_price_per_unit', 0))
    markup = float(data.get('markup_percentage', 0))

    # Auto-calculate sell price if not provided
    if sell_per == 0 and unit_cost > 0 and markup > 0:
        sell_per = round(unit_cost * (1 + markup / 100), 2)

    jm = JobMaterial(
        organization_id=job.organization_id,
        job_id=job_id,
        phase_id=data.get('phase_id') or None,
        project_id=getattr(job, 'project_id', None),
        part_id=data.get('part_id') or None,
        custom_description=data.get('custom_description') or None,
        quantity=qty,
        unit_of_measure=data.get('unit_of_measure', 'each'),
        unit_cost=unit_cost,
        markup_percentage=markup,
        sell_price_per_unit=sell_per,
        total_cost=round(qty * unit_cost, 2),
        total_sell=round(qty * sell_per, 2),
        source_location_id=data.get('source_location_id') or None,
        is_billable=data.get('is_billable', True),
        is_warranty_replacement=data.get('is_warranty_replacement', False),
        added_by=added_by,
        notes=data.get('notes') or None,
        status='logged',
    )
    db.add(jm)

    # Decrement inventory if from catalog stock at a specific location
    if jm.part_id and jm.source_location_id:
        stock = db.query(InventoryStock).filter_by(
            part_id=jm.part_id, location_id=jm.source_location_id
        ).first()
        if stock:
            qty_int = int(qty)
            stock.quantity_on_hand = max(0, stock.quantity_on_hand - qty_int)

            db.add(InventoryTransaction(
                organization_id=job.organization_id,
                part_id=jm.part_id,
                location_id=jm.source_location_id,
                transaction_type='issued',
                quantity=-qty_int,
                unit_cost=unit_cost,
                job_id=job_id,
                reference_number=job.job_number,
                notes=f'Used on Job {job.job_number}: {job.title}',
                created_by=added_by,
            ))

    db.commit()
    return jm


def return_material(db, job_material_id, performed_by, quantity_returned=None, notes=''):
    """Return a material — creates negative entry and restores inventory."""
    original = db.query(JobMaterial).filter_by(id=job_material_id).first()
    if not original:
        raise ValueError(f'JobMaterial {job_material_id} not found')

    qty = quantity_returned or float(original.quantity)

    return_jm = JobMaterial(
        organization_id=original.organization_id,
        job_id=original.job_id,
        phase_id=original.phase_id,
        project_id=original.project_id,
        part_id=original.part_id,
        custom_description=(original.custom_description or original.display_name) + ' [RETURN]',
        quantity=-qty,
        unit_of_measure=original.unit_of_measure,
        unit_cost=original.unit_cost,
        markup_percentage=original.markup_percentage,
        sell_price_per_unit=original.sell_price_per_unit,
        total_cost=round(-qty * float(original.unit_cost or 0), 2),
        total_sell=round(-qty * float(original.sell_price_per_unit or 0), 2),
        source_location_id=original.source_location_id,
        is_billable=original.is_billable,
        added_by=performed_by,
        notes=notes or f'Return from Job',
        status='logged',
    )
    db.add(return_jm)

    # Restore inventory
    if original.part_id and original.source_location_id:
        stock = db.query(InventoryStock).filter_by(
            part_id=original.part_id, location_id=original.source_location_id
        ).first()
        if stock:
            qty_int = int(qty)
            stock.quantity_on_hand += qty_int

            job = db.query(Job).filter_by(id=original.job_id).first()
            db.add(InventoryTransaction(
                organization_id=original.organization_id,
                part_id=original.part_id,
                location_id=original.source_location_id,
                transaction_type='returned',
                quantity=qty_int,
                unit_cost=float(original.unit_cost or 0),
                job_id=original.job_id,
                reference_number=job.job_number if job else None,
                notes=notes or f'Return from Job',
                created_by=performed_by,
            ))

    db.commit()
    return return_jm


def get_billable_materials_for_invoice(db, job_id):
    """Return all billable, verified+ materials for invoice population."""
    materials = db.query(JobMaterial).filter(
        JobMaterial.job_id == job_id,
        JobMaterial.is_billable == True,
        JobMaterial.status.in_(['verified', 'invoiced']),
        JobMaterial.quantity > 0,
    ).all()
    return [{
        'description': m.display_name,
        'quantity': float(m.quantity),
        'unit': m.unit_of_measure or 'each',
        'unit_price': float(m.sell_price_per_unit or 0),
        'total': float(m.total_sell or 0),
        'job_material_id': m.id,
    } for m in materials]
