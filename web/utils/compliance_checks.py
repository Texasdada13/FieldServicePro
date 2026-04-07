"""Compliance checks for job workflow transitions and dashboard alerts."""
from datetime import date, timedelta


def get_job_compliance_status(db, job_id):
    """
    Get overall compliance status for a job.
    Returns dict with status ('clear', 'warning', 'blocked') and details.
    """
    from models.permit import Permit

    issues = []
    blockers = []

    permits = db.query(Permit).filter_by(job_id=job_id).all()
    for p in permits:
        if p.status in ('inspection_required', 'inspection_failed'):
            blockers.append({
                'type': 'permit', 'id': p.id,
                'message': f'{p.type_display} permit ({p.permit_number or "no number"}) -- {p.status_display}',
                'severity': 'danger',
            })
        elif p.is_expiring_soon:
            issues.append({
                'type': 'permit', 'id': p.id,
                'message': f'{p.type_display} permit expiring {p.expiry_date.strftime("%b %d, %Y")}',
                'severity': 'warning',
            })
        elif p.is_expired:
            blockers.append({
                'type': 'permit', 'id': p.id,
                'message': f'{p.type_display} permit expired {p.expiry_date.strftime("%b %d, %Y")}',
                'severity': 'danger',
            })

    status = 'blocked' if blockers else ('warning' if issues else 'clear')
    return {'status': status, 'blockers': blockers, 'issues': issues, 'all_items': blockers + issues}


def check_job_can_start(db, job_id):
    """Check if a job can transition to 'in_progress'. Returns (ok, warnings)."""
    from models.permit import Permit

    warnings = []

    # Check for blocking permits
    permits = db.query(Permit).filter_by(job_id=job_id).all()
    for p in permits:
        if p.status in ('inspection_required', 'inspection_failed'):
            warnings.append(f"Permit {p.permit_number or '#' + str(p.id)} -- {p.status_display}")
        elif p.is_expired:
            warnings.append(f"Permit {p.permit_number or '#' + str(p.id)} expired {p.expiry_date.strftime('%b %d, %Y') if p.expiry_date else ''}")

    # Check technician certifications
    try:
        from models.job import Job
        job = db.query(Job).filter_by(id=job_id).first()
        if job and job.assigned_technician_id:
            ok, cert_warns = check_technician_certifications_for_job(
                db, job.assigned_technician_id, job_id)
            warnings.extend(cert_warns)
    except Exception:
        pass

    return len(warnings) == 0, warnings


def check_job_can_complete(db, job_id):
    """Check if a job can transition to 'completed'. Returns (ok, warnings)."""
    from models.permit import Permit
    warnings = []
    blocking = Permit.get_blocking_permits(db, job_id)
    for p in blocking:
        warnings.append(f"Permit {p.permit_number or '#' + str(p.id)} -- {p.status_display}")
    return len(warnings) == 0, warnings


def check_technician_certifications_for_job(db, technician_id, job_id):
    """
    Check if a technician has the required certifications for a job.
    Returns (ok, warnings).
    """
    warnings = []

    try:
        from models.job import Job
        from models.certification import TechnicianCertification, JobCertificationRequirement

        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return True, []

        job_type = getattr(job, 'job_type', None)
        if not job_type:
            return True, []

        # Check job-type requirements
        requirements = db.query(JobCertificationRequirement).filter_by(
            job_type=job_type, is_mandatory=True).all()
        for req in requirements:
            cert = db.query(TechnicianCertification).filter_by(
                technician_id=technician_id,
                certification_type=req.certification_type,
            ).first()
            if not cert or not cert.is_valid:
                type_label = dict(TechnicianCertification.CERT_TYPES).get(
                    req.certification_type, req.certification_type)
                warnings.append(f"Missing or expired certification: {type_label} (required)")

        # Check for expired required certs
        tech_certs = db.query(TechnicianCertification).filter_by(
            technician_id=technician_id, is_required=True).all()
        for cert in tech_certs:
            if cert.is_expired:
                warnings.append(
                    f"Required certification expired: {cert.certification_name} "
                    f"(expired {cert.expiry_date.strftime('%b %d, %Y')})")

    except Exception:
        pass

    return len(warnings) == 0, warnings


def check_invoice_can_pay(db, invoice_id):
    """
    Check if an invoice can be marked as paid (lien waiver check).
    Returns (ok, warnings). Soft block — caller decides whether to proceed.
    """
    warnings = []
    try:
        from models.lien_waiver import LienWaiver
        from models.invoice import Invoice

        invoice = db.query(Invoice).filter_by(id=invoice_id).first()
        if not invoice or not invoice.job_id:
            return True, []

        # Check for outstanding lien waivers on this job
        pending_waivers = db.query(LienWaiver).filter(
            LienWaiver.job_id == invoice.job_id,
            LienWaiver.status.notin_(['accepted']),
        ).all()

        for w in pending_waivers:
            warnings.append(
                f"Lien waiver from {w.party_name} ({w.type_display}) is {w.status_display}")

    except Exception:
        pass

    return len(warnings) == 0, warnings


def get_all_compliance_alerts(db):
    """
    Get all active compliance alerts for the dashboard.
    Returns list of alert dicts sorted by severity.
    """
    alerts = []

    # Expiring permits
    try:
        from models.permit import Permit
        for p in Permit.get_expiring_soon(db):
            alerts.append({
                'type': 'permit', 'severity': 'warning',
                'message': f'Permit {p.permit_number or "#" + str(p.id)} expires {p.expiry_date.strftime("%b %d")}',
                'link': f'/permits/{p.id}',
            })
        for p in Permit.get_needing_inspection(db):
            alerts.append({
                'type': 'permit', 'severity': 'danger',
                'message': f'Permit {p.permit_number or "#" + str(p.id)} -- {p.status_display}',
                'link': f'/permits/{p.id}',
            })
    except Exception:
        pass

    # Expiring insurance
    try:
        from models.insurance import InsurancePolicy
        expiring_policies = db.query(InsurancePolicy).filter(
            InsurancePolicy.end_date >= date.today(),
            InsurancePolicy.status.notin_(['cancelled', 'expired']),
        ).all()
        for p in expiring_policies:
            if p.is_expiring_soon:
                alerts.append({
                    'type': 'insurance', 'severity': 'warning',
                    'message': f'{p.type_display} policy expires {p.end_date.strftime("%b %d")} ({p.days_until_expiry}d)',
                    'link': f'/settings/insurance/{p.id}',
                })
    except Exception:
        pass

    # Expiring certifications
    try:
        from models.certification import TechnicianCertification
        certs = db.query(TechnicianCertification).filter(
            TechnicianCertification.expiry_date.isnot(None),
            TechnicianCertification.expiry_date >= date.today(),
            TechnicianCertification.status.notin_(['suspended', 'revoked', 'expired']),
        ).all()
        for c in certs:
            if c.is_expiring_soon:
                tech_name = c.technician.full_name if c.technician else 'Unknown'
                alerts.append({
                    'type': 'certification', 'severity': 'warning',
                    'message': f'{tech_name}: {c.certification_name} expires {c.expiry_date.strftime("%b %d")}',
                    'link': f'/settings/technicians/{c.technician_id}/certifications',
                })
    except Exception:
        pass

    # Sort by severity
    severity_order = {'danger': 0, 'warning': 1, 'info': 2}
    alerts.sort(key=lambda a: severity_order.get(a['severity'], 3))

    return alerts
