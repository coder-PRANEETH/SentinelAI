"""
utils/validators.py
Marshmallow schemas for all API request bodies.
Returns field-level error details on invalid input.
"""

from marshmallow import Schema, fields, validate, validates, ValidationError, EXCLUDE

# ─────────────────────────────────────────────────────────────────────────────
# Allowed enumerations
# ─────────────────────────────────────────────────────────────────────────────

VALID_INCIDENT_TYPES = [
    "Vehicle Breakdown",
    "Road Blockage",
    "Fallen Tree",
    "Traffic Disruption",
    "Road Closure",
]

VALID_PRIORITIES = ["P1", "P2", "P3", "P4"]

VALID_STATUSES = [
    "REPORTED", "UNDER_ASSESSMENT", "RESOURCES_ASSIGNED",
    "IN_PROGRESS", "RESOLVED", "CLOSED", "CANCELLED",
]


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

class LoginSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    username = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    password = fields.Str(required=True, validate=validate.Length(min=1))


# ─────────────────────────────────────────────────────────────────────────────
# Predict
# ─────────────────────────────────────────────────────────────────────────────

class PredictSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    incident_type = fields.Str(
        required=False,
        validate=validate.OneOf(VALID_INCIDENT_TYPES),
    )
    event_type_grouped = fields.Str(load_default="unknown")
    event_cause = fields.Str(load_default="unknown")
    corridor = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
    )
    location = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=500),
    )
    vehicle_type = fields.Str(load_default="unknown")
    veh_type_grouped = fields.Str(load_default="unknown")
    police_station_grouped = fields.Str(load_default="unknown")
    latitude = fields.Float(load_default=0.0)
    longitude = fields.Float(load_default=0.0)
    location_cluster = fields.Int(load_default=-1)
    hour_of_day = fields.Int(load_default=12, validate=validate.Range(0, 23))
    month = fields.Int(load_default=1, validate=validate.Range(1, 12))
    day_of_week = fields.Str(load_default="unknown")
    is_peak_hour = fields.Int(load_default=0, validate=validate.OneOf([0, 1]))
    is_weekend = fields.Int(load_default=0, validate=validate.OneOf([0, 1]))
    is_cascaded = fields.Int(load_default=0, validate=validate.OneOf([0, 1]))
    cascade_size = fields.Int(load_default=1, validate=validate.Range(min=1))
    raw_transcript = fields.Str(load_default=None, allow_none=True)


# ─────────────────────────────────────────────────────────────────────────────
# Historical Search
# ─────────────────────────────────────────────────────────────────────────────

class HistoricalSearchSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    query_text = fields.Str(required=False, load_default=None, allow_none=True)
    query = fields.Str(required=False, load_default=None, allow_none=True)  # alias
    top_k = fields.Int(load_default=10, validate=validate.Range(min=1, max=100))
    min_similarity = fields.Float(load_default=0.7, validate=validate.Range(0.0, 1.0))

    def get_query(self, data: dict) -> str:
        return data.get("query_text") or data.get("query") or ""


# ─────────────────────────────────────────────────────────────────────────────
# Resource allocation / release
# ─────────────────────────────────────────────────────────────────────────────

class ResourcesSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    officers = fields.Int(load_default=0, validate=validate.Range(min=0))
    patrol_vehicles = fields.Int(load_default=0, validate=validate.Range(min=0))
    vehicles = fields.Int(load_default=0, validate=validate.Range(min=0))  # alias
    tow_trucks = fields.Int(load_default=0, validate=validate.Range(min=0))
    barricades = fields.Int(load_default=0, validate=validate.Range(min=0))


class AllocateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    incident_id = fields.Str(required=True)
    resources = fields.Nested(ResourcesSchema, required=True)


class ReleaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    incident_id = fields.Str(required=True)
    dispatch_id = fields.Str(required=True)


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────────

class DispatchSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    incident_id = fields.Str(required=True)
    station_id = fields.Str(required=True)
    resources_dispatched = fields.Nested(ResourcesSchema, required=True)
    override = fields.Bool(load_default=False)
    override_reason = fields.Str(load_default=None, allow_none=True)
    operator_id = fields.Str(required=False, allow_none=True)
    notes = fields.Str(load_default=None, allow_none=True)

    @validates("override_reason")
    def validate_override_reason(self, value, **kwargs):
        """Validated at route level because we need access to 'override' field too."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Incident Feedback
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    incident_id = fields.Str(required=True)
    actual_priority = fields.Str(
        required=True,
        validate=validate.OneOf(VALID_PRIORITIES),
    )
    actual_resolution_time_minutes = fields.Int(
        required=True,
        validate=validate.Range(min=0),
    )
    road_closure_occurred = fields.Bool(required=True)
    outcome_description = fields.Str(load_default=None, allow_none=True)
    operator_id = fields.Str(load_default=None, allow_none=True)


# ─────────────────────────────────────────────────────────────────────────────
# Station readiness query params (not a body — parsed from request.args)
# ─────────────────────────────────────────────────────────────────────────────

class ReadinessQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    officers = fields.Int(load_default=0, validate=validate.Range(min=0))
    patrol_vehicles = fields.Int(load_default=0, validate=validate.Range(min=0))
    tow_trucks = fields.Int(load_default=0, validate=validate.Range(min=0))
    barricades = fields.Int(load_default=0, validate=validate.Range(min=0))
    min_readiness = fields.Float(load_default=0.0, validate=validate.Range(0.0, 100.0))
    sort = fields.Str(load_default="readiness_desc")
