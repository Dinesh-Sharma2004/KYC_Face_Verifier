# Feast Contract Analysis

| Component | Source location | Purpose | Dependencies | Recommended source of truth | Migration strategy | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| Entity | `2_multi_agent_pipeline/credit_scoring_pipeline/features/feature_repo/entity.py` | Defines `applicant_id` as the Feast entity | Feast `Entity`, `ValueType.STRING` | Yes | Reuse exactly; do not rename entity | Low |
| Feature view | `2_multi_agent_pipeline/credit_scoring_pipeline/features/feature_repo/feature_view.py` | Defines `credit_score_features` feature view | Feast `FeatureView`, `Field`, `PostgreSQLSource` | Yes | Keep feature names and types; add adapters upstream to produce compatible rows | Low |
| Offline source | `feature_view.py` | Queries `credit_score_data` from PostgreSQL | Feast Postgres offline store | Yes | Preserve query fields and timestamp `submission_date` | Medium: source table is referenced but not created in repo |
| Feature store config | `features/feature_repo/feature_store.yaml` | Configures local provider with Postgres offline and online stores | Feast, PostgreSQL | Yes | Parameterize credentials later; do not change contracts now | Medium: hard-coded localhost credentials |
| Dynamic writer | `2_multi_agent_pipeline/credit_scoring_pipeline/agents/feast_writer_agent.py` | Creates `doc_chunks_view` dynamically from CSV | Feast `FeatureStore`, `FileSource` | No, experimental | Replace with adapter into existing `credit_score_features` when validated | High: imports missing `agents.utils.schema` and creates new FeatureView at runtime |

## Feature Contract

`credit_score_features` expects:

| Field | Type | Source table column |
| --- | --- | --- |
| `applicant_id` | string entity | `credit_score_data.applicant_id` |
| `age` | Int64 | `credit_score_data.age` |
| `income` | Float32 | `credit_score_data.income` |
| `credit_history_length` | Int64 | `credit_score_data.credit_history_length` |
| `number_of_loans` | Int64 | `credit_score_data.number_of_loans` |
| `loan_amount` | Float32 | `credit_score_data.loan_amount` |
| `default_history` | String | `credit_score_data.default_history` |
| `submission_date` | timestamp | `credit_score_data.submission_date` |

## Migration Strategy

Keep Feast unchanged. Add a unified `CreditScoreFeatureRecord` contract and make Feature Store Agent validate rows against that contract before inserting into `credit_score_data` or materializing Feast.
