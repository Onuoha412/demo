from pathlib import Path


def test_demo_seed_contains_required_records() -> None:
    seed = (Path(__file__).resolve().parents[2] / "database" / "seeds" / "demo_data.sql").read_text()
    for name in ("Babcock University", "Student Affairs", "Admissions", "Finance", "ICT Support", "Medical Centre"):
        assert name in seed
