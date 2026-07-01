# LG-CNS-ABM

## Smoke Test

```bash
cd LG_CNS_VNB_ABM/abm_ver2
python simulate.py '{"project_type":"legacy_migration","num_sprints":1,"seed":42}'
python simulate.py '{"project_type":"deadline_driven","requirement_clarity":0.9,"codebase_stability":0.95,"sprint_backlog_size":5,"num_sprints":1,"seed":42}'
```

The second command verifies that explicitly passed `requirement_clarity`,
`codebase_stability`, and `sprint_backlog_size` override the selected
`project_type` defaults.
