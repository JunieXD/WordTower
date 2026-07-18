"""增加社交功能相关表和字段

Revision ID: 9df4c0d8d2b1
Revises: dd56af527a03
Create Date: 2026-04-05 23:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9df4c0d8d2b1'
down_revision: Union[str, Sequence[str], None] = 'dd56af527a03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_active_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('user_user_link', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_user_user_link_friend_status', ['friend_id', 'status'], unique=False)
        batch_op.create_index('ix_user_user_link_pair', ['user_id', 'friend_id'], unique=False)

    op.execute("UPDATE user_user_link SET created_at = updated_at WHERE created_at IS NULL")

    op.create_table(
        'friend_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('content', sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recipient_id'], ['user.id']),
        sa.ForeignKeyConstraint(['sender_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_friend_message_recipient_id', 'friend_message', ['recipient_id'], unique=False)
    op.create_index('ix_friend_message_sender_id', 'friend_message', ['sender_id'], unique=False)
    op.create_index('ix_friend_message_pair_created_at', 'friend_message', ['sender_id', 'recipient_id', 'created_at'], unique=False)
    op.create_index('ix_friend_message_recipient_read_at', 'friend_message', ['recipient_id', 'read_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_friend_message_recipient_read_at', table_name='friend_message')
    op.drop_index('ix_friend_message_pair_created_at', table_name='friend_message')
    op.drop_index('ix_friend_message_sender_id', table_name='friend_message')
    op.drop_index('ix_friend_message_recipient_id', table_name='friend_message')
    op.drop_table('friend_message')

    with op.batch_alter_table('user_user_link', schema=None) as batch_op:
        batch_op.drop_index('ix_user_user_link_pair')
        batch_op.drop_index('ix_user_user_link_friend_status')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_active_at')
