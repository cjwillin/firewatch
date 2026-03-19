"""Add campgrounds table with FTS search

Revision ID: add_campgrounds_table
Revises: 65f00fee2244
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_campgrounds_table'
down_revision = '65f00fee2244'
branch_labels = None
depends_on = None


def upgrade():
    # Create campgrounds table
    op.create_table(
        'campgrounds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recreation_id', sa.String(), nullable=False, unique=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('preview_image_url', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_synced', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create FTS virtual table for fast search
    op.execute('''
        CREATE VIRTUAL TABLE campgrounds_fts USING fts5(
            recreation_id,
            name,
            city,
            state,
            content='campgrounds',
            content_rowid='id'
        )
    ''')
    
    # Trigger to keep FTS in sync on insert
    op.execute('''
        CREATE TRIGGER campgrounds_ai AFTER INSERT ON campgrounds BEGIN
            INSERT INTO campgrounds_fts(rowid, recreation_id, name, city, state)
            VALUES (new.id, new.recreation_id, new.name, new.city, new.state);
        END
    ''')
    
    # Trigger to keep FTS in sync on update
    op.execute('''
        CREATE TRIGGER campgrounds_au AFTER UPDATE ON campgrounds BEGIN
            UPDATE campgrounds_fts SET
                recreation_id = new.recreation_id,
                name = new.name,
                city = new.city,
                state = new.state
            WHERE rowid = new.id;
        END
    ''')
    
    # Trigger to keep FTS in sync on delete
    op.execute('''
        CREATE TRIGGER campgrounds_ad AFTER DELETE ON campgrounds BEGIN
            DELETE FROM campgrounds_fts WHERE rowid = old.id;
        END
    ''')
    
    # Index for location-based queries
    op.create_index('idx_campgrounds_location', 'campgrounds', ['state', 'city'])


def downgrade():
    op.execute('DROP TRIGGER IF EXISTS campgrounds_ad')
    op.execute('DROP TRIGGER IF EXISTS campgrounds_au')
    op.execute('DROP TRIGGER IF EXISTS campgrounds_ai')
    op.execute('DROP TABLE IF EXISTS campgrounds_fts')
    op.drop_index('idx_campgrounds_location', table_name='campgrounds')
    op.drop_table('campgrounds')
