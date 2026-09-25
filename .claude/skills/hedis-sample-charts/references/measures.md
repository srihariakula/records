# Measure evidence reference

What each chart in `scripts/specs.js` contains, and what to include when adding a measure. These are summaries for building test data, not the official specifications. For anything beyond test data, check the current NCQA HEDIS technical specifications, since measure definitions change year to year (e.g. HBD became GSD in MY2024).

## Existing charts (measurement year 2024)

| Measure | Population | Evidence in the chart | Designed outcome |
|---|---|---|---|
| **CBP**: Controlling High Blood Pressure | 18–85, hypertension | I10 diagnosis on 2+ outpatient dates. BP on 5 dates. The most recent date has two readings, 148/92 and 136/84; the lowest systolic and lowest diastolic of the day give 136/84. Exclusion review is negative (no ESRD, dialysis, hospice, frailty). | Compliant (<140/90) |
| **COA**: Care for Older Adults | 66+, Special Needs Plan | Medication review by the prescribing practitioner plus a medication list, same date. Functional status: Katz ADL and Lawton IADL. Pain assessment: numeric scale, 3/10. Advance care planning is noted but isn't a COA indicator. | All 3 indicators met |
| **GSD**: Glycemic Status Assessment for Patients with Diabetes | 18–75, diabetes | E11.65 diagnosis. HbA1c on 5 dates, most recent 7.6% on 09/18/2024. | <8.0 met, >9.0 not met |
| **PPC**: Prenatal and Postpartum Care | Live-birth deliveries | Prenatal visit at 9w2d with fetal heart tones, OB exam and an obstetric lab panel. Delivery 09/03/2024. Postpartum visit 10/15/2024, 42 days later (window: 7–84 days). | Both indicators met |
| **TRC**: Transitions of Care | 18+, inpatient discharge | Admission notice 07/02, the day of admission. Discharge summary received 07/08, within 2 days of the 07/06 discharge, with all required elements. Engagement visit 07/15. Medication reconciliation 07/15, comparing discharge medications against the outpatient list. | All 4 indicators met |
| **WCC**: Weight Assessment and Counseling for Nutrition and Physical Activity for Children/Adolescents | 3–17 | Height, weight, BMI and BMI percentile (88th). Nutrition counseling and physical activity counseling, all at the same well visit. | All 3 indicators met |

## Adding another measure: evidence to include

- **BPD** (Blood Pressure Control for Patients With Diabetes; 18–75 with diabetes): diabetes diagnosis, then BP readings like CBP's. The target is <140/90 on the most recent date, using the lowest systolic and diastolic of that date.
- **EED** (Eye Exam for Patients With Diabetes; the root `EED.pdf` and `EED_*.txt` are the originals): a retinal or dilated eye exam by an eye-care professional with a result (retinopathy or none), in the measurement year, or a negative result in the prior year.
- **CCS** (Cervical Cancer Screening): cervical cytology in the last 3 years (ages 21–64) or hrHPV testing in the last 5 years (30–64), with dates and results.
- **COL / COL-E** (Colorectal Cancer Screening): colonoscopy, FIT, sigmoidoscopy, CT colonography or FIT-DNA with dates inside the lookback windows.
- **BCS-E** (Breast Cancer Screening): a mammogram date inside the window, and a history of bilateral mastectomy as an exclusion variant.

To test exclusions or non-compliance rather than compliance, make a second spec for the same measure (same `measure: 'CBP'`, plus `file: 'CBP_noncompliant'` so it gets its own .docx). Set the outcome deliberately and document it in the spec comment.
