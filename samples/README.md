# Synthetic HEDIS sample charts (.docx)

Sample medical records for testing the viewer's upload, search, NER and field-extraction flows, one per HEDIS measure, laid out in the same format as the root `CBP.pdf` sample: a per-page patient header (name/DOB, Date of Visit, gender, MRN, provider), `Section -` / `Sub:` headings, `Label: value` lines, date-column lab and vitals grids, a problem list, an e-signature, and a `Doc ID` / `Page X of Y` / `Printed` footer.

**Every patient, provider, facility and identifier is fictitious. No PHI.** Measurement year is 2024.

| File | Measure | Evidence in the chart |
|---|---|---|
| `CBP.docx` | Controlling High Blood Pressure | Hypertension diagnosis (I10). BP readings on 5 dates. The most recent date (11/14/2024) has two readings, 148/92 and 136/84, so the representative BP is 136/84, which is controlled. Exclusion review is all negative. |
| `COA.docx` | Care for Older Adults | A 75-year-old D-SNP member. Medication review by the prescribing practitioner with a medication list, 06/12/2024. Functional status assessment (Katz ADL 6/6, Lawton IADL 5/8). Pain assessment (numeric scale, 3/10). |
| `GSD.docx` | Glycemic Status Assessment for Patients with Diabetes | Type 2 diabetes (E11.65). HbA1c on 5 dates. The most recent is 7.6% on 09/18/2024: below 8.0 and not above 9.0. |
| `PPC.docx` | Prenatal and Postpartum Care | Two visits. The first-trimester prenatal visit on 02/08/2024 (9w2d) has fetal heart tones, an OB exam and prenatal labs. Delivery was 09/03/2024. The postpartum visit on 10/15/2024 is 42 days after delivery. |
| `TRC.docx` | Transitions of Care | Three notes around an inpatient stay (admitted 07/02, discharged 07/06/2024). Admission notification on 07/02. Discharge information received on 07/08. Patient engagement and medication reconciliation at the 07/15 visit. |
| `WCC.docx` | Weight Assessment and Counseling for Nutrition and Physical Activity for Children/Adolescents | An 11-year-old well-child visit on 05/20/2024. Height, weight and BMI percentile (88th). Nutrition counseling and physical activity counseling. |

Viewing or searching a `.docx` requires LibreOffice **with Writer**. On Debian/Ubuntu install `libreoffice-writer`; `libreoffice-core` alone can't open documents.
