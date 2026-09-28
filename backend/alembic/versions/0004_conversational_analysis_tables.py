"""add_conversational_analysis_tables

Revision ID: 0004_conversational_tables
Revises: f355042a7291
Create Date: 2026-09-28 15:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_conversational_tables'
down_revision: Union[str, Sequence[str], None] = 'f355042a7291'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. conversations
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('project_id', sa.String(length=36), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='New Analysis Conversation'),
        sa.Column('state_revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('active_context_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_conversations_project_id', 'conversations', ['project_id'])
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'])
    op.create_index('ix_conversations_updated_at', 'conversations', ['updated_at'])

    # 2. conversation_messages
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('turn_id', sa.String(length=36), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('client_request_id', sa.String(length=128), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_conversation_messages_conversation_id', 'conversation_messages', ['conversation_id'])
    op.create_index('ix_conversation_messages_turn_id', 'conversation_messages', ['turn_id'])
    op.create_index('ix_conversation_messages_client_request_id', 'conversation_messages', ['client_request_id'])

    # 3. conversation_turns
    op.create_table(
        'conversation_turns',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_request_id', sa.String(length=128), nullable=False),
        sa.Column('user_message_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='accepted'),
        sa.Column('turn_type', sa.String(length=50), nullable=False, server_default='analysis'),
        sa.Column('result_id', sa.String(length=36), nullable=True),
        sa.Column('job_id', sa.String(length=36), nullable=True),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('conversation_id', 'client_request_id', name='uq_conv_turn_request')
    )
    op.create_index('ix_conversation_turns_conversation_id', 'conversation_turns', ['conversation_id'])
    op.create_index('ix_conversation_turns_client_request_id', 'conversation_turns', ['client_request_id'])

    # 4. conversation_datasets
    op.create_table(
        'conversation_datasets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='original'),
        sa.Column('acquisition_date', sa.String(length=50), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_conversation_datasets_conversation_id', 'conversation_datasets', ['conversation_id'])

    # 5. conversation_results
    op.create_table(
        'conversation_results',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('conversation_id', sa.String(length=36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('turn_id', sa.String(length=36), nullable=True),
        sa.Column('parent_result_id', sa.String(length=36), nullable=True),
        sa.Column('result_role', sa.String(length=50), nullable=False, server_default='original'),
        sa.Column('operation', sa.String(length=100), nullable=False),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('findings_json', sa.Text(), nullable=True),
        sa.Column('sections_json', sa.Text(), nullable=True),
        sa.Column('metrics_json', sa.Text(), nullable=True),
        sa.Column('mask_url', sa.String(length=512), nullable=True),
        sa.Column('source_dataset_ids_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_conversation_results_conversation_id', 'conversation_results', ['conversation_id'])
    op.create_index('ix_conversation_results_parent_result_id', 'conversation_results', ['parent_result_id'])


def downgrade() -> None:
    op.drop_table('conversation_results')
    op.drop_table('conversation_datasets')
    op.drop_table('conversation_turns')
    op.drop_table('conversation_messages')
    op.drop_table('conversations')
