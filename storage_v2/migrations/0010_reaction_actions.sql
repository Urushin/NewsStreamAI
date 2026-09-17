CREATE TABLE user_reaction_actions (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('like', 'unlike')),
    client_event_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT INTO user_reaction_actions (id, user_id, event_id, action, client_event_id, occurred_at)
SELECT id, user_id, event_id, 'like', client_event_id, occurred_at
FROM user_interactions WHERE event_id IS NOT NULL AND json_extract(metadata_json, '$.user_action') = 'like';
CREATE INDEX ix_reaction_actions_user_event ON user_reaction_actions(user_id, event_id, occurred_at DESC);
CREATE TRIGGER prevent_reaction_action_mutation BEFORE UPDATE ON user_reaction_actions
BEGIN SELECT RAISE(ABORT, 'reaction actions are append-only'); END;
