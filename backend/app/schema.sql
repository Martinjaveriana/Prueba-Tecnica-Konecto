CREATE TABLE IF NOT EXISTS actuators (
    part_number TEXT PRIMARY KEY,
    alias TEXT NOT NULL,
    size SMALLINT NOT NULL,
    enclosure TEXT NOT NULL CHECK (enclosure IN ('weatherproof', 'explosionproof')),
    voltage_v SMALLINT NOT NULL,
    phases SMALLINT NOT NULL,
    current_type TEXT NOT NULL CHECK (current_type IN ('AC', 'DC', 'AC/DC')),
    motor_power_w SMALLINT,
    certifications TEXT[] NOT NULL,
    hazardous_classification TEXT[] NOT NULL,
    has_data BOOLEAN NOT NULL,
    source_page SMALLINT NOT NULL
);

CREATE INDEX IF NOT EXISTS actuators_alias_idx ON actuators (alias);

-- Values that depend on the service type. 'unspecified' is the 3-phase table, which gives a
-- single rating without saying whether it applies to On/Off or Modulating.
CREATE TABLE IF NOT EXISTS service_ratings (
    part_number TEXT NOT NULL REFERENCES actuators ON DELETE CASCADE,
    service TEXT NOT NULL CHECK (service IN ('on_off', 'modulating', 'unspecified')),
    torque_in_lbs INTEGER NOT NULL,
    torque_nm INTEGER NOT NULL,
    duty_cycle_pct SMALLINT NOT NULL,
    cycles_per_hour INTEGER,
    starts_per_hour INTEGER,
    PRIMARY KEY (part_number, service)
);

-- Values that depend on the power frequency. frequency_hz is NULL for 24 V models, whose
-- tables have a single value.
CREATE TABLE IF NOT EXISTS electrical_ratings (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    part_number TEXT NOT NULL REFERENCES actuators ON DELETE CASCADE,
    frequency_hz SMALLINT CHECK (frequency_hz IN (50, 60)),
    speed_sec INTEGER NOT NULL,
    fla_a NUMERIC(4, 1) NOT NULL,
    lra_a NUMERIC(4, 1) NOT NULL,
    UNIQUE NULLS NOT DISTINCT (part_number, frequency_hz)
);

-- Conversations. A turn is saved as one user message and one assistant message, together.
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    -- Assistant messages only: what the tools returned in that turn, and how it was produced.
    products JSONB NOT NULL DEFAULT '[]',
    needs_clarification BOOLEAN NOT NULL DEFAULT false,
    debug JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_session_idx ON messages (session_id, id);
