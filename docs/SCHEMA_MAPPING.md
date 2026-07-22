# Schema Mapping

## Document Type

| Legacy value | Unified value |
| --- | --- |
| `Aadhaar Card`, `aadhaar`, `aadhar`, `AADHAAR_CARD` | `AADHAAR_CARD` |
| `PAN Card`, `pan`, `PAN_CARD` | `PAN_CARD` |
| `UNKNOWN`, missing, unsupported | `UNKNOWN` |

## Legacy PAN/Aadhaar Extraction To `DocumentExtractionRecord`

| Legacy source field | Unified field |
| --- | --- |
| `filename` | `filename` |
| `path`, `file_path` | `file_path` |
| `unique_id`, `user_id` | `user_id` |
| `doc_type`, `document_type`, `extracted_data.document_type` | `document_type` |
| `_classification_confidence` | `classification_confidence` |
| `raw_text`, `raw_text_content` | `raw_text_content` |
| `validation_status` | `validation_status` |
| `validation_errors` | `validation_errors` |
| `face_coords`, `face_coordinates` | `face_coordinates` |
| `llm_repaired` | `llm_repaired` |
| flat extracted fields or `extracted_data` | `extracted_data` |

## Aadhaar Field Mapping

| Legacy field | Unified extracted data field |
| --- | --- |
| `front_data.full_name_en`, `full_name_en` | `full_name_en` |
| `front_data.full_name_native`, `full_name_native` | `full_name_native` |
| `full_name` | `full_name` |
| `front_data.date_of_birth`, `date_of_birth` | `date_of_birth` |
| `front_data.year_of_birth`, `year_of_birth` | `year_of_birth` |
| `front_data.gender`, `gender` | `gender` |
| `front_data.aadhaar_number`, `aadhaar_number` | `aadhaar_number` |
| `back_data.address`, `address` | `address` |
| `back_data.address_native`, `address_native` | `address_native` |
| `back_data.pincode`, `pincode` | `pincode` |
| `back_data.guardian_name`, `guardian_name` | `guardian_name` |

## PAN Field Mapping

| Legacy field | Unified extracted data field |
| --- | --- |
| `full_name_en` | `full_name_en` |
| `full_name` | `full_name` |
| `father_name` | `father_name` |
| `date_of_birth` | `date_of_birth` |
| `pan_number` | `pan_number` |

## Unified To Feature Engineering `users`

| Unified field | Existing `users` table column |
| --- | --- |
| `extracted_data.full_name_en` or `full_name` or `full_name_native` | `user_name` |
| `extracted_data.date_of_birth` | `date_of_birth` |
| derived from DOB by existing agent | `age` |
| presence of `aadhaar_number` | `is_aadhaar_verified` |
| `extracted_data.aadhaar_number` | `aadhaar_number` |
| `extracted_data.gender` | `aadhaar_gender` |
| `extracted_data.address` | `aadhaar_address` |
| presence of `pan_number` | `is_pan_verified` |
| `extracted_data.pan_number` | `pan_number` |

## Face Detection To `FaceRecordContract`

| Detection output | Existing FaceRecord-compatible field |
| --- | --- |
| `face_id` | `face_id` |
| task-supplied document id | `document_id` |
| `page`, `page_number` | `page_number` |
| `bbox[0]` in `xywh` format | `bbox_left` |
| `bbox[1]` in `xywh` format | `bbox_top` |
| `bbox[2]` in `xywh` format | `bbox_width` |
| `bbox[3]` in `xywh` format | `bbox_height` |
| `coords=[x1,y1,x2,y2]` with `bbox_format="xyxy"` | converted to left/top/width/height |
| `confidence` | `confidence` |
| `rotation_found` | `rotation_found` |
| `analysis_json` | `analysis_json` |

## Face Verification Result

| Verification output | Existing FaceRecord-compatible field |
| --- | --- |
| `same_person=True` | `verification_result="match"` |
| `same_person=False` | `verification_result="no_match"` |
| `probability`, `confidence` | `verification_confidence` |

## Feast Feature Contract

| Unified `CreditScoreFeatureRecord` | Existing Feast source |
| --- | --- |
| `applicant_id` | `credit_score_data.applicant_id` |
| `age` | `credit_score_data.age` |
| `income` | `credit_score_data.income` |
| `credit_history_length` | `credit_score_data.credit_history_length` |
| `number_of_loans` | `credit_score_data.number_of_loans` |
| `loan_amount` | `credit_score_data.loan_amount` |
| `default_history` | `credit_score_data.default_history` |
| `submission_date` | Feast timestamp field |
