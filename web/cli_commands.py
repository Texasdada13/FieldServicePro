"""
Flask CLI commands for contract automation.
Register in app.py then run: flask contracts run-automation

Example crontab (run every hour):
0 * * * * cd /app && flask contracts run-automation >> /var/log/fsp_automation.log 2>&1
"""

import click
from flask import Blueprint

automation_cli = Blueprint('contracts_cli', __name__, cli_group='contracts')


@automation_cli.cli.command('run-automation')
@click.option('--verbose', is_flag=True, default=False)
def run_automation(verbose):
    """Run all contract & SLA automation checks."""
    from models.database import get_session
    from web.utils.contract_automation import run_all_automations

    db = get_session()
    try:
        results = run_all_automations(db)
        click.echo(f"[Contract Automation] {results}")
        if verbose:
            for key, val in results.items():
                click.echo(f"  {key}: {val}")
    except Exception as e:
        click.echo(f"[Contract Automation] ERROR: {e}", err=True)
        raise
    finally:
        db.close()


@automation_cli.cli.command('expire-contracts')
def expire_contracts():
    """Mark overdue contracts as expired."""
    from models.database import get_session
    from web.utils.contract_automation import check_expired_contracts
    db = get_session()
    try:
        result = check_expired_contracts(db)
        click.echo(f"Expired: {result['expired']} contract(s)")
    finally:
        db.close()


@automation_cli.cli.command('create-renewals')
def create_renewals():
    """Create renewal drafts for auto-renew contracts nearing expiry."""
    from models.database import get_session
    from web.utils.contract_automation import create_renewal_drafts
    db = get_session()
    try:
        result = create_renewal_drafts(db)
        click.echo(f"Renewal drafts created: {result['renewal_drafts_created']}")
    finally:
        db.close()


@automation_cli.cli.command('generate-jobs')
def generate_jobs():
    """Generate scheduled jobs from contract line items."""
    from models.database import get_session
    from web.utils.contract_automation import generate_scheduled_jobs
    db = get_session()
    try:
        result = generate_scheduled_jobs(db)
        click.echo(f"Jobs created: {result['scheduled_jobs_created']}")
    finally:
        db.close()


@automation_cli.cli.command('check-sla-breaches')
def check_sla():
    """Flag overdue SLA jobs."""
    from models.database import get_session
    from web.utils.contract_automation import check_sla_breaches
    db = get_session()
    try:
        result = check_sla_breaches(db)
        click.echo(f"SLA breaches flagged: {result['sla_breaches_flagged']}")
    finally:
        db.close()
