"""resize pgvector dimensions to 1024

Revision ID: d123456789ab
Revises: c97ba63dc720
Create Date: 2026-05-30 19:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd123456789ab'
down_revision = 'c97ba63dc720'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Resize the vector column to 1024 for Mistral
    op.execute('ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024);')

def downgrade() -> None:
    # Revert to 768 for Ollama
    op.execute('ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(768);')
