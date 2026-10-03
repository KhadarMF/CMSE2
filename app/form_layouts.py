"""Presentation sections; field names and persistence remain in FORM_CONFIG."""
FORM_LAYOUTS = {
    "site-survey": [
        ("Survey visit", "Start with the visit details and the site's current power supply.", "survey_date surveyed_by gps_coordinates existing_power_source power_supply"),
        ("Energy & load assessment", "Record consumption and the loads the new system needs to support.", "monthly_consumption_kwh monthly_electricity_bill ac_loads connected_load_kw estimated_peak_load_kw total_daily_consumption_kwh day_consumption_kwh night_consumption_kwh critical_load_kw critical_energy_kwh"),
        ("Installation site", "Assess the available space, shading and installation conditions.", "available_space roof_type roof_condition shading_status earthing_condition inverter_battery_location access_road"),
        ("Survey notes", "Add requirements or observations that the design team should know.", "remarks"),
    ],
    "solar-pump-survey": [
        ("Survey visit", "Identify the visit, surveyor and water source.", "survey_date surveyed_by gps_coordinates water_source"),
        ("Water & pumping requirements", "Record water levels and the flow needed at the site.", "total_depth_m static_water_level_m dynamic_water_level_m required_flow_m3h required_water_m3day existing_pump"),
        ("Delivery & installation", "Describe the pipe route, storage tank and solar installation area.", "vertical_delivery_height_m horizontal_pipe_distance_m pipe_diameter tank_details solar_area shading_status access_road"),
        ("Survey notes", "Add site observations and any special requirements.", "remarks"),
    ],
    "daily-site-report": [
        ("Site & attendance", "Record today's site conditions and the team on site.", "report_date site_location weather site_supervisor manpower employees_present employees_absent normal_hours overtime_hours"),
        ("Work & progress", "Describe planned work, completed activities and resources used.", "planned_activities work_done_today completed_quantity quantity_unit materials_used tools_equipment_used progress_percentage"),
        ("Delays & safety", "Flag issues that need attention or a decision.", "delayed_activities delay_reason issues_challenges safety_notes"),
        ("Next steps", "Prepare the team for the next working day.", "next_day_plan remarks"),
    ],
}


def form_sections(form_key, fields):
    remaining = {field[0]: field for field in fields}
    sections = []
    for title, description, names in FORM_LAYOUTS.get(form_key, []):
        group = [remaining.pop(name) for name in names.split() if name in remaining]
        if group:
            sections.append({"title": title, "description": description, "fields": group})
    if remaining:
        sections.append({"title": "Form details", "description": "Complete the information for this project record.", "fields": list(remaining.values())})
    return sections
