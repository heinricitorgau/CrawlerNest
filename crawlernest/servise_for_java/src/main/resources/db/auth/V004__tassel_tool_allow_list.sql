-- =========================================================
-- desk.chat_action: the allow-list becomes Tassel's tools
-- =========================================================
--
-- V003 allowed the four tool names in the first design draft. The assistant's
-- tools are now defined in prompts/tassel_tools.json, and this
-- list must name exactly those (TasselToolsContractTest checks it):
--
--   update_target_list         add a school, change its stage, or remove it
--   create_action_task         add a dated action item to the task list
--   generate_narrative_themes  store 1-2 suggested narrative themes
--
-- Run by AuthSchemaInitializer after V003 on every start. DROP ... IF EXISTS and
-- then ADD makes the pair idempotent. NOT VALID: a row written under the old
-- names stays readable rather than stopping the API from starting; every new
-- row is checked.

ALTER TABLE desk.chat_action DROP CONSTRAINT IF EXISTS chat_action_tool_name_check;

ALTER TABLE desk.chat_action ADD CONSTRAINT chat_action_tool_name_check
    CHECK (tool_name IN ('update_target_list', 'create_action_task', 'generate_narrative_themes')) NOT VALID;
