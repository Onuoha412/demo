CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(160) NOT NULL,
    slug VARCHAR(160) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    full_name VARCHAR(160) NOT NULL,
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'customer'
        CHECK (role IN ('customer', 'staff', 'admin')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    address VARCHAR(255),
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_branches_organization_name UNIQUE (organization_id, name)
);

ALTER TABLE users
    ADD COLUMN branch_id UUID REFERENCES branches(id) ON DELETE SET NULL;

CREATE INDEX ix_users_branch_id ON users (branch_id);

CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    code VARCHAR(32) NOT NULL,
    description TEXT,
    average_service_minutes INTEGER NOT NULL DEFAULT 10
        CHECK (average_service_minutes > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_services_branch_code UNIQUE (branch_id, code)
);

CREATE TABLE counters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'offline'
        CHECK (status IN ('available', 'busy', 'offline')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_counters_branch_number UNIQUE (branch_id, number)
);

CREATE TABLE queues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    name VARCHAR(160) NOT NULL,
    prefix VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'paused', 'closed')),
    current_number INTEGER NOT NULL DEFAULT 0 CHECK (current_number >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_queues_service_name UNIQUE (service_id, name)
);

CREATE TABLE queue_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    queue_number INTEGER NOT NULL CHECK (queue_number > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'called', 'serving', 'completed', 'skipped', 'cancelled')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    called_at TIMESTAMPTZ,
    service_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    estimated_wait_minutes INTEGER
        CHECK (estimated_wait_minutes IS NULL OR estimated_wait_minutes >= 0),
    counter_id UUID REFERENCES counters(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_queue_entries_queue_number UNIQUE (queue_id, queue_number)
);

CREATE TABLE queue_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    queue_entry_id UUID REFERENCES queue_entries(id) ON DELETE SET NULL,
    event_type VARCHAR(20) NOT NULL
    CHECK (event_type IN ('created', 'joined', 'called', 'serving', 'completed', 'skipped', 'cancelled', 'paused', 'resumed')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    queue_entry_id UUID REFERENCES queue_entries(id) ON DELETE SET NULL,
    type VARCHAR(30) NOT NULL
        CHECK (type IN (
            'queue_update', 'turn_approaching', 'turn_called', 'system',
            'queue_joined', 'queue_approaching', 'customer_called',
            'service_completed', 'queue_paused', 'queue_resumed'
        )),
    title VARCHAR(160) NOT NULL,
    message TEXT NOT NULL,
    event_key VARCHAR(160) NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_notifications_user_event_key
    ON notifications (user_id, event_key);

CREATE TABLE notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    joined BOOLEAN NOT NULL DEFAULT TRUE,
    called BOOLEAN NOT NULL DEFAULT TRUE,
    approaching BOOLEAN NOT NULL DEFAULT TRUE,
    completed BOOLEAN NOT NULL DEFAULT TRUE,
    queue_updates BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_entry_id UUID NOT NULL UNIQUE REFERENCES queue_entries(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_users_organization_id ON users (organization_id);
CREATE INDEX ix_branches_organization_id ON branches (organization_id);
CREATE INDEX ix_services_branch_id ON services (branch_id);
CREATE INDEX ix_counters_branch_id ON counters (branch_id);
CREATE INDEX ix_queues_service_id ON queues (service_id);
CREATE INDEX ix_queues_status ON queues (status);
CREATE INDEX ix_queue_entries_queue_status ON queue_entries (queue_id, status);
CREATE INDEX ix_queue_entries_customer_id ON queue_entries (customer_id);
CREATE INDEX ix_queue_events_queue_created_at ON queue_events (queue_id, created_at);
CREATE INDEX ix_queue_events_queue_entry_id ON queue_events (queue_entry_id);
CREATE INDEX ix_notifications_user_created_at ON notifications (user_id, created_at);
CREATE INDEX ix_notifications_user_is_read ON notifications (user_id, is_read);
CREATE INDEX ix_feedback_queue_entry_id ON feedback (queue_entry_id);
