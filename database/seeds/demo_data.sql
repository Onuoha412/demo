INSERT INTO organizations (id, name, slug, description)
VALUES ('00000000-0000-0000-0000-000000000001', 'Babcock University', 'babcock-university', 'Demo organization for QueueLess development.')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO branches (id, organization_id, name, address, timezone)
VALUES ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'Student Affairs', 'Babcock University Main Campus', 'Africa/Lagos')
ON CONFLICT (organization_id, name) DO NOTHING;

INSERT INTO services (id, branch_id, name, code, description, average_service_minutes)
VALUES
    ('00000000-0000-0000-0000-000000000020', '00000000-0000-0000-0000-000000000010', 'Admissions', 'ADM', 'Admissions enquiries and applications.', 15),
    ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000010', 'Finance', 'FIN', 'Student finance and payment support.', 10),
    ('00000000-0000-0000-0000-000000000022', '00000000-0000-0000-0000-000000000010', 'ICT Support', 'ICT', 'Technology support for students and staff.', 12),
    ('00000000-0000-0000-0000-000000000023', '00000000-0000-0000-0000-000000000010', 'Medical Centre', 'MED', 'General medical centre enquiries.', 20)
ON CONFLICT (branch_id, code) DO NOTHING;

INSERT INTO counters (id, branch_id, name, number, status)
VALUES
    ('00000000-0000-0000-0000-000000000030', '00000000-0000-0000-0000-000000000010', 'Counter 1', 1, 'available'),
    ('00000000-0000-0000-0000-000000000031', '00000000-0000-0000-0000-000000000010', 'Counter 2', 2, 'offline')
ON CONFLICT (branch_id, number) DO NOTHING;

INSERT INTO queues (id, service_id, name, prefix)
VALUES
    ('00000000-0000-0000-0000-000000000040', '00000000-0000-0000-0000-000000000020', 'Admissions Queue', 'A'),
    ('00000000-0000-0000-0000-000000000041', '00000000-0000-0000-0000-000000000021', 'Finance Queue', 'F'),
    ('00000000-0000-0000-0000-000000000042', '00000000-0000-0000-0000-000000000022', 'ICT Support Queue', 'I'),
    ('00000000-0000-0000-0000-000000000043', '00000000-0000-0000-0000-000000000023', 'Medical Centre Queue', 'M')
ON CONFLICT (service_id, name) DO NOTHING;
