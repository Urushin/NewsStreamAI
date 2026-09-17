-- Bookmark removal is a reversible library action, never a negative preference.
CREATE TABLE user_bookmark_actions (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('save', 'unsave')),
    client_event_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT INTO user_bookmark_actions (id, user_id, event_id, action, client_event_id, occurred_at)
SELECT id, user_id, event_id, 'save', client_event_id, occurred_at
FROM user_interactions WHERE interaction_type = 'save' AND event_id IS NOT NULL;
CREATE INDEX ix_bookmark_actions_user_event ON user_bookmark_actions(user_id, event_id, occurred_at DESC);
CREATE TRIGGER prevent_bookmark_action_mutation BEFORE UPDATE ON user_bookmark_actions
BEGIN SELECT RAISE(ABORT, 'bookmark actions are append-only'); END;
