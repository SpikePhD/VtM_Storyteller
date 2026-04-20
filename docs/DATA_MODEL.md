# Data Model

## Player
- id
- name
- clan
- profession
- hunger
- health
- willpower
- humanity
- inventory (list of item ids)
- location_id
- stats (dict)
- current_goal (optional)

## NPC
- id
- name
- role
- location_id
- schedule
- goals
- traits (voice, behavior)
- relationship_to_player
- trust_level
- hostility_level
- fear_level
- respect_level
- willingness_to_help
- secrecy_level
- current_disposition
- known_topics
- taboo_topics
- knowledge_facts
- current_social_goal

## Location
- id
- name
- type
- connected_locations (list)
- travel_time (dict)
- danger_level
- scene_tags

## Plot Thread
- id
- name
- stage
- active (bool)
- triggers
- consequences
- revealable_topics
- gated_facts

## Conversation Context
- active_npc_id
- conversation_stance
- active_subtopic
- last_social_outcome
- turn_count

## Social Outcome Packet
- action_type
- target_npc_id
- topic
- topic_status
- social_move
- required_check
- check_result
- npc_response_mode
- stance_shift
- trust_shift
- applied_effects
- plot_effects

## Event Log Entry
- timestamp
- description
- involved_entities
- event_type
- structured_payload
