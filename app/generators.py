import random
import string
from faker import Faker

fake = Faker()

ICD10_CODES = [
    ("J18.9", "Pneumonia, unspecified organism"),
    ("I10", "Essential hypertension"),
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("M54.5", "Low back pain"),
    ("J06.9", "Acute upper respiratory infection"),
    ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
    ("F32.9", "Major depressive disorder, single episode"),
    ("N39.0", "Urinary tract infection, site not specified"),
    ("J44.1", "Chronic obstructive pulmonary disease with acute exacerbation"),
    ("G43.909", "Migraine, unspecified, not intractable"),
]

MEDICATIONS = [
    ("Amoxicillin", "500mg"), ("Lisinopril", "10mg"), ("Metformin", "850mg"),
    ("Omeprazole", "20mg"), ("Atorvastatin", "40mg"), ("Amlodipine", "5mg"),
    ("Metoprolol", "25mg"), ("Sertraline", "50mg"), ("Albuterol", "90mcg"),
    ("Prednisone", "10mg"), ("Levothyroxine", "50mcg"), ("Gabapentin", "300mg"),
]

INSURANCE_PREFIXES = ["BCB", "UHC", "AET", "CIG", "HUM", "KAI", "ANT", "MOL"]

LAB_TESTS = [
    ("HbA1c", "{:.1f}", "%", 4.0, 14.0),
    ("Glucose", "{:.0f}", "mg/dL", 60, 400),
    ("WBC", "{:.1f}", "x10^3/uL", 2.0, 20.0),
    ("Hemoglobin", "{:.1f}", "g/dL", 7.0, 18.0),
    ("Creatinine", "{:.2f}", "mg/dL", 0.5, 5.0),
    ("Potassium", "{:.1f}", "mEq/L", 2.5, 6.5),
    ("TSH", "{:.2f}", "mIU/L", 0.1, 10.0),
    ("Cholesterol", "{:.0f}", "mg/dL", 120, 350),
]


def _gen_ssn() -> str:
    area = random.randint(100, 899)
    group = random.randint(1, 99)
    serial = random.randint(1, 9999)
    return f"{area:03d}-{group:02d}-{serial:04d}"


def _gen_name() -> str:
    return fake.name()


def _gen_email() -> str:
    return fake.email()


def _gen_phone() -> str:
    # Generate exactly 10 digits as (XXX) XXX-XXXX to avoid Faker's
    # inconsistent formats that may include country codes (+1 = 11 digits)
    area = random.randint(200, 999)
    exchange = random.randint(200, 999)
    subscriber = random.randint(0, 9999)
    return f"({area:03d}) {exchange:03d}-{subscriber:04d}"


def _gen_address() -> str:
    return fake.address().replace("\n", ", ")


def _gen_dob() -> str:
    return fake.date_of_birth(minimum_age=18, maximum_age=90).strftime("%m/%d/%Y")


def _gen_drivers_license() -> str:
    state = fake.state_abbr()
    num = "".join(random.choices(string.digits, k=8))
    return f"{state}-{num}"


def _gen_credit_card() -> str:
    return fake.credit_card_number()


def _gen_mrn() -> str:
    num = random.randint(0, 999999)
    return f"MRN-{num:06d}"


def _gen_diagnosis() -> str:
    code, desc = random.choice(ICD10_CODES)
    return f"{code} - {desc}"


def _gen_medication() -> str:
    drug, dose = random.choice(MEDICATIONS)
    return f"{drug} {dose}"


def _gen_provider() -> str:
    return f"Dr. {fake.first_name()} {fake.last_name()}"


def _gen_insurance_id() -> str:
    prefix = random.choice(INSURANCE_PREFIXES)
    num = random.randint(1000000, 9999999)
    return f"{prefix}-{num}"


def _gen_admission_date() -> str:
    return fake.date_between(start_date="-2y", end_date="today").strftime("%m/%d/%Y")


def _gen_lab_result() -> str:
    test_name, fmt, unit, low, high = random.choice(LAB_TESTS)
    value = random.uniform(low, high)
    return f"{test_name} {fmt.format(value)} {unit}"


GENERATOR_REGISTRY: dict[str, callable] = {
    "ssn": _gen_ssn,
    "name": _gen_name,
    "email": _gen_email,
    "phone": _gen_phone,
    "address": _gen_address,
    "dob": _gen_dob,
    "drivers_license": _gen_drivers_license,
    "credit_card": _gen_credit_card,
    "mrn": _gen_mrn,
    "diagnosis": _gen_diagnosis,
    "medication": _gen_medication,
    "provider": _gen_provider,
    "insurance_id": _gen_insurance_id,
    "admission_date": _gen_admission_date,
    "lab_result": _gen_lab_result,
}


def generate_value(gen_type: str) -> str:
    if gen_type not in GENERATOR_REGISTRY:
        raise ValueError(f"Unknown generator type: {gen_type}")
    return GENERATOR_REGISTRY[gen_type]()


def generate_all(gen_types: list[str]) -> dict[str, str]:
    return {t: generate_value(t) for t in gen_types}
