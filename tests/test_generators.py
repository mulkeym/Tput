import re
from app.generators import generate_value, GENERATOR_REGISTRY, generate_all


class TestGenerateValue:
    def test_ssn_format(self):
        val = generate_value("ssn")
        assert re.match(r"^\d{3}-\d{2}-\d{4}$", val)

    def test_name_is_two_words(self):
        val = generate_value("name")
        parts = val.strip().split()
        assert len(parts) >= 2

    def test_email_has_at_sign(self):
        val = generate_value("email")
        assert "@" in val

    def test_phone_format(self):
        val = generate_value("phone")
        digits = re.sub(r"\D", "", val)
        assert len(digits) == 10

    def test_address_nonempty(self):
        val = generate_value("address")
        assert len(val) > 10

    def test_dob_date_format(self):
        val = generate_value("dob")
        assert re.match(r"^\d{2}/\d{2}/\d{4}$", val)

    def test_drivers_license_nonempty(self):
        val = generate_value("drivers_license")
        assert len(val) > 3

    def test_credit_card_format(self):
        val = generate_value("credit_card")
        digits = re.sub(r"\D", "", val)
        assert len(digits) >= 12

    def test_mrn_format(self):
        val = generate_value("mrn")
        assert val.startswith("MRN-")
        assert len(val) == 10

    def test_diagnosis_has_code(self):
        val = generate_value("diagnosis")
        assert re.search(r"[A-Z]\d+", val)

    def test_medication_nonempty(self):
        val = generate_value("medication")
        assert len(val) > 3

    def test_provider_starts_with_dr(self):
        val = generate_value("provider")
        assert val.startswith("Dr.")

    def test_insurance_id_format(self):
        val = generate_value("insurance_id")
        assert re.match(r"^[A-Z]+-\d+$", val)

    def test_admission_date_format(self):
        val = generate_value("admission_date")
        assert re.match(r"^\d{2}/\d{2}/\d{4}$", val)

    def test_lab_result_has_value(self):
        val = generate_value("lab_result")
        assert re.search(r"\d", val)

    def test_unknown_generator_raises(self):
        try:
            generate_value("nonexistent_type")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestGenerateAll:
    def test_returns_dict_with_requested_keys(self):
        result = generate_all(["name", "ssn", "mrn"])
        assert "name" in result
        assert "ssn" in result
        assert "mrn" in result

    def test_each_call_produces_unique_values(self):
        results = [generate_all(["ssn"]) for _ in range(20)]
        ssns = [r["ssn"] for r in results]
        assert len(set(ssns)) > 1


class TestRegistryCompleteness:
    def test_all_pii_types_registered(self):
        pii_types = ["ssn", "name", "email", "phone", "address", "dob",
                     "drivers_license", "credit_card"]
        for t in pii_types:
            assert t in GENERATOR_REGISTRY

    def test_all_phi_types_registered(self):
        phi_types = ["mrn", "diagnosis", "medication", "provider",
                     "insurance_id", "admission_date", "lab_result"]
        for t in phi_types:
            assert t in GENERATOR_REGISTRY
