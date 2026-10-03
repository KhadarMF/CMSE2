"""Phase 20K split off-grid and solar pumping surveys

Revision ID: b20k0000a001
Revises: b20i0000a001
"""
from alembic import op
import sqlalchemy as sa

revision = 'b20k0000a001'
down_revision = 'b20i0000a001'
branch_labels = None
depends_on = None

def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('site_survey_form')}
    with op.batch_alter_table('site_survey_form') as batch:
        if 'monthly_consumption_kwh' not in columns:
            batch.add_column(sa.Column('monthly_consumption_kwh', sa.String(length=80), nullable=True))
        if 'monthly_electricity_bill' not in columns:
            batch.add_column(sa.Column('monthly_electricity_bill', sa.String(length=80), nullable=True))
        if 'power_supply' not in columns:
            batch.add_column(sa.Column('power_supply', sa.String(length=80), nullable=True))
        if 'connected_load_kw' not in columns:
            batch.add_column(sa.Column('connected_load_kw', sa.String(length=80), nullable=True))
        if 'estimated_peak_load_kw' not in columns:
            batch.add_column(sa.Column('estimated_peak_load_kw', sa.String(length=80), nullable=True))
        if 'day_consumption_kwh' not in columns:
            batch.add_column(sa.Column('day_consumption_kwh', sa.String(length=80), nullable=True))
        if 'night_consumption_kwh' not in columns:
            batch.add_column(sa.Column('night_consumption_kwh', sa.String(length=80), nullable=True))
        if 'critical_load_kw' not in columns:
            batch.add_column(sa.Column('critical_load_kw', sa.String(length=80), nullable=True))
        if 'critical_energy_kwh' not in columns:
            batch.add_column(sa.Column('critical_energy_kwh', sa.String(length=80), nullable=True))
        if 'inverter_battery_location' not in columns:
            batch.add_column(sa.Column('inverter_battery_location', sa.String(length=200), nullable=True))
    if 'solar_pump_survey_form' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('solar_pump_survey_form',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('project.id'), nullable=False, unique=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('created_at', sa.DateTime()), sa.Column('approval_status', sa.String(80)), sa.Column('manager_comments', sa.Text()),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('user.id')), sa.Column('reviewed_at', sa.DateTime()),
        sa.Column('survey_date', sa.Date()), sa.Column('surveyed_by', sa.String(150)), sa.Column('gps_coordinates', sa.String(150)),
        sa.Column('water_source', sa.String(100)), sa.Column('total_depth_m', sa.String(80)), sa.Column('static_water_level_m', sa.String(80)),
        sa.Column('dynamic_water_level_m', sa.String(80)), sa.Column('required_flow_m3h', sa.String(80)), sa.Column('required_water_m3day', sa.String(80)),
        sa.Column('vertical_delivery_height_m', sa.String(80)), sa.Column('horizontal_pipe_distance_m', sa.String(80)), sa.Column('pipe_diameter', sa.String(80)),
        sa.Column('existing_pump', sa.String(200)), sa.Column('tank_details', sa.String(200)), sa.Column('solar_area', sa.String(150)),
        sa.Column('shading_status', sa.String(120)), sa.Column('access_road', sa.String(150)), sa.Column('remarks', sa.Text())
    )

def downgrade():
    op.drop_table('solar_pump_survey_form')
    with op.batch_alter_table('site_survey_form') as batch:
        for col in ['inverter_battery_location','critical_energy_kwh','critical_load_kw','night_consumption_kwh','day_consumption_kwh','estimated_peak_load_kw','connected_load_kw','power_supply','monthly_electricity_bill','monthly_consumption_kwh']:
            batch.drop_column(col)
