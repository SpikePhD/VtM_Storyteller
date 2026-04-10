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

## NPC
- id
- name
- role
- location_id
- attitude_to_player
- goals
- schedule
- traits (voice, behavior)

## Location
- id
- name
- type
- connected_locations (list)
- travel_time (dict)
- danger_level

## Plot Thread
- id
- name
- stage
- active (bool)
- triggers
- consequences

## Event Log Entry
- timestamp
- description
- involved_entities
