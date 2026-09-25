// Synthetic HEDIS MY2024 sample charts, one per measure, in the CBP.pdf
// sample's format. Every patient, provider, facility and identifier here is
// fictitious. Each chart carries the medical-record evidence its measure is
// abstracted for (see the "evidence" note on each spec).

const PRINTED = '01/15/2025';

// ---------------------------------------------------------------- CBP
// Controlling High Blood Pressure (18-85, hypertension). Evidence: HTN dx on
// 2 outpatient dates, BP readings with dates; most recent date has two
// readings (lowest systolic 136 + lowest diastolic 84 -> representative BP
// 136/84, controlled <140/90). No exclusions (no ESRD/dialysis/hospice).
const CBP = {
  measure: 'CBP', measureName: 'Controlling High Blood Pressure', docId: '24117305', printed: PRINTED,
  patient: { name: 'Delgado, Ramon', dob: '04/17/1962', gender: 'Male' },
  encounters: [{
    visitDate: '11/14/2024', provider: 'SUSAN PATEL, MD', signedAt: '11/14/2024 04:42 PM',
    blocks: [
      { section: 'Office Visit' },
      { kv: [['Services are being rendered at', 'RIVERSIDE FAMILY MEDICINE'], ['Visit Type', 'Follow-up, chronic disease management']] },
      { sub: 'Chief Complaint' },
      { text: 'Follow-up of essential hypertension and hyperlipidemia. No complaints today.' },
      { sub: 'History of Present Illness' },
      { text: '62 year old male with essential hypertension diagnosed 03/2019, on lisinopril and amlodipine. Reports adherence to medications; checks BP at home 3-4 times per week with readings 130s-140s/80s. Denies chest pain, headache, visual changes, dyspnea or lower extremity swelling. Walking 30 minutes 4 days per week; has reduced added salt.' },
      { sub: 'Overall Patient Status' },
      { kv: [['Patient', 'Stable'], ['Meds, Labs, and Data Trends', 'Reviewed']] },

      { section: 'Vitals' },
      { kv: [['BP (initial, 09:12 AM, right arm, seated)', '148/92'], ['BP (repeat after 5 min rest, 09:24 AM, right arm, seated)', '136/84'],
             ['Pulse', '74 bpm'], ['Resp', '16'], ['Temp', '98.2 F'], ['SpO2', '98%'], ['Ht', '5\'10"'], ['Wt', '201.4 lbs'], ['BMI', '28.9 - Overweight']] },
      { comment: 'Initial reading elevated; repeat reading after rest is at goal. Representative BP for today 136/84.' },

      { section: 'Physical Exam' },
      { sub: 'General Appearance' }, { kv: [['Appearance', 'Appears comfortable and is in no distress']] },
      { sub: 'Neck' }, { kv: [['JVP', 'No increase in JVP'], ['Carotids', 'No bruits']] },
      { sub: 'Lungs' }, { kv: [['Status', 'Normal']] }, { comment: 'Clear to auscultation bilaterally.' },
      { sub: 'Heart' }, { kv: [['Status', 'Normal']] }, { comment: 'RRR, S1, S2 normal. No murmurs or gallops.' },
      { sub: 'Extremities' }, { kv: [['Status', 'Edema Not Present']] },

      { section: 'BP & Cardiovascular Management' },
      { grid: { headers: ['Vitals', '11/14/24', '08/22/24', '05/09/24', '01/24/24', '10/03/23'],
        rows: [
          ['BP (initial)', '148/92', '150/94', '138/86', '142/88', '156/96'],
          ['BP (repeat)', '136/84', '146/90', '--', '--', '152/94'],
          ['Pulse', '74', '78', '72', '76', '80'],
          ['Weight (lbs)', '201.4', '203.0', '204.8', '206.2', '208.5'],
          ['BMI', '28.9', '29.1', '29.4', '29.6', '29.9'],
        ] } },
      { status: ['BP: 136/84-11/14/24 - At Goal (<140/90)', 'BP: 146/90-08/22/24 - Above Goal', 'BP: 138/86-05/09/24 - At Goal'] },
      { comment: 'BP at goal on repeat today after amlodipine was increased on 08/22/24. Continue current regimen; home BP log reviewed and consistent.' },

      { section: 'Labs' },
      { grid: { headers: ['Lab Test', '11/07/24', '05/02/24', '01/18/24'],
        rows: [
          ['SODIUM', '139', '140', '138'], ['POTASSIUM', '4.6', '4.4', '4.7'], ['CREATININE', '1.02', '0.98', '1.05'],
          ['EGFR', '82', '86', '79'], ['BUN', '17', '15', '18'], ['GLUCOSE', '98', '104 H', '96'],
          ['CHOLESTEROL', '188', '', '214 H'], ['LDL', '108 H', '', '132 H'], ['HDL-CHOLESTEROL', '46', '', '42'], ['TRIGLYCERIDES', '170 H', '', '199 H'],
          ['URINE ALB/CREAT RATIO', '12', '', ''],
        ] } },
      { status: ['K: 4.6-11/07/24 - In Target', 'Creatinine: 1.02-11/07/24 - Normal', 'LDL: 108 H-11/07/24 - Improved'] },

      { section: 'Medications' },
      { bullets: ['Lisinopril 20 mg tablet - 1 tablet by mouth once daily', 'Amlodipine 10 mg tablet - 1 tablet by mouth once daily (increased from 5 mg on 08/22/2024)', 'Atorvastatin 20 mg tablet - 1 tablet by mouth at bedtime', 'Aspirin 81 mg tablet - 1 tablet by mouth once daily'] },

      { section: 'Exclusion Review' },
      { kv: [['End stage renal disease / dialysis', 'No'], ['Kidney transplant / nephrectomy', 'No'], ['Hospice or palliative care', 'No'], ['Pregnancy', 'N/A'], ['Frailty / advanced illness', 'No']] },

      { section: 'Problem List' },
      { problems: [
        ['Essential (primary) hypertension (I10)', 'Diagnosed 03/2019. Controlled today on repeat reading 136/84. Continue lisinopril 20 mg and amlodipine 10 mg; home BP monitoring; recheck 3 months.'],
        ['Hyperlipidemia, unspecified (E78.5)', 'LDL improved to 108 on atorvastatin 20 mg; continue, diet counseling given.'],
        ['Overweight, BMI 28.0-28.9 (Z68.28)', 'Down 7 lbs over the past year. Continue walking program.'],
      ] },
    ],
  }],
};

// ---------------------------------------------------------------- COA
// Care for Older Adults (66+, Medicare SNP). Evidence: medication review by a
// prescribing practitioner with a medication list on the same date,
// functional status assessment (ADLs + IADLs, standardized tools), and a
// pain assessment (numeric scale) - all within the measurement year.
const COA = {
  measure: 'COA', measureName: 'Care for Older Adults', docId: '24098812', printed: PRINTED,
  patient: { name: 'Whitfield, Eleanor', dob: '02/08/1949', gender: 'Female' },
  encounters: [{
    visitDate: '06/12/2024', provider: 'MARCUS OKAFOR, MD', signedAt: '06/12/2024 03:15 PM',
    blocks: [
      { section: 'Annual Wellness Visit' },
      { kv: [['Services are being rendered at', 'LAKEVIEW SENIOR CARE CLINIC'], ['Plan', 'Medicare Advantage Dual Eligible Special Needs Plan (D-SNP)'], ['Accompanied by', 'Daughter (caregiver)']] },
      { sub: 'Overall Patient Status' },
      { kv: [['Patient', 'Stable'], ['Meds, Labs, and Data Trends', 'Reviewed']] },
      { comment: '75 year old female seen for annual wellness visit and care plan review. Lives with daughter. Reports chronic bilateral knee pain, otherwise feels well.' },

      { section: 'Vitals' },
      { kv: [['BP', '132/78'], ['Pulse', '70 bpm'], ['Temp', '97.9 F'], ['SpO2', '97%'], ['Ht', '5\'3"'], ['Wt', '142.6 lbs'], ['BMI', '25.3']] },

      { section: 'Medication Review' },
      { grid: { headers: ['Medication', 'Dose', 'Frequency', 'Indication', 'Status'],
        rows: [
          ['Metoprolol succinate ER', '25 mg', 'Once daily', 'Hypertension', 'Continue'],
          ['Losartan', '50 mg', 'Once daily', 'Hypertension', 'Continue'],
          ['Levothyroxine', '75 mcg', 'Once daily, AM', 'Hypothyroidism', 'Continue'],
          ['Acetaminophen', '650 mg', 'Every 8 hrs as needed', 'Knee osteoarthritis pain', 'Continue'],
          ['Calcium carbonate + Vitamin D3', '600 mg / 800 IU', 'Twice daily', 'Osteopenia', 'Continue'],
          ['Ibuprofen (OTC)', '200 mg', 'As needed', 'Knee pain', 'DISCONTINUED'],
        ] } },
      { kv: [['Medication Review Completed', 'Yes'], ['Reviewed by', 'MARCUS OKAFOR, MD (prescribing practitioner)'], ['Date of Review', '06/12/2024']] },
      { comment: 'Complete medication list including OTC and supplements reviewed with patient and daughter. OTC ibuprofen discontinued given age, hypertension and renal risk; acetaminophen continued for pain. No duplications or significant interactions identified.' },

      { section: 'Functional Status Assessment' },
      { sub: 'Activities of Daily Living (Katz Index)' },
      { grid: { headers: ['ADL', 'Status', 'Notes'],
        rows: [
          ['Bathing', 'Independent', 'Shower chair in use'], ['Dressing', 'Independent', ''], ['Toileting', 'Independent', ''],
          ['Transferring', 'Independent', 'Slow; uses armrests'], ['Continence', 'Independent', ''], ['Feeding', 'Independent', ''],
        ] } },
      { kv: [['Katz ADL Score', '6/6 - Full function']] },
      { sub: 'Instrumental Activities of Daily Living (Lawton IADL)' },
      { grid: { headers: ['IADL', 'Status', 'Notes'],
        rows: [
          ['Using telephone', 'Independent', ''], ['Shopping', 'Needs assistance', 'Daughter drives'], ['Food preparation', 'Independent', ''],
          ['Housekeeping', 'Needs assistance', 'Heavy chores'], ['Laundry', 'Independent', ''], ['Transportation', 'Needs assistance', 'Does not drive'],
          ['Managing medications', 'Independent', 'Weekly pill organizer'], ['Managing finances', 'Independent', ''],
        ] } },
      { kv: [['Lawton IADL Score', '5/8'], ['Gait / Mobility', 'Ambulates with single-point cane; Timed Up and Go 13 seconds'], ['Falls in past 12 months', 'None']] },
      { comment: 'Functional status assessed today using Katz ADL and Lawton IADL instruments. Independent in all ADLs; needs help with shopping, housekeeping and transportation, which daughter provides.' },

      { section: 'Pain Assessment' },
      { kv: [['Pain Present', 'Yes'], ['Pain Scale Used', 'Numeric Rating Scale (0-10)'], ['Current Pain Score', '3/10'], ['Worst in past week', '6/10'],
             ['Location', 'Bilateral knees'], ['Character', 'Aching, worse with stairs'], ['Impact on function', 'Mild - limits long walks']] },
      { comment: 'Chronic osteoarthritis knee pain, stable. Continue scheduled acetaminophen as needed, referred to physical therapy for strengthening.' },

      { section: 'Advance Care Planning' },
      { kv: [['Advance directive on file', 'Yes - Health care proxy (daughter) dated 03/14/2022'], ['Discussed today', 'Yes, preferences unchanged']] },

      { section: 'Physical Exam' },
      { sub: 'General Appearance' }, { kv: [['Appearance', 'Well appearing elderly female in no distress']] },
      { sub: 'Lungs' }, { kv: [['Status', 'Normal']] },
      { sub: 'Heart' }, { kv: [['Status', 'Normal']] }, { comment: 'RRR, S1, S2 normal.' },
      { sub: 'Extremities' }, { kv: [['Status', 'Edema Not Present']] }, { comment: 'Crepitus both knees, no effusion.' },

      { section: 'Problem List' },
      { problems: [
        ['Primary osteoarthritis of both knees (M17.0)', 'Pain 3/10 today. Acetaminophen, PT referral; stop OTC NSAIDs.'],
        ['Essential (primary) hypertension (I10)', 'BP 132/78, controlled on metoprolol and losartan.'],
        ['Hypothyroidism, unspecified (E03.9)', 'TSH 2.1 on 05/28/2024; continue levothyroxine 75 mcg.'],
        ['Osteopenia (M85.80)', 'Calcium and vitamin D; DEXA due 2025.'],
      ] },
    ],
  }],
};

// ---------------------------------------------------------------- GSD
// Glycemic Status Assessment for Patients with Diabetes (18-75). Evidence:
// diabetes dx, dated HbA1c results; most recent in MY = 7.6% on 09/18/2024
// (<8.0 controlled, not >9.0).
const GSD = {
  measure: 'GSD', measureName: 'Glycemic Status Assessment for Patients with Diabetes', docId: '24131560', printed: PRINTED,
  patient: { name: 'Nguyen, Thomas', dob: '09/22/1966', gender: 'Male' },
  encounters: [{
    visitDate: '09/30/2024', provider: 'ANGELA RUIZ, MD', signedAt: '09/30/2024 11:05 AM',
    blocks: [
      { section: 'Office Visit' },
      { kv: [['Services are being rendered at', 'EASTSIDE ENDOCRINOLOGY ASSOCIATES'], ['Visit Type', 'Diabetes follow-up']] },
      { sub: 'Overall Patient Status' },
      { kv: [['Patient', 'Stable'], ['Meds, Labs, and Data Trends', 'Reviewed']] },
      { sub: 'History of Present Illness' },
      { text: '58 year old male with type 2 diabetes mellitus since 2015, with hyperglycemia, here to review labs. Semaglutide started 03/2024 and titrated to 1 mg weekly. Home fasting glucose 110-140. No hypoglycemia. Lost 12 lbs since March.' },

      { section: 'Vitals' },
      { kv: [['BP', '128/76'], ['Pulse', '72 bpm'], ['Ht', '5\'7"'], ['Wt', '184.0 lbs'], ['BMI', '28.8']] },

      { section: 'Glycemic Management' },
      { grid: { headers: ['Lab Test', '09/18/24', '06/18/24', '03/05/24', '12/11/23', '09/12/23'],
        rows: [
          ['HEMOGLOBIN A1C %', '7.6 H', '8.1 H', '8.6 H', '9.4 H', '9.1 H'],
          ['GLUCOSE, FASTING', '128 H', '146 H', '171 H', '212 H', '198 H'],
          ['CREATININE', '0.94', '0.97', '1.01', '0.99', '1.03'],
          ['EGFR', '91', '88', '84', '86', '82'],
          ['URINE ALB/CREAT RATIO', '24', '', '31 H', '', '38 H'],
          ['LDL', '82', '', '96', '', '118 H'],
          ['TRIGLYCERIDES', '162 H', '', '204 H', '', '231 H'],
        ] } },
      { status: ['HbA1c: 7.6 H-09/18/24 - Improved, below 8.0', 'HbA1c: 8.1 H-06/18/24 - Above Target', 'UACR: 24-09/18/24 - Normal'] },
      { comment: 'Most recent HbA1c 7.6% (collected 09/18/2024) - improved from 9.4% in 12/2023 after adding semaglutide. Goal <7.0%. Continue current regimen; repeat HbA1c in 3 months.' },

      { section: 'Diabetes Care' },
      { kv: [['Foot Exam', 'Monofilament sensation intact bilaterally; pulses 2+; no ulcers'], ['Retinal Exam', 'Dilated eye exam 04/22/2024 by ophthalmology - no diabetic retinopathy'],
             ['Hypoglycemia Episodes', 'None reported'], ['Self-monitoring', 'Glucometer, fasting daily']] },

      { section: 'Medications' },
      { bullets: ['Metformin ER 1000 mg - 2 tablets by mouth once daily with evening meal', 'Semaglutide 1 mg - subcutaneous once weekly (started 03/2024)', 'Insulin glargine 18 units - subcutaneous at bedtime (reduced from 24 units)', 'Atorvastatin 40 mg - 1 tablet by mouth daily', 'Lisinopril 10 mg - 1 tablet by mouth daily'] },

      { section: 'Physical Exam' },
      { sub: 'General Appearance' }, { kv: [['Appearance', 'Appears comfortable and is in no distress']] },
      { sub: 'Heart' }, { kv: [['Status', 'Normal']] },
      { sub: 'Extremities' }, { kv: [['Status', 'Edema Not Present']] },

      { section: 'Problem List' },
      { problems: [
        ['Type 2 diabetes mellitus with hyperglycemia (E11.65)', 'HbA1c 7.6% on 09/18/2024, improved. Continue metformin, semaglutide; glargine reduced to 18 units.'],
        ['Long term (current) use of insulin (Z79.4)', 'No hypoglycemia.'],
        ['Hyperlipidemia (E78.5)', 'LDL 82 on atorvastatin 40 mg.'],
      ] },
    ],
  }],
};

// ---------------------------------------------------------------- PPC
// Prenatal and Postpartum Care. Evidence: prenatal visit in the first
// trimester (9w2d, OB exam + FHT + prenatal labs), delivery 09/03/2024, and a
// postpartum visit 10/15/2024 (42 days after delivery, within 7-84 days).
const PPC = {
  measure: 'PPC', measureName: 'Prenatal and Postpartum Care', docId: '24145087', printed: PRINTED,
  patient: { name: 'Carter, Jasmine', dob: '05/14/1995', gender: 'Female' },
  encounters: [
    {
      visitDate: '02/08/2024', provider: 'LAUREN MITCHELL, MD', signedAt: '02/08/2024 02:48 PM',
      blocks: [
        { section: 'Initial Prenatal Visit' },
        { kv: [['Services are being rendered at', 'HARBORVIEW WOMEN\'S HEALTH'], ['Visit Type', 'New OB - initial prenatal visit']] },
        { sub: 'Obstetric History' },
        { kv: [['Gravida / Para', 'G2 P1001'], ['LMP', '12/05/2023 (certain)'], ['EDD', '09/10/2024 (by LMP, confirmed by 8 week ultrasound)'], ['Gestational Age', '9 weeks 2 days'], ['Prior Delivery', '2021 SVD at term, uncomplicated']] },
        { comment: 'Positive home pregnancy test 01/10/2024. Mild nausea, no vomiting, bleeding or cramping. Taking prenatal vitamins.' },
        { section: 'Vitals' },
        { kv: [['BP', '114/70'], ['Pulse', '82 bpm'], ['Wt', '148.0 lbs'], ['Ht', '5\'5"'], ['BMI (pre-pregnancy)', '24.1']] },
        { section: 'Obstetric Exam' },
        { kv: [['Fetal Heart Tones', '158 bpm by Doppler'], ['Uterine size', 'Consistent with dates (~9 weeks)'], ['Pelvic Exam', 'Normal external genitalia, cervix closed/long, no discharge'], ['Breast Exam', 'Normal']] },
        { sub: 'Ultrasound' }, { comment: 'Transvaginal ultrasound 02/01/2024: single intrauterine pregnancy, CRL 8w3d, cardiac activity present.' },
        { section: 'Prenatal Labs' },
        { grid: { headers: ['Lab Test', '02/08/24'],
          rows: [
            ['ABO / RH', 'O Positive'], ['ANTIBODY SCREEN', 'Negative'], ['RUBELLA IGG', 'Immune'], ['HEPATITIS B SURFACE AG', 'Nonreactive'],
            ['HIV 1/2 AG/AB', 'Nonreactive'], ['RPR', 'Nonreactive'], ['HEMOGLOBIN', '12.1'], ['PLATELETS', '248'], ['URINE CULTURE', 'No growth'],
            ['CHLAMYDIA / GONORRHEA NAAT', 'Negative / Negative'],
          ] } },
        { section: 'Problem List' },
        { problems: [
          ['Supervision of normal pregnancy, first trimester (Z34.81)', 'Intrauterine pregnancy at 9w2d by LMP. Prenatal labs sent, prenatal vitamins, return in 4 weeks.'],
          ['Nausea of pregnancy', 'Mild; dietary measures, vitamin B6 as needed.'],
        ] },
      ],
    },
    {
      visitDate: '10/15/2024', provider: 'LAUREN MITCHELL, MD', signedAt: '10/15/2024 10:20 AM',
      blocks: [
        { section: 'Postpartum Visit' },
        { kv: [['Services are being rendered at', 'HARBORVIEW WOMEN\'S HEALTH'], ['Visit Type', 'Comprehensive postpartum visit']] },
        { sub: 'Delivery Summary' },
        { kv: [['Date of Delivery', '09/03/2024'], ['Facility', 'ST. MARY\'S WOMEN\'S HOSPITAL'], ['Gestational Age at Delivery', '38 weeks 6 days'],
               ['Delivery Type', 'Spontaneous vaginal delivery'], ['Outcome', 'Live born male infant, 3.41 kg, Apgars 8/9'], ['Complications', '2nd degree perineal laceration, repaired']] },
        { comment: 'Patient seen 42 days postpartum. Doing well, breastfeeding exclusively. Lochia resolved. No fever, heavy bleeding or calf pain.' },
        { section: 'Vitals' },
        { kv: [['BP', '112/72'], ['Pulse', '76 bpm'], ['Wt', '156.2 lbs']] },
        { section: 'Postpartum Exam' },
        { kv: [['Breasts', 'Lactating, no masses, nipples intact'], ['Abdomen', 'Soft, non-tender, uterus not palpable'], ['Perineum', 'Laceration well healed'], ['Pelvic Exam', 'Normal, cervix closed']] },
        { section: 'Postpartum Screening & Counseling' },
        { kv: [['Edinburgh Postnatal Depression Scale (EPDS)', '5 - Negative screen'], ['Infant feeding', 'Exclusive breastfeeding'], ['Contraception', 'Counseled; levonorgestrel IUD placement scheduled 11/2024'],
               ['Glucose / BP follow-up', 'No gestational diabetes or hypertension during pregnancy'], ['Resumption of activity', 'Cleared for exercise and intercourse']] },
        { section: 'Problem List' },
        { problems: [
          ['Encounter for routine postpartum follow-up (Z39.2)', '42 days after vaginal delivery on 09/03/2024. Normal exam, EPDS 5.'],
          ['Encounter for lactation supervision (Z39.1)', 'Exclusive breastfeeding going well.'],
        ] },
      ],
    },
  ],
};

// ---------------------------------------------------------------- TRC
// Transitions of Care (18+). Evidence for all four indicators around an
// inpatient stay 07/02-07/06/2024: admission notification 07/02 (day of
// admission), discharge information received 07/08 (within 2 days after
// discharge) with the required elements, patient engagement 07/15 (within
// 30 days), medication reconciliation 07/15 (within 30 days).
const TRC = {
  measure: 'TRC', measureName: 'Transitions of Care', docId: '24126643', printed: PRINTED,
  patient: { name: 'Brooks, Harold', dob: '12/03/1953', gender: 'Male' },
  encounters: [
    {
      visitDate: '07/02/2024', provider: 'DANIEL KIM, MD', signedAt: '07/02/2024 03:05 PM',
      blocks: [
        { section: 'Care Coordination Note' },
        { kv: [['Services are being rendered at', 'NORTHGATE PRIMARY CARE'], ['Note Type', 'Notification of inpatient admission']] },
        { kv: [['Notification Received', '07/02/2024 02:32 PM'], ['Source', 'ADT feed - MERCY GENERAL HOSPITAL'], ['Admission Date', '07/02/2024'],
               ['Admitting Diagnosis', 'Acute on chronic systolic (congestive) heart failure'], ['Admitting Physician', 'HOSPITALIST SERVICE, MERCY GENERAL']] },
        { comment: 'PCP office notified of inpatient admission on the day of admission. Care manager to follow hospital course and arrange post-discharge visit.' },
      ],
    },
    {
      visitDate: '07/08/2024', provider: 'DANIEL KIM, MD', signedAt: '07/08/2024 09:40 AM',
      blocks: [
        { section: 'Receipt of Discharge Information' },
        { kv: [['Date Received', '07/08/2024'], ['Document', 'Discharge Summary - MERCY GENERAL HOSPITAL'], ['Admission / Discharge', '07/02/2024 - 07/06/2024'],
               ['Practitioner responsible for care during stay', 'JOHN ABERNATHY, MD (hospitalist)']] },
        { sub: 'Diagnoses at Discharge' },
        { bullets: ['Acute on chronic systolic (congestive) heart failure (I50.23)', 'Hypertensive heart disease with heart failure (I11.0)', 'Chronic kidney disease, stage 3a (N18.31)'] },
        { sub: 'Procedures / Treatment' },
        { text: 'IV furosemide diuresis (net -4.2 L). Transthoracic echocardiogram 07/03/2024: LVEF 30%.' },
        { sub: 'Current Medication List at Discharge' },
        { bullets: ['Furosemide 40 mg by mouth twice daily (NEW dose)', 'Sacubitril/valsartan 24/26 mg by mouth twice daily (NEW - replaces lisinopril)', 'Metoprolol succinate ER 50 mg by mouth daily', 'Spironolactone 25 mg by mouth daily (NEW)', 'Atorvastatin 40 mg by mouth daily'] },
        { sub: 'Testing Results / Pending Tests' },
        { text: 'BMP on 07/06: K 4.3, creatinine 1.38. Pending: none.' },
        { sub: 'Instructions for Patient Care' },
        { text: 'Daily weights; call for gain >3 lbs in 2 days or 5 lbs in a week. 2 g sodium diet, 2 L fluid restriction. PCP follow-up within 7-10 days with BMP. Cardiology follow-up in 2-4 weeks.' },
        { comment: 'Discharge summary received and reviewed by PCP 07/08/2024 (within 2 days of discharge). Post-discharge visit scheduled 07/15/2024.' },
      ],
    },
    {
      visitDate: '07/15/2024', provider: 'DANIEL KIM, MD', signedAt: '07/15/2024 12:10 PM',
      blocks: [
        { section: 'Post-Discharge Office Visit' },
        { kv: [['Services are being rendered at', 'NORTHGATE PRIMARY CARE'], ['Visit Type', 'Transitional care, in person'], ['Days since discharge', '9']] },
        { comment: 'Seen for follow-up after hospitalization 07/02-07/06/2024 for acute on chronic systolic heart failure. Breathing much improved, sleeping on 1 pillow. Home weights stable 186-187 lbs. No chest pain or dizziness.' },
        { section: 'Vitals' },
        { kv: [['BP', '122/74'], ['Pulse', '66 bpm'], ['SpO2', '96%'], ['Wt', '186.8 lbs (discharge weight 187.4 lbs)']] },
        { section: 'Medication Reconciliation' },
        { grid: { headers: ['Medication', 'Prior to Admission', 'At Discharge', 'Reconciled Action'],
          rows: [
            ['Lisinopril', '20 mg daily', 'Stopped', 'Discontinued - replaced by sacubitril/valsartan'],
            ['Sacubitril/valsartan', '--', '24/26 mg BID', 'Continue'],
            ['Furosemide', '20 mg daily', '40 mg BID', 'Continue 40 mg BID'],
            ['Spironolactone', '--', '25 mg daily', 'Continue'],
            ['Metoprolol succinate ER', '25 mg daily', '50 mg daily', 'Continue 50 mg daily'],
            ['Atorvastatin', '40 mg daily', '40 mg daily', 'Continue'],
            ['Naproxen (OTC)', 'As needed', 'Not listed', 'STOP - avoid NSAIDs with HF/CKD'],
          ] } },
        { kv: [['Medication Reconciliation Completed', 'Yes'], ['Completed by', 'DANIEL KIM, MD'], ['Date', '07/15/2024']] },
        { comment: 'Discharge medications reconciled with the current outpatient medication list. Patient and wife instructed; updated list provided.' },
        { section: 'Labs' },
        { grid: { headers: ['Lab Test', '07/15/24', '07/06/24', '07/02/24'],
          rows: [['POTASSIUM', '4.5', '4.3', '3.9'], ['CREATININE', '1.31 H', '1.38 H', '1.52 H'], ['BNP', '412 H', '', '1,860 H'], ['SODIUM', '137', '136', '134 L']] } },
        { section: 'Problem List' },
        { problems: [
          ['Chronic systolic (congestive) heart failure (I50.22)', 'Euvolemic post discharge. Continue GDMT; cardiology 07/29/2024.'],
          ['Chronic kidney disease, stage 3a (N18.31)', 'Creatinine improving; recheck BMP 1 week.'],
        ] },
      ],
    },
  ],
};

// ---------------------------------------------------------------- WCC
// Weight Assessment and Counseling for Nutrition and Physical Activity for
// Children/Adolescents (3-17). Evidence: height, weight and BMI percentile,
// counseling for nutrition, counseling for physical activity - same visit.
const WCC = {
  measure: 'WCC', measureName: 'Weight Assessment and Counseling for Nutrition and Physical Activity for Children/Adolescents', docId: '24103478', printed: PRINTED,
  patient: { name: 'Ramirez, Sofia', dob: '03/19/2013', gender: 'Female' },
  encounters: [{
    visitDate: '05/20/2024', provider: 'KEVIN LIU, MD', signedAt: '05/20/2024 04:05 PM',
    blocks: [
      { section: 'Well Child Visit' },
      { kv: [['Services are being rendered at', 'SUNNYBROOK PEDIATRICS'], ['Visit Type', '11 year well child check'], ['Accompanied by', 'Mother']] },
      { sub: 'Overall Patient Status' },
      { kv: [['Patient', 'Healthy'], ['Interval History', 'No illnesses or ER visits since last visit. Doing well in 5th grade.']] },

      { section: 'Growth & Vitals' },
      { kv: [['Height', '146.2 cm (57.6 in)'], ['Weight', '45.8 kg (101.0 lbs)'], ['BMI', '21.4 kg/m2'], ['BMI Percentile for age/sex', '88th percentile'], ['BP', '104/66'], ['Pulse', '84 bpm']] },
      { grid: { headers: ['Growth', '05/20/24', '05/15/23', '05/11/22'],
        rows: [['Height (cm)', '146.2', '139.8', '133.5'], ['Weight (kg)', '45.8', '40.1', '34.6'], ['BMI (kg/m2)', '21.4', '20.5', '19.4'], ['BMI Percentile', '88th', '86th', '83rd']] } },
      { status: ['BMI Percentile: 88th-05/20/24 - Overweight range (85th-94th)'] },

      { section: 'Nutrition Counseling' },
      { kv: [['Counseling Provided', 'Yes'], ['Diet History', '2 sugar-sweetened drinks per day, fast food 2-3 times per week, few vegetables']] },
      { comment: 'Counseled patient and mother on nutrition: 5 servings of fruits and vegetables daily, replace soda/juice with water or low-fat milk, limit fast food to once per week, family meals and portion sizes. "Healthy Eating for Kids" handout given.' },

      { section: 'Physical Activity Counseling' },
      { kv: [['Counseling Provided', 'Yes'], ['Current Activity', 'PE class 2x/week; about 3 hours/day recreational screen time']] },
      { comment: 'Discussed goal of at least 60 minutes of moderate to vigorous physical activity daily. Patient interested in joining community soccer this summer. Recommended limiting recreational screen time to under 2 hours per day.' },

      { section: 'Physical Exam' },
      { sub: 'General Appearance' }, { kv: [['Appearance', 'Well appearing, active, in no distress']] },
      { sub: 'HEENT' }, { kv: [['Status', 'Normal']] },
      { sub: 'Lungs' }, { kv: [['Status', 'Normal']] },
      { sub: 'Heart' }, { kv: [['Status', 'Normal']] }, { comment: 'RRR, no murmur.' },
      { sub: 'Skin' }, { kv: [['Status', 'Normal - no acanthosis nigricans']] },

      { section: 'Screening & Immunizations' },
      { kv: [['Vision', '20/20 OU'], ['Hearing', 'Pass'], ['Development / School', 'Age appropriate'], ['Immunizations', 'Tdap and MenACWY due at 11 - administered today; HPV dose 1 administered today']] },

      { section: 'Problem List' },
      { problems: [
        ['Encounter for routine child health examination without abnormal findings (Z00.129)', '11 year well visit.'],
        ['Body mass index [BMI] pediatric, 85th percentile to less than 95th percentile for age (Z68.53)', 'BMI 88th percentile; nutrition and physical activity counseling provided.'],
        ['Dietary counseling and surveillance (Z71.3)', 'Nutrition counseling as above.'],
        ['Counseling on physical activity (Z71.82)', 'Exercise counseling as above.'],
      ] },
    ],
  }],
};

module.exports = [CBP, COA, GSD, PPC, TRC, WCC];
