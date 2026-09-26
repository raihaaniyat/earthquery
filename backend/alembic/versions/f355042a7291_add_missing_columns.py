"""add_missing_columns

Revision ID: f355042a7291
Revises: 0002_external_providers
Create Date: 2026-09-26 16:10:16.390527

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f355042a7291'
down_revision: Union[str, Sequence[str], None] = '0002_external_providers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to analysis_jobs
    op.add_column('analysis_jobs', sa.Column('lease_holder', sa.String(length=100), nullable=True))
    op.add_column('analysis_jobs', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('analysis_jobs', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add missing column to finding_evidence
    op.add_column('finding_evidence', sa.Column('observation_scope', sa.String(length=50), nullable=True))
    
    # Add missing column and index to findings
    op.add_column('findings', sa.Column('step_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_findings_step_id'), 'findings', ['step_id'], unique=False)
    op.create_foreign_key('fk_findings_step_id_execution_steps', 'findings', 'execution_steps', ['step_id'], ['id'], ondelete='SET NULL')
    
    # Add missing columns to outbox_events (with default for max_attempts)
    op.add_column('outbox_events', sa.Column('max_attempts', sa.Integer(), server_default='5', nullable=False))
    op.add_column('outbox_events', sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('outbox_events', sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('outbox_events', 'delivered_at')
    op.drop_column('outbox_events', 'last_attempt_at')
    op.drop_column('outbox_events', 'max_attempts')
    
    op.drop_constraint('fk_findings_step_id_execution_steps', 'findings', type_='foreignkey')
    op.drop_index(op.f('ix_findings_step_id'), table_name='findings')
    op.drop_column('findings', 'step_id')
    
    op.drop_column('finding_evidence', 'observation_scope')
    
    op.drop_column('analysis_jobs', 'completed_at')
    op.drop_column('analysis_jobs', 'started_at')
    op.drop_column('analysis_jobs', 'lease_holder')
