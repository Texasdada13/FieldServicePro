"""Routes for insurance policy management."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models.database import get_session
from models.insurance import InsurancePolicy
from models.division import Division
from web.utils.file_utils import save_uploaded_file, get_entity_documents
from web.auth import role_required

insurance_bp = Blueprint('insurance', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _tpl_vars(**extra):
    base = dict(active_page='insurance', user=current_user, divisions=_get_divisions())
    base.update(extra)
    return base


@insurance_bp.route('/settings/insurance')
@login_required
def insurance_list():
    db = get_session()
    try:
        policies = db.query(InsurancePolicy).order_by(InsurancePolicy.end_date.asc()).all()
        for p in policies:
            old = p.status
            p.update_status()
            if p.status != old:
                db.commit()

        active = [p for p in policies if p.status == 'active']
        expiring = [p for p in policies if p.status == 'expiring_soon']
        total_coverage = sum(float(p.coverage_amount or 0) for p in active)
        total_premium = sum(float(p.premium or 0) for p in active)

        return render_template('insurance/insurance_list.html',
                               **_tpl_vars(
                                   policies=policies,
                                   active_count=len(active),
                                   expiring_count=len(expiring),
                                   expired_count=len([p for p in policies if p.status == 'expired']),
                                   total_coverage=total_coverage,
                                   total_premium=total_premium,
                                   policy_types=InsurancePolicy.POLICY_TYPES,
                               ))
    finally:
        db.close()


@insurance_bp.route('/settings/insurance/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def insurance_new():
    db = get_session()
    try:
        if request.method == 'POST':
            f = request.form
            policy = InsurancePolicy(
                policy_type=f.get('policy_type', 'general_liability'),
                policy_number=f.get('policy_number', '').strip(),
                provider=f.get('provider', '').strip(),
                coverage_amount=float(f.get('coverage_amount') or 0),
                deductible=float(f['deductible']) if f.get('deductible') else None,
                premium=float(f['premium']) if f.get('premium') else None,
                auto_renew=f.get('auto_renew') == 'on',
                renewal_reminder_days=int(f.get('renewal_reminder_days') or 30),
                division_id=int(f['division_id']) if f.get('division_id') else None,
                notes=f.get('notes', '').strip() or None,
                created_by=current_user.id,
            )
            for df in ['start_date', 'end_date']:
                val = f.get(df, '').strip()
                if val:
                    try:
                        setattr(policy, df, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        flash(f'Invalid {df.replace("_", " ")}.', 'danger')
                        return redirect(request.url)

            policy.update_status()
            db.add(policy)
            db.flush()

            for file in request.files.getlist('documents'):
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='insurance_policy',
                                           entity_id=policy.id, category='insurance',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash('Insurance policy created.', 'success')
            return redirect(url_for('insurance.insurance_detail', policy_id=policy.id))

        divs = db.query(Division).filter_by(organization_id=current_user.organization_id).all()
        return render_template('insurance/insurance_form.html',
                               **_tpl_vars(policy=None, all_divisions=divs,
                                           policy_types=InsurancePolicy.POLICY_TYPES))
    finally:
        db.close()


@insurance_bp.route('/settings/insurance/<int:policy_id>')
@login_required
def insurance_detail(policy_id):
    db = get_session()
    try:
        policy = db.query(InsurancePolicy).filter_by(id=policy_id).first()
        if not policy:
            abort(404)
        documents = get_entity_documents(db, 'insurance_policy', policy.id)
        return render_template('insurance/insurance_detail.html',
                               **_tpl_vars(policy=policy, documents=documents))
    finally:
        db.close()


@insurance_bp.route('/settings/insurance/<int:policy_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def insurance_edit(policy_id):
    db = get_session()
    try:
        policy = db.query(InsurancePolicy).filter_by(id=policy_id).first()
        if not policy:
            abort(404)

        if request.method == 'POST':
            f = request.form
            policy.policy_type = f.get('policy_type', policy.policy_type)
            policy.policy_number = f.get('policy_number', '').strip()
            policy.provider = f.get('provider', '').strip()
            policy.coverage_amount = float(f.get('coverage_amount') or 0)
            policy.deductible = float(f['deductible']) if f.get('deductible') else None
            policy.premium = float(f['premium']) if f.get('premium') else None
            policy.auto_renew = f.get('auto_renew') == 'on'
            policy.renewal_reminder_days = int(f.get('renewal_reminder_days') or 30)
            policy.division_id = int(f['division_id']) if f.get('division_id') else None
            policy.notes = f.get('notes', '').strip() or None

            for df in ['start_date', 'end_date']:
                val = f.get(df, '').strip()
                if val:
                    try:
                        setattr(policy, df, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass

            policy.update_status()

            for file in request.files.getlist('documents'):
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='insurance_policy',
                                           entity_id=policy.id, category='insurance',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash('Insurance policy updated.', 'success')
            return redirect(url_for('insurance.insurance_detail', policy_id=policy.id))

        divs = db.query(Division).filter_by(organization_id=current_user.organization_id).all()
        return render_template('insurance/insurance_form.html',
                               **_tpl_vars(policy=policy, all_divisions=divs,
                                           policy_types=InsurancePolicy.POLICY_TYPES))
    finally:
        db.close()


@insurance_bp.route('/settings/insurance/<int:policy_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def insurance_delete(policy_id):
    db = get_session()
    try:
        policy = db.query(InsurancePolicy).filter_by(id=policy_id).first()
        if not policy:
            abort(404)
        db.delete(policy)
        db.commit()
        flash('Insurance policy deleted.', 'success')
    finally:
        db.close()
    return redirect(url_for('insurance.insurance_list'))


@insurance_bp.route('/settings/insurance/<int:policy_id>/coi')
@login_required
def insurance_coi(policy_id):
    db = get_session()
    try:
        policy = db.query(InsurancePolicy).filter_by(id=policy_id).first()
        if not policy:
            abort(404)
        return render_template('insurance/coi_print.html',
                               **_tpl_vars(policy=policy))
    finally:
        db.close()
