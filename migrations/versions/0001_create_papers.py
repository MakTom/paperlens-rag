"""Create canonical paper metadata table."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "papers",
        sa.Column("arxiv_id", sa.String(32), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("text_kind", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("papers")
