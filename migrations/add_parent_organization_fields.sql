-- Add parent organization fields to campgrounds table
-- These enable grouping campgrounds by park system (e.g., all Los Padres NF campgrounds)

ALTER TABLE campgrounds ADD COLUMN parent_entity_id TEXT;
ALTER TABLE campgrounds ADD COLUMN parent_name TEXT;
ALTER TABLE campgrounds ADD COLUMN org_name TEXT;

-- Create index on parent_entity_id for fast related campground lookups
CREATE INDEX idx_campgrounds_parent_entity_id ON campgrounds(parent_entity_id);
