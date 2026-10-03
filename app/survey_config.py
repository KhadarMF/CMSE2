"""Choose the required survey consistently across project evidence and reports."""


OFF_GRID_SURVEY = (
    "Solar Off-Grid Survey & Load Assessment", "site_surveys", "site-survey"
)
PUMP_SURVEY = (
    "Solar Pumping Site Survey", "solar_pump_surveys", "solar-pump-survey"
)


def survey_group(project):
    return PUMP_SURVEY if "pump" in (project.project_type or "").casefold() else OFF_GRID_SURVEY
